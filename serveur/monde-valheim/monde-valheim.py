#!/usr/bin/env python3
"""Lit et fabrique les fichiers .fwl de Valheim (metadonnees de monde).

Le serveur dedie n'a pas de parametre -seed : lance sur un nom de monde
inexistant, il tire une seed au hasard. La methode habituelle consiste a creer
le monde sur un PC client puis a copier les fichiers, ce qui suppose qu'un
joueur soit disponible et sur la bonne version.

Ce script court-circuite ce detour en ecrivant directement le .fwl. Le serveur
genere ensuite le .db lui-meme au premier demarrage : le monde de Valheim est
produit zone par zone a la demande, seule la seed doit etre fixee d'avance.

Le format est un « package » Unity : un entier de longueur, puis la version de
format, le nom du monde, le nom de la seed, la seed entiere, un identifiant
unique et la version du generateur de monde.
"""

import argparse
import io
import json
import os
import random
import string
import struct
import sys

# Version de format et de generateur observees sur le monde en place (Valheim
# 0.2xx, septembre 2026). Le .fwl du monde courant sert de reference : si la 1.0
# change ces nombres, les relire sur un monde cree par la 1.0 avant d'ecrire.
VERSION_FORMAT = 37
VERSION_GENERATEUR = 2


def hash_stable(s):
    """GetStableHashCode() de Valheim, reimplementee.

    Valheim ne stocke pas seulement le nom de la seed mais aussi sa valeur
    entiere, et c'est cet entier que le generateur utilise. Les deux doivent
    concorder, sinon le jeu afficherait un nom de seed qui ne correspond pas au
    monde genere. Verifiee contre le monde « Midgard » : m24VpSVsVw -> 2007084186.
    """
    def i32(x):
        x &= 0xFFFFFFFF
        return x - 0x100000000 if x >= 0x80000000 else x

    h1 = h2 = 5381
    i = 0
    while i < len(s):
        h1 = i32(((h1 << 5) + h1) ^ ord(s[i]))
        if i == len(s) - 1:
            break
        h2 = i32(((h2 << 5) + h2) ^ ord(s[i + 1]))
        i += 2
    return i32(h1 + i32(h2 * 1566083941))


def lit_chaine(f):
    """Chaine Unity : longueur en entier 7 bits par octet, puis UTF-8."""
    n = s = 0
    while True:
        b = f.read(1)[0]
        n |= (b & 0x7F) << s
        if not b & 0x80:
            break
        s += 7
    return f.read(n).decode("utf-8")


def ecrit_chaine(f, texte):
    b = texte.encode("utf-8")
    n = len(b)
    while True:
        o = n & 0x7F
        n >>= 7
        f.write(bytes([o | (0x80 if n else 0)]))
        if not n:
            break
    f.write(b)


def lire(chemin):
    d = open(chemin, "rb").read()
    f = io.BytesIO(d)
    annonce = struct.unpack("<i", f.read(4))[0]
    infos = {"fichier": chemin, "octets": len(d), "longueur_annoncee": annonce,
             "version_format": struct.unpack("<i", f.read(4))[0]}
    infos["monde"] = lit_chaine(f)
    infos["seed"] = lit_chaine(f)
    infos["seed_entiere"] = struct.unpack("<i", f.read(4))[0]
    infos["uid"] = struct.unpack("<q", f.read(8))[0]
    infos["version_generateur"] = struct.unpack("<i", f.read(4))[0]
    # Deux champs de queue, oublies au premier essai : le serveur avait alors
    # refuse le fichier (« data error LoadError ») et regenere un monde au
    # hasard. La lecture semblait pourtant reussir, les champs precedents
    # tombant juste -- d'ou l'interet de verifier qu'il ne reste aucun octet.
    infos["besoin_db"] = bool(f.read(1)[0])
    n = struct.unpack("<i", f.read(4))[0]
    infos["cles_globales_initiales"] = [lit_chaine(f) for _ in range(n)]
    infos["seed_coherente"] = hash_stable(infos["seed"]) == infos["seed_entiere"]
    infos["octets_restants"] = len(d) - f.tell()
    return infos


def creer(chemin, monde, seed, version_format, version_generateur):
    corps = io.BytesIO()
    corps.write(struct.pack("<i", version_format))
    ecrit_chaine(corps, monde)
    ecrit_chaine(corps, seed)
    corps.write(struct.pack("<i", hash_stable(seed)))
    corps.write(struct.pack("<q", random.getrandbits(63)))
    corps.write(struct.pack("<i", version_generateur))
    # besoin_db a 0 et aucune cle globale initiale : c'est exactement ce que le
    # serveur ecrit lui-meme pour un monde neuf, constate en comparant avec un
    # .fwl qu'il venait de generer. Le champ passe a 1 quand le .db existe.
    corps.write(b"\x00")
    corps.write(struct.pack("<i", 0))
    charge = corps.getvalue()
    with open(chemin, "wb") as f:
        f.write(struct.pack("<i", len(charge)))
        f.write(charge)
    return len(charge) + 4


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = ap.add_subparsers(dest="action", required=True)

    a = sous.add_parser("lire", help="affiche la seed et les versions d'un .fwl")
    a.add_argument("fichier")
    a.add_argument("--json", action="store_true", help="sortie exploitable par un script")

    b = sous.add_parser("creer", help="ecrit un .fwl neuf pour une seed choisie")
    b.add_argument("fichier")
    b.add_argument("--monde", required=True, help="nom du monde, casse comprise")
    b.add_argument("--seed", required=True, help="nom de la seed, ex. HHcLC5acQt")
    b.add_argument("--version-format", type=int, default=VERSION_FORMAT)
    b.add_argument("--version-generateur", type=int, default=VERSION_GENERATEUR)
    b.add_argument("--ecraser", action="store_true")

    c = sous.add_parser("hash", help="seed entiere correspondant a un nom de seed")
    c.add_argument("seed")

    o = ap.parse_args()

    if o.action == "lire":
        infos = lire(o.fichier)
        if o.json:
            print(json.dumps(infos, ensure_ascii=False))
        else:
            for cle, val in infos.items():
                print("%-20s %s" % (cle, val))
        return

    if o.action == "hash":
        print(hash_stable(o.seed))
        return

    if os.path.exists(o.fichier) and not o.ecraser:
        sys.exit("%s existe deja ; --ecraser pour le remplacer" % o.fichier)
    n = creer(o.fichier, o.monde, o.seed, o.version_format, o.version_generateur)
    print("%s ecrit, %d octets : monde « %s », seed « %s » (%d)" % (
        o.fichier, n, o.monde, o.seed, hash_stable(o.seed)))
    print("Le .db sera genere par le serveur au premier demarrage.")


if __name__ == "__main__":
    main()
