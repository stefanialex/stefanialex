#!/usr/bin/env python3
"""Collecteur de statistiques du serveur Valheim.

Lit le journal de valheim.service et en derive des evenements de joueurs dans
une base SQLite. Aucun mod, rien a installer chez les joueurs : tout vient de
ce que le serveur ecrit deja dans son journal.

Le journal est relu depuis le debut a chaque demarrage plutot que suivi par
curseur. C'est volontaire : la contrainte UNIQUE rend l'insertion idempotente,
donc une relecture ne cree pas de doublon, et le collecteur se repare tout seul
apres une coupure ou une base supprimee. Sans curseur a maintenir, il n'y a pas
d'etat qui puisse se desynchroniser.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"

# Valheim prefixe ses lignes de son horloge locale : « 09/04/2026 13:43:03: ».
# Les lignes sans ce prefixe (traces Unity, Steam) ne nous interessent pas.
PREFIXE = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2}): (.*)$")

MOTIFS = [
    # « Got connection SteamID 76561198076795149 » : un joueur entre.
    ("connexion", re.compile(r"^Got connection SteamID (\d+)$"), "steamid"),
    # « Closing socket 76561198076795149 » : il sort. Le SteamID permet
    # d'apparier la sortie a l'entree, ce que le pseudo ne permettrait pas.
    ("deconnexion", re.compile(r"^Closing socket (\d+)$"), "steamid"),
    # « Got character ZDOID from Beware : 0:0 » : le 0:0 signale une mort.
    # Tout autre identifiant est une apparition (arrivee ou reapparition).
    ("zdoid", re.compile(r"^Got character ZDOID from (.+?) : (-?\d+):(\d+)$"), "zdoid"),
    # « Random event set:army_theelder » : Valheim ne declenche le raid d'un
    # boss qu'une fois ce boss vaincu. C'est notre seule trace datee de la
    # progression, le journal ne dit rien des global keys.
    ("raid", re.compile(r"^Random event set:(\S+)$"), "detail"),
    ("sauvegarde", re.compile(r"^Saved (\d+) ZDOs$"), "detail"),
    ("jour", re.compile(r"^Time [\d,.]+, day:(\d+) .*$"), "detail"),
    # « Found location of type Dragonqueen » : le serveur localise l'autel d'un
    # boss, ce qui precede la chasse de plusieurs heures. Verifie sur Moder :
    # deux localisations le 08/09 a 22h03 et 22h42, mise a mort le 09/09 a
    # 01h28. C'est la seule source qui annonce une intention et non un fait.
    ("autel", re.compile(r"^Found location of type (\S+)$"), "detail"),
    # « Placed locations in zone 14,-82  duration 67,63 ms » : Valheim peuple
    # une zone la premiere fois qu'un joueur en approche. Donc du terrain neuf,
    # et non du terrain recharge -- verifie le 2026-09-09 : zero ligne dans les
    # 20 minutes suivant les redemarrages de 5h01 du 08 et du 09, alors que la
    # soiree du 08 en compte 56 a 18h, 90 a 19h et 65 a 21h. C'est la seule
    # mesure de l'exploration reelle, celle que le temps de jeu ne dit pas.
    ("zone", re.compile(r"^Placed locations in zone (\S+)\s+duration [\d,.]+ ms$"),
     "detail"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS evenements (
  id          INTEGER PRIMARY KEY,
  horodatage  TEXT NOT NULL,
  monde       TEXT,
  type        TEXT NOT NULL,
  joueur      TEXT,
  steamid     TEXT,
  detail      TEXT
);
-- Unicite pour rendre la relecture du journal idempotente. Elle porte sur des
-- COALESCE et non directement sur les colonnes : dans SQLite deux NULL ne sont
-- jamais egaux, or la plupart des lignes ont des colonnes nulles (pas de pseudo
-- sur une connexion, pas de SteamID sur une mort). Une contrainte UNIQUE posee
-- sur les colonnes brutes ne se declencherait donc jamais et chaque relecture
-- dupliquerait tout le journal.
CREATE UNIQUE INDEX IF NOT EXISTS idx_ev_unique ON evenements (
  horodatage, type, COALESCE(joueur, ''), COALESCE(steamid, ''), COALESCE(detail, '')
);
CREATE INDEX IF NOT EXISTS idx_ev_type  ON evenements (type, horodatage);
CREATE INDEX IF NOT EXISTS idx_ev_joueur ON evenements (joueur, horodatage);

-- Metadonnees des mondes traverses. Le collecteur tourne sous l'utilisateur
-- valheim, seul a pouvoir lire /var/lib/valheim (0750) : il releve la seed ici
-- pour que le rapport, lui, n'ait besoin d'aucun privilege. L'historique sert
-- aussi a garder trace de l'ancien monde quand on en demarre un neuf.
CREATE TABLE IF NOT EXISTS mondes (
  monde              TEXT PRIMARY KEY,
  seed               TEXT,
  seed_entiere       INTEGER,
  version_format     INTEGER,
  version_generateur INTEGER,
  premiere_vue       TEXT,
  derniere_vue       TEXT
);

CREATE TABLE IF NOT EXISTS joueurs (
  steamid      TEXT PRIMARY KEY,
  pseudo       TEXT,
  premiere_vue TEXT,
  derniere_vue TEXT
);
"""


