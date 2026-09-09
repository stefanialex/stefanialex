#!/bin/bash
# Bascule le serveur sur un monde neuf, a une heure annoncee, en prevenant le
# groupe dans le salon Discord.
#
# Pourquoi ce script plutot que la main : le 2026-09-09, la bascule vers la 1.0
# a coupe la partie sans prevenir personne, parce que la chaine du jour J
# annonce mais n'attend pas. Baby a demande un depart groupe a heure fixe, ce
# qui suppose l'inverse : annoncer largement avant, laisser le temps de finir ce
# qu'on fait, puis basculer a la seconde dite.
#
# Ce script ne cree pas le monde lui-meme. Le serveur dedie genere tout seul un
# monde dont le nom n'existe pas, avec une seed au hasard -- verifie a 15h19 le
# 2026-09-09 avec NordheimV1. Ecrire les metadonnees a la main serait le seul
# moyen d'imposer une seed, et le format 1.0 ne le permet pas encore : le
# fichier porte une queue de taille variable dont le sens n'est pas etabli.
#
# L'ancien monde n'est jamais detruit. Il reste dans worlds_local a cote du
# neuf, une archive est prise juste avant la bascule, et une copie de cette
# archive est mise hors de portee de la purge a 30 jours.
set -euo pipefail

ENV=/etc/valheim.env
SAVEDIR=/var/lib/valheim/donnees
MONDES="$SAVEDIR/worlds_local"
OUTIL=/usr/local/bin/monde-valheim.py
SAUVEGARDE=/usr/local/bin/sauvegarde-valheim.sh
CONF=/etc/valheim-discord.conf
ARCHIVES=/srv/jeux/sauvegardes
GARDE=/home/lapserv/archives-valheim

NOM=""
HEURE=""
CONFIRM=0
MODIFICATEURS=""
UNITE=/etc/systemd/system/valheim.service
JALONS="30 10 2"          # minutes avant la bascule ou l'on previent

vert()  { printf '\033[32m%s\033[0m\n' "$*"; }
jaune() { printf '\033[33m%s\033[0m\n' "$*"; }
mourir() { printf '\033[31merreur : %s\033[0m\n' "$*" >&2; exit 1; }

aide() {
    cat <<'FIN'
bascule-monde-valheim.sh --nom NOM [--a HH:MM] [--confirm]

  --nom NOM     nom du monde neuf. Lettres, chiffres, tiret, souligne.
  --a HH:MM     heure de la bascule, aujourd'hui. Sans elle : tout de suite.
  --jalons "30 10 2"
                minutes avant l'heure ou l'on previent dans le salon.
  --modificateurs "-modifier raids muchmore -modifier resources more"
                options de difficulte a appliquer au passage. Categories :
                combat, deathpenalty, resources, raids, portals.
  --confirm     execute pour de vrai. Sans lui : simulation, rien n'est touche.

La bascule elle-meme : sauvegarde verifiee, copie de l'archive hors purge,
arret du serveur, changement de NOM_MONDE, redemarrage, attente du chargement,
puis annonce de la seed des qu'elle touche le disque -- ce qui prend jusqu'a un
intervalle de sauvegarde, dix minutes ici, le monde vivant d'abord en memoire.
FIN
}

while [ $# -gt 0 ]; do
    case "$1" in
        --nom) NOM="${2:-}"; shift 2 ;;
        --a) HEURE="${2:-}"; shift 2 ;;
        --jalons) JALONS="${2:-}"; shift 2 ;;
        --modificateurs) MODIFICATEURS="${2:-}"; shift 2 ;;
        --confirm) CONFIRM=1; shift ;;
        -h|--help) aide; exit 0 ;;
        *) mourir "argument inconnu : $1" ;;
    esac
done

[ -n "$NOM" ] || { aide; mourir "--nom est obligatoire"; }
case "$NOM" in
    *[!A-Za-z0-9_-]*|"") mourir "nom de monde invalide : « $NOM »" ;;
