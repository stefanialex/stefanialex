#!/usr/bin/env bash
#
# 01-disques.sh — Prépare les disques secondaires pour le serveur.
#
#   sudo ./serveur/01-disques.sh              # simulation : montre le plan, ne touche à rien
#   sudo ./serveur/01-disques.sh --confirm    # exécution réelle, avec confirmation par disque
#
# RÈGLE ABSOLUE : le disque qui porte « / » n'est jamais touché. Il est mis en
# liste noire, et le script refuse de le cibler même s'il est passé en argument.
# Formater la racine d'un système en cours d'exécution est impossible de toute
# façon ; le garde-fou est là pour empêcher d'effacer le mauvais disque par erreur.
#
# Résultat attendu :
#   /srv/ia    — modèles et données IA (un modèle pèse de 5 à 45 Gio)
#   /srv/jeux  — mondes et serveurs de jeu
#
# S'il n'y a qu'un seul disque secondaire, les deux dossiers y sont créés côte à côte.

set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${ICI}/lib/common.sh"

CONFIRME=0
DISQUES_DEMANDES=()

usage() {
  cat <<'FIN'
Usage : sudo ./01-disques.sh [--confirm] [disque ...]

  --confirm      Exécute réellement. Sans ce drapeau, le script se contente
                 d'afficher ce qu'il ferait.
  disque         Nom court (sdb) ou chemin (/dev/sdb). Si aucun n'est donné,
                 tous les disques secondaires détectés sont proposés.

Variables d'environnement :
  RACINE_IA      Point de montage des données IA   (défaut : /srv/ia)
  RACINE_JEUX    Point de montage des jeux         (défaut : /srv/jeux)
  SYSTEME_FICHIERS  ext4 (défaut) ou xfs
FIN
}

SYSTEME_FICHIERS="${SYSTEME_FICHIERS:-ext4}"

# ---------------------------------------------------------------------------

analyser_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --confirm) CONFIRME=1 ;;
      -h|--help) usage; exit 0 ;;
      -*)        fatal "Option inconnue : $1" ;;
      *)         DISQUES_DEMANDES+=("$(basename "$1")") ;;
    esac
    shift
  done
}

# Vérifie qu'un disque est réellement formatable. Renvoie 1 avec un message
# explicite sinon — on préfère refuser que se tromper de disque.
disque_utilisable() {
  local disque="$1" systeme="$2"

  if [[ ! -b "/dev/${disque}" ]]; then
    erreur "/dev/${disque} n'existe pas ou n'est pas un périphérique bloc."
    return 1
  fi

  if [[ "$disque" == "$systeme" ]]; then
    erreur "/dev/${disque} porte le système de fichiers racine. Refus catégorique."
    return 1
  fi

  # Un disque dont une partition est montée est soit le système, soit en cours
  # d'utilisation : dans les deux cas on ne l'efface pas silencieusement.
  local montages
  montages="$(lsblk -no MOUNTPOINT "/dev/${disque}" 2>/dev/null | grep -v '^$' || true)"
  if [[ -n "$montages" ]]; then
    erreur "/dev/${disque} a des partitions montées :"
    sed 's/^/      /' <<<"$montages"
    erreur "Démonte-les d'abord (umount), ou choisis un autre disque."
    return 1
  fi

  return 0
}

# Affiche l'état actuel d'un disque : ce qui va être détruit.
decrire_disque() {
  local disque="$1"
  local taille modele
  taille="$(lsblk -dno SIZE "/dev/${disque}" 2>/dev/null | tr -d ' ')"
  modele="$(lsblk -dno MODEL "/dev/${disque}" 2>/dev/null | sed 's/ *$//')"

  printf '\n  %s/dev/%s%s — %s %s\n' "$C_GRAS" "$disque" "$C_FIN" "$taille" "${modele:-modèle inconnu}"
  printf '  Contenu actuel (sera entièrement détruit) :\n'
  lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "/dev/${disque}" | sed 's/^/      /'
}

