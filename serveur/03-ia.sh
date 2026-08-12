#!/usr/bin/env bash
#
# 03-ia.sh — Installe la pile d'inférence locale.
#
#   sudo ./serveur/03-ia.sh            # simulation
#   sudo ./serveur/03-ia.sh --confirm  # exécution réelle
#
# Deux briques, deux usages :
#
#   Ollama + Open WebUI  Le cœur serveur. API sur le réseau local (port 11434)
#                        et interface de chat dans le navigateur (port 8080),
#                        accessibles depuis n'importe quel appareil de la maison.
#
#   LM Studio            Application de bureau, demandée explicitement. Utile
#                        devant un écran pour explorer et comparer des modèles.
#                        Sans session graphique, Ollama couvre déjà le besoin.
#
# Les modèles sont choisis selon la VRAM et la RAM réellement mesurées.

set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${ICI}/lib/common.sh"

CONFIRME=0
SAUTER_LMSTUDIO="${SAUTER_LMSTUDIO:-0}"
SAUTER_WEBUI="${SAUTER_WEBUI:-0}"
SAUTER_MODELES="${SAUTER_MODELES:-0}"

PORT_OLLAMA=11434
PORT_WEBUI=8080

# Lien de téléchargement stable : le site redirige de lui-même vers la dernière
# version publiée, il n'y a donc pas de numéro de version à maintenir ici.
URL_LMSTUDIO="https://lmstudio.ai/download/latest/linux/x64?format=AppImage"

usage() {
  cat <<'FIN'
Usage : sudo ./03-ia.sh [--confirm]

  --confirm      Exécute réellement. Sans ce drapeau, affiche seulement le plan.

Variables d'environnement :
  SAUTER_LMSTUDIO=1   N'installe pas LM Studio
  SAUTER_WEBUI=1      N'installe pas Open WebUI (ni Docker)
  SAUTER_MODELES=1    N'télécharge aucun modèle
  RACINE_IA=/chemin   Emplacement des modèles (défaut : /srv/ia)
FIN
}

faire() {
  if (( CONFIRME )); then
    "$@"
  else
    printf '      %s%s%s\n' "$C_JAUNE" "$*" "$C_FIN" >&2
  fi
}

# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

installer_ollama() {
  titre "Ollama (moteur d'inférence)"

  if dispo ollama; then
    succes "Ollama déjà installé ($(ollama --version 2>/dev/null | head -n1))"
  else
    info "Installation depuis le script officiel"
    # Le script officiel détecte le GPU et installe les bibliothèques CUDA/ROCm
    # correspondantes — c'est la voie recommandée en amont.
    faire bash -c 'curl -fsSL https://ollama.com/install.sh | sh'
  fi

  configurer_service_ollama
}

# Tant qu'OLLAMA_MODELS n'est pas défini, Ollama range ses modèles dans
# /usr/share/ollama/.ollama/models, sur le disque système. Les y laisser au
# moment où l'on bascule vers le disque dédié aurait deux effets fâcheux : le
# service reconfiguré ne les verrait plus (« aucun modèle installé » alors
# qu'ils sont bien là), et plusieurs Gio resteraient à occuper la partition
# système pour rien.
migrer_modeles_existants() {
  local defaut=/usr/share/ollama/.ollama/models
  local cible="${RACINE_IA}/ollama"

  [[ -d "$defaut" ]] || return 0
  [[ "$defaut" != "$cible" ]] || return 0
  [[ -n "$(ls -A "$defaut" 2>/dev/null)" ]] || return 0

  # Des modèles des deux côtés : fusionner à l'aveugle pourrait écraser des
  # manifestes divergents. Mieux vaut le signaler que décider à la place.
  if [[ -n "$(ls -A "$cible" 2>/dev/null)" ]]; then
    attention "Modèles présents à la fois dans ${defaut} et ${cible}."
    attention "Migration ignorée : fusionne les deux à la main, puis relance."
    return 0
  fi

  info "Déplacement des modèles déjà téléchargés vers ${cible} ($(du -sh "$defaut" 2>/dev/null | cut -f1))"
  # À l'arrêt : déplacer les blobs sous le nez d'un service qui tourne, c'est
  # se garantir une lecture à mi-copie.
  faire systemctl stop ollama
  faire cp -a "${defaut}/." "${cible}/"
  faire rm -rf "$defaut"
  if id ollama >/dev/null 2>&1; then
    faire chown -R ollama:ollama "$cible"
  fi
}

