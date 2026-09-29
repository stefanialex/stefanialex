#!/usr/bin/env python3
"""L'oracle : des indices tires du monde reel, dits a demi-mot.

Le serveur sait ou se trouvent les lieux que le groupe a fait generer -- autels
de boss, cryptes, grottes a trolls -- parce qu'il ecrit une ligne a chaque fois
qu'il en pose un. Cet oracle croise ces lieux avec l'avancement du groupe et en
tire un indice, formule de facon volontairement vague.

Pourquoi vague. Alexandre a demande un « coach et maitre du jeu », pas un
guide de solution. Donner « l'autel est en (384, -256) » supprime l'exploration,
qui est le coeur du jeu. Donner « quelque chose de plus vieux que vous repose a
cinq cents pas vers le levant » oriente sans reveler : le groupe garde le
plaisir de chercher, et l'indice reste vrai.

D'ou trois regles d'ecriture, tenues par le code et pas par la bonne volonte :

  - jamais de coordonnee exacte : direction cardinale et distance arrondie a la
    centaine de pas ;
  - jamais plus d'un indice par sujet et par jour ;
  - rien sur ce que le groupe a deja trouve -- l'oracle se tait sur les boss
    vaincus, et ne parle que de l'etape en cours.

Ce que l'oracle NE sait pas, et il ne doit pas faire semblant : la carte
complete. Il ne connait que ce que le serveur a genere parce qu'un joueur s'en
est approche. Tout le reste du monde n'existe pas encore sur le disque.

Usage :
    oracle-valheim.py                 # l'indice du jour
    oracle-valheim.py --json
    oracle-valheim.py --tout          # tout ce que l'oracle sait, pour debug
"""

import argparse
import datetime
import json
import math
import os
import re
import urllib.error
import urllib.request
import sqlite3
import subprocess
import sys

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
CONF = "/etc/valheim-discord.conf"
AGENT = "valheim-serveur/1.0 (collecteur de statistiques auto-heberge)"
# Le meme nom que le reste du salon : l'oracle n'est pas un second personnage,
# c'est la meme voix qui parle a demi-mot.
NOM_AFFICHE = "Claudo Le Viking"
ZONE = 64.0          # cote d'une zone Valheim, en metres

LIGNE = re.compile(r"Placed location (\w+) in zone (-?\d+),(-?\d+)")

# Les boss, dans l'ordre, avec le nom du lieu de leur autel.
ETAPES = [
    ("defeated_eikthyr", "Eikthyr", "Eikthyrnir"),
    ("defeated_gdking", "l'Ancien", "GDKing"),
    ("defeated_bonemass", "Bonemass", "Bonemass"),
    ("defeated_dragon", "Moder", "Dragonqueen"),
    ("defeated_goblinking", "Yagluth", "GoblinKing"),
]

