#!/usr/bin/env python3
"""Qui a fabrique quoi : compte les objets qui portent le nom de leur artisan.

Valheim inscrit le nom du joueur sur chaque objet qu'il fabrique. Ces noms
vivent dans le monde, et ce programme les compte.

LE FORMAT, TROUVE LE 2026-09-10, parce qu'il n'etait documente nulle part et
que ce qu'on croyait etait faux. Depuis la 1.0 un monde n'est plus deux
fichiers mais un DOSSIER :

    _main.<N>.fwl2      metadonnees : seed, cles globales initiales
    _main.<N>.db2       etat du monde, un flux gzip, format 41
    _main.<N>.chunks    l'index : int16 41, puis le nombre de chunks, puis
                        une entree par region
    <x>_<y>__<a>_<b>.chunk   les ZDO, une par region

Les chunks ne sont **pas** compresses : on y voit des flottants repetes a
l'identique, ce qu'une compression aurait mange. Les flux gzip qu'ils
contiennent -- 31 sur ce monde -- sont des modifications de TERRAIN, des
deltas de heightmap de 15 a 22 ko dominés par des zeros, et non des
inventaires. C'est la premiere fausse piste.

La seconde, plus couteuse : les chaines sont prefixees par leur longueur, donc
un « grep » ne les trouve pas de facon fiable et j'ai d'abord conclu que les
noms d'artisan avaient disparu de la 1.0. Ils sont bien la. On les cherche donc
par leur forme exacte -- l'octet de longueur suivi du nom en UTF-8 -- ce qui est
a la fois exact et rapide, sans avoir a decoder la structure d'un enregistrement.

LA DISPOSITION D'UN OBJET, lue dans ItemDrop/ItemData::Save le 2026-09-10 --
monodis sur assembly_valheim.dll, avec MONO_PATH pointant sur le dossier
Managed, sinon monodis meurt sur netstandard 2.1 :

    int32  durabilite x 100
    uint8  case x    uint8  case y    uint8  niveau de monde
    uint8  MASQUE    0x01 ramasse  0x02 equipe  0x04 qualite != 1
                     0x08 pile != 1 0x10 variante 0x20 artisan
                     0x40 prefab    0x80 donnees libres
    si 0x04  uint16 qualite      si 0x08  uint16 pile
    si 0x10  int32  variante
    si 0x20  int64  crafterID  PUIS  string crafterName
    si 0x40  int32  hash(nom du prefab)
    si 0x80  compte puis paires (cle, valeur)
    uint8   masque 2   0x01 triche

Elle est VARIABLE, pilotee par le masque : c'est ce qui rendait toute lecture a
champs fixes impossible. Et j'avais d'abord annonce le masque en tete sur
quatre octets -- un grep trop filtrant m'avait fait perdre des lignes d'IL. Le
masque est cinquieme, sur un octet, et la durabilite passe devant.

L'inventaire, lui, s'ouvre sur un int32 de version -- 109 en 1.0 -- puis le
nombre d'objets sur un uint16. On part de la et on avance : la lecture se
VALIDE d'elle-meme, puisqu'une disposition fausse ne retombe pas sur une
frontiere coherente apres N objets. Un ancrage sur le nom d'artisan, essaye
d'abord, acceptait au contraire n'importe quel alignement dont le masque
concordait -- il rendait des piles de 24 832 et des qualites de 33 566.

Les objets ne portent plus leur nom mais le HASH de leur nom. La table
hash -> nom est fabriquee par noms-prefabs-valheim.py, a cote. Sans elle le
programme affiche les hashes bruts et reste utilisable.

Il ne voit pas non plus les objets qui sont dans l'inventaire PERSONNEL d'un
joueur : les fichiers de personnage vivent chez le joueur, pas sur le serveur.
Ce qu'il compte, ce sont les objets poses dans le monde -- coffres, supports
d'armes, etabli, ce qui traine par terre.

Consequence a ne pas se cacher : ce nombre BAISSE. Ce n'est pas un compteur de
ce qu'un joueur a fabrique dans sa vie, c'est un inventaire de ce qui existe
encore dans le monde a son nom. Un objet qui passe dans un sac, qui casse ou
qui se mange en sort. Mesure du 2026-09-10 entre deux sauvegardes distantes
d'une heure : Bëwulf de 8 a 10 objets, « Djoos Io » de 11 a 9. Les deux
mouvements sont vrais, et aucun des deux ne dit qui a forge le plus depuis le
debut -- seulement qui a laisse le plus derriere lui.

Il lit le MONDE VIVANT quand il y a droit, et retombe sinon sur la derniere
archive de sauvegarde, lisible par tous. Depuis le 2026-09-10, lapserv est
dans le groupe valheim en lecture seule, donc la page Cockpit -- qui tourne
sous le compte de l'humain -- voit l'etat du moment et non celui d'il y a une
heure. Le repli garde le programme utilisable sans ce droit : sur une machine
neuve, ou pour qui n'est pas dans le groupe, il repond quand meme.

La difference n'est pas cosmetique : le compte des objets BOUGE. Entre deux
sauvegardes distantes d'une heure, le 2026-09-10, Bëwulf est passe de 8 a 10
objets et « Djoos Io » de 11 a 9. Lire une archive, c'est afficher un etat que
personne ne reconnait plus.

« --monde » force un dossier precis, « --archive » une archive precise.
"""

