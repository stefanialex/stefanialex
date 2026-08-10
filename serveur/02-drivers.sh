#!/usr/bin/env bash
#
# 02-drivers.sh — Pilotes graphiques et réglages système pour un usage serveur.
#
#   sudo ./serveur/02-drivers.sh            # simulation
#   sudo ./serveur/02-drivers.sh --confirm  # exécution réelle
#
# Le script s'adapte au GPU détecté (NVIDIA / AMD / Intel / aucun) et applique
# les réglages qui distinguent un serveur d'un poste de bureau : pas de mise en
# veille, fréquence CPU constante, accès SSH, pare-feu.
#
# Idempotent : relancer ne casse rien et ne duplique aucune configuration.

set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${ICI}/lib/common.sh"

CONFIRME=0
SAUTER_SSH="${SAUTER_SSH:-0}"
SAUTER_PARE_FEU="${SAUTER_PARE_FEU:-0}"

usage() {
  cat <<'FIN'
Usage : sudo ./02-drivers.sh [--confirm]

  --confirm      Exécute réellement. Sans ce drapeau, affiche seulement le plan.

Variables d'environnement :
  SAUTER_SSH=1        N'installe et ne configure pas OpenSSH
  SAUTER_PARE_FEU=1   Ne touche pas à ufw
FIN
}

# Exécute la commande, ou l'affiche seulement en mode simulation.
faire() {
  if (( CONFIRME )); then
    "$@"
  else
    printf '      %s%s%s\n' "$C_JAUNE" "$*" "$C_FIN" >&2
  fi
}

# Installe les paquets manquants uniquement — évite de retélécharger à chaque run.
installer() {
  local manquants=()
  local paquet
  for paquet in "$@"; do
    if ! dpkg-query -W -f='${Status}' "$paquet" 2>/dev/null | grep -q "ok installed"; then
      manquants+=("$paquet")
    fi
  done

  if [[ ${#manquants[@]} -eq 0 ]]; then
    succes "Déjà installé : $*"
    return 0
  fi

  info "À installer : ${manquants[*]}"
  faire apt-get install -y "${manquants[@]}"
}

# ---------------------------------------------------------------------------
# Pilotes graphiques
# ---------------------------------------------------------------------------

configurer_gpu() {
  local gpu
  gpu="$(detecter_gpu)"

  titre "Carte graphique : ${gpu}"

  case "$gpu" in
    nvidia) configurer_nvidia ;;
    amd)    configurer_amd ;;
    intel)  configurer_intel ;;
    *)
      attention "Aucune carte graphique détectée : l'inférence se fera sur le CPU."
      verifier_avx2
      ;;
  esac
}

configurer_nvidia() {
  # Pop!_OS livre déjà les pilotes propriétaires dans son image « NVIDIA ».
  # On vérifie plutôt qu'on ne réinstalle : écraser un pilote fonctionnel est
  # le meilleur moyen de se retrouver sans affichage.
  if dispo nvidia-smi && nvidia-smi >/dev/null 2>&1; then
    succes "Pilote NVIDIA fonctionnel"
    nvidia-smi --query-gpu=name,driver_version,memory.total \
               --format=csv,noheader 2>/dev/null | sed 's/^/      /'
  else
    attention "Carte NVIDIA détectée mais le pilote ne répond pas."
    if [[ -f /etc/os-release ]] && grep -qi 'pop' /etc/os-release; then
      info "Sur Pop!_OS, le pilote s'installe avec :"
      printf '      sudo apt install system76-driver-nvidia\n'
      printf '      sudo reboot\n'
    else
      info "Installation du pilote recommandé :"
      printf '      sudo ubuntu-drivers autoinstall && sudo reboot\n'
    fi
    attention "Relance ce script après le redémarrage."
    return 0
  fi

  # CUDA n'est pas requis par Ollama (qui embarque ses propres bibliothèques),
  # mais nvtop rend le suivi de charge GPU beaucoup plus lisible.
  installer nvtop

  # Persistence mode : garde le pilote initialisé entre deux requêtes, ce qui
  # supprime une latence de plusieurs centaines de millisecondes au chargement.
  if dispo nvidia-smi; then
    info "Activation du mode persistant du pilote"
    faire nvidia-smi -pm 1
  fi
}