# Efface, partitionne, formate et monte un disque.
preparer_disque() {
  local disque="$1" point_montage="$2"
  local device="/dev/${disque}"
  local partition

  info "Effacement des signatures existantes sur ${device}"
  wipefs -a "$device"

  info "Création d'une table GPT et d'une partition unique"
  # sgdisk est plus prévisible que parted en mode script.
  sgdisk --zap-all "$device"
  sgdisk --new=1:0:0 --typecode=1:8300 "$device"

  # Laisse au noyau le temps de relire la table avant de formater.
  partprobe "$device" || true
  udevadm settle || true

  partition="$(lsblk -no NAME,TYPE "$device" | awk '$2 == "part" { print $1; exit }')"
  partition="/dev/$(printf '%s' "$partition" | tr -d '│├─└ ')"
  [[ -b "$partition" ]] || fatal "Partition introuvable après partitionnement de ${device}"

  info "Formatage de ${partition} en ${SYSTEME_FICHIERS}"
  case "$SYSTEME_FICHIERS" in
    ext4)
      # -m 1 : ne réserve que 1 % à root au lieu de 5 %. Sur un disque de données
      # de plusieurs téraoctets, les 4 % économisés sont loin d'être négligeables.
      mkfs.ext4 -F -m 1 -L "$(basename "$point_montage")" "$partition"
      ;;
    xfs)
      mkfs.xfs -f -L "$(basename "$point_montage")" "$partition"
      ;;
    *)
      fatal "Système de fichiers non pris en charge : ${SYSTEME_FICHIERS}"
      ;;
  esac

  local uuid
  uuid="$(blkid -s UUID -o value "$partition")"
  [[ -n "$uuid" ]] || fatal "UUID illisible pour ${partition}"

  mkdir -p "$point_montage"

  # Montage par UUID : l'ordre d'énumération des disques change d'un démarrage à
  # l'autre, /dev/sdb aujourd'hui peut être /dev/sdc demain.
  if grep -q "UUID=${uuid}" /etc/fstab; then
    info "Entrée fstab déjà présente pour ${uuid}"
  else
    info "Ajout de l'entrée fstab"
    printf 'UUID=%s  %s  %s  defaults,noatime  0  2\n' \
      "$uuid" "$point_montage" "$SYSTEME_FICHIERS" >>/etc/fstab
  fi

  systemctl daemon-reload
  mount "$point_montage" 2>/dev/null || mount -a

  mountpoint -q "$point_montage" || fatal "Le montage de ${point_montage} a échoué"
  succes "${device} → ${point_montage} ($(df -h --output=size "$point_montage" | tail -n1 | tr -d ' ') disponibles)"
}

# Cas sans disque secondaire : on crée simplement les dossiers sur la racine.
preparer_sur_racine() {
  info "Création de ${RACINE_IA} et ${RACINE_JEUX} sur le disque système"
  mkdir -p "$RACINE_IA" "$RACINE_JEUX"
  succes "Dossiers créés (pas de disque dédié)"
  attention "Surveille l'espace libre : les modèles IA occupent vite plusieurs dizaines de Gio."
}