esac
[ ${#NOM} -le 30 ] || mourir "nom de monde trop long"

# Grammaire fermee : on n'ecrit dans la ligne de commande du serveur que des
# couples connus. Une valeur inventee serait ignoree en silence par le jeu, et
# on croirait la difficulte changee alors que non.
if [ -n "$MODIFICATEURS" ]; then
    set -- $MODIFICATEURS
    while [ $# -gt 0 ]; do
        [ "$1" = "-modifier" ] || mourir "modificateurs : attendu « -modifier », vu « $1 »"
        case "${2:-}" in
            combat)       case "${3:-}" in veryeasy|easy|hard|veryhard) ;; *) mourir "combat : ${3:-vide} inconnu" ;; esac ;;
            deathpenalty) case "${3:-}" in casual|veryeasy|easy|hard|hardcore) ;; *) mourir "deathpenalty : ${3:-vide} inconnu" ;; esac ;;
            resources)    case "${3:-}" in muchless|less|more|muchmore|most) ;; *) mourir "resources : ${3:-vide} inconnu" ;; esac ;;
            raids)        case "${3:-}" in none|muchless|less|more|muchmore) ;; *) mourir "raids : ${3:-vide} inconnu" ;; esac ;;
            portals)      case "${3:-}" in casual|hard|veryhard) ;; *) mourir "portals : ${3:-vide} inconnu" ;; esac ;;
            *) mourir "categorie inconnue : ${2:-vide}" ;;
        esac
        shift 3
    done
fi

annonce() {
    local texte=$1 url
    url=$(grep -oP '(?<=^WEBHOOK=).*' "$CONF" 2>/dev/null | tr -d '"' || true)
    [ -n "$url" ] || { jaune "pas de webhook : « $texte »"; return 0; }
    # --data-binary avec un fichier temporaire plutot qu'un argument : le texte
    # contient des retours a la ligne et des emoji.
    local corps
    corps=$(mktemp)
    python3 - "$texte" >"$corps" <<'PY'
import json, sys
print(json.dumps({"content": sys.argv[1], "username": "Claudo Le Viking",
                  "allowed_mentions": {"parse": []}}))
PY
    curl -sS -X POST -H 'Content-Type: application/json' \
         --data-binary "@$corps" "$url" >/dev/null || jaune "annonce non partie"
    rm -f "$corps"
}

monde_actuel() {
    grep -oP '(?<=^NOM_MONDE=).*' "$ENV" 2>/dev/null | tr -d '"' || true
}

seed_de() {
    local monde=$1 meta
    meta=$("$OUTIL" chemin "$MONDES" "$monde" 2>/dev/null) || return 1
    "$OUTIL" lire "$meta" 2>/dev/null | awk '/^seed / { print $2 }'
}

ACTUEL=$(monde_actuel)
[ -n "$ACTUEL" ] || mourir "NOM_MONDE introuvable dans $ENV"
[ "$ACTUEL" != "$NOM" ] || mourir "le serveur est deja sur « $NOM »"

if "$OUTIL" chemin "$MONDES" "$NOM" >/dev/null 2>&1; then
    mourir "un monde « $NOM » existe deja ; choisis un autre nom"
fi

# L'instant de la bascule. Sans --a, c'est maintenant.
if [ -n "$HEURE" ]; then
    CIBLE=$(date -d "today $HEURE" +%s 2>/dev/null) \
        || mourir "heure illisible : « $HEURE » (attendu HH:MM)"
    [ "$CIBLE" -gt "$(date +%s)" ] || mourir "$HEURE est deja passe"
else
    CIBLE=$(date +%s)
fi

SEED_ACTUELLE=$(seed_de "$ACTUEL" || echo inconnue)

echo "monde actuel            $ACTUEL (seed ${SEED_ACTUELLE:-inconnue})"
echo "monde neuf              $NOM, seed tiree au hasard par le serveur"
echo "bascule                 $(date -d "@$CIBLE" '+%H:%M:%S')"
echo "avertissements          $JALONS minutes avant"
if [ -n "$MODIFICATEURS" ]; then
    echo "modificateurs           $MODIFICATEURS"
fi

if [ "$CONFIRM" -eq 0 ]; then
    jaune "simulation : rien n'a ete touche. Ajoute --confirm pour executer."
    exit 0
fi

annonce "📣  **Départ groupé à $(date -d "@$CIBLE" '+%Hh%M')** sur un monde neuf : **$NOM**.