configurer_service_ollama() {
  info "Configuration du service systemd"

  local sous_reseau
  sous_reseau="$(sous_reseau_local)"

  # Par défaut Ollama n'écoute que sur 127.0.0.1 : inutilisable depuis un autre
  # appareil. On l'ouvre sur le réseau local, et le pare-feu limite la portée.
  #
  # OLLAMA_MODELS place les fichiers sur le disque dédié : un seul modèle peut
  # peser 45 Gio, la partition système serait vite saturée.
  #
  # OLLAMA_KEEP_ALIVE garde le modèle chargé en mémoire entre deux requêtes ;
  # sans ça chaque question repaie plusieurs secondes de chargement.
  faire mkdir -p /etc/systemd/system/ollama.service.d
  faire tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<FIN
[Service]
Environment="OLLAMA_HOST=0.0.0.0:${PORT_OLLAMA}"
Environment="OLLAMA_MODELS=${RACINE_IA}/ollama"
Environment="OLLAMA_KEEP_ALIVE=30m"
FIN

  faire mkdir -p "${RACINE_IA}/ollama"
  # Le service tourne sous l'utilisateur « ollama » créé par l'installeur.
  if id ollama >/dev/null 2>&1; then
    faire chown -R ollama:ollama "${RACINE_IA}/ollama"
  fi

  migrer_modeles_existants

  faire systemctl daemon-reload
  # `enable --now` ne redémarre PAS un service déjà actif — or le script
  # officiel démarre Ollama dès son installation, donc avant que l'override
  # n'existe. Sans redémarrage explicite, le processus continue de tourner
  # sans OLLAMA_MODELS ni OLLAMA_HOST : les modèles atterrissent sur le disque
  # système et l'API n'écoute que sur 127.0.0.1, alors que le récapitulatif
  # annonce l'adresse du réseau local.
  faire systemctl enable ollama
  faire systemctl restart ollama

  if (( CONFIRME )); then
    attendre_ollama || attention "Ollama ne répond pas encore, vérifie : systemctl status ollama"
  fi

  succes "API Ollama : http://$(ip_locale):${PORT_OLLAMA}"

  if [[ -n "$sous_reseau" ]]; then
    info "Ouverture du port ${PORT_OLLAMA} pour ${sous_reseau} uniquement"
    if dispo ufw; then
      faire ufw allow from "$sous_reseau" to any port "$PORT_OLLAMA" proto tcp
    fi
  else
    attention "Sous-réseau local indéterminé : le port ${PORT_OLLAMA} n'est pas ouvert dans ufw."
    attention "N'expose jamais cette API sur Internet — elle n'a aucune authentification."
  fi
}

attendre_ollama() {
  local _
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${PORT_OLLAMA}/api/tags" >/dev/null 2>&1; then
      succes "Ollama répond"
      return 0
    fi
    sleep 1
  done
  return 1
}

# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------

# Renvoie, un par ligne, les modèles à essayer par ordre de préférence.
#
# Les noms de modèles apparaissent et disparaissent du registre. Plutôt que de
# figer une référence qui finira par ne plus exister, on propose une liste de
# candidats et le script retient le premier qui se télécharge réellement.
choisir_modeles() {
  local vram ram
  vram="$(vram_gio)"
  ram="$(ram_gio)"

  # Sans GPU, c'est la RAM qui contraint, et il faut garder de la marge pour le
  # système : on raisonne sur environ la moitié de la mémoire installée.
  local budget_gio="$vram"
  if (( vram < 4 )); then
    budget_gio=$(( ram / 2 ))
  fi

  if (( budget_gio >= 24 )); then
    printf 'hermes4:70b\nhermes3:70b\nhermes4:14b\nhermes3:8b\n'
  elif (( budget_gio >= 12 )); then
    printf 'hermes4:14b\nhermes3:8b\nhermes4:8b\n'
  elif (( budget_gio >= 6 )); then
    printf 'hermes3:8b\nhermes4:8b\n'
  else
    printf 'hermes3:3b\nhermes3:8b\n'
  fi
}

