#!/usr/bin/env bash
#
# 04-jeux.sh — Serveurs de jeu Minecraft (Paper) et Valheim (SteamCMD).
#
#   sudo ./serveur/04-jeux.sh                      # simulation, les deux jeux
#   sudo ./serveur/04-jeux.sh --confirm minecraft  # installe uniquement Minecraft
#   sudo ./serveur/04-jeux.sh --confirm valheim
#   sudo ./serveur/04-jeux.sh --confirm            # les deux
#
# Chaque serveur tourne sous un compte système dédié, sans droits inutiles, et
# est géré par systemd (démarrage automatique, redémarrage après plantage).
# Une sauvegarde quotidienne des mondes est mise en place par un timer systemd.
#
# À lancer après 03-ia.sh, quand la partie IA est validée.

set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${ICI}/lib/common.sh"

CONFIRME=0
JEUX=()

PORT_MINECRAFT=25565
PORT_VALHEIM=2456          # occupe aussi 2457 et 2458
APPID_VALHEIM=896660

usage() {
  cat <<'FIN'
Usage : sudo ./04-jeux.sh [--confirm] [minecraft|valheim ...]

  --confirm      Exécute réellement. Sans ce drapeau, affiche seulement le plan.
  minecraft      Serveur Minecraft (PaperMC)
  valheim        Serveur Valheim (SteamCMD)
                 Sans précision, les deux sont installés.

Variables d'environnement :
  RACINE_JEUX=/chemin     Emplacement des serveurs (défaut : /srv/jeux)
  RAM_MINECRAFT=4G        Mémoire allouée à Minecraft (défaut : calculée)
  VERSION_MINECRAFT=1.21.4  Version de Paper (défaut : la plus récente stable)
FIN
}

faire() {
  if (( CONFIRME )); then
    "$@"
  else
    printf '      %s%s%s\n' "$C_JAUNE" "$*" "$C_FIN" >&2
  fi
}

# Crée un compte système sans shell de connexion : si le serveur de jeu est
# compromis, l'attaquant n'hérite pas d'un accès utilisateur exploitable.
creer_compte() {
  local compte="$1" dossier="$2"

  if id "$compte" >/dev/null 2>&1; then
    succes "Compte ${compte} déjà présent"
  else
    info "Création du compte système ${compte}"
    faire useradd --system --create-home --home-dir "$dossier" \
                  --shell /usr/sbin/nologin "$compte"
  fi

  faire mkdir -p "$dossier"
  faire chown -R "${compte}:${compte}" "$dossier"
}

# Installe un timer systemd qui archive un dossier chaque nuit et ne conserve
# que les sauvegardes récentes.
installer_sauvegarde() {
  local nom="$1" source="$2" jours="${3:-7}"
  local destination="${RACINE_JEUX}/sauvegardes/${nom}"

  info "Sauvegarde quotidienne de ${source} (rétention ${jours} jours)"
  faire mkdir -p "$destination"

  faire tee "/etc/systemd/system/sauvegarde-${nom}.service" >/dev/null <<FIN
[Unit]
Description=Sauvegarde du serveur ${nom}

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'tar czf "${destination}/${nom}-\$(date +%%Y%%m%%d-%%H%%M).tar.gz" -C "${source}" . && find "${destination}" -name "${nom}-*.tar.gz" -mtime +${jours} -delete'
FIN

  faire tee "/etc/systemd/system/sauvegarde-${nom}.timer" >/dev/null <<FIN
[Unit]
Description=Sauvegarde quotidienne du serveur ${nom}

[Timer]
OnCalendar=*-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
FIN

  faire systemctl daemon-reload
  faire systemctl enable --now "sauvegarde-${nom}.timer"
}

# ---------------------------------------------------------------------------
# Minecraft — PaperMC
# ---------------------------------------------------------------------------

