#!/usr/bin/env python3
"""Releve les succes Steam et le temps de jeu total des joueurs.

Les succes vivent dans le fichier de personnage, chez le joueur : le serveur ne
les verra jamais. La seule voie est l'API Web de Steam, et elle ne repond que
pour les profils dont les « details du jeu » sont publics -- etre amis sur
Steam n'y change rien.

Valheim ne definit aucun succes avant la 1.0 du 9 septembre 2026, qui en ajoute
plus de cinquante. Le script gere ce cas sans se plaindre : il releve le temps
de jeu, constate qu'aucun succes n'existe, et attend.

Les identifiants Steam ne sont pas saisis a la main : ils viennent du journal
du serveur, releves par le collecteur a chaque connexion.
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
CONF = "/etc/valheim-steam.conf"
CONF_DISCORD = "/etc/valheim-discord.conf"
APP = 892970
API = "https://api.steampowered.com"
AGENT = "valheim-serveur/1.0 (releve des succes)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS steam_joueur (
  steamid        TEXT PRIMARY KEY,
  heures_totales INTEGER,
  lisible        INTEGER,
  releve         TEXT
);
CREATE TABLE IF NOT EXISTS steam_succes (
  steamid   TEXT NOT NULL,
  cle       TEXT NOT NULL,
  nom       TEXT,
  vu_le     TEXT NOT NULL,
  PRIMARY KEY (steamid, cle)
);
"""


def valeur(fichier, nom):
    try:
        with open(fichier) as f:
            for l in f:
                if l.startswith(nom + "="):
                    return l.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def interroge(chemin, params):
    url = "%s%s?%s" % (API, chemin, urllib.parse.urlencode(params))
    r = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(r, timeout=25) as rep:
        return json.load(rep)


def annonce(texte):
    url = valeur(CONF_DISCORD, "WEBHOOK")
    if not url:
        return
    corps = json.dumps({"content": texte, "allowed_mentions": {"parse": []}}).encode()
    r = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    try:
        urllib.request.urlopen(r, timeout=15)
    except (urllib.error.URLError, OSError) as e:
        print("annonce non partie : %s" % e, file=sys.stderr)


def libelles(cle):
    """Nom lisible de chaque succes, tel que le jeu le declare.

    Renvoie un dictionnaire vide tant que Valheim n'a pas de succes, ce qui est
    le cas avant la 1.0 : ce n'est pas une erreur, seulement un jeu qui n'en a
    pas encore.
    """
    try:
        d = interroge("/ISteamUserStats/GetSchemaForGame/v2/",
                      {"key": cle, "appid": APP})
    except (urllib.error.URLError, OSError, ValueError):
        return {}
    a = d.get("game", {}).get("availableGameStats", {}).get("achievements", [])
    return {x["name"]: x.get("displayName") or x["name"] for x in a}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--muet", action="store_true", help="ne rien publier sur Discord")
    ap.add_argument("--liste", action="store_true", help="affiche l'etat et sort")
    o = ap.parse_args()

    cle = valeur(CONF, "CLE")
    if not cle:
        return 0  # pas configure : ce n'est pas une erreur

    cx = sqlite3.connect(BASE)
    cx.executescript(SCHEMA)
    joueurs = list(cx.execute("SELECT steamid, pseudo FROM joueurs"))

    if o.liste:
        for sid, pseudo in joueurs:
            r = cx.execute("SELECT heures_totales, lisible FROM steam_joueur "
                           "WHERE steamid = ?", (sid,)).fetchone()
            n = cx.execute("SELECT count(*) FROM steam_succes WHERE steamid = ?",
                           (sid,)).fetchone()[0]
            print("  %-16s %s, %d succes" % (
                pseudo,
                "%d h au total" % r[0] if r and r[0] is not None else "non relevé",
                n))
        return 0

    noms = libelles(cle)
    maintenant = datetime.now().isoformat(sep=" ", timespec="seconds")
    nouveaux = []

    for sid, pseudo in joueurs:
        # Temps de jeu total, toutes parties confondues. Sert aussi de test de
        # visibilite : sans « details du jeu » publics, la reponse est vide.
        heures, lisible = None, 0
        try:
            d = interroge("/IPlayerService/GetOwnedGames/v1/",
                          {"key": cle, "steamid": sid, "include_appinfo": 0,
                           "appids_filter[0]": APP})["response"]
            jeux = d.get("games")
            if jeux is not None:
                lisible = 1
                v = next((g for g in jeux if g["appid"] == APP), None)
                if v:
                    heures = round(v["playtime_forever"] / 60)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            print("%s : %s" % (pseudo, e), file=sys.stderr)

        cx.execute("INSERT INTO steam_joueur (steamid, heures_totales, lisible, releve) "
                   "VALUES (?, ?, ?, ?) ON CONFLICT (steamid) DO UPDATE SET "
                   "heures_totales = excluded.heures_totales, "
                   "lisible = excluded.lisible, releve = excluded.releve",
                   (sid, heures, lisible, maintenant))

        if not noms or not lisible:
            continue
        try:
            d = interroge("/ISteamUserStats/GetPlayerAchievements/v1/",
                          {"key": cle, "steamid": sid, "appid": APP})["playerstats"]
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            continue
        connus = {c for (c,) in cx.execute(
            "SELECT cle FROM steam_succes WHERE steamid = ?", (sid,))}
        premier = not connus
        for s in d.get("achievements", []):
            if not s.get("achieved"):
                continue
            if s["apiname"] in connus:
                continue
            cx.execute("INSERT OR IGNORE INTO steam_succes (steamid, cle, nom, vu_le) "
                       "VALUES (?, ?, ?, ?)",
                       (sid, s["apiname"], noms.get(s["apiname"], s["apiname"]),
                        maintenant))
            # Au premier releve on n'annonce rien : tout ce qui est deja obtenu
            # sortirait d'un coup dans le salon.
            if not premier:
                nouveaux.append((pseudo, noms.get(s["apiname"], s["apiname"])))
    cx.commit()

    if not noms:
        print("Valheim ne definit encore aucun succes (ils arrivent avec la 1.0)")
    for pseudo, nom in nouveaux:
        print("succes : %s -> %s" % (pseudo, nom))
    if nouveaux and not o.muet:
        if len(nouveaux) <= 4:
            for pseudo, nom in nouveaux:
                annonce("🏅  **%s** vient de débloquer « %s »." % (pseudo, nom))
        else:
            compte = {}
            for pseudo, _ in nouveaux:
                compte[pseudo] = compte.get(pseudo, 0) + 1
            annonce("🏅  Nouveaux succès : " + ", ".join(
                "**%s** ×%d" % (p, n) for p, n in compte.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
