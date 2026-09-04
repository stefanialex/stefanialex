#!/bin/bash
# Tout ce qu'il faut faire au lancement de Valheim 1.0, le 9 septembre 2026.
#
# Le serveur dedie n'a pas de branche de test : la 1.0 arrivera sans preavis
# verifiable. Ce script sert a etre pret plutot qu'a improviser -- il detecte la
# sortie, met a jour, mesure ce que la nouvelle version change, cree le monde
# neuf avec la bonne seed, et le dit sur Discord.
#
# Rien qui modifie la machine ne s'execute sans --confirm.
set -euo pipefail

APP=896660
INSTALL=/srv/jeux/valheim/serveur
MANIFESTE="$INSTALL/steamapps/appmanifest_$APP.acf"
UTILISATEUR=valheim
MAISON=/srv/jeux/valheim
STEAMCMD=/usr/games/steamcmd
SAVEDIR=/var/lib/valheim/donnees
MONDES="$SAVEDIR/worlds_local"
OUTIL=/usr/local/bin/monde-valheim.py
BASCULE=/usr/local/bin/nouveau-monde-valheim.sh
SAUVEGARDE=/usr/local/bin/sauvegarde-valheim.sh
CONF_DISCORD=/etc/valheim-discord.conf
SONDE_DIR=/var/tmp/sonde-valheim
SONDE_PORT=2466
JOURNAL=/var/log/serveur-ia
MARQUEUR=/var/lib/valheim-stats/1.0-annoncee
SONDE_RESULTAT=/var/lib/valheim-stats/generateur-sonde
# La chaine automatique ne se declenche pas avant cette date. Sans cette
# barriere, un simple correctif publie par Iron Gate avant la 1.0 suffirait a
# faire basculer le monde -- la partie en cours serait archivee pour rien.
PAS_AVANT=2026-09-09
NOM_AUTO=NordheimV1

CONFIRM=0
FORCE=0
ACTION=verifier
NOM=""
SEED=""
INTERVALLE=300

vert()  { printf '\033[32m%s\033[0m\n' "$*"; }
jaune() { printf '\033[33m%s\033[0m\n' "$*"; }
mourir() { printf '\033[31merreur : %s\033[0m\n' "$*" >&2; exit 1; }
titre() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }

aide() {
    cat <<'AIDE'
Usage : jour-j-valheim.sh [action] [options]

Actions, dans l'ordre ou on les utilise le jour J :

  --verifier        audit de preparation. Ne modifie rien, ne demande pas
                    --confirm. A lancer des maintenant, et le matin du 9.
  --attendre        interroge Steam jusqu'a ce que le buildid du serveur dedie
                    change, puis sort. C'est la detection de la sortie de la 1.0.
                    --intervalle SECONDES entre deux interrogations (defaut 300)
  --controle        un seul controle, pour une minuterie : compare les buildid
                    et annonce sur Discord la premiere fois qu'ils divergent.
                    N'installe rien. C'est la detection automatique de la
                    sortie ; la mise a jour et le monde neuf restent manuels.
  --maj             sauvegarde, arret, mise a jour SteamCMD, redemarrage,
                    verification.
  --sonde           mesure ce que la nouvelle version change : cree un monde
                    jetable sur un serveur separe et lit la version de format
                    et la version du generateur de monde. C'est ce qui dit si
                    les seeds conseillees avant la 1.0 valent encore quelque
                    chose.
  --monde           cree le monde neuf. --nom NOM obligatoire, --seed SEED
                    conseille. La version du generateur vient de --sonde.
  --tout            enchaine maj, sonde, monde. --nom et --seed requis.
  --automatique     la meme chose sans intervention, pour une minuterie :
                    monde NordheimV1, seed tiree au hasard, annonces Discord a
                    chaque etape. Ne fait rien avant le 2026-09-09, et rien si
                    le monde existe deja.
  --retour-arriere  reinstalle la branche « default_old » (previous stable), si
                    la 1.0 empeche le serveur de demarrer.

  --confirm         execute pour de vrai. Sans lui : simulation.
  --force           bascule le monde meme si des joueurs sont connectes
AIDE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --verifier|--attendre|--controle|--automatique|--maj|--sonde|--monde|--tout|--retour-arriere)
            ACTION="${1#--}"; shift ;;
        --nom) NOM="${2:-}"; shift 2 ;;
        --seed) SEED="${2:-}"; shift 2 ;;
        --intervalle) INTERVALLE="${2:-}"; shift 2 ;;
        --confirm) CONFIRM=1; shift ;;
        --force) FORCE=1; shift ;;
        -h|--help) aide; exit 0 ;;
        *) mourir "argument inconnu : $1" ;;
    esac