import argparse
import collections
import glob
import gzip
import json
import os
import sqlite3
import struct
import sys
import tarfile
import tempfile

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAUVEGARDES = ("/srv/jeux/sauvegardes", "/srv/ia/sauvegardes-valheim",
               "/var/backups/valheim")
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"
TABLE_PREFABS = "/var/tmp/valheim-prefabs.json.gz"


def personnages(cx, monde=None):
    """Tous les personnages connus, rapportes a leur compte.

    La source est la table « pseudos », alimentee par le collecteur : elle
    garde tous les noms qu'un compte a portes, et non le seul dernier. Sans
    elle il faudrait ecrire les noms en dur, et ils changent -- quatre des cinq
    joueurs ont refait leur personnage en deux jours.
    """
    try:
        lignes = cx.execute("SELECT steamid, pseudo FROM pseudos").fetchall()
    except sqlite3.OperationalError:
        lignes = cx.execute("SELECT steamid, pseudo FROM joueurs").fetchall()
    courant = dict(cx.execute("SELECT steamid, pseudo FROM joueurs"))

    # Et tous les noms que le journal a vus, rattaches ou non. La difference
    # n'est pas theorique : le collecteur refuse de deviner quand deux joueurs
    # entrent ensemble, et « DjoosI O » est reste orphelin le 2026-09-10. Il
    # avait pourtant fabrique quatre objets, qu'un compte fonde sur la seule
    # table « pseudos » aurait passes sous silence.
    orphelins = [j for (j,) in cx.execute(
        "SELECT DISTINCT joueur FROM evenements WHERE joueur IS NOT NULL")
        if j not in {p for _s, p in lignes}]
    return lignes, courant, orphelins


def monde_le_plus_recent(cx):
    r = cx.execute("SELECT monde FROM mondes ORDER BY derniere_vue DESC LIMIT 1").fetchone()
    return r[0] if r else None


def lisible(dossier):
    """Le dossier existe et on peut vraiment y lire un chunk.

    os.access ne suffit pas : il repond sur les droits declares, pas sur ce
    qu'un open() obtiendra. On essaie donc pour de vrai.
    """
    try:
        fs = glob.glob(os.path.join(dossier, "*.chunk"))
        if not fs:
            return False
        with open(fs[0], "rb") as f:
            f.read(1)
        return True
    except OSError:
        return False


def derniere_archive():
    """La sauvegarde la plus recente, sur le premier disque qui en a une."""
    candidates = []
    for d in SAUVEGARDES:
        candidates += glob.glob(os.path.join(d, "valheim-*.tar.gz"))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def chunks_depuis_archive(archive, monde, dossier):
    """Extrait les seuls chunks du monde voulu. Rien d'autre : une archive
    pese plus de cent mega, et le reste ne nous sert pas."""
    prefixe = "./worlds_local/%s/" % monde
    tires = []
    with tarfile.open(archive, "r:gz") as t:
        for m in t:
            if m.name.startswith(prefixe) and m.name.endswith(".chunk"):
                m.name = os.path.basename(m.name)
                t.extract(m, dossier, filter="data")
                tires.append(os.path.join(dossier, m.name))
    return tires


VERSION_INVENTAIRE = 109
RAMASSE, EQUIPE, QUALITE, PILE, VARIANTE, ARTISAN, PREFAB, LIBRE = (
    1, 2, 4, 8, 16, 32, 64, 128)


def table_prefabs(chemin=TABLE_PREFABS):
    """hash -> nom, fabriquee par noms-prefabs-valheim.py. Absente : on rend
    un dictionnaire vide et les hashes s'affichent bruts."""
    try:
        with gzip.open(chemin, "rt", encoding="utf-8") as f:
            brut = json.load(f)
    except (OSError, ValueError):
        return {}
    # Un hash ambigu -- il y en a 27 dans le jeu -- s'affiche avec ses deux
    # noms plutot qu'avec l'un des deux, choisi au hasard.
    return {int(k): (v[0] if len(v) == 1 else " ou ".join(v))
            if isinstance(v, list) else v for k, v in brut.items()}


