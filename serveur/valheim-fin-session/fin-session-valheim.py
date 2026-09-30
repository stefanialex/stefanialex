#!/usr/bin/env python3
"""Fin de session : mesure le monde, coche les chantiers mesurables, et poste
le compte rendu du soir sur Discord.

POURQUOI CE PROGRAMME EXISTE, ET CE QU'IL NE FAIT PAS.

Les douze chantiers de la feuille de Baby ne sont pas mesurables depuis le
serveur -- il ne voit ni la cuisine, ni le bucheronnage, ni un port construit.
Ils restent declaratifs, coches a la main. Les dix ajoutes le 2026-09-20 pour
le palier Yagluth puis les Brumeuses, eux, LE SONT : un Wisplight est un objet
d'inventaire, une Forge noire est un objet pose, un fragment de Sealbreaker se
compte, et Yagluth mort est une cle globale du monde.

D'ou la regle qui tient tout : **un chantier absent de REGLES n'est jamais
touche.** Le programme ne devine pas, il ne « suppose pas fini », il ne remet
pas non plus a faire ce qu'un humain a coche. Il n'ecrit que ce qu'il a mesure.

LES TROIS SOURCES, et pourquoi trois.

  1. Les inventaires du monde, pour les matieres et l'equipement. Lus par
     artisan-valheim.py, importe et non recopie : le format des objets de la
     1.0 a coute assez cher a etablir pour qu'il n'en existe qu'une version.
     ATTENTION -- ils ne contiennent que ce qui est POSE ou EN COFFRE. Ce que
     les joueurs portent dans leur sac vit dans leur fichier de personnage,
     chez eux, et reste invisible. Un chantier peut donc etre fait en vrai et
     affiche « a faire » : c'est une limite assumee, pas un bug. C'est
     exactement le piege dans lequel je suis tombe le 2026-09-20 en comptant
     les hashes de prefabs directement dans les chunks, ce qui ne voit QUE les
     objets poses et m'a fait annoncer « zero fer » a un groupe qui en a 1713.
  2. Les objets poses, pour les stations. Comptes par le hash de leur prefab
     dans les chunks -- la, c'est la bonne methode, une station EST un objet
     pose.
  3. Les cles globales en base, pour les boss.

Usage :
    fin-session-valheim.py            # mesure, ecrit, publie
    fin-session-valheim.py --sec      # mesure et affiche, n'ecrit rien
    fin-session-valheim.py --json
"""

import argparse
import collections
import glob
import importlib.util
import json
import os
import re
import sqlite3
import struct
import sys
import urllib.error
import urllib.request

DONNEES = "/var/lib/valheim/donnees/worlds_local"
ARCHIVES = "/srv/jeux/sauvegardes"
BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
VERT = 0x3D7317
AGENT = "valheim-serveur/1.0 (fin de session auto-hebergee)"


