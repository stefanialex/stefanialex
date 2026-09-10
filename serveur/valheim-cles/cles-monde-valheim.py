#!/usr/bin/env python3
"""Releve les « global keys » du monde Valheim : la progression exacte.

Pourquoi cette routine existe. La progression etait deduite des raids, et
c'etait faux : un raid n'est pas debloque par le boss dont il porte le nom mais
par le precedent. « army_theelder » exige defeated_eikthyr, « army_bonemass »
exige defeated_gdking. La lecture etait donc decalee d'un boss -- et le defi de
Bab-y, ancre sur la chute de l'Ancien, comptait les morts a partir de la
mauvaise date.

Les global keys, elles, ne se deduisent pas : elles sont ecrites dans le
fichier de monde. Elles n'ont pas d'horodatage, d'ou cette routine : en
relevant regulierement, on date le passage d'absente a presente.

Le fichier fait 14 Mo et son format complet exige de parcourir tous les ZDO.
On ne le parcourt pas : on cherche les chaines connues sous leur forme Unity,
un octet de longueur suivi du texte. Verifie sur le monde en place avant la
1.0 -- chaque cle presente apparaissait exactement une fois, a 97,7 % du
fichier, la ou vivent les global keys.

Depuis la 1.0 (2026-09-09), le contenu du monde est un flux **gzip** dans un
fichier « _main.N.db2 » range dans le dossier du monde. La recherche se fait
donc sur les octets decompresses, et la remarque sur les 97,7 % ne vaut plus
que pour les archives d'avant la mise a jour. Les deux formats restent lus,
pour pouvoir relire une archive ancienne.
"""

import argparse
import json
import os
import re
import sqlite3
import struct
import subprocess
import sys
import zlib
import urllib.error
import urllib.request
from datetime import datetime

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"
CONF = "/etc/valheim-discord.conf"
AGENT = "valheim-serveur/1.0 (releve des cles de monde)"

