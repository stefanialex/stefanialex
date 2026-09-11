#!/usr/bin/env python3
"""Prevision meteo de Valheim, biome par biome.

La meteo de Valheim est **entierement determinee par le temps ecoule du monde**.
Elle ne depend ni de la seed ni du monde : la meme sequence se deroule partout,
et elle est donc previsible aussi loin qu'on veut.

Le mecanisme, etabli le 2026-09-09 :

    periode = temps_total_du_monde / 666        (secondes, division entiere)
    Random.InitState(periode)                   generateur d'Unity
    environnement = tirage pondere dans la table du biome

Soit un changement toutes les 666 secondes de TEMPS DE MONDE. Et c'est la que
se trouve la difficulte, decouverte le 2026-09-09 apres l'avoir d'abord niee :

    le temps de monde n'avance PAS a la vitesse du temps reel.

Mesure sur NordheimV1, sur cinq points du journal : le rapport vaut 1,30 puis
1,09 puis 1,29 puis 0,67 selon les intervalles. Le journal affiche un champ
« skipspeed » de 25 a 45 -- le serveur accelere la nuit quand personne n'est
connecte, et le temps parait se figer quand le serveur est vide.

Consequence a assumer : convertir une periode en heure de montre n'est pas
fiable. Une premiere version annoncait un changement a 20h13 en extrapolant
depuis une reference de deux heures ; la reference fraiche donnait 20h00. Ce
qui reste exact, c'est la SEQUENCE : quel temps a quelle periode, et dans quel
ordre. Les heures affichees sont donnees a titre indicatif et le programme dit
sur quelle reference il s'appuie et de quand elle date.

Corollaire pratique : lire le fichier de monde VIVANT, dont la fraicheur est
d'au plus un intervalle de sauvegarde. Une archive de deux heures ne vaut rien
pour l'heure, meme si elle vaut toujours pour la sequence.

Deux choses sont sures et une reste a calibrer.

PAS SUR, ET C'ETAIT PRESENTE COMME SUR : que la periode se calcule sur le
temps ecoule DU MONDE. Les sources disent « la meteo evolue de la meme facon
dans tous les mondes », ce qui peut vouloir dire deux choses -- que la sequence
est commune et parcourue selon le temps de chaque monde, ou que tous les mondes
montrent le meme ciel au meme instant reel. J'ai retenu la premiere sans la
tester, et la seconde expliquerait la refutation du 2026-09-09 mieux que ma
theorie d'un generateur defaillant. Test prevu : charger deux mondes d'ages
differents et comparer leur ciel a la meme minute. Voir observations.json.

SUR : les tables par biome, reconstituees a partir des pourcentages publies.
Les poids entiers les reproduisent exactement -- Prairies 25/1/1/1/1 donne bien
86,2 % et 3,4 %, Ashlands 30/4/2/1 donne 81,1 / 10,8 / 5,4 / 2,7.

A CALIBRER : la formule exacte de « Random.value » d'Unity. Le generateur est
un xorshift128 dont l'amorce est documentee, mais la conversion du dernier mot
en flottant a plusieurs variantes publiees. Elles donnent des tirages
differents, donc des noms de temps differents. D'ou l'option --variante et le
mode --calibrer : on affiche ce que chaque variante predit, quelqu'un regarde
en jeu, et on fixe la bonne une fois pour toutes.

Tant que la calibration n'est pas faite, ce programme annonce l'heure des
changements avec certitude et le temps qu'il fera avec un doute -- et il le
dit.

Usage :
    meteo-valheim.py --monde /var/lib/valheim/donnees/worlds_local/NordheimV1
    meteo-valheim.py --temps 565305 --heures 3
    meteo-valheim.py --monde <dossier> --calibrer
"""

import argparse
import glob
import json
import os
import struct
import sys
from datetime import datetime, timedelta

DUREE = 666.0          # m_environmentDuration, en secondes de temps de monde

# Ce programme est appelable par lapserv sous le compte valheim, via une regle
# sudoers. Cette regle l'autorise avec n'importe quels arguments, parce que
# borner un chemin par des jokers dans un fichier sudoers marche mal -- « * » y
# traverse les « / », donc « .../worlds_local/../../../etc/shadow » passerait.
# La limite est donc posee ici, ou elle peut etre exacte : le chemin demande
# doit se resoudre a l'interieur du dossier des mondes. Le programme n'ecrit
# rien et n'imprime que des noms de temps et des horaires.
RACINE_AUTORISEE = "/var/lib/valheim/donnees/worlds_local"