# Ce qui merite un indice, et comment le nommer sans le nommer.
MURMURES = {
    "Eikthyrnir": "quelque chose de plus vieux que vous",
    "GDKing": "des pierres dressees que la foret protege",
    "Bonemass": "une odeur qui monte des eaux mortes",
    "Dragonqueen": "un souffle froid, tout en haut",
    "GoblinKing": "des feux qui brulent dans la plaine",
    "Crypt2": "des tombes que la Foret Noire garde",
    "Crypt3": "des tombes que la Foret Noire garde",
    "Crypt4": "des tombes que la Foret Noire garde",
    "TrollCave02": "un antre ou dort quelque chose de grand",
    "Vendor_BlackForest": "un marchand, si on sait ecouter",
    "SunkenCrypt4": "des cryptes noyees",
    "Grave1": "des morts mal enterres",
    "StoneTowerRuins07": "des tours qui ne tiennent plus",
    "StoneTowerRuins09": "des tours qui ne tiennent plus",
    "StoneTowerRuins10": "des tours qui ne tiennent plus",
    "BearCave": "une tanniere chaude",
    "Runestone_Meadows": "une pierre qui parle",
    # Les Brumeuses, ajoutees le 2026-09-20 : le groupe y est entre la veille
    # et l'oracle n'avait aucun mot pour en parler, alors que le serveur avait
    # deja pose quinze lieux la-bas. Il voyait tout et se taisait.
    "Mistlands_DvergrTownEntrance1": "un seuil taille par d'autres mains, et ce qui remue derriere",
    "Mistlands_Excavation1": "une fouille que la brume a reprise",
    "Mistlands_Excavation2": "une fouille que la brume a reprise",
    "Mistlands_Giant1": "des os trop grands pour une bete",
    "Mistlands_GuardTower1_ruined_new2": "une tour de guet que la brume avale",
    "Mistlands_GuardTower2_new": "une tour de guet que la brume avale",
    "Mistlands_RoadPost1": "un jalon sur une route que plus personne n'emprunte",
    "Mistlands_Swords1": "des lames plantees, et personne pour les reprendre",
    "Mistlands_Viaduct1": "un pont qui ne mene plus nulle part",
    "Mistlands_Harbour1": "un port sans navire",
    "Mistlands_RockSpire1": "une aiguille de pierre qui perce la brume",
    "Mistlands_Statue2": "une statue qui regarde encore",
    # Le Big Rock Clearing : unique par monde, vingt-deux cailloux de
    # compagnie autour. Le groupe en avait deja un -- un seul BigRock dans le
    # monde au 2026-09-20 -- et le croyait rarissime, sur la foi d'une rumeur
    # de « quatre par monde ». Le lieu etait deja genere : l'oracle pouvait le
    # dire, il lui manquait le mot.
    "BigRockClearing": "un cercle de pierres qui vous rendent votre regard",
    # Trouve le 2026-09-29 par « --muets », unique dans ce monde et jamais
    # annonce. Reste une DECOUVERTE et non un rappel : c'est une marchande, et
    # se faire repeter l'adresse d'un marchand chez qui on a deja tout achete
    # est exactement la plainte qui a lance ce chantier.
    "BogWitch_Camp": "un feu qui brule dans la tourbe, et quelqu'un pour l'entretenir",
    # Le Grand Nord, ajoute le 2026-09-29. Le serveur y avait deja pose
    # vingt-neuf lieux -- l'oracle les voyait tous et n'avait aucun mot pour
    # eux, exactement comme pour les Brumeuses le 20/09. Ces murmures ne
    # serviront qu'une fois Fader tombe, mais ils seront prets.
    "DN_gammeltrollFrac01": "un geant change en pierre, et ce qu'il garde dedans",
    "DN_gammeltrollFrac02": "un geant change en pierre, et ce qu'il garde dedans",
    "DN_hut01": "un abri que le gel n'a pas tout a fait pris",
    "IcePond1": "une eau qui ne bouge plus",
    "MorkBorg": "une porte qui demande sa clef, et quatorze etages dessous",
    "AbandonedLogCabin02": "des rondins empiles par des mains parties depuis",
    "AbandonedLogCabin03": "des rondins empiles par des mains parties depuis",
    "AbandonedLogCabin04": "des rondins empiles par des mains parties depuis",
}

# Les cabanes du Grand Nord se ressemblent et sont nombreuses -- trente ici --
# exactement comme les tombes de la Foret Noire et les ruines des Brumeuses.
# On les annonce en grappe, sinon l'oracle rend un plan cadastral.
CABANES_NORD = ("AbandonedLogCabin02", "AbandonedLogCabin03",
                "AbandonedLogCabin04", "DN_hut01")