def module(nom, chemin):
    """Importe un programme voisin. Les noms contiennent des tirets, d'ou
    l'import par chemin plutot que par nom de module."""
    spec = importlib.util.spec_from_file_location(nom, chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


AR = module("ar", "/usr/local/bin/artisan-valheim.py")
CH = module("ch", "/usr/local/bin/chantier-valheim.py")
BI = module("bi", "/usr/local/bin/bilan-discord-valheim.py")


def dossier_monde(monde):
    """Le monde en place si on peut le lire, sinon la derniere archive.

    Lire le monde en place evite de dependre du rythme des archives : la
    derniere peut avoir une heure, et une heure de jeu change le resultat.
    """
    vif = os.path.join(DONNEES, monde)
    if os.path.isdir(vif) and os.access(vif, os.R_OK):
        return vif, "monde en place"
    arch = sorted(glob.glob(os.path.join(ARCHIVES, "valheim-*.tar.gz")))
    if not arch:
        return None, None
    import tarfile, tempfile
    tmp = tempfile.mkdtemp(prefix="fin-session-")
    with tarfile.open(arch[-1]) as t:
        prefixe = "./worlds_local/%s/" % monde
        membres = [m for m in t.getmembers() if m.name.startswith(prefixe)]
        if not membres:
            return None, None
        t.extractall(tmp, members=membres)
    return os.path.join(tmp, "worlds_local", monde), os.path.basename(arch[-1])


# La table des noms de prefabs, cherchee dans l'ordre. artisan-valheim.py ne
# connait que /var/tmp, que PrivateTmp=yes masque a un service : sous systemd
# il obtiendrait une table VIDE, tous les stocks tomberaient a zero, et le
# programme cocherait ou decocherait sur du vent sans la moindre erreur. La
# meme panne a deja coute une conclusion fausse le 2026-09-12. D'ou cette liste
# et le refus, plus bas, de rien ecrire sans table.
TABLES = (
    "/usr/local/share/valheim/prefabs.json.gz",
    os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/prefabs.json.gz",
    "/var/tmp/valheim-prefabs.json.gz",
)


def table_noms():
    for chemin in TABLES:
        t = AR.table_prefabs(chemin)
        if t:
            return t, chemin
    return {}, None


def recense(dossier, table):
    """Tout ce que les inventaires du monde contiennent, par nom, en quantite."""
    tot = collections.Counter()
    for f in sorted(glob.glob(os.path.join(dossier, "*.chunk"))):
        for o in AR.objets_du_chunk(open(f, "rb").read()):
            h = o.get("prefab")
            n = table.get(h) or table.get(str(h)) or str(h)
            if isinstance(n, (list, set)):
                n = sorted(n)[0]
            tot[n] += o.get("pile", 1)
    return tot


def poses(dossier, noms):
    """Combien d'objets de ces prefabs sont POSES dans le monde."""
    octets = [open(f, "rb").read()
              for f in glob.glob(os.path.join(dossier, "*.chunk"))]
    res = {}
    for n in noms:
        motif = struct.pack("<i", hash_stable(n))
        res[n] = sum(d.count(motif) for d in octets)
    return res


def hash_stable(s):
    """GetStableHashCode de Valheim. Recopie ici faute d'etre exporte par un
    voisin : artisan-valheim.py le porte en interne sans le publier."""
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


def etiquettes(dossier):
    """Les etiquettes de portail, comptees. Deux portails de meme etiquette
    forment une paire ; une seule moitie ne mene nulle part.

    Elles vivent dans le chunk des objets persistants-distants (« 00_01__0_ »),
    ou tous les portails du monde sont regroupes quelle que soit leur position.
    """
    mot = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _'-]{1,19}$")
    c = collections.Counter()
    for f in glob.glob(os.path.join(dossier, "00_01__0_*.chunk")):
        d = open(f, "rb").read()
        for i in range(len(d) - 1):
            n = d[i]
            if 2 <= n <= 20:
                s = d[i + 1:i + 1 + n]
                if len(s) == n and all(32 <= b < 127 for b in s):
                    t = s.decode("ascii")
                    if mot.match(t) and sum(x.isalpha() for x in t) >= max(2, len(t) - 3):
                        c[t] += 1
    return c


def cles(monde):
    try:
        cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
        return {c for (c,) in cx.execute(
            "SELECT cle FROM cles_globales WHERE monde IS ?", (monde,))}
    except sqlite3.Error:
        return set()


def palier(n, seuils):
    """a_faire / en_cours / fait selon deux seuils. Rend None sous le premier,
    pour ne pas ecraser un chantier qu'un humain aurait coche a la main."""
    debut, fin = seuils
    if n >= fin:
        return "fait"
    if n >= debut:
        return "en_cours"
    return None


# Un chantier par ligne, et la mesure qui le decide. Tout chantier absent de
# cette table est laisse tel quel, pour toujours.
def regles(inv, pose, tags, k, joueurs):
    demister = inv["Demister"]
    padded = min(inv["ArmorPaddedCuirass"], inv["ArmorPaddedGreaves"], inv["HelmetPadded"])
    carapace = min(inv["ArmorCarapaceChest"], inv["ArmorCarapaceLegs"], inv["HelmetCarapace"])
    return {
        "Wisplight pour chacun": palier(demister, (1, joueurs)) or
                                 ("en_cours" if inv["Wisp"] else None),
        "Armure rembourree pour chacun": palier(padded, (1, joueurs)),
        "Tuer Yagluth": "fait" if "defeated_goblinking" in k else None,
        "Black Cores": palier(inv["BlackCore"], (1, 10)),
        "Forge noire": "fait" if pose["blackforge"] else None,
        "Raffinerie d'eitr et extracteurs de seve":
            "fait" if pose["eitrrefinery"] else
            ("en_cours" if pose["piece_sapcollector"] or inv["Sap"] else None),
        "Table galdr": "fait" if pose["piece_magetable"] else None,
        "Armure de carapace": palier(carapace, (1, joueurs)) or
                              ("en_cours" if inv["Carapace"] >= 20 else None),
        "9 fragments de Sealbreaker": palier(inv["DvergrKeyFragment"], (1, 9)),
        "Reposer un portail dans les Brumeuses":
            "fait" if tags["Myst"] >= 2 else None,
        # Le palier Ashlands. Mesure du 2026-09-29 : la presse et le drakkar
        # etaient DEJA faits, et personne ne le savait -- le conseil du soir
        # repetait « avant tout, le drakkar » a un groupe qui en avait un a
        # flot depuis un moment. La Forge noire, elle, plafonne au niveau 3.
        "Presse d'artisan": "fait" if pose["artisan_ext1"] else None,
        "Drakkar": "fait" if pose["VikingShip_Ashlands"] else None,
        "Forge noire niveau 4 (Decoupeuse a metal)":
            "fait" if pose["blackforge_ext3_metalcutter"] else None,
        "Forge noire niveau 5 (Tailleur de gemmes)":
            "fait" if pose["blackforge_ext4_gemcutter"] else
            ("en_cours" if inv["GemstoneRed"] else None),
        "Vin de resistance au feu": palier(inv["BarleyWine"], (1, 40)),
        "9 fragments de cloche": palier(inv["BellFragment"], (1, 9)),
    }


# Ce qu'on montre, et ce qui bloque, AU PALIER EN COURS. Jusqu'au 2026-09-30
# les deux etaient figes sur les Brumeuses : le soir ou le groupe a tue la Reine,
# le compte rendu affichait encore un stock de Softtissue et de Sap, et une liste
# de verrous dont les trois etaient leves depuis des jours. Un rapport qui parle
# du palier precedent est pire qu'un rapport muet -- il a l'air juste.
#
# Le libelle est separe du prefab : le prefab est ce qu'on MESURE, le libelle ce
# qu'un humain lit. Tous les prefabs ci-dessous ont ete verifies presents dans la
# table le 2026-09-30 -- « BloodGold » et « FrostCore » portent une majuscule au
# milieu, et « Ice », « Timberwood », « SealPelt », « PetrifiedTissue » n'existent
# PAS sous ces noms, donc ils ne sont pas ici. Un prefab mal orthographie
# afficherait un zero parfaitement credible.
STOCKS = {
    "defeated_queen": ("Brumeuses", [
        ("Carapace", "Carapace"), ("Tissu mou", "Softtissue"),
        ("Marbre noir", "BlackMarble"), ("Bois d'Yggdrasil", "YggdrasilWood"),
        ("Seve", "Sap"), ("Eitr", "Eitr"), ("Fragments", "DvergrKeyFragment")]),
    "defeated_fader": ("Ashlands", [
        ("Flametal", "FlametalNew"), ("Peau d'asksvin", "AskHide"),
        ("Os calcine", "CharredBone"), ("Tendon de morgen", "MorgenSinew"),
        ("Gemmes", "GemstoneRed"), ("Cloches", "BellFragment"),
        ("Vin de feu", "BarleyWine")]),
    "defeated_fimbulbringer": ("Grand Nord", [
        ("Bloodgold", "BloodGold"), ("Frostcore", "FrostCore"),
        ("Viande d'elan", "MooseMeat"), ("Peau d'elan", "MooseHide"),
        ("Chou frise", "Kale"), ("Avoine", "Oats"), ("Poteitr", "Poteitr"),
        ("Resistance givre", "MeadFrostResist")]),
}

# Un verrou est une chose SANS LAQUELLE le palier ne se franchit pas. Il
# disparait du rapport des qu'il est leve : une liste ou tout est vert n'apprend
# rien. « inv » compte dans les coffres, « pose » compte ce qui est bati.
VERROUS = {
    "defeated_queen": [
        ("inv", "Demister", 1, "**Wisplight : 0** — on se bat aveugle dans la brume"),
        ("inv", "BlackCore", 1, "**BlackCore : 0** — bloque Forge noire, Raffinerie et Table galdr"),
    ],
    "defeated_fader": [
        ("pose", "blackforge_ext3_metalcutter", 1,
         "**Decoupeuse a metal absente** — sans elle, aucune arme gemmee n'existe"),
        ("inv", "BarleyWine", 10,
         "**Vin de resistance au feu trop bas** — la lave et les Charred brulent, c'est obligatoire"),
    ],
    "defeated_fimbulbringer": [
        ("inv", "MeadFrostResist", 10,
         "**Resistance au givre trop basse** — les trois meteos du Nord gelent, jour et nuit"),
        ("inv", "Embers", 1,
         "**Braises : 0** — sans elles, ni pelle a neige ni charge de braise, donc pas de Bloodgold"),
    ],
}

PREFABS_POSES = ("blackforge", "piece_magetable", "eitrrefinery",
                 "piece_sapcollector", "piece_preptable",
                 # Le palier Ashlands, ajoute le 2026-09-29. Les noms ont ete
                 # LUS dans la table de prefabs, pas devines : la presse
                 # d'artisan est « artisan_ext1 » et non « piece_artisanpress »,
                 # et le drakkar est « VikingShip_Ashlands ». Se tromper de nom
                 # ne leve aucune erreur -- ca compte simplement zero, pour
                 # toujours.
                 "artisan_ext1", "VikingShip_Ashlands",
                 "blackforge_ext3_metalcutter", "blackforge_ext4_gemcutter")


ORDRE_PALIERS = ["defeated_eikthyr", "defeated_gdking", "defeated_bonemass",
                 "defeated_dragon", "defeated_goblinking", "defeated_queen",
                 "defeated_fader", "defeated_fimbulbringer"]


def compte_rendu(monde, source, d, changements, inv, pose, k, joueurs):
    faits = sum(1 for c in d["chantiers"] if c["etat"] == "fait")
    total = len(d["chantiers"])
    lignes = ["**Fin de session — %s**" % monde, ""]
    if changements:
        lignes.append("**Ce qui a bouge aujourd'hui :**")
        for nom, avant, apres in changements:
            lignes.append("• %s : %s → **%s**" % (nom, avant, apres))
    else:
        lignes.append("_Rien de mesurable n'a change aujourd'hui._")
    lignes += ["", "**Chantiers : %d/%d faits.**" % (faits, total), ""]

    prochain = next((c for c in ORDRE_PALIERS if c not in k), None)

    verrous = ["• " + t for ou, quoi, seuil, t in VERROUS.get(prochain, [])
               if (inv[quoi] if ou == "inv" else pose.get(quoi, 0)) < seuil]
    if verrous:
        lignes.append("**Verrous :**")
        lignes += verrous
        lignes.append("")

    biome, quoi = STOCKS.get(prochain, (None, []))
    if quoi:
        lignes.append("**Stock %s :** " % biome + " · ".join(
            "%s %d" % (libelle, inv[prefab]) for libelle, prefab in quoi))
        lignes.append("")
    lignes.append("_Mesure sur %s. Les sacs des joueurs ne sont pas visibles "
                  "d'ici : un chantier peut etre fait sans que je le voie._" % source)
    return "\n".join(lignes)


def publie(texte):
    url = BI.config()
    if not url:
        print("webhook non configure : rien n'est publie", file=sys.stderr)
        return 0
    corps = json.dumps({"embeds": [{"title": "🌙  Fin de session",
                                    "color": VERT,
                                    "description": texte[:4000]}],
                        "username": "Claudo Le Viking",
                        "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as rep:
            print("compte rendu publie (HTTP %s)" % rep.status)
    except (urllib.error.URLError, OSError) as e:
        print("publication impossible : %s" % e, file=sys.stderr)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="Fin de session Valheim.")
    ap.add_argument("--sec", action="store_true",
                    help="mesure et affiche, sans rien ecrire ni publier")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--chantiers", help="un autre fichier de chantiers, pour essayer")
    o = ap.parse_args()

    if o.chantiers:
        CH.FICHIER = o.chantiers
    d = CH.charge()
    monde = os.environ.get("NOM_MONDE") or CH_monde() or "NordheimV2"
    dossier, source = dossier_monde(monde)
    if not dossier:
        print("monde introuvable : ni en place, ni en archive", file=sys.stderr)
        return 1

    table, table_source = table_noms()
    if not table:
        print("REFUS : table des prefabs introuvable (%s). Sans elle tous les "
              "stocks valent zero et les chantiers seraient coches a tort."
              % ", ".join(TABLES), file=sys.stderr)
        return 1
    inv = recense(dossier, table)
    pose = poses(dossier, PREFABS_POSES)
    tags = etiquettes(dossier)
    k = cles(monde)
    joueurs = max(1, len(d.get("joueurs", {})))

    voulus = regles(inv, pose, tags, k, joueurs)
    changements = []
    for c in d["chantiers"]:
        cible = voulus.get(c["nom"])
        if cible and cible != c["etat"]:
            changements.append((c["nom"], c["etat"], cible))
            if not o.sec:
                c["etat"] = cible

    texte = compte_rendu(monde, source, d, changements, inv, pose, k, joueurs)
    if o.json:
        print(json.dumps({"monde": monde, "source": source,
                          "changements": changements,
                          "texte": texte}, ensure_ascii=False, indent=2))
        return 0
    print(texte)
    if o.sec:
        print("\n[--sec : rien n'a ete ecrit ni publie]")
        return 0
    if changements:
        CH.sauve(d)
    return publie(texte)


def CH_monde():
    """Le monde charge par le serveur, lu dans sa ligne de commande."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            args = open("/proc/%s/cmdline" % pid, "rb").read().decode(
                "utf-8", "replace").split("\0")
        except OSError:
            continue
        if args and "valheim_server" in args[0] and "-world" in args:
            i = args.index("-world")
            if i + 1 < len(args) and args[i + 1]:
                return args[i + 1]
    return None


if __name__ == "__main__":
    sys.exit(main())
