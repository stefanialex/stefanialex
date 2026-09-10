#!/usr/bin/env python3
"""Rapport statistique du serveur Valheim, a partir de la base du collecteur.

Ne lit rien du journal : tout vient de valheim.db, alimentee par
collecte-valheim.py. Sortie texte pour le terminal, ou JSON pour la page
Cockpit avec --json.
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"
OUTIL_MONDE = "/usr/local/bin/monde-valheim.py"
OBJECTIFS = "/etc/valheim/objectifs.json"
CHANTIERS = "/etc/valheim/chantiers.json"


def metadonnees_monde(cx):
    """Seed et versions des mondes, relevees par le collecteur.

    Le rapport ne lit pas le .fwl lui-meme : /var/lib/valheim est en 0750 et
    n'est lisible que par l'utilisateur valheim. Le collecteur, qui tourne sous
    cet utilisateur, a deja depose ces metadonnees en base -- la page Cockpit
    n'a donc besoin d'aucun privilege pour les afficher.
    """
    lignes = cx.execute(
        "SELECT monde, seed, seed_entiere, version_format, version_generateur, "
        "premiere_vue, derniere_vue FROM mondes ORDER BY derniere_vue DESC").fetchall()
    cles = ("monde", "seed", "seed_entiere", "version_format",
            "version_generateur", "premiere_vue", "derniere_vue")
    return [dict(zip(cles, l)) for l in lignes]

# Les boss, par leur cle interne. La progression exacte vient des global keys
# du fichier de monde, relevees par cles-monde-valheim.py.
BOSS = [
    ("defeated_eikthyr", "Eikthyr"),
    ("defeated_gdking", "l'Ancien"),
    ("defeated_bonemass", "Bonemass"),
    ("defeated_dragon", "Moder"),
    ("defeated_goblinking", "Yagluth"),
    ("defeated_queen", "la Reine"),
    ("defeated_fader", "Fader"),
]

# Le nom que Valheim donne au lieu d'invocation, tel qu'il sort de « Found
# location of type X », rapporte au boss qu'on y appelle. Les cinq premiers
# sont verifies sur nos propres journaux : Midgard a vu Eikthyrnir, GDKing,
# Bonemass et Dragonqueen, chaque fois plusieurs heures avant la mise a mort.
# Les deux derniers ne le sont pas -- aucun des deux n'est encore apparu chez
# nous -- et un lieu inconnu s'affiche sous son nom brut plutot que d'etre
# tu : mieux vaut un nom illisible qu'un autel invisible.
AUTELS = {
    "Eikthyrnir": "defeated_eikthyr",
    "GDKing": "defeated_gdking",
    "Bonemass": "defeated_bonemass",
    "Dragonqueen": "defeated_dragon",
    "GoblinKing": "defeated_goblinking",
    "Mistlands_DvergrBossEntrance1": "defeated_queen",   # non verifie
    "FaderLocation": "defeated_fader",                   # non verifie
}

# Les donjons, sous le nom que le serveur leur donne en les peuplant. Le type
# dit le biome, donc la courbe raconte ce que le groupe farme.
#
# Le pluriel est ecrit a la main plutot que devine. Une regle mecanique se
# trompe des le deuxieme cas : « ferme abandonnee » demande l'accord des DEUX
# mots, « crypte de Foret-Noire » celui du premier seul. Huit lignes de table
# valent mieux qu'une heuristique qui a l'air de marcher.
DONJONS = {
    "DG_ForestCrypt": ("crypte de Forêt-Noire", "cryptes de Forêt-Noire"),
    "DG_SunkenCrypt": ("crypte engloutie", "cryptes englouties"),
    "DG_Cave": ("grotte gelée", "grottes gelées"),
    "DG_GoblinCamp": ("camp de Fulings", "camps de Fulings"),
    "DG_MeadowsFarm": ("ferme abandonnée", "fermes abandonnées"),
    "DG_MeadowsVillage": ("village abandonné", "villages abandonnés"),
    "DG_DvergrTown": ("cité des Dvergrs", "cités des Dvergrs"),
    "DG_DvergrBossEntrance": ("mine infestée", "mines infestées"),
}
NOM_BOSS = dict(BOSS)

# Quel raid exige quelle cle. Attention, ce n'est PAS le boss du meme nom : un
# raid se debloque avec le boss PRECEDENT. « army_theelder » exige
# defeated_eikthyr et non defeated_gdking ; « army_bonemass » exige
# defeated_gdking. Deduire la progression du nom des raids -- ce que faisait la
# premiere version -- decalait donc toute la lecture d'un boss.
# Verifie sur ce serveur : army_bonemass s'etait declenche alors que
# defeated_bonemass est absent du fichier de monde.
RAID_EXIGE = {
    # « army_eikthyr » n'exige RIEN : c'est le premier raid, disponible des le
    # depart. La table le faisait dependre de defeated_eikthyr, ce qui
    # contredisait la regle enoncee juste au-dessus -- un raid se debloque avec
    # le boss PRECEDENT, et il n'y a pas de boss avant Eikthyr. Observe le
    # 2026-09-09 sur NordheimV2 : un army_eikthyr s'est declenche a 22h33 alors
    # que le monde ne portait aucune cle globale.
    "army_theelder": "defeated_eikthyr",
    "army_bonemass": "defeated_gdking",
    "army_moder": "defeated_bonemass",     # deduit du meme motif
    "army_goblin": "defeated_dragon",      # deduit du meme motif
}


def duree(secondes):
    s = int(secondes)
    if s < 3600:
        return "%d min" % (s // 60)
    h, m = divmod(s // 60, 60)
    return "%d h %02d" % (h, m)


def monde_actif(cx):
    """Le monde le plus recemment vu par le collecteur."""
    r = cx.execute("SELECT monde FROM mondes ORDER BY derniere_vue DESC LIMIT 1").fetchone()
    return r[0] if r else None


def charge(cx, monde=None):
    """Reconstitue les sessions, les morts et la progression d'un monde.

    Le cloisonnement par monde n'est pas cosmetique : a partir du 9 septembre,
    les evenements de Midgard et ceux de NordheimV1 cohabitent en base. Sans
    filtre, les morts de l'ancien monde compteraient dans les defis du nouveau.
    """
    ou = ""
    arg = ()
    if monde:
        ou = " AND monde = ?"
        arg = (monde,)
    ident = {sid: pseudo for sid, pseudo in
             cx.execute("SELECT steamid, pseudo FROM joueurs")}

    # Sessions : on apparie chaque connexion a la deconnexion suivante du meme
    # SteamID. Une session sans deconnexion est en cours.
    ouvertes, sessions = {}, []
    for ts, typ, sid in cx.execute(
            "SELECT horodatage, type, steamid FROM evenements "
            "WHERE type IN ('connexion', 'deconnexion')" + ou +
            " ORDER BY horodatage, id", arg):
        t = datetime.fromisoformat(ts)
        if typ == "connexion":
            ouvertes[sid] = t
        elif sid in ouvertes:
            sessions.append((sid, ouvertes.pop(sid), t, False))
    maintenant = datetime.now()
    for sid, debut in ouvertes.items():
        sessions.append((sid, debut, maintenant, True))

    morts = {}
    for joueur, ts in cx.execute(
            "SELECT joueur, horodatage FROM evenements WHERE type = 'mort'" + ou +
            " ORDER BY horodatage", arg):
        morts.setdefault(joueur, []).append(ts)

    progression = {}
    for detail, ts in cx.execute(
            "SELECT detail, min(horodatage) FROM evenements WHERE type = 'raid'" + ou +
            " GROUP BY detail", arg):
        progression[detail] = ts

    infos = cx.execute(
        "SELECT monde, max(horodatage), detail FROM evenements "
        "WHERE type = 'sauvegarde'" + ou, arg).fetchone()
    jour = cx.execute(
        "SELECT detail FROM evenements WHERE type = 'jour'" + ou +
        " ORDER BY horodatage DESC LIMIT 1", arg).fetchone()

    return ident, sessions, morts, progression, infos, jour


def attribue_par_presence(cx, monde, ident, sessions):
    """Credite les evenements de groupe aux joueurs en ligne a cet instant.

    Les zones neuves, les entrees de donjon et les raids ne portent aucun nom :
    le serveur ne dit pas qui les a declenches. Mais il dit qui etait connecte,
    a la seconde. Croiser les deux rend ces mesures nominatives -- et
    indiscutables quand un seul joueur etait en ligne.

    Le credit est partage entre les presents plutot que donne a chacun en
    entier. Sans ce partage, une soiree a quatre vaudrait quatre fois une
    soiree en solo pour la meme exploration, et le classement mesurerait la
    taille du groupe au lieu du travail fourni. Le compte « solo » est garde a
    part : c'est le seul chiffre que personne ne peut contester.

    Verifie sur Midgard le 2026-09-09 : 1096 zones creditees, aucune orpheline
    -- toutes ont ete generees avec au moins un joueur connecte, ce qui
    confirme que la ligne du journal marque bien une decouverte et non un
    rechargement de terrain par le serveur.
    """
    ou, arg = "", ()
    if monde:
        ou, arg = " AND monde = ?", (monde,)

    intervalles = [(ident.get(sid, sid), debut, fin)
                   for sid, debut, fin, _en_cours in sessions]

    def presents(quand):
        return sorted({p for p, a, b in intervalles if a <= quand <= b})

    res = {}

    def entree(p):
        return res.setdefault(p, {"zones": 0.0, "zones_solo": 0, "donjons": 0.0,
                                  "donjons_solo": 0, "raids_vus": 0,
                                  "raids_tenus": 0})

    orphelins = {"zone": 0, "donjon": 0, "raid": 0}
    # Les zones sont dedoublonnees sur leur coordonnee et datees a leur premiere
    # apparition : depuis la 1.0, le serveur ecrit une ligne par lieu pose et
    # non une par zone, donc compter les evenements gonflerait le chiffre d'un
    # facteur variable. La premiere apparition est aussi la bonne date : c'est
    # l'instant de la decouverte.
    # Les donjons, eux, ne sont PAS dedoublonnes : leur detail est le type
    # (DG_ForestCrypt), donc regrouper reduirait toutes les cryptes a une.
    requetes = {
        "zone": ("SELECT min(horodatage) FROM evenements WHERE type = 'zone'"
                 + ou + " GROUP BY detail", arg),
        "donjon": ("SELECT horodatage FROM evenements WHERE type = 'donjon'"
                   + ou, arg),
    }
    for typ in ("zone", "donjon"):
        requete, parametres = requetes[typ]
        for (h,) in cx.execute(requete, parametres):
            qui = presents(datetime.fromisoformat(h))
            if not qui:
                orphelins[typ] += 1
                continue
            cle = "zones" if typ == "zone" else "donjons"
            for p in qui:
                entree(p)[cle] += 1.0 / len(qui)
            if len(qui) == 1:
                entree(qui[0])[cle + "_solo"] += 1

    # Un raid est « tenu » si personne ne meurt dans les cinq minutes qui
    # suivent : meme fenetre que le KPI d'equipe, pour que les deux chiffres
    # racontent la meme histoire.
    morts_h = [datetime.fromisoformat(h) for (h,) in cx.execute(
        "SELECT horodatage FROM evenements WHERE type = 'mort'" + ou, arg)]
    for (h,) in cx.execute(
            "SELECT horodatage FROM evenements WHERE type = 'raid'" + ou, arg):
        d = datetime.fromisoformat(h)
        qui = presents(d)
        if not qui:
            orphelins["raid"] += 1
            continue
        perdu = any(d <= m <= d + timedelta(minutes=5) for m in morts_h)
        for p in qui:
            e = entree(p)
            e["raids_vus"] += 1
            if not perdu:
                e["raids_tenus"] += 1

    # Ramene au temps de jeu, parce que le brut ne mesure pas le talent mais la
    # presence. Constate sur Midgard : Bab-y finissait derniere de tout avec 17
    # sessions quand Beny en avait 81. Un classement qui met toujours la meme
    # personne au dernier rang ne donne envie a personne, et il est faux.
    heures = {}
    for p, a_, b_ in intervalles:
        heures[p] = heures.get(p, 0.0) + max(0.0, (b_ - a_).total_seconds()) / 3600.0

    for p, e in res.items():
        h = heures.get(p, 0.0)
        e["heures"] = round(h, 1)
        e["zones"] = round(e["zones"], 1)
        e["donjons"] = round(e["donjons"], 1)
        # Sous une heure de jeu, un rapport a l'heure raconte n'importe quoi :
        # une zone en dix minutes ferait six zones par heure.
        e["zones_par_heure"] = round(e["zones"] / h, 1) if h >= 1 else None
        e["donjons_par_heure"] = round(e["donjons"] / h, 2) if h >= 1 else None
        e["raids_taux"] = (round(100 * e["raids_tenus"] / e["raids_vus"])
                           if e["raids_vus"] else None)
    return {"joueurs": res, "sans_personne_en_ligne": orphelins}


# Les roles de la feuille de Baby, et la mesure qui leur correspond quand elle
# existe. Trois seulement sont mesurables aujourd'hui ; les autres restent
# declaratifs et c'est dit tel quel, plutot que de bricoler un chiffre qui n'en
# est pas un. « Happynes manager » est un role de vanne, il le reste.
ROLES_MESURES = {
    "Explorateur": ("zones", "zones neuves", "zones_par_heure"),
}
# Les donjons et les raids ne correspondent a aucun role de la feuille : ils
# sont publies comme mesures de groupe, par joueur, sans pretendre arbitrer un
# titre. Forcer « Capitaine de navire » sur les donjons aurait donne un chiffre
# qui ne veut rien dire -- essaye, puis retire.


def roles(cx, monde, ident, sessions):
    """Chaque role declare, confronte a la mesure quand il y en a une."""
    c = chantiers()
    if not c:
        return None
    presence = attribue_par_presence(cx, monde, ident, sessions)
    par = presence["joueurs"]
    # La feuille nomme les joueurs « Lapin, Beny, Djoose, Baby » ; les mesures
    # les nomment par leur pseudo en jeu. La table des joueurs de chantiers.json
    # fait le pont.
    pseudo_de = {n: (d.get("pseudo") or n) for n, d in (c.get("joueurs") or {}).items()}

    sortie = []
    for f in c.get("fonctions") or []:
        nom = f.get("nom", "")
        titulaires = f.get("titulaires") or []
        mesure = ROLES_MESURES.get(nom)
        entree = {"role": nom, "titulaires": titulaires,
                  "mesure": mesure[1] if mesure else None,
                  "classement": None, "titulaire_en_tete": None,
                  "pseudos_inconnus": None}
        if mesure:
            cle, _libelle, cle_rendement = mesure
            classement = sorted(
                ((p, e.get(cle) or 0, e.get(cle_rendement), e.get("heures"))
                 for p, e in par.items() if e.get(cle)),
                # Au rendement quand il est calculable pour tout le monde,
                # sinon au brut : c'est la demande d'Alexandre du 2026-09-09,
                # « adapter les chiffres en fonction du temps de jeu ».
                key=lambda t: -(t[2] if t[2] is not None else 0))
            entree["classement"] = [
                {"joueur": p, "valeur": v, "par_heure": r, "heures": h}
                for p, v, r, h in classement]
            # La feuille nomme les personnages, pas les personnes, et un
            # personnage neuf change de nom. Plutot que d'annoncer « le
            # titulaire n'est pas en tete » -- une accusation fausse -- on dit
            # qu'on ne sait pas, et lequel des pseudos manque a l'appel.
            # Comparaison sur des noms nettoyes des deux cotes : « Bab-y » est
            # enregistre avec une espace finale par le jeu, ce qui l'avait deja
            # fait disparaitre d'un releve le 2026-09-09.
            tetes = {(pseudo_de.get(t, t) or "").strip() for t in titulaires}
            mesures = {(p or "").strip() for p, _v, _r, _h in classement}
            manquants = sorted(tetes - mesures)
            entree["pseudos_inconnus"] = manquants or None
            # On ne tranche que si TOUS les titulaires sont identifiables. Avec
            # un seul pseudo perime, le verdict serait une accusation fausse :
            # le 2026-09-09 la feuille disait « Lapin -> Brewtmoiminou », or
            # Lapin jouait LapInV, et le script annoncait que le titulaire
            # n'etait pas en tete alors qu'il menait de quatre longueurs.
            if classement and not manquants:
                entree["titulaire_en_tete"] = classement[0][0].strip() in tetes
        sortie.append(entree)
    return {"roles": sortie, "presence": presence}


def par_joueur(ident, sessions, morts):
    """Agrege sessions et morts par joueur, indexe par pseudo."""
    res = {}
    for sid, debut, fin, en_cours in sessions:
        pseudo = ident.get(sid, "SteamID %s" % sid)
        e = res.setdefault(pseudo, {"steamid": sid, "sessions": 0, "temps": 0.0,
                                    "morts": 0, "derniere": None, "en_cours": False})
        e["sessions"] += 1
        e["temps"] += (fin - debut).total_seconds()
        e["en_cours"] = e["en_cours"] or en_cours
        d = fin.isoformat(sep=" ", timespec="seconds")
        if not e["derniere"] or d > e["derniere"]:
            e["derniere"] = d
    for pseudo, dates in morts.items():
        e = res.setdefault(pseudo, {"steamid": None, "sessions": 0, "temps": 0.0,
                                    "morts": 0, "derniere": None, "en_cours": False})
        e["morts"] = len(dates)
    return res


def defi_baby(morts, boss_vaincus):
    """« Au moins un joueur encore jamais mort apres avoir battu l'Ancien. »

    Le defi propose par Bab-y. L'ancrage vient de la cle defeated_gdking du
    fichier de monde, et non plus du raid « army_theelder » : ce raid se
    declenche apres Eikthyr, pas apres l'Ancien, et le defi comptait donc les
    morts depuis une date trop precoce.
    """
    depuis = next((e["date"] for e in boss_vaincus
                   if e["cle"] == "defeated_gdking"), None)
    if not depuis:
        return None
    tenants, tombes = [], {}
    joueurs = set(morts) | set()
    for j in joueurs:
        apres = [d for d in morts.get(j, []) if d >= depuis]
        if apres:
            tombes[j] = (len(apres), apres[0])
        else:
            tenants.append(j)
    return {"depuis": depuis, "tenants": tenants, "tombes": tombes}


def progression_boss(cx, monde, progression_raids):
    """Boss vaincus, avec la meilleure date connue pour chacun.

    Deux sources, dans cet ordre. Les global keys du fichier de monde disent
    avec certitude qui est tombe ; quand la routine a observe le passage
    d'absente a presente, la date est exacte. Sinon -- cle deja la au premier
    releve -- on cherche une borne haute : le premier raid qui exige cette cle
    prouve qu'elle existait deja a ce moment.
    """
    cles = {}
    try:
        for cle, vue, certaine in cx.execute(
                "SELECT cle, premiere_vue, certaine FROM cles_globales WHERE monde = ?",
                (monde,)):
            cles[cle] = {"date": vue, "certaine": bool(certaine)}
    except sqlite3.OperationalError:
        return []  # la routine n'a pas encore tourne

    # Borne haute par les raids, avec la correspondance exacte raid -> cle.
    bornes = {}
    for raid, ts in progression_raids.items():
        exigee = RAID_EXIGE.get(raid)
        if exigee and (exigee not in bornes or ts < bornes[exigee]):
            bornes[exigee] = ts

    resultat = []
    for cle, nom in BOSS:
        if cle not in cles:
            continue
        e = cles[cle]
        date, exacte = e["date"], e["certaine"]
        if not exacte and cle in bornes:
            date, exacte = bornes[cle], False
        resultat.append({"cle": cle, "boss": nom, "date": date, "exacte": exacte})
    return resultat


def defis(agg, morts, progression, sessions, ident, boss_vaincus):
    """Construit le tableau des defis, mesures et non declaratifs.

    Seules des metriques calculables depuis le journal sont retenues : un defi
    qu'on ne peut pas verifier automatiquement n'a pas sa place ici, il finirait
    en dispute. « Pas de portail » ou « pacifiste » relevent de l'honneur et
    restent volontairement dehors.
    """
    maintenant = datetime.now()
    liste = []

    # 1. Le defi de Bab-y, generalise a chaque boss dont on a la date.
    for etape in boss_vaincus:
        cle, boss, depuis = etape["cle"], etape["boss"], etape["date"]
        rangs = []
        for pseudo, e in agg.items():
            apres = [d for d in morts.get(pseudo, []) if d >= depuis]
            rangs.append({"joueur": pseudo, "valeur": len(apres),
                          "tient": not apres,
                          "note": "intact" if not apres
                                  else "première mort le %s" % apres[0][:16]})
        liste.append({
            "nom": "Intact depuis %s" % boss,
            "regle": "n'être jamais mort depuis la chute de %s" % boss,
            "metrique": "morts enregistrées après le %s" % depuis[:16],
            "sens": "moins", "rangs": sorted(rangs, key=lambda r: r["valeur"]),
        })

    # 2. Morts par heure de jeu : plus juste qu'un total brut, qui punit
    #    seulement celui qui joue le plus.
    rangs = []
    for pseudo, e in agg.items():
        heures = e["temps"] / 3600.0
        if heures < 1:
            continue
        rangs.append({"joueur": pseudo, "valeur": round(e["morts"] / heures, 2),
                      "tient": None,
                      "note": "%d morts en %s" % (e["morts"], duree(e["temps"]))})
    if rangs:
        liste.append({
            "nom": "Le plus solide",
            "regle": "le moins de morts par heure de jeu",
            "metrique": "morts / heures de session",
            "sens": "moins", "rangs": sorted(rangs, key=lambda r: r["valeur"]),
        })

    # 3. Serie en cours sans mourir. La metrique qui se regarde en direct.
    rangs = []
    for pseudo, e in agg.items():
        dates = morts.get(pseudo, [])
        depart = datetime.fromisoformat(dates[-1]) if dates else None
        if depart is None:
            # Jamais mort : la serie court depuis la premiere session.
            debuts = [d for sid, d, _f, _c in sessions if ident.get(sid) == pseudo]
            depart = min(debuts) if debuts else maintenant
        rangs.append({"joueur": pseudo,
                      "valeur": int((maintenant - depart).total_seconds()),
                      "tient": None,
                      "note": "depuis le %s" % depart.isoformat(sep=" ")[:16]})
    if rangs:
        liste.append({
            "nom": "Série en cours",
            "regle": "le plus longtemps sans mourir, en temps réel",
            "metrique": "temps écoulé depuis la dernière mort",
            "sens": "plus", "rangs": sorted(rangs, key=lambda r: -r["valeur"]),
            "unite": "duree",
        })

    # 4. Vitesse de progression du groupe entre deux boss.
    etapes = sorted((e["date"], e["boss"]) for e in boss_vaincus)
    if len(etapes) >= 2:
        rangs = []
        for (t1, b1), (t2, b2) in zip(etapes, etapes[1:]):
            ecart = datetime.fromisoformat(t2) - datetime.fromisoformat(t1)
            rangs.append({"joueur": "%s -> %s" % (b1, b2),
                          "valeur": int(ecart.total_seconds()),
                          "tient": None, "note": "du %s au %s" % (t1[:10], t2[:10])})
        liste.append({
            "nom": "Rythme du groupe",
            "regle": "temps écoulé entre deux boss",
            "metrique": "écart entre deux victoires consécutives",
            "sens": "moins", "rangs": rangs, "unite": "duree",
        })

    return liste


# ---------- KPI et objectifs ----------

def objectifs():
    """Liste des KPI et de leurs cibles, hors du code.

    Les indicateurs et les objectifs d'un groupe changent en cours de partie ;
    les recompiler n'aurait pas de sens. Le fichier est modifiable a la main,
    et son absence n'est pas une erreur : la page affiche alors les seules
    statistiques brutes.
    """
    try:
        with open(OBJECTIFS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def chantiers():
    """Fonctions et chantiers declares, tenus a la main.

    Rien la-dedans n'est mesurable depuis le serveur : il ne voit ni la
    cuisine, ni le bucheronnage, ni un port acheve. C'est renvoye sous une cle
    distincte des KPI mesures, pour qu'un affichage ne puisse pas faire passer
    un declaratif pour une mesure.
    """
    try:
        with open(CHANTIERS, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    total = len(d.get("chantiers", []))
    faits = sum(1 for c in d.get("chantiers", []) if c.get("etat") == "fait")
    d["avancement"] = {"faits": faits, "total": total,
                       "part": round(faits / total, 3) if total else None}
    return d


def temps_cumule(sessions, jusqu_a=None):
    """Temps de jeu additionne de tout le groupe, eventuellement arrete a une date.

    Les sessions se chevauchent quand plusieurs jouent ensemble, et c'est
    voulu : on mesure l'effort du groupe, pas la duree calendaire.
    """
    total = 0.0
    for _sid, debut, fin, _en_cours in sessions:
        if jusqu_a is not None:
            if debut >= jusqu_a:
                continue
            fin = min(fin, jusqu_a)
        total += max(0.0, (fin - debut).total_seconds())
    return total


def raids_tenus(cx, monde, fenetre=timedelta(minutes=5)):
    """Les raids traverses sans une seule mort.

    Un raid dure environ deux minutes en jeu, plus le temps d'achever les
    derniers assaillants : on regarde donc les cinq minutes qui suivent son
    apparition. La fenetre est genereuse a dessein -- mieux vaut refuser un
    raid tenu de justesse que d'en compter un ou quelqu'un est mort.

    C'est le seul defi qui recompense la coordination plutot que la
    performance individuelle : une seule mort et le raid ne compte pas, quel
    que soit le joueur. Le filtre par monde suit la meme regle que charge() --
    les 26 raids de Midgard n'ont pas a nourrir les defis de NordheimV1.
    """
    ou, arg = "", ()
    if monde:
        ou, arg = " AND monde = ?", (monde,)
    raids = [datetime.fromisoformat(d) for (d,) in cx.execute(
        "SELECT horodatage FROM evenements WHERE type = 'raid'" + ou
        + " ORDER BY horodatage", arg)]
    morts = [datetime.fromisoformat(d) for (d,) in cx.execute(
        "SELECT horodatage FROM evenements WHERE type = 'mort'" + ou, arg)]
    tenus = serie = record = 0
    for debut in raids:
        if any(debut <= m <= debut + fenetre for m in morts):
            serie = 0
        else:
            tenus += 1
            serie += 1
            record = max(record, serie)
    return {"tenus": tenus, "total": len(raids), "serie": serie, "record": record}


def valeur_kpi(source, ident, sessions, morts, progression, agg, boss_vaincus,
               raids=None):
    """Calcule un indicateur. Renvoie None si la donnee manque encore."""
    maintenant = datetime.now()

    if source in ("raids_sans_perte", "raids_serie", "raids_record"):
        # Avant le premier raid il n'y a rien a afficher : sur un monde neuf,
        # ils n'apparaissent qu'apres l'Ancien.
        if not raids or not raids["total"]:
            return None
        return raids[{"raids_sans_perte": "tenus", "raids_serie": "serie",
                      "raids_record": "record"}[source]]

    if source == "chantiers_faits":
        c = chantiers()
        return c["avancement"]["faits"] if c else None

    if source == "boss_vaincus":
        return len(boss_vaincus)

    if source.startswith("intacts_depuis:"):
        vise = source.split(":", 1)[1]
        depuis = next((e["date"] for e in boss_vaincus if e["cle"] == vise), None)
        if not depuis:
            return None
        return sum(1 for p in agg
                   if not [d for d in morts.get(p, []) if d >= depuis])

    if source == "morts_total":
        return sum(len(v) for v in morts.values())

    if source == "morts_par_heure":
        h = temps_cumule(sessions) / 3600.0
        if h < 1:
            return None
        return round(sum(len(v) for v in morts.values()) / h, 3)

    if source == "temps_groupe":
        return int(temps_cumule(sessions))

    if source == "serie_max":
        series = []
        for pseudo in agg:
            dates = morts.get(pseudo, [])
            if dates:
                depart = datetime.fromisoformat(dates[-1])
            else:
                debuts = [d for sid, d, _f, _c in sessions if ident.get(sid) == pseudo]
                if not debuts:
                    continue
                depart = min(debuts)
            series.append((maintenant - depart).total_seconds())
        return int(max(series)) if series else None

    if source == "dernier_palier":
        # En temps de jeu cumule du groupe, et non en calendrier : comparer un
        # ecart de dates a un objectif exprime en heures de jeu melangeait deux
        # unites, et une semaine sans se connecter gonflait le chiffre.
        etapes = sorted(e["date"] for e in boss_vaincus)
        if len(etapes) < 2:
            return None
        return int(temps_cumule(sessions, datetime.fromisoformat(etapes[-1]))
                   - temps_cumule(sessions, datetime.fromisoformat(etapes[-2])))

    if source == "sessions_7j":
        limite = maintenant - timedelta(days=7)
        return sum(1 for _sid, debut, _f, _c in sessions if debut >= limite)

    return None


def kpis(cx, monde):
    """Chaque KPI avec sa valeur, sa cible et son avancement."""
    conf = objectifs()
    if not conf:
        return None
    ident, sessions, morts, progression, _i, _j = charge(cx, monde)
    agg = par_joueur(ident, sessions, morts)
    boss_vaincus = progression_boss(cx, monde, progression)
    raids = raids_tenus(cx, monde)

    resultat = {"kpis": [], "jalons": []}
    for k in conf.get("kpis", []):
        v = valeur_kpi(k["source"], ident, sessions, morts, progression, agg,
                       boss_vaincus, raids)
        cible = k.get("cible")
        entree = dict(k)
        entree["valeur"] = v
        if v is None or not cible:
            entree["avancement"] = None
            entree["tenu"] = None
        elif k.get("sens") == "moins":
            # Un objectif « au plus » est tenu tant qu'on est sous la cible.
            # L'avancement se lit alors comme une marge : 1 = large, 0 = depasse.
            entree["tenu"] = v <= cible
            entree["avancement"] = 1.0 if v == 0 else min(1.0, cible / v)
        else:
            entree["tenu"] = v >= cible
            entree["avancement"] = min(1.0, v / cible)
        resultat["kpis"].append(entree)

    # Jalons : a quel moment du temps de jeu cumule chaque boss est tombe.
    for j in conf.get("jalons", []):
        ts = next((e["date"] for e in boss_vaincus if e["boss"] == j["boss"]), None)
        e = dict(j)
        if ts:
            h = temps_cumule(sessions, datetime.fromisoformat(ts)) / 3600.0
            e["heures_reelles"] = round(h, 1)
            e["date"] = ts
            e["tenu"] = h <= j["heures_cumulees"]
        else:
            e["heures_reelles"] = None
            e["date"] = None
            e["tenu"] = None
        resultat["jalons"].append(e)
    return resultat


def filtre_monde(monde):
    """Le fragment de WHERE et son argument, pour un monde ou pour tous."""
    return (" AND monde = ?", (monde,)) if monde else ("", ())


def taille_monde(cx, monde=None):
    """Le nombre d'objets du monde, et la date du dernier point de sauvegarde.

    Deux sources, parce que la 1.0 a coupe en deux ce que la 0.2 disait en une
    ligne. Le recensement « Connections N ZDOS:M » porte le compte ; la ligne
    « World save (5/5) done » porte la date. Sur les mondes d'avant, le compte
    n'existe pas et on retombe sur le detail de l'ancienne ligne, qui le
    portait -- c'est pour Midgard que ce repli existe, et pour lui seul.
    """
    ou, arg = filtre_monde(monde)
    z = cx.execute(
        "SELECT detail, horodatage FROM evenements WHERE type = 'zdos'" + ou +
        " ORDER BY horodatage DESC LIMIT 1", arg).fetchone()
    s = cx.execute(
        "SELECT max(horodatage), detail FROM evenements "
        "WHERE type = 'sauvegarde'" + ou, arg).fetchone()
    sauvegarde = s[0] if s and s[0] else None
    if z:
        return {"zdos": int(z[0]), "releve": z[1], "sauvegarde": sauvegarde,
                "source": "recensement"}
    # Avant la 1.0 : le compte etait le detail de la ligne de sauvegarde.
    if s and s[0] and s[1] is not None:
        return {"zdos": int(s[1]), "releve": s[0], "sauvegarde": sauvegarde,
                "source": "sauvegarde"}
    return {"zdos": None, "releve": None, "sauvegarde": sauvegarde,
            "source": None}


def autels(cx, monde, boss_vaincus):
    """Les lieux d'invocation reperes par le serveur, du plus ancien au plus recent.

    C'est la seule source qui annonce une intention et non un fait : sur
    Midgard, l'autel de Bonemass est apparu le 3 septembre a 23h12 et Bonemass
    est tombe le 5 ; celui de Moder le 8 a 22h03, mise a mort le 9 a 01h28.
    Un autel repere est donc une chasse ouverte, et c'est ce qui manquait au
    brief : le serveur le savait depuis le 2026-09-10 a 02h36 pour l'Ancien,
    sans que rien ne le dise.
    """
    ou, arg = filtre_monde(monde)
    tombes = {e["cle"] for e in boss_vaincus}
    res = []
    for lieu, n, premiere, derniere in cx.execute(
            "SELECT detail, count(*), min(horodatage), max(horodatage) "
            "FROM evenements WHERE type = 'autel'" + ou +
            " GROUP BY detail ORDER BY min(horodatage)", arg):
        cle = AUTELS.get(lieu)
        nom = dict(BOSS).get(cle) if cle else None
        res.append({"lieu": lieu, "cle": cle, "boss": nom or lieu,
                    "connu": nom is not None, "vues": n,
                    "premiere": premiere, "derniere": derniere,
                    "vaincu": cle in tombes if cle else False})
    return res


def donjons(cx, monde=None):
    """Les entrees de donjon, par type, avec leur nom lisible."""
    ou, arg = filtre_monde(monde)
    types = []
    for typ, n, derniere in cx.execute(
            "SELECT detail, count(*), max(horodatage) FROM evenements "
            "WHERE type = 'donjon'" + ou +
            " GROUP BY detail ORDER BY count(*) DESC", arg):
        noms = DONJONS.get(typ, (typ, typ))
        types.append({"type": typ, "nom": noms[0], "nom_pluriel": noms[1],
                      "entrees": n, "connu": typ in DONJONS, "derniere": derniere})
    return {"total": sum(t["entrees"] for t in types), "types": types}


def exploration(cx, monde=None):
    """Les zones de terrain neuf, en tout et sur les dernieres 24 heures.

    Une zone n'est peuplee qu'a la premiere approche : ces lignes mesurent donc
    le terrain decouvert, pas le terrain traverse. Le compte porte sur les
    coordonnees distinctes -- la 1.0 ecrit une ligne par lieu pose, donc
    plusieurs par zone, et compter les evenements compterait faux.
    """
    ou, arg = filtre_monde(monde)
    veille = (datetime.now() - timedelta(hours=24)).isoformat(sep=" ", timespec="seconds")
    total = cx.execute(
        "SELECT count(DISTINCT detail) FROM evenements WHERE type = 'zone'" + ou,
        arg).fetchone()[0]
    recent = cx.execute(
        "SELECT count(DISTINCT detail) FROM evenements WHERE type = 'zone'"
        " AND horodatage >= ?" + ou, (veille,) + arg).fetchone()[0]
    return {"zones": total, "zones_24h": recent}


def texte(cx, monde=None):
    ident, sessions, morts, progression, infos, jour = charge(cx, monde)
    agg = par_joueur(ident, sessions, morts)
    boss_vaincus = progression_boss(cx, monde, progression)

    nom_monde = (infos[0] if infos and infos[0] else None) or monde or "?"
    print("SERVEUR VALHEIM — monde « %s »" % nom_monde)
    if jour:
        print("jour %s dans le monde" % jour[0])
    t = taille_monde(cx, monde)
    if t["zdos"]:
        print("%s objets dans le monde (releve du %s)" % (t["zdos"], t["releve"][:16]))
    if t["sauvegarde"]:
        print("derniere sauvegarde %s" % t["sauvegarde"][:16])
    print()

    print("JOUEURS")
    print("%-16s %8s %9s %6s   %s" % ("pseudo", "sessions", "temps", "morts", "derniere fois"))
    for pseudo, e in sorted(agg.items(), key=lambda kv: -kv[1]["temps"]):
        print("%-16s %8d %9s %6d   %s%s" % (
            pseudo, e["sessions"], duree(e["temps"]), e["morts"],
            e["derniere"] or "-", "  (en jeu)" if e["en_cours"] else ""))
    print()

    print("PROGRESSION, d'apres les cles du monde")
    if not boss_vaincus:
        print("  releve des cles pas encore effectue (cles-monde-valheim.py)")
    for e in boss_vaincus:
        print("  %-16s vaincu %s %s%s" % (
            e["boss"], "le" if e["exacte"] else "avant le", e["date"][:16],
            "" if e["exacte"] else "   (borne haute)"))
    for cle, nom in BOSS:
        if not any(e["cle"] == cle for e in boss_vaincus):
            print("  %-16s pas encore" % nom)
    print()

    au = autels(cx, monde, boss_vaincus)
    print("AUTELS REPERES par le serveur")
    if not au:
        print("  aucun -- personne n'a encore approche un lieu d'invocation")
    for e in au:
        etat = "boss vaincu" if e["vaincu"] else "CHASSE OUVERTE"
        print("  %-16s repere le %s   %d vue(s)   %s%s" % (
            e["boss"], e["premiere"][:16], e["vues"], etat,
            "" if e["connu"] else "   (lieu non identifie)"))
    print()

    ex = exploration(cx, monde)
    dj = donjons(cx, monde)
    print("EXPLORATION  %d zones decouvertes, dont %d sur les dernieres 24 h"
          % (ex["zones"], ex["zones_24h"]))
    print()
    print("DONJONS  %d entrees" % dj["total"])
    if not dj["types"]:
        print("  aucune entree relevee sur ce monde")
    for e in dj["types"]:
        print("  %-26s %4d   derniere le %s%s" % (
            e["nom_pluriel"] if e["entrees"] > 1 else e["nom"],
            e["entrees"], e["derniere"][:16],
            "" if e["connu"] else "   (type inconnu)"))
    print()

    d = defi_baby(morts, boss_vaincus)
    if d:
        print("DEFI DE BAB-Y — jamais mort depuis la chute de l'Ancien (%s)" % d["depuis"])
        if d["tenants"]:
            for j in sorted(d["tenants"]):
                print("  TIENT TOUJOURS   %s" % j)
        for j, (n, premiere) in sorted(d["tombes"].items()):
            print("  perdu            %-16s %d mort(s), la premiere le %s" % (j, n, premiere))
        if not d["tenants"]:
            print("  personne ne tient le defi sur ce monde")

    for defi in defis(agg, morts, progression, sessions, ident, boss_vaincus):
        print()
        print("%s — %s" % (defi["nom"].upper(), defi["regle"]))
        for r in defi["rangs"]:
            v = duree(r["valeur"]) if defi.get("unite") == "duree" else r["valeur"]
            marque = "  TIENT" if r["tient"] else ""
            print("  %-24s %10s   %s%s" % (r["joueur"], v, r["note"], marque))

    k = kpis(cx, monde)
    if not k:
        return
    print()
    print("KPI ET OBJECTIFS")
    for e in k["kpis"]:
        if e["valeur"] is None:
            print("  %-44s %14s" % (e["libelle"], "pas encore"))
            continue
        fmt = duree if e.get("unite") == "duree" else (lambda x: str(x))
        etat = "TENU" if e["tenu"] else "a faire"
        barre = ""
        if e["avancement"] is not None:
            plein = int(round(e["avancement"] * 10))
            barre = "[" + "#" * plein + "." * (10 - plein) + "]"
        print("  %-44s %14s / %-12s %s %s" % (
            e["libelle"], fmt(e["valeur"]), fmt(e["cible"]), barre, etat))

    c = chantiers()
    if c:
        a = c["avancement"]
        print()
        print("CHANTIERS DECLARES  %d/%d faits  (tenus a la main, pas mesures)"
              % (a["faits"], a["total"]))
        for ch in c["chantiers"]:
            marque = {"fait": "x", "en_cours": "~", "a_faire": "."}[ch["etat"]]
            print("  [%s] %-26s %s" % (marque, ch["nom"],
                                       ", ".join(ch["titulaires"]) or "-"))

    if any(j["date"] for j in k["jalons"]):
        print()
        print("JALONS, en temps de jeu cumule du groupe")
        print("  (un raid absent ne prouve rien : Eikthyr peut etre tombe sans")
        print("   que son raid se soit jamais declenche)")
        for j in k["jalons"]:
            if not j["date"]:
                print("  %-16s %s" % (j["boss"], "aucun raid observe"))
                continue
            print("  %-16s %6.1f h  (objectif %d h)   %s" % (
                j["boss"], j["heures_reelles"], j["heures_cumulees"],
                "TENU" if j["tenu"] else "depasse"))


def donnees(cx, monde=None):
    ident, sessions, morts, progression, infos, jour = charge(cx, monde)
    agg = par_joueur(ident, sessions, morts)
    boss_vaincus = progression_boss(cx, monde, progression)
    t = taille_monde(cx, monde)
    return {
        "mondes": metadonnees_monde(cx),
        "monde": (infos[0] if infos and infos[0] else None) or monde,
        "jour": jour[0] if jour else None,
        "zdos": t["zdos"],
        "derniere_sauvegarde": t["sauvegarde"],
        "autels": autels(cx, monde, boss_vaincus),
        "donjons": donjons(cx, monde),
        "exploration": exploration(cx, monde),
        "joueurs": [dict(pseudo=p, **e) for p, e in
                    sorted(agg.items(), key=lambda kv: -kv[1]["temps"])],
        "progression": [{"boss": e["boss"], "premier": e["date"],
                         "exacte": e["exacte"], "cle": e["cle"]}
                        for e in boss_vaincus],
        "raids": [{"raid": c, "premier": t}
                  for c, t in sorted(progression.items(), key=lambda kv: kv[1])],
        "defi_baby": defi_baby(morts, boss_vaincus),
        "defis": defis(agg, morts, progression, sessions, ident, boss_vaincus),
        "kpi": kpis(cx, monde),
        "roles": roles(cx, monde, ident, sessions),
        "chantiers": chantiers(),
        "genere": datetime.now().isoformat(timespec="seconds"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="sortie JSON pour la page Cockpit")
    ap.add_argument("--monde", default=None,
                    help="monde a analyser ; par defaut le monde en cours")
    ap.add_argument("--tous-mondes", action="store_true",
                    help="ne cloisonne pas : additionne tous les mondes")
    a = ap.parse_args()
    cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
    monde = None if a.tous_mondes else (a.monde or monde_actif(cx))
    if a.json:
        print(json.dumps(donnees(cx, monde), ensure_ascii=False, indent=1))
    else:
        texte(cx, monde)


if __name__ == "__main__":
    main()