# Vérifie que l'outillage de partitionnement est présent AVANT d'écrire quoi que
# ce soit. Sans ce contrôle, wipefs efface la table de partition puis le script
# meurt sur le sgdisk manquant : le disque est déjà entamé pour rien.
verifier_outils() {
  local -A paquet=(
    [sgdisk]=gdisk
    [wipefs]=util-linux
    [partprobe]=parted
    [blkid]=util-linux
    [lsblk]=util-linux
  )
  case "$SYSTEME_FICHIERS" in
    ext4) paquet[mkfs.ext4]=e2fsprogs ;;
    xfs)  paquet[mkfs.xfs]=xfsprogs ;;
  esac

  local manquants=() outil
  for outil in "${!paquet[@]}"; do
    command -v "$outil" >/dev/null 2>&1 || manquants+=("${paquet[$outil]}")
  done

  [[ ${#manquants[@]} -eq 0 ]] && return 0

  # Dédoublonne : util-linux couvre plusieurs outils à lui seul.
  local liste
  liste="$(printf '%s\n' "${manquants[@]}" | sort -u | tr '\n' ' ')"
  fatal "Outils de partitionnement manquants. Installe-les puis relance :
       apt install -y ${liste% }"
}

# ---------------------------------------------------------------------------

main() {
  analyser_arguments "$@"
  exiger_root "$@"
  demarrer_journal "01-disques"
  verifier_outils

  titre "Préparation des disques"

  local systeme
  systeme="$(disque_systeme)"

  if [[ -z "$systeme" ]]; then
    fatal "Impossible d'identifier le disque système. Par sécurité, le script s'arrête ici.
       Lance 'lsblk' et 'findmnt /' puis partage la sortie."
  fi
  succes "Disque système protégé : /dev/${systeme} (ne sera jamais touché)"

  # Sélection des disques : ceux demandés, sinon tous les secondaires détectés.
  local candidats=()
  if [[ ${#DISQUES_DEMANDES[@]} -gt 0 ]]; then
    candidats=("${DISQUES_DEMANDES[@]}")
  else
    local d
    while read -r d; do
      [[ -n "$d" ]] && candidats+=("$d")
    done < <(disques_secondaires)
  fi

  if [[ ${#candidats[@]} -eq 0 ]]; then
    attention "Aucun disque secondaire détecté."
    if (( CONFIRME )); then
      preparer_sur_racine
    else
      info "Avec --confirm, le script créerait ${RACINE_IA} et ${RACINE_JEUX} sur le disque système."
    fi
    exit 0
  fi

  # Filtre les candidats inutilisables avant d'afficher quoi que ce soit.
  local valides=()
  local disque
  for disque in "${candidats[@]}"; do
    if disque_utilisable "$disque" "$systeme"; then
      valides+=("$disque")
    fi
  done

  [[ ${#valides[@]} -gt 0 ]] || fatal "Aucun disque utilisable parmi ceux proposés."

  # Répartition : le plus gros disque reçoit l'IA (les modèles sont volumineux),
  # le suivant les jeux. Avec un seul disque, les deux cohabitent dessus.
  local plan_points=()
  if [[ ${#valides[@]} -eq 1 ]]; then
    plan_points=("$RACINE_IA")
  else
    plan_points=("$RACINE_IA" "$RACINE_JEUX")
  fi

  titre "Plan"
  local i
  for i in "${!valides[@]}"; do
    decrire_disque "${valides[$i]}"
    if [[ -n "${plan_points[$i]:-}" ]]; then
      printf '  → sera formaté en %s et monté sur %s%s%s\n' \
        "$SYSTEME_FICHIERS" "$C_GRAS" "${plan_points[$i]}" "$C_FIN"
    else
      printf '  → aucun rôle attribué, sera ignoré\n'
    fi
  done

  if [[ ${#valides[@]} -eq 1 ]]; then
    printf '\n  Un seul disque : %s et %s cohabiteront dessus.\n' "$RACINE_IA" "$RACINE_JEUX"
  fi

  if ! (( CONFIRME )); then
    echo
    attention "Mode simulation : rien n'a été modifié."
    info "Pour exécuter réellement : sudo $0 --confirm"
    exit 0
  fi

  # Exécution réelle : confirmation disque par disque, saisie exacte du nom.
  for i in "${!valides[@]}"; do
    disque="${valides[$i]}"
    local point="${plan_points[$i]:-}"
    [[ -n "$point" ]] || continue

    echo
    decrire_disque "$disque"
    if ! confirmer_saisie "/dev/${disque}" \
         "TOUTES LES DONNÉES DE CE DISQUE SERONT PERDUES. Retape son chemin pour confirmer"; then
      attention "Saisie incorrecte — /dev/${disque} est laissé intact."
      continue
    fi

    preparer_disque "$disque" "$point"
  done

  # Avec un disque unique, le dossier jeux vit sur le même volume.
  if [[ ${#valides[@]} -eq 1 ]] && mountpoint -q "$RACINE_IA"; then
    mkdir -p "${RACINE_IA}/jeux"
    if [[ ! -e "$RACINE_JEUX" ]]; then
      ln -s "${RACINE_IA}/jeux" "$RACINE_JEUX"
      info "${RACINE_JEUX} → lien vers ${RACINE_IA}/jeux"
    fi
  fi

  titre "Résultat"
  lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT | sed 's/^/  /'
  echo
  succes "Disques prêts."
  info "Vérifie que tout remonte après un redémarrage : sudo reboot, puis lsblk"
}

main "$@"
