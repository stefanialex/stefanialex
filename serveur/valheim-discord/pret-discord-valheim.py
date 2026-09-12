#!/usr/bin/env python3
"""Annonce dans le salon que le serveur est joignable, apres une mise a jour.

Demande d'Alexandre le 2026-09-12, au sortir de la deuxieme mise a jour de
Valheim en deux jours : pendant qu'on met le serveur a niveau, le groupe ne
sait pas quand revenir.

QUAND IL PARLE, et quand il se tait. Il est lance en meme temps que le serveur,
mais il n'annonce QUE si la version a change depuis la derniere annonce. Sinon
le redemarrage quotidien de 5h01 et le redemarrage hebdomadaire posteraient un
message chaque fois, et le salon apprendrait a ne plus les lire. Une mise a
jour est une nouvelle ; un redemarrage de routine n'en est pas une.

CE QU'IL ATTEND. Pas le demarrage du processus -- le serveur met une trentaine
de secondes a charger le monde et refuse les connexions entre-temps. Le
marqueur est « ZDOMan.LoadChunks done », derniere etape du chargement : apres
elle, le serveur accepte les joueurs. Annoncer plus tot enverrait le groupe se
heurter a une porte fermee.
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
CONF = "/etc/valheim-discord.conf"
AGENT = "valheim-serveur/1.0 (annonce de disponibilite auto-hebergee)"
NOM_AFFICHE = "Claudo Le Viking"

PRET = "ZDOMan.LoadChunks done"
VERSION = re.compile(r"Valheim version: l?-?([\d.]+) \(network version (\d+)\)")
MONDE = re.compile(r"Load world: (\S+)")


def journal(depuis):
    try:
        return subprocess.run(
            ["journalctl", "-u", "valheim", "-o", "cat", "--no-pager",
             "--since", depuis],
            capture_output=True, text=True, errors="replace", timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def attends(depuis, patience):
    """Rend le texte du journal des que le serveur est pret, ou None."""
    fin = datetime.datetime.now() + patience
    while datetime.datetime.now() < fin:
        texte = journal(depuis)
        if PRET in texte:
            return texte
        import time
        time.sleep(5)
    return None


def annonce(texte):
    try:
        with open(CONF) as f:
            url = next(l.split("=", 1)[1].strip().strip('"')
                       for l in f if l.startswith("WEBHOOK="))
    except (OSError, StopIteration):
        print("pas de webhook configure", file=sys.stderr)
        return False
    corps = json.dumps({"content": texte, "username": NOM_AFFICHE,
                        "allowed_mentions": {"parse": []}}).encode()
    r = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    try:
        urllib.request.urlopen(r, timeout=20)
    except (urllib.error.URLError, OSError) as e:
        print("annonce non partie : %s" % e, file=sys.stderr)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--patience", type=int, default=600,
                    help="secondes d'attente du marqueur de disponibilite")
    ap.add_argument("--quand-meme", action="store_true",
                    help="annonce meme si la version n'a pas change")
    ap.add_argument("--essai", action="store_true", help="montre sans publier")
    o = ap.parse_args()

    depuis = (datetime.datetime.now() - datetime.timedelta(minutes=2)
              ).strftime("%Y-%m-%d %H:%M:%S")
    texte = attends(depuis, datetime.timedelta(seconds=o.patience))
    if texte is None:
        print("serveur pas pret apres %d s : rien annonce" % o.patience,
              file=sys.stderr)
        return 1

    v = VERSION.search(texte)
    version = "%s (réseau %s)" % v.groups() if v else "version inconnue"
    m = MONDE.search(texte)
    monde = m.group(1) if m else None

    cx = sqlite3.connect(BASE)
    cx.execute("CREATE TABLE IF NOT EXISTS reglages (cle TEXT PRIMARY KEY, valeur TEXT)")
    avant = cx.execute("SELECT valeur FROM reglages WHERE cle = 'version_annoncee'"
                       ).fetchone()
    if avant and avant[0] == version and not o.quand_meme:
        print("version inchangee (%s) : redemarrage de routine, rien annonce" % version)
        return 0

    jour = cx.execute("SELECT detail FROM evenements WHERE type = 'jour' "
                      "ORDER BY horodatage DESC LIMIT 1").fetchone()
    bouts = ["🟢  **Le serveur est de retour** — Valheim %s." % version]
    if monde:
        bouts.append("Monde « %s »%s." % (
            monde, ", jour %s" % jour[0] if jour else ""))
    bouts.append("Vous pouvez vous reconnecter.")
    msg = " ".join(bouts)

    if o.essai:
        print(msg)
        return 0
    if not annonce(msg):
        return 1
    cx.execute("INSERT INTO reglages (cle, valeur) VALUES ('version_annoncee', ?) "
               "ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur", (version,))
    cx.commit()
    print("annonce : %s" % msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
