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
`!defi <votre idée>` — propose un défi ; Claude dira s'il est mesurable,
déclaratif ou impossible
`!claude <votre question>` — pose une question ; réponse quand Claude passe
`!demandes` — la file en attente

*Les commandes ci-dessus sont les seules actions possibles depuis le salon.
Un message ne peut rien exécuter d'autre.*"""

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


# --- filtre de sortie ---------------------------------------------------
# Rien de ce qui sort vers le salon ne doit contenir de secret. Ce n'est pas
# une precaution theorique : le bot lit des messages ecrits par des personnes,
# et une demande formulee pour obtenir « la configuration » ou « le contenu de
# /etc » ne doit pas pouvoir aboutir. Le filtre agit en dernier, sur le message
# construit, quel que soit le chemin qui l'a produit.
MOTIF_WEBHOOK = re.compile(r"https://discord(?:app)?\.com/api/webhooks/\S+")


def secrets_connus():
    valeurs = []
    for fichier, cles in ((CONF, ("WEBHOOK", "TOKEN")),
                          ("/etc/valheim-steam.conf", ("CLE",))):
        try:
            with open(fichier) as f:
                for l in f:
                    for c in cles:
                        if l.startswith(c + "="):
                            v = l.split("=", 1)[1].strip().strip('"')
                            if len(v) >= 16:
                                valeurs.append(v)
        except OSError:
            pass
    return valeurs


def nettoie(valeur, secrets=None):
    """Remplace tout secret par une mention neutre, recursivement."""
    if secrets is None:
        secrets = secrets_connus()
    if isinstance(valeur, dict):
        return {k: nettoie(v, secrets) for k, v in valeur.items()}
    if isinstance(valeur, list):
        return [nettoie(v, secrets) for v in valeur]
    if not isinstance(valeur, str):
        return valeur
    for x in secrets:
        valeur = valeur.replace(x, "‹masqué›")
    return MOTIF_WEBHOOK.sub("‹masqué›", valeur)


VERT = 0x3D7317      # le vert d'etat de Cockpit, pour que tout se ressemble
GRIS = 0x4D4D4D


def repond(salon, token, contenu):
    """Publie une reponse : du texte, ou un embed si on lui passe un dict.

    Les embeds existent pour ca : titre, colonnes alignees par Discord
    lui-meme, et une couleur qui distingue une reponse d'un message ordinaire.
    Un pave monospace faisait le travail mais ne ressemblait a rien.
    """
    corps = {"allowed_mentions": {"parse": []}}
    if isinstance(contenu, dict):
        corps["embeds"] = [contenu]
    else:
        corps["content"] = contenu[:MAX_REPONSE]
    corps = nettoie(corps)
    try:
        appel("/channels/%s/messages" % salon, token, "POST", corps)
    except (urllib.error.URLError, OSError) as e:
        print("reponse non envoyee : %s" % e, file=sys.stderr)


