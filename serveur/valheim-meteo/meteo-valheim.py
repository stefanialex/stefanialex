#!/usr/bin/env python3
"""Prevision meteo de Valheim, biome par biome.

La meteo de Valheim est **entierement determinee par le temps ecoule du monde**.
Elle ne depend ni de la seed ni du monde : la meme sequence se deroule partout,
et elle est donc previsible aussi loin qu'on veut.

Le mecanisme, etabli le 2026-09-09 :

    periode = temps_total_du_monde / 666        (secondes, division entiere)
    Random.InitState(periode)                   generateur d'Unity
    environnement = tirage pondere dans la table du biome

Soit un changement toutes les 666 secondes de temps de monde -- et le temps de
monde avance a la meme vitesse que le temps reel, donc toutes les 11 min 06 s
de vraie vie.

Deux choses sont sures et une reste a calibrer.

SUR : la periode de 666 secondes et l'instant des changements. Ils ne dependent
que de l'arithmetique, donc les heures de bascule annoncees par ce programme
sont exactes meme si le nom du temps est faux.

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

# Poids entiers reconstituees depuis les pourcentages publies. Le nom entre
# parentheses est celui qu'affiche la console du jeu (« env <nom> »), pour
# qu'on puisse verifier a la main.
TABLES = {
    "Prairies":     [("Dégagé", 25), ("Brouillard", 1), ("Pluie fine", 1),
                     ("Pluie", 1), ("Orage", 1)],
    "Forêt Noire":  [("Dégagé", 20), ("Brouillard", 1), ("Pluie", 1), ("Orage", 1)],
    "Marais":       [("Pluie", 1)],
    "Montagnes":    [("Neige", 5), ("Blizzard", 1)],
    "Plaines":      [("Dégagé", 5), ("Brouillard", 1), ("Pluie fine", 1)],
    "Mistlands":    [("Dégagé", 15), ("Pluie", 1), ("Orage", 1)],
    "Océan":        [("Dégagé", 10), ("Brouillard", 1), ("Pluie fine", 1),
                     ("Pluie", 1), ("Orage", 1)],
    "Ashlands":     [("Pluie de cendres", 30), ("Pluie de braises", 4),
                     ("Brouillard", 2), ("Orage", 1)],
    "Grand Nord":   [("Neige", 2), ("Blizzard", 1), ("Dégagé", 1)],
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
            return nom
    return table[0][0]


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
    print("(les heures sont sures ; les noms dependent de la variante %d, non "
          "encore calibree)\n" % o.variante)
    biomes = [b for b in TABLES if b not in CONSTANTS]
    print("%-9s " % "" + " ".join("%-16s" % b for b in biomes))
    for p in prev:
        marque = "▶" if p["en_cours"] else " "
        print("%s %-7s " % (marque, p["debut"][:5])
              + " ".join("%-16s" % p["biomes"][b] for b in biomes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
