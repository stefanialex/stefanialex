#!/usr/bin/env python3
"""Ce qu'il reste a farmer, par style de jeu, mesure sur le monde en place.

POURQUOI CE PROGRAMME EXISTE. Le point du soir disait « prochaine etape » en
piochant dans conseils.json, et fin-session-valheim.py cochait des chantiers.
Aucun des deux ne repondait a la seule question que le groupe pose vraiment :
*il me manque quoi, concretement, pour la suite ?* Le 2026-09-28 a 22h08 le
groupe a tue la Reine ; le compte rendu de 00h01 a annonce « rien de mesurable
n'a change aujourd'hui » et a affiche un stock Brumeuses. Les deux tables --
ETAPES de l'oracle et regles() de la fin de session -- s'arretaient aux
Brumeuses, donc le systeme entier s'est taxi sans rien dire le jour ou le
groupe a franchi la marche.

CE QU'IL FAIT. Il croise trois mesures et une table :

  - les cles globales, qui donnent le palier atteint ;
  - l'inventaire REEL du monde, lu chunk par chunk via artisan-valheim.py ;
  - ce que chaque STYLE DE JEU reclame au palier suivant (preparation.json) ;
  - et il soustrait.

Le resultat est une liste de courses, pas un cours. « Il vous manque 96
Flametal » se lit en une seconde ; « le Flametal se trouve dans les Ashlands »
ne sert a personne qui y est deja alle.

CE QU'IL NE VOIT PAS, ET IL LE DIT. Les sacs des joueurs vivent chez les
joueurs, pas sur le serveur : un objet porte est invisible d'ici. Le 2026-09-10
cette limite a fait annoncer « zero fer » a un groupe qui en avait 1713 eclats.
Toute sortie porte donc la reserve, et les manques sont des MAJORANTS : ce qui
manque vraiment est au plus ce qui est affiche.

Usage :
    preparation-valheim.py                  # tous les styles
    preparation-valheim.py --style melee    # un seul
    preparation-valheim.py --json
    preparation-valheim.py --discord        # message court, pret a poster
"""

import argparse
import collections
import glob
import importlib.util
import json
import os
import sqlite3
import sys

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"
TABLE = "/var/tmp/valheim-prefabs.json.gz"
ICI = os.path.dirname(os.path.abspath(__file__))


def premier_existant(*chemins):
    """Le premier chemin qui existe, sinon le dernier.

    Ce programme doit tourner a DEUX endroits : dans le depot, ou ses voisins
    sont dans des dossiers freres, et installe dans /usr/local/bin, ou tout est
    a plat et les donnees vivent dans /etc/valheim. Ecrire les chemins par
    rapport au fichier marchait dans le depot et cassait une fois installe --
    constate le 2026-09-29, «  No such file: /usr/local/bin/preparation.json ».
    Un test lance depuis le depot ne pouvait pas le voir.
    """
    for c in chemins:
        if os.path.exists(c):
            return c
    return chemins[-1]


# Le voisin qui sait lire un inventaire de coffre. On l'importe par son chemin
# plutot que par son nom : il n'est pas installe comme module, et le copier
# ferait deux lecteurs a maintenir au lieu d'un.
ARTISAN = premier_existant(
    os.path.join(ICI, "..", "valheim-artisan", "artisan-valheim.py"),
    "/usr/local/bin/artisan-valheim.py")
DONNEES = premier_existant(
    "/etc/valheim/preparation.json",
    os.path.join(ICI, "preparation.json"))