installer_modeles() {
  titre "Modèles Hermes"

  if [[ "$SAUTER_MODELES" == "1" ]]; then
    info "Ignoré (SAUTER_MODELES=1)"
    return 0
  fi

  info "Matériel : $(vram_gio) Gio de VRAM, $(ram_gio) Gio de RAM"

  local candidats
  candidats="$(choisir_modeles)"
  info "Candidats par ordre de préférence : $(tr '\n' ' ' <<<"$candidats")"

  if ! (( CONFIRME )); then
    printf '      %sollama pull <premier candidat disponible>%s\n' "$C_JAUNE" "$C_FIN"
    return 0
  fi

  local modele
  local installe=""
  while read -r modele; do
    [[ -n "$modele" ]] || continue
    info "Tentative de téléchargement : ${modele}"
    if ollama pull "$modele" 2>&1 | sed 's/^/      /'; then
      installe="$modele"
      succes "Modèle installé : ${modele}"
      break
    fi
    attention "${modele} indisponible dans le registre, essai suivant"
  done <<<"$candidats"

  if [[ -z "$installe" ]]; then
    attention "Aucun modèle Hermes n'a pu être téléchargé."
    attention "Cherche les variantes disponibles sur https://ollama.com/search?q=hermes"
    attention "puis : ollama pull <nom>"
    return 0
  fi

  # Un modèle d'embeddings est indispensable dès qu'on veut interroger ses
  # propres documents depuis Open WebUI.
  info "Téléchargement d'un modèle d'embeddings (recherche documentaire)"
  ollama pull nomic-embed-text 2>&1 | sed 's/^/      /' || \
    attention "Échec du téléchargement des embeddings, sans conséquence pour le chat"

  tester_inference "$installe"
}

# Mesure concrète du débit : un chiffre vaut mieux qu'une promesse.
tester_inference() {
  local modele="$1"
  titre "Test d'inférence"

  info "Requête de test sur ${modele}…"

  # La réponse passe par un fichier plutôt que par une variable : elle contient
  # du JSON avec guillemets et retours à la ligne, qu'il ne faut jamais
  # réinjecter dans un script.
  local fichier
  fichier="$(mktemp)"
  # shellcheck disable=SC2064  # on veut figer le chemin maintenant, pas à la sortie
  trap "rm -f '${fichier}'" RETURN

  if ! curl -fsS "http://127.0.0.1:${PORT_OLLAMA}/api/generate" \
       -H 'Content-Type: application/json' \
       --data-binary @- >"$fichier" 2>/dev/null <<FIN
{"model": "${modele}",
 "prompt": "Réponds en une phrase : à quoi sert un serveur ?",
 "stream": false}
FIN
  then
    attention "Le test a échoué. Vérifie : systemctl status ollama"
    return 0
  fi

  # Ollama renvoie les compteurs de tokens et les durées en nanosecondes.
  local resultat
  resultat="$(python3 - "$fichier" <<'PY' 2>/dev/null || true
import json, sys

with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)

n = d.get("eval_count", 0)
t = d.get("eval_duration", 0)
print(f"{n / (t / 1e9):.1f}" if n and t else "")
print(" ".join(d.get("response", "").split())[:200])
PY
)"

  local debit reponse
  debit="$(sed -n '1p' <<<"$resultat")"
  reponse="$(sed -n '2p' <<<"$resultat")"

  [[ -n "$reponse" ]] && printf '      Réponse : %s\n' "$reponse"

  if [[ -n "$debit" ]]; then
    succes "Débit mesuré : ${debit} tokens/seconde"
    # Repère d'interprétation : en dessous de ~5 t/s la conversation devient pénible.
    if (( ${debit%%.*} < 5 )); then
      attention "C'est lent pour un usage conversationnel. Un modèle plus petit,"
      attention "ou une carte graphique, améliorerait nettement le confort."
    fi
  fi
}