done

# ---------- briques ----------

buildid_installe() {
    grep -oP '(?<="buildid"\s{2}")[0-9]+' "$MANIFESTE" 2>/dev/null | head -1
}

buildid_distant() {
    # app_info_update 1 force le rafraichissement du cache : sans lui, steamcmd
    # peut resservir un buildid vieux de plusieurs heures et la detection de la
    # sortie passerait a cote.
    local sortie
    sortie=$(timeout 300 sudo -u "$UTILISATEUR" env HOME="$MAISON" \
        "$STEAMCMD" +login anonymous +app_info_update 1 \
        +app_info_print "$APP" +quit 2>/dev/null || true)
    # On lit le buildid de la branche « public » et d'aucune autre : les
    # branches default_old et default_pre* portent des buildid plus anciens qui
    # feraient croire a un changement.
    printf '%s' "$sortie" | awk '
        /"branches"/      { dans_branches = 1 }
        dans_branches && /"public"/ { dans_public = 1; next }
        dans_public && /"buildid"/ {
            gsub(/[^0-9]/, "", $2); print $2; exit
        }
        dans_public && /^\t*\}/ { dans_public = 0 }'
}

annonce() {
    # Discord si configure ; silencieux sinon. Le webhook est un secret, il
    # n'apparait pas dans la sortie.
    local url
    url=$(grep -oP '(?<=^WEBHOOK=).*' "$CONF_DISCORD" 2>/dev/null | tr -d '"' || true)
    [ -n "$url" ] || return 0
    curl -sS -m 15 -H 'Content-Type: application/json' \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1], "allowed_mentions": {"parse": []}}))' "$1")" \
        "$url" >/dev/null 2>&1 || jaune "annonce Discord non partie"
}

version_reseau() {
    sudo journalctl -u valheim --no-pager -o cat 2>/dev/null \
        | grep -oP '(?<=Network version check, their:)[0-9]+' | tail -1
}

joueurs_en_jeu() {
    /usr/local/bin/stats-valheim.py --json 2>/dev/null | python3 -c 'import json,sys
d = json.load(sys.stdin)
print(" ".join(j["pseudo"] for j in d["joueurs"] if j["en_cours"]))' 2>/dev/null || true
}

# ---------- actions ----------

