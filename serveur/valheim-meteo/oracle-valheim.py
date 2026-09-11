#!/usr/bin/env python3
"""L'oracle : des indices tires du monde reel, dits a demi-mot.

Le serveur sait ou se trouvent les lieux que le groupe a fait generer -- autels
de boss, cryptes, grottes a trolls -- parce qu'il ecrit une ligne a chaque fois
qu'il en pose un. Cet oracle croise ces lieux avec l'avancement du groupe et en
tire un indice, formule de facon volontairement vague.

Pourquoi vague. Alexandre a demande un « coach et maitre du jeu », pas un
guide de solution. Donner « l'autel est en (384, -256) » supprime l'exploration,
qui est le coeur du jeu. Donner « quelque chose de plus vieux que vous repose a
cinq cents pas vers le levant » oriente sans reveler : le groupe garde le
plaisir de chercher, et l'indice reste vrai.

D'ou trois regles d'ecriture, tenues par le code et pas par la bonne volonte :

  - jamais de coordonnee exacte : direction cardinale et distance arrondie a la
    centaine de pas ;
  - jamais plus d'un indice par sujet et par jour ;
  - rien sur ce que le groupe a deja trouve -- l'oracle se tait sur les boss
    vaincus, et ne parle que de l'etape en cours.

Ce que l'oracle NE sait pas, et il ne doit pas faire semblant : la carte
complete. Il ne connait que ce que le serveur a genere parce qu'un joueur s'en
est approche. Tout le reste du monde n'existe pas encore sur le disque.

Usage :
    oracle-valheim.py                 # l'indice du jour
    oracle-valheim.py --json
    oracle-valheim.py --tout          # tout ce que l'oracle sait, pour debug
"""

import argparse
import datetime
import json
import math
import os
import re
import urllib.error
import urllib.request
import sqlite3
import subprocess
import sys

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
CONF = "/etc/valheim-discord.conf"
AGENT = "valheim-serveur/1.0 (collecteur de statistiques auto-heberge)"
# Le meme nom que le reste du salon : l'oracle n'est pas un second personnage,
# c'est la meme voix qui parle a demi-mot.
NOM_AFFICHE = "Claudo Le Viking"
ZONE = 64.0          # cote d'une zone Valheim, en metres

LIGNE = re.compile(r"Placed location (\w+) in zone (-?\d+),(-?\d+)")

# Les boss, dans l'ordre, avec le nom du lieu de leur autel.
ETAPES = [
    ("defeated_eikthyr", "Eikthyr", "Eikthyrnir"),
    ("defeated_gdking", "l'Ancien", "GDKing"),
    ("defeated_bonemass", "Bonemass", "Bonemass"),
    ("defeated_dragon", "Moder", "Dragonqueen"),
    ("defeated_goblinking", "Yagluth", "GoblinKing"),
]

# Ce qui merite un indice, et comment le nommer sans le nommer.
MURMURES = {
    "Eikthyrnir": "quelque chose de plus vieux que vous",
    "GDKing": "des pierres dressees que la foret protege",
    "Bonemass": "une odeur qui monte des eaux mortes",
    "Dragonqueen": "un souffle froid, tout en haut",
    "GoblinKing": "des feux qui brulent dans la plaine",
    "Crypt2": "des tombes que la Foret Noire garde",
    "Crypt3": "des tombes que la Foret Noire garde",
    "Crypt4": "des tombes que la Foret Noire garde",
    "TrollCave02": "un antre ou dort quelque chose de grand",
    "Vendor_BlackForest": "un marchand, si on sait ecouter",
    "SunkenCrypt4": "des cryptes noyees",
    "Grave1": "des morts mal enterres",
    "StoneTowerRuins07": "des tours qui ne tiennent plus",
    "StoneTowerRuins09": "des tours qui ne tiennent plus",
    "StoneTowerRuins10": "des tours qui ne tiennent plus",
    "BearCave": "une tanniere chaude",
    "Runestone_Meadows": "une pierre qui parle",
}

CARDINAUX = [(0, "au nord"), (45, "au nord-est"), (90, "au levant"),
             (135, "au sud-est"), (180, "au sud"), (225, "au sud-ouest"),
             (270, "au couchant"), (315, "au nord-ouest")]