# ---------------------------------------------------------------------------
# Open WebUI
# ---------------------------------------------------------------------------

installer_webui() {
  titre "Open WebUI (interface de chat)"

  if [[ "$SAUTER_WEBUI" == "1" ]]; then
    info "Ignoré (SAUTER_WEBUI=1)"
    return 0
  fi

  if ! dispo docker; then
    info "Installation de Docker"
    faire apt-get install -y docker.io
    faire systemctl enable --now docker
  else
    succes "Docker déjà installé"
  fi

  faire mkdir -p "${RACINE_IA}/openwebui"

  # Le conteneur est recréé à chaque exécution, mais les données (comptes,
  # historique de conversation) vivent dans le volume monté : rien n'est perdu.
  if (( CONFIRME )) && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx open-webui; then
    info "Conteneur existant : suppression avant recréation (les données sont conservées)"
    faire docker rm -f open-webui
  fi

  info "Démarrage du conteneur Open WebUI"
  faire docker run -d \
    --name open-webui \
    --restart unless-stopped \
    --add-host=host.docker.internal:host-gateway \
    -p "${PORT_WEBUI}:8080" \
    -e "OLLAMA_BASE_URL=http://host.docker.internal:${PORT_OLLAMA}" \
    -v "${RACINE_IA}/openwebui:/app/backend/data" \
    ghcr.io/open-webui/open-webui:main

  local sous_reseau
  sous_reseau="$(sous_reseau_local)"
  if [[ -n "$sous_reseau" ]]; then
    info "Ouverture du port ${PORT_WEBUI} pour ${sous_reseau} uniquement"
    if dispo ufw; then
      faire ufw allow from "$sous_reseau" to any port "$PORT_WEBUI" proto tcp
    fi
  fi

  autoriser_conteneurs_vers_ollama
  restreindre_docker_au_reseau_local

  succes "Interface web : http://$(ip_locale):${PORT_WEBUI}"
  info "Le premier compte créé sur cette page devient administrateur — fais-le tout de suite."
}

# ---------------------------------------------------------------------------
# Pare-feu et conteneurs
#
# Docker court-circuite ufw. Ses règles de traduction d'adresse s'appliquent
# avant que le paquet n'atteigne les chaînes d'ufw : un port publié par un
# conteneur est donc joignable même quand « ufw status » affiche une restriction
# dessus. La règle « 8080 depuis le réseau local seulement » posée juste au-dessus
# ne protège en réalité que les services de l'hôte, pas Open WebUI.
#
# La seule chaîne que Docker et ufw respectent tous les deux est DOCKER-USER :
# la chaîne FORWARD la consulte avant les règles de Docker, et Docker ne la vide
# jamais, précisément pour qu'on puisse y mettre ce genre de politique.
#
# On l'alimente depuis after.rules, qu'ufw rejoue à chaque « ufw reload » et au
# démarrage de la machine. Le « -F » en tête du bloc rend l'opération rejouable :
# ufw applique ces fichiers avec iptables-restore -n, sans vidage préalable, si
# bien que sans lui les règles s'accumuleraient en double à chaque rechargement.
#
# IPv6 mérite le même traitement, et plus encore : la machine a une adresse
# publique routable, sans NAT pour la masquer.
# ---------------------------------------------------------------------------

MARQUEUR_DEBUT='# >>> serveur-ia : restriction des conteneurs (03-ia.sh) >>>'
MARQUEUR_FIN='# <<< serveur-ia <<<'

# Open WebUI joint Ollama par host.docker.internal, qui pointe sur l'adresse de
# la passerelle du pont Docker (172.17.0.1). La destination est donc l'hôte
# lui-même : ce trafic traverse INPUT, pas FORWARD, et se heurte à la règle qui
# n'ouvre le port 11434 qu'au sous-réseau local. Le conteneur, lui, sort en
# 172.17.0.x — il était donc silencieusement rejeté, et l'interface de chat
# s'affichait sans aucun modèle disponible.
#
# On autorise explicitement l'entrée depuis le pont Docker. La règle est posée
# sur l'interface plutôt que sur le sous-réseau 172.17.0.0/16 : ainsi une
# adresse du réseau local usurpant une IP de conteneur n'en profite pas.
autoriser_conteneurs_vers_ollama() {
  dispo ufw || return 0

  info "Autorisation du pont Docker vers le port ${PORT_OLLAMA} (Open WebUI → Ollama)"
  faire ufw allow in on docker0 to any port "$PORT_OLLAMA" proto tcp
}

