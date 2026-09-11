#!/usr/bin/env python3
"""Le bilan de la soiree, publie quand le dernier joueur s'est deconnecte.

Complement des deux autres : notifie-discord-valheim.py poste les evenements au
fil de l'eau, bilan-discord-valheim.py envoie a 19h un point tourne vers
l'AVANT -- ou en est le groupe, quel conseil pour l'etape en cours. Celui-ci
regarde en ARRIERE : ce qui s'est passe ce soir-la.

QUAND IL PART. Pas a heure fixe -- le groupe joue parfois jusqu'a quatre heures
du matin, et un bilan de 1h couperait la soiree en deux. Il part dix minutes
apres la deconnexion du dernier joueur, quelle que soit l'heure, et se trouve
donc dans le salon quand le groupe ouvre Discord le lendemain. Une minuterie
regarde toutes les cinq minutes s'il y a lieu de parler.

CE QU'EST UNE SOIREE. Les sessions sont regroupees en BLOCS separes par au
moins trente minutes sans personne en ligne. Sans ce regroupement, une
reconnexion de cinq minutes a deux heures du matin publierait un second bilan
qui n'aurait rien a raconter. Le bloc doit aussi peser au moins un quart
d'heure : une connexion qui verifie que le serveur repond n'est pas une soiree.

Chaque bilan publie est marque en base par la fin du bloc qu'il couvre. Un bloc
deja raconte ne le sera pas deux fois, meme si la minuterie repasse ou si la
machine redemarre.
"""

import argparse
import collections
import datetime
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
CONF = "/etc/valheim-discord.conf"
AGENT = "valheim-serveur/1.0 (bilan de soiree auto-heberge)"
NOM_AFFICHE = "Claudo Le Viking"

TROU = datetime.timedelta(minutes=30)      # ce qui separe deux soirees
REPOS = datetime.timedelta(minutes=10)     # attente avant de parler
PLANCHER = datetime.timedelta(minutes=15)  # en deca, ce n'etait pas une soiree

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")


