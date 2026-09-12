#!/usr/bin/env python3
"""Collecteur de statistiques du serveur Valheim.

Lit le journal de valheim.service et en derive des evenements de joueurs dans
une base SQLite. Aucun mod, rien a installer chez les joueurs : tout vient de
ce que le serveur ecrit deja dans son journal.

Le journal est relu depuis le debut a chaque demarrage plutot que suivi par
curseur. C'est volontaire : la contrainte UNIQUE rend l'insertion idempotente,
donc une relecture ne cree pas de doublon, et le collecteur se repare tout seul
apres une coupure ou une base supprimee. Sans curseur a maintenir, il n'y a pas
d'etat qui puisse se desynchroniser.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
SAVEDIR = "/var/lib/valheim/donnees/worlds_local"

# Valheim prefixe ses lignes de son horloge locale : « 09/04/2026 13:43:03: ».
# Les lignes sans ce prefixe (traces Unity, Steam) ne nous interessent pas.
PREFIXE = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2}): (.*)$")

MOTIFS = [
    # « Got connection SteamID 76561198076795149 » : un joueur entre.
    ("connexion", re.compile(r"^Got connection SteamID (\d+)$"), "steamid"),
    # « Closing socket 76561198076795149 » : il sort. Le SteamID permet
    # d'apparier la sortie a l'entree, ce que le pseudo ne permettrait pas.
    ("deconnexion", re.compile(r"^Closing socket (\d+)$"), "steamid"),
    # « Got character ZDOID from Beware : 0:0 » : le 0:0 signale une mort.
    # Tout autre identifiant est une apparition (arrivee ou reapparition).
    ("zdoid", re.compile(r"^Got character ZDOID from (.+?) : (-?\d+):(\d+)$"), "zdoid"),
    # « Random event set:army_theelder » : Valheim ne declenche le raid d'un
    # boss qu'une fois ce boss vaincu. C'est notre seule trace datee de la
    # progression, le journal ne dit rien des global keys.
    ("raid", re.compile(r"^Random event set:(\S+)$"), "detail"),
    # La sauvegarde, et la taille du monde qu'elle mesurait. La 0.2 disait tout
    # en une ligne, « Saved 12345 ZDOs » : la date du point de sauvegarde ET le
    # nombre d'objets du monde. La 1.0 a separe les deux, et le motif unique ne
    # captait plus rien -- constate le 2026-09-10 : 1795 releves sur Midgard,
    # zero sur NordheimV2. On lit donc les deux lignes de la 1.0.
    ("sauvegarde", re.compile(r"^Saved (\d+) ZDOs$"), "detail"),
    # « World save (5/5) done. Total time [41ms] » : la sauvegarde 1.0 est
    # confirmee. On garde la duree comme detail -- c'est le seul chiffre de la
    # ligne, et une sauvegarde qui s'allonge annonce un monde qui grossit.
    ("sauvegarde", re.compile(r"^World save \(5/5\) done\. Total time \[(\d+)ms\]$"),
     "detail"),
    # «  Connections 0 ZDOS:144313  sent:0 recv:0 » : le recensement d'objets,
    # ecrit toutes les dix minutes, sauvegarde ou pas. C'est le remplacant du
    # compte que portait « Saved N ZDOs », d'ou son type propre : melanger les
    # deux ferait passer un recensement pour une sauvegarde.
    # Le corps de cette ligne commence par une espace, d'ou le \s* : sans lui
    # le motif ne colle pas, en silence.
    ("zdos", re.compile(r"^\s*Connections \d+ ZDOS:(\d+)\b.*$"), "detail"),
    # La MEME ligne porte le nombre de joueurs connectes, et personne ne le
    # gardait. C'est pourtant la seule source fiable : l'appariement
    # connexion/deconnexion laisse des sessions ouvertes pour toujours quand le
    # serveur s'arrete sans ecrire « Closing socket » -- constate le
    # 2026-09-12, quatre sessions fantomes alors que le serveur annoncait
    # « Connections 0 ». Le serveur, lui, dit la verite toutes les dix minutes.
    ("connectes", re.compile(r"^\s*Connections (\d+) ZDOS:\d+\b.*$"), "detail"),
    ("jour", re.compile(r"^Time [\d,.]+, day:(\d+) .*$"), "detail"),
    # « Found location of type Dragonqueen » : le serveur localise l'autel d'un
    # boss, ce qui precede la chasse de plusieurs heures. Verifie sur Moder :
    # deux localisations le 08/09 a 22h03 et 22h42, mise a mort le 09/09 a
    # 01h28. C'est la seule source qui annonce une intention et non un fait.
    ("autel", re.compile(r"^Found location of type (\S+)$"), "detail"),
    # « Placed locations in zone 14,-82  duration 67,63 ms » : Valheim peuple
    # une zone la premiere fois qu'un joueur en approche. Donc du terrain neuf,
    # et non du terrain recharge -- verifie le 2026-09-09 : zero ligne dans les
    # 20 minutes suivant les redemarrages de 5h01 du 08 et du 09, alors que la
    # soiree du 08 en compte 56 a 18h, 90 a 19h et 65 a 21h. C'est la seule
    # mesure de l'exploration reelle, celle que le temps de jeu ne dit pas.
    ("zone", re.compile(r"^Placed locations in zone (\S+)\s+duration [\d,.]+ ms$"),
     "detail"),
    # La 1.0 a change la formulation, et en mieux : elle nomme ce qu'elle pose.
    #   avant  « Placed locations in zone 14,-82  duration 67,63 ms »
    #   1.0    « Placed location Dolmen1 in zone 5,-3  duration 12 ms »
    # On garde la coordonnee de zone comme detail, pour que la mesure reste
    # comparable entre les deux formats. Consequence a ne pas oublier : il y a
    # desormais PLUSIEURS lignes par zone, une par lieu pose, donc compter les
    # evenements ne compte plus les zones -- il faut les dedoublonner sur le
    # detail. Le nom du lieu (Dolmen, Runestone, Crypt...) est une richesse
    # nouvelle, pas encore exploitee.
    ("zone", re.compile(r"^Placed location \S+ in zone (\S+)\s+duration [\d,.]+ ms$"),
     "detail"),
    # « Generating DG_SunkenCrypt(Clone), Seed: 1234 ... » : un donjon est
    # peuple a la premiere entree d'un joueur. Le type dit le biome -- crypte
    # de Foret Noire, crypte de marais, camp de gobelins, grotte gelee -- donc
    # la courbe raconte ce que le groupe farme. Sur Midgard, la semaine du 09
    # septembre : une centaine d'entrees, dominees par les cryptes de Foret
    # Noire puis celles de marais, avec une pointe de cryptes de marais la
    # veille de la chute de Bonemass -- la razzia de fer.
    #
    # Les comptes exacts ne se reproduisent pas d'une heure sur l'autre : le
    # journal systemd a une profondeur limitee, donc la fenetre glisse. Ce qui
    # est stable, c'est ce qu'on met en base au fur et a mesure.
    ("donjon", re.compile(r"^Generating (DG_\w+)\(Clone\), Seed: .*$"), "detail"),
]

# « Load world: NordheimV1 (NordheimV1) » : le serveur annonce le monde qu'il
# charge. Ce n'est pas un evenement de joueur, donc ce motif ne figure pas dans
# MOTIFS -- il sert a savoir, en rejouant le journal, a quel monde appartient
# chaque ligne.
CHARGE_MONDE = re.compile(r"^Load world: (\S+)")

SCHEMA = """
CREATE TABLE IF NOT EXISTS evenements (
  id          INTEGER PRIMARY KEY,
  horodatage  TEXT NOT NULL,
  monde       TEXT,
  type        TEXT NOT NULL,
  joueur      TEXT,
  steamid     TEXT,
  detail      TEXT,
  -- Rang de cet evenement parmi ses jumeaux de la meme seconde. Voir rang_de().
  rang        INTEGER NOT NULL DEFAULT 0
);
-- Unicite pour rendre la relecture du journal idempotente. Elle porte sur des
-- COALESCE et non directement sur les colonnes : dans SQLite deux NULL ne sont
-- jamais egaux, or la plupart des lignes ont des colonnes nulles (pas de pseudo
-- sur une connexion, pas de SteamID sur une mort). Une contrainte UNIQUE posee
-- sur les colonnes brutes ne se declencherait donc jamais et chaque relecture
-- dupliquerait tout le journal.
--
-- Le rang en fait partie, et c'est ce qui manquait. Sans lui, deux evenements
-- identiques a la meme seconde n'en faisaient qu'un -- et Valheim en produit :
-- il peuple souvent plusieurs donjons dans la meme seconde, quand un joueur
-- approche d'une zone qui en contient plusieurs. Mesure du 2026-09-10 sur le
-- journal entier : 266 entrees de donjon ecrites, 219 en base. 47 perdues,
-- 18 %. Les autres types n'ont produit qu'une seule collision (un autel) --
-- zero sur les morts, les connexions, les sauvegardes et les zones, ou le
-- dedoublonnage se fait de toute facon dans la requete.
CREATE UNIQUE INDEX IF NOT EXISTS idx_ev_unique ON evenements (
  horodatage, type, COALESCE(joueur, ''), COALESCE(steamid, ''), COALESCE(detail, ''),
  rang
);
CREATE INDEX IF NOT EXISTS idx_ev_type  ON evenements (type, horodatage);
CREATE INDEX IF NOT EXISTS idx_ev_joueur ON evenements (joueur, horodatage);