Le monde actuel **$ACTUEL** (seed \`${SEED_ACTUELLE:-inconnue}\`) est **conservé** — archivé, pas détruit. On pourra y revenir.

Finissez ce que vous faites : le serveur redémarre à $(date -d "@$CIBLE" '+%Hh%M') pile et vous serez déconnectés."

for m in $JALONS; do
    quand=$((CIBLE - m * 60))
    maintenant=$(date +%s)
    if [ "$quand" -le "$maintenant" ]; then
        continue
    fi
    sleep $((quand - maintenant))
    if [ "$m" -le 2 ]; then
        annonce "⚠️  **$m minutes.** Mettez-vous à l'abri et déconnectez-vous, le serveur redémarre sur **$NOM**."
    else
        annonce "⏳  Dans **$m minutes**, bascule sur **$NOM**."
    fi
done

reste=$((CIBLE - $(date +%s)))
if [ "$reste" -gt 0 ]; then
    sleep "$reste"
fi

vert "== bascule =="
annonce "🔄  Bascule en cours. Sauvegarde de **$ACTUEL**, puis démarrage de **$NOM**. Une minute."

"$SAUVEGARDE" || mourir "la sauvegarde a echoue ; rien n'a ete change"

# Une copie hors de la purge a 30 jours : c'est le dernier etat du monde qu'on
# quitte, et il n'est pas reproductible.
mkdir -p "$GARDE"
DERNIERE=$(ls -t "$ARCHIVES"/valheim-*.tar.gz 2>/dev/null | head -1 || true)
if [ -n "$DERNIERE" ]; then
    cp -p "$DERNIERE" "$GARDE/${ACTUEL}-avant-$NOM-$(basename "$DERNIERE")"
    chown -R lapserv:lapserv "$GARDE" || true
    vert "archive conservee : $GARDE/${ACTUEL}-avant-$NOM-$(basename "$DERNIERE")"
fi

systemctl stop valheim.service

# Les modificateurs passent par une variable pour que les reglages suivants ne
# demandent plus qu'un redemarrage. Le « $ » est SANS accolades : systemd
# decoupe « $VAR » en plusieurs arguments sur les espaces, mais pas « ${VAR} »,
# qui resterait un seul mot -- le serveur recevrait « -modifier raids muchmore »
# en bloc et l'ignorerait sans rien dire.
if [ -n "$MODIFICATEURS" ]; then
    if ! grep -q '\$MODIFICATEURS' "$UNITE"; then
        cp -p "$UNITE" "$UNITE.avant-modificateurs"
        sed -i 's|^\( *\)-public 0 \\|\1$MODIFICATEURS \\\n\1-public 0 \\|' "$UNITE"
        grep -q '\$MODIFICATEURS' "$UNITE" \
            || mourir "impossible d'ajouter \$MODIFICATEURS a $UNITE ; serveur arrete"
        systemctl daemon-reload
        vert "unite completee, copie de secours en $UNITE.avant-modificateurs"
    fi
    sed -i '/^MODIFICATEURS=/d' "$ENV"
    printf 'MODIFICATEURS=%s\n' "$MODIFICATEURS" >>"$ENV"
    vert "modificateurs : $MODIFICATEURS"
fi
# sed sur la seule ligne NOM_MONDE : le fichier porte aussi le mot de passe du
# serveur, qu'il ne faut ni reecrire ni faire apparaitre dans un journal.
sed -i "s/^NOM_MONDE=.*/NOM_MONDE=$NOM/" "$ENV"
grep -q "^NOM_MONDE=$NOM$" "$ENV" || mourir "$ENV n'a pas ete modifie ; serveur arrete"
systemctl start valheim.service

for _ in $(seq 1 60); do
    if journalctl -u valheim --since '-3 min' --no-pager -o cat 2>/dev/null \
        | grep -qa "Load world: $NOM"; then
        break
    fi
    sleep 5
done
journalctl -u valheim --since '-3 min' --no-pager -o cat 2>/dev/null \
    | grep -qa "Load world: $NOM" \
    || mourir "le serveur n'a pas charge $NOM ; regarder journalctl -u valheim"

vert "$NOM charge"
MOT_MOD=""
if [ -n "$MODIFICATEURS" ]; then
    MOT_MOD="

⚙️  Règles du monde : \`$MODIFICATEURS\`"
fi
annonce "✅  **$NOM est en ligne.** Créez vos personnages, on repart de zéro.$MOT_MOD

Sa seed arrive dès la première sauvegarde du monde, dans une dizaine de minutes — le monde vit d'abord en mémoire."

# La seed ne touche le disque qu'a la premiere sauvegarde du monde, soit un
# intervalle de sauvegarde apres le demarrage.
for _ in $(seq 1 90); do
    SEED=$(seed_de "$NOM" || true)
    if [ -n "${SEED:-}" ]; then
        break
    fi
    sleep 20
done
if [ -n "${SEED:-}" ]; then
    vert "seed de $NOM : $SEED"
    annonce "🌍  Seed de **$NOM** : \`$SEED\`"
else
    jaune "seed non lue apres 30 minutes"
    annonce "🌍  **$NOM** tourne, mais je n'ai pas encore pu lire sa seed. Je la donnerai plus tard."
fi
