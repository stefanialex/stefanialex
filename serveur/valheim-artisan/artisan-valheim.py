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

CE QUE CE PROGRAMME NE SAIT PAS, et il faut le dire : il compte les objets par
artisan, pas QUELS objets. Lier chaque objet a son nom demande de decoder
l'enregistrement d'inventaire, dont l'alignement ne colle a aucune disposition
connue de Inventory.Save. C'est le prochain chantier, et il passera par le
desassemblage de assembly_valheim.dll.

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
import json
import os
import re
import sqlite3
import sys
import tarfile
import tempfile

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAUVEGARDES = ("/srv/jeux/sauvegardes", "/srv/ia/sauvegardes-valheim",
               "/var/backups/valheim")
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"


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


def compte(fichiers, noms, steamids):
    """Compte, dans les chunks, les chaines exactement prefixees.

    On construit l'aiguille plutot que de balayer tous les offsets : l'octet de
    longueur, puis le nom en UTF-8. Une occurrence trouvee ainsi est une vraie
    chaine du fichier, pas une coincidence d'octets -- c'est ce qui distingue
    ce compte d'un « grep », qui melangeait des suites de flottants avec des
    noms.
    """
    par_nom = collections.Counter()
    par_steam = collections.Counter()
    par_region = collections.Counter()
    for f in sorted(fichiers):
        d = open(f, "rb").read()
        for nom in noms:
            b = nom.encode("utf-8")
            if not (2 <= len(b) <= 40):
                continue
            n = d.count(bytes([len(b)]) + b)
            if n:
                par_nom[nom] += n
                par_region[os.path.basename(f)] += n
        for sid in steamids:
            b = ("Steam_%s" % sid).encode()
            n = d.count(bytes([len(b)]) + b)
            if n:
                par_steam[sid] += n
    return par_nom, par_steam, par_region


def rapport(monde, source, par_nom, par_steam, par_region, lignes, courant):
    """Le compte par COMPTE Steam, avec le detail par personnage.

    Un joueur qui a refait son personnage a fabrique sous deux noms : les
    additionner sous son compte est la seule lecture qui ait un sens pour « qui
    a forge ». Le detail par personnage reste a cote, parce que c'est lui qui
    dit quand.
    """
    compte_de = {pseudo: sid for sid, pseudo in lignes}   # pseudo -> compte
    pseudo_de = {}
    for sid, pseudo in lignes:
        pseudo_de.setdefault(sid, [])
        pseudo_de[sid].append(pseudo)

    par_compte = collections.Counter()
    for nom, n in par_nom.items():
        sid = compte_de.get(nom)
        par_compte[sid if sid else "?%s" % nom] += n

    return {
        "monde": monde,
        "source": source,
        "total": sum(par_nom.values()),
        "artisans": [
            {"compte": courant.get(sid, sid), "steamid": sid, "objets": n,
             "personnages": sorted(
                 [{"pseudo": p, "objets": par_nom[p]}
                  for p in pseudo_de.get(sid, []) if par_nom.get(p)],
                 key=lambda e: -e["objets"])}
            for sid, n in par_compte.most_common() if not str(sid).startswith("?")
        ],
        "sans_compte": [{"pseudo": k[1:], "objets": n}
                        for k, n in par_compte.most_common()
                        if str(k).startswith("?")],
        "identifiants_steam": [{"steamid": s, "objets": n}
                               for s, n in par_steam.most_common()],
        "regions": [{"region": r, "objets": n} for r, n in par_region.most_common()],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--monde", default=None,
                    help="dossier d'un monde, au lieu de la derniere sauvegarde")
    ap.add_argument("--archive", default=None, help="une archive precise")
    ap.add_argument("--nom-monde", default=None,
                    help="nom du monde a lire dans l'archive")
    ap.add_argument("--json", action="store_true")
    o = ap.parse_args()

    cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
    lignes, courant, orphelins = personnages(cx)
    noms = sorted({p for _s, p in lignes} | set(orphelins))
    steamids = sorted({s for s, _p in lignes})
    monde = o.nom_monde or monde_le_plus_recent(cx)

    temporaire = None
    vivant = os.path.join(SAVEDIR, monde) if monde else None
    if not o.monde and not o.archive and vivant and lisible(vivant):
        # Le monde vivant d'abord : c'est le seul etat que les joueurs
        # reconnaissent. On verifie qu'il est vraiment lisible plutot que de
        # supposer le droit -- l'appartenance au groupe valheim ne vaut que
        # pour les sessions ouvertes apres l'avoir recue.
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
            print("monde inconnu : préciser --nom-monde", file=sys.stderr)
            return 1
        temporaire = tempfile.mkdtemp(prefix="artisan-valheim-")
        fichiers = chunks_depuis_archive(archive, monde, temporaire)
        source = archive

    if not fichiers:
        print("aucun chunk pour le monde « %s »" % monde, file=sys.stderr)
        return 1

    par_nom, par_steam, par_region = compte(fichiers, noms, steamids)
    r = rapport(monde, source, par_nom, par_steam, par_region, lignes, courant)

    if temporaire:
        for f in fichiers:
            os.unlink(f)
        os.rmdir(temporaire)

    if o.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0

    print("ARTISANS du monde « %s »" % r["monde"])
    print("d'apres %s" % os.path.basename(r["source"]))
    print()
    if not r["total"]:
        print("aucun objet fabrique ne porte de nom dans ce monde")
        return 0
    print("%-16s %8s   %s" % ("compte", "objets", "personnages"))
    for a in r["artisans"]:
        detail = ", ".join("%s (%d)" % (p["pseudo"], p["objets"])
                           for p in a["personnages"])
        print("%-16s %8d   %s" % (a["compte"], a["objets"], detail))
    for a in r["sans_compte"]:
        print("%-16s %8d   (nom non rattache a un compte Steam)"
              % (a["pseudo"], a["objets"]))
    print()
    print("%d objet(s) fabrique(s) reperes dans le monde" % r["total"])
    if r["identifiants_steam"]:
        print()
        print("Nouveaute 1.0 : certains objets portent aussi le compte Steam de")
        print("leur artisan, et non seulement son pseudo.")
        for e in r["identifiants_steam"]:
            print("   %-22s %d objet(s)" % (e["steamid"], e["objets"]))
    print()
    print("Ne sont comptes que les objets POSES DANS LE MONDE -- coffres,")
    print("supports, etabli, ce qui traine. Les inventaires personnels vivent")
    print("dans le fichier de personnage, chez le joueur, hors de portee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
