#!/usr/bin/env python3
"""Fabrique la table hash -> nom de prefab, en lisant les bundles du jeu.

Depuis la 1.0, un objet dans un inventaire n'est plus designe par son nom mais
par le HASH de ce nom -- StringExtensionMethods::GetStableHashCode, lu dans
assembly_utils.dll le 2026-09-10 : deux djb2 entrelaces, l'un sur les
caracteres pairs et l'autre sur les impairs, puis « a + b * 1566083941 ».
Le hash n'est pas inversible : il faut donc la liste des noms.

Ces noms sont dans les bundles d'assets du jeu, en clair, dans des flux
UnityFS compresses en LZ4. Le decompresseur est ici, en Python pur : ni le
module lz4 ni l'outil ne sont installes sur cette machine, et le format de bloc
tient en trente lignes.

DEUX PIEGES, tombes dans cet ordre :

  1. Le bourrage. Les blocs commencent sur un multiple de seize quand le
     drapeau 0x200 est pose (« BlockInfoNeedPaddingAtStart », Unity 2019.4+).
     Sans lui, le premier bloc part de travers et LZ4 s'arrete sur un decalage
     hors limites.

  2. Le format des chaines. Dans un bundle Unity la longueur est un int32 ;
     dans un chunk de monde -- un ZPackage -- elle tient sur un octet en 7 bits.
     J'ai d'abord recolte avec le second format : 157 807 « noms » ramasses,
     et UN SEUL hash resolu sur 91. Avec le bon : 64 254 noms, et 91 sur 91.
     Une recolte abondante qui ne resout rien est le signe qu'on lit du bruit.

La table est ecrite dans /var/tmp plutot que dans le depot : 833 ko compresses,
et elle est a refaire a chaque mise a jour du jeu. Le programme des artisans
s'en passe -- il affiche alors les hashes bruts -- mais il dit tout avec.

Lecture seule, sur un jeu qui tourne : rien n'est touche du cote du serveur.
"""

import argparse
import collections
import glob
import gzip
import json
import os
import re
import struct
import sys

BUNDLES = ("/srv/jeux/valheim/serveur/valheim_server_Data/StreamingAssets/"
           "SoftRef/Bundles")
TABLE = "/var/tmp/valheim-prefabs.json.gz"

# Une chaine Unity : int32 de longueur, puis les octets. On borne la longueur a
# 48 et on exige un debut de nom plausible, sinon tout flottant qui commence par
# un petit entier passerait pour une chaine.
MOTIF = re.compile(rb"[\x02-\x30]\x00\x00\x00[A-Za-z][A-Za-z0-9_]{1,47}")


def hash_stable(s):
    """GetStableHashCode de Valheim, lu dans assembly_utils.dll."""
    a = b = 5381
    i, n = 0, len(s)
    while i < n:
        a = (((a << 5) + a) ^ ord(s[i])) & 0xFFFFFFFF
        if i == n - 1:
            break
        b = (((b << 5) + b) ^ ord(s[i + 1])) & 0xFFFFFFFF
        i += 2
    v = (a + b * 1566083941) & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def lz4(src, taille=0):
    """Bloc LZ4 brut. Un octet de jeton : quartet haut le nombre de litteraux,
    quartet bas la longueur du match moins quatre ; 15 veut dire « lire la
    suite octet par octet »."""
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        jeton = src[i]; i += 1
        lit = jeton >> 4
        if lit == 15:
            while True:
                o = src[i]; i += 1
                lit += o
                if o != 255:
                    break
        out += src[i:i + lit]; i += lit
        if i >= n:
            break
        decalage = src[i] | (src[i + 1] << 8); i += 2
        longueur = (jeton & 15) + 4
        if (jeton & 15) == 15:
            while True:
                o = src[i]; i += 1
                longueur += o
                if o != 255:
                    break
        depart = len(out) - decalage
        if depart < 0:
            raise ValueError("decalage hors limites")
        if decalage >= longueur:
            out += out[depart:depart + longueur]
        else:
            for k in range(longueur):
                out.append(out[depart + k])
    if taille and len(out) != taille:
        raise ValueError("taille attendue %d, obtenue %d" % (taille, len(out)))
    return bytes(out)