# Les POINTS DE RESSOURCE, ajoutes le 2026-09-29 a la demande d'Alexandre.
# Ils echappent au filtre « deja foule », et c'est volontaire : on ne va pas
# chez un marchand deux fois pour le decouvrir, mais on retourne dix fois a un
# geant de pierre. Avoir traverse la zone ne veut pas dire avoir exploite le
# lieu -- et le serveur ne peut pas distinguer les deux, puisqu'il ne voit ni
# les sacs ni ce qui a ete casse.
#
# Consequence assumee, a ne pas cacher : un gammeltroll DEJA fait sauter sera
# quand meme rappele. C'est pourquoi ces rappels sont formules comme des
# rappels -- « vous les connaissez » -- et donnent le NOMBRE plutot que de
# faire croire a une decouverte.
# Le troisieme champ est le GENRE, ecrit a la main comme les pluriels du
# voisin stats-valheim.py et pour la meme raison : « dont le plus proche »
# contre « dont la plus proche ». Aucune regle mecanique ne devine le genre
# d'un nom francais, et se tromper sur chaque rappel feminin se voit.
RESSOURCES = {
    "DN_gammeltrollFrac01": ("un geant change en pierre", "geants changes en pierre", "m"),
    "DN_gammeltrollFrac02": ("un geant change en pierre", "geants changes en pierre", "m"),
    "MorkBorg": ("une porte qui demande sa clef", "portes qui demandent leur clef", "f"),
    "IcePond1": ("une eau qui ne bouge plus", "eaux qui ne bougent plus", "f"),
    "Mistlands_DvergrTownEntrance1": ("un seuil taille par d'autres mains",
                                      "seuils tailles par d'autres mains", "m"),
    # Trouve le 2026-09-29 par « --muets » : trente-sept epaves posees et pas
    # un mot pour elles. Trois epaves sur quatre cachent un coffre enterre, et
    # ce coffre porte presque toujours de quoi payer les poches d'Haldor.
    "ShipWreck01_DN": ("une coque echouee que la glace retient",
                       "coques echouees que la glace retient", "f"),
    # Le murmure ci-dessus ne couvrait que 37 epaves sur 71 : les trois
    # « FrozenShip » et « ShipWreck02_DN » en ajoutent 34. Meme libelle, donc
    # le regroupement par libelle les compte ensemble et n'en fait qu'un indice.
    "ShipWreck02_DN": ("une coque echouee que la glace retient",
                       "coques echouees que la glace retient", "f"),
    "FrozenShip01_DN": ("une coque echouee que la glace retient",
                        "coques echouees que la glace retient", "f"),
    "FrozenShip02_DN": ("une coque echouee que la glace retient",
                        "coques echouees que la glace retient", "f"),
    "FrozenShip03_DN": ("une coque echouee que la glace retient",
                        "coques echouees que la glace retient", "f"),
    # Meme oubli cote Brumeuses : il existe une SECONDE entree de mine.
    "Mistlands_DvergrTownEntrance2": ("un seuil taille par d'autres mains",
                                      "seuils tailles par d'autres mains", "m"),
    # Grand Nord. Le site memorial est le plus utile des trois : trois charbons
    # a son autel y appellent un Guerrier dechu, qui lache les essences, et
    # c'est la que se trouve le Vegvisir du dernier boss.
    "NorthMemorialPlace": ("une pierre ou l'on se souvient des morts",
                           "pierres ou l'on se souvient des morts", "f"),
    "NorthVillage": ("un village que le nord a vide",
                     "villages que le nord a vides", "m"),
    "TarPit1": ("une mare noire qui remue", "mares noires qui remuent", "f"),
    "TarPit2": ("une mare noire qui remue", "mares noires qui remuent", "f"),
    "TarPit3": ("une mare noire qui remue", "mares noires qui remuent", "f"),
    # La Forge du Potentiel. Classee RESSOURCE et non decouverte, apres coup :
    # en decouverte elle etait filtree -- le groupe avait traverse sa zone --
    # donc l'oracle n'en aurait jamais souffle mot, alors que c'est le lieu le
    # plus utile de la liste. Et ce n'est pas une decouverte : on y RETOURNE, une
    # fois par idole, et il y a seize idoles. Une seule par monde, et la
    # premiere approchee fixe l'emplacement pour toujours.
    # Reserve : l'identification vient du nom du prefab, aucune source
    # consultee le 29/09 ne la confirme.
    "AncientUpgradeStation": ("un atelier laisse par de plus anciens",
                              "ateliers laisses par de plus anciens", "m"),
}