def monde_courant():
    """Nom du monde reellement charge, lu sur la ligne de commande du serveur.

    /etc/valheim.env contient le mot de passe et n'est lisible que par root ;
    le collecteur ne tourne pas en root. Mais il tourne sous le meme
    utilisateur que le serveur de jeu, donc /proc lui est ouvert -- et
    l'argument -world y figure deja developpe.

    C'est plus sur que de lister les .fwl : des qu'un ancien monde traine a
    cote du nouveau, le classement alphabetique designe n'importe lequel des
    deux. La ligne de commande, elle, ne peut pas se tromper.
    """
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                args = f.read().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        if not args or "valheim_server" not in args[0]:
            continue
        if "-world" in args:
            i = args.index("-world")
            if i + 1 < len(args) and args[i + 1]:
                return args[i + 1]
    # Repli si le serveur est arrete : le .fwl le plus recemment ecrit, hors
    # sauvegardes automatiques.
    try:
        actifs = [f for f in os.listdir(SAVEDIR)
                  if f.endswith(".fwl") and "_backup_auto-" not in f]
        if actifs:
            actifs.sort(key=lambda f: os.path.getmtime(os.path.join(SAVEDIR, f)))
            return actifs[-1][:-4]
    except OSError:
        pass
    return None


OUTIL_MONDE = "/usr/local/bin/monde-valheim.py"