# Poids entiers reconstituees depuis les pourcentages publies. Le nom entre
# parentheses est celui qu'affiche la console du jeu (« env <nom> »), pour
# qu'on puisse verifier a la main.
# Les tables, LUES DANS LE JEU le 2026-09-10, et non plus reprises d'une source
# exterieure. Elles viennent du bundle
# valheim_server_Data/StreamingAssets/SoftRef/Bundles/d59cfac, un UnityFS
# compresse en LZ4 : la liste « m_biomes » de EnvMan y donne, pour chaque
# biome, ses couples (nom d'environnement, poids) DANS L'ORDRE. Le meme bloc
# figure deux fois dans le fichier, a l'identique -- deux scenes, une seule
# verite.
#
# Ce que la lecture a change, et ce n'est pas cosmetique : les POIDS etaient
# justes, ils avaient ete verifies au pourcentage pres. Mais l'ORDRE etait faux
# dans quatre biomes sur six, et c'est l'ordre qui decide dans quelle bande
# tombe un tirage, donc quel temps il donne.
#
#   Prairies      Pluie et Brouillard etaient permutes avec Orage et Pluie fine
#   Foret Noire   Pluie et Brouillard permutes
#   Montagnes     ORDRE RENVERSE. Le blizzard occupe le BAS de la plage, pas le
#                 haut : une observation de blizzard disait donc l'exact
#                 contraire de ce qu'on en tirait.
#   Ocean         « Clear » est le QUATRIEME et non le premier. Un ciel degage
#                 en mer contraint le tirage des DEUX cotes, entre 0,214 et
#                 0,929 : c'est devenu l'observation la plus utile du jeu.
#   Plaines       seul biome ou l'ordre suppose etait le bon.
#
# Les noms sont ceux du jeu, NOMS les traduit pour l'affichage. « DeepForest
# Mist » est le temps ordinaire de la Foret Noire, celui que les joueurs
# decrivent comme du beau temps.
TABLES = {
    "Prairies":     [("Clear", 5.0), ("Rain", 0.2), ("Misty", 0.2),
                     ("ThunderStorm", 0.2), ("LightRain", 0.2)],
    "Forêt Noire":  [("DeepForest Mist", 2.0), ("Rain", 0.1), ("Misty", 0.1),
                     ("ThunderStorm", 0.1)],
    "Marais":       [("SwampRain", 1.0)],
    "Montagnes":    [("SnowStorm", 1.0), ("Snow", 5.0)],
    "Plaines":      [("Heath clear", 2.0), ("Misty", 0.4), ("LightRain", 0.4)],
    "Océan":        [("Rain", 0.1), ("LightRain", 0.1), ("Misty", 0.1),
                     ("Clear", 1.0), ("ThunderStorm", 0.1)],
}

# Ces trois-la ont bien une table, CONTRAIREMENT A CE QUE J'AI ECRIT LE
# 2026-09-10. Je n'avais parcouru que la liste contigue de EnvMan -- six
# biomes -- et conclu du haut de cette fenetre qu'Ashlands, Grand Nord et
# Mistlands n'en avaient pas. Leurs BiomeEnvSetup sont ailleurs dans le meme
# bundle, a 2 703 120, 2 777 884 et 5 788 044, avec la meme signature : le nom
# du biome, son drapeau, puis les couples (environnement, poids). Verifie le
# 2026-09-11 : ils y etaient DEJA dans le bundle de la veille, la mise a jour
# 1.0.12 n'y est pour rien.
#
# Comme pour les six autres, les poids repris de la source exterieure etaient
# justes et l'ordre faux : en Ashlands, « brouillard » et « pluie de braises »
# etaient permutes ; au Grand Nord, le blizzard occupe le BAS de la plage, pas
# le haut. Seules les Mistlands etaient dans le bon ordre.
TABLES.update({
    "Grand Nord":  [("Twilight_SnowStorm", 0.5), ("Twilight_Snow", 1.0),
                    ("Twilight_Clear", 1.0)],
    "Ashlands":    [("Ashlands_ashrain", 1.5), ("Ashlands_misty", 0.1),
                    ("Ashlands_CinderRain", 0.2), ("Ashlands_storm", 0.05)],
    "Mistlands":   [("Mistlands_clear", 1.5), ("Mistlands_rain", 0.1),
                    ("Mistlands_thunder", 0.1)],
})

