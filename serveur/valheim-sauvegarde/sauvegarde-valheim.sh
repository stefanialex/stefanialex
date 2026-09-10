#!/bin/bash
# Sauvegarde du monde Valheim, verifiee et repliquee sur trois disques distincts.
#
# Le monde vit sur le SSD (sda3). Une archive posee sur un seul disque ne protege que
# d'une fausse manoeuvre, pas d'une panne materielle : d'ou les miroirs.
set -euo pipefail

SOURCE=/var/lib/valheim/donnees
PRIMAIRE=/srv/jeux/sauvegardes                 # sdc1 - disque mecanique
MIROIRS=(/srv/ia/sauvegardes-valheim           # sdb1 - autre disque mecanique
         /var/backups/valheim)                 # sda3 - SSD systeme
RETENTION_JOURS=30
GRAIN_FIN_JOURS=3   # en deca, on garde chaque heure ; au-dela, une par jour

NOM="valheim-$(date +%Y%m%d-%H%M%S).tar.gz"

mkdir -p "$PRIMAIRE"
# On ecrit sous un nom temporaire : une archive interrompue ne doit jamais
# pouvoir passer pour une archive valide.
#
# `Midgard.db.new` est le fichier que le jeu ecrit avant de le renommer par
# dessus `Midgard.db`. Il est transitoire et a moitie ecrit : l'archiver n'a
# aucun interet, et c'est lui qui disparaissait sous le nez de tar.
#
# Reste l'horodatage du dossier, qui bouge des qu'une sauvegarde du jeu tombe
# pendant l'archivage - soit une fois sur deux, le jeu sauvegardant toutes les
# 10 min. tar sort alors en 1, ce qui suffisait a tuer le script via `set -e`
# alors que l'archive etait bonne. `Midgard.db` n'est jamais reecrit sur place
# (le jeu procede par renommage), donc ce qu'on lit reste coherent.
# Seul le code 2 - erreur fatale, disque plein ou source absente - doit
# arreter la sauvegarde ; la verification ci-dessous refuse de toute facon une
# archive illisible.
CODE_TAR=0
tar czf "$PRIMAIRE/$NOM.partiel" -C "$SOURCE" --exclude='*.new' . || CODE_TAR=$?
if (( CODE_TAR >= 2 )); then
    echo "tar a echoue (code $CODE_TAR), archive abandonnee" >&2
    rm -f "$PRIMAIRE/$NOM.partiel"
    exit 1
fi

# Verification avant publication. Sans ca on empile des archives dont on
# ignore si elles sont lisibles - le pire des cas le jour ou on en a besoin.
gzip -t "$PRIMAIRE/$NOM.partiel"
tar tzf "$PRIMAIRE/$NOM.partiel" >/dev/null
mv "$PRIMAIRE/$NOM.partiel" "$PRIMAIRE/$NOM"

for m in "${MIROIRS[@]}"; do
    mkdir -p "$m"
    cp -p "$PRIMAIRE/$NOM" "$m/$NOM.partiel"
    mv "$m/$NOM.partiel" "$m/$NOM"
done

for d in "$PRIMAIRE" "${MIROIRS[@]}"; do
    # Au-dela de la retention, on supprime.
    find "$d" -name 'valheim-*.tar.gz' -mtime "+$RETENTION_JOURS" -delete

    # Eclaircissage : passe 3 jours, une seule archive par jour suffit. Sans ca,
    # 24 archives quotidiennes finissent par saturer le disque quand le monde
    # grossit - un monde longuement explore depasse facilement 100 Mio.
    find "$d" -name 'valheim-*.tar.gz' -mtime +"$GRAIN_FIN_JOURS" -printf '%f\n' \
        | sort \
        | awk -F'-' '{ jour = $2 } jour == precedent { print } { precedent = jour }' \
        | while read -r vieille; do rm -f "$d/$vieille"; done

    find "$d" -name '*.partiel' -mmin +60 -delete
done

TAILLE=$(du -h "$PRIMAIRE/$NOM" | cut -f1)
NB=$(find "$PRIMAIRE" -name 'valheim-*.tar.gz' | wc -l)
echo "$NOM ($TAILLE) verifiee, repliquee sur ${#MIROIRS[@]} disques ; $NB archives conservees"
