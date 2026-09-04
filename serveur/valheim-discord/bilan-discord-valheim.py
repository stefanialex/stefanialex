#!/usr/bin/env python3
"""Publie le bilan KPI du serveur Valheim sur Discord.

Complement de notifie-discord-valheim.py, qui poste les evenements au fil de
l'eau : celui-ci envoie une synthese, une fois par jour. Il ne calcule rien
lui-meme et appelle stats-valheim.py --json, pour qu'il n'existe qu'une seule
definition de chaque indicateur.
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request

CONF = "/etc/valheim-discord.conf"
STATS = "/usr/local/bin/stats-valheim.py"
# Discord passe par Cloudflare, qui refuse l'agent par defaut de Python.
AGENT = "valheim-serveur/1.0 (bilan quotidien auto-heberge)"
LIMITE = 1900  # Discord coupe a 2000 caracteres


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


def jauge(av):
    if av is None:
        return "          "
    n = int(round(av * 10))
    return "#" * n + "." * (10 - n)


def bilan(d):
    lignes = []
    tete = ["**Bilan du serveur**"]
    if d.get("monde"):
        tete.append("monde *%s*" % d["monde"])
    if d.get("jour"):
        tete.append("jour %s" % d["jour"])
    if d.get("zdos"):
        tete.append("%s objets" % format(int(d["zdos"]), ",d").replace(",", " "))
    lignes.append(" · ".join(tete))

    k = d.get("kpi") or {}
    if k.get("kpis"):
        lignes.append("```")
        for e in k["kpis"]:
            if e["valeur"] is None:
                lignes.append("%-34s %14s" % (e["libelle"][:34], "pas mesurable"))
                continue
            f = duree if e.get("unite") == "duree" else (lambda x: "%g" % x)
            lignes.append("%-34s %9s /%9s  %s %s" % (
                e["libelle"][:34], f(e["valeur"]), f(e["cible"]),
                jauge(e["avancement"]), "OK" if e["tenu"] else "--"))
        lignes.append("```")

    faits = [j for j in k.get("jalons", []) if j.get("date")]
    if faits:
        lignes.append("**Jalons**, en temps de jeu cumulé : " + " · ".join(
            "%s %.1f h/%d h %s" % (j["boss"], j["heures_reelles"],
                                   j["heures_cumulees"],
                                   "✅" if j["tenu"] else "⏱️")
            for j in faits))

    c = d.get("chantiers")
    if c and c.get("avancement", {}).get("total"):
        a = c["avancement"]
        en_cours = [ch["nom"] for ch in c["chantiers"] if ch["etat"] == "en_cours"]
        ligne = "**Chantiers** %d/%d faits" % (a["faits"], a["total"])
        if en_cours:
            ligne += " · en cours : " + ", ".join(en_cours[:4])
        lignes.append(ligne)

    # Les meneurs de chaque defi : c'est ce qui se lit en premier dans un salon.
    # Un defi que personne ne tient ne doit pas designer de « meneur » : sur
    # « intact depuis l'Ancien », annoncer DjOsE en tete avec 2 morts laisserait
    # croire qu'il le tient. On dit alors que personne ne le tient.
    for defi in (d.get("defis") or [])[:4]:
        rangs = defi.get("rangs") or []
        if not rangs:
            continue
        premier = rangs[0]
        v = duree(premier["valeur"]) if defi.get("unite") == "duree" \
            else "%g" % premier["valeur"]
        binaire = any(r.get("tient") is not None for r in rangs)
        if binaire and not premier.get("tient"):
            lignes.append("**%s** — personne ne le tient (au mieux **%s**, %s)" % (
                defi["nom"], premier["joueur"], v))
        elif premier.get("tient"):
            lignes.append("**%s** — **%s** le tient toujours" % (
                defi["nom"], premier["joueur"]))
        else:
            lignes.append("**%s** — en tête : **%s** (%s)" % (
                defi["nom"], premier["joueur"], v))

    texte = "\n".join(lignes)
    return texte[:LIMITE]


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
    corps = json.dumps({"content": bilan(d),
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