-- Metadonnees des mondes traverses. Le collecteur tourne sous l'utilisateur
-- valheim, seul a pouvoir lire /var/lib/valheim (0750) : il releve la seed ici
-- pour que le rapport, lui, n'ait besoin d'aucun privilege. L'historique sert
-- aussi a garder trace de l'ancien monde quand on en demarre un neuf.
CREATE TABLE IF NOT EXISTS mondes (
  monde              TEXT PRIMARY KEY,
  seed               TEXT,
  seed_entiere       INTEGER,
  version_format     INTEGER,
  version_generateur INTEGER,
  premiere_vue       TEXT,
  derniere_vue       TEXT
);

CREATE TABLE IF NOT EXISTS joueurs (
  steamid      TEXT PRIMARY KEY,
  pseudo       TEXT,
  premiere_vue TEXT,
  derniere_vue TEXT
);

-- Tous les personnages qu'un compte a portes, et pas seulement le dernier.
-- La table « joueurs » n'en garde qu'un : elle repond a « qui est-ce ? ».
-- Celle-ci repond a « ce nom, c'etait qui ? », question qui se pose des qu'un
-- joueur refait son personnage. Le 2026-09-09 au soir, deux l'ont fait :
-- Djoose est passe de « Djoos Io » a « DjoosI o », Bab-y de « Babyy » a
-- « Babyyy ». Les anciens noms sont alors devenus des joueurs fantomes,
-- porteurs de morts que plus aucun compte ne reclamait.
CREATE TABLE IF NOT EXISTS pseudos (
  steamid      TEXT NOT NULL,
  pseudo       TEXT NOT NULL,
  premiere_vue TEXT NOT NULL,
  derniere_vue TEXT NOT NULL,
  PRIMARY KEY (steamid, pseudo)
);