def chaine_zero(d, p):
    f = d.index(b"\0", p)
    return d[p:f].decode("utf-8", "replace"), f + 1


def deplie(chemin):
    """Les octets d'un bundle UnityFS, decompresses."""
    d = open(chemin, "rb").read()
    sig, p = chaine_zero(d, 0)
    if sig != "UnityFS":
        raise ValueError("pas un UnityFS")
    version, = struct.unpack_from(">I", d, p); p += 4
    _v, p = chaine_zero(d, p)
    _rev, p = chaine_zero(d, p)
    p += 8                                        # taille totale annoncee
    ci_comp, ci_brut, drapeaux = struct.unpack_from(">III", d, p); p += 12
    if version >= 7:
        p += (-p) % 16
    if drapeaux & 0x80:
        debut = len(d) - ci_comp
    else:
        debut = p
        p += ci_comp
        if drapeaux & 0x200:
            p += (-p) % 16                        # piege numero 1
    brut = d[debut:debut + ci_comp]
    infos = lz4(brut, ci_brut) if drapeaux & 0x3F in (2, 3) else brut

    q = 16
    nb, = struct.unpack_from(">i", infos, q); q += 4
    blocs = []
    for _ in range(nb):
        blocs.append(struct.unpack_from(">IIH", infos, q)); q += 10

    sortie = bytearray()
    for b_brut, b_comp, b_drap in blocs:
        mor = d[p:p + b_comp]; p += b_comp
        m = b_drap & 0x3F
        if m in (2, 3):
            sortie += lz4(mor, b_brut)
        elif m == 0:
            sortie += mor
        elif m == 1:
            import lzma
            sortie += lzma.decompress(mor)
        else:
            raise ValueError("compression de bloc %d inconnue" % m)
    return bytes(sortie)


def recolte(dossier, bavard=False):
    noms = set()
    fichiers = [f for f in sorted(glob.glob(os.path.join(dossier, "*")),
                                  key=os.path.getsize)
                if os.path.isfile(f) and os.path.getsize(f) > 1024]
    for f in fichiers:
        try:
            d = deplie(f)
        except (ValueError, OSError, IndexError, struct.error) as e:
            if bavard:
                print("  %-12s ignore (%s)" % (os.path.basename(f), e),
                      file=sys.stderr)
            continue
        avant = len(noms)
        for m in MOTIF.finditer(d):
            n, = struct.unpack_from("<i", d, m.start())
            s = d[m.start() + 4:m.start() + 4 + n]
            if len(s) == n and all(32 <= c < 127 for c in s):
                noms.add(s.decode())
        if bavard:
            print("  %-12s %6.1f Mo, %d noms neufs"
                  % (os.path.basename(f), len(d) / 1e6, len(noms) - avant),
                  file=sys.stderr)
        del d
    return noms


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundles", default=BUNDLES)
    ap.add_argument("--sortie", default=TABLE)
    ap.add_argument("--bavard", action="store_true")
    o = ap.parse_args()

    if not os.path.isdir(o.bundles):
        print("dossier de bundles introuvable : %s" % o.bundles, file=sys.stderr)
        return 1
    noms = recolte(o.bundles, o.bavard)
    if not noms:
        print("aucun nom recolte : droits sur %s ?" % o.bundles, file=sys.stderr)
        return 1
    # Un hash peut avoir PLUSIEURS noms : sur les 64 281 noms recoltes le
    # 2026-09-10, 27 collisions. On garde la liste plutot que d'en choisir une
    # au hasard -- afficher « AxeFlint » quand c'est peut-etre autre chose est
    # pire que d'afficher les deux.
    table = collections.defaultdict(set)
    for n in noms:
        table[str(hash_stable(n))].add(n)
    table = {h: sorted(v) for h, v in table.items()}
    doubles = sum(1 for v in table.values() if len(v) > 1)
    # Ecriture par renommage : une table tronquee ne doit jamais etre lue.
    tmp = o.sortie + ".partiel"
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(table, f, ensure_ascii=False)
    os.replace(tmp, o.sortie)
    os.chmod(o.sortie, 0o644)
    print("%d noms, %d hashes dont %d ambigus, ecrits dans %s (%.0f ko)"
          % (len(noms), len(table), doubles, o.sortie,
             os.path.getsize(o.sortie) / 1e3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
