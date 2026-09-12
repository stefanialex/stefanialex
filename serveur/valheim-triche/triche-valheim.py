#!/usr/bin/env python3
"""Surveille la contamination « triche » du monde Valheim.

Pourquoi cette routine existe. Le 2026-09-12 au soir, le jeu a affiche un
message d'objet triche alors que personne n'avait touche a une console -- il
n'y a meme pas d'admin dans la partie. Le balayage des 120 archives a montre
un monde parfaitement propre du 28/08 au 12/09 21:00:42, puis deux entites
marquees a 21:32:26. Sans releve, on ne l'aurait jamais date, et on aurait
cherche la cause au mauvais endroit pendant des jours.

Ce qui est marque, et par quoi. Lu dans l'IL de assembly_valheim.dll :

  Character::ApplyDamage   marque la VICTIME si l'attaquant a une arme
                           trichee EQUIPEE qui fait des degats, ou vole en
                           debug, ou est en god mode, ou en ghost mode, ou
                           est LUI-MEME DEJA MARQUE, ou si le coup depasse
                           99 999 de degats.
  Character::OnDeath       recopie le drapeau sur le CharacterDrop, donc sur
                           le butin.
  Ragdoll::Setup/SpawnLoot idem pour le cadavre et ce qu'il lache.
  Player::TryPlacePiece    marque la CONSTRUCTION si les materiaux consommes
                           sont marques (Inventory::ItemCheated) ou si le
                           joueur est en NoCostCheat.
  InventoryGui::DoCrafting idem pour l'objet fabrique.

Il n'y a donc aucune generation spontanee : chaque marque vient d'une marque
anterieure. La contagion circule seule dans la faune -- les mobs se battent
entre eux -- et remonte jusqu'a nous par le butin, puis repart dans nos
constructions et nos fabrications des qu'on utilise le materiau contamine.

Ce que ca coute vraiment. Le controle des succes est VIVANT et LOCAL :
Inventory::AnyCheatedItem sur l'inventaire du joueur, evalue en continu. Il
empeche d'ENREGISTRER un nouveau succes tant qu'on porte un objet marque ; il
n'en retire aucun. Poser l'objet suffit a redebloquer. Rien n'est perdu.

Deux compteurs, a ne pas confondre :

  - les ZDO marques : creatures, coffres, constructions. Champ « cheated »
    dans le ZDO, trouve par son hash stable.
  - les objets marques : bit 0 du second masque, a la fin du blob ItemData.

Un monde sans ZDO marque peut contenir des objets marques, et l'inverse. Les
deux sont donc releves separement.

Limite a connaitre : les sacs des joueurs ne sont PAS dans le fichier de
monde. Ils vivent dans le fichier de personnage, chez chaque joueur. Ce
releve ne les voit pas, et une restauration du monde ne les nettoie pas.
"""

import argparse
import collections
import glob
import json
import os
import sqlite3
import struct
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"
CONF = "/etc/valheim-discord.conf"
ARTISAN = "/usr/local/bin/artisan-valheim.py"
AGENT = "valheim-serveur/1.0 (surveillance triche)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS triche_releves (
  monde     TEXT NOT NULL,
  quand     TEXT NOT NULL,
  zdos      INTEGER NOT NULL,
  objets    INTEGER NOT NULL,
  detail    TEXT NOT NULL,
  PRIMARY KEY (monde, quand)
);
"""


def hash_stable(s):
    """StringExtensionMethods.GetStableHashCode : deux djb2 entrelaces.

    Le XOR compte : avec une addition a la place, le hash de « cheated »
    tombe a cote et le balayage renvoie zero partout -- sans erreur, ce qui
    ferait croire a un monde sain.
    """
    a = b = 5381
    i = 0
    while i < len(s):
        a = (((a << 5) + a) ^ ord(s[i])) & 0xFFFFFFFF
        if i + 1 >= len(s):
            break
        b = (((b << 5) + b) ^ ord(s[i + 1])) & 0xFFFFFFFF
        i += 2
    v = (a + b * 1566083941) & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


CHEATED = struct.pack("<i", hash_stable("cheated"))
ENTETE_INVENTAIRE = struct.pack("<i", 109)


def monde_actif():
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


def charge_artisan():
    """Le decodeur d'inventaire, s'il est installe. Sans lui on ne compte que
    les ZDO -- degrade, mais pas muet : c'est le compteur de ZDO qui a permis
    de dater la contamination."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("artisan", ARTISAN)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    except Exception as e:
        print("decodeur d'objets indisponible (%s) : on ne compte que les ZDO" % e,
              file=sys.stderr)
        return None


def zdos_marques(d):
    """Positions du champ « cheated » valant 1.

    On lit l'octet qui suit le hash : le champ existe aussi a 0, et compter
    les seules presences du hash donnerait un marque partout.
    """
    out = []
    i = -1
    while True:
        i = d.find(CHEATED, i + 1)
        if i < 0:
            return out
        if i + 5 <= len(d) and d[i + 4] == 1:
            out.append(i)