def duree(secondes):
    s = int(secondes)
    if s < 3600:
        return "%d min" % (s // 60)
    h, m = divmod(s // 60, 60)
    return "%d h %02d" % (h, m)


def sessions(cx, monde):
    """Les sessions appariees, par SteamID. Une session sans deconnexion est
    en cours -- et sa presence suffit a se taire."""
    ouvertes, finies, encore = {}, [], False
    for ts, typ, sid in cx.execute(
            "SELECT horodatage, type, steamid FROM evenements "
            "WHERE type IN ('connexion', 'deconnexion') AND monde = ? "
            "ORDER BY horodatage, id", (monde,)):
        t = datetime.datetime.fromisoformat(ts)
        if typ == "connexion":
            ouvertes[sid] = t
        elif sid in ouvertes:
            finies.append((sid, ouvertes.pop(sid), t))
    return finies, bool(ouvertes)


def blocs(finies):
    """Regroupe les sessions en soirees : tout ce qui se touche a moins de
    trente minutes appartient au meme bloc."""
    if not finies:
        return []
    par_debut = sorted(finies, key=lambda s: s[1])
    lot = [par_debut[0]]
    sortie = []
    for s in par_debut[1:]:
        fin_lot = max(x[2] for x in lot)
        if s[1] - fin_lot > TROU:
            sortie.append(lot)
            lot = [s]
        else:
            lot.append(s)
    sortie.append(lot)
    return sortie


def compte(cx, monde, debut, fin, typ, distinct=False):
    q = ("SELECT count(DISTINCT detail) FROM evenements " if distinct else
         "SELECT count(*) FROM evenements ")
    return cx.execute(q + "WHERE monde = ? AND type = ? AND horodatage >= ? "
                      "AND horodatage <= ?",
                      (monde, typ, debut.isoformat(sep=" "),
                       fin.isoformat(sep=" "))).fetchone()[0]


def raconte(cx, monde, bloc, precedent, ident, alias):
    debut = min(s[1] for s in bloc)
    fin = max(s[2] for s in bloc)
    par_joueur = collections.defaultdict(float)
    for sid, d, f in bloc:
        par_joueur[sid] += (f - d).total_seconds()
    total = sum(par_joueur.values())

    morts = collections.Counter()
    for (j,) in cx.execute(
            "SELECT joueur FROM evenements WHERE type = 'mort' AND monde = ? "
            "AND horodatage >= ? AND horodatage <= ?",
            (monde, debut.isoformat(sep=" "), fin.isoformat(sep=" "))):
        morts[alias.get(j, j)] += 1

    lignes = []
    for sid, s in sorted(par_joueur.items(), key=lambda kv: -kv[1]):
        nom = ident.get(sid, "SteamID %s" % sid)
        m = morts.get(nom, 0)
        lignes.append("`%-12s` %-8s %s" % (
            nom[:12], duree(s), ("%d mort%s" % (m, "s" if m > 1 else "")) if m else "—"))

    champs = [{"name": "⏱️  Qui était là", "inline": False,
               "value": "\n".join(lignes) or "personne"}]

    zones = compte(cx, monde, debut, fin, "zone", distinct=True)
    donjons = compte(cx, monde, debut, fin, "donjon")
    raids = compte(cx, monde, debut, fin, "raid")
    terrain = []
    if zones:
        terrain.append("%d zone%s de terrain neuf" % (zones, "s" if zones > 1 else ""))
    if donjons:
        terrain.append("%d entrée%s de donjon" % (donjons, "s" if donjons > 1 else ""))
    if raids:
        terrain.append("%d raid%s" % (raids, "s" if raids > 1 else ""))
    if terrain:
        champs.append({"name": "🗺️  Ce que la soirée a ouvert", "inline": False,
                       "value": "\n".join(terrain)})

    autels = [d for (d,) in cx.execute(
        "SELECT DISTINCT detail FROM evenements WHERE type = 'autel' AND monde = ? "
        "AND horodatage >= ? AND horodatage <= ?",
        (monde, debut.isoformat(sep=" "), fin.isoformat(sep=" ")))]
    if autels:
        champs.append({"name": "🏛️  Autels repérés", "inline": False,
                       "value": ", ".join(sorted(autels))})

    jour = cx.execute(
        "SELECT detail FROM evenements WHERE type = 'jour' AND monde = ? "
        "AND horodatage <= ? ORDER BY horodatage DESC LIMIT 1",
        (monde, fin.isoformat(sep=" "))).fetchone()
    if jour:
        champs.append({"name": "📅  Dans le monde", "inline": False,
                       "value": "jour %s" % jour[0]})

    # La comparaison avec la soiree precedente : un chiffre seul ne dit rien.
    pied = ""
    if precedent:
        avant = sum((f - d).total_seconds() for _s, d, f in precedent)
        ecart = total - avant
        sens = "de plus" if ecart >= 0 else "de moins"
        pied = "soirée précédente : %s, soit %s %s" % (
            duree(avant), duree(abs(ecart)), sens)

    titre = "🌙  Soirée du %d %s" % (debut.day, MOIS[debut.month - 1])
    desc = "%s → %s · %d joueur%s · %s de jeu cumulé" % (
        debut.strftime("%Hh%M"), fin.strftime("%Hh%M"), len(par_joueur),
        "s" if len(par_joueur) > 1 else "", duree(total))
    return {"title": titre, "description": desc, "fields": champs,
            "footer": {"text": pied} if pied else None}


def publie(url, embed):
    corps = json.dumps({"embeds": [embed], "username": NOM_AFFICHE,
                        "allowed_mentions": {"parse": []}}).encode()
    r = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    with urllib.request.urlopen(r, timeout=20) as rep:
        return rep.status


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--essai", action="store_true",
                    help="montre le bilan sans rien publier ni marquer")
    ap.add_argument("--quand-meme", action="store_true",
                    help="publie meme si cette soiree est deja racontee")
    o = ap.parse_args()

    cx = sqlite3.connect(BASE)
    monde = cx.execute("SELECT monde FROM mondes ORDER BY derniere_vue DESC "
                       "LIMIT 1").fetchone()
    if not monde:
        return 0
    monde = monde[0]
    ident = dict(cx.execute("SELECT steamid, pseudo FROM joueurs"))
    try:
        alias = {p: ident.get(s, p) for s, p in
                 cx.execute("SELECT steamid, pseudo FROM pseudos")}
    except sqlite3.OperationalError:
        alias = {}

    finies, quelqu_un_en_ligne = sessions(cx, monde)
    if quelqu_un_en_ligne:
        print("quelqu'un joue encore : on attend")
        return 0
    lots = blocs(finies)
    if not lots:
        return 0
    dernier = lots[-1]
    fin = max(s[2] for s in dernier)
    debut = min(s[1] for s in dernier)

    if datetime.datetime.now() - fin < REPOS:
        print("dernier depart il y a moins de %d min : on attend" % (REPOS.seconds // 60))
        return 0
    if fin - debut < PLANCHER:
        print("bloc trop court (%s) : ce n'etait pas une soiree" % duree((fin-debut).total_seconds()))
        return 0

    cx.execute("CREATE TABLE IF NOT EXISTS reglages (cle TEXT PRIMARY KEY, valeur TEXT)")
    marque = cx.execute("SELECT valeur FROM reglages WHERE cle = 'soiree_racontee'"
                        ).fetchone()
    if marque and marque[0] >= fin.isoformat(sep=" ") and not o.quand_meme:
        print("soiree deja racontee")
        return 0

    embed = raconte(cx, monde, dernier, lots[-2] if len(lots) > 1 else None,
                    ident, alias)
    if o.essai:
        print(json.dumps(embed, ensure_ascii=False, indent=1))
        return 0

    try:
        with open(CONF) as f:
            url = next(l.split("=", 1)[1].strip().strip('"')
                       for l in f if l.startswith("WEBHOOK="))
    except (OSError, StopIteration):
        print("pas de webhook configure", file=sys.stderr)
        return 0
    try:
        code = publie(url, embed)
    except (urllib.error.URLError, OSError) as e:
        print("publication impossible : %s" % e, file=sys.stderr)
        return 1
    # La marque n'est posee qu'apres publication reussie : un echec reseau doit
    # etre rattrape au passage suivant, pas avale.
    cx.execute("INSERT INTO reglages (cle, valeur) VALUES ('soiree_racontee', ?) "
               "ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur",
               (fin.isoformat(sep=" "),))
    cx.commit()
    print("bilan de soiree publie (HTTP %s), bloc %s -> %s" % (code, debut, fin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
