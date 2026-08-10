#!/usr/bin/env bash
#
# 00-audit.sh — Inventaire complet du matériel. LECTURE SEULE.
#
# Ce script ne modifie rien. Il collecte tout ce qui est nécessaire pour
# dimensionner le serveur IA (taille de modèle chargeable, présence d'un GPU
# utilisable, état des disques) et écrit un rapport Markdown.
#
#   sudo ./serveur/00-audit.sh
#
# Certaines informations (mémoire détaillée, BIOS, santé SMART) exigent root.
# Sans root le script fonctionne quand même, en signalant ce qui manque.

set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${ICI}/lib/common.sh"

RAPPORT="${RAPPORT:-${ICI}/rapport-audit.md}"

# Écrit un bloc de code Markdown contenant la sortie de la commande donnée.
bloc() {
  local description="$1"; shift
  {
    printf '```\n'
    essayer "$description" "$@"
    printf '```\n\n'
  } >>"$RAPPORT"
}

section() {
  printf '\n## %s\n\n' "$1" >>"$RAPPORT"
  titre "$1"
}

# ---------------------------------------------------------------------------

main() {
  if [[ ${EUID} -ne 0 ]]; then
    attention "Lancé sans sudo : mémoire détaillée, BIOS et santé SMART seront incomplets."
    attention "Pour un rapport complet : sudo $0"
    echo
  fi

  : >"$RAPPORT"
  {
    printf '# Rapport d'\''audit matériel\n\n'
    printf -- '- Date : %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
    printf -- '- Machine : %s\n' "$(hostname)"
    printf -- '- Généré par : `serveur/00-audit.sh`\n'
  } >>"$RAPPORT"

  # --- Système ------------------------------------------------------------
  section "Système"
  bloc "informations de distribution" cat /etc/os-release
  bloc "version du noyau" uname -a
  bloc "temps de fonctionnement" uptime

  # --- Processeur ---------------------------------------------------------
  # Les jeux d'instructions AVX2 / AVX-512 conditionnent directement la vitesse
  # d'inférence quand le calcul se fait sur le CPU.
  section "Processeur"
  bloc "détail du processeur" lscpu

  {
    printf '**Jeux d'\''instructions utiles à l'\''inférence :**\n\n'
    for drapeau in avx avx2 avx512f f16c fma; do
      if grep -qm1 "\\b${drapeau}\\b" /proc/cpuinfo; then
        printf -- '- `%s` : présent\n' "$drapeau"
      else
        printf -- '- `%s` : **absent**\n' "$drapeau"
      fi
    done
    printf '\n'
  } >>"$RAPPORT"

  if ! cpu_a_avx2; then
    attention "AVX2 absent : l'inférence sur CPU sera très lente. Un GPU devient quasi indispensable."
  fi

  # --- Mémoire ------------------------------------------------------------
  # Le nombre de slots libres décide s'il est possible d'ajouter de la RAM,
  # ce qui est souvent l'amélioration la plus rentable pour faire tourner des
  # modèles plus gros.
  section "Mémoire vive"
  bloc "mémoire disponible" free -h
  bloc "barrettes et slots" dmidecode -t memory

  local ram_mesure ram
  ram_mesure="$(ram_mo)"
  ram="$(ram_gio)"
  printf '**RAM totale : %s Gio installés (%s Mio vus par le noyau)**\n\n' \
    "$ram" "$ram_mesure" >>"$RAPPORT"

  # --- Carte graphique ----------------------------------------------------
  section "Carte graphique"
  bloc "cartes graphiques et pilotes" lspci -nnk

  local gpu vram
  gpu="$(detecter_gpu)"
  vram="$(vram_gio)"

  {
    printf -- '- Type détecté : **%s**\n' "$gpu"
    if (( vram > 0 )); then
      printf -- '- VRAM détectée : **%s Gio**\n\n' "$vram"
    else
      printf -- '- VRAM : non déterminée (GPU absent, pilote non chargé, ou mémoire partagée)\n\n'
    fi
  } >>"$RAPPORT"

  case "$gpu" in
    nvidia) bloc "état du GPU NVIDIA" nvidia-smi ;;
    amd)    bloc "état du GPU AMD" rocm-smi ;;
  esac

  bloc "pilote OpenGL en cours" glxinfo -B

  # --- Disques ------------------------------------------------------------
  section "Disques"

  local systeme
  systeme="$(disque_systeme)"
  {
    if [[ -n "$systeme" ]]; then
      printf -- '- Disque **système** (jamais formaté par ces scripts) : `/dev/%s`\n' "$systeme"
    else
      printf -- '- Disque système : **non identifié** — `01-disques.sh` refusera de s'\''exécuter.\n'
    fi
  } >>"$RAPPORT"

  local secondaires
  secondaires="$(disques_secondaires)"
  {
    if [[ -n "$secondaires" ]]; then
      printf -- '- Disques secondaires (formatables) : '
      local d
      while read -r d; do
        [[ -n "$d" ]] && printf '`/dev/%s` ' "$d"
      done <<<"$secondaires"
      printf '\n\n'
    else
      printf -- '- Aucun disque secondaire détecté : tout devra tenir sur le disque système.\n\n'
    fi
  } >>"$RAPPORT"

  bloc "arborescence des disques" \
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL,ROTA
  bloc "espace occupé" df -hT -x tmpfs -x devtmpfs

  # SMART : les heures de fonctionnement et le compteur de secteurs réalloués
  # disent si un vieux disque mérite encore qu'on écrive dessus.
  local disque
  for disque in $(lsblk -dno NAME,TYPE | awk '$2 == "disk" { print $1 }'); do
    [[ "$disque" == zram* || "$disque" == loop* ]] && continue
    printf '### Santé SMART de /dev/%s\n\n' "$disque" >>"$RAPPORT"
    bloc "santé SMART" smartctl -H -i -A "/dev/${disque}"
  done

  # --- Réseau -------------------------------------------------------------
  section "Réseau"
  bloc "interfaces réseau" ip -brief address
  bloc "route par défaut" ip route show default

  {
    printf -- '- Adresse IP principale : `%s`\n' "$(ip_locale)"
    printf -- '- Sous-réseau local : `%s`\n\n' "$(sous_reseau_local)"
  } >>"$RAPPORT"

  # Une liaison Wi-Fi suffit rarement pour un serveur de jeu : à signaler.
  local interface
  interface="$(interface_defaut)"
  if [[ -n "$interface" && -d "/sys/class/net/${interface}/wireless" ]]; then
    attention "La route par défaut passe par le Wi-Fi (${interface}). Un câble Ethernet est fortement conseillé pour un serveur."
    printf -- '> Connexion par Wi-Fi détectée : préférer l'\''Ethernet pour un serveur.\n\n' >>"$RAPPORT"
  fi

  # --- Carte mère et BIOS -------------------------------------------------
  # Utile pour savoir si l'ajout d'un GPU est envisageable (format, alimentation).
  section "Carte mère et BIOS"
  bloc "version du BIOS" dmidecode -t bios
  bloc "carte mère" dmidecode -t baseboard
  bloc "châssis" dmidecode -t chassis

  # --- Synthèse -----------------------------------------------------------
  section "Synthèse et recommandation"
  ecrire_synthese "$gpu" "$vram" "$ram"

  echo
  succes "Rapport écrit dans : ${RAPPORT}"
  info "Relis-le, puis partage-le pour calibrer les étapes suivantes."
}