installer_minecraft() {
  titre "Serveur Minecraft (PaperMC)"

  local dossier="${RACINE_JEUX}/minecraft"
  local compte="minecraft"

  # Paper est un serveur optimisé, largement plus performant que le serveur
  # officiel à nombre de joueurs égal, et compatible avec les plugins Bukkit.
  info "Installation de Java 21 (requis par les versions récentes)"
  faire apt-get install -y openjdk-21-jre-headless

  creer_compte "$compte" "$dossier"

  telecharger_paper "$dossier" "$compte"

  # L'EULA de Mojang doit être acceptée par la personne qui exploite le serveur.
  # Le script ne le fait pas à sa place ; il explique comment.
  if [[ -f "${dossier}/eula.txt" ]] && grep -q 'eula=true' "${dossier}/eula.txt" 2>/dev/null; then
    succes "EULA Mojang déjà acceptée"
  else
    attention "L'EULA de Mojang doit être acceptée avant le premier démarrage."
    attention "Lis https://aka.ms/MinecraftEULA puis, si tu l'acceptes :"
    printf '      echo "eula=true" | sudo tee %s/eula.txt\n' "$dossier"
    printf '      sudo systemctl start minecraft\n'
  fi

  local memoire
  memoire="$(memoire_minecraft)"
  info "Mémoire allouée au serveur : ${memoire}"

  # Les options de GC (G1) sont celles recommandées par la communauté Paper :
  # elles réduisent nettement les micro-saccades dues aux pauses du ramasse-miettes.
  faire tee /etc/systemd/system/minecraft.service >/dev/null <<FIN
[Unit]
Description=Serveur Minecraft (PaperMC)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${compte}
Group=${compte}
WorkingDirectory=${dossier}
ExecStart=/usr/bin/java -Xms${memoire} -Xmx${memoire} \\
  -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 \\
  -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC \\
  -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 \\
  -jar ${dossier}/paper.jar nogui
Restart=on-failure
RestartSec=10s
SuccessExitStatus=0 1

# Cloisonnement : le service ne peut écrire que dans son propre dossier.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${dossier}

[Install]
WantedBy=multi-user.target
FIN

  faire systemctl daemon-reload
  faire systemctl enable minecraft

  info "Ouverture du port ${PORT_MINECRAFT}/tcp"
  if dispo ufw; then
    faire ufw allow "${PORT_MINECRAFT}/tcp"
  fi

  installer_sauvegarde "minecraft" "$dossier" 7

  succes "Minecraft installé — connexion sur $(ip_locale):${PORT_MINECRAFT}"
  info "Démarrer : sudo systemctl start minecraft"
  info "Journal  : sudo journalctl -u minecraft -f"
}

# Récupère le dernier build stable de Paper via l'API officielle.
telecharger_paper() {
  local dossier="$1" compte="$2"

  if ! (( CONFIRME )); then
    printf '      %scurl … https://api.papermc.io/v2/… -o %s/paper.jar%s\n' \
      "$C_JAUNE" "$dossier" "$C_FIN"
    return 0
  fi

  local version="${VERSION_MINECRAFT:-}"
  if [[ -z "$version" ]]; then
    version="$(curl -fsS https://api.papermc.io/v2/projects/paper |
      python3 -c 'import json,sys; print(json.load(sys.stdin)["versions"][-1])' 2>/dev/null)" || true
  fi

  if [[ -z "$version" ]]; then
    attention "Impossible de contacter l'API PaperMC."
    attention "Télécharge le jar manuellement depuis https://papermc.io/downloads"
    attention "et place-le dans ${dossier}/paper.jar"
    return 0
  fi

  local build
  build="$(curl -fsS "https://api.papermc.io/v2/projects/paper/versions/${version}/builds" |
    python3 -c '
import json, sys
builds = json.load(sys.stdin)["builds"]
stables = [b for b in builds if b.get("channel") == "default"]
print((stables or builds)[-1]["build"])' 2>/dev/null)" || true

  [[ -n "$build" ]] || { attention "Build Paper introuvable pour la version ${version}"; return 0; }

  local jar="paper-${version}-${build}.jar"
  info "Téléchargement de Paper ${version} build ${build}"
  curl -fsS -o "${dossier}/paper.jar" \
    "https://api.papermc.io/v2/projects/paper/versions/${version}/builds/${build}/downloads/${jar}" || {
      attention "Téléchargement échoué"
      return 0
    }

  chown "${compte}:${compte}" "${dossier}/paper.jar"
  succes "Paper ${version} (build ${build}) installé"
}

# Alloue de la mémoire au serveur de jeu en gardant de quoi faire tourner l'IA.
memoire_minecraft() {
  if [[ -n "${RAM_MINECRAFT:-}" ]]; then
    printf '%s\n' "$RAM_MINECRAFT"
    return 0
  fi

  local ram
  ram="$(ram_gio)"
  local alloue

  # Un serveur Minecraft familial se contente de 4 Gio. Au-delà, le gain est
  # marginal et la mémoire est plus utile au modèle de langage.
  if   (( ram >= 32 )); then alloue=6
  elif (( ram >= 16 )); then alloue=4
  elif (( ram >= 8 ));  then alloue=2
  else                       alloue=1
  fi

  printf '%dG\n' "$alloue"
}

# ---------------------------------------------------------------------------
# Valheim — SteamCMD
# ---------------------------------------------------------------------------

installer_valheim() {
  titre "Serveur Valheim (SteamCMD)"

  local dossier="${RACINE_JEUX}/valheim"
  local compte="valheim"

  # SteamCMD est dans le dépôt multiverse et exige d'accepter la licence Steam,
  # ce que debconf demande normalement de façon interactive.
  info "Installation de SteamCMD"
  faire dpkg --add-architecture i386
  faire apt-get update
  faire bash -c 'echo steam steam/question select "I AGREE" | debconf-set-selections'
  faire bash -c 'echo steam steam/license note "" | debconf-set-selections'
  faire apt-get install -y steamcmd

  creer_compte "$compte" "$dossier"

  info "Téléchargement du serveur Valheim (app ${APPID_VALHEIM})"
  faire sudo -u "$compte" /usr/games/steamcmd \
    +force_install_dir "${dossier}/serveur" \
    +login anonymous \
    +app_update "$APPID_VALHEIM" validate \
    +quit

  configurer_valheim "$dossier" "$compte"

  info "Ouverture des ports ${PORT_VALHEIM}-$((PORT_VALHEIM + 2))/udp"
  if dispo ufw; then
    faire ufw allow "${PORT_VALHEIM}:$((PORT_VALHEIM + 2))/udp"
  fi

  installer_sauvegarde "valheim" "${dossier}/.config/unity3d/IronGate/Valheim" 14

  succes "Valheim installé — connexion sur $(ip_locale):${PORT_VALHEIM}"
  info "Démarrer : sudo systemctl start valheim"
  info "Journal  : sudo journalctl -u valheim -f"
}

