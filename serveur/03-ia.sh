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

  faire systemctl daemon-reload
  faire systemctl enable --now ollama

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

  succes "Interface web : http://$(ip_locale):${PORT_WEBUI}"
  info "Le premier compte créé sur cette page devient administrateur — fais-le tout de suite."
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
    attention "L'URL de téléchargement de LM Studio change à chaque version et le site"
    attention "ne publie pas de lien stable exploitable en script."
    info "Marche à suivre :"
    printf '      1. Ouvrir https://lmstudio.ai/download depuis un navigateur\n'
    printf '      2. Télécharger la version Linux (.AppImage)\n'
    printf '      3. sudo mv ~/Téléchargements/LM-Studio-*.AppImage /opt/lmstudio/LM-Studio.AppImage\n'
    printf '      4. sudo chmod +x /opt/lmstudio/LM-Studio.AppImage\n'
    printf '      5. Relancer ce script : le raccourci sera créé automatiquement\n'
    return 0
  fi

  info "Création du raccourci d'application"
  faire tee /usr/share/applications/lmstudio.desktop >/dev/null <<'FIN'
[Desktop Entry]
Name=LM Studio
Comment=Exécution de modèles de langage en local
Exec=/opt/lmstudio/LM-Studio.AppImage
Icon=applications-science
Terminal=false
Type=Application
Categories=Development;Science;
FIN

  succes "LM Studio installé"
  info "Configure son dossier de modèles sur ${RACINE_IA}/lmstudio pour ne pas saturer le disque système."
  faire mkdir -p "${RACINE_IA}/lmstudio"

  if [[ -n "${SUDO_USER:-}" ]]; then
    faire chown -R "${SUDO_USER}:${SUDO_USER}" "${RACINE_IA}/lmstudio"
  fi
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
