#!/usr/bin/env python3
"""Lit un fichier de monde Valheim et en sort ce que le journal ne dit pas.

Le journal du serveur donne les connexions, les morts, les raids, les zones.
Il ne dit rien de ce qui *existe* dans le monde : le contenu des coffres, et
surtout **qui a fabrique quoi**. Cette information est dans le fichier de
monde, et elle permet de confronter les roles declares du groupe aux faits.

Format, etabli le 2026-09-09 sur Midgard (version 37) par lecture directe des
octets, faute de specification publique. Rien ici n'est devine : chaque champ a
ete verifie contre une valeur connue par ailleurs.

  En-tete du fichier
    int32   version du format          37 sur Midgard
    double  temps total du monde       565305.56 sur l'archive de 14h00. C'est
                                       la meme grandeur que la ligne « Time »
                                       du journal, et l'entree de l'algorithme
                                       de meteo : 666 secondes par periode.
                                       Non verifie a la seconde contre le
                                       journal, faute d'une ligne « Time » assez
                                       proche -- le serveur n'en ecrit que
                                       quelques-unes par jour. Les deux champs
                                       suivants, eux, sont verifies exactement.
    int64   identifiant de session     444589436, identique au « my sessionID »
                                       du journal
    uint32  prochain identifiant
    int32   nombre de ZDOs             447562, identique a « Loading 447562 zdos »

  Les inventaires de coffres sont stockes en base64 dans des champs texte de
  ZDO. On les retrouve par leur signature : un inventaire commence par sa
  version en int32, donc « agAA » en base64 pour la version 106. Chercher les
  noms d'objets en clair ne donne rien, et chercher n'importe quelle suite de
  caracteres base64 donne un decodage **desaligne** -- qui produit du texte
  plausible et des chiffres faux. C'est le piege principal de ce fichier.

  Un objet d'inventaire, version 106
    chaine  nom du prefab
    int32   taille de la pile
    float   durabilite
    int32   position dans la grille x
    int32   position dans la grille y
    octet   equipe
    int32   qualite
    int32   variante
    int64   identifiant de l'artisan
    chaine  nom de l'artisan           <- le « Fabrique par X » de l'infobulle
    int32   nombre de paires de donnees libres, puis autant de couples de
            chaines
    int32   niveau de monde            <- ces deux champs existent DEJA en 106,
    octet   ramasse                       contrairement a ce qu'on lit ailleurs.
                                          Sans eux, un inventaire sur deux
                                          derive et l'artisan tombe a vide.

  Les chaines sont a prefixe de longueur sur 7 bits, comme .NET.

Attention aux pseudos : « Bab-y » est enregistre avec une espace finale. Une
comparaison exacte sans nettoyage la fait disparaitre des resultats -- c'est
arrive le 2026-09-09 et ca a fait conclure a tort qu'elle ne fabriquait rien.

Usage :
    lecteur-monde-valheim.py <monde.db>            # resume lisible
    lecteur-monde-valheim.py <monde.db> --json     # pour les autres programmes

Le fichier de monde n'a pas besoin d'etre celui en service : une copie
extraite d'une archive convient, et c'est meme preferable -- lire le fichier
vivant pendant que le jeu ecrit dedans n'a aucun interet.
"""

import argparse
import base64
import collections
import json
import re
import struct
import sys
import zlib