configurer_amd() {
  # Mesa/RADV suffit pour l'inférence via Vulkan et est déjà présent sur Pop!_OS.
  # ROCm n'apporte un gain qu'à partir de RDNA2, et son installation est
  # invasive : on ne la déclenche pas automatiquement.
  succes "Pilote AMD open source (amdgpu/Mesa) — utilisable via Vulkan"
  installer nvtop mesa-vulkan-drivers vulkan-tools

  info "Vérification du support Vulkan :"
  if dispo vulkaninfo; then
    vulkaninfo --summary 2>/dev/null | grep -i 'deviceName' | sed 's/^/      /' || true
  fi

  attention "Pour de meilleures performances, ROCm est envisageable si la carte est"
  attention "RDNA2 ou plus récente. Installation manuelle et intrusive : à voir ensemble"
  attention "une fois le rapport d'audit partagé."
}

configurer_intel() {
  attention "GPU Intel intégré uniquement : pas d'accélération exploitable pour les LLM."
  info "L'inférence se fera sur le CPU."
  installer intel-gpu-tools
  verifier_avx2
}

verifier_avx2() {
  if cpu_a_avx2; then
    succes "AVX2 présent — l'inférence CPU restera raisonnable"
  else
    attention "AVX2 absent : l'inférence CPU sera très lente (moins d'un token par seconde"
    attention "sur un modèle 7B). Ajouter une carte graphique est quasiment indispensable."
  fi
}

# ---------------------------------------------------------------------------
# Réglages système
# ---------------------------------------------------------------------------

configurer_microcode() {
  titre "Microcode du processeur"

  if grep -qm1 'GenuineIntel' /proc/cpuinfo; then
    installer intel-microcode
  elif grep -qm1 'AuthenticAMD' /proc/cpuinfo; then
    installer amd64-microcode
  else
    info "Fabricant du processeur non reconnu, microcode ignoré"
  fi
}

configurer_frequence_cpu() {
  titre "Fréquence du processeur"

  # Un serveur d'inférence ne gagne rien à réduire sa fréquence : le temps de
  # remontée se paie sur chaque requête courte.
  installer linux-tools-common "linux-tools-$(uname -r)" || true

  if ! dispo cpupower; then
    attention "cpupower indisponible sur ce noyau, réglage de fréquence ignoré"
    return 0
  fi

  local gouverneurs
  gouverneurs="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null || true)"

  if [[ -z "$gouverneurs" ]]; then
    info "Pas de pilotage de fréquence exposé par ce matériel, rien à faire"
    return 0
  fi

  if grep -q performance <<<"$gouverneurs"; then
    info "Passage du gouverneur en 'performance'"
    faire cpupower frequency-set -g performance

    # Rendre le réglage persistant : il est réinitialisé à chaque démarrage.
    faire tee /etc/systemd/system/cpu-performance.service >/dev/null <<'FIN'
[Unit]
Description=Gouverneur CPU en mode performance
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/cpupower frequency-set -g performance
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
FIN
    faire systemctl daemon-reload
    faire systemctl enable --now cpu-performance.service
    succes "Gouverneur 'performance' appliqué et rendu persistant"
  else
    attention "Le gouverneur 'performance' n'est pas disponible (gouverneurs : ${gouverneurs})"
  fi
}

configurer_memoire() {
  titre "Mémoire d'échange"

  local ram
  ram="$(ram_gio)"
  local swap_actuel
  swap_actuel="$(awk 'NR>1 { total += $3 } END { printf "%d", total / 1024 / 1024 }' /proc/swaps 2>/dev/null || echo 0)"

  info "RAM : ${ram} Gio — swap actuel : ${swap_actuel} Gio"

  # Un dépassement mémoire pendant le chargement d'un modèle est le mode de
  # panne le plus courant sur ce type de machine. Un filet de sécurité évite
  # que le noyau tue le service en pleine requête.
  if (( swap_actuel > 0 )); then
    succes "Swap déjà configuré"
  elif (( ram <= 16 )); then
    info "RAM limitée : activation de zram (compression en mémoire, plus rapide que le disque)"
    installer systemd-zram-generator
    faire tee /etc/systemd/zram-generator.conf >/dev/null <<'FIN'
[zram0]
zram-size = ram / 2
compression-algorithm = zstd
FIN
    faire systemctl daemon-reload
    succes "zram configuré (effectif au prochain démarrage)"
  else
    info "RAM confortable et pas de swap : acceptable, mais un fichier d'échange"
    info "de quelques Gio reste une sécurité peu coûteuse."
  fi

  # Sur un serveur d'inférence, on veut que le noyau garde les pages du modèle
  # en RAM plutôt que de les envoyer vers le swap.
  info "Réduction de la tendance au swap (vm.swappiness=10)"
  faire tee /etc/sysctl.d/99-serveur-ia.conf >/dev/null <<'FIN'
# Garder les pages des modèles en RAM autant que possible.
vm.swappiness = 10
# Un serveur de jeu ouvre beaucoup de fichiers et de connexions.
fs.file-max = 200000
FIN
  faire sysctl --system >/dev/null
}