def lis_chaine(d, p):
    """Chaine ZPackage : longueur en 7 bits, puis UTF-8. Ce n'est PAS le format
    des bundles, ou la longueur est un int32 -- les confondre coute une
    journee."""
    n, dec = 0, 0
    while True:
        if p >= len(d):
            return None, p
        o = d[p]; p += 1
        n |= (o & 0x7F) << dec
        if not o & 0x80:
            break
        dec += 7
        if dec > 21:
            return None, p
    if n > 200 or p + n > len(d):
        return None, p
    try:
        return d[p:p + n].decode("utf-8"), p + n
    except UnicodeDecodeError:
        return None, p + n


def lis_objet(d, p):
    if p + 8 > len(d):
        return None, p
    durabilite, = struct.unpack_from("<i", d, p)
    x, y, niveau, masque = struct.unpack_from("<4B", d, p + 4)
    p += 8
    if not 0 <= durabilite <= 10000000:
        return None, p
    o = {"case": (x, y), "niveau_monde": niveau, "masque": masque,
         "durabilite": durabilite / 100.0, "qualite": 1, "pile": 1,
         "variante": 0, "artisan": None, "crafterID": 0, "prefab": None,
         "equipe": bool(masque & EQUIPE), "libre": {}}
    if masque & QUALITE:
        o["qualite"], = struct.unpack_from("<H", d, p); p += 2
    if masque & PILE:
        o["pile"], = struct.unpack_from("<H", d, p); p += 2
    if masque & VARIANTE:
        o["variante"], = struct.unpack_from("<i", d, p); p += 4
    if masque & ARTISAN:
        o["crafterID"], = struct.unpack_from("<q", d, p); p += 8
        nom, p = lis_chaine(d, p)
        if nom is None:
            return None, p
        o["artisan"] = nom
    if masque & PREFAB:
        if p + 4 > len(d):
            return None, p
        o["prefab"], = struct.unpack_from("<i", d, p); p += 4
    if masque & LIBRE:
        n, dec = 0, 0
        while True:
            if p >= len(d):
                return None, p
            b = d[p]; p += 1
            n |= (b & 0x7F) << dec
            if not b & 0x80:
                break
            dec += 7
        if n > 32:
            return None, p
        for _ in range(n):
            cle, p = lis_chaine(d, p)
            val, p = lis_chaine(d, p)
            if cle is None or val is None:
                return None, p
            o["libre"][cle] = val
    if p >= len(d):
        return None, p
    masque2 = d[p]; p += 1
    if masque2 & ~0x01:
        return None, p
    if not (1 <= o["qualite"] <= 10 and 1 <= o["pile"] <= 999):
        return None, p
    return o, p


def objets_du_chunk(d):
    """Tous les objets des inventaires d'un chunk."""
    trouves = []
    aiguille = struct.pack("<i", VERSION_INVENTAIRE)
    i = -1
    while True:
        i = d.find(aiguille, i + 1)
        if i < 0:
            return trouves
        p = i + 4
        if p + 2 > len(d):
            continue
        nb, = struct.unpack_from("<H", d, p)
        p += 2
        if not 1 <= nb <= 64:
            continue
        lot = []
        for _ in range(nb):
            o, p = lis_objet(d, p)
            if o is None:
                lot = None
                break
            lot.append(o)
        if lot:
            trouves += lot


def compte(fichiers, noms, steamids):
    """Les objets fabriques, leur artisan et leur nom."""
    fabriques = []
    total_objets = 0
    par_region = collections.Counter()
    for f in sorted(fichiers):
        d = open(f, "rb").read()
        objets = objets_du_chunk(d)
        total_objets += len(objets)
        for o in objets:
            if o["artisan"]:
                o["region"] = os.path.basename(f)
                fabriques.append(o)
                par_region[o["region"]] += 1
    return fabriques, total_objets, par_region