# L'Ocean a une seconde table, pour les eaux des Ashlands : une entree
# « Ashlands_SeaStorm » de poids 0,05 portant le drapeau m_ashlandsOverride.
# C'est le PREMIER drapeau non nul trouve dans tout le jeu, et il valide la
# lecture : SelectWeightedEnvironment exclut du total et du parcours toute
# entree ainsi marquee, donc cette tempete n'existe que dans les eaux des
# Ashlands. Elle n'est pas ajoutee ici : le programme ne sait pas ou se tient
# le joueur, et l'annoncer partout serait faux.
OCEAN_ASHLANDS = [("Ashlands_SeaStorm", 0.05)]

NOMS = {
    "Clear": "Dégagé", "Rain": "Pluie", "Misty": "Brouillard",
    "ThunderStorm": "Orage", "LightRain": "Pluie fine",
    "SwampRain": "Pluie", "SnowStorm": "Blizzard", "Snow": "Neige",
    "DeepForest Mist": "Brume de forêt", "Heath clear": "Dégagé",
    "Twilight_SnowStorm": "Blizzard", "Twilight_Snow": "Neige",
    "Twilight_Clear": "Dégagé", "Ashlands_ashrain": "Pluie de cendres",
    "Ashlands_misty": "Brouillard", "Ashlands_CinderRain": "Pluie de braises",
    "Ashlands_storm": "Orage", "Ashlands_SeaStorm": "Tempête",
    "Mistlands_clear": "Dégagé", "Mistlands_rain": "Pluie",
    "Mistlands_thunder": "Orage",
}
# Le Marais pleut toujours et les Mistlands sont toujours sombres : le jeu y
# force l'environnement tant qu'un joueur s'y trouve. Les annoncer serait du
# bruit.
CONSTANTS = {"Marais": "Pluie, toujours"}


class HasardUnity:
    """xorshift128 d'Unity, amorce comme UnityEngine.Random.InitState().

    L'amorce et le pas sont documentes et concordants d'une source a l'autre.
    C'est la conversion du dernier mot en flottant qui varie, d'ou les trois
    variantes ci-dessous -- c'est exactement ce que --calibrer sert a trancher.
    """

    def __init__(self, graine, variante=1):
        self.x = graine & 0xFFFFFFFF
        self.y = (self.x * 1812433253 + 1) & 0xFFFFFFFF
        self.z = (self.y * 1812433253 + 1) & 0xFFFFFFFF
        self.w = (self.z * 1812433253 + 1) & 0xFFFFFFFF
        self.variante = variante

    def _mot(self):
        t = (self.x ^ (self.x << 11)) & 0xFFFFFFFF
        self.x, self.y, self.z = self.y, self.z, self.w
        self.w = (self.w ^ (self.w >> 19) ^ t ^ (t >> 8)) & 0xFFFFFFFF
        return self.w

    def valeur(self):
        m = self._mot()
        if self.variante == 1:
            # Reinterpretation IEEE754 : mantisse dans [1,2) puis -1.
            brut = (m >> 9) | 0x3F800000
            return struct.unpack("<f", struct.pack("<I", brut))[0] - 1.0
        if self.variante == 2:
            return (m & 0x7FFFFF) / float(0x800000)
        return m / 4294967296.0


def environnement(biome, periode, variante=1):
    table = TABLES[biome]
    total = float(sum(p for _n, p in table))
    tirage = HasardUnity(periode, variante).valeur() * total
    cumul = 0.0
    for nom, poids in table:
        cumul += poids
        if tirage <= cumul:
            return NOMS.get(nom, nom)
    return NOMS.get(table[0][0], table[0][0])


def temps_du_monde(dossier):
    """Le temps ecoule du monde, et l'instant ou il a ete mesure.

    Il est ecrit dans l'en-tete du fichier de contenu : version en int32 puis
    ce temps en double. Vrai pour les deux formats -- l'ancien « .db » comme le
    « .db2 » compresse de la 1.0, dont seul le corps est en gzip.

    L'instant de reference est la date du fichier : le temps de monde avance a
    la meme vitesse que le temps reel, donc on extrapole sans erreur.
    """
    chemin = None
    if os.path.isdir(dossier):
        cands = glob.glob(os.path.join(dossier, "_main.*.db2"))
        if cands:
            def rang(f):
                try:
                    return int(os.path.basename(f).split(".")[1])
                except (IndexError, ValueError):
                    return -1
            chemin = max(cands, key=rang)
    elif os.path.exists(dossier):
        chemin = dossier
    if not chemin:
        return None, None
    with open(chemin, "rb") as f:
        tete = f.read(16)
    temps, = struct.unpack_from("<d", tete, 4)
    return temps, datetime.fromtimestamp(os.path.getmtime(chemin))