# L'ordre des paliers. La cle est celle du monde, pas un nom d'affichage : les
# noms changent de langue, les cles non.
#
# ATTENTION : « defeated_fimbulbringer » est une SUPPOSITION, pas une mesure.
# Les sept premieres viennent du code du projet et sont vues en base ; la
# huitieme, celle de Kall Fimbulbringer, n'a ete trouvee dans aucune source le
# 2026-09-29 et personne ne l'a encore fait apparaitre dans ce monde. Le jour
# ou Kall tombe, cles-monde-valheim.py ecrira « nouvelle cle : X » : c'est ce
# X qu'il faut recopier ici. Tant que la vraie clef n'est pas connue, ce
# programme continuera d'annoncer le Grand Nord comme prochain palier meme
# apres l'avoir fini -- il ne se trompera pas avant, mais il se trompera la.
PALIERS = ["defeated_eikthyr", "defeated_gdking", "defeated_bonemass",
           "defeated_dragon", "defeated_goblinking", "defeated_queen",
           "defeated_fader", "defeated_fimbulbringer"]


def charge_artisan():
    spec = importlib.util.spec_from_file_location("artisan", ARTISAN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def monde_actif(cx):
    r = cx.execute("SELECT monde FROM mondes ORDER BY derniere_vue DESC "
                   "LIMIT 1").fetchone()
    return r[0] if r else None


def dossier_monde(monde):
    d = os.path.join(SAVEDIR, monde)
    return d if glob.glob(os.path.join(d, "*.chunk")) else None


def stocks(dossier, artisan):
    """Tout ce que les coffres et le sol du monde contiennent, par nom."""
    try:
        table = artisan.table_prefabs(TABLE)
    except (OSError, ValueError):
        table = {}
    tot = collections.Counter()
    for f in glob.glob(os.path.join(dossier, "*.chunk")):
        with open(f, "rb") as fh:
            d = fh.read()
        for o in artisan.objets_du_chunk(d):
            h = o.get("prefab")
            n = table.get(h) or table.get(str(h)) or str(h)
            if isinstance(n, (list, set)):
                n = sorted(n)[0]
            tot[n] += o.get("pile", 1)
    return tot


def palier(cx, monde):
    """Le palier atteint et celui qui vient, d'apres les cles globales."""
    vaincus = {c for (c,) in cx.execute(
        "SELECT cle FROM cles_globales WHERE monde IS ?", (monde,))}
    atteint = None
    for c in PALIERS:
        if c in vaincus:
            atteint = c
        else:
            return atteint, c
    return atteint, None


def au_stock(mat, stock):
    """Le stock d'un materiau, alias compris.

    Un meme objet porte parfois deux prefabs : le Flametal des Ashlands est
    « FlametalNew », « Flametal » etant le prefab herite et inutilise. Ecrire
    le mauvais des deux ne leve aucune erreur -- ca annonce simplement qu'il
    manque tout. On note donc « FlametalNew|Flametal » et on additionne.
    """
    return sum(stock.get(a, 0) for a in mat.split("|"))


def manques(besoin, stock):
    """Ce qui manque, en soustrayant le stock du besoin. Jamais negatif."""
    out = {}
    for mat, n in besoin.items():
        reste = n - au_stock(mat, stock)
        if reste > 0:
            out[mat.split("|")[0]] = reste
    return out


def besoin_du_style(style, joueurs):
    """Les materiaux d'un style, multiplies par le nombre de joueurs concernes.

    Les stations ne se multiplient pas -- une forge noire sert tout le monde --
    alors que l'equipement, si. La table distingue donc « par_joueur » de
    « une_fois », faute de quoi on reclamerait quatre forges.
    """
    b = collections.Counter()
    for mat, n in (style.get("une_fois") or {}).items():
        b[mat] += n
    for mat, n in (style.get("par_joueur") or {}).items():
        b[mat] += n * joueurs
    return dict(b)


def rapport(monde, atteint, prochain, data, stock, joueurs, styles_voulus):
    etape = (data.get("paliers") or {}).get(prochain or "", {})
    out = {"monde": monde, "palier_atteint": atteint, "prochain": prochain,
           "biome": etape.get("biome"), "joueurs": joueurs, "styles": [],
           "reserve": "Les sacs des joueurs ne sont pas visibles du serveur : "
                      "les manques ci-dessus sont des majorants."}
    if not etape:
        out["avertissement"] = (
            "Aucune donnee de preparation pour « %s ». Tant que cette entree "
            "manque, ce programme ne peut rien dire -- et c'est exactement le "
            "silence qui a coute la soiree du 2026-09-28." % prochain)
        return out
    out["resume"] = etape.get("resume")
    out["obligatoire"] = etape.get("obligatoire") or []
    for nom, style in (etape.get("styles") or {}).items():
        if styles_voulus and nom not in styles_voulus:
            continue
        besoin = besoin_du_style(style, joueurs)
        out["styles"].append({
            "nom": nom,
            "resume": style.get("resume"),
            "stuff": style.get("stuff") or [],
            "nourriture": style.get("nourriture") or [],
            "hydromels": style.get("hydromels") or [],
            "manque": manques(besoin, stock),
            "en_stock": {m.split("|")[0]: au_stock(m, stock) for m in besoin},
        })
    return out


def bloc(titre, items):
    """Un titre puis une puce par ligne.

    Les trois listes sortaient jointes par des virgules, ce qui faisait un pave
    illisible des que « stuff » comptait cinq entrees -- et un pave sur Discord
    est precisement le reproche qui a lance ce chantier. Une puce par ligne
    coute quelques octets et se lit d'un coup d'oeil.
    """
    if not items:
        return []
    return ["**%s :**" % titre] + ["  • %s" % i for i in items]


def texte(r):
    L = []
    L.append("**Ou vous en etes — %s**" % r["monde"])
    if r.get("avertissement"):
        L.append("_%s_" % r["avertissement"])
        return "\n".join(L)
    L.append("Palier atteint : **%s**. Prochain : **%s** (%s)."
             % (r["palier_atteint"] or "aucun", r["prochain"], r["biome"] or "?"))
    if r.get("resume"):
        L.append(r["resume"])
    if r["obligatoire"]:
        L.append("")
        L += bloc("Non negociable", r["obligatoire"])
    for s in r["styles"]:
        L.append("\n__%s__ — %s" % (s["nom"], s.get("resume") or ""))
        L += bloc("Stuff", s["stuff"])
        L += bloc("Bouffe", s["nourriture"])
        L += bloc("Hydromels", s["hydromels"])
        if s["manque"]:
            L.append("**A farmer :** " + " · ".join(
                "%s %d" % (m, n) for m, n in sorted(
                    s["manque"].items(), key=lambda kv: -kv[1])))
        else:
            L.append("**Rien ne manque en coffre.**")
    L.append("\n_%s_" % r["reserve"])
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--monde")
    ap.add_argument("--style", action="append",
                    help="ne montrer que ce style ; repetable")
    ap.add_argument("--joueurs", type=int,
                    help="taille du groupe (defaut : compte en base)")
    ap.add_argument("--json", action="store_true")
    o = ap.parse_args()

    try:
        cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
        cx.execute("SELECT 1 FROM mondes LIMIT 1")
    except sqlite3.Error as e:
        print("base illisible : %s" % e, file=sys.stderr)
        return 1

    monde = o.monde or monde_actif(cx)
    if not monde:
        print("aucun monde connu", file=sys.stderr)
        return 1
    dossier = dossier_monde(monde)
    if not dossier:
        print("pas de chunks lisibles pour « %s »" % monde, file=sys.stderr)
        return 1

    joueurs = o.joueurs or cx.execute(
        "SELECT count(*) FROM joueurs").fetchone()[0] or 1
    try:
        with open(DONNEES, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print("preparation.json illisible : %s" % e, file=sys.stderr)
        return 1

    atteint, prochain = palier(cx, monde)
    stock = stocks(dossier, charge_artisan())
    r = rapport(monde, atteint, prochain, data, stock, joueurs,
                set(o.style or []))
    print(json.dumps(r, ensure_ascii=False, indent=1) if o.json else texte(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
