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
from datetime import datetime

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


def duree(secondes):
    s = int(secondes)
    if s < 3600:
        return "%d min" % (s // 60)
    return "%d h %02d" % (s // 3600, (s % 3600) // 60)


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


def debut_session(cx, steamid, avant_id):
    r = cx.execute("SELECT horodatage FROM evenements WHERE type = 'connexion' "
                   "AND steamid = ? AND id < ? ORDER BY id DESC LIMIT 1",
                   (steamid, avant_id)).fetchone()
    return r[0] if r else None


def premier_raid(cx, detail, id_ev):
    """Vrai si c'est la premiere fois qu'on voit ce raid : donc un boss neuf."""
    r = cx.execute("SELECT min(id) FROM evenements WHERE type = 'raid' AND detail = ?",
                   (detail,)).fetchone()
    return r and r[0] == id_ev


def message(cx, ev):
    id_ev, ts, _monde, typ, joueur, steamid, detail = ev
    heure = ts[11:16]
    if typ == "connexion":
        return "🛡️  **%s** arrive sur le serveur. (%s)" % (pseudo_de(cx, steamid), heure)
    if typ == "deconnexion":
        p = pseudo_de(cx, steamid)
        debut = debut_session(cx, steamid, id_ev)
        if debut:
            d = datetime.fromisoformat(ts) - datetime.fromisoformat(debut)
            return "👋  **%s** repart apres %s de jeu." % (p, duree(d.total_seconds()))
        return "👋  **%s** repart." % p
    if typ == "mort":
        n = morts_de(cx, joueur, id_ev)
        return "💀  **%s** est mort. Ça lui fait **%d mort%s** sur ce monde." % (
            joueur, n, "s" if n > 1 else "")
    if typ == "raid":
        quoi = RAIDS.get(detail, detail)
        if detail in RAIDS and detail.startswith("army_") and premier_raid(cx, detail, id_ev):
            return ("⚔️  Premier raid de %s : le boss correspondant est donc tombé. "
                    "Nouvelle étape franchie." % quoi)
        return "⚔️  Raid : %s attaque la base. (%s)" % (quoi, heure)
    return None


# Discord passe par Cloudflare, qui repond 403 a l'agent utilisateur par defaut
# de Python (« Python-urllib/3.x »). Il faut donc en declarer un explicitement.
# Le premier essai contre un faux salon local n'avait rien montre : une maquette
# sur 127.0.0.1 n'a pas de Cloudflare devant elle.
AGENT = "valheim-serveur/1.0 (collecteur de statistiques auto-heberge)"


def publie(url, texte):
    corps = json.dumps({"content": texte, "allowed_mentions": {"parse": []}}).encode()
    requete = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    with urllib.request.urlopen(requete, timeout=15) as r:
        return r.status


def main():
    url = config()
    if not url:
        return 0  # pas encore configure : ce n'est pas une erreur

    cx = sqlite3.connect(BASE)
    dernier = curseur(cx)
    if dernier is None:
        # Premier demarrage : on se cale sur le present. Sans ca, tout
        # l'historique du monde partirait d'un coup dans le salon.
        maxi = cx.execute("SELECT coalesce(max(id), 0) FROM evenements").fetchone()[0]
        curseur(cx, maxi)
        print("premier demarrage, curseur cale sur l'evenement %d" % maxi)
        return 0

    interessants = ("connexion", "deconnexion", "mort", "raid")
    lignes = cx.execute(
        "SELECT id, horodatage, monde, type, joueur, steamid, detail FROM evenements "
        "WHERE id > ? AND type IN (?, ?, ?, ?) ORDER BY id",
        (dernier, *interessants)).fetchall()
    if not lignes:
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

    curseur(cx, lignes[-1][0])
    print("%d evenement(s) publie(s)" % len(textes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
