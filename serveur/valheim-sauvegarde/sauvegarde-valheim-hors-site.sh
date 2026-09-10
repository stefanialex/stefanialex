#!/bin/bash
# Envoie une archive par jour hors de la machine.
#
# Les trois copies locales sont sur trois disques, mais dans le meme boitier :
# un incendie, un vol ou une alimentation qui grille tout les emporte ensemble.
# Cette copie-la est la seule qui survive a la perte de la machine.
set -euo pipefail

SOURCE=/srv/jeux/sauvegardes
DISTANT=gdrive:sauvegardes-valheim
CONF=/etc/rclone/rclone.conf
RETENTION_DISTANTE=90d

DERNIERE=$(ls -1t "$SOURCE"/valheim-*.tar.gz 2>/dev/null | head -1)
if [ -z "$DERNIERE" ]; then
    echo "aucune archive locale a envoyer" >&2
    exit 1
fi

# On revalide avant de televerser : envoyer une archive illisible hors site
# donnerait une fausse assurance, ce qui est pire que pas de copie du tout.
gzip -t "$DERNIERE"

OPTS=(--config "$CONF" --drive-use-trash=false --retries 3 --low-level-retries 5 --timeout 120s)

rclone copy "${OPTS[@]}" "$DERNIERE" "$DISTANT/"
rclone delete "${OPTS[@]}" --min-age "$RETENTION_DISTANTE" "$DISTANT/"

NB=$(rclone ls "${OPTS[@]}" "$DISTANT/" | wc -l)
POIDS=$(rclone size "${OPTS[@]}" "$DISTANT/" 2>/dev/null | tail -1)
echo "$(basename "$DERNIERE") envoye hors site ; $NB archives sur le Drive ($POIDS)"
