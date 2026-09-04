#!/usr/bin/env python3
"""Lit un salon Discord et execute les commandes du groupe.

Un webhook est a sens unique : il permet d'ecrire, jamais de lire. La lecture
exige un bot, avec son propre token et l'intent « Message Content ».

Deux sortes de demandes, et la distinction est le coeur du programme :

  - Les demandes mecaniques (cocher un chantier, changer une cible) sont
    executees et confirmees dans la minute, par du code, sans intervention.
  - Les demandes qui exigent du jugement (« inventez-nous un defi ») sont
    rangees en file d'attente. Claude ne tourne pas en permanence : il les
    traitera a sa prochaine invocation.

Le contenu des messages vient de personnes : il est traite comme une donnee,
jamais comme une commande a interpreter. Aucun shell n'est invoque, les
sous-processus recoivent des listes d'arguments, et chaque commande est
reconnue par une grammaire fermee.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

CONF = "/etc/valheim-discord.conf"
BASE = os.environ.get("STATE_DIRECTORY", "/var/lib/valheim-stats") + "/valheim.db"
CHANTIER = "/usr/local/bin/chantier-valheim.py"
STATS = "/usr/local/bin/stats-valheim.py"
BILAN = "/usr/local/bin/bilan-discord-valheim.py"
OBJECTIFS = "/etc/valheim/objectifs.json"
API = "https://discord.com/api/v10"
AGENT = "valheim-serveur/1.0 (bot de salon auto-heberge)"
MAX_REPONSE = 1900

SCHEMA = """
CREATE TABLE IF NOT EXISTS discord_demandes (
  id         TEXT PRIMARY KEY,
  horodatage TEXT,
  auteur     TEXT,
  contenu    TEXT,
  commande   TEXT,
  etat       TEXT DEFAULT 'recu',
  reponse    TEXT
);
CREATE TABLE IF NOT EXISTS reglages (cle TEXT PRIMARY KEY, valeur TEXT);
"""

AIDE = """**Commandes du salon**
`!aide` — cette liste
`!stats` — les chiffres du moment
`!bilan` — republie le bilan complet
`!chantiers` — l'etat des chantiers
`!chantier <nom> <a faire|en cours|fait>` — coche un chantier
`!qui <nom> <Lapin|Beny|Djoose|Baby>` — affecte quelqu'un
`!objectif <cle> <valeur>` — change une cible de KPI
`!defi <votre idee>` — propose un defi ; Claude le traitera et dira s'il est
mesurable, declaratif ou impossible
`!demandes` — les propositions en attente"""

ETATS = {"fait": "fait", "en cours": "en_cours", "en_cours": "en_cours",
         "a faire": "a_faire", "a_faire": "a_faire", "afaire": "a_faire"}


def config():
    d = {}
    try:
        with open(CONF) as f:
            for l in f:
                l = l.strip()
                if l.startswith("#") or "=" not in l:
                    continue
                c, v = l.split("=", 1)
                d[c.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return d


def appel(chemin, token, methode="GET", corps=None, params=None):
    url = API + chemin
    if params:
        url += "?" + urllib.parse.urlencode(params)
    donnees = json.dumps(corps).encode() if corps is not None else None
    r = urllib.request.Request(url, data=donnees, method=methode, headers={
        "Authorization": "Bot " + token,
        "Content-Type": "application/json",
        "User-Agent": AGENT})
    with urllib.request.urlopen(r, timeout=20) as rep:
        brut = rep.read()
        return json.loads(brut) if brut else None


def repond(salon, token, texte):
    try:
        appel("/channels/%s/messages" % salon, token, "POST",
              {"content": texte[:MAX_REPONSE], "allowed_mentions": {"parse": []}})
    except (urllib.error.URLError, OSError) as e:
        print("reponse non envoyee : %s" % e, file=sys.stderr)


def lance(argv):
    """Sous-processus sans shell : le contenu d'un message ne peut pas s'evader."""
    r = subprocess.run(argv, capture_output=True, text=True, timeout=90)
    return r.returncode, (r.stdout or r.stderr).strip()


def traite(contenu, cx):
    """Rend (reponse, differe). differe = la demande attend un humain."""
    m = re.match(r"^!(\w+)\s*(.*)$", contenu.strip(), re.S)
    if not m:
        return None, False
    cmd, reste = m.group(1).lower(), m.group(2).strip()

    if cmd == "aide":
        return AIDE, False

    if cmd == "stats":
        _c, sortie = lance([STATS])
        garde = [l for l in sortie.splitlines()
                 if l.startswith(("JOUEURS", "KPI", "  ")) ][:24]
        return "```\n" + "\n".join(garde) + "\n```", False

    if cmd == "bilan":
        _c, _s = lance([BILAN])
        return None, False  # le bilan se publie lui-meme

    if cmd == "chantiers":
        _c, sortie = lance([CHANTIER, "liste"])
        debut = sortie.find("CHANTIERS")
        return "```\n" + sortie[debut:][:1500] + "\n```", False

    if cmd == "chantier":
        p = re.match(r"^(.*?)\s+(fait|en[ _]cours|a[ _]?faire)$", reste, re.I)
        if not p:
            return ("Il me manque l'etat. Exemple : `!chantier armurerie fait`.\n"
                    "Etats possibles : fait, en cours, a faire."), False
        etat = ETATS[p.group(2).lower().replace("  ", " ")]
        code, sortie = lance([CHANTIER, "etat", p.group(1).strip(), etat])
        return ("✅ " if code == 0 else "⚠️ ") + sortie, False

    if cmd == "qui":
        p = reste.rsplit(None, 1)
        if len(p) != 2:
            return "Exemple : `!qui avant poste marais Djoose`.", False
        code, sortie = lance([CHANTIER, "qui", p[0], p[1]])
        return ("✅ " if code == 0 else "⚠️ ") + sortie, False

    if cmd == "objectif":
        p = reste.split()
        if len(p) != 2:
            return ("Exemple : `!objectif morts_total 30`. Les cles sont celles "
                    "de la page des defis."), False
        return change_objectif(p[0], p[1]), False

    if cmd in ("defi", "objectifs", "demande"):
        if not reste:
            return "Dis-moi lequel : `!defi personne ne meurt avant Moder`.", False
        return ("📝 Noté : « %s ».\nClaude le traitera et dira s'il est mesurable "
                "par le serveur, declaratif, ou impossible." % reste[:300]), True

    if cmd == "demandes":
        lignes = cx.execute(
            "SELECT horodatage, auteur, contenu FROM discord_demandes "
            "WHERE etat = 'recu' AND commande = 'defi' ORDER BY id").fetchall()
        if not lignes:
            return "Aucune proposition en attente.", False
        return "**En attente de Claude**\n" + "\n".join(
            "• %s — *%s* : %s" % (h[:16], a, c[:120]) for h, a, c in lignes[:10]), False

    return ("Commande inconnue : `!%s`. Tape `!aide`." % cmd), False


def change_objectif(cle, valeur):
    try:
        with open(OBJECTIFS, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        return "⚠️ objectifs illisibles (%s)" % e
    for k in d.get("kpis", []):
        if k["cle"] == cle:
            try:
                v = float(valeur)
            except ValueError:
                return "⚠️ « %s » n'est pas un nombre." % valeur
            avant = k.get("cible")
            k["cible"] = int(v) if v == int(v) else v
            # Ecriture par renommage : une interruption ne doit pas laisser un
            # fichier de configuration tronque.
            tmp = OBJECTIFS + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, OBJECTIFS)
            return "✅ %s : cible %s → %s" % (k["libelle"], avant, k["cible"])
    cles = ", ".join(k["cle"] for k in d.get("kpis", []))
    return "⚠️ cle inconnue. Celles qui existent : %s" % cles


def main():
    c = config()
    token, salon = c.get("TOKEN"), c.get("SALON")
    if not token or not salon:
        return 0  # pas encore configure : ce n'est pas une erreur

    autorises = [x for x in re.split(r"[,\s]+", c.get("AUTORISES", "")) if x]

    cx = sqlite3.connect(BASE)
    cx.executescript(SCHEMA)
    r = cx.execute("SELECT valeur FROM reglages WHERE cle = 'discord_dernier_message'"
                   ).fetchone()
    dernier = r[0] if r else None

    params = {"limit": 50}
    if dernier:
        params["after"] = dernier
    try:
        messages = appel("/channels/%s/messages" % salon, token, params=params) or []
    except urllib.error.HTTPError as e:
        corps = e.read()[:200].decode("utf8", "replace")
        print("lecture impossible : HTTP %s %s" % (e.code, corps), file=sys.stderr)
        if "50001" in corps or e.code == 403:
            # Cas rencontre a l'installation : le salon valheim est prive, et
            # une surcharge y refuse « voir le salon » a @everyone. Le bot lit
            # les autres salons mais pas celui-la. Le message dit quoi faire,
            # sinon le journal ne montrerait qu'un code d'erreur opaque.
            print("  -> le bot n'a pas acces a ce salon. Dans Discord :\n"
                  "     Modifier le salon > Permissions > ajouter le bot, avec\n"
                  "     « Voir les salons », « Voir les anciens messages » et\n"
                  "     « Envoyer des messages ».", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as e:
        print("lecture impossible : %s" % e, file=sys.stderr)
        return 1

    messages = sorted(messages, key=lambda m: int(m["id"]))
    if not messages:
        return 0

    if not dernier:
        # Premier demarrage : on se cale sur le present sans rejouer l'historique
        # du salon, qui declencherait d'anciennes commandes.
        cx.execute("INSERT INTO reglages VALUES ('discord_dernier_message', ?) "
                   "ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur",
                   (messages[-1]["id"],))
        cx.commit()
        print("premier demarrage, cale sur le message %s" % messages[-1]["id"])
        return 0

    traites = 0
    for msg in messages:
        contenu = (msg.get("content") or "").strip()
        auteur = (msg.get("author") or {}).get("username", "?")
        if msg.get("author", {}).get("bot"):
            continue
        if not contenu.startswith("!"):
            continue  # on ne conserve que ce qui nous est adresse
        if autorises and str(msg["author"]["id"]) not in autorises:
            repond(salon, token, "Je n'accepte les commandes que des comptes autorises.")
            continue

        reponse, differe = traite(contenu, cx)
        cmd = re.match(r"^!(\w+)", contenu)
        cx.execute(
            "INSERT OR IGNORE INTO discord_demandes "
            "(id, horodatage, auteur, contenu, commande, etat, reponse) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg["id"], msg.get("timestamp", "")[:19].replace("T", " "), auteur,
             contenu[:1000], cmd.group(1).lower() if cmd else None,
             "recu" if differe else "traite", (reponse or "")[:1000]))
        if reponse:
            repond(salon, token, reponse)
        traites += 1

    cx.execute("INSERT INTO reglages VALUES ('discord_dernier_message', ?) "
               "ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur",
               (messages[-1]["id"],))
    cx.commit()
    print("%d message(s) lu(s), %d commande(s) traitee(s)" % (len(messages), traites))
    return 0


if __name__ == "__main__":
    sys.exit(main())
