#!/bin/bash
# Bascule le serveur Valheim sur un monde neuf, avec une seed choisie.
#
# Ecrit pour la 1.0 du 9 septembre 2026 : monde neuf, personnages neufs, defis
# remis a zero. Le serveur dedie n'a pas de parametre -seed -- il tire au hasard
# si le monde n'existe pas -- donc la seed est imposee en fabriquant le .fwl
# d'avance avec monde-valheim.py. Le serveur genere le .db ensuite, le monde de
# Valheim etant produit zone par zone a la demande.
#
# Rien ne s'execute sans --confirm : sans ce drapeau, le script affiche ce qu'il
# ferait et s'arrete.
set -euo pipefail

SAVEDIR=/var/lib/valheim/donnees
MONDES="$SAVEDIR/worlds_local"
ARCHIVES="$SAVEDIR/anciens-mondes"
ENV=/etc/valheim.env
OUTIL=/usr/local/bin/monde-valheim.py
SAUVEGARDE=/usr/local/bin/sauvegarde-valheim.sh
JOURNAL=/var/log/serveur-ia

NOM=""
SEED=""
CONFIRM=0
FORCE=0
GENERATEUR=""

jaune() { printf '\033[33m%s\033[0m\n' "$*"; }
mourir() { printf '\033[31merreur : %s\033[0m\n' "$*" >&2; exit 1; }

aide() {
    cat <<'AIDE'
Usage : nouveau-monde-valheim.sh --nom NOM [--seed SEED] [--confirm] [--force]

  --nom NOM         nom du nouveau monde (obligatoire), casse comprise
  --seed SEED       seed a imposer ; par defaut, 10 caracteres tires au hasard
                    comme le fait le jeu
  --generateur N    version du generateur de monde a inscrire dans le .fwl.
                    Par defaut, celle du monde actuel. A verifier apres la 1.0 :
                    si un monde cree par la 1.0 annonce autre chose, passer
                    cette valeur, sinon le serveur refusera le fichier.
  --force           bascule meme si des joueurs sont connectes (ils seront
                    deconnectes, leur progression du moment sauvegardee)
  --confirm         execute pour de vrai
AIDE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --nom) NOM="${2:-}"; shift 2 ;;
        --seed) SEED="${2:-}"; shift 2 ;;
        --generateur) GENERATEUR="${2:-}"; shift 2 ;;
        --confirm) CONFIRM=1; shift ;;
        --force) FORCE=1; shift ;;
        -h|--help) aide; exit 0 ;;
        *) mourir "argument inconnu : $1" ;;
    esac
done

[ "$(id -u)" -eq 0 ] || mourir "a lancer avec sudo"
[ -n "$NOM" ] || { aide; mourir "--nom est obligatoire"; }
[ -x "$OUTIL" ] || mourir "$OUTIL absent"
[[ "$NOM" =~ ^[A-Za-z0-9_-]+$ ]] || mourir "nom de monde invalide : lettres, chiffres, - et _ seulement"

# La seed du jeu fait 10 caracteres alphanumeriques. On accepte plus large, mais
# on refuse ce qui ne survivrait pas a l'aller-retour avec le champ du jeu.
if [ -z "$SEED" ]; then
    SEED=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 10)
    jaune "aucune seed donnee, tiree au hasard : $SEED"
fi
[[ "$SEED" =~ ^[A-Za-z0-9]{1,32}$ ]] || mourir "seed invalide : lettres et chiffres, 32 au plus"

# Version du generateur : celle du monde actuel, sauf indication contraire. Un
# monde cree avec la mauvaise valeur est refuse au chargement.
ACTUEL=$(grep -oP '(?<=^NOM_MONDE=).*' "$ENV" | tr -d '"' || true)
if [ -z "$GENERATEUR" ]; then
    # Les deux formats sont possibles ; monde-valheim.py sait lequel est vivant.
    META_ACTUEL=$("$OUTIL" chemin "$MONDES" "$ACTUEL" 2>/dev/null || true)
    if [ -n "$META_ACTUEL" ]; then
        GENERATEUR=$("$OUTIL" lire "$META_ACTUEL" \
            | awk '/^version_generateur/ { print $2 }')
    fi
fi
GENERATEUR="${GENERATEUR:-2}"

# Depuis la 1.0 (format 41), un monde est un dossier et son fichier de
# metadonnees porte quatre octets de queue dont le sens n'est pas etabli.
# Ecrire quand meme produirait un fichier que le serveur refuse : il le
# signale par un « data error LoadError » noye dans son journal, puis genere
# un monde a la seed au hasard. On aurait donc un monde neuf, sans la seed
# demandee, et rien pour le dire. Mieux vaut s'arreter ici.
if [ -n "${META_ACTUEL:-}" ]; then
    FORMAT_ACTUEL=$("$OUTIL" lire "$META_ACTUEL" \
        | awk '/^version_format/ { print $2 }')
    if [ "${FORMAT_ACTUEL:-0}" -ge 41 ]; then
        mourir "le serveur est en 1.0 (format $FORMAT_ACTUEL) et ce script ne
sait pas encore y imposer une seed.

Pour un monde neuf a seed ALEATOIRE, il n'y a rien a faire ici : mettre son
nom dans NOM_MONDE de $ENV puis redemarrer valheim.service suffit, le serveur
le genere lui-meme. Verifie le 2026-09-09 avec NordheimV1.

Pour imposer une seed, il faut d'abord identifier les quatre octets de queue
du format 41 sur un monde cree par la 1.0."
    fi
