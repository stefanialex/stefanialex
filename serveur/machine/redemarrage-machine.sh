#!/bin/bash
# Redemarrage mensuel de la machine.
#
# Les mises a jour de securite s'installent toutes seules, mais un nouveau
# noyau ne prend effet qu'au redemarrage : sans celui-ci, la machine tourne
# indefiniment sur un noyau corrige mais pas charge.
#
# Ce n'est pas le redemarrage quotidien du jeu, qui ne touche pas au systeme.
set -euo pipefail

annonce() {
    local url
    url=$(grep -oP '(?<=^WEBHOOK=).*' /etc/valheim-discord.conf 2>/dev/null | tr -d '"' || true)
    [ -n "$url" ] || return 0
    curl -sS -m 15 -H 'Content-Type: application/json' \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1], "allowed_mentions": {"parse": []}}))' "$1")" \
        "$url" >/dev/null 2>&1 || true
}

EN_JEU=$(/usr/local/bin/stats-valheim.py --json 2>/dev/null \
    | python3 -c 'import json,sys
d = json.load(sys.stdin)
print(" ".join(j["pseudo"] for j in d["joueurs"] if j["en_cours"]))' 2>/dev/null || true)

if [ -n "$EN_JEU" ]; then
    # On ne coupe pas une partie en cours pour un redemarrage d'entretien : il
    # attendra le mois prochain, ou une execution manuelle.
    echo "joueurs en jeu ($EN_JEU) : redemarrage reporte"
    exit 0
fi

echo "aucun joueur : redemarrage d'entretien"
annonce "🔧 Redémarrage mensuel du serveur pour appliquer les mises à jour du système. Retour dans deux ou trois minutes."

/usr/local/bin/sauvegarde-valheim.sh
# L'arret du service ecrit le monde sur disque (KillSignal=SIGINT). On le fait
# explicitement avant le redemarrage plutot que de compter sur l'ordre
# d'extinction de systemd.
systemctl stop valheim.service
sync
systemctl reboot