def previsions(temps, mesure_a, heures, variante=1):
    """Les periodes a venir, avec leur instant de debut en heure locale."""
    maintenant = datetime.now()
    ecoule = (maintenant - mesure_a).total_seconds()
    actuel = temps + max(0.0, ecoule)
    debut = int(actuel // DUREE)
    reste = DUREE - (actuel - debut * DUREE)

    sortie = []
    for i in range(int(heures * 3600 / DUREE) + 1):
        periode = debut + i
        quand = maintenant + timedelta(seconds=(reste + (i - 1) * DUREE) if i else 0)
        sortie.append({
            "periode": periode,
            "debut": quand.strftime("%H:%M:%S"),
            "en_cours": i == 0,
            "biomes": {b: (CONSTANTS[b] if b in CONSTANTS
                           else environnement(b, periode, variante))
                       for b in TABLES},
        })
    return sortie


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--monde", help="dossier du monde, ou fichier .db/.db2")
    ap.add_argument("--temps", type=float, help="temps de monde en secondes")
    ap.add_argument("--heures", type=float, default=2.0)
    ap.add_argument("--variante", type=int, default=1, choices=(1, 2, 3))
    ap.add_argument("--calibrer", action="store_true",
                    help="montre ce que chaque variante predit, pour trancher")
    ap.add_argument("--json", action="store_true")
    o = ap.parse_args()

    if o.temps is not None:
        temps, mesure = o.temps, datetime.now()
    elif o.monde:
        vrai = os.path.realpath(o.monde)
        racine = os.path.realpath(RACINE_AUTORISEE)
        # Autorise aussi hors racine quand on n'est pas passe par sudo : lire
        # une archive extraite pour verifier une sequence est legitime, et sans
        # privilege il n'y a rien a proteger.
        if os.environ.get("SUDO_USER") and not (
                vrai == racine or vrai.startswith(racine + os.sep)):
            sys.exit("sous sudo, --monde doit rester dans %s" % RACINE_AUTORISEE)
        temps, mesure = temps_du_monde(o.monde)
        if temps is None:
            sys.exit("aucun fichier de monde lisible dans %s" % o.monde)
    else:
        sys.exit("il faut --monde ou --temps")

    if o.calibrer:
        p = int((temps + (datetime.now() - mesure).total_seconds()) // DUREE)
        print("periode en cours : %d" % p)
        print("Regarde en jeu, puis retiens la variante qui correspond.\n")
        for v in (1, 2, 3):
            print("--- variante %d ---" % v)
            for b in ("Prairies", "Forêt Noire", "Montagnes", "Plaines", "Océan"):
                print("  %-14s %s" % (b, environnement(b, p, v)))
            print()
        return 0

    prev = previsions(temps, mesure, o.heures, o.variante)
    if o.json:
        print(json.dumps({"temps_monde": round(temps, 1),
                          "variante": o.variante, "previsions": prev},
                         ensure_ascii=False, indent=1))
        return 0

    actuel = temps + max(0.0, (datetime.now() - mesure).total_seconds())
    print("temps du monde %.0f s (mesure %.0f s a %s) · periode %d · "
          "changement toutes les 11 min 06 s"
          % (actuel, temps, mesure.strftime("%H:%M"), prev[0]["periode"]))
    age = (datetime.now() - mesure).total_seconds() / 60.0
    print("reference : %s, il y a %.0f min. Les heures sont INDICATIVES -- le "
          "temps du monde n'avance pas a la vitesse du temps reel (le serveur "
          "accelere la nuit quand il est vide). La sequence, elle, est exacte."
          % (mesure.strftime("%H:%M:%S"), age))
    print("noms selon la variante %d, non encore calibree\n" % o.variante)
    biomes = [b for b in TABLES if b not in CONSTANTS]
    print("%-9s " % "" + " ".join("%-16s" % b for b in biomes))
    for p in prev:
        marque = "▶" if p["en_cours"] else " "
        print("%s %-7s " % (marque, p["debut"][:5])
              + " ".join("%-16s" % p["biomes"][b] for b in biomes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
