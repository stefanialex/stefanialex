#!/usr/bin/env python3
"""Publie les evenements du serveur Valheim sur un salon Discord.

Ne relit pas le journal : consomme la base du collecteur. Les deux morceaux
restent ainsi independants -- un seul code connait le format des logs, et une
panne de reseau cote Discord ne peut pas faire perdre un evenement, puisque le
curseur n'avance qu'apres publication reussie.

L'adresse du webhook vit dans /etc/valheim-discord.conf, hors du depot : c'est
un secret, quiconque l'a peut ecrire dans le salon. Sans ce fichier, le script
ne fait rien et sort sans erreur -- il peut donc etre installe et arme avant
que l'adresse existe.
"""

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
CONF = "/etc/valheim-discord.conf"
LOT_MAX = 10  # au-dela, on resume : Discord limite la taille d'un message

# Les cles internes de Valheim ne sont pas ce que voient les joueurs.
RAIDS = {
    "army_eikthyr": "l'armee d'Eikthyr",
    "army_theelder": "l'armee de l'Ancien",
    "army_bonemass": "l'armee de Bonemass",
    "army_moder": "la meute de Moder",
    "army_goblin": "la horde de Yagluth",
    "foresttrolls": "des trolls des forets",
    "blobs": "des blobs du marais",
    "skeletons": "des squelettes",
    "surtlings": "des surtlings",
    "wolves": "une meute de loups",
}


def config():
    try:
        with open(CONF) as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne.startswith("WEBHOOK="):
                    return ligne.split("=", 1)[1].strip().strip('"')
    except OSError:
        return None
    return None


def curseur(cx, valeur=None):
    cx.execute("CREATE TABLE IF NOT EXISTS reglages "
               "(cle TEXT PRIMARY KEY, valeur TEXT)")
    if valeur is None:
        r = cx.execute("SELECT valeur FROM reglages WHERE cle = 'discord_dernier_id'"
                       ).fetchone()
        return int(r[0]) if r else None
    cx.execute("INSERT INTO reglages (cle, valeur) VALUES ('discord_dernier_id', ?) "
               "ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur", (str(valeur),))
    cx.commit()


def pseudo_de(cx, steamid):
    r = cx.execute("SELECT pseudo FROM joueurs WHERE steamid = ?", (steamid,)).fetchone()
    return r[0] if r and r[0] else "un viking"


def morts_de(cx, joueur, avant_id):
    return cx.execute("SELECT count(*) FROM evenements WHERE type = 'mort' "
                      "AND joueur = ? AND id <= ?", (joueur, avant_id)).fetchone()[0]


def premier_raid(cx, detail, id_ev):
    """Vrai si c'est la premiere fois qu'on voit ce raid : donc un boss neuf."""
    r = cx.execute("SELECT min(id) FROM evenements WHERE type = 'raid' AND detail = ?",
                   (detail,)).fetchone()
    return r and r[0] == id_ev


# Fenetres d'etouffement. Le salon a servi de test grandeur nature : une
# soiree ou un joueur s'est reconnecte six fois et est mort cinq fois a produit
# une vingtaine de messages, et le groupe a demande qu'on calme ca.
FENETRE_ARRIVEE = timedelta(minutes=30)
FENETRE_MORT = timedelta(minutes=15)
RECONNEXIONS_SUSPECTES = 4      # par heure
FENETRE_INSTABLE = timedelta(hours=2)


def recent(cx, requete, args, depuis):
    """Vrai s'il existe un evenement du meme genre dans la fenetre."""
    r = cx.execute(requete, args + (depuis.isoformat(sep=" ", timespec="seconds"),)
                   ).fetchone()
    return bool(r and r[0])


def arrivee_a_annoncer(cx, ts, steamid, id_ev):
    """Une reconnexion dans la demi-heure n'est pas une arrivee.

    Sans ce filtre, un joueur dont le lien saute produit une ligne « arrive sur
    le serveur » a chaque retour -- six en trente minutes, constate le
    2026-09-04.
    """
    t = datetime.fromisoformat(ts)
    return not recent(cx,
        "SELECT 1 FROM evenements WHERE type = 'connexion' AND steamid = ? "
        "AND id < ? AND horodatage > ? LIMIT 1",
        (steamid, id_ev), t - FENETRE_ARRIVEE)


def morts_recentes(cx, joueur, ts, id_ev):
    """Nombre de morts du joueur dans le quart d'heure precedent."""
    t = datetime.fromisoformat(ts)
    return cx.execute(
        "SELECT count(*) FROM evenements WHERE type = 'mort' AND joueur = ? "
        "AND id < ? AND horodatage > ?",
        (joueur, id_ev, (t - FENETRE_MORT).isoformat(sep=" ", timespec="seconds"))
    ).fetchone()[0]