action_verifier() {
    titre "Preparation du jour J"
    local pb=0

    local bi bd
    bi=$(buildid_installe); echo "buildid installe        ${bi:-inconnu}"
    bd=$(buildid_distant);  echo "buildid publie          ${bd:-injoignable}"
    if [ -n "$bi" ] && [ -n "$bd" ]; then
        if [ "$bi" = "$bd" ]; then
            echo "                        identiques : la 1.0 n'est pas encore publiee"
        else
            vert  "                        DIFFERENTS : une mise a jour est disponible"
        fi
    else
        jaune "                        comparaison impossible"; pb=1
    fi

    echo "version reseau du jeu   $(version_reseau)"

    local monde
    monde=$(grep -oP '(?<=^NOM_MONDE=).*' /etc/valheim.env 2>/dev/null | tr -d '"' || true)
    echo "monde en cours          ${monde:-inconnu}"
    if [ -f "$MONDES/$monde.fwl" ]; then
        "$OUTIL" lire "$MONDES/$monde.fwl" \
            | awk '/^(seed|version_format|version_generateur) / { printf "%-24s%s\n", $1, $2 }'
    fi

    for s in valheim.service collecte-valheim.service; do
        printf '%-32s%s\n' "$s" "$(systemctl is-active $s)"
    done
    for t in redemarrage-valheim.timer sauvegarde-valheim.timer \
             notifie-discord-valheim.timer; do
        printf '%-32s%s\n' "$t" "$(systemctl is-active $t 2>/dev/null)"
    done

    if grep -q '^WEBHOOK=' "$CONF_DISCORD" 2>/dev/null; then
        echo "Discord                 configure"
    else
        jaune "Discord                 pas d'adresse de webhook ; les annonces seront muettes"
    fi

    echo "joueurs en jeu          $(joueurs_en_jeu || echo aucun)"

    local libre
    libre=$(df --output=avail -BG /srv/jeux | tail -1 | tr -dc '0-9')
    printf '%-24s%s Go\n' "place sur /srv/jeux" "$libre"
    # Une mise a jour majeure retelecharge l'essentiel des ~1,7 Go installes, et
    # la sauvegarde prealable ecrit une archive de plus.
    [ "${libre:-0}" -ge 10 ] || { jaune "moins de 10 Go libres, c'est juste"; pb=1; }

    local archives
    archives=$(sudo find /srv/jeux/sauvegardes -name 'valheim-*.tar.gz' -mtime -1 2>/dev/null | wc -l)
    printf '%-24s%s\n' "archives < 24 h" "$archives"
    [ "$archives" -ge 1 ] || { jaune "aucune sauvegarde recente"; pb=1; }

    for f in "$OUTIL" "$BASCULE" "$SAUVEGARDE" "$STEAMCMD"; do
        [ -x "$f" ] || { jaune "manque : $f"; pb=1; }
    done

    echo
    [ "$pb" -eq 0 ] && vert "pret." || jaune "des points sont a regler avant le jour J."
    return 0
}

action_attendre() {
    local bi
    bi=$(buildid_installe)
    [ -n "$bi" ] || mourir "buildid installe illisible"
    echo "buildid installe $bi ; interrogation de Steam toutes les ${INTERVALLE}s."
    echo "Ctrl+C pour arreter."
    while true; do
        local bd
        bd=$(buildid_distant)
        if [ -n "$bd" ] && [ "$bd" != "$bi" ]; then
            vert "nouveau buildid publie : $bd (installe : $bi)"
            annonce "🔔 Nouvelle version du serveur Valheim publiée sur Steam (build $bd). Mise à jour en attente."
            return 0
        fi
        printf '%s buildid %s, rien de neuf\n' "$(date +%H:%M:%S)" "${bd:-?}"
        sleep "$INTERVALLE"
    done
}

