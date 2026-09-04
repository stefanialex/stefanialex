#!/bin/bash
# Rend Cockpit joignable meme si la box change l'adresse du serveur.
#
# Le probleme : Cockpit ecoute sur 192.168.1.120 en dur. Cette adresse vient du
# DHCP de la box, sans reservation possible -- l'acces a la box n'est pas
# disponible. Le socket a FreeBind=yes, donc il se lierait quand meme a une
# adresse absente : Cockpit demarrerait sans etre joignable, en silence.
#
# La solution retenue : ajouter une deuxieme adresse fixe sur la carte reseau,
# 192.168.1.253, choisie parmi les adresses hautes et verifiee libre par sonde
# ARP. Cockpit ecoute sur les deux. L'ancienne adresse reste en place pour la
# redirection de ports du jeu, que la box seule pourrait changer.
#
# Pourquoi pas le pare-feu. L'autre approche consistait a faire ecouter Cockpit
# partout et a refuser le port 9090 sur tailscale0. Elle a ete ecartee pour une
# raison de verifiabilite : depuis la machine elle-meme, un appel a sa propre
# adresse Tailscale passe par la boucle locale et non par l'interface, donc
# aucune commande locale ne peut prouver que les PC des autres joueurs -- qui
# sont sur le tailnet et pour lesquels le pare-feu autorise tous les ports --
# n'atteignent pas le formulaire de connexion. En gardant une ecoute liee a des
# adresses precises, la preuve redevient locale et immediate.
#
# Rien ne s'execute sans --confirm.
set -euo pipefail

UUID=dc5ebfde-eff1-30f9-b3a2-ae06dbb3c352
CARTE=enp0s31f6
ANCIENNE=192.168.1.120
NOUVELLE=192.168.1.253
PASSERELLE=192.168.1.254
DROPIN=/etc/systemd/system/cockpit.socket.d/ecoute-locale.conf
SECOURS=/var/backups/cockpit-ecoute-locale.conf.avant
CONFIRM=0

jaune() { printf '\033[33m%s\033[0m\n' "$*"; }
mourir() { printf '\033[31merreur : %s\033[0m\n' "$*" >&2; exit 1; }

[ "${1:-}" = "--confirm" ] && CONFIRM=1

[ "$(id -u)" -eq 0 ] || mourir "a lancer avec sudo"
[ -f "$DROPIN" ] || mourir "$DROPIN absent : configuration de Cockpit inattendue"

echo
echo "  carte reseau        $CARTE"
echo "  adresses apres      $ANCIENNE/24 (inchangee) + $NOUVELLE/24 (nouvelle)"
echo "  Cockpit ecoutera    $ANCIENNE:9090 et $NOUVELLE:9090"
echo
jaune "  Ta session Cockpit va se couper quelques secondes : cockpit.service a"
jaune "  Requires=cockpit.socket, donc redemarrer le socket arrete Cockpit."
jaune "  Reconnecte-toi ensuite sur l'une ou l'autre adresse."
echo
echo "  Verification automatique apres bascule, et retour arriere immediat si"
echo "  l'une des deux adresses ne repond pas."
echo

if [ "$CONFIRM" -eq 0 ]; then
    jaune "simulation : rien n'a ete modifie. Ajoute --confirm pour executer."
    exit 0
fi

retour_arriere() {
    jaune "retour arriere en cours"
    nmcli connection modify "$UUID" ipv4.addresses "$ANCIENNE/24" \
        ipv4.gateway "$PASSERELLE" || true
    nmcli device reapply "$CARTE" || true
    [ -f "$SECOURS" ] && cp -f "$SECOURS" "$DROPIN"
    systemctl daemon-reload || true
    systemctl restart cockpit.socket || true
    jaune "configuration precedente restauree"
}

mkdir -p "$(dirname "$SECOURS")"
cp -f "$DROPIN" "$SECOURS"

echo "-- 1. deuxieme adresse sur la carte"
nmcli connection modify "$UUID" \
    ipv4.addresses "$ANCIENNE/24,$NOUVELLE/24" ipv4.gateway "$PASSERELLE"
nmcli device reapply "$CARTE"
ip -4 addr show "$CARTE" | grep inet

echo "-- 2. ecoute de Cockpit sur les deux adresses"
cat > "$DROPIN" <<'BLOC'
# Cockpit n'ecoute que sur le reseau local, pas sur tailscale0 : le tailnet
# contient les machines partagees des autres joueurs, et le pare-feu y autorise
# tous les ports (« allow in on tailscale0 »). Voir README, section Cockpit.
#
# Deux adresses : celle du DHCP, gardee pour ne rien casser, et 192.168.1.253
# qui est fixe et ne depend pas de la box. Si la box change la premiere, la
# seconde continue de repondre.
[Socket]
ListenStream=
ListenStream=192.168.1.120:9090
ListenStream=192.168.1.253:9090
FreeBind=yes
BLOC
systemctl daemon-reload
systemctl restart cockpit.socket

echo "-- 3. verification"
sleep 3
ECHEC=""
ss -tln | grep -q "$ANCIENNE:9090" || ECHEC="pas d'ecoute sur $ANCIENNE"
ss -tln | grep -q "$NOUVELLE:9090" || ECHEC="${ECHEC:+$ECHEC ; }pas d'ecoute sur $NOUVELLE"
for a in "$ANCIENNE" "$NOUVELLE"; do
    C=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$a:9090/" || echo 000)
    echo "  https://$a:9090/ -> $C"
    [ "$C" = "200" ] || ECHEC="${ECHEC:+$ECHEC ; }$a repond $C"
done

# L'ecoute doit rester liee : aucune adresse Tailscale dans la liste.
if ss -tln | grep 9090 | grep -qE '0\.0\.0\.0|100\.'; then
    ECHEC="${ECHEC:+$ECHEC ; }Cockpit ecoute au-dela du reseau local"
fi

if [ -n "$ECHEC" ]; then
    printf '\033[31mverification echouee : %s\033[0m\n' "$ECHEC" >&2
    retour_arriere
    exit 1
fi

echo
echo "Cockpit repond sur les deux adresses, et sur elles seules."
echo "Adresse a retenir, celle qui ne bougera plus : https://$NOUVELLE:9090"