def rapport(monde, source, fabriques, total_objets, par_region, lignes,
            courant, prefabs):
    """Par COMPTE Steam, avec le detail des objets.

    Un joueur qui a refait son personnage a fabrique sous deux noms :
    additionner sous son compte est la seule lecture qui reponde a « qui a
    forge ». Le detail par personnage reste a cote, parce que c'est lui qui dit
    quand.
    """
    compte_de = {pseudo: sid for sid, pseudo in lignes}
    pseudos_de = collections.defaultdict(list)
    for sid, pseudo in lignes:
        pseudos_de[sid].append(pseudo)

    def decrit(o):
        return {"objet": prefabs.get(o["prefab"], "hash %s" % o["prefab"]),
                "prefab": o["prefab"], "qualite": o["qualite"],
                "pile": o["pile"], "durabilite": round(o["durabilite"], 1),
                "equipe": o["equipe"], "artisan": o["artisan"],
                "region": o.get("region")}

    par_cle = collections.defaultdict(list)
    for o in fabriques:
        sid = compte_de.get(o["artisan"])
        par_cle[sid if sid else "?" + o["artisan"]].append(o)

    artisans, sans = [], []
    for cle, lot in sorted(par_cle.items(), key=lambda e: -len(e[1])):
        objets = sorted((decrit(o) for o in lot), key=lambda e: e["objet"])
        if isinstance(cle, str) and cle.startswith("?"):
            sans.append({"pseudo": cle[1:], "objets": len(lot),
                         "detail": objets})
            continue
        parpseudo = collections.Counter(o["artisan"] for o in lot)
        artisans.append({
            "compte": courant.get(cle, cle), "steamid": cle,
            "objets": len(lot), "detail": objets,
            "personnages": [{"pseudo": p, "objets": n}
                            for p, n in parpseudo.most_common()]})

    return {"monde": monde, "source": source, "total": len(fabriques),
            "objets_lus": total_objets, "noms_connus": bool(prefabs),
            "artisans": artisans, "sans_compte": sans,
            "regions": [{"region": r, "objets": n}
                        for r, n in par_region.most_common()]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--monde", default=None,
                    help="dossier d'un monde, au lieu du monde vivant")
    ap.add_argument("--archive", default=None, help="une archive precise")
    ap.add_argument("--nom-monde", default=None)
    ap.add_argument("--noms", default=TABLE_PREFABS,
                    help="table hash -> nom (noms-prefabs-valheim.py)")
    ap.add_argument("--json", action="store_true")
    o = ap.parse_args()

    cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
    lignes, courant, _orphelins = personnages(cx)
    monde = o.nom_monde or monde_le_plus_recent(cx)

    temporaire = None
    vivant = os.path.join(SAVEDIR, monde) if monde else None
    if not o.monde and not o.archive and vivant and lisible(vivant):
        o.monde = vivant
    if o.monde:
        fichiers = glob.glob(os.path.join(o.monde, "*.chunk"))
        source = o.monde
        monde = os.path.basename(os.path.normpath(o.monde))
    else:
        archive = o.archive or derniere_archive()
        if not archive:
            print("aucune archive de sauvegarde lisible", file=sys.stderr)
            return 1
        if not monde:
            print("monde inconnu : preciser --nom-monde", file=sys.stderr)
            return 1
        temporaire = tempfile.mkdtemp(prefix="artisan-valheim-")
        fichiers = chunks_depuis_archive(archive, monde, temporaire)
        source = archive

    if not fichiers:
        print("aucun chunk pour le monde « %s »" % monde, file=sys.stderr)
        return 1

    fabriques, total, par_region = compte(fichiers, None, None)
    r = rapport(monde, source, fabriques, total, par_region, lignes, courant,
                table_prefabs(o.noms))

    if temporaire:
        for f in fichiers:
            os.unlink(f)
        os.rmdir(temporaire)

    if o.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0

    print("ARTISANS du monde « %s »" % r["monde"])
    print("d'apres %s" % os.path.basename(r["source"]))
    print("%d objets lus dans les inventaires du monde, %d fabriques"
          % (r["objets_lus"], r["total"]))
    if not r["noms_connus"]:
        print("table des noms absente : lancer noms-prefabs-valheim.py")
    print()
    for a in r["artisans"] + r["sans_compte"]:
        qui = a.get("compte") or a["pseudo"]
        persos = ", ".join("%s (%d)" % (p["pseudo"], p["objets"])
                           for p in a.get("personnages", []))
        print("%s -- %d objet(s)%s" % (qui, a["objets"],
                                       "   " + persos if persos else
                                       "   (nom non rattache a un compte)"))
        for e in a["detail"]:
            det = []
            if e["qualite"] > 1:
                det.append("qualite %d" % e["qualite"])
            if e["pile"] > 1:
                det.append("x%d" % e["pile"])
            if e["equipe"]:
                det.append("equipe")
            print("   %-26s %s" % (e["objet"], ", ".join(det)))
        print()
    print("Ne sont comptes que les objets POSES DANS LE MONDE -- coffres,")
    print("supports, etabli, ce qui traine. Les inventaires personnels vivent")
    print("dans le fichier de personnage, chez le joueur, hors de portee.")
    print("Ce nombre BAISSE quand un objet passe dans un sac ou se consomme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
