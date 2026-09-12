#!/bin/bash
# Restaure un monde Valheim depuis une archive, apres l'avoir prouvee saine.
#
# Ecrit le 2026-09-12, la nuit ou la contamination « triche » s'est mise a se
# propager toute seule : 2 entites marquees a 21h32, 23 a 23h40, dont 21
# pieces de construction posees avec du bois marque. Restaurer a la main sous
# la pression, c'est renommer le mauvais dossier ; d'ou ce script.
#
# Deux garde-fous qui valent leur poids :
#
#   1. On AUDITE l'archive avant de toucher au monde en place. Restaurer une
#      archive deja contaminee ne se verrait qu'apres coup, une fois le monde
#      courant deja ecrase. --force existe pour les cas ou on sait ce qu'on
#      fait, et il faut le taper.
#   2. On ne SUPPRIME jamais le monde courant : on le deplace sous un nom
#      date. C'est la seule copie de ce qui a ete joue depuis la derniere
#      archive, et c'est aussi la piece a conviction si on veut comprendre
#      plus tard.
#
# Ce que ce script ne peut PAS faire : nettoyer les sacs des joueurs. Un
# inventaire de personnage vit dans le fichier de personnage, chez le joueur.
# Une restauration du monde ne le touche pas -- si quelqu'un reconnecte avec
# un objet marque dans son sac et s'en sert pour batir ou fabriquer, la
# contamination repart du meme pied.
set -euo pipefail

DONNEES=/var/lib/valheim/donnees
AUDIT=/usr/local/bin/triche-valheim.py
FORCE=0

usage() {
    echo "usage: $(basename "$0") [--force] <archive.tar.gz>" >&2
    echo "       --force : restaurer meme si l'archive contient des marques" >&2
    exit 2
}

while (( $# )); do
    case "$1" in
        --force) FORCE=1; shift ;;
        -h|--help) usage ;;
        -*) usage ;;
        *) ARCHIVE="$1"; shift ;;
    esac
done
[[ -n "${ARCHIVE:-}" ]] || usage
[[ -r "$ARCHIVE" ]] || { echo "archive illisible : $ARCHIVE" >&2; exit 1; }
(( EUID == 0 )) || { echo "a lancer en root : le monde appartient a valheim" >&2; exit 1; }

# Quel monde ? Celui que le serveur a charge, ou a defaut le seul que
# l'archive contienne. Se tromper de monde ici, c'est ecraser le mauvais.
MONDE=$(tr '\0' '\n' < /proc/"$(pgrep -f valheim_server.x86_64 | head -1)"/cmdline 2>/dev/null \
        | grep -A1 -x -- -world | tail -1 || true)
if [[ -z "$MONDE" ]]; then
    MONDE=$(tar tzf "$ARCHIVE" | sed -n 's|^\./worlds_local/\([^/]*\)/_main\..*|\1|p' \
            | sort -u | head -1)
fi
[[ -n "$MONDE" ]] || { echo "monde introuvable, ni dans le serveur ni dans l'archive" >&2; exit 1; }
echo "monde : $MONDE"
echo "archive : $ARCHIVE"

HORODATE=$(date +%Y%m%d-%H%M%S)
TEMP="$DONNEES/worlds_local/.restauration-$HORODATE"
trap 'rm -rf "$TEMP"' EXIT

# Extraction a cote, sur le meme systeme de fichiers : la bascule finale est
# alors un simple renommage, donc atomique. Extraire par-dessus le monde en
# place laisserait un monde mi-ancien mi-neuf si l'extraction echouait.
mkdir -p "$TEMP"
# --strip-components=3 : le « ./ » de tete compte comme un composant. Avec 2,
# on obtient un dossier « NordheimV2 » DANS le temporaire, l'audit ne trouve
# aucun chunk, annonce « 0 marque » -- et le monde en place se fait ecraser
# par du vide. C'est le garde-fou ci-dessous qui doit attraper ce genre de
# panne muette, pas la chance.
tar xzf "$ARCHIVE" -C "$TEMP" --strip-components=3 "./worlds_local/$MONDE"
CHUNKS=$(find "$TEMP" -maxdepth 1 -name '*.chunk' | wc -l)
FWL=$(find "$TEMP" -maxdepth 1 -name '_main.*.fwl2' | wc -l)
echo "extrait : $(ls -A "$TEMP" | wc -l) fichier(s), dont $CHUNKS chunk(s)"
if (( CHUNKS < 1 || FWL < 1 )); then
    echo "REFUS : extraction vide ou incomplete ($CHUNKS chunk, $FWL fwl2)." >&2
    echo "Un audit sur un dossier vide repond « 0 marque » : on ne s'y fie pas." >&2
    exit 1
fi

if [[ -x "$AUDIT" ]]; then
    echo "--- audit de l'archive ---"
    RESULTAT=$("$AUDIT" --dossier "$TEMP")
    echo "$RESULTAT"
    if ! grep -q ": 0 ZDO marque(s) .*, 0 pile" <<<"$RESULTAT"; then
        if (( FORCE )); then
            echo "archive NON saine, mais --force demande : on continue" >&2
        else
            echo "REFUS : cette archive contient deja des marques de triche." >&2
            echo "Choisis-en une plus ancienne, ou relance avec --force." >&2
            exit 1
        fi
    fi
else
    echo "audit indisponible ($AUDIT absent) : restauration sans verification" >&2
fi

echo "--- arret du serveur ---"
systemctl stop valheim.service

QUARANTAINE="$DONNEES/worlds_local/${MONDE}_avant-restauration-$HORODATE"
mv "$DONNEES/worlds_local/$MONDE" "$QUARANTAINE"
mv "$TEMP" "$DONNEES/worlds_local/$MONDE"
trap - EXIT
chown -R valheim:valheim "$DONNEES/worlds_local/$MONDE"
chmod -R u=rwX,go=rX "$DONNEES/worlds_local/$MONDE"

echo "monde precedent conserve dans : $QUARANTAINE"
echo "--- redemarrage ---"
systemctl start valheim.service
echo "fait. Verifie avec : journalctl -u valheim -f"