fi

if META_EXISTANT=$("$OUTIL" chemin "$MONDES" "$NOM" 2>/dev/null); then
    mourir "$META_EXISTANT existe deja ; choisis un autre nom"
fi

# Personne ne doit etre en jeu : l'arret deconnecte tout le monde, et une
# bascule de monde pendant qu'on joue perd la session en cours.
EN_JEU=$(/usr/local/bin/stats-valheim.py --json 2>/dev/null \
    | python3 -c 'import json,sys
d = json.load(sys.stdin)
print(" ".join(j["pseudo"] for j in d["joueurs"] if j["en_cours"]))' 2>/dev/null || true)
if [ -n "$EN_JEU" ] && [ "$FORCE" -eq 0 ]; then
    mourir "joueurs en jeu ($EN_JEU) ; attends qu'ils sortent, ou --force"
fi

SEED_ENTIERE=$("$OUTIL" hash "$SEED")

echo
echo "  monde actuel        $ACTUEL  ->  archive dans $ARCHIVES/"
echo "  nouveau monde       $NOM"
echo "  seed                $SEED  (entier $SEED_ENTIERE)"
echo "  generateur          version $GENERATEUR"
echo "  joueurs en jeu      ${EN_JEU:-aucun}"
echo
echo "  1. sauvegarde complete et verifiee du monde actuel, sur trois disques"
echo "  2. arret propre du serveur (il ecrit le monde en s'arretant)"
echo "  3. deplacement des fichiers de $ACTUEL vers $ARCHIVES/"
echo "  4. fabrication de $MONDES/$NOM.fwl avec la seed choisie"
echo "  5. NOM_MONDE=$NOM dans $ENV"
echo "  6. redemarrage, puis verification que le monde neuf est bien charge"
echo

if [ "$CONFIRM" -eq 0 ]; then
    jaune "simulation : rien n'a ete modifie. Ajoute --confirm pour executer."
    exit 0
fi

mkdir -p "$JOURNAL"
TRACE="$JOURNAL/nouveau-monde-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$TRACE") 2>&1
echo "== bascule vers le monde $NOM, seed $SEED, $(date -Is) =="

echo "-- 1. sauvegarde"
[ -x "$SAUVEGARDE" ] && "$SAUVEGARDE" || jaune "$SAUVEGARDE absent, etape sautee"

echo "-- 2. arret du serveur"
systemctl stop valheim.service
echo "arrete"

echo "-- 3. archivage de l'ancien monde"
mkdir -p "$ARCHIVES"
chown valheim:valheim "$ARCHIVES"
if [ -n "$ACTUEL" ]; then
    # Les sauvegardes automatiques du jeu partent avec : elles appartiennent a
    # l'ancien monde et n'ont plus rien a faire a cote du nouveau.
    shopt -s nullglob
    for f in "$MONDES/$ACTUEL".* "$MONDES/${ACTUEL}_backup_auto-"*; do
        mv -v "$f" "$ARCHIVES/"
    done
    shopt -u nullglob
fi

echo "-- 4. fabrication du monde neuf"
"$OUTIL" creer "$MONDES/$NOM.fwl" --monde "$NOM" --seed "$SEED" \
    --version-generateur "$GENERATEUR"
chown valheim:valheim "$MONDES/$NOM.fwl"
chmod 644 "$MONDES/$NOM.fwl"
"$OUTIL" lire "$MONDES/$NOM.fwl"

echo "-- 5. bascule de la configuration"
# On reecrit la seule ligne NOM_MONDE : le fichier contient aussi le mot de
# passe du serveur, qui ne doit ni bouger ni apparaitre dans un journal.
if grep -q '^NOM_MONDE=' "$ENV"; then
    sed -i "s|^NOM_MONDE=.*|NOM_MONDE=$NOM|" "$ENV"
else
    echo "NOM_MONDE=$NOM" >> "$ENV"
fi
grep '^NOM_MONDE=' "$ENV"

echo "-- 6. redemarrage et verification"
DEPART=$(date -Is)
systemctl start valheim.service

# Le serveur met une minute a charger. On attend la preuve, dans un sens ou
# dans l'autre : la ligne de chargement du monde, ou l'erreur de format.
for _ in $(seq 60); do
    if journalctl -u valheim --since "$DEPART" --no-pager -o cat 2>/dev/null \
        | grep -q "Load world: $NOM"; then
        VERDICT=charge; break
    fi
    if journalctl -u valheim --since "$DEPART" --no-pager -o cat 2>/dev/null \
        | grep -qE 'LoadError|error loading world'; then
        VERDICT=refuse; break
    fi
    sleep 3
done

case "${VERDICT:-attente}" in
    charge)
        echo
        echo "monde « $NOM » charge, seed $SEED."
        journalctl -u valheim --since "$DEPART" --no-pager -o cat | grep "Load world" | tail -2
        echo "Les joueurs doivent creer un personnage neuf : le fichier de"
        echo "personnage vit chez eux, le serveur n'y touche pas."
        ;;
    refuse)
        mourir "le serveur a refuse le .fwl fabrique. L'ancien monde est intact
dans $ARCHIVES/ ; verifie la version du generateur avec --generateur et
relance, ou restaure l'ancien monde en remettant ses fichiers dans $MONDES/
et NOM_MONDE=$ACTUEL dans $ENV."
        ;;
    *)
        mourir "aucune trace de chargement au bout de 3 minutes ; regarde
journalctl -u valheim"
        ;;
esac

echo "trace complete : $TRACE"