desactiver_veille() {
  titre "Mise en veille"

  # Sans ça, le serveur disparaît du réseau tout seul au bout de quelques minutes.
  info "Désactivation de la veille, de la mise en veille prolongée et de l'hibernation"
  faire systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

  # Sur une install de bureau, logind endort aussi la machine quand l'écran est
  # fermé ou après inactivité.
  if [[ -f /etc/systemd/logind.conf ]]; then
    info "Configuration de logind (ignorer la fermeture du capot, pas de veille auto)"
    faire mkdir -p /etc/systemd/logind.conf.d
    faire tee /etc/systemd/logind.conf.d/99-serveur.conf >/dev/null <<'FIN'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
IdleAction=ignore
FIN
  fi

  succes "La machine restera allumée et joignable"
}

configurer_horloge() {
  titre "Horloge"
  # Une horloge décalée casse les certificats TLS et les connexions aux serveurs
  # de jeu. C'est le genre de panne qu'on met une heure à diagnostiquer.
  faire timedatectl set-ntp true

  if (( CONFIRME )) && dispo timedatectl; then
    timedatectl status 2>/dev/null | sed 's/^/      /' || true
  fi
}

configurer_ssh() {
  titre "Accès SSH"

  if [[ "$SAUTER_SSH" == "1" ]]; then
    info "Ignoré (SAUTER_SSH=1)"
    return 0
  fi

  installer openssh-server

  faire systemctl enable --now ssh

  # Durcissement conditionnel : désactiver le mot de passe sans qu'une clé soit
  # en place enferme dehors définitivement. On ne le fait donc que si une clé
  # publique existe déjà.
  local a_une_cle=0
  local fichier
  for fichier in /home/*/.ssh/authorized_keys /root/.ssh/authorized_keys; do
    [[ -s "$fichier" ]] && a_une_cle=1
  done

  if (( a_une_cle )); then
    info "Clé publique détectée : désactivation de l'authentification par mot de passe"
    faire tee /etc/ssh/sshd_config.d/99-serveur.conf >/dev/null <<'FIN'
PasswordAuthentication no
PermitRootLogin prohibit-password
FIN
    faire systemctl reload ssh
    succes "SSH durci (connexion par clé uniquement)"
  else
    attention "Aucune clé publique trouvée : l'authentification par mot de passe reste active."
    attention "Depuis ton poste habituel, installe ta clé puis relance ce script :"
    printf '      ssh-copy-id %s@%s\n' "${SUDO_USER:-utilisateur}" "$(ip_locale)"
  fi

  info "Adresse pour te connecter : ssh ${SUDO_USER:-utilisateur}@$(ip_locale)"
}

configurer_pare_feu() {
  titre "Pare-feu"

  if [[ "$SAUTER_PARE_FEU" == "1" ]]; then
    info "Ignoré (SAUTER_PARE_FEU=1)"
    return 0
  fi

  installer ufw

  # On n'ouvre que SSH ici. Les ports applicatifs sont ouverts par les scripts
  # qui installent les services concernés, et restreints au réseau local.
  info "Autorisation de SSH"
  faire ufw allow OpenSSH

  if ! ufw status 2>/dev/null | grep -q "Status: active"; then
    info "Activation du pare-feu"
    faire ufw --force enable
  else
    succes "Pare-feu déjà actif"
  fi

  if (( CONFIRME )); then
    ufw status verbose 2>/dev/null | sed 's/^/      /' || true
  fi
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
  demarrer_journal "02-drivers"

  if ! (( CONFIRME )); then
    attention "Mode simulation : les commandes en jaune seraient exécutées, rien n'est modifié."
    attention "Pour exécuter réellement : sudo $0 --confirm"
  fi

  titre "Mise à jour de la liste des paquets"
  faire apt-get update

  configurer_gpu
  configurer_microcode
  configurer_frequence_cpu
  configurer_memoire
  desactiver_veille
  configurer_horloge
  configurer_ssh
  configurer_pare_feu

  echo
  if (( CONFIRME )); then
    succes "Configuration terminée."
    info "Un redémarrage est conseillé pour appliquer zram et les éventuels pilotes."
    info "Ensuite : sudo ./serveur/03-ia.sh --confirm"
  else
    info "Simulation terminée. Rien n'a été modifié."
  fi
}

main "$@"
