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
NOM_BOSS = dict(BOSS)

# Quel raid exige quelle cle. Attention, ce n'est PAS le boss du meme nom : un
# raid se debloque avec le boss PRECEDENT. « army_theelder » exige
# defeated_eikthyr et non defeated_gdking ; « army_bonemass » exige
# defeated_gdking. Deduire la progression du nom des raids -- ce que faisait la
# premiere version -- decalait donc toute la lecture d'un boss.
# Verifie sur ce serveur : army_bonemass s'etait declenche alors que
# defeated_bonemass est absent du fichier de monde.
RAID_EXIGE = {
    "army_eikthyr": "defeated_eikthyr",
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
                                  else "premiere mort le %s" % apres[0][:16]})
        liste.append({
            "nom": "Intact depuis %s" % boss,
            "regle": "n'etre jamais mort depuis la chute de %s" % boss,
            "metrique": "morts enregistrees apres le %s" % depuis[:16],
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
            "nom": "Serie en cours",
            "regle": "le plus longtemps sans mourir, en temps reel",
            "metrique": "temps ecoule depuis la derniere mort",
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
            "regle": "temps ecoule entre deux boss",
            "metrique": "ecart entre les premiers raids de chaque boss",
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


def valeur_kpi(source, ident, sessions, morts, progression, agg, boss_vaincus):
    """Calcule un indicateur. Renvoie None si la donnee manque encore."""
    maintenant = datetime.now()

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

    resultat = {"kpis": [], "jalons": []}
    for k in conf.get("kpis", []):
        v = valeur_kpi(k["source"], ident, sessions, morts, progression, agg,
                       boss_vaincus)
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


def texte(cx, monde=None):
    ident, sessions, morts, progression, infos, jour = charge(cx, monde)
    agg = par_joueur(ident, sessions, morts)
    boss_vaincus = progression_boss(cx, monde, progression)

    nom_monde = (infos[0] if infos and infos[0] else None) or monde or "?"
    print("SERVEUR VALHEIM — monde « %s »" % nom_monde)
    if jour:
        print("jour %s dans le monde" % jour[0])
    if infos and infos[2]:
        print("%s ZDOs a la derniere sauvegarde (%s)" % (infos[2], infos[1]))
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
    return {
        "mondes": metadonnees_monde(cx),
        "monde": (infos[0] if infos and infos[0] else None) or monde,
        "jour": jour[0] if jour else None,
        "zdos": infos[2] if infos else None,
        "derniere_sauvegarde": infos[1] if infos else None,
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
