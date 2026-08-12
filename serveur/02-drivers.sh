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
SAUTER_MAJ_AUTO="${SAUTER_MAJ_AUTO:-0}"

usage() {
  cat <<'FIN'
Usage : sudo ./02-drivers.sh [--confirm]

  --confirm      Exécute réellement. Sans ce drapeau, affiche seulement le plan.

Variables d'environnement :
  SAUTER_SSH=1        N'installe et ne configure pas OpenSSH
  SAUTER_PARE_FEU=1   Ne touche pas à ufw
  SAUTER_MAJ_AUTO=1   N'active pas les mises à jour de sécurité automatiques
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
    printf '      ssh-copy-id %s@%s\n' "$(utilisateur_cible)" "$(ip_locale)"
  fi

  info "Adresse pour te connecter : ssh $(utilisateur_cible)@$(ip_locale)"
}

# Une machine allumée en permanence dont personne ne surveille les paquets est
# le vrai risque de long terme : les deux autres trous d'un serveur maison sont
# statiques, celui-là s'aggrave tout seul à chaque publication de faille.
#
# Le piège de Pop!_OS : `lsb_release -is` répond « Pop », mais les correctifs
# sont des paquets Ubuntu (`o=Ubuntu,a=noble-security`) servis par le miroir
# apt.pop-os.org. Le modèle livré par le paquet cible
# « ${distro_id}:${distro_codename}-security », soit « Pop:noble-security » — qui
# ne correspond à aucune origine existante. Installé sans rien changer,
# unattended-upgrades tournerait chaque nuit sans jamais rien appliquer, et
# `systemctl status` afficherait un service parfaitement vert.
#
# On écrit donc une origine explicite, désignée par `origin=` plutôt que par le
# nom de la distribution, et dans un fichier à nous : les mises à jour du paquet
# réécrivent 50unattended-upgrades.
configurer_maj_securite() {
  titre "Mises à jour de sécurité automatiques"

  if [[ "$SAUTER_MAJ_AUTO" == "1" ]]; then
    info "Ignoré (SAUTER_MAJ_AUTO=1)"
    return 0
  fi

  installer unattended-upgrades

  info "Origine ciblée : origin=Ubuntu, archive=<codename>-security"
  faire tee /etc/apt/apt.conf.d/52serveur-ia-securite >/dev/null <<'FIN'
// Posé par serveur/02-drivers.sh — voir le commentaire du script.
//
// Sur Pop!_OS, « ${distro_id} » vaut « Pop » alors que les correctifs portent
// l'origine « Ubuntu ». On désigne donc l'origine explicitement, sinon rien
// n'est jamais installé.
Unattended-Upgrade::Origins-Pattern {
        "origin=Ubuntu,archive=${distro_codename}-security";
};

// Redémarrage laissé à la main : cette machine héberge des serveurs de jeu et
// des sessions d'inférence qu'un redémarrage nocturne couperait net. En
// contrepartie, un correctif de noyau n'est actif qu'après un redémarrage
// manuel — voir /var/run/reboot-required.
Unattended-Upgrade::Automatic-Reboot "false";

// Fait le ménage des vieux noyaux : /boot est petit, et son remplissage fait
// échouer les mises à jour suivantes, sécurité comprise.
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";

// Découpe l'installation en petites étapes : si la machine s'éteint au milieu,
// ce qui est déjà appliqué l'est proprement.
Unattended-Upgrade::MinimalSteps "true";
FIN

  faire tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'FIN'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
FIN

  # Ce sont les minuteries systemd qui déclenchent tout : sans elles, les
  # fichiers ci-dessus ne sont jamais lus.
  faire systemctl enable --now apt-daily.timer apt-daily-upgrade.timer

  if (( CONFIRME )); then
    verifier_maj_securite
  fi
}

# Contrôle qui compte : la seule preuve qu'unattended-upgrades fasse quelque
# chose est qu'il désigne nos origines et retienne des paquets. « service actif »
# ne dit rien — c'est précisément ainsi que la panne silencieuse passe inaperçue.
verifier_maj_securite() {
  local sortie codename
  # LC_ALL=C est indispensable : en français l'outil répond « Les origines
  # autorisées sont : », que les motifs ci-dessous ne reconnaîtraient pas. Un
  # contrôle qui échoue à cause de la langue est pire que pas de contrôle, il
  # annonce une panne inexistante.
  sortie="$(LC_ALL=C unattended-upgrade --dry-run --debug 2>&1)" || true
  codename="$(lsb_release -cs 2>/dev/null || echo noble)"

  # On cherche la trace de l'origine dans la décision, pas seulement dans la
  # liste des origines autorisées : ce qui compte est qu'un paquet du dépôt de
  # sécurité soit effectivement retenu.
  if grep -q "archive:'${codename}-security' origin:'Ubuntu'" <<<"$sortie"; then
    succes "Le dépôt de sécurité Ubuntu est bien pris en compte"
  elif grep -q "origin=Ubuntu,archive=${codename}-security" <<<"$sortie"; then
    succes "Origine de sécurité autorisée, aucun paquet concerné pour l'instant"
  else
    attention "L'origine de sécurité n'est PAS reconnue : les correctifs ne seront"
    attention "jamais appliqués, alors que le service paraîtra en bonne santé."
    attention "Inspecter : LC_ALL=C unattended-upgrade --dry-run --debug"
    return 0
  fi

  # Le relevé vient d'apt et non de la sortie de débogage d'unattended-upgrades,
  # qui étale les noms de paquets sur plusieurs lignes sans marqueur de fin.
  # « Inst » n'est pas traduit dans une simulation apt.
  local liste
  liste="$(LC_ALL=C apt-get -s upgrade 2>/dev/null |
             awk '/^Inst/ && /-security/ { print $2 }' | sort -u | tr '\n' ' ')"
  if [[ -n "${liste// /}" ]]; then
    info "Correctifs de sécurité en attente : ${liste}"
  else
    succes "Aucun correctif de sécurité en attente"
  fi

  local prochaine
  prochaine="$(systemctl list-timers apt-daily-upgrade.timer --no-pager 2>/dev/null |
                 awk 'NR==2 { print $1, $2, $3 }')"
  [[ -n "$prochaine" ]] && info "Prochain passage : ${prochaine}"

  signaler_paquets_epingles
}