def lien_instable(cx, ts, steamid, id_ev):
    """Diagnostic plutot que symptome.

    Repeter « untel arrive » dix fois ne dit rien a personne. Compter les
    reconnexions et le dire une fois, si.
    """
    t = datetime.fromisoformat(ts)
    n = cx.execute(
        "SELECT count(*) FROM evenements WHERE type = 'connexion' AND steamid = ? "
        "AND id <= ? AND horodatage > ?",
        (steamid, id_ev, (t - timedelta(hours=1)).isoformat(sep=" ", timespec="seconds"))
    ).fetchone()[0]
    if n < RECONNEXIONS_SUSPECTES:
        return None
    cle = "instable_%s" % steamid
    r = cx.execute("SELECT valeur FROM reglages WHERE cle = ?", (cle,)).fetchone()
    if r and datetime.fromisoformat(r[0]) > t - FENETRE_INSTABLE:
        return None
    cx.execute("INSERT INTO reglages VALUES (?, ?) ON CONFLICT (cle) DO UPDATE SET "
               "valeur = excluded.valeur", (cle, ts))
    return n


def personne_en_ligne(cx, ts, id_ev):
    """Vrai si le serveur n'avait AUCUN joueur a cet instant.

    La source est la ligne « Connections N ZDOS:M », que le serveur ecrit
    toutes les dix minutes et que le collecteur garde depuis le 2026-09-12.
    C'est la seule fiable : l'appariement connexion/deconnexion laisse des
    sessions ouvertes pour toujours quand le serveur s'arrete sans ecrire
    « Closing socket », et il annoncerait alors du monde la ou il n'y a
    personne.

    Le dernier releve peut dater de dix minutes : on regarde donc aussi s'il y
    a eu une connexion entre-temps, sinon un raid tombant juste apres l'arrivee
    d'un joueur serait tu a tort.
    """
    r = cx.execute(
        "SELECT detail FROM evenements WHERE type = 'connectes' AND horodatage <= ? "
        "ORDER BY horodatage DESC, id DESC LIMIT 1", (ts,)).fetchone()
    if not r:
        return False          # rien de releve : dans le doute, on annonce
    dernier = cx.execute(
        "SELECT max(horodatage) FROM evenements WHERE type = 'connectes' "
        "AND horodatage <= ?", (ts,)).fetchone()[0]
    arrivee = cx.execute(
        "SELECT 1 FROM evenements WHERE type = 'connexion' AND horodatage > ? "
        "AND horodatage <= ? LIMIT 1", (dernier, ts)).fetchone()
    return r[0] == "0" and not arrivee


def message(cx, ev):
    id_ev, ts, _monde, typ, joueur, steamid, detail = ev
    heure = ts[11:16]
    if typ == "connexion":
        p = pseudo_de(cx, steamid)
        n = lien_instable(cx, ts, steamid, id_ev)
        if n:
            return ("📡  **%s** s'est reconnecté **%d fois en une heure**. Sa "
                    "connexion décroche : à vérifier de son côté (câble plutôt "
                    "que wifi, ou lien opérateur). Les morts qui suivent une "
                    "coupure ne comptent pas vraiment." % (p, n))
        if not arrivee_a_annoncer(cx, ts, steamid, id_ev):
            return None
        return "🛡️  **%s** arrive sur le serveur. (%s)" % (p, heure)
    if typ == "mort":
        # Une mort par quart d'heure au plus : les series de morts rapprochees
        # sont regroupees dans le message suivant plutot qu'annoncees une par une.
        rapprochees = morts_recentes(cx, joueur, ts, id_ev)
        if rapprochees:
            return None
        n = morts_de(cx, joueur, id_ev)
        return "💀  **%s** est mort. Ça lui fait **%d mort%s** sur ce monde." % (
            joueur, n, "s" if n > 1 else "")
    if typ == "raid":
        quoi = RAIDS.get(detail, detail)
        premier = (detail in RAIDS and detail.startswith("army_")
                   and premier_raid(cx, detail, id_ev))
        if premier:
            # Un PREMIER raid reste annonce meme serveur vide : il revele
            # qu'un boss est tombe, ce qui est une nouvelle et non du bruit, et
            # il n'arrive qu'une fois par boss.
            return ("⚔️  Premier raid de %s : le boss correspondant est donc tombé. "
                    "Nouvelle étape franchie." % quoi)
        # Les autres, non. « Annoncer des raids quand personne n'est connecte
        # ne sert a rien » -- Alexandre, le 2026-09-12. Une attaque sur une
        # base vide n'a ni temoin ni consequence.
        if personne_en_ligne(cx, ts, id_ev):
            return None
        return "⚔️  Raid : %s attaque la base. (%s)" % (quoi, heure)
    return None