restreindre_docker_au_reseau_local() {
  info "Restriction des conteneurs au réseau local (chaîne DOCKER-USER)"

  if ! dispo ufw; then
    attention "ufw absent : aucune restriction posée sur les conteneurs."
    return 0
  fi

  local interface sous_reseau prefixe6
  interface="$(interface_defaut)"
  sous_reseau="$(sous_reseau_local)"
  prefixe6="$(prefixe_ipv6_local)"

  if [[ -z "$interface" || -z "$sous_reseau" ]]; then
    attention "Interface ou sous-réseau indéterminés : restriction non posée."
    attention "Le port ${PORT_WEBUI} du conteneur reste joignable au-delà du réseau local."
    return 0
  fi

  # Ordre des règles : on laisse passer les réponses aux connexions déjà
  # établies, puis le réseau local, puis on jette tout ce qui entre encore par
  # l'interface physique. Le trafic sortant d'un conteneur arrive avec
  # « -i docker0 » et n'est donc pas concerné par ce rejet.
  local bloc4
  bloc4="$(cat <<FIN
${MARQUEUR_DEBUT}
*filter
:DOCKER-USER - [0:0]
-F DOCKER-USER
-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -s ${sous_reseau} -j RETURN
-A DOCKER-USER -i ${interface} -j DROP
-A DOCKER-USER -j RETURN
COMMIT
${MARQUEUR_FIN}
FIN
)"

  # fe80::/10 doit rester autorisé : la découverte de voisins et l'autoconfi-
  # guration passent par là, les bloquer casse IPv6 de façon déroutante.
  local regle_prefixe6=''
  if [[ -n "$prefixe6" ]]; then
    regle_prefixe6="-A DOCKER-USER -s ${prefixe6} -j RETURN"
  fi

  local bloc6
  bloc6="$(cat <<FIN
${MARQUEUR_DEBUT}
*filter
:DOCKER-USER - [0:0]
-F DOCKER-USER
-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -s fe80::/10 -j RETURN
${regle_prefixe6}
-A DOCKER-USER -i ${interface} -j DROP
-A DOCKER-USER -j RETURN
COMMIT
${MARQUEUR_FIN}
FIN
)"

  # Une ligne vide dans un fichier iptables-restore est acceptée, mais autant
  # ne pas en produire quand la machine n'a pas d'adresse IPv6 globale.
  bloc6="$(grep -v '^$' <<<"$bloc6")"

  appliquer_bloc_ufw /etc/ufw/after.rules  "$bloc4"
  appliquer_bloc_ufw /etc/ufw/after6.rules "$bloc6"

  faire ufw reload

  if (( CONFIRME )); then
    if iptables -S DOCKER-USER 2>/dev/null | grep -q -- "-i ${interface} -j DROP"; then
      succes "Conteneurs joignables depuis ${sous_reseau} uniquement"
      if [[ -n "$prefixe6" ]]; then
        info "En IPv6 : depuis ${prefixe6} uniquement. Ce préfixe est délégué par la"
        info "box et peut changer — relancer ce script si l'accès IPv6 cesse de marcher."
      fi
    else
      attention "La chaîne DOCKER-USER ne contient pas la règle attendue."
      attention "Vérifie : iptables -S DOCKER-USER"
    fi
  fi
}