def direction(x, z):
    """Un point cardinal, en mots. Le nord de Valheim est le +Z."""
    angle = (math.degrees(math.atan2(x, z)) + 360) % 360
    return min(CARDINAUX, key=lambda c: min(abs(angle - c[0]),
                                            360 - abs(angle - c[0])))[1]


def pas(distance):
    """Une distance arrondie a la centaine, dite en pas plutot qu'en metres.

    L'arrondi n'est pas cosmetique : il empeche l'oracle de servir de GPS.
    """
    return int(round(distance / 100.0) * 100)


def monde_courant():
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                args = f.read().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        if args and "valheim_server" in args[0] and "-world" in args:
            i = args.index("-world")
            if i + 1 < len(args) and args[i + 1]:
                return args[i + 1]
    return None


def lieux(depuis):
    """Les lieux generes depuis une date, par type, en coordonnees de monde.

    Lus dans le journal et non en base : le collecteur ne retient que la zone,
    pas le type de lieu. Consequence a connaitre -- la profondeur du journal
    limite la memoire de l'oracle, qui oubliera les lieux les plus anciens.
    """
    cmd = ["journalctl", "-u", "valheim", "-o", "cat", "--no-pager"]
    if depuis:
        cmd += ["--since", depuis]
    try:
        sortie = subprocess.run(cmd, capture_output=True, text=True,
                                errors="replace", timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    trouves = {}
    for m in LIGNE.finditer(sortie):
        nom, zx, zy = m.group(1), int(m.group(2)), int(m.group(3))
        trouves.setdefault(nom, set()).add((zx * ZONE, zy * ZONE))
    return {n: sorted(p) for n, p in trouves.items()}


def etape(cx, monde):
    """Le prochain boss a abattre, d'apres les cles globales du monde."""
    vaincus = {c for (c,) in cx.execute(
        "SELECT cle FROM cles_globales WHERE monde IS ?", (monde,))}
    for cle, nom, lieu in ETAPES:
        if cle not in vaincus:
            return cle, nom, lieu
    return None, None, None


def indices(cx, monde, tous=False):
    """Les indices disponibles, du plus pertinent au moins."""
    debut = cx.execute(
        "SELECT min(horodatage) FROM evenements WHERE monde IS ?",
        (monde,)).fetchone()
    trouves = lieux(debut[0] if debut and debut[0] else None)
    _cle, nom_boss, lieu_boss = etape(cx, monde)

    sortie = []
    if lieu_boss and trouves.get(lieu_boss):
        proche = min(trouves[lieu_boss], key=lambda p: math.hypot(*p))
        d = math.hypot(*proche)
        sortie.append({
            "sujet": "boss",
            "texte": "%s repose a quelque %d pas %s. Vous etes passes assez "
                     "pres pour que la terre s'en souvienne."
                     % (MURMURES.get(lieu_boss, "quelque chose").capitalize(),
                        pas(d), direction(*proche)),
        })

    cryptes = [p for n in ("Crypt2", "Crypt3", "Crypt4") for p in trouves.get(n, [])]
    if cryptes:
        # La grappe : le quadrant qui en compte le plus.
        quadrants = {}
        for x, z in cryptes:
            quadrants.setdefault(direction(x, z), []).append((x, z))
        # A nombre egal, la direction la plus PROCHE : le 2026-09-09 l'oracle
        # designait six tombes a 1100 pas au sud-est alors que six autres
        # attendaient a 830 pas au levant. Un indice juste mais moins utile
        # qu'un autre reste un mauvais indice.
        ou, groupe = min(
            quadrants.items(),
            key=lambda kv: (-len(kv[1]),
                            sum(math.hypot(*p) for p in kv[1]) / len(kv[1])))
        d = sum(math.hypot(*p) for p in groupe) / len(groupe)
        sortie.append({
            "sujet": "cryptes",
            "texte": "Les tombes de la Foret Noire ne sont pas dispersees au "
                     "hasard : %d d'entre elles se serrent %s, a quelque %d pas."
                     % (len(groupe), ou, pas(d)),
        })

    for nom in ("Vendor_BlackForest", "TrollCave02", "BearCave"):
        if trouves.get(nom):
            proche = min(trouves[nom], key=lambda p: math.hypot(*p))
            sortie.append({
                "sujet": nom,
                "texte": "%s, a quelque %d pas %s."
                         % (MURMURES.get(nom, nom).capitalize(),
                            pas(math.hypot(*proche)), direction(*proche)),
            })

    if not trouves:
        sortie.append({
            "sujet": "rien",
            "texte": "Le monde ne m'a encore rien dit. Marchez, et je verrai.",
        })
    return sortie if tous else sortie


def annonce(texte):
    """Publie dans le salon. Silencieux si le webhook n'est pas configure : le
    programme doit rester lancable sur une machine neuve."""
    try:
        with open(CONF) as f:
            url = next(l.split("=", 1)[1].strip().strip('"')
                       for l in f if l.startswith("WEBHOOK="))
    except (OSError, StopIteration):
        print("pas de webhook configure, rien publie", file=sys.stderr)
        return False
    corps = json.dumps({"content": texte, "username": NOM_AFFICHE,
                        "allowed_mentions": {"parse": []}}).encode()
    r = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    try:
        urllib.request.urlopen(r, timeout=15)
    except (urllib.error.URLError, OSError) as e:
        print("annonce non partie : %s" % e, file=sys.stderr)
        return False
    return True


def deja_dit_aujourd_hui(jour):
    """Un indice par jour, et pas un de plus.

    La rotation est deterministe sur la date, donc deux lancements le meme jour
    rediraient mot pour mot la meme chose. Le garde-fou est en base plutot que
    dans la minuterie : une minuterie « Persistent » rattrape un passage manque
    au demarrage, et c'est justement la qu'on republierait.
    """
    cx = sqlite3.connect(BASE)
    try:
        cx.execute("CREATE TABLE IF NOT EXISTS reglages "
                   "(cle TEXT PRIMARY KEY, valeur TEXT)")
        r = cx.execute(
            "SELECT valeur FROM reglages WHERE cle = 'oracle_dernier_jour'").fetchone()
        if r and r[0] == jour:
            return True
        cx.execute("INSERT INTO reglages (cle, valeur) VALUES "
                   "('oracle_dernier_jour', ?) ON CONFLICT (cle) DO UPDATE SET "
                   "valeur = excluded.valeur", (jour,))
        cx.commit()
        return False
    except sqlite3.OperationalError as e:
        # Base non inscriptible : on ne publie PAS. Sans la marque, un second
        # passage rediraient le meme indice dans le salon, et deux fois le meme
        # oracle dans la journee le decredibilise. Echouer bruyamment vaut
        # mieux que publier en double.
        raise SystemExit("base non inscriptible (%s) : rien publie. Ce "
                         "programme doit tourner sous le compte valheim." % e)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tout", action="store_true",
                    help="tous les indices, sans rotation")
    ap.add_argument("--discord", action="store_true",
                    help="publie l'indice du jour dans le salon")
    ap.add_argument("--quand-meme", action="store_true",
                    help="publie meme si c'est deja fait aujourd'hui")
    o = ap.parse_args()

    monde = monde_courant()
    cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
    tous = indices(cx, monde, tous=True)
    if not tous:
        return 0
    if o.tout:
        choisis = tous
    else:
        # Rotation deterministe sur la date : chacun revient regulierement,
        # aucun n'est oublie, et deux jours de suite ne se ressemblent pas.
        jour = datetime.date.today().toordinal()
        choisis = [tous[jour % len(tous)]]

    if o.discord:
        jour = datetime.date.today().isoformat()
        if not o.quand_meme and deja_dit_aujourd_hui(jour):
            print("indice du %s deja publie" % jour)
            return 0
        texte = "\n".join("🔮  " + i["texte"] for i in choisis)
        if not annonce(texte):
            return 1
        print("publie : %s" % texte.replace("\n", " / "))
        return 0

    if o.json:
        print(json.dumps({"monde": monde, "indices": choisis}, ensure_ascii=False))
    else:
        for i in choisis:
            print("🔮  " + i["texte"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