# Discord passe par Cloudflare, qui repond 403 a l'agent utilisateur par defaut
# de Python (« Python-urllib/3.x »). Il faut donc en declarer un explicitement.
# Le premier essai contre un faux salon local n'avait rien montre : une maquette
# sur 127.0.0.1 n'a pas de Cloudflare devant elle.
AGENT = "valheim-serveur/1.0 (collecteur de statistiques auto-heberge)"


# Le webhook affiche par defaut le nom configure cote Discord (« Claudio »),
# alors que les reponses aux commandes arrivent sous celui de l'application bot
# (« Claudo Le Viking »). Deux noms pour le meme interlocuteur, ce qui n'aide
# personne. On force donc celui du bot, seul choix possible sans passer par le
# portail developpeur Discord -- le nom de l'application, lui, ne se change
# que la-bas.
NOM_AFFICHE = "Claudo Le Viking"


def publie(url, texte):
    corps = json.dumps({"content": texte, "username": NOM_AFFICHE,
                        "allowed_mentions": {"parse": []}}).encode()
    requete = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    with urllib.request.urlopen(requete, timeout=15) as r:
        return r.status


def main():
    url = config()
    if not url:
        return 0  # pas encore configure : ce n'est pas une erreur

    cx = sqlite3.connect(BASE)
    dernier = curseur(cx)   # cree aussi la table reglages
    if dernier is None:
        # Premier demarrage : on se cale sur le present. Sans ca, tout
        # l'historique du monde partirait d'un coup dans le salon.
        maxi = cx.execute("SELECT coalesce(max(id), 0) FROM evenements").fetchone()[0]
        curseur(cx, maxi)
        print("premier demarrage, curseur cale sur l'evenement %d" % maxi)
        return 0

    # Les departs ne sont plus publies, a la demande du groupe : « je me sens
    # flique, elle est ou la pointeuse ? ». Les sessions restent mesurees en
    # base -- les KPI de temps de jeu en dependent -- elles ne sont simplement
    # plus annoncees au fil de l'eau.
    interessants = ("connexion", "mort", "raid")
    lignes = cx.execute(
        "SELECT id, horodatage, monde, type, joueur, steamid, detail FROM evenements "
        "WHERE id > ? AND type IN (?, ?, ?) ORDER BY id",
        (dernier, *interessants)).fetchall()
    if not lignes:
        return 0

    # Plancher de fraicheur. Le curseur porte sur l'IDENTIFIANT, qui est
    # attribue a l'insertion : une ligne ancienne reinserée apres coup recoit
    # un identifiant neuf et passait donc pour un evenement du moment.
    #
    # C'est arrive le 2026-09-10 a 11h04. En retirant la regle qui effacait les
    # morts d'un personnage abandonne, deux morts sont revenues en base au
    # rejeu du journal -- l'une de la veille a 21h28 -- et le salon les a
    # annoncees comme si elles venaient d'avoir lieu.
    #
    # Le collecteur inserant dans l'ordre du journal, un evenement reellement
    # neuf porte toujours une date au moins egale a la plus recente deja
    # traitee. Une date anterieure signale une reinsertion : on avance le
    # curseur dessus sans rien dire. La comparaison se fait sur le maximum des
    # lignes deja traitees, et non sur la ligne du curseur, qui a pu etre
    # effacee depuis par une purge.
    plancher = cx.execute(
        "SELECT max(horodatage) FROM evenements WHERE id <= ?", (dernier,)).fetchone()[0]
    fin = lignes[-1][0]
    if plancher:
        anciennes = [l for l in lignes if l[1] < plancher]
        lignes = [l for l in lignes if l[1] >= plancher]
        if anciennes:
            print("%d evenement(s) reinseres, anterieurs au %s : non annonces"
                  % (len(anciennes), plancher))
    if not lignes:
        curseur(cx, fin)
        return 0

    if len(lignes) > LOT_MAX:
        # Rattrapage apres une longue coupure : un resume plutot que trente
        # messages d'affilee.
        compte = {}
        for l in lignes:
            compte[l[3]] = compte.get(l[3], 0) + 1
        textes = ["📋  Rattrapage : " + ", ".join(
            "%d %s" % (n, t) for t, n in sorted(compte.items()))]
    else:
        textes = [t for t in (message(cx, l) for l in lignes) if t]

    for t in textes:
        try:
            publie(url, t)
        except (urllib.error.URLError, OSError) as e:
            # Le curseur n'avance pas : le prochain passage reprendra ici.
            print("publication impossible (%s), on retentera" % e, file=sys.stderr)
            return 1

    curseur(cx, fin)
    print("%d evenement(s) publie(s)" % len(textes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