def releve_monde(cx, monde):
    """Note la seed et les versions du monde actif.

    Le format du .fwl n'est connu que de monde-valheim.py, appele en
    sous-processus : un seul endroit dans le depot sait decoder ce fichier.
    """
    if not monde:
        return
    chemin = os.path.join(SAVEDIR, monde + ".fwl")
    try:
        r = subprocess.run([OUTIL_MONDE, "lire", "--json", chemin],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return
        i = json.loads(r.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return
    n = datetime.now().isoformat(sep=" ", timespec="seconds")
    cx.execute(
        "INSERT INTO mondes (monde, seed, seed_entiere, version_format, "
        "version_generateur, premiere_vue, derniere_vue) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT (monde) DO UPDATE SET derniere_vue = excluded.derniere_vue, "
        "seed = excluded.seed, version_generateur = excluded.version_generateur",
        (i["monde"], i["seed"], i["seed_entiere"], i["version_format"],
         i["version_generateur"], n, n))
    cx.commit()


def ouvre():
    os.makedirs(os.path.dirname(BASE), exist_ok=True)
    cx = sqlite3.connect(BASE)
    cx.executescript(SCHEMA)
    return cx


def analyse(ligne):
    """Une ligne de journal -> (horodatage, type, joueur, steamid, detail) ou None."""
    m = PREFIXE.match(ligne.rstrip())
    if not m:
        return None
    mois, jour, an, h, mi, s, corps = m.groups()
    ts = "%s-%s-%s %s:%s:%s" % (an, mois, jour, h, mi, s)
    for nom, motif, forme in MOTIFS:
        c = motif.match(corps)
        if not c:
            continue
        if forme == "steamid":
            return (ts, nom, None, c.group(1), None)
        if forme == "detail":
            return (ts, nom, None, None, c.group(1))
        # zdoid : 0:0 vaut mort, le reste vaut apparition
        # Le separateur du log est «  :  », donc la capture non gourmande du
        # pseudo ramene l'espace qui precede : « Bab-y » sortirait « Bab-y ».
        pseudo, zdo, sous = c.group(1).strip(), c.group(2), c.group(3)
        if zdo == "0" and sous == "0":
            return (ts, "mort", pseudo, None, None)
        return (ts, "apparition", pseudo, None, "%s:%s" % (zdo, sous))
    return None


def relie_pseudos(cx):
    """Associe chaque SteamID a un pseudo.

    Le pseudo n'apparait que sur les lignes ZDOID, le SteamID que sur les
    lignes de connexion : rien ne les relie directement. On exploite la
    sequence -- une apparition suit toujours de quelques secondes la connexion
    qui l'a provoquee. L'association n'est retenue que si une seule connexion
    est en attente dans la fenetre, sinon deux joueurs entrant ensemble
    donneraient une correspondance fausse.
    """
    lignes = cx.execute(
        "SELECT horodatage, type, joueur, steamid FROM evenements "
        "WHERE type IN ('connexion', 'apparition') ORDER BY horodatage, id"
    ).fetchall()
    attente = []  # [(horodatage, steamid)]
    for ts, typ, joueur, steamid in lignes:
        t = datetime.fromisoformat(ts)
        attente = [(a, sid) for (a, sid) in attente if t - a <= timedelta(seconds=180)]
        if typ == "connexion":
            attente.append((t, steamid))
            continue
        if len(attente) != 1:
            continue  # ambigu : on ne devine pas
        _, sid = attente.pop()
        cx.execute(
            "INSERT INTO joueurs (steamid, pseudo, premiere_vue, derniere_vue) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (steamid) DO UPDATE SET "
            "pseudo = excluded.pseudo, derniere_vue = excluded.derniere_vue",
            (sid, joueur, ts, ts),
        )
    cx.commit()


def enregistre(cx, monde, lot):
    avant = cx.execute("SELECT count(*) FROM evenements").fetchone()[0]
    cx.executemany(
        "INSERT OR IGNORE INTO evenements "
        "(horodatage, monde, type, joueur, steamid, detail) VALUES (?, ?, ?, ?, ?, ?)",
        [(ts, monde, typ, j, sid, d) for (ts, typ, j, sid, d) in lot],
    )
    cx.commit()
    return cx.execute("SELECT count(*) FROM evenements").fetchone()[0] - avant


def rattrapage(cx, depuis):
    monde = monde_courant()
    cmd = ["journalctl", "-u", "valheim", "-o", "cat", "--no-pager"]
    if depuis:
        cmd += ["--since", depuis]
    sortie = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    lot = [e for e in (analyse(l) for l in sortie.stdout.splitlines()) if e]
    releve_monde(cx, monde)
    return len(lot), enregistre(cx, monde, lot)


def suit(cx):
    monde = monde_courant()
    p = subprocess.Popen(
        ["journalctl", "-u", "valheim", "-o", "cat", "-f", "-n", "0"],
        stdout=subprocess.PIPE, text=True, errors="replace", bufsize=1,
    )
    for ligne in p.stdout:
        e = analyse(ligne)
        if not e:
            continue
        # Un changement de monde (9 septembre : nouveau monde 1.0) doit etre vu
        # sans redemarrer le collecteur, sinon les evenements du monde neuf
        # seraient etiquetes avec l'ancien nom.
        if e[1] == "connexion":
            neuf = monde_courant()
            if neuf and neuf != monde:
                monde = neuf
                releve_monde(cx, monde)
        enregistre(cx, monde, [e])
        if e[1] in ("connexion", "apparition"):
            relie_pseudos(cx)
        sys.stdout.write("%s %s %s\n" % (e[0], e[1], e[2] or e[3] or e[4] or ""))
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rattrapage-seul", action="store_true",
                    help="relit le journal et sort, sans suivre")
    ap.add_argument("--depuis", default=None,
                    help="date de depart du rattrapage (defaut : tout le journal)")
    a = ap.parse_args()

    cx = ouvre()
    lus, neufs = rattrapage(cx, a.depuis)
    relie_pseudos(cx)
    print("rattrapage : %d evenements reconnus, %d nouveaux" % (lus, neufs))
    if a.rattrapage_seul:
        return
    suit(cx)


if __name__ == "__main__":
    main()