configurer_valheim() {
  local dossier="$1" compte="$2"
  local fichier_env="/etc/valheim.env"

  # Le mot de passe ne doit pas finir dans l'unité systemd, lisible par tous.
  # Il vit dans un fichier en mode 600, chargé par EnvironmentFile.
  if [[ -f "$fichier_env" ]]; then
    succes "Configuration existante conservée (${fichier_env})"
  else
    local mot_de_passe="${MOT_DE_PASSE_VALHEIM:-}"

    if [[ -z "$mot_de_passe" ]] && (( CONFIRME )); then
      attention "Valheim exige un mot de passe d'au moins 5 caractères,"
      attention "différent du nom du serveur."
      read -r -s -p "  Mot de passe du serveur : " mot_de_passe
      echo
    fi

    if [[ -z "$mot_de_passe" ]]; then
      mot_de_passe="a-changer"
      attention "Aucun mot de passe fourni : « ${mot_de_passe} » est posé temporairement."
      attention "Modifie-le dans ${fichier_env} avant d'ouvrir le serveur."
    fi

    faire tee "$fichier_env" >/dev/null <<FIN
NOM_SERVEUR=${NOM_SERVEUR_VALHEIM:-Serveur maison}
NOM_MONDE=${NOM_MONDE_VALHEIM:-Monde}
MOT_DE_PASSE=${mot_de_passe}
FIN
    faire chmod 600 "$fichier_env"
  fi

  faire tee /etc/systemd/system/valheim.service >/dev/null <<FIN
[Unit]
Description=Serveur Valheim
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${compte}
Group=${compte}
WorkingDirectory=${dossier}/serveur
EnvironmentFile=${fichier_env}
Environment="LD_LIBRARY_PATH=${dossier}/serveur/linux64"
Environment="SteamAppId=892970"
ExecStart=${dossier}/serveur/valheim_server.x86_64 \\
  -nographics -batchmode \\
  -name "\${NOM_SERVEUR}" \\
  -port ${PORT_VALHEIM} \\
  -world "\${NOM_MONDE}" \\
  -password "\${MOT_DE_PASSE}" \\
  -public 0
Restart=on-failure
RestartSec=10s

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${dossier}

[Install]
WantedBy=multi-user.target
FIN

  faire systemctl daemon-reload
  faire systemctl enable valheim

  info "Le serveur est en mode privé (-public 0) : rejoins-le par son adresse IP."
}

# ---------------------------------------------------------------------------

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --confirm)          CONFIRME=1 ;;
      minecraft|valheim)  JEUX+=("$1") ;;
      -h|--help)          usage; exit 0 ;;
      *)                  fatal "Argument inconnu : $1" ;;
    esac
    shift
  done

  [[ ${#JEUX[@]} -gt 0 ]] || JEUX=(minecraft valheim)

  exiger_root "$@"
  demarrer_journal "04-jeux"

  if ! (( CONFIRME )); then
    attention "Mode simulation : les commandes en jaune seraient exécutées, rien n'est modifié."
    attention "Pour exécuter réellement : sudo $0 --confirm"
  fi

  faire mkdir -p "$RACINE_JEUX"

  avertir_memoire

  local jeu
  for jeu in "${JEUX[@]}"; do
    case "$jeu" in
      minecraft) installer_minecraft ;;
      valheim)   installer_valheim ;;
    esac
  done

  echo
  if (( CONFIRME )); then
    succes "Serveurs de jeu installés."
    attention "Pour jouer depuis l'extérieur de la maison, il faut rediriger les ports"
    attention "sur ta box Internet. Cela expose la machine : voir docs/exploitation.md."
  else
    info "Simulation terminée. Rien n'a été modifié."
  fi
}

# La cohabitation IA + jeu est le principal piège de cette machine : deux gros
# consommateurs de RAM, et un dépassement tue le service le moins prioritaire.
avertir_memoire() {
  local ram
  ram="$(ram_gio)"

  if (( ram < 16 )); then
    attention "Avec ${ram} Gio de RAM, faire tourner un LLM et un serveur de jeu"
    attention "en même temps risque de saturer la mémoire. Mieux vaut alterner :"
    attention "  sudo systemctl stop ollama    avant de lancer une partie"
  elif (( ram < 32 )); then
    info "Avec ${ram} Gio de RAM, la cohabitation est possible mais serrée."
    info "Voir docs/exploitation.md pour plafonner la mémoire de chaque service."
  fi
}

main "$@"