def duree(secondes):
    s = int(secondes or 0)
    if s < 3600:
        return "%d min" % (s // 60)
    return "%d h %02d" % (s // 3600, (s % 3600) // 60)


PUCE = {"fait": "✅", "en_cours": "🔧", "a_faire": "▫️"}


def embed_chantiers():
    r = subprocess.run([STATS, "--json"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return "⚠️ chantiers indisponibles."
    c = (json.loads(r.stdout) or {}).get("chantiers")
    if not c:
        return "Aucun chantier déclaré."
    a = c.get("avancement", {})
    lignes = ["%s %s%s" % (PUCE.get(ch["etat"], "▫️"), ch["nom"],
                           " — " + ", ".join(ch["titulaires"]) if ch["titulaires"] else "")
              for ch in c["chantiers"]]
    fonctions = ["**%s** — %s" % (f["nom"], ", ".join(f["titulaires"]) or "personne")
                 for f in c.get("fonctions", [])]
    return {"title": "🏗️  Chantiers — %s / %s" % (a.get("faits", 0), a.get("total", 0)),
            "color": VERT if a.get("faits") else GRIS,
            "fields": [
                {"name": "Constructions", "value": "\n".join(lignes)[:1024], "inline": False},
                {"name": "Fonctions", "value": "\n".join(fonctions)[:1024], "inline": False}],
            "footer": {"text": "déclaratif · chantier-valheim.py ou !chantier <nom> fait"}}


def resume_stats():
    """Reponse a !stats, construite depuis le JSON et non gratee dans du texte.

    La premiere version filtrait la sortie de presentation sur l'indentation
    des lignes : les lignes de joueurs commencent au premier caractere, elles
    passaient donc a la trappe pendant que l'indentation des autres sections
    etait conservee. Le JSON est le contrat, la mise en page n'en est pas un.

    Le temps de jeu par joueur n'y figure pas volontairement : le groupe a
    demande de retirer la pointeuse, et une commande tapee dans le salon
    l'affiche a tout le monde tout autant qu'une annonce automatique. Il reste
    consultable dans Cockpit.
    """
    r = subprocess.run([STATS, "--json"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return "⚠️ statistiques indisponibles."
    d = json.loads(r.stdout)

    tete = []
    if d.get("monde"):
        tete.append("monde *%s*" % d["monde"])
    if d.get("jour"):
        tete.append("jour %s" % d["jour"])
    en_jeu = [j["pseudo"] for j in d.get("joueurs", []) if j.get("en_cours")]
    tete.append(", ".join(en_jeu) + " en jeu" if en_jeu else "personne en jeu")

    # Serie en cours par joueur : la metrique qui sert les defis.
    series = {}
    for defi in d.get("defis") or []:
        if defi.get("nom") == "Serie en cours":
            series = {x["joueur"]: x["valeur"] for x in defi["rangs"]}

    joueurs, morts, sans = [], [], []
    for j in d.get("joueurs", []):
        h = (j["temps"] or 0) / 3600.0
        taux = " · %.2f/h" % (j["morts"] / h) if h >= 1 else ""
        joueurs.append(j["pseudo"] + (" 🎮" if j.get("en_cours") else ""))
        morts.append("%d%s" % (j["morts"], taux))
        sans.append(duree(series[j["pseudo"]]) if j["pseudo"] in series else "—")

    # Trois champs « inline » : Discord les met en colonnes et les aligne
    # lui-meme, quelle que soit la police du lecteur.
    champs = [
        {"name": "Joueur", "value": "\n".join(joueurs) or "—", "inline": True},
        {"name": "Morts", "value": "\n".join(morts) or "—", "inline": True},
        {"name": "Sans mourir", "value": "\n".join(sans) or "—", "inline": True},
    ]

    k = d.get("kpi") or {}
    court = [e for e in k.get("kpis", [])
             if e["cle"] in ("boss", "intacts", "chantiers") and e["valeur"] is not None]
    if court:
        champs.append({"name": "Objectifs", "inline": False, "value": "\n".join(
            "%s **%s / %s** %s" % (e["libelle"], e["valeur"], e["cible"],
                                   "✅" if e["tenu"] else "")
            for e in court)})

    return {"title": "⚔️  Serveur Valheim",
            "description": " · ".join(tete),
            "color": VERT, "fields": champs,
            "footer": {"text": "relevé à " + (d.get("genere") or "")[11:16]}}


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
        return {"title": "🛠️  Commandes du salon", "color": GRIS,
                "description": AIDE.split("\n", 1)[1]}, False

    if cmd == "stats":
        return resume_stats(), False

    if cmd == "bilan":
        _c, _s = lance([BILAN])
        return None, False  # le bilan se publie lui-meme

    if cmd == "chantiers":
        return embed_chantiers(), False

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

    if cmd == "claude":
        if not reste:
            return ("Pose ta question : `!claude comment on prépare Bonemass ?`\n"
                    "Je ne suis pas en ligne en permanence — ta question part "
                    "dans une file et reçoit une réponse quand je passe."), False
        return ("💬  Question notée : « %s ».\nJe ne tourne pas en continu : "
                "la réponse arrivera quand je passerai. `!demandes` pour voir "
                "la file." % reste[:300]), True

    if cmd in ("defi", "objectifs", "demande"):
        if not reste:
            return "Dis-moi lequel : `!defi personne ne meurt avant Moder`.", False
        return ("📝 Noté : « %s ».\nClaude le traitera et dira s'il est mesurable "
                "par le serveur, declaratif, ou impossible." % reste[:300]), True

    if cmd == "demandes":
        lignes = cx.execute(
            "SELECT horodatage, auteur, contenu FROM discord_demandes "
            "WHERE etat = 'recu' AND commande IN ('defi', 'claude') "
            "ORDER BY id").fetchall()
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
            # Liste blanche d'auteurs : une commande n'est executee que si elle
            # vient d'un compte connu. Le salon est prive, mais un salon prive
            # peut s'ouvrir par erreur, et c'est la seule barriere qui ne
            # depende pas des reglages Discord.
            repond(salon, token,
                   "Je n'accepte les commandes que des comptes autorisés.")
            continue

        reponse, differe = traite(contenu, cx)
        cmd = re.match(r"^!(\w+)", contenu)
        cx.execute(
            "INSERT OR IGNORE INTO discord_demandes "
            "(id, horodatage, auteur, contenu, commande, etat, reponse) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg["id"], msg.get("timestamp", "")[:19].replace("T", " "), auteur,
             contenu[:1000], cmd.group(1).lower() if cmd else None,
             "recu" if differe else "traite",
             json.dumps(reponse, ensure_ascii=False)[:1000] if isinstance(reponse, dict)
             else (reponse or "")[:1000]))
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