def objets_marques(d, artisan, table):
    """Piles d'objets portant le bit de triche, par nom de prefab.

    On part de l'en-tete d'inventaire -- version 109 puis le nombre d'objets
    sur un uint16 -- et on exige que les N objets se decodent d'affilee. Un
    alignement faux ne retombe pas sur une frontiere coherente : le lot est
    alors rejete en entier plutot que de produire des noms inventes.
    """
    compte = collections.Counter()
    if artisan is None:
        return compte
    i = -1
    while True:
        i = d.find(ENTETE_INVENTAIRE, i + 1)
        if i < 0:
            return compte
        p = i + 4
        if p + 2 > len(d):
            continue
        nb, = struct.unpack_from("<H", d, p)
        p += 2
        if not 1 <= nb <= 64:
            continue
        lot = []
        for _ in range(nb):
            o, q = artisan.lis_objet(d, p)
            if o is None:
                lot = None
                break
            lot.append((o, d[q - 1] & 1))
            p = q
        if not lot:
            continue
        for o, triche in lot:
            if triche:
                n = table.get(o["prefab"], "?") if table else str(o["prefab"])
                compte["/".join(n) if isinstance(n, list) else n] += 1


def releve(dossier, artisan, table):
    zdos = collections.Counter()
    objets = collections.Counter()
    for f in sorted(glob.glob(os.path.join(dossier, "*.chunk"))):
        region = os.path.basename(f).split("__")[0]
        with open(f, "rb") as fh:
            d = fh.read()
        n = len(zdos_marques(d))
        if n:
            zdos[region] += n
        objets.update(objets_marques(d, artisan, table) or {})
    return zdos, objets


def annonce(texte):
    try:
        with open(CONF) as f:
            url = next(l.split("=", 1)[1].strip().strip('"')
                       for l in f if l.startswith("WEBHOOK="))
    except (OSError, StopIteration):
        return
    corps = json.dumps({"content": texte,
                        "allowed_mentions": {"parse": []}}).encode()
    r = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    try:
        urllib.request.urlopen(r, timeout=15)
    except (urllib.error.URLError, OSError) as e:
        print("annonce non partie : %s" % e, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--muet", action="store_true", help="ne rien publier sur Discord")
    ap.add_argument("--quand-meme", action="store_true",
                    help="publie meme si le compte n'a pas augmente")
    ap.add_argument("--dossier", help="auditer ce dossier de monde au lieu du monde actif")
    o = ap.parse_args()

    if o.dossier:
        monde, dossier = os.path.basename(o.dossier.rstrip("/")), o.dossier
    else:
        monde = monde_actif()
        if not monde:
            print("serveur arrete : rien a relever")
            return 0
        dossier = os.path.join(SAVEDIR, monde)
    if not os.path.isdir(dossier):
        print("dossier de monde introuvable : %s" % dossier, file=sys.stderr)
        return 1

    artisan = charge_artisan()
    table = artisan.table_prefabs() if artisan else None
    zdos, objets = releve(dossier, artisan, table)
    nz, no = sum(zdos.values()), sum(objets.values())

    detail = json.dumps({"zdos": dict(zdos), "objets": dict(objets)},
                        ensure_ascii=False, sort_keys=True)
    print("%s : %d ZDO marque(s) %s, %d pile(s) d'objets marquee(s) %s" % (
        monde, nz, dict(zdos) or "", no, dict(objets.most_common(10)) or ""))

    if o.dossier:
        return 0

    cx = sqlite3.connect(BASE)
    cx.executescript(SCHEMA)
    avant = cx.execute("SELECT zdos, objets FROM triche_releves WHERE monde = ? "
                       "ORDER BY quand DESC LIMIT 1", (monde,)).fetchone()
    maintenant = datetime.now().isoformat(sep=" ", timespec="seconds")
    cx.execute("INSERT OR REPLACE INTO triche_releves "
               "(monde, quand, zdos, objets, detail) VALUES (?, ?, ?, ?, ?)",
               (monde, maintenant, nz, no, detail))
    cx.commit()

    if avant is None:
        print("premier releve : rien a comparer")
        return 0
    monte = nz > avant[0] or no > avant[1]
    if not monte and not o.quand_meme:
        return 0
    if o.muet:
        return 0
    corps = ["⚠️  **Contamination « triche » en hausse**",
             "ZDO marqués : **%d** (avant %d) — %s" % (
                 nz, avant[0], ", ".join("%s×%d" % kv for kv in zdos.most_common(6)) or "aucun"),
             "Piles d'objets marquées : **%d** (avant %d) — %s" % (
                 no, avant[1], ", ".join("%s×%d" % kv for kv in objets.most_common(6)) or "aucune"),
             "",
             "Rappel : ça ne retire aucun succès déjà gagné. Ça empêche seulement "
             "d'en enregistrer un nouveau **tant qu'on porte** un objet marqué. "
             "Poser l'objet suffit. Et surtout : ne construisez ni ne fabriquez "
             "rien avec un matériau marqué — la marque passe dans l'objet fini."]
    annonce("\n".join(corps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