# Les ruines des Brumeuses se ressemblent et sont nombreuses. On les annonce en
# grappe, comme les tombes de la Foret Noire : onze indices le meme jour, ce
# n'est plus un oracle, c'est un plan. L'entree de ville dvergr, elle, sort du
# lot et garde son indice propre -- c'est par la que passent les mines.
RUINES_BRUMEUSES = (
    "Mistlands_Excavation1", "Mistlands_Excavation2", "Mistlands_Giant1",
    "Mistlands_GuardTower1_ruined_new2", "Mistlands_GuardTower2_new",
    "Mistlands_RoadPost1", "Mistlands_Swords1", "Mistlands_Viaduct1",
    "Mistlands_Harbour1", "Mistlands_RockSpire1", "Mistlands_Statue2",
)

CARDINAUX = [(0, "au nord"), (45, "au nord-est"), (90, "au levant"),
             (135, "au sud-est"), (180, "au sud"), (225, "au sud-ouest"),
             (270, "au couchant"), (315, "au nord-ouest")]


def direction(x, z):
    """Un point cardinal, en mots. Le nord de Valheim est le +Z."""
    angle = (math.degrees(math.atan2(x, z)) + 360) % 360
    return min(CARDINAUX, key=lambda c: min(abs(angle - c[0]),
                                            360 - abs(angle - c[0])))[1]


def pas(distance):
    """Une distance arrondie a la centaine, dite en pas plutot qu'en metres.

    L'arrondi n'est pas cosmetique : il empeche l'oracle de servir de GPS.
    """
    return int(round(distance / 100.0) * 100)


def monde_courant():
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