SIGNATURES = {base64.b64encode(bytes([v, 0, 0]))[:4]: v for v in range(99, 112)}
B64 = set(b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/')

PLATS = re.compile(r'Stew|Soup|Jerky|^Mead|^Bread|^Sausages|^FishWraps|Omelette'
                   r'|Pudding|Jam|Smoothie|Eyescream|^Feast|^Cooked|^Pie')


class Paquet:
    """Lecteur de ZPackage : entiers little-endian, chaines a prefixe 7 bits."""

    def __init__(self, b):
        self.b, self.o = b, 0

    def i32(self):
        v = struct.unpack_from('<i', self.b, self.o)[0]; self.o += 4; return v

    def i64(self):
        v = struct.unpack_from('<q', self.b, self.o)[0]; self.o += 8; return v

    def f32(self):
        v = struct.unpack_from('<f', self.b, self.o)[0]; self.o += 4; return v

    def octet(self):
        v = self.b[self.o]; self.o += 1; return v

    def chaine(self):
        n, dec = 0, 0
        while True:
            c = self.b[self.o]; self.o += 1
            n |= (c & 0x7f) << dec
            if not c & 0x80:
                break
            dec += 7
        v = self.b[self.o:self.o + n]; self.o += n
        return v.decode('utf8')


def entete(d):
    version, = struct.unpack_from('<i', d, 0)
    temps, = struct.unpack_from('<d', d, 4)
    session, = struct.unpack_from('<q', d, 12)
    suivant, = struct.unpack_from('<I', d, 20)
    zdos, = struct.unpack_from('<i', d, 24)
    return {"version_format": version, "temps_total": round(temps, 2),
            "session": session, "prochain_identifiant": suivant, "zdos": zdos}


def charge(chemin):
    """Les octets du monde, decompresses si le format l'exige.

    Deux formats coexistent depuis le 2026-09-09 :

      avant la 1.0   « Midgard.db », un seul fichier, en clair
      depuis         « Midgard/_main.1.db2 », un flux gzip precede d'un
                     en-tete de seize octets -- version en int32, temps du
                     monde en double, longueur du flux en int32 -- et suivi de
                     quarante octets de pied.

    Renvoie aussi l'en-tete quand il est lisible : celui du format 1.0 ne
    contient que trois champs, alors que l'ancien en portait cinq.
    """
    d = open(chemin, 'rb').read()
    if not chemin.endswith('.db2'):
        return d, entete(d)
    version, = struct.unpack_from('<i', d, 0)
    temps, = struct.unpack_from('<d', d, 4)
    taille, = struct.unpack_from('<i', d, 12)
    brut = zlib.decompressobj(31).decompress(d[16:16 + taille])
    return brut, {"version_format": version, "temps_total": round(temps, 2),
                  "flux_compresse": taille, "decompresse": len(brut)}


def lit_inventaire(b):
    p = Paquet(b)
    version = p.i32()
    nb = p.i32()
    objets = []
    for _ in range(nb):
        nom = p.chaine()
        pile = p.i32()
        p.f32()                       # durabilite
        p.i32(); p.i32(); p.octet()   # grille x, y, equipe
        qualite = p.i32()
        p.i32()                       # variante
        cid = p.i64()
        cnom = p.chaine().strip()     # « Bab-y » porte une espace finale
        if version >= 106:
            for _ in range(p.i32()):
                p.chaine(); p.chaine()
            p.i32()                   # niveau de monde
            p.octet()                 # ramasse
        objets.append({"objet": nom, "pile": pile, "qualite": qualite,
                       "artisan": cnom or None, "artisan_id": cid or None})
    return version, objets, p.o


def inventaires(d):
    """Tous les inventaires du fichier, plus le compte des rejets.

    Un blob n'est retenu que si sa lecture consomme exactement ses octets, a
    deux pres -- le remplissage base64 peut en ajouter jusqu'a deux. Sans ce
    controle, un blob mal aligne passe pour valide et pollue tout le reste.
    """
    trouves, rejets = [], 0
    for m in re.finditer(b'|'.join(re.escape(s) for s in SIGNATURES), d):
        fin = m.start()
        while fin < len(d) and d[fin] in B64:
            fin += 1
        brut = d[m.start():fin]
        b = None
        for pad in range(4):
            try:
                b = base64.b64decode(brut + b'=' * pad)
                break
            except Exception:
                pass
        if not b or len(b) < 8:
            rejets += 1
            continue
        try:
            version, objets, consomme = lit_inventaire(b)
        except Exception:
            rejets += 1
            continue
        if consomme <= len(b) <= consomme + 2:
            trouves.append((version, objets))
        else:
            rejets += 1
    return trouves, rejets


def resume(chemin):
    d, tete = charge(chemin)
    invs, rejets = inventaires(d)
    stock = collections.Counter()
    par_artisan = collections.Counter()
    plats = collections.Counter()
    fleches = collections.Counter()
    detail = collections.Counter()
    noms = {}
    for _version, objets in invs:
        for o in objets:
            stock[o["objet"]] += o["pile"]
            a = o["artisan"]
            if not a:
                continue
            par_artisan[a] += 1
            detail[(o["objet"], a)] += 1
            if o["artisan_id"]:
                noms[o["artisan_id"]] = a
            if PLATS.search(o["objet"]):
                plats[a] += 1
            if o["objet"].startswith("Arrow"):
                fleches[a] += 1
    return {"entete": tete,
            "inventaires_lus": len(invs), "blobs_rejetes": rejets,
            "stock": dict(stock.most_common()),
            "fabrique_par": dict(par_artisan.most_common()),
            "plats_par": dict(plats.most_common()),
            "fleches_par": dict(fleches.most_common()),
            "detail": {"%s|%s" % k: v for k, v in detail.most_common()},
            "identifiants": {str(k): v for k, v in noms.items()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument("monde", help="chemin d'un fichier .db de monde Valheim")
    ap.add_argument("--json", action="store_true")
    o = ap.parse_args()
    try:
        r = resume(o.monde)
    except (OSError, struct.error) as e:
        sys.exit("lecture impossible : %s" % e)
    if o.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    e = r["entete"]
    # L'en-tete de la 1.0 ne porte plus le nombre de ZDOs ni l'identifiant de
    # session : on n'affiche que ce qui est present.
    bouts = ["format %d" % e["version_format"]]
    if e.get("zdos") is not None:
        bouts.append("%d ZDOs" % e["zdos"])
    if e.get("decompresse") is not None:
        bouts.append("%d ko decompresses" % (e["decompresse"] // 1024))
    bouts.append("temps total %.0f s" % e["temps_total"])
    bouts.append("%d inventaires lus (%d blobs ecartes)"
                 % (r["inventaires_lus"], r["blobs_rejetes"]))
    print(" · ".join(bouts))
    for titre, cle in (("Objets fabriqués et encore stockés", "fabrique_par"),
                       ("Plats", "plats_par"), ("Flèches", "fleches_par")):
        if r[cle]:
            print("\n%s" % titre)
            for qui, n in r[cle].items():
                print("   %-16s %3d" % (qui, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
