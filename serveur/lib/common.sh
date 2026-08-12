#!/usr/bin/env bash
# Fonctions partagées par tous les scripts du dossier serveur/.
# Ce fichier n'est pas exécutable : il est destiné à être sourcé.
#
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
  C_ROUGE=$'\033[31m'; C_VERT=$'\033[32m'; C_JAUNE=$'\033[33m'
  C_BLEU=$'\033[34m';  C_GRAS=$'\033[1m';  C_FIN=$'\033[0m'
else
  C_ROUGE=''; C_VERT=''; C_JAUNE=''; C_BLEU=''; C_GRAS=''; C_FIN=''
fi

info()    { printf '%s\n' "${C_BLEU}  ·${C_FIN} $*"; }
succes()  { printf '%s\n' "${C_VERT}  ✓${C_FIN} $*"; }
attention() { printf '%s\n' "${C_JAUNE}  !${C_FIN} $*" >&2; }
erreur()  { printf '%s\n' "${C_ROUGE}  ✗${C_FIN} $*" >&2; }

titre() {
  printf '\n%s\n' "${C_GRAS}${C_BLEU}── $* ${C_FIN}"
}

fatal() {
  erreur "$*"
  exit 1
}

# ---------------------------------------------------------------------------
# Journalisation
#
# Duplique toute la sortie du script vers /var/log/serveur-ia/<nom>-<date>.log
# tout en continuant à l'afficher. Si le dossier n'est pas créable (script lancé
# sans les droits root), on retombe silencieusement sur /tmp.
# ---------------------------------------------------------------------------

demarrer_journal() {
  local nom="${1:-serveur}"
  local dossier="/var/log/serveur-ia"

  if ! mkdir -p "$dossier" 2>/dev/null; then
    dossier="${TMPDIR:-/tmp}/serveur-ia"
    mkdir -p "$dossier" || return 0
  fi

  JOURNAL="${dossier}/${nom}-$(date +%Y%m%d-%H%M%S).log"
  exec > >(tee -a "$JOURNAL") 2>&1
  info "Journal : ${JOURNAL}"
}

# ---------------------------------------------------------------------------
# Garde-fous
# ---------------------------------------------------------------------------

exiger_root() {
  if [[ ${EUID} -ne 0 ]]; then
    fatal "Ce script doit être lancé avec sudo : sudo $0 $*"
  fi
}

# Vrai si la commande existe dans le PATH.
dispo() {
  command -v "$1" >/dev/null 2>&1
}

# Compte pour lequel on installe, quand le script tourne en root. Chaîne vide
# si indéterminable.
#
# `sudo` renseigne SUDO_USER, mais il exige un terminal pour son mot de passe et
# devient donc inutilisable depuis un contexte non interactif : on passe alors
# par `pkexec`, qui ne renseigne que PKEXEC_UID. Sans ce repli, tout `chown`
# conditionné à SUDO_USER est silencieusement sauté et les dossiers restent à
# root — hors de portée de l'application de bureau censée y écrire.
utilisateur_cible() {
  if [[ -n "${SUDO_USER:-}" ]]; then
    printf '%s\n' "$SUDO_USER"
    return 0
  fi

  if [[ -n "${PKEXEC_UID:-}" ]]; then
    local nom
    nom="$(getent passwd "$PKEXEC_UID" 2>/dev/null | cut -d: -f1)"
    [[ -n "$nom" ]] && { printf '%s\n' "$nom"; return 0; }
  fi

  # Dernier repli : le premier compte humain. Les comptes de service ont un UID
  # inférieur à 1000, et « nobody » se place tout en haut de la plage.
  getent passwd 2>/dev/null |
    awk -F: '$3 >= 1000 && $3 < 60000 { print $1; exit }'
}

# Dossier personnel du compte passé en argument. Chaîne vide si inconnu.
dossier_personnel() {
  local compte="$1"
  [[ -n "$compte" ]] || return 0
  getent passwd "$compte" 2>/dev/null | cut -d: -f6
}

# Affiche la valeur de la commande si elle existe, sinon un message explicite.
# Évite qu'un outil manquant (fréquent sur une install fraîche) fasse échouer
# tout le script alors qu'on ne fait que collecter de l'information.
essayer() {
  local description="$1"; shift
  if dispo "$1"; then
    "$@" 2>&1 || printf '(échec de : %s)\n' "$*"
  else
    printf '(%s indisponible : la commande « %s » n'\''est pas installée)\n' \
      "$description" "$1"
  fi
}