def lieux(depuis):
    """Les lieux generes depuis une date, par type, en coordonnees de monde.

    Lus dans le journal et non en base : le collecteur ne retient que la zone,
    pas le type de lieu. Consequence a connaitre -- la profondeur du journal
    limite la memoire de l'oracle, qui oubliera les lieux les plus anciens.
    """
    cmd = ["journalctl", "-u", "valheim", "-o", "cat", "--no-pager"]
    if depuis:
        cmd += ["--since", depuis]
    try:
        sortie = subprocess.run(cmd, capture_output=True, text=True,
                                errors="replace", timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    trouves = {}
    for m in LIGNE.finditer(sortie):
        nom, zx, zy = m.group(1), int(m.group(2)), int(m.group(3))
        trouves.setdefault(nom, set()).add((zx * ZONE, zy * ZONE))
    return {n: sorted(p) for n, p in trouves.items()}


def zones_vues(cx, monde):
    """Les zones ou un joueur a deja mis les pieds, en coordonnees de zone.

    Le collecteur ecrit un evenement « zone » a chaque zone chargee par un
    joueur. Une zone fait 64 metres de cote : y avoir ete, c'est etre passe a
    portee de vue de ce qu'elle contient. C'est la meilleure definition de
    « trouve » dont on dispose cote serveur, et elle suffit.
    """
    vues = set()
    for (d,) in cx.execute(
            "SELECT DISTINCT detail FROM evenements "
            "WHERE type = 'zone' AND monde IS ?", (monde,)):
        if not d or "," not in d:
            continue
        try:
            zx, zy = (int(v) for v in d.split(",", 1))
        except ValueError:
            continue
        vues.add((zx, zy))
    return vues


def inexplores(trouves, vues):
    """Les lieux dont le groupe ignore encore l'existence.

    L'en-tete de ce fichier promet depuis le premier jour que l'oracle ne parle
    pas de ce qui est deja trouve. Jusqu'au 2026-09-29 cette regle n'etait
    tenue QUE pour les boss, par les cles globales ; tous les autres sujets --
    marchands, cavernes, entrees dvergr -- etaient annonces des que le serveur
    les avait poses, trouves ou non. Mesure ce jour-la : les six sujets que
    l'oracle savait nommer avaient tous ete visites, Haldor et Hildir compris.
    L'oracle etait donc integralement du bruit, et le disait tous les jours.
    """
    reste = {}
    for nom, points in trouves.items():
        if nom in RESSOURCES:
            reste[nom] = points          # on y retourne : jamais filtre
            continue
        neufs = [p for p in points
                 if (int(round(p[0] / ZONE)), int(round(p[1] / ZONE))) not in vues]
        if neufs:
            reste[nom] = neufs
    return reste


def muets(trouves):
    """Les types de lieux que le serveur a poses et dont l'oracle n'a pas le mot.

    Trois fois ce projet a decouvert APRES COUP que l'oracle traversait un
    biome entier sans rien pouvoir en dire : les Brumeuses le 2026-09-20 (15
    lieux poses, zero murmure), le Grand Nord le 2026-09-29 (29 lieux), et les
    Ashlands qui viennent. A chaque fois le programme se taisait sans que rien
    ne le signale -- le silence ne leve pas d'erreur.

    Cette fonction existe pour que la quatrieme fois se voie tout de suite.
    Elle ne devine aucun nom : elle dit seulement « voila ce que je vois et que
    je ne sais pas nommer », et c'est a un humain d'ecrire le murmure.
    """
    connus = set(MURMURES) | set(RESSOURCES) | set(RUINES_BRUMEUSES) | set(CABANES_NORD)
    return sorted(((len(p), n) for n, p in trouves.items() if n not in connus),
                  reverse=True)


def etape(cx, monde):
    """Le prochain boss a abattre, d'apres les cles globales du monde."""
    vaincus = {c for (c,) in cx.execute(
        "SELECT cle FROM cles_globales WHERE monde IS ?", (monde,))}
    for cle, nom, lieu in ETAPES:
        if cle not in vaincus:
            return cle, nom, lieu
    return None, None, None


def indices(cx, monde, tous=False):
    """Les indices disponibles, du plus pertinent au moins."""
    debut = cx.execute(
        "SELECT min(horodatage) FROM evenements WHERE monde IS ?",
        (monde,)).fetchone()
    trouves = lieux(debut[0] if debut and debut[0] else None)
    # « --tout » montre ce que l'oracle SAIT ; le mode normal ne garde que
    # ce qu'il a encore un interet a dire.
    if not tous:
        trouves = inexplores(trouves, zones_vues(cx, monde))
    _cle, nom_boss, lieu_boss = etape(cx, monde)

    sortie = []
    if lieu_boss and trouves.get(lieu_boss):
        proche = min(trouves[lieu_boss], key=lambda p: math.hypot(*p))
        d = math.hypot(*proche)
        sortie.append({
            "sujet": "boss",
            "texte": "%s repose a quelque %d pas %s. Vous etes passes assez "
                     "pres pour que la terre s'en souvienne."
                     % (MURMURES.get(lieu_boss, "quelque chose").capitalize(),
                        pas(d), direction(*proche)),
        })

    cryptes = [p for n in ("Crypt2", "Crypt3", "Crypt4") for p in trouves.get(n, [])]
    if cryptes:
        # La grappe : le quadrant qui en compte le plus.
        quadrants = {}
        for x, z in cryptes:
            quadrants.setdefault(direction(x, z), []).append((x, z))
        # A nombre egal, la direction la plus PROCHE : le 2026-09-09 l'oracle
        # designait six tombes a 1100 pas au sud-est alors que six autres
        # attendaient a 830 pas au levant. Un indice juste mais moins utile
        # qu'un autre reste un mauvais indice.
        ou, groupe = min(
            quadrants.items(),
            key=lambda kv: (-len(kv[1]),
                            sum(math.hypot(*p) for p in kv[1]) / len(kv[1])))
        d = sum(math.hypot(*p) for p in groupe) / len(groupe)
        sortie.append({
            "sujet": "cryptes",
            "texte": "Les tombes de la Foret Noire ne sont pas dispersees au "
                     "hasard : %d d'entre elles se serrent %s, a quelque %d pas."
                     % (len(groupe), ou, pas(d)),
        })

    brumes = [p for n in RUINES_BRUMEUSES for p in trouves.get(n, [])]
    if brumes:
        proche = min(brumes, key=lambda p: math.hypot(*p))
        sortie.append({
            "sujet": "brumeuses",
            "texte": "Sous la brume, %d ouvrages tiennent encore debout. Le "
                     "plus proche est a quelque %d pas %s."
                     % (len(brumes), pas(math.hypot(*proche)),
                        direction(*proche)),
        })

    nord = [p for n in CABANES_NORD for p in trouves.get(n, [])]
    if nord:
        proche = min(nord, key=lambda p: math.hypot(*p))
        sortie.append({
            "sujet": "grand_nord",
            "texte": "Loin au nord, %d abris tiennent encore sous la neige. Le "
                     "plus proche est a quelque %d pas %s."
                     % (len(nord), pas(math.hypot(*proche)),
                        direction(*proche)),
        })

    # Les rappels de ressource, regroupes par libelle : les deux variantes de
    # gammeltroll sont le meme sujet et ne doivent pas faire deux indices.
    groupes = {}
    for nom, (un, plusieurs, genre) in RESSOURCES.items():
        for p in trouves.get(nom, []):
            groupes.setdefault((un, plusieurs, genre), []).append(p)
    for (un, plusieurs, genre), points in groupes.items():
        proche = min(points, key=lambda p: math.hypot(*p))
        d, ou = pas(math.hypot(*proche)), direction(*proche)
        if len(points) == 1:
            texte = ("Vous %s connaissez deja : %s vous attend a quelque "
                     "%d pas %s." % ("la" if genre == "f" else "le", un, d, ou))
        else:
            texte = ("Vous les connaissez deja : %d %s, dont %s plus proche a "
                     "quelque %d pas %s."
                     % (len(points), plusieurs,
                        "la" if genre == "f" else "le", d, ou))
        sortie.append({"sujet": "ressource", "texte": texte})

    for nom in ("Vendor_BlackForest", "BogWitch_Camp", "TrollCave02",
                "BearCave", "BigRockClearing"):
        if trouves.get(nom):
            proche = min(trouves[nom], key=lambda p: math.hypot(*p))
            sortie.append({
                "sujet": nom,
                "texte": "%s, a quelque %d pas %s."
                         % (MURMURES.get(nom, nom).capitalize(),
                            pas(math.hypot(*proche)), direction(*proche)),
            })

    if not sortie:
        # Deux silences a ne pas confondre. Le monde n'a rien pose : l'oracle
        # ne sait rien. Le monde a tout pose et le groupe a tout foule : il
        # sait, et il n'a plus rien d'utile a dire. Le second cas se produit
        # des qu'un groupe a bien explore -- c'etait deja vrai le 2026-09-29 --
        # et le confondre avec le premier ferait mentir l'oracle.
        tout = lieux(debut[0] if debut and debut[0] else None)
        sortie.append({
            "sujet": "rien",
            "texte": "Vous avez foule tout ce que je sais nommer. Poussez plus "
                     "loin que vos traces, et j'aurai de nouveau quelque chose "
                     "a vous dire."
                     if tout else
                     "Le monde ne m'a encore rien dit. Marchez, et je verrai.",
        })
    return sortie


def annonce(texte):
    """Publie dans le salon. Silencieux si le webhook n'est pas configure : le
    programme doit rester lancable sur une machine neuve."""
    try:
        with open(CONF) as f:
            url = next(l.split("=", 1)[1].strip().strip('"')
                       for l in f if l.startswith("WEBHOOK="))
    except (OSError, StopIteration):
        print("pas de webhook configure, rien publie", file=sys.stderr)
        return False
    corps = json.dumps({"content": texte, "username": NOM_AFFICHE,
                        "allowed_mentions": {"parse": []}}).encode()
    r = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    try:
        urllib.request.urlopen(r, timeout=15)
    except (urllib.error.URLError, OSError) as e:
        print("annonce non partie : %s" % e, file=sys.stderr)
        return False
    return True


def deja_dit_aujourd_hui(jour):
    """Un indice par jour, et pas un de plus.

    La rotation est deterministe sur la date, donc deux lancements le meme jour
    rediraient mot pour mot la meme chose. Le garde-fou est en base plutot que
    dans la minuterie : une minuterie « Persistent » rattrape un passage manque
    au demarrage, et c'est justement la qu'on republierait.
    """
    cx = sqlite3.connect(BASE)
    try:
        cx.execute("CREATE TABLE IF NOT EXISTS reglages "
                   "(cle TEXT PRIMARY KEY, valeur TEXT)")
        r = cx.execute(
            "SELECT valeur FROM reglages WHERE cle = 'oracle_dernier_jour'").fetchone()
        if r and r[0] == jour:
            return True
        cx.execute("INSERT INTO reglages (cle, valeur) VALUES "
                   "('oracle_dernier_jour', ?) ON CONFLICT (cle) DO UPDATE SET "
                   "valeur = excluded.valeur", (jour,))
        cx.commit()
        return False
    except sqlite3.OperationalError as e:
        # Base non inscriptible : on ne publie PAS. Sans la marque, un second
        # passage rediraient le meme indice dans le salon, et deux fois le meme
        # oracle dans la journee le decredibilise. Echouer bruyamment vaut
        # mieux que publier en double.
        raise SystemExit("base non inscriptible (%s) : rien publie. Ce "
                         "programme doit tourner sous le compte valheim." % e)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tout", action="store_true",
                    help="tous les indices, sans rotation")
    ap.add_argument("--discord", action="store_true",
                    help="publie l'indice du jour dans le salon")
    ap.add_argument("--quand-meme", action="store_true",
                    help="publie meme si c'est deja fait aujourd'hui")
    ap.add_argument("--muets", action="store_true",
                    help="les lieux poses dont l'oracle n'a pas le mot")
    o = ap.parse_args()

    monde = monde_courant()
    cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
    if o.muets:
        debut = cx.execute(
            "SELECT min(horodatage) FROM evenements WHERE monde IS ?",
            (monde,)).fetchone()
        m = muets(lieux(debut[0] if debut and debut[0] else None))
        print("%d types de lieux poses sans murmure :" % len(m))
        for n, nom in m:
            print("  %4d  %s" % (n, nom))
        return 0
    # « tous=o.tout » et non « tous=True ». Jusqu'au 2026-09-29 cette ligne
    # passait TOUJOURS True : le filtre « deja foule » existait, mais la
    # rotation quotidienne piochait dans la liste NON filtree, donc il ne
    # servait a rien en production. Un test qui appelait indices() en direct ne
    # pouvait pas le voir -- il faut passer par main() pour que ce bug parle.
    tous = indices(cx, monde, tous=o.tout)
    if not tous:
        return 0
    if o.tout:
        choisis = tous
    else:
        # Rotation deterministe sur la date : chacun revient regulierement,
        # aucun n'est oublie, et deux jours de suite ne se ressemblent pas.
        jour = datetime.date.today().toordinal()
        choisis = [tous[jour % len(tous)]]

    if o.discord:
        jour = datetime.date.today().isoformat()
        if not o.quand_meme and deja_dit_aujourd_hui(jour):
            print("indice du %s deja publie" % jour)
            return 0
        texte = "\n".join("🔮  " + i["texte"] for i in choisis)
        if not annonce(texte):
            return 1
        print("publie : %s" % texte.replace("\n", " / "))
        return 0

    if o.json:
        print(json.dumps({"monde": monde, "indices": choisis}, ensure_ascii=False))
    else:
        for i in choisis:
            print("🔮  " + i["texte"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