# Traduit les mesures en une recommandation concrète de taille de modèle.
# La règle : le modèle quantifié doit tenir en VRAM (rapide) ou en RAM (lent).
# Les deux tailles sont déjà arrondies aux capacités réellement installées.
ecrire_synthese() {
  local gpu="$1" vram_gio="$2" ram_gio="$3"

  {
    printf -- '- GPU : **%s**' "$gpu"
    (( vram_gio > 0 )) && printf ' (%s Gio de VRAM)' "$vram_gio"
    printf '\n'
    printf -- '- RAM : **%s Gio**\n' "$ram_gio"
    printf -- '- AVX2 : **%s**\n\n' "$(cpu_a_avx2 && echo présent || echo absent)"

    printf '**Modèle recommandé au démarrage :**\n\n'

    if [[ "$gpu" == "nvidia" || "$gpu" == "amd" ]] && (( vram_gio >= 24 )); then
      printf 'Modèle 32B en quantisation Q4 — entièrement en VRAM, très confortable.\n'
      printf 'Un 70B en Q3 avec déchargement partiel reste jouable mais plus lent.\n'
    elif [[ "$gpu" == "nvidia" || "$gpu" == "amd" ]] && (( vram_gio >= 12 )); then
      printf 'Modèle 14B en Q4_K_M ou Q5 — bon compromis qualité/vitesse, tout en VRAM.\n'
    elif [[ "$gpu" == "nvidia" || "$gpu" == "amd" ]] && (( vram_gio >= 6 )); then
      printf 'Modèle 7–8B en Q4_K_M — tient en VRAM, réponses fluides.\n'
    elif (( ram_gio >= 32 )); then
      printf 'Pas de GPU exploitable : inférence sur CPU. Un 7–8B en Q4_K_M reste utilisable,\n'
      printf 'compter quelques tokens par seconde. Un 14B fonctionnera mais sera lent.\n'
    elif (( ram_gio >= 16 )); then
      printf 'Pas de GPU exploitable et RAM limitée : rester sur du 7–8B en Q4_K_M,\n'
      printf 'sans autre service lourd en parallèle.\n'
    else
      printf 'RAM insuffisante pour un usage confortable : viser un modèle 3–4B quantifié,\n'
      printf 'ou ajouter de la mémoire avant d'\''aller plus loin.\n'
    fi
    printf '\n'

    if [[ "$gpu" == "aucun" || "$gpu" == "intel" ]]; then
      printf '> Ajouter une carte NVIDIA d'\''occasion (12 Gio de VRAM ou plus) est,\n'
      printf '> de loin, l'\''amélioration la plus rentable pour ce type de serveur.\n\n'
    fi

    printf '**Cohabitation IA + serveur de jeu :** avec %s Gio de RAM, ' "$ram_gio"
    if (( ram_gio >= 32 )); then
      printf 'les deux peuvent tourner simultanément sans difficulté.\n'
    elif (( ram_gio >= 16 )); then
      printf 'la cohabitation est possible mais serrée : plafonner chaque service\n'
      printf 'avec `MemoryMax` (voir `docs/exploitation.md`).\n'
    else
      printf 'mieux vaut alterner : IA **ou** serveur de jeu, pas les deux à la fois.\n'
    fi
    printf '\n'
  } >>"$RAPPORT"
}

main "$@"