# Pop!_OS épingle son propre dépôt à la priorité 1001, au-dessus de tout le
# reste. Là où il livre sa propre version d'un paquet, celle du dépôt de sécurité
# Ubuntu ne s'installera donc jamais — ni automatiquement, ni par `apt upgrade`.
# Le cas concret est systemd, que Pop reconstruit avec ses correctifs.
#
# On ne touche pas à cet épinglage : passer outre remplacerait le systemd de Pop
# par celui d'Ubuntu, au risque de casser COSMIC et l'intégration System76. Mais
# ce décalage doit être visible, sinon « aucune mise à jour en attente » se lit
# comme « rien à corriger », ce qui est faux.
signaler_paquets_epingles() {
  dispo python3 || return 0

  local rapport
  rapport="$(python3 - <<'PY' 2>/dev/null || true
import apt, apt_pkg
try:
    cache = apt.Cache()
except Exception:
    raise SystemExit(0)

retard = {}
for paquet in cache:
    if not paquet.is_installed:
        continue
    installee = paquet.installed.version
    for version in paquet.versions:
        for origine in version.origins:
            if origine.origin == "Ubuntu" and origine.archive.endswith("-security"):
                if apt_pkg.version_compare(version.version, installee) > 0:
                    retard[paquet.name] = version.version
                break

if retard:
    print(len(retard))
    print(" ".join(sorted(retard)[:6]))
PY
)"

  local nombre noms
  nombre="$(sed -n '1p' <<<"$rapport")"
  noms="$(sed -n '2p' <<<"$rapport")"

  if [[ -n "$nombre" ]] && (( nombre > 0 )); then
    attention "${nombre} paquets restent en retard sur le dépôt de sécurité Ubuntu,"
    attention "retenus par l'épinglage de Pop!_OS (priorité 1001) : ${noms}…"
    attention "Ce n'est pas un défaut de configuration : Pop livre ses propres"
    attention "versions et rattrape à son rythme. Rien à faire, sauf à décider"
    attention "d'écraser son systemd par celui d'Ubuntu — au risque de COSMIC."
  else
    succes "Aucun paquet en retard sur le dépôt de sécurité Ubuntu"
  fi
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
  #
  # SSH aussi : le profil « OpenSSH » d'ufw ouvre le port 22 à tout Internet, et
  # comme le mot de passe reste actif tant qu'aucune clé n'est installée, cela
  # revient à offrir une invite de connexion au monde entier. IPv6 rend la chose
  # concrète — la machine a une adresse publique routable, sans NAT pour la
  # masquer, et une box qui laisse entrer suffit.
  local sous_reseau
  sous_reseau="$(sous_reseau_local)"

  if [[ -n "$sous_reseau" ]]; then
    info "Autorisation de SSH depuis ${sous_reseau} uniquement"
    faire ufw allow from "$sous_reseau" to any port 22 proto tcp
    # Retire la règle grande ouverte si une exécution précédente l'avait posée.
    # `ufw delete` sort en erreur quand la règle n'existe pas : sous `set -e`,
    # cela arrêterait le script alors qu'il n'y a rien à faire.
    # Il faut la sortie verbeuse : la forme courte affiche « OpenSSH » sans le
    # port ni la direction, alors que la verbeuse donne « 22/tcp (OpenSSH) …
    # ALLOW IN … Anywhere ». On ne cible que les lignes dont la provenance est
    # « Anywhere », pour ne jamais confondre cette règle avec celle qu'on vient
    # de poser pour le réseau local.
    if LC_ALL=C ufw status verbose 2>/dev/null | grep -q '^22/tcp.*ALLOW IN.*Anywhere'; then
      info "Retrait de l'ancienne règle SSH ouverte à tout Internet"
      faire ufw delete allow OpenSSH || true
    fi
  else
    attention "Sous-réseau local indéterminé : SSH est ouvert à tout Internet."
    faire ufw allow OpenSSH
  fi

  # Le test doit forcer la locale : sur un système en français ufw répond
  # « État : actif », que ce motif ne reconnaît pas — le script réactivait donc
  # le pare-feu à chaque exécution en annonçant l'avoir activé.
  if ! LC_ALL=C ufw status 2>/dev/null | grep -q "Status: active"; then
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
  configurer_maj_securite

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