# Remplace le bloc délimité par les marqueurs dans un fichier de règles ufw,
# ou l'ajoute s'il n'y est pas encore. Le contenu est réécrit par redirection
# pour conserver le propriétaire et les droits du fichier d'origine (0640 root).
appliquer_bloc_ufw() {
  local fichier="$1" bloc="$2"

  if ! (( CONFIRME )); then
    printf '      %s# %s recevrait :%s\n' "$C_JAUNE" "$fichier" "$C_FIN"
    local ligne
    while IFS= read -r ligne; do
      printf '      %s%s%s\n' "$C_JAUNE" "$ligne" "$C_FIN"
    done <<<"$bloc"
    return 0
  fi

  [[ -f "$fichier" ]] || fatal "${fichier} est absent : ufw est-il bien installé ?"

  local temporaire
  temporaire="$(mktemp)"

  # Comparaison de chaînes exacte plutôt qu'une expression rationnelle : les
  # marqueurs contiennent des caractères que sed interpréterait.
  awk -v debut="$MARQUEUR_DEBUT" -v fin="$MARQUEUR_FIN" '
    $0 == debut { dans = 1; next }
    $0 == fin   { dans = 0; next }
    !dans       { print }
  ' "$fichier" >"$temporaire"

  printf '%s\n' "$bloc" >>"$temporaire"
  cat "$temporaire" >"$fichier"
  rm -f "$temporaire"

  succes "Bloc écrit dans ${fichier}"
}

# ---------------------------------------------------------------------------
# LM Studio
# ---------------------------------------------------------------------------

installer_lmstudio() {
  titre "LM Studio (application de bureau)"

  if [[ "$SAUTER_LMSTUDIO" == "1" ]]; then
    info "Ignoré (SAUTER_LMSTUDIO=1)"
    return 0
  fi

  # Sans serveur graphique, l'AppImage ne se lancera pas. On le signale sans
  # bloquer : l'utilisateur peut brancher un écran plus tard.
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]] && ! systemctl list-units --type=target 2>/dev/null | grep -q graphical.target; then
    attention "Aucune session graphique détectée : LM Studio ne pourra pas s'ouvrir ici."
    attention "Ollama et Open WebUI couvrent déjà l'usage serveur."
    info "Installation quand même, pour le jour où un écran sera branché."
  fi

  faire mkdir -p /opt/lmstudio

  # L'AppImage a besoin de FUSE pour se monter ; absent d'une install serveur.
  installer_paquet libfuse2t64 || installer_paquet libfuse2 || true

  if [[ -x /opt/lmstudio/LM-Studio.AppImage ]]; then
    succes "LM Studio déjà présent dans /opt/lmstudio"
  else
    info "Téléchargement de LM Studio (environ 1 Gio)"
    faire curl -fL --retry 3 --retry-delay 5 \
      -o /opt/lmstudio/LM-Studio.AppImage "$URL_LMSTUDIO"

    if (( CONFIRME )) && ! appimage_valide /opt/lmstudio/LM-Studio.AppImage; then
      attention "Le fichier récupéré n'est pas une AppImage exploitable (téléchargement"
      attention "interrompu, ou page d'erreur servie à la place du binaire)."
      faire rm -f /opt/lmstudio/LM-Studio.AppImage
      info "À la main : https://lmstudio.ai/download, puis"
      printf '      sudo mv ~/Téléchargements/LM-Studio-*.AppImage /opt/lmstudio/LM-Studio.AppImage\n'
      printf '      sudo chmod +x /opt/lmstudio/LM-Studio.AppImage && relancer ce script\n'
      return 0
    fi

    faire chmod 0755 /opt/lmstudio/LM-Studio.AppImage
  fi

  # L'icône vit dans l'AppImage : l'extraire évite un raccourci à l'icône
  # générique. En cas d'échec, on retombe sur un thème système.
  local icone=applications-science
  if (( CONFIRME )) && extraire_icone_lmstudio; then
    icone=/opt/lmstudio/lm-studio.png
  fi

  info "Création du raccourci d'application"
  faire tee /usr/share/applications/lmstudio.desktop >/dev/null <<FIN
