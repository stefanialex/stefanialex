#!/usr/bin/env python3
"""Suivi declaratif des fonctions et des chantiers du groupe.

La feuille de Baby liste des roles et des constructions. Rien de tout cela
n'est visible depuis le serveur : il ne voit ni la cuisine, ni le
bucheronnage, ni un port acheve. Ces objectifs sont donc tenus a la main, et
affiches a cote des KPI mesures -- en distinguant clairement les deux, pour
qu'on ne prenne pas un declaratif pour une mesure.
"""

import argparse
import difflib
import json
import os
import sys
import tempfile
import unicodedata

FICHIER = "/etc/valheim/chantiers.json"
ETATS = ("a_faire", "en_cours", "fait")
SYMBOLE = {"a_faire": "·", "en_cours": "~", "fait": "x"}


def charge():
    with open(FICHIER, encoding="utf-8") as f:
        return json.load(f)


def sauve(d):
    # Ecriture par fichier temporaire puis renommage : une interruption ne doit
    # pas laisser un fichier de configuration tronque, que plus rien ne lirait.
    rep = os.path.dirname(FICHIER)
    fd, tmp = tempfile.mkstemp(dir=rep, prefix=".chantiers-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, FICHIER)
    except BaseException:
        os.unlink(tmp)
        raise


def sans_accent(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")


def trouve(liste, motif):
    """Retrouve une entree par fragment de nom, en refusant l'ambiguite.

    Le rapprochement tolere les accents et l'orthographe : les libelles sont
    ceux de la feuille de Baby, « Armurie » et non « armurerie », et personne
    ne tapera son orthographe a elle. On tente d'abord le fragment exact, puis
    un rapprochement approximatif -- et seulement s'il ne designe qu'une seule
    entree, pour ne jamais cocher le mauvais chantier.
    """
    m = sans_accent(motif)
    # Les alias comptent autant que le nom : Benny dira « caillou », pas
    # « trophée de Golem de pierre ». Une entree se cherche par le mot qu'on
    # emploie pour elle, pas par son libelle officiel.
    def mots(e):
        return [sans_accent(x) for x in [e["nom"]] + e.get("alias", [])]
    coups = [e for e in liste if any(m in x for x in mots(e))]
    if not coups:
        tous = [(x, e) for e in liste for x in mots(e)]
        proches = difflib.get_close_matches(m, [x for x, _ in tous], n=3, cutoff=0.6)
        coups = []
        for x, e in tous:
            if x in proches and e not in coups:
                coups.append(e)
    if not coups:
        sys.exit("aucune entree ne correspond a « %s »" % motif)
    if len(coups) > 1:
        sys.exit("« %s » correspond a %d entrees : %s" % (
            motif, len(coups), ", ".join(e["nom"] for e in coups)))
    return coups[0]


def action_liste(d):
    print("JOUEURS")
    for cle, v in d["joueurs"].items():
        pseudo = v.get("pseudo") or "?"
        marque = "  <- pseudo en jeu a confirmer" if pseudo == "?" else ""
        print("  %-8s pseudo en jeu : %-16s discord : %s%s" % (
            cle, pseudo, v.get("discord", "?"), marque))

    print()
    print("FONCTIONS")
    for f in d["fonctions"]:
        titu = ", ".join(f["titulaires"]) or "personne"
        print("  %-26s %s" % (f["nom"], titu))

    print()
    faits = sum(1 for c in d["chantiers"] if c["etat"] == "fait")
    print("CHANTIERS  %d/%d faits" % (faits, len(d["chantiers"])))
    for c in d["chantiers"]:
        titu = ", ".join(c["titulaires"]) or "-"
        print("  [%s] %-26s %s" % (SYMBOLE[c["etat"]], c["nom"], titu))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = ap.add_subparsers(dest="action", required=True)
    sous.add_parser("liste", help="affiche fonctions et chantiers")

    e = sous.add_parser("etat", help="change l'etat d'un chantier")
    e.add_argument("chantier", help="fragment du nom, ex. « portails »")
    e.add_argument("etat", choices=ETATS)

    q = sous.add_parser("qui", help="affecte quelqu'un a un chantier ou une fonction")
    q.add_argument("nom", help="fragment du nom")
    q.add_argument("joueur", help="Lapin, Beny, Djoose ou Baby")
    q.add_argument("--retirer", action="store_true")

    p = sous.add_parser("pseudo", help="associe un joueur a son pseudo en jeu")
    p.add_argument("joueur")
    p.add_argument("pseudo")

    o = ap.parse_args()
    d = charge()

    if o.action == "liste":
        action_liste(d)
        return

    if o.action == "etat":
        c = trouve(d["chantiers"], o.chantier)
        avant = c["etat"]
        c["etat"] = o.etat
        sauve(d)
        print("%s : %s -> %s" % (c["nom"], avant, o.etat))
        return

    if o.action == "qui":
        cible = trouve(d["chantiers"] + d["fonctions"], o.nom)
        if o.joueur not in d["joueurs"]:
            sys.exit("joueur inconnu : %s (connus : %s)" % (
                o.joueur, ", ".join(d["joueurs"])))
        if o.retirer:
            cible["titulaires"] = [t for t in cible["titulaires"] if t != o.joueur]
        elif o.joueur not in cible["titulaires"]:
            cible["titulaires"].append(o.joueur)
        sauve(d)
        print("%s : %s" % (cible["nom"], ", ".join(cible["titulaires"]) or "personne"))
        return

    if o.action == "pseudo":
        if o.joueur not in d["joueurs"]:
            sys.exit("joueur inconnu : %s" % o.joueur)
        d["joueurs"][o.joueur]["pseudo"] = o.pseudo
        sauve(d)
        print("%s -> %s" % (o.joueur, o.pseudo))


if __name__ == "__main__":
    main()