# Demande une confirmation en imposant la saisie exacte d'un mot.
# Utilisé avant toute opération destructrice.
confirmer_saisie() {
  local attendu="$1"
  local question="${2:-Pour confirmer, tape exactement}"
  local reponse

  printf '%s\n' "${C_JAUNE}${question} : ${C_GRAS}${attendu}${C_FIN}"
  read -r -p "> " reponse || return 1

  [[ "$reponse" == "$attendu" ]]
}

# ---------------------------------------------------------------------------
# Détection matérielle
# ---------------------------------------------------------------------------

# Nom du disque physique portant la racine, ex. « nvme0n1 » ou « sda ».
# Chaîne vide si indéterminable — les appelants doivent traiter ce cas comme
# bloquant avant toute opération destructrice.
disque_systeme() {
  local source parent
  source="$(findmnt -no SOURCE / 2>/dev/null)" || return 0
  [[ -n "$source" ]] || return 0

  # Sur LVM / chiffrement, PKNAME remonte d'un seul cran ; on boucle jusqu'au
  # disque physique (TYPE=disk).
  local courant="$source"
  for _ in 1 2 3 4 5; do
    local type_courant
    type_courant="$(lsblk -no TYPE "$courant" 2>/dev/null | head -n1)"
    [[ "$type_courant" == "disk" ]] && { basename "$courant"; return 0; }

    parent="$(lsblk -no PKNAME "$courant" 2>/dev/null | head -n1)"
    [[ -n "$parent" ]] || break
    courant="/dev/${parent}"
  done

  # Toujours sortir en succès : les appelants distinguent le cas « indéterminé »
  # par une chaîne vide, et un code de retour non nul tuerait leur $(…) sous set -e.
  [[ -n "$courant" ]] && basename "$courant"
  return 0
}

# Liste les disques physiques hors disque système, un par ligne (nom court).
# Exclut aussi les périphériques amovibles et les images loop/zram/rom.
disques_secondaires() {
  local systeme
  systeme="$(disque_systeme)"

  lsblk -dno NAME,TYPE,RM 2>/dev/null | while read -r nom type amovible; do
    [[ "$type" == "disk" ]]        || continue
    [[ "$nom" == "$systeme" ]]     && continue
    [[ "$nom" == zram* ]]          && continue
    [[ "$nom" == loop* ]]          && continue
    [[ "$amovible" == "1" ]]       && continue
    printf '%s\n' "$nom"
  done
}

# Écrit « nvidia », « amd », « intel » ou « aucun » sur la sortie standard.
detecter_gpu() {
  local sortie=""

  if dispo lspci; then
    sortie="$(lspci 2>/dev/null | grep -Ei 'vga|3d controller|display controller' || true)"
  fi

  # Repli sans lspci : les pilotes chargés exposent des marqueurs dans /sys.
  if [[ -z "$sortie" ]]; then
    [[ -d /proc/driver/nvidia ]] && { printf 'nvidia\n'; return 0; }
    if compgen -G "/sys/module/amdgpu" >/dev/null; then printf 'amd\n'; return 0; fi
    if compgen -G "/sys/module/i915"   >/dev/null; then printf 'intel\n'; return 0; fi
    printf 'aucun\n'; return 0
  fi

  # Une carte dédiée prime sur l'IGP quand les deux sont présents : c'est elle
  # qui fera l'inférence.
  if grep -qi nvidia <<<"$sortie"; then printf 'nvidia\n'
  elif grep -Eqi 'amd|ati|radeon' <<<"$sortie"; then printf 'amd\n'
  elif grep -qi intel <<<"$sortie"; then printf 'intel\n'
  else printf 'aucun\n'
  fi
}

# VRAM en mébioctets, ou 0 si indéterminable (GPU absent, ou CPU seul).
vram_mo() {
  if dispo nvidia-smi; then
    local v
    v="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d ' ')"
    if [[ "$v" =~ ^[0-9]+$ ]]; then printf '%s\n' "$v"; return 0; fi
  fi

  local fichier
  for fichier in /sys/class/drm/card*/device/mem_info_vram_total; do
    [[ -r "$fichier" ]] || continue
    local octets
    octets="$(cat "$fichier" 2>/dev/null)"
    if [[ "$octets" =~ ^[0-9]+$ ]] && (( octets > 0 )); then
      printf '%s\n' "$(( octets / 1024 / 1024 ))"
      return 0
    fi
  done

  printf '0\n'
}

# RAM totale en mébioctets.
ram_mo() {
  awk '/^MemTotal:/ { printf "%d\n", $2 / 1024 }' /proc/meminfo
}