# Les boss, dans l'ordre de progression. Le nom interne ne ressemble pas
# toujours au nom affiche : gdking est l'Ancien, dragon est Moder.
BOSS = [
    ("defeated_eikthyr", "Eikthyr"),
    ("defeated_gdking", "l'Ancien"),
    ("defeated_bonemass", "Bonemass"),
    ("defeated_dragon", "Moder"),
    ("defeated_goblinking", "Yagluth"),
    ("defeated_queen", "la Reine"),
    ("defeated_fader", "Fader"),
]
# La cle du boss du Deep North n'est pas connue avant la 1.0 : elle sera a
# ajouter ici une fois le nom sorti.
AUTRES = ["killed_surtling", "KilledTroll", "KilledBat", "nonstop_raids"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS cles_globales (
  monde        TEXT NOT NULL,
  cle          TEXT NOT NULL,
  premiere_vue TEXT NOT NULL,
  certaine     INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (monde, cle)
);

-- La trace du passage, monde par monde. Sans elle, un monde neuf n'a aucune
-- cle, donc rien a inscrire, donc le releve se croyait le premier a chaque
-- tour : « premier releve : aucun boss » toutes les cinq minutes pendant huit
-- heures, le 2026-09-10. Le bruit n'etait que le symptome. Le vrai degat
-- attendait la suite : le premier boss a tomber aurait ete inscrit
-- « certaine = 0 », date incertaine, alors qu'on interroge le monde toutes
-- les cinq minutes et qu'on connaissait donc l'heure a cinq minutes pres.
CREATE TABLE IF NOT EXISTS releves_monde (
  monde         TEXT PRIMARY KEY,
  premier       TEXT NOT NULL,
  dernier       TEXT NOT NULL
);
"""


def monde_actif():
    """Nom du monde charge, lu sur la ligne de commande du serveur."""
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


def fichier_monde(monde):
    """Le fichier de contenu a lire, dans l'un ou l'autre format.

    On prefere la sauvegarde precedente : elle est complete par construction,
    alors que le fichier actif peut etre en cours d'ecriture au moment ou on le
    lit -- 14 Mo ne s'ecrivent pas instantanement. Le retard vaut au plus un
    intervalle de sauvegarde, dix minutes ici, ce qui est sans consequence pour
    detecter la chute d'un boss.

    Avant la 1.0 cette sauvegarde s'appelait « Midgard.db.old ». Depuis, un
    monde vit dans son dossier et ses fichiers sont numerotes :
    « NordheimV1/_main.1.db2 ». Quand plusieurs generations coexistent, on
    prend l'avant-derniere, pour la meme raison qu'on preferait « .db.old ».
    """
    dossier = os.path.join(SAVEDIR, monde)
    if os.path.isdir(dossier):
        generations = []
        try:
            for f in os.listdir(dossier):
                if f.startswith("_main.") and f.endswith(".db2"):
                    try:
                        generations.append((int(f.split(".")[1]),
                                            os.path.join(dossier, f)))
                    except ValueError:
                        pass
        except OSError:
            generations = []
        if generations:
            generations.sort()
            return generations[-2][1] if len(generations) > 1 else generations[-1][1]
    for nom in ("%s.db.old" % monde, "%s.db" % monde):
        chemin = os.path.join(SAVEDIR, nom)
        if os.path.exists(chemin):
            return chemin
    return None


def contenu(chemin):
    """Les octets a fouiller, decompresses si le format l'exige.

    Le .db2 de la 1.0 est un flux gzip precede d'un en-tete de seize octets --
    version en int32, temps du monde en double, longueur du flux en int32 --
    et suivi de quarante octets de pied. Chercher une cle dans le fichier brut
    ne renvoie donc plus jamais rien, et **sans erreur** : la detection des
    boss s'arreterait en silence, ce qui est exactement le genre de panne
    qu'on ne remarque qu'apres des semaines de statistiques fausses.
    """
    with open(chemin, "rb") as f:
        d = f.read()
    if not chemin.endswith(".db2"):
        return d
    taille = struct.unpack_from("<i", d, 12)[0]
    return zlib.decompressobj(31).decompress(d[16:16 + taille])


def cles_presentes(chemin):
    """Cles trouvees dans le fichier, sous leur forme Unity."""
    d = contenu(chemin)
    trouvees = []
    for cle in [c for c, _ in BOSS] + AUTRES:
        b = cle.encode()
        if len(b) > 127:
            continue  # au-dela, la longueur Unity tient sur deux octets
        if re.search(re.escape(bytes([len(b)]) + b), d):
            trouvees.append(cle)
    return trouvees


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
    ap.add_argument("--liste", action="store_true", help="affiche l'etat et sort")
    ap.add_argument("--bavard", action="store_true",
                    help="ecrit une ligne meme quand rien n'a change")
    o = ap.parse_args()

    monde = monde_actif()
    if not monde:
        print("serveur arrete : rien a relever")
        return 0
    chemin = fichier_monde(monde)
    if not chemin:
        print("aucun fichier de monde pour %s" % monde, file=sys.stderr)
        return 1

    cx = sqlite3.connect(BASE)
    cx.executescript(SCHEMA)

    connues = {c: (v, cert) for c, v, cert in cx.execute(
        "SELECT cle, premiere_vue, certaine FROM cles_globales WHERE monde = ?",
        (monde,))}
    deja_releve = cx.execute(
        "SELECT 1 FROM releves_monde WHERE monde = ?", (monde,)).fetchone() is not None

    if o.liste:
        for cle, nom in BOSS:
            if cle in connues:
                v, cert = connues[cle]
                print("  %-14s vaincu %s %s" % (
                    nom, "le" if cert else "avant le", v[:16]))
            else:
                print("  %-14s pas encore" % nom)
        return 0

    presentes = cles_presentes(chemin)
    maintenant = datetime.now().isoformat(sep=" ", timespec="seconds")
    # Au tout premier relevé, ce qui est deja la n'a pas de date : on l'inscrit
    # comme incertaine plutot que de laisser croire que le boss vient de tomber.
    premier_releve = not deja_releve
    nouvelles = []
    for cle in presentes:
        if cle in connues:
            continue
        cx.execute("INSERT OR IGNORE INTO cles_globales "
                   "(monde, cle, premiere_vue, certaine) VALUES (?, ?, ?, ?)",
                   (monde, cle, maintenant, 0 if premier_releve else 1))
        nouvelles.append(cle)
    cx.execute("INSERT INTO releves_monde (monde, premier, dernier) VALUES (?, ?, ?) "
               "ON CONFLICT (monde) DO UPDATE SET dernier = excluded.dernier",
               (monde, maintenant, maintenant))
    cx.commit()

    noms = dict(BOSS)
    if premier_releve:
        deja = [noms[c] for c, _ in BOSS if c in presentes]
        print("premier releve du monde %s : %s" % (monde, ", ".join(deja) or "aucun boss"))
        return 0

    for cle in nouvelles:
        if cle in noms:
            print("BOSS VAINCU : %s (%s)" % (noms[cle], cle))
            if not o.muet:
                annonce("🏆  **%s est tombé !** Le monde vient d'enregistrer "
                        "`%s`.\nLes défis ancrés sur ce boss repartent d'ici."
                        % (noms[cle], cle))
        else:
            print("nouvelle cle : %s" % cle)
    # Rien de neuf : on se tait. Ce releve tourne toutes les cinq minutes, et
    # une ligne par tour noie dans le journal les seules qui comptent, celles
    # qui annoncent un boss. --bavard les rend pour le diagnostic.
    if not nouvelles and o.bavard:
        print("aucun changement (%d cle(s) connues)" % len(connues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