action_controle() {
    # Pense pour une minuterie : un seul appel, pas de boucle. Le marqueur evite
    # de reannoncer la meme sortie a chaque passage -- une annonce toutes les
    # quinze minutes pendant des heures ne servirait personne.
    local bi bd
    bi=$(buildid_installe); bd=$(buildid_distant)
    if [ -z "$bd" ] || [ -z "$bi" ]; then
        echo "comparaison impossible (installe=${bi:-?} publie=${bd:-?})"
        return 0
    fi
    if [ "$bi" = "$bd" ]; then
        echo "buildid $bi inchange"
        return 0
    fi
    if [ -f "$MARQUEUR" ] && grep -qx "$bd" "$MARQUEUR" 2>/dev/null; then
        echo "buildid $bd deja annonce"
        return 0
    fi
    vert "nouveau buildid publie : $bd (installe : $bi)"
    annonce "🔔 **Nouvelle version du serveur Valheim publiée sur Steam** (build \`$bd\`, installé \`$bi\`).
Le serveur n'est pas encore à jour : les clients en 1.0 seront refusés jusqu'à la mise à jour.
Prochaine étape, à lancer à la main : \`jour-j-valheim.sh --maj --confirm\`, puis \`--sonde\`, puis le monde neuf **NordheimV1**."
    mkdir -p "$(dirname "$MARQUEUR")"
    echo "$bd" >> "$MARQUEUR"
}

action_automatique() {
    # Enchaine tout, sans intervention : mise a jour, sonde, monde neuf avec une
    # seed tiree au hasard. Pensee pour une minuterie, donc chaque garde-fou
    # compte -- personne ne lira la sortie au moment ou elle passe.
    local aujourdhui
    aujourdhui=$(date +%F)
    if [ "$aujourdhui" \< "$PAS_AVANT" ]; then
        # Avant la date de sortie annoncee, on se contente de prevenir. Un
        # correctif mineur publie entre-temps ne doit pas archiver la partie.
        action_controle
        return 0
    fi

    local bi bd
    bi=$(buildid_installe); bd=$(buildid_distant)
    if [ -z "$bi" ] || [ -z "$bd" ] || [ "$bi" = "$bd" ]; then
        echo "rien a faire (installe=${bi:-?} publie=${bd:-?})"
        return 0
    fi
    if [ -e "$MONDES/$NOM_AUTO.fwl" ]; then
        echo "$NOM_AUTO existe deja : la bascule a deja eu lieu"
        return 0
    fi
    if [ "$CONFIRM" -eq 0 ]; then
        jaune "simulation : maj vers $bd, sonde, puis monde $NOM_AUTO a seed aleatoire."
        return 0
    fi

    # Le nom du monde en cours est relu ici : $ACTUEL appartient au script de
    # bascule, et sous « set -u » y faire reference depuis celui-ci aurait fait
    # echouer la chaine au moment ou elle annonce une erreur -- le pire moment.
    local en_place
    en_place=$(grep -oP '(?<=^NOM_MONDE=).*' /etc/valheim.env 2>/dev/null | tr -d '"' || true)

    annonce "🔔 **Valheim 1.0 est publié** (build \`$bd\`). Je lance la mise à jour, puis le monde neuf **$NOM_AUTO**. Le serveur revient dans quelques minutes."
    if ! action_maj; then
        annonce "⚠️ La mise à jour a échoué. Le monde **${en_place:-actuel}** est intact et le serveur reste sur l'ancienne version. Il faut regarder à la main."
        return 1
    fi
    if ! action_sonde; then
        annonce "⚠️ La sonde a échoué : je ne connais pas la version du générateur de monde, donc je ne crée pas le monde neuf. Le monde actuel est intact."
        return 1
    fi
    NOM="$NOM_AUTO"
    SEED=""      # tiree au hasard par le script de bascule
    FORCE=1      # les joueurs se reconnectent souvent juste apres la mise a jour
    action_monde
}

action_maj() {
    local bi bd
    bi=$(buildid_installe); bd=$(buildid_distant)
    echo "buildid installe $bi -> publie ${bd:-?}"
    local en_jeu; en_jeu=$(joueurs_en_jeu)
    [ -n "$en_jeu" ] && jaune "joueurs en jeu : $en_jeu ; ils seront deconnectes"

    if [ "$CONFIRM" -eq 0 ]; then
        jaune "simulation : sauvegarde, arret, app_update $APP validate, redemarrage."
        return 0
    fi

    annonce "🛠️ Mise à jour du serveur en cours, il revient dans quelques minutes."
    titre "sauvegarde"
    "$SAUVEGARDE"
    titre "arret"
    systemctl stop valheim.service
    titre "mise a jour SteamCMD"
    # validate reverifie chaque fichier : plus lent, mais c'est la seule facon
    # d'attraper une installation partielle apres une grosse mise a jour.
    sudo -u "$UTILISATEUR" env HOME="$MAISON" "$STEAMCMD" \
        +force_install_dir "$INSTALL" +login anonymous \
        +app_update "$APP" validate +quit
    local apres; apres=$(buildid_installe)
    echo "buildid apres mise a jour : $apres"
    [ "$apres" != "$bi" ] || jaune "le buildid n'a pas change"
    titre "redemarrage"
    systemctl start valheim.service
    for _ in $(seq 40); do
        systemctl is-active --quiet valheim.service || mourir "le serveur ne demarre pas ; envisage --retour-arriere"
        if sudo journalctl -u valheim --since '-3 min' --no-pager -o cat 2>/dev/null \
            | grep -q 'Load world'; then
            vert "serveur reparti, monde charge"
            annonce "✅ Serveur à jour (build $apres) et de retour en ligne."
            return 0
        fi
        sleep 5
    done
    mourir "pas de trace de chargement du monde apres la mise a jour"
}

action_sonde() {
    # On laisse le serveur creer un monde tout seul, dans un coin, et on lit le
    # .fwl qu'il ecrit. C'est la mesure directe de ce que la nouvelle version
    # change : inutile de speculer sur la generation de monde, la version du
    # generateur est inscrite dans le fichier.
    local en_jeu; en_jeu=$(joueurs_en_jeu)
    if [ -n "$en_jeu" ]; then
        # Un second serveur Unity prend un coeur et quelques Go le temps de
        # generer son monde. Ce n'est pas dangereux, mais ca peut faire tressauter
        # la partie en cours -- et au-dela de 150 ms de latence, les monstres se
        # teleportent pour tout le monde.
        jaune "joueurs en jeu ($en_jeu) : la sonde peut faire tressauter leur partie"
        jaune "une minute. Le jour J, elle passe apres la mise a jour, serveur vide."
    fi
    if [ "$CONFIRM" -eq 0 ]; then
        jaune "simulation : un serveur jetable sur le port $SONDE_PORT creerait un"
        jaune "monde dans $SONDE_DIR, et son .fwl serait lu puis efface."
        return 0
    fi
    rm -rf "$SONDE_DIR"; mkdir -p "$SONDE_DIR/worlds_local"
    chown -R "$UTILISATEUR:$UTILISATEUR" "$SONDE_DIR"
    local trace="$SONDE_DIR/sonde.log"
    sudo -u "$UTILISATEUR" env HOME="$SONDE_DIR" SteamAppId=892970 \
        LD_LIBRARY_PATH="$INSTALL/linux64" \
        "$INSTALL/valheim_server.x86_64" -nographics -batchmode \
        -name "Sonde" -port "$SONDE_PORT" -world "Sonde" \
        -password "sonde12345" -savedir "$SONDE_DIR" -public 0 \
        > "$trace" 2>&1 &
    local pid=$!   # le PID, pas un pgrep : un motif de recherche finirait par
                   # se reconnaitre lui-meme dans la ligne de commande.
    for _ in $(seq 60); do
        [ -f "$SONDE_DIR/worlds_local/Sonde.fwl" ] && break
        kill -0 "$pid" 2>/dev/null || break
        sleep 3
    done
    kill -INT "$pid" 2>/dev/null || true
    for _ in $(seq 20); do kill -0 "$pid" 2>/dev/null || break; sleep 2; done
    kill -9 "$pid" 2>/dev/null || true

    [ -f "$SONDE_DIR/worlds_local/Sonde.fwl" ] \
        || mourir "le serveur n'a pas cree de monde ; voir $trace"
    titre "ce que cette version ecrit dans un monde neuf"
    "$OUTIL" lire "$SONDE_DIR/worlds_local/Sonde.fwl"
    local gen actuel
    gen=$("$OUTIL" lire "$SONDE_DIR/worlds_local/Sonde.fwl" \
        | awk '/^version_generateur/ { print $2 }')
    actuel=$(grep -oP '(?<=^NOM_MONDE=).*' /etc/valheim.env | tr -d '"')
    if [ -f "$MONDES/$actuel.fwl" ]; then
        local avant
        avant=$("$OUTIL" lire "$MONDES/$actuel.fwl" \
            | awk '/^version_generateur/ { print $2 }')
        echo
        echo "generateur : monde actuel $avant  ->  version installee $gen"
        if [ "$avant" != "$gen" ]; then
            jaune "LA GENERATION DE MONDE A CHANGE."
            jaune "Aucune seed conseillee avant cette version n'est fiable : la meme"
            jaune "seed ne produit plus la meme carte. Choisis la seed sur un outil"
            jaune "de previsualisation a jour, ou en jeu."
            annonce "⚠️ La génération de monde a changé (générateur $avant → $gen). Les seeds repérées avant la mise à jour ne donnent plus la même carte."
        else
            vert "inchangee : une seed reperee avant la mise a jour tient toujours."
        fi
    fi
    echo
    echo "Passe cette valeur a --monde : le generateur $gen sera inscrit dans le"
    echo "monde neuf. Sans ca, le serveur refuserait le fichier."
    # Le resultat est ecrit hors du repertoire jetable, qu'on efface juste apres.
    # Sans ca --monde ne trouvait plus rien et retombait sur la valeur par
    # defaut : sur la 1.0, cela aurait pu produire un fichier refuse au
    # chargement, avec un message parlant de seed alors que le probleme etait
    # ailleurs.
    mkdir -p "$(dirname "$SONDE_RESULTAT")"
    printf '%s\n' "$gen" > "$SONDE_RESULTAT"
    rm -rf "$SONDE_DIR"
}

action_monde() {
    [ -n "$NOM" ] || mourir "--nom est obligatoire"
    local gen=""
    [ -s "$SONDE_RESULTAT" ] && gen=$(cat "$SONDE_RESULTAT")
    local args=(--nom "$NOM")
    [ -n "$SEED" ] && args+=(--seed "$SEED")
    [ -n "$gen" ] && args+=(--generateur "$gen")
    [ "$CONFIRM" -eq 1 ] && args+=(--confirm)
    # Transmis tel quel : le jour J, les joueurs se reconnectent souvent dans la
    # minute qui suit la mise a jour, et le garde-fou du script delegue bloquerait
    # la bascule alors qu'on veut justement l'enchainer.
    [ "$FORCE" -eq 1 ] && args+=(--force)
    "$BASCULE" "${args[@]}"
    if [ "$CONFIRM" -eq 1 ]; then
        # La seed est relue dans le fichier cree : sans --seed elle a ete tiree
        # au hasard par le script de bascule, et c'est cette valeur-la qu'il
        # faut annoncer pour que le groupe puisse regarder la carte en ligne.
        local vraie
        vraie=$("$OUTIL" lire "$MONDES/$NOM.fwl" 2>/dev/null \
            | awk '/^seed / { print $2 }' || true)
        annonce "🌍 **Nouveau monde en ligne : $NOM**
Seed : \`${vraie:-inconnue}\` — à coller sur valheim-map.world pour voir la carte.
Créez un personnage neuf. Les compteurs de défis repartent de zéro, dont celui de Bab-y : n'être jamais mort après avoir battu l'Ancien."
    fi
}

action_retour_arriere() {
    jaune "Reinstallation de la branche « default_old » (previous stable)."
    jaune "A n'utiliser que si la nouvelle version empeche le serveur de demarrer."
    if [ "$CONFIRM" -eq 0 ]; then
        jaune "simulation : app_update $APP -beta default_old validate."
        return 0
    fi
    systemctl stop valheim.service
    sudo -u "$UTILISATEUR" env HOME="$MAISON" "$STEAMCMD" \
        +force_install_dir "$INSTALL" +login anonymous \
        +app_update "$APP" -beta default_old validate +quit
    systemctl start valheim.service
    echo "buildid : $(buildid_installe)"
    jaune "Attention : un monde deja ouvert par la nouvelle version peut ne plus"
    jaune "etre lisible par l'ancienne. Les archives sont dans /srv/jeux/sauvegardes."
}

# ---------- deroulement ----------

case "$ACTION" in
    verifier) action_verifier ;;
    attendre) action_attendre ;;
    controle) action_controle ;;
    sonde|maj|monde|tout|automatique|retour-arriere)
        [ "$(id -u)" -eq 0 ] || mourir "a lancer avec sudo"
        mkdir -p "$JOURNAL"
        case "$ACTION" in
            maj) action_maj ;;
            sonde) action_sonde ;;
            monde) action_monde ;;
            automatique) action_automatique ;;
            retour-arriere) action_retour_arriere ;;
            tout)
                [ -n "$NOM" ] || mourir "--tout exige --nom"
                action_maj; action_sonde; action_monde ;;
        esac ;;
esac