[Desktop Entry]
Name=LM Studio
Comment=Exécution de modèles de langage en local
Exec=/opt/lmstudio/LM-Studio.AppImage %U
Icon=${icone}
Terminal=false
Type=Application
Categories=Development;Science;
StartupWMClass=LM Studio
FIN
  faire update-desktop-database /usr/share/applications

  succes "LM Studio installé"
  faire mkdir -p "${RACINE_IA}/lmstudio"

  local compte
  compte="$(utilisateur_cible)"
  if [[ -n "$compte" ]]; then
    faire chown -R "${compte}:${compte}" "${RACINE_IA}/lmstudio"
  else
    attention "Compte utilisateur indéterminé : ${RACINE_IA}/lmstudio reste à root,"
    attention "LM Studio ne pourra pas y écrire. Corrige à la main : chown -R <toi> ${RACINE_IA}/lmstudio"
  fi

  configurer_reglages_lmstudio "$compte"
}

# Trois réglages que l'application ne devinera pas, et qui coûtent cher à
# découvrir en cours de route :
#
#   downloadsFolder      Par défaut les modèles vont dans le dossier personnel,
#                        sur le disque système. Un seul modèle pèse plusieurs
#                        gibioctets : la partition se remplit vite.
#
#   defaultContextLength Certains modèles annoncent une fenêtre énorme — 262 000
#                        jetons pour Qwen3.5 — que la VRAM ne peut pas suivre.
#                        Le cache d'attention grandit avec elle, et le chargement
#                        échoue ou déborde sur le processeur. 8192 tient partout.
#
#   alwaysAllowLoadAnyway  Le garde-fou en mode « high » refuse des chargements
#                        que la VRAM permettrait pourtant. On le garde — son
#                        avertissement est utile — mais on autorise à passer
#                        outre, sinon un modèle chargeable reste inaccessible.
#
# Fusion plutôt qu'écrasement : le fichier contient aussi tout l'état de
# l'interface, qu'on n'a aucune raison de réinitialiser.
configurer_reglages_lmstudio() {
  local compte="$1"
  local maison reglages

  maison="$(dossier_personnel "$compte")"
  if [[ -z "$maison" ]]; then
    attention "Dossier personnel introuvable : réglages de LM Studio non appliqués."
    return 0
  fi
  reglages="${maison}/.lmstudio/settings.json"

  # L'application réécrit ce fichier en quittant : une modification faite
  # pendant qu'elle tourne serait perdue sans prévenir.
  if ps -eo comm= 2>/dev/null | grep -qi 'lm.studio'; then
    attention "LM Studio est en cours d'exécution : ferme-le puis relance ce script"
    attention "pour appliquer le dossier de modèles, le contexte et le garde-fou."
    return 0
  fi

  info "Réglages de LM Studio (dossier de modèles, contexte 8192, garde-fou)"

  # Le fichier contient l'état complet de l'interface : on le modifie avec un
  # outil qui comprend le JSON, jamais à coups de sed.
  installer_paquet jq || true
  if ! dispo jq; then
    attention "jq indisponible : réglages de LM Studio non appliqués."
    attention "À faire dans l'application : dossier de modèles ${RACINE_IA}/lmstudio,"
    attention "contexte 8192, et « toujours autoriser le chargement »."
    return 0
  fi

  if ! (( CONFIRME )); then
    printf '      %sfusion dans %s :%s\n' "$C_JAUNE" "$reglages" "$C_FIN"
    printf '      %sdownloadsFolder=%s/lmstudio, defaultContextLength=8192,%s\n' \
      "$C_JAUNE" "$RACINE_IA" "$C_FIN"
    printf '      %smodelLoadingGuardrails.alwaysAllowLoadAnyway=true%s\n' \
      "$C_JAUNE" "$C_FIN"
    return 0
  fi

  mkdir -p "$(dirname "$reglages")"
  [[ -f "$reglages" ]] || printf '{}\n' >"$reglages"

  local temporaire
  temporaire="$(mktemp)"

  # `// {}` protège des clés absentes : sur un fichier fraîchement créé,
  # .modelLoadingGuardrails vaut null, et null + {} échouerait.
  if jq --arg dossier "${RACINE_IA}/lmstudio" '
        .downloadsFolder = $dossier
      | .defaultContextLength = { type: "custom", value: 8192 }
      | .modelLoadingGuardrails =
          ((.modelLoadingGuardrails // {}) + { alwaysAllowLoadAnyway: true })
     ' "$reglages" >"$temporaire" && [[ -s "$temporaire" ]]; then
    cat "$temporaire" >"$reglages"
    [[ -n "$compte" ]] && chown "${compte}:${compte}" "$reglages"
    succes "Réglages écrits dans ${reglages}"
  else
    attention "Fusion impossible dans ${reglages} — fichier laissé intact."
    attention "À faire dans l'application : dossier de modèles ${RACINE_IA}/lmstudio,"
    attention "contexte 8192, et « toujours autoriser le chargement »."
  fi

  rm -f "$temporaire"
}

# Une AppImage de type 2 est un ELF dont les octets 8 à 10 valent « AI\x02 ».
# Le contrôle attrape le cas courant : une page HTML d'erreur enregistrée sous
# le nom du binaire, qu'un simple test d'existence laisserait passer.
appimage_valide() {
  local fichier="$1"
  [[ -s "$fichier" ]] || return 1
  (( $(stat -c %s "$fichier" 2>/dev/null || echo 0) > 100000000 )) || return 1
  [[ "$(od -An -tx1 -j8 -N3 "$fichier" 2>/dev/null | tr -d ' \n')" == "414902" ]]
}

# Récupère l'icône livrée dans l'AppImage. Le chemin interne « lm-studio.png »
# de la racine est un lien symbolique ; on va donc chercher le vrai fichier.
extraire_icone_lmstudio() {
  [[ -f /opt/lmstudio/lm-studio.png ]] && return 0

  local temp
  temp="$(mktemp -d)" || return 1

  # --appimage-extract est traité par le lanceur de l'AppImage sans démarrer
  # l'application : utilisable en root, contrairement à Electron qui refuse.
  if ! ( cd "$temp" && /opt/lmstudio/LM-Studio.AppImage \
         --appimage-extract 'usr/share/icons/*' ) >/dev/null 2>&1; then
    rm -rf "$temp"
    return 1
  fi

  local trouvee
  trouvee="$(find "${temp}/squashfs-root" -type f -name 'lm-studio.png' \
    -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -n1 | cut -f2)"

  if [[ -n "$trouvee" ]]; then
    install -m 0644 "$trouvee" /opt/lmstudio/lm-studio.png
    rm -rf "$temp"
    return 0
  fi

  rm -rf "$temp"
  return 1
}

# Installe un paquet unique, sans échouer si son nom n'existe pas dans la
# distribution (les noms varient entre versions d'Ubuntu).
installer_paquet() {
  local paquet="$1"
  if dpkg-query -W -f='${Status}' "$paquet" 2>/dev/null | grep -q "ok installed"; then
    return 0
  fi
  if ! apt-cache show "$paquet" >/dev/null 2>&1; then
    return 1
  fi
  faire apt-get install -y "$paquet"
}

# ---------------------------------------------------------------------------

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --confirm) CONFIRME=1 ;;
      -h|--help) usage; exit 0 ;;
      *)         fatal "Option inconnue : $1" ;;
    esac
    shift
  done

  exiger_root "$@"
  demarrer_journal "03-ia"

  if ! (( CONFIRME )); then
    attention "Mode simulation : les commandes en jaune seraient exécutées, rien n'est modifié."
    attention "Pour exécuter réellement : sudo $0 --confirm"
  fi

  if [[ ! -d "$RACINE_IA" ]]; then
    attention "${RACINE_IA} n'existe pas — lance d'abord ./serveur/01-disques.sh"
    faire mkdir -p "$RACINE_IA"
  fi

  installer_ollama
  installer_modeles
  installer_webui
  installer_lmstudio

  echo
  if (( CONFIRME )); then
    titre "Récapitulatif"
    printf '      Interface de chat : http://%s:%s\n' "$(ip_locale)" "$PORT_WEBUI"
    printf '      API Ollama        : http://%s:%s\n' "$(ip_locale)" "$PORT_OLLAMA"
    printf '      Modèles installés :\n'
    ollama list 2>/dev/null | sed 's/^/        /' || true
    echo
    succes "Pile IA opérationnelle."
    info "Serveurs de jeu quand tu veux : sudo ./serveur/04-jeux.sh --confirm"
  else
    info "Simulation terminée. Rien n'a été modifié."
  fi
}

main "$@"