-- Une « vie » : un personnage, le compte qui le porte, le monde ou il vit, et
-- ses bornes. C'est la table qui permet de remettre les compteurs a zero quand
-- un joueur repart sur un personnage neuf -- demande d'Alexandre le
-- 2026-09-10, apres une mort en etant absent du clavier.
--
-- Elle ne remplace pas « pseudos », elle la precise : « pseudos » ignore le
-- monde, or c'est justement par monde qu'un personnage vit et meurt. Et elle
-- n'efface rien : les vies passees restent, ce sont elles qui donnent le
-- cumul affiche a cote du compteur du personnage en cours.
--
-- « monde » vaut '' et non NULL quand il est inconnu : dans une cle primaire
-- SQLite, deux NULL ne sont jamais egaux, donc l'unicite ne se declencherait
-- pas et chaque relecture du journal ajouterait une ligne.
CREATE TABLE IF NOT EXISTS vies (
  monde   TEXT NOT NULL DEFAULT '',
  steamid TEXT NOT NULL,
  pseudo  TEXT NOT NULL,
  debut   TEXT NOT NULL,
  fin     TEXT NOT NULL,
  PRIMARY KEY (monde, steamid, pseudo)
);
"""


def monde_courant():
    """Nom du monde reellement charge, lu sur la ligne de commande du serveur.

    /etc/valheim.env contient le mot de passe et n'est lisible que par root ;
    le collecteur ne tourne pas en root. Mais il tourne sous le meme
    utilisateur que le serveur de jeu, donc /proc lui est ouvert -- et
    l'argument -world y figure deja developpe.

    C'est plus sur que de lister les .fwl : des qu'un ancien monde traine a
    cote du nouveau, le classement alphabetique designe n'importe lequel des
    deux. La ligne de commande, elle, ne peut pas se tromper.
    """
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                args = f.read().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        if not args or "valheim_server" not in args[0]:
            continue
        if "-world" in args:
            i = args.index("-world")
            if i + 1 < len(args) and args[i + 1]:
                return args[i + 1]
    # Repli si le serveur est arrete : le monde ecrit le plus recemment, hors
    # sauvegardes automatiques. Les deux formats coexistent sur le disque apres
    # une mise a jour vers la 1.0 -- l'ancien « Midgard.fwl » reste a cote du
    # nouveau dossier « Midgard/ », fige et trompeur. On les datte donc tous
    # les deux et on garde le plus recent, ce qui designe naturellement le
    # format vivant.
    candidats = []
    try:
        for f in os.listdir(SAVEDIR):
            if "_backup_auto-" in f:
                continue
            chemin = os.path.join(SAVEDIR, f)
            if f.endswith(".fwl"):
                candidats.append((f[:-4], chemin))
            elif os.path.isdir(chemin):
                meta = chemin_metadonnees(f)
                if meta:
                    candidats.append((f, meta))
    except OSError:
        return None
    if not candidats:
        return None
    try:
        candidats.sort(key=lambda c: os.path.getmtime(c[1]))
    except OSError:
        return candidats[-1][0]
    return candidats[-1][0]


OUTIL_MONDE = "/usr/local/bin/monde-valheim.py"


def chemin_metadonnees(monde):
    """Le fichier de metadonnees d'un monde, dans l'un ou l'autre format.

    Jusqu'a la 0.221, un monde etait deux fichiers cote a cote :
    « Midgard.fwl » et « Midgard.db ». La 1.0 range chaque monde dans son
    propre dossier et numerote ses fichiers :

        worlds_local/NordheimV1/_main.1.fwl2     metadonnees
        worlds_local/NordheimV1/_main.1.db2      contenu, compresse en gzip
        worlds_local/NordheimV1/_main.1.chunks   index des troncons

    Le numero n'est pas decoratif : c'est un compteur, donc on prend le plus
    grand plutot que d'ecrire « 1 » en dur et de decouvrir le probleme dans
    six mois.

    Les deux formats sont acceptes : le nouveau d'abord, l'ancien en repli,
    pour que ce programme reste capable de relire une archive d'avant la 1.0.
    """
    dossier = os.path.join(SAVEDIR, monde)
    if os.path.isdir(dossier):
        try:
            noms = [f for f in os.listdir(dossier)
                    if f.startswith("_main.") and f.endswith(".fwl2")]
        except OSError:
            noms = []
        if noms:
            def rang(f):
                try:
                    return int(f.split(".")[1])
                except (IndexError, ValueError):
                    return -1
            return os.path.join(dossier, max(noms, key=rang))
    ancien = os.path.join(SAVEDIR, monde + ".fwl")
    return ancien if os.path.exists(ancien) else None


def releve_monde(cx, monde):
    """Note la seed et les versions du monde actif.

    Le format du fichier de metadonnees n'est connu que de monde-valheim.py,
    appele en sous-processus : un seul endroit dans le depot sait le decoder.
    Il lit les deux versions sans modification -- la structure n'a pas change
    avec la 1.0, seuls le numero de version, le nom et l'emplacement du
    fichier ont bouge.
    """
    if not monde:
        return
    chemin = chemin_metadonnees(monde)
    if not chemin:
        return
    try:
        r = subprocess.run([OUTIL_MONDE, "lire", "--json", chemin],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return
        i = json.loads(r.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return
    n = datetime.now().isoformat(sep=" ", timespec="seconds")
    cx.execute(
        "INSERT INTO mondes (monde, seed, seed_entiere, version_format, "
        "version_generateur, premiere_vue, derniere_vue) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT (monde) DO UPDATE SET derniere_vue = excluded.derniere_vue, "
        "seed = excluded.seed, version_generateur = excluded.version_generateur",
        (i["monde"], i["seed"], i["seed_entiere"], i["version_format"],
         i["version_generateur"], n, n))
    cx.commit()


# Le rang d'un evenement parmi ses jumeaux exacts de la meme seconde, compte
# pour la duree de ce processus. C'est ce qui rend le rang utilisable sans
# casser l'idempotence : le collecteur relit le journal entier a chaque
# demarrage, dans le meme ordre, donc la meme ligne recoit toujours le meme
# rang et l'INSERT OR IGNORE retombe sur la meme ligne de base.
RANGS = {}


def rang_de(ts, typ, joueur, steamid, detail):
    """Le rang de cet evenement parmi ses jumeaux deja vus dans cette passe."""
    cle = (ts, typ, joueur, steamid, detail)
    n = RANGS.get(cle, 0)
    RANGS[cle] = n + 1
    return n


def migre(cx):
    """Ajoute la colonne rang et refait l'index unique sur une base d'avant.

    La colonne s'ajoute sans douleur, mais l'index ne se remplace pas tout
    seul : « CREATE UNIQUE INDEX IF NOT EXISTS » ne fait rien quand le nom
    existe deja, meme si sa definition a change. On lit donc son texte plutot
    que sa presence -- une verification qui ne peut pas se tromper sur ce
    qu'elle constate.

    Effet au prochain rattrapage : le premier de chaque groupe de jumeaux
    retombe sur la ligne deja en base, les suivants s'inserent enfin. Les 47
    entrees de donjon perdues depuis le 2026-09-09 reviennent.
    """
    colonnes = {r[1] for r in cx.execute("PRAGMA table_info(evenements)")}
    if "rang" not in colonnes:
        cx.execute("ALTER TABLE evenements ADD COLUMN rang INTEGER NOT NULL DEFAULT 0")
    r = cx.execute("SELECT sql FROM sqlite_master WHERE type = 'index' "
                   "AND name = 'idx_ev_unique'").fetchone()
    if r and "rang" not in (r[0] or ""):
        cx.execute("DROP INDEX idx_ev_unique")
        cx.executescript(SCHEMA)
    cx.commit()


def ouvre():
    os.makedirs(os.path.dirname(BASE), exist_ok=True)
    cx = sqlite3.connect(BASE)
    cx.executescript(SCHEMA)
    migre(cx)
    return cx


def analyse(ligne):
    """Une ligne de journal -> LISTE d'evenements, souvent vide ou d'un seul.

    Une liste et non un evenement unique : « Connections 2 ZDOS:557389 » en
    porte deux, le recensement d'objets et le nombre de joueurs en ligne. Le
    programme rendait le premier motif trouve et s'arretait, ce qui interdisait
    d'en tirer deux -- limitation connue depuis le 2026-09-09, levee ici.

    Les motifs ne se recouvrent pas par ailleurs : les deux « sauvegarde » et
    les deux « zone » s'excluent par leur libelle, donc collecter toutes les
    correspondances ne cree aucun doublon.
    """
    m = PREFIXE.match(ligne.rstrip())
    if not m:
        return []
    mois, jour, an, h, mi, s, corps = m.groups()
    ts = "%s-%s-%s %s:%s:%s" % (an, mois, jour, h, mi, s)
    trouves = []
    for nom, motif, forme in MOTIFS:
        c = motif.match(corps)
        if not c:
            continue
        if forme == "steamid":
            trouves.append((ts, nom, None, c.group(1), None))
        elif forme == "detail":
            trouves.append((ts, nom, None, None, c.group(1)))
        else:
            # zdoid : 0:0 vaut mort, le reste vaut apparition. Le separateur du
            # log est «  :  », donc la capture non gourmande du pseudo ramene
            # l'espace qui precede.
            pseudo, zdo, sous = c.group(1).strip(), c.group(2), c.group(3)
            if zdo == "0" and sous == "0":
                trouves.append((ts, "mort", pseudo, None, None))
            else:
                trouves.append((ts, "apparition", pseudo, None,
                                "%s:%s" % (zdo, sous)))
    return trouves


def relie_pseudos(cx):
    """Associe chaque SteamID a un pseudo.

    Le pseudo n'apparait que sur les lignes ZDOID, le SteamID que sur les
    lignes de connexion : rien ne les relie directement. On exploite la
    sequence -- une apparition suit toujours de quelques secondes la connexion
    qui l'a provoquee. L'association n'est retenue que si une seule connexion
    est en attente dans la fenetre, sinon deux joueurs entrant ensemble
    donneraient une correspondance fausse.
    """
    lignes = cx.execute(
        "SELECT horodatage, type, joueur, steamid FROM evenements "
        "WHERE type IN ('connexion', 'apparition') ORDER BY horodatage, id"
    ).fetchall()
    attente = []  # [(horodatage, steamid)]
    for ts, typ, joueur, steamid in lignes:
        t = datetime.fromisoformat(ts)
        attente = [(a, sid) for (a, sid) in attente if t - a <= timedelta(seconds=180)]
        if typ == "connexion":
            attente.append((t, steamid))
            continue
        if len(attente) != 1:
            continue  # ambigu : on ne devine pas
        _, sid = attente.pop()
        cx.execute(
            "INSERT INTO joueurs (steamid, pseudo, premiere_vue, derniere_vue) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (steamid) DO UPDATE SET "
            "pseudo = excluded.pseudo, derniere_vue = excluded.derniere_vue",
            (sid, joueur, ts, ts),
        )
        # Et l'on garde la trace du nom, meme quand un autre lui succedera.
        cx.execute(
            "INSERT INTO pseudos (steamid, pseudo, premiere_vue, derniere_vue) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (steamid, pseudo) DO UPDATE SET "
            "derniere_vue = excluded.derniere_vue",
            (sid, joueur, ts, ts),
        )
    cx.commit()


# Delai en deca duquel une « mort » suivant la premiere apparition d'un
# personnage est tenue pour un artefact de creation, et non pour une mort.
NAISSANCE = timedelta(seconds=90)


def morts_de_naissance(cx, lot, mondes):
    """Ecarte les fausses morts dues a la creation d'un personnage.

    Le journal ecrit « Got character ZDOID from X : 0:0 » a la mort, mais aussi
    quand le serveur relache le personnage provisoire d'un joueur qui vient
    d'entrer avec un perso neuf. La sequence est reconnaissable :

        21:11:38  apparition  Lapvin  ZDO :5
        21:11:43  mort        Lapvin           <- 5 secondes plus tard
        21:11:44  apparition  Lapvin  ZDO :7

    Le 2026-09-09, le groupe a recree quatre personnages sur un monde neuf et le
    salon a annonce quatre morts qui n'avaient pas eu lieu. C'est aussi ce que
    le groupe a tranche : recreer un personnage ne doit pas casser une serie.

    Le critere est le delai depuis la PREMIERE apparition de ce personnage sur
    ce monde, et non depuis la connexion : quelqu'un peut creer un second
    personnage en cours de session -- c'est arrive le soir meme -- et le pseudo
    suffit, sans avoir a le relier a un compte Steam, lien fragile des qu'un
    joueur enchaine plusieurs persos.

    Le prix a payer, assume : une vraie mort dans les 90 premieres secondes
    d'un personnage neuf est perdue. Mieux vaut manquer une mort au spawn que
    d'en inventer quatre.

    Portee reelle, mesuree le 2026-09-09 en reconstruisant deux fois le journal
    entier, avec et sans le filtre : 92 morts brutes, 84 retenues. Le filtre en
    ecarte donc 7 et la regle du personnage abandonne 1. Les 7 sont a 2, 5, 8,
    10, 20, 24 et 58 secondes de la premiere apparition de leur personnage --
    toutes des creations de perso, dont trois anterieures au monde neuf du
    soir, le groupe ayant deja refait des personnages dans l'apres-midi.

    Cette mesure corrige une affirmation fausse : j'avais d'abord annonce que le
    filtre ne retirait rien de l'historique, en comparant la base reconstruite
    filtree a la base de production... deja filtree. Une comparaison circulaire,
    donc un test incapable d'echouer. Alexandre a demande de creuser, et il
    avait raison.
    """
    # Premiere apparition de chaque personnage concerne : ce que dit le lot,
    # puis ce que dit la base -- et la base doit etre interrogee AUSSI pour un
    # personnage qui ne fait que mourir dans ce lot, sans y apparaitre.
    #
    # C'est le cas normal en suivi, ou le lot ne contient qu'une seule ligne :
    # « premieres » restait alors vide, la boucle de rattrapage en base ne
    # tournait sur rien, et le filtre laissait passer la mort. Deux fausses
    # morts en ont profite le 2026-09-10, a 10h25 et 10h37, sur des
    # personnages crees quatre et treize secondes plus tot -- annoncees dans le
    # salon, et posees sur le compteur d'un personnage qui venait de naitre.
    # Seul le rattrapage complet filtrait, parce que son lot porte l'apparition
    # et la mort ensemble.
    premieres = {}
    orphelines = set()
    for (ts, typ, j, _sid, _d), m in zip(lot, mondes):
        if not j:
            continue
        if typ == "apparition":
            cle = (m, j)
            if cle not in premieres or ts < premieres[cle]:
                premieres[cle] = ts
        elif typ == "mort":
            orphelines.add((m, j))
    for (m, j) in set(premieres) | orphelines:
        r = cx.execute(
            "SELECT min(horodatage) FROM evenements "
            "WHERE type = 'apparition' AND joueur = ? AND monde IS ?",
            (j, m)).fetchone()
        if r and r[0] and ((m, j) not in premieres or r[0] < premieres[(m, j)]):
            premieres[(m, j)] = r[0]

    lot2, mondes2 = [], []
    for e, m in zip(lot, mondes):
        ts, typ, j = e[0], e[1], e[2]
        if typ == "mort" and j:
            debut = premieres.get((m, j))
            if debut and (datetime.fromisoformat(ts)
                          - datetime.fromisoformat(debut)) < NAISSANCE:
                continue
        lot2.append(e)
        mondes2.append(m)
    return lot2, mondes2


def comptes_par_pseudo(cx):
    """Quel compte Steam a joue quel personnage, et depuis quand.

    Meme technique que relie_pseudos -- une apparition suit de quelques
    secondes la connexion qui l'a provoquee, et on refuse de deviner quand
    plusieurs connexions sont en attente -- mais on garde ici TOUT l'historique
    au lieu du seul dernier pseudo : c'est ce qui permet de voir qu'un compte a
    change de personnage.
    """
    lignes = cx.execute(
        "SELECT horodatage, type, joueur, steamid, monde FROM evenements "
        "WHERE type IN ('connexion', 'apparition') ORDER BY horodatage, id"
    ).fetchall()
    attente, vus = [], {}
    for ts, typ, joueur, steamid, monde in lignes:
        t = datetime.fromisoformat(ts)
        attente = [(a, sid) for (a, sid) in attente if t - a <= timedelta(seconds=180)]
        if typ == "connexion":
            attente.append((t, steamid))
            continue
        if len(attente) != 1:
            continue
        _, sid = attente.pop()
        vus.setdefault((monde, joueur), (sid, ts))
    return vus


def purge_morts_de_naissance(cx):
    """Efface les fausses morts de creation deja inscrites en base.

    morts_de_naissance() filtre a l'insertion, et « INSERT OR IGNORE » ne
    revient jamais sur une ligne deja ecrite : les fausses morts passees avant
    le correctif du 2026-09-10 restaient donc en base pour toujours, et un
    rattrapage ne pouvait pas les reprendre.

    Meme critere que le filtre, applique a tout l'historique : une mort qui
    tombe dans les 90 secondes de la premiere apparition de son personnage sur
    son monde n'a pas eu lieu. Le prix est le meme, et deja assume : une vraie
    mort au spawn d'un personnage neuf est perdue. Cette regle-la se repare
    d'elle-meme a chaque demarrage, alors que les lignes fautives, elles,
    s'accumulaient.
    """
    efface = 0
    for monde, joueur, ts in cx.execute(
            "SELECT monde, joueur, horodatage FROM evenements "
            "WHERE type = 'mort' AND joueur IS NOT NULL").fetchall():
        r = cx.execute(
            "SELECT min(horodatage) FROM evenements "
            "WHERE type = 'apparition' AND joueur = ? AND monde IS ?",
            (joueur, monde)).fetchone()
        if not r or not r[0]:
            continue
        if (datetime.fromisoformat(ts)
                - datetime.fromisoformat(r[0])) < NAISSANCE:
            efface += cx.execute(
                "DELETE FROM evenements WHERE type = 'mort' AND monde IS ? "
                "AND joueur = ? AND horodatage = ?", (monde, joueur, ts)).rowcount
    if efface:
        cx.commit()
    return efface


def enregistre_vies(cx):
    """Inscrit chaque personnage avec ses bornes, pour que les compteurs
    puissent repartir de zero au personnage suivant.

    Le debut vient de comptes_par_pseudo -- la premiere apparition du
    personnage, rapportee au compte Steam par la sequence connexion/apparition.
    La fin est la derniere trace de ce personnage dans le journal, quelle qu'en
    soit la nature : elle sert a raconter les vies passees, pas a decider
    laquelle est en cours. Le personnage en cours, c'est celui dont le DEBUT
    est le plus recent -- pas celui dont la fin est la plus tardive. La nuance
    compte : un joueur peut mourir sur un personnage neuf, donc y laisser une
    trace, et une trace tardive sur un ancien nom ne doit pas le ressusciter.

    Rien n'est efface, jamais : une vie inscrite le reste. Un personnage qu'on
    reprend plus tard voit seulement sa borne de fin avancer.
    """
    comptes = comptes_par_pseudo(cx)
    fins = {}
    for monde, joueur, ts in cx.execute(
            "SELECT monde, joueur, max(horodatage) FROM evenements "
            "WHERE joueur IS NOT NULL GROUP BY monde, joueur"):
        fins[(monde, joueur)] = ts
    for (monde, joueur), (sid, debut) in comptes.items():
        cx.execute(
            "INSERT INTO vies (monde, steamid, pseudo, debut, fin) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (monde, steamid, pseudo) DO UPDATE SET "
            "debut = min(debut, excluded.debut), fin = max(fin, excluded.fin)",
            (monde or "", sid, joueur, debut, fins.get((monde, joueur), debut)))
    cx.commit()
    return cx.execute("SELECT count(*) FROM vies").fetchone()[0]


# RETIREE le 2026-09-10 : purge_morts_abandonnees().
#
# Elle effacait les morts d'un personnage abandonne pour un neuf dans les dix
# minutes. Regle decidee par le groupe le 2026-09-09, quand Baby est morte sur
# un personnage cree onze minutes plus tot et a repris un autre aussitot : les
# morts d'un personnage qui n'existe plus ne disaient rien du joueur du jour.
#
# Le besoin etait reel, la methode trop chere. Depuis que les compteurs se
# cloisonnent par personnage -- table « vies » ici, par_joueur() dans
# stats-valheim.py -- une mort subie par un personnage retire ne pese deja plus
# sur le personnage en cours, sans qu'il faille la supprimer. La supprimer, en
# plus, la retirait de l'histoire du compte, du cumul du groupe et du KPI des
# morts cumulees : le 2026-09-10 la mort d'Alexandre, absent du clavier, a
# disparu de partout alors que seul son nouveau personnage devait l'ignorer.
#
# Elle rendait aussi les defis truquables : « intact depuis Eikthyr » se
# gagnait en mourant puis en refaisant son personnage dans les dix minutes.
#
# Retrait demande par Alexandre. Consequence assumee : les morts que la regle
# effacait reviennent en base au prochain rejeu du journal, dans la limite de
# ce que le journal garde encore. Celles qui en sont sorties sont perdues.


def enregistre(cx, monde, lot):
    """Insere un lot. « monde » peut etre un nom, ou une liste parallele au lot.

    La liste sert au rattrapage, qui rejoue un journal traversant plusieurs
    mondes : chaque ligne doit porter le monde charge a ce moment-la, et non
    celui d'aujourd'hui.
    """
    avant = cx.execute("SELECT count(*) FROM evenements").fetchone()[0]
    if isinstance(monde, (list, tuple)):
        mondes = list(monde)
    else:
        mondes = [monde] * len(lot)
    cx.executemany(
        "INSERT OR IGNORE INTO evenements "
        "(horodatage, monde, type, joueur, steamid, detail, rang) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(ts, m, typ, j, sid, d, rang_de(ts, typ, j, sid, d))
         for (ts, typ, j, sid, d), m in zip(lot, mondes)],
    )
    cx.commit()
    return cx.execute("SELECT count(*) FROM evenements").fetchone()[0] - avant


def rattrapage(cx, depuis):
    """Rejoue le journal, en suivant les changements de monde qu'il annonce.

    Etiqueter tout le lot avec le monde du jour etait faux, et le silence de
    cette faute est instructif : tant qu'un motif existait deja, l'index unique
    ecartait les doublons et les originaux gardaient leur bon monde. Mais le
    jour ou l'on AJOUTE un motif -- les donjons, le 2026-09-09 -- tout
    l'historique s'inserait sous le monde courant. 149 entrees de donjon de
    Midgard se sont ainsi retrouvees attribuees a NordheimV1, cree le meme jour
    a 15h19.

    Les lignes qui precedent le premier « Load world » du journal recoivent ce
    premier monde : un journal commence toujours par un demarrage de serveur,
    et l'attribution la plus probable est celle du monde qu'il ouvre.
    """
    monde = monde_courant()
    cmd = ["journalctl", "-u", "valheim", "-o", "cat", "--no-pager"]
    if depuis:
        cmd += ["--since", depuis]
    sortie = subprocess.run(cmd, capture_output=True, text=True, errors="replace")

    lot, mondes = [], []
    courant = None
    for ligne in sortie.stdout.splitlines():
        m = PREFIXE.match(ligne.rstrip())
        if m:
            c = CHARGE_MONDE.match(m.group(7))
            if c:
                courant = c.group(1)
                continue
        for e in analyse(ligne):
            lot.append(e)
            mondes.append(courant)
    # Les lignes d'avant le premier « Load world » heritent de celui-ci.
    premier = next((m for m in mondes if m), monde)
    mondes = [m or premier for m in mondes]

    lot, mondes = morts_de_naissance(cx, lot, mondes)
    releve_monde(cx, monde)
    nb = enregistre(cx, mondes, lot)
    # Apres coup seulement : rattacher les pseudos, reconnaitre les creations
    # de personnage et recenser les vies demande de connaitre toute
    # l'histoire, y compris ce que ce lot vient d'ajouter.
    relie_pseudos(cx)
    nees = purge_morts_de_naissance(cx)
    if nees:
        print("%d mort(s) effacee(s) : creation de personnage" % nees)
    print("%d personnage(s) recense(s)" % enregistre_vies(cx))
    return len(lot), nb


def suit(cx):
    monde = monde_courant()
    p = subprocess.Popen(
        ["journalctl", "-u", "valheim", "-o", "cat", "-f", "-n", "0"],
        stdout=subprocess.PIPE, text=True, errors="replace", bufsize=1,
    )
    for ligne in p.stdout:
        for e in analyse(ligne):
            # Un changement de monde (9 septembre : nouveau monde 1.0) doit
            # etre vu sans redemarrer le collecteur, sinon les evenements du
            # monde neuf seraient etiquetes avec l'ancien nom.
            if e[1] == "connexion":
                neuf = monde_courant()
                if neuf and neuf != monde:
                    monde = neuf
                    releve_monde(cx, monde)
            # Meme filtre qu'au rattrapage, mais sur un seul evenement : la
            # premiere apparition du personnage est deja en base a cet instant,
            # puisqu'elle precede la fausse mort de quelques secondes.
            e_lot, _m = morts_de_naissance(cx, [e], [monde])
            if not e_lot:
                sys.stdout.write("%s mort ecartee (creation de perso) %s\n"
                                 % (e[0], e[2] or ""))
                sys.stdout.flush()
                continue
            enregistre(cx, monde, [e])
            if e[1] in ("connexion", "apparition"):
                relie_pseudos(cx)
                enregistre_vies(cx)
            sys.stdout.write("%s %s %s\n" % (e[0], e[1], e[2] or e[3] or e[4] or ""))
            sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rattrapage-seul", action="store_true",
                    help="relit le journal et sort, sans suivre")
    ap.add_argument("--depuis", default=None,
                    help="date de depart du rattrapage (defaut : tout le journal)")
    a = ap.parse_args()

    cx = ouvre()
    lus, neufs = rattrapage(cx, a.depuis)
    relie_pseudos(cx)
    print("rattrapage : %d evenements reconnus, %d nouveaux" % (lus, neufs))
    if a.rattrapage_seul:
        return
    suit(cx)


if __name__ == "__main__":
    main()
