#!/usr/bin/env python3
"""Publie le bilan KPI du serveur Valheim sur Discord.

Complement de notifie-discord-valheim.py, qui poste les evenements au fil de
l'eau : celui-ci envoie une synthese, une fois par jour. Il ne calcule rien
lui-meme et appelle stats-valheim.py --json, pour qu'il n'existe qu'une seule
definition de chaque indicateur.
"""

import datetime
import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request

CONF = "/etc/valheim-discord.conf"
STATS = "/usr/local/bin/stats-valheim.py"
CONSEILS = "/etc/valheim/conseils.json"
BASE = "/var/lib/valheim-stats/valheim.db"
# Discord passe par Cloudflare, qui refuse l'agent par defaut de Python.
AGENT = "valheim-serveur/1.0 (bilan quotidien auto-heberge)"


def config():
    try:
        with open(CONF) as f:
            for l in f:
                if l.startswith("WEBHOOK="):
                    return l.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def duree(s):
    s = int(s or 0)
    if s < 3600:
        return "%d min" % (s // 60)
    return "%d h %02d" % (s // 3600, (s % 3600) // 60)


# Les boss dans l'ordre : le prochain a abattre determine l'etape, donc les
# conseils du jour.
ORDRE_BOSS = ["defeated_eikthyr", "defeated_gdking", "defeated_bonemass",
              "defeated_dragon", "defeated_goblinking", "defeated_queen",
              "defeated_fader"]


def point_du_soir(d):
    """Le point meteo : ou en est le groupe, et un conseil du jour.

    Le conseil tourne de facon deterministe sur la date plutot que d'etre tire
    au sort : chacun revient a intervalle regulier, aucun n'est oublie, et deux
    jours de suite ne se ressemblent pas.
    """
    try:
        with open(CONSEILS, encoding="utf-8") as f:
            conf = json.load(f)
    except (OSError, ValueError):
        return None

    vaincus = {e.get("cle") for e in (d.get("progression") or [])}
    prochain = next((c for c in ORDRE_BOSS if c not in vaincus), None)
    etape = (conf.get("etapes") or {}).get(prochain)
    if not etape:
        return None

    # Le vivier melange la preparation de l'etape, ses conseils propres et les
    # conseils generaux : la preparation revient ainsi regulierement sans
    # occuper le message tous les soirs.
    vivier = [etape["preparer"]] + etape.get("conseils", []) + conf.get("generaux", [])
    jour = datetime.date.today().toordinal()
    conseil = vivier[jour % len(vivier)]

    return {"name": "🌤️  Prochaine étape — %s" % etape["biome"], "inline": False,
            "value": "%s\n\n💡  %s" % (etape["objectif"], conseil)}


def succes_du_jour():
    """Une ligne sur les succes Steam, seulement s'il y en a."""
    try:
        cx = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
        lignes = list(cx.execute(
            "SELECT j.pseudo, count(s.cle) FROM joueurs j "
            "LEFT JOIN steam_succes s ON s.steamid = j.steamid "
            "GROUP BY j.steamid ORDER BY count(s.cle) DESC"))
    except sqlite3.Error:
        return None
    if not lignes or not any(n for _, n in lignes):
        return None
    return " · ".join("%s **%d**" % (p, n) for p, n in lignes if n)


METEO = "/usr/local/bin/meteo-valheim.py"
MONDES = "/var/lib/valheim/donnees/worlds_local"
# Le temps par defaut de chaque biome : celui qui sort dans la grande majorite
# des periodes. On n'annonce que ce qui s'en ecarte -- annoncer « degage » huit
# fois sur dix serait du bruit.
BANAL = {"Prairies": "Dégagé", "Forêt Noire": "Dégagé", "Plaines": "Dégagé",
         "Mistlands": "Dégagé", "Océan": "Dégagé", "Montagnes": "Neige",
         "Ashlands": "Pluie de cendres", "Grand Nord": "Neige"}


METEO_VALIDEE = False


def champ_meteo(d):
    """Le bulletin : ce qu'il fait, puis ce qui sort de l'ordinaire ensuite.

    Les heures ne sont volontairement pas affichees. Le temps de Valheim change
    toutes les 666 secondes de TEMPS DE MONDE, et le temps de monde n'avance
    pas a la vitesse du temps reel : le serveur accelere la nuit quand il est
    vide. Annoncer « brouillard a 20h13 » serait faux d'une dizaine de minutes,
    comme constate le 2026-09-09. La sequence, elle, est exacte.
    """
    # Coupe tant que la prevision n'est pas validee. Le 2026-09-09 a 19h02, le
    # modele annoncait « degage » dans les Prairies pour les periodes 22, 23 et
    # 24, sous chacune de ses trois variantes de generateur -- Alexandre y
    # voyait de la pluie. Ce n'est pas un desaccord de detail : le generateur ne
    # reproduit pas celui d'Unity. Le chiffre qui le prouve : a la periode 23 le
    # tirage vaut 0,857 sur 29, et un tirage aussi bas selectionne forcement la
    # PREMIERE entree de la liste du biome ; pour que ce soit la pluie, il
    # faudrait qu'elle soit en tete d'une liste ou elle ne pese que 3 %. Aucun
    # reordonnancement ne sauve le modele.
    #
    # Un bulletin faux publie a quatre personnes est pire que pas de bulletin :
    # elles partiraient en mer sur une prevision de temps clair. On rallumera
    # quand des observations auront permis de retrouver le vrai generateur --
    # chaque couple (periode, biome, temps observe) le contraint.
    if not METEO_VALIDEE:
        return None
    monde = d.get("monde")
    if not monde:
        return None
    try:
        r = subprocess.run([METEO, "--monde", os.path.join(MONDES, monde),
                            "--heures", "2", "--json"],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return None
        prev = json.loads(r.stdout)["previsions"]
    except (OSError, ValueError, subprocess.SubprocessError, KeyError):
        return None
    if not prev:
        return None

    maintenant = prev[0]["biomes"]
    lignes = ["**Maintenant** — " + " · ".join(
        "%s %s" % (b, t.lower()) for b, t in maintenant.items()
        if b != "Marais" and t != BANAL.get(b))
        or "**Maintenant** — rien de notable, temps ordinaire partout"]

    # Groupe par periode : un ciel qui se couvre partout a la fois donnait six
    # fois « dans 3 periodes », ce qui se lit mal.
    a_venir = []
    for i, p in enumerate(prev[1:], start=1):
        notables = ["**%s** sur %s" % (t.lower(), b)
                    for b, t in p["biomes"].items()
                    if b != "Marais" and t != BANAL.get(b)]
        if notables:
            a_venir.append("dans %d période%s — %s"
                           % (i, "s" if i > 1 else "", ", ".join(notables)))
    if a_venir:
        lignes.append("**Ensuite** — " + "\n".join(a_venir[:4]))
    lignes.append("_Une période dure 666 s de temps de monde ; le serveur "
                  "l'accélère quand il est vide, donc pas d'heure fixe._")
    return {"name": "🌦️  Météo", "value": "\n".join(lignes)[:1024], "inline": False}


def champs_roles(d):
    """Les roles confrontes a la mesure, plus les raids par joueur.

    Deux chiffres pour chaque joueur : le brut et le rapport a l'heure de jeu.
    Le brut seul mesurerait la presence et non le travail -- Bab-y finissait
    derniere de tout avec trois fois moins d'heures que Beny, alors qu'a
    l'heure elle explore autant que Djoose.
    """
    r = d.get("roles") or {}
    champs = []

    for x in r.get("roles") or []:
        if not x.get("mesure") or not x.get("classement"):
            continue
        lignes = []
        for c in x["classement"][:4]:
            ph = c.get("par_heure")
            lignes.append("`%-14s` **%s** %s%s" % (
                c["joueur"], c["valeur"], x["mesure"],
                "  ·  %s/h" % ph if ph is not None else ""))
        marque = {True: " ✅", False: " ❌", None: ""}[x.get("titulaire_en_tete")]
        titre = "🎭  %s — %s%s" % (x["role"], ", ".join(x["titulaires"]), marque)
        valeur = "\n".join(lignes)
        if x.get("pseudos_inconnus"):
            # Sans le bon pseudo on ne peut pas dire si le titulaire tient son
            # role : on le dit, avec la commande qui repare.
            valeur += ("\n_Verdict impossible : le personnage `%s` n'a pas joué "
                       "sur ce monde. `!pseudo <joueur> <nom en jeu>` pour "
                       "corriger._" % "`, `".join(x["pseudos_inconnus"]))
        champs.append({"name": titre, "value": valeur, "inline": False})

    joueurs = (r.get("presence") or {}).get("joueurs") or {}
    duels = sorted(((p, e) for p, e in joueurs.items() if e.get("raids_vus")),
                   key=lambda kv: -(kv[1].get("raids_taux") or 0))
    if duels:
        champs.append({"name": "⚔️  Raids tenus, par joueur", "inline": False,
                       "value": "  ·  ".join(
                           "`%s` **%d %%** (%d/%d)" % (p, e["raids_taux"],
                                                       e["raids_tenus"], e["raids_vus"])
                           for p, e in duels)})
    return champs


VERT = 0x3D7317


def champ_autels(d):
    """Les lieux d'invocation reperes, chasse ouverte d'abord.

    C'est le champ qui manquait : le serveur savait depuis 02h36 que l'autel de
    l'Ancien etait localise, et le bilan du matin n'en disait rien. Un autel
    repere annonce la chasse plusieurs heures avant la mise a mort -- Bonemass
    deux jours, Moder trois heures.
    """
    au = d.get("autels") or []
    ouvertes = [e for e in au if not e["vaincu"]]
    if not ouvertes:
        return None
    lignes = []
    for e in ouvertes:
        lignes.append("**%s** — repéré le %s à %s%s" % (
            e["boss"], e["premiere"][8:10] + "/" + e["premiere"][5:7],
            e["premiere"][11:16],
            "" if e["connu"] else "  _(lieu non identifié)_"))
    return {"name": "🗿  Autels repérés — la chasse est ouverte", "inline": False,
            "value": "\n".join(lignes)[:1024]}


def champ_terrain(d):
    """Le terrain decouvert et les donjons ouverts, deux mesures jamais publiees."""
    ex = d.get("exploration") or {}
    dj = d.get("donjons") or {}
    lignes = []
    if ex.get("zones"):
        recent = ex.get("zones_24h") or 0
        lignes.append("**%d** zones découvertes%s" % (
            ex["zones"], "  ·  dont **%d** sur 24 h" % recent if recent else ""))
    for e in (dj.get("types") or [])[:6]:
        nom = e["nom_pluriel"] if e["entrees"] > 1 else e["nom"]
        lignes.append("`%3d` %s%s" % (e["entrees"], nom,
                                      "" if e["connu"] else "  _(type inconnu)_"))
    if not lignes:
        return None
    return {"name": "🧭  Terrain", "inline": False, "value": "\n".join(lignes)[:1024]}


def bilan(d):
    """Construit l'embed du bilan.

    Un embed plutot qu'un pave monospace : Discord aligne les colonnes
    lui-meme, et le message reste lisible sur telephone -- ce que ne faisait
    pas un tableau a chasse fixe de soixante-dix colonnes.

    Le contenu est aussi degraisse : les jauges en croix, les doublons entre
    objectifs et defis, et les classements qui repetaient la meme information
    ont disparu. Un bilan quotidien doit se lire en dix secondes.
    """
    tete = []
    if d.get("monde"):
        tete.append("**%s**" % d["monde"])
    if d.get("jour"):
        tete.append("jour %s" % d["jour"])
    if d.get("zdos"):
        tete.append("%s objets" % format(int(d["zdos"]), ",d").replace(",", " "))

    # Classement : trois colonnes que Discord aligne seul.
    series = {}
    for defi in d.get("defis") or []:
        if defi.get("nom") == "Série en cours":
            series = {x["joueur"]: x["valeur"] for x in defi["rangs"]}
    noms, morts, sans = [], [], []
    for j in d.get("joueurs", []):
        h = (j["temps"] or 0) / 3600.0
        noms.append(j["pseudo"] + (" 🎮" if j.get("en_cours") else ""))
        morts.append("%d%s" % (j["morts"], " · %.2f/h" % (j["morts"] / h) if h >= 1 else ""))
        sans.append(duree(series[j["pseudo"]]) if j["pseudo"] in series else "—")

    champs = [
        {"name": "Joueur", "value": "\n".join(noms) or "—", "inline": True},
        {"name": "Morts", "value": "\n".join(morts) or "—", "inline": True},
        {"name": "Sans mourir", "value": "\n".join(sans) or "—", "inline": True},
    ]

    k = d.get("kpi") or {}
    if k.get("kpis"):
        lignes = []
        for e in k["kpis"]:
            if e["valeur"] is None:
                continue
            f = duree if e.get("unite") == "duree" else (lambda x: "%g" % x)
            lignes.append("%s **%s** / %s — %s" % (
                "✅" if e["tenu"] else "🔸", f(e["valeur"]), f(e["cible"]), e["libelle"]))
        if lignes:
            champs.append({"name": "🎯  Objectifs", "inline": False,
                           "value": "\n".join(lignes)[:1024]})

    faits = [j for j in k.get("jalons", []) if j.get("date")]
    if faits:
        dernier = faits[-1]
        champs.append({"name": "Dernier jalon", "inline": False,
                       "value": "%s atteint à **%.1f h** de jeu cumulé (objectif %d h) %s"
                                % (dernier["boss"], dernier["heures_reelles"],
                                   dernier["heures_cumulees"],
                                   "✅" if dernier["tenu"] else "⏱️")})

    au = champ_autels(d)
    if au:
        champs.append(au)

    pt = point_du_soir(d)
    if pt:
        champs.append(pt)

    for champ in champs_roles(d):
        champs.append(champ)

    tr = champ_terrain(d)
    if tr:
        champs.append(tr)

    mt = champ_meteo(d)
    if mt:
        champs.append(mt)

    sc = succes_du_jour()
    if sc:
        champs.append({"name": "🏅  Succès Steam", "value": sc, "inline": False})

    # Le titre suivait l'usage et non l'heure : un bilan republie a midi par
    # « !bilan » s'annoncait « du soir ». Il y en a eu un le 2026-09-09 a 12h11.
    h = datetime.datetime.now().hour
    quand = ("🌙  Bilan du soir" if h >= 17 else
             "🌅  Bilan du matin" if h < 12 else
             "☀️  Bilan de la journée")
    return {"title": quand, "description": " · ".join(tete),
            "color": VERT, "fields": champs,
            "footer": {"text": "relevé à %s · `!stats` pour le détail"
                               % (d.get("genere") or "")[11:16]}}


def main():
    url = config()
    if not url:
        return 0
    r = subprocess.run([STATS, "--json"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print("stats-valheim.py a echoue : %s" % r.stderr.strip(), file=sys.stderr)
        return 1
    d = json.loads(r.stdout)
    if not (d.get("joueurs") or d.get("kpi")):
        return 0  # rien a dire
    corps = json.dumps({"embeds": [bilan(d)], "username": "Claudo Le Viking",
                        "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(url, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as rep:
            print("bilan publie (HTTP %s)" % rep.status)
    except (urllib.error.URLError, OSError) as e:
        print("publication impossible : %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