# Convertit des mébioctets en la taille commerciale correspondante, en gibioctets.
#
# Indispensable : une machine de 16 Go annonce ~15,6 Gio (le noyau et le
# matériel en réservent une part), et une carte graphique de 8 Go annonce
# souvent 8188 Mio. Une division entière donnerait 15 et 7, ce qui ferait
# basculer les deux du mauvais côté des seuils de recommandation.
#
# On retient donc la plus petite taille standard supérieure ou égale à la
# mesure, tant que l'écart reste plausible (moins de 15 %).
arrondir_gio() {
  local mo="$1"
  local gio_mesure=$(( mo / 1024 ))
  local standard

  for standard in 1 2 3 4 6 8 12 16 24 32 48 64 96 128 192 256 384 512; do
    if (( standard >= gio_mesure )); then
      # Refuse d'arrondir vers une taille bien supérieure à la mesure : sur une
      # machine de 20 Gio (barrettes dépareillées), on veut 20, pas 24.
      if (( standard * 1024 - mo <= standard * 150 )); then
        printf '%s\n' "$standard"
      else
        printf '%s\n' "$gio_mesure"
      fi
      return 0
    fi
  done

  printf '%s\n' "$gio_mesure"
}

# RAM totale en gibioctets, arrondie à la taille réellement installée.
ram_gio() {
  arrondir_gio "$(ram_mo)"
}

# VRAM en gibioctets, arrondie. 0 si aucun GPU exploitable.
vram_gio() {
  local mo
  mo="$(vram_mo)"
  (( mo > 0 )) || { printf '0\n'; return 0; }
  arrondir_gio "$mo"
}

# Vrai si le CPU expose AVX2 — en dessous, l'inférence CPU devient très lente.
cpu_a_avx2() {
  grep -qm1 '\bavx2\b' /proc/cpuinfo
}

# Interface portant la route par défaut. Chaîne vide si indéterminable.
interface_defaut() {
  dispo ip || return 0
  ip route show default 2>/dev/null | awk '/default/ { print $5; exit }'
}

# Sous-réseau local au format CIDR (ex. 192.168.1.0/24), pour restreindre les
# règles de pare-feu. Chaîne vide si indéterminable.
sous_reseau_local() {
  dispo ip || return 0

  local interface cidr
  interface="$(interface_defaut)"
  [[ -n "$interface" ]] || return 0

  cidr="$(ip -4 -o addr show dev "$interface" scope global 2>/dev/null |
          awk '{ print $4; exit }')"
  [[ -n "$cidr" ]] || return 0

  # Normalise vers l'adresse réseau : 192.168.1.42/24 -> 192.168.1.0/24
  python3 - "$cidr" <<'PY' 2>/dev/null || printf '%s\n' "$cidr"
import ipaddress, sys
print(ipaddress.ip_interface(sys.argv[1]).network)
PY
}

# Préfixe IPv6 du réseau local au format CIDR (ex. 2001:861:3910:e4f0::/64).
# Chaîne vide si la machine n'a pas d'adresse IPv6 globale.
#
# Sert à écrire des règles de pare-feu IPv6 : contrairement à IPv4, il n'y a pas
# de NAT pour masquer la machine, son adresse est routable depuis Internet. Le
# préfixe est délégué par la box et peut changer — d'où la nécessité de rejouer
# le script qui s'en sert si l'accès IPv6 au réseau local cesse de fonctionner.
prefixe_ipv6_local() {
  dispo ip || return 0

  local interface cidr
  interface="$(interface_defaut)"
  [[ -n "$interface" ]] || return 0

  # `scope global` écarte déjà le lien-local ; on prend la première adresse
  # permanente, en sautant les adresses temporaires de vie privée.
  cidr="$(ip -6 -o addr show dev "$interface" scope global 2>/dev/null |
          grep -v temporary |
          awk '{ print $4; exit }')"
  [[ -n "$cidr" ]] || return 0

  python3 - "$cidr" <<'PY' 2>/dev/null || true
import ipaddress, sys
print(ipaddress.ip_interface(sys.argv[1]).network)
PY
}

# Adresse IPv4 principale de la machine, pour afficher les URL d'accès.
# Retombe sur « adresse-du-serveur » plutôt que sur du vide, pour que les URL
# affichées restent lisibles même quand la détection échoue.
ip_locale() {
  local adresse=""

  if dispo ip; then
    adresse="$(ip -4 -o addr show scope global 2>/dev/null |
                 awk '{ split($4, a, "/"); print a[1]; exit }')"
  elif dispo hostname; then
    adresse="$(hostname -I 2>/dev/null | awk '{ print $1 }')"
  fi

  printf '%s\n' "${adresse:-adresse-du-serveur}"
}

# ---------------------------------------------------------------------------
# Chemins communs
# ---------------------------------------------------------------------------

RACINE_IA="${RACINE_IA:-/srv/ia}"
RACINE_JEUX="${RACINE_JEUX:-/srv/jeux}"
