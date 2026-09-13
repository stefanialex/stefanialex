# Serveur Valheim — installation pas à pas

Marche à suivre manuelle, commande par commande, pour un serveur **privé**
(non listé publiquement) **sans crossplay** (Steam uniquement), joignable par
**Tailscale**.

Le choix de Tailscale est délibéré : il évite toute redirection de port sur la
box, n'expose **rien** sur Internet, et donne au serveur une adresse qui ne
change jamais. Voir l'étape 6 pour la comparaison avec les deux alternatives.

Chaque étape indique ce que tu dois voir pour savoir qu'elle a réussi. Si une
sortie diffère, arrête-toi là plutôt que d'enchaîner.

---

## Ce dont le serveur a besoin

| Ressource | Minimum | Confortable | Pourquoi |
|---|---|---|---|
| RAM | 2 Gio | 4 Gio | Le serveur consomme ~3 Gio en pratique. 8 Gio si 10+ joueurs ou des mods |
| CPU | 2 cœurs | 4 cœurs | La simulation du monde est largement **mono-thread** : la fréquence compte plus que le nombre de cœurs |
| Disque | 4 Gio | 20 Gio | ~2 Gio d'installation, le reste pour le monde et les sauvegardes |
| Réseau | — | Ethernet | En Wi-Fi, les micro-coupures se voient chez tous les joueurs |

Aucun GPU nécessaire : le serveur tourne en `-nographics -batchmode`.

Pour mesurer ta machine :

```bash
nproc
grep -m1 'model name' /proc/cpuinfo
free -h
df -h /
ip -brief address
```

---

## Étape 1 — Dépendances

Pop!_OS est basé sur Ubuntu : `steamcmd` vient du dépôt *multiverse*. Le binaire
est 32 bits, il faut activer cette architecture.

```bash
sudo dpkg --add-architecture i386
sudo add-apt-repository multiverse -y
sudo apt update
sudo apt install -y steamcmd
```

Un écran bleu demande d'accepter la licence Steam : `Tab` puis `Entrée` sur
**I AGREE**.

**Vérification :**

```bash
which steamcmd
```

Doit répondre `/usr/games/steamcmd`.

---

## Étape 2 — Compte système dédié

Le serveur ne doit pas tourner sous ton compte personnel : s'il était compromis,
l'attaquant hériterait de tout ton accès. Un compte système sans shell de
connexion limite les dégâts.

```bash
sudo useradd --system --create-home --home-dir /srv/jeux/valheim \
             --shell /usr/sbin/nologin valheim
sudo mkdir -p /srv/jeux/valheim/serveur
sudo chown -R valheim:valheim /srv/jeux/valheim

# Le monde ne vit pas avec les binaires : il va sur le SSD, /srv/jeux etant un
# disque mecanique. Voir « Performances ».
sudo mkdir -p /var/lib/valheim/donnees
sudo chown -R valheim:valheim /var/lib/valheim
sudo chmod 750 /var/lib/valheim
```

**Vérification :**

```bash
id valheim
ls -ld /srv/jeux/valheim
```

Le dossier doit appartenir à `valheim:valheim`.

---

## Étape 3 — Installer le serveur

App ID **896660** — c'est le serveur dédié ; 892970 est le jeu lui-même.
Connexion anonyme, aucun compte Steam requis.

```bash
sudo -u valheim /usr/games/steamcmd \
  +force_install_dir /srv/jeux/valheim/serveur \
  +login anonymous \
  +app_update 896660 validate \
  +quit
```

Compter quelques minutes et environ 2 Gio de téléchargement. La dernière ligne
doit indiquer `Success! App '896660' fully installed.`

**Vérification :**

```bash
ls -l /srv/jeux/valheim/serveur/valheim_server.x86_64
```

---

## Étape 4 — Mot de passe

Deux règles imposées par Valheim, qui font échouer le démarrage **sans message
d'erreur clair** :

- le mot de passe fait **au moins 5 caractères** ;
- il **ne doit pas être contenu dans le nom du serveur**. « Valhalla » avec le
  mot de passe « valha » est refusé.

Le mot de passe ne doit pas se retrouver dans l'unité systemd, lisible par tous.
Il vit dans un fichier en `chmod 600` :

```bash
sudo tee /etc/valheim.env >/dev/null <<'FIN'
NOM_SERVEUR=Serveur des Vikings
NOM_MONDE=Midgard
MOT_DE_PASSE=change-moi-vraiment
MODIFICATEURS=
FIN
sudo chmod 600 /etc/valheim.env
sudo nano /etc/valheim.env
```

Mets un vrai mot de passe dans `nano`, puis `Ctrl+O`, `Entrée`, `Ctrl+X`.

### Les modificateurs de monde, et pourquoi ils passent par une variable

`MODIFICATEURS` est vide par défaut et porte les options de difficulté que
Valheim accepte en ligne de commande, sous la forme
`-modifier <categorie> <valeur>`, autant de fois qu'on veut :

| Catégorie | Valeurs |
|---|---|
| `combat` | `veryeasy` `easy` `hard` `veryhard` |
| `deathpenalty` | `casual` `veryeasy` `easy` `hard` `hardcore` |
| `resources` | `muchless` `less` `more` `muchmore` `most` |
| `raids` | `none` `muchless` `less` `more` `muchmore` |
| `portals` | `casual` `hard` `veryhard` |

Exemple, demandé par Alexandre le 2026-09-09 parce qu'il aime se faire
attaquer par les sangliers pour le butin :

```bash
MODIFICATEURS=-modifier raids muchmore
```

**Le `$` est sans accolades, et ce n'est pas une faute de frappe.** systemd
découpe `$VARIABLE` en plusieurs arguments sur les espaces, mais **pas**
`${VARIABLE}`, qui reste un argument unique. Avec des accolades, le serveur
recevrait `-modifier raids muchmore` comme un seul mot et l'ignorerait — sans
message d'erreur. C'est aussi pourquoi les autres variables du fichier gardent
leurs accolades **et** leurs guillemets : un nom de serveur avec un espace doit
rester un seul argument.

Changer un modificateur ne demande donc que d'éditer `/etc/valheim.env` puis
`systemctl restart valheim` — pas de `daemon-reload`, l'unité ne bouge pas.

Deux choses à savoir avant de monter les raids. Les événements sont **liés à la
progression** : le raid des sangliers est celui d'Eikthyr, donc il n'arrive
rien avant qu'il soit tombé, et monter la fréquence n'y change rien. Et ça
frotte avec le défi d'équipe « série de raids sans perte » : plus de raids veut
dire plus d'occasions d'allonger la série, mais aussi plus d'occasions de la
casser.

---

## Étape 5 — Service systemd

N'utilise pas le `start_server.sh` livré avec le serveur : Steam l'écrase à
chaque mise à jour. On appelle le binaire directement.

```bash
sudo tee /etc/systemd/system/valheim.service >/dev/null <<'FIN'
[Unit]
Description=Serveur Valheim
After=network-online.target
# Sans ces montages le service ne démarre pas du tout, plutôt que de démarrer
# et d'échouer de façon obscure — ou pire, de créer un monde vide.
RequiresMountsFor=/srv/jeux /var/lib/valheim
Wants=network-online.target

[Service]
Type=simple
# Pas de Nice= ici : il serait réécrit. Voir « Performances ».
CPUWeight=500
User=valheim
Group=valheim
WorkingDirectory=/srv/jeux/valheim/serveur
EnvironmentFile=/etc/valheim.env

# Sans SteamAppId le binaire refuse de démarrer : installé comme app 896660,
# il doit s'identifier comme le jeu 892970.
Environment="SteamAppId=892970"
Environment="LD_LIBRARY_PATH=/srv/jeux/valheim/serveur/linux64"

ExecStart=/srv/jeux/valheim/serveur/valheim_server.x86_64 \
  -nographics -batchmode \
  -name "${NOM_SERVEUR}" \
  -port 2456 \
  -world "${NOM_MONDE}" \
  -password "${MOT_DE_PASSE}" \
  -savedir /var/lib/valheim/donnees \
  $MODIFICATEURS \
  -public 0 \
  -saveinterval 600 \
  -backups 4 -backupshort 7200 -backuplong 43200

# Valheim sauvegarde le monde en s'arrêtant. Sans ces deux lignes, systemd le
# tue trop tôt et la progression depuis la dernière sauvegarde est perdue.
KillSignal=SIGINT
TimeoutStopSec=120

Restart=on-failure
RestartSec=10s

# Cloisonnement : le service n'écrit que dans son propre dossier.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/jeux/valheim /var/lib/valheim

[Install]
WantedBy=multi-user.target
FIN

sudo systemctl daemon-reload
sudo systemctl enable valheim
```

### Ce que signifient les options

| Option | Effet |
|---|---|
| `-public 0` | Serveur **privé** : absent de la liste publique, rejoint par IP |
| `-savedir` | Chemin explicite, au lieu de `~/.config/unity3d/…` — prévisible, et compatible avec `ProtectHome=true`. Pointé sur le SSD, voir « Performances » |
| `-saveinterval 600` | Sauvegarde automatique toutes les 10 minutes. C'est exactement ce qu'une coupure de courant peut emporter |
| `-backups 4` | Conserve 4 sauvegardes tournantes |
| *(absent)* `-crossplay` | Ouvre aux joueurs Xbox/PlayStation et fournit un code d'invitation. Inutile ici : Tailscale rend déjà le serveur joignable sans redirection. Voir l'étape 6 |

---

## Étape 6 — Réseau privé Tailscale

### Pourquoi, et les alternatives écartées

Pour que des joueurs extérieurs atteignent le serveur, il faut résoudre deux
problèmes : traverser la box, et disposer d'une adresse stable. Trois solutions
existent.

| Solution | Box à configurer | Adresse stable | Exposition Internet | Consoles |
|---|---|---|---|---|
| **Tailscale** | non | **oui, définitive** | **aucune** | non (PC seulement) |
| Redirection de ports | oui, NAT/PAT + bail statique | non — IP dynamique, sauf DNS dynamique | serveur exposé | oui |
| `-crossplay` | non | non — **le code change à chaque redémarrage** | aucune | oui |

Tailscale l'emporte dès que tous les joueurs sont sur PC. Le crossplay reste la
seule option si quelqu'un joue sur Xbox ou PlayStation : Tailscale ne s'installe
pas sur console.

### Installer

```bash
. /etc/os-release
CODE=${UBUNTU_CODENAME:-$VERSION_CODENAME}   # « noble » sur Pop!_OS 24.04

curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${CODE}.noarmor.gpg" \
  | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${CODE}.tailscale-keyring.list" \
  | sudo tee /etc/apt/sources.list.d/tailscale.list

sudo apt update
sudo apt install -y tailscale
```

### Authentifier la machine

```bash
sudo tailscale login --hostname=valheim-serveur --qr=false
```

La commande **bloque** en attendant que tu ouvres le lien d'authentification
dans un navigateur. Sur un serveur sans écran, ou si le lien ne s'affiche pas,
il est aussi écrit dans le journal :

```bash
sudo journalctl -u tailscaled --since -2min | grep -o 'https://login.tailscale.com/a/[a-z0-9]*'
```

Ne tue pas la commande `login` avant d'avoir validé dans le navigateur : le
processus doit rester vivant pour terminer l'enregistrement.

**Vérification :**

```bash
sudo tailscale status
sudo tailscale ip -4
```

Tu dois obtenir une adresse en `100.x.y.z` — ici **`100.76.246.124`**. Elle est
attribuée une fois pour toutes : ni un redémarrage, ni un changement d'IP
publique ne la modifient.

### Dans la console d'administration

Deux réglages qui ne se font pas en ligne de commande, sur
[login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines).

**1. Désactiver l'expiration de la clé.** Menu `...` de la ligne
`valheim-serveur` → **Disable key expiry**. Sans ça la clé expire au bout de
180 jours et le serveur disparaît du réseau sans prévenir — une panne
incompréhensible six mois plus tard.

**2. Partager la machine.** Menu `...` → **Share...**, un lien par invité.
L'invité ne voit **que** cette machine, rien d'autre du réseau domestique, et
ne compte pas dans les 6 utilisateurs du plan gratuit. C'est préférable à
l'inviter comme utilisateur du réseau, ce qui lui donnerait accès à tout.

---

## Étape 7 — Pare-feu

Le serveur n'étant joignable que par le tunnel, **aucun port de jeu n'a besoin
d'être ouvert sur Internet**.

```bash
sudo ufw allow in on tailscale0 comment 'Reseau prive Tailscale'
sudo ufw allow 41641/udp comment 'Tailscale traversee NAT'
sudo ufw status verbose
```

`41641/udp` n'est pas indispensable : il permet aux pairs de se joindre en
**direct** plutôt que via un relais, ce qui réduit la latence. Comme aucune
redirection n'existe sur la box, rien ne peut l'atteindre depuis Internet.

Si le serveur a d'abord été exposé, retire l'ancienne règle :

```bash
sudo ufw delete allow 2456:2457/udp
```

État attendu — SSH en local, le reste par le tunnel, rien d'ouvert au monde :

```
Par défaut : deny (incoming), allow (outgoing)
22/tcp                     ALLOW IN    192.168.1.0/24
Anywhere on tailscale0     ALLOW IN    Anywhere
41641/udp                  ALLOW IN    Anywhere
```

---

## Étape 8 — Démarrer

```bash
sudo systemctl start valheim
sudo systemctl status valheim
sudo journalctl -u valheim -f
```

Le premier démarrage crée le monde et prend une à deux minutes. Dans le journal,
tu dois voir passer :

- `DungeonDB Start` puis `Zonesystem Awake` — le monde est chargé ;
- `Game server connected` — le serveur est en ligne.

`Ctrl+C` pour quitter le suivi du journal (ça n'arrête pas le serveur).

**Vérification :**

```bash
sudo ss -ulnp | grep 2456
sudo ls -l /var/lib/valheim/donnees/worlds_local/
```

Deux fichiers doivent exister : `Midgard.fwl` (le monde) et `Midgard.db` (les
données de jeu).

---

## Étape 9 — Se connecter

Une seule adresse sert à tout le monde, depuis la maison comme de l'extérieur :
celle du tunnel.

```bash
sudo tailscale ip -4      # ici 100.76.246.124
```

Dans Valheim : **Rejoindre une partie → Rejoindre par IP →**
`100.76.246.124:2456`, puis le mot de passe.

L'adresse locale `192.168.1.120` fonctionne aussi depuis la maison, mais autant
n'en retenir qu'une.

### Ce que chaque joueur doit faire

1. Ouvrir le lien de partage reçu et se connecter — compte Google, Microsoft ou
   GitHub, gratuit, aucune carte bancaire.
2. Installer Tailscale depuis [tailscale.com/download](https://tailscale.com/download)
   et se connecter avec **le même compte**.
3. Dans Valheim : **Rejoindre par IP** → `100.76.246.124:2456` + mot de passe.

Tailscale doit tourner pendant la partie. Il ne ralentit pas leur connexion :
seul le trafic à destination du serveur emprunte le tunnel, le reste de leur
Internet est inchangé.

À savoir : le serveur n'apparaît pas dans la liste Steam et le bouton
« Rejoindre » depuis la liste d'amis Steam ne fonctionne pas. C'est **Rejoindre
par IP**, à chaque fois.

Le serveur n'étant pas exposé sur Internet, la surface d'attaque est
quasi nulle — ce qui ne dispense pas de tenir la machine à jour
(`sudo apt update && sudo apt upgrade`).

---

## Étape 10 — Sauvegardes

Quatre pannes distinctes, quatre protections différentes. Le tableau dit
laquelle couvre quoi ; sans lui, on empile des sauvegardes sans savoir contre
quoi elles servent.

| Panne | Ce qui sauve | Perte maximale |
|---|---|---|
| Coupure de courant, plantage | `-saveinterval 600` | 10 min de jeu |
| Fausse manœuvre, monde corrompu | Archives horaires | 1 h |
| Un disque lâche | Miroirs sur les deux autres disques | 1 h |
| Incendie, vol, machine perdue | Copie quotidienne hors site | 24 h |

Valheim fait ses propres sauvegardes tournantes, mais **dans le même dossier**
que le monde : une panne de disque emporte les deux. D'où ce qui suit.

### Le script d'archivage

```bash
sudo tee /usr/local/bin/sauvegarde-valheim.sh >/dev/null <<'FIN'
#!/bin/bash
set -euo pipefail

SOURCE=/var/lib/valheim/donnees
PRIMAIRE=/srv/jeux/sauvegardes                 # sdc1 - disque mecanique
MIROIRS=(/srv/ia/sauvegardes-valheim           # sdb1 - autre disque mecanique
         /var/backups/valheim)                 # sda3 - SSD systeme
RETENTION_JOURS=30
GRAIN_FIN_JOURS=3

NOM="valheim-$(date +%Y%m%d-%H%M%S).tar.gz"

mkdir -p "$PRIMAIRE"
CODE_TAR=0
tar czf "$PRIMAIRE/$NOM.partiel" -C "$SOURCE" --exclude='*.new' . || CODE_TAR=$?
if (( CODE_TAR >= 2 )); then
    echo "tar a echoue (code $CODE_TAR), archive abandonnee" >&2
    rm -f "$PRIMAIRE/$NOM.partiel"
    exit 1
fi

gzip -t "$PRIMAIRE/$NOM.partiel"
tar tzf "$PRIMAIRE/$NOM.partiel" >/dev/null
mv "$PRIMAIRE/$NOM.partiel" "$PRIMAIRE/$NOM"

for m in "${MIROIRS[@]}"; do
    mkdir -p "$m"
    cp -p "$PRIMAIRE/$NOM" "$m/$NOM.partiel"
    mv "$m/$NOM.partiel" "$m/$NOM"
done

for d in "$PRIMAIRE" "${MIROIRS[@]}"; do
    find "$d" -name 'valheim-*.tar.gz' -mtime "+$RETENTION_JOURS" -delete
    find "$d" -name 'valheim-*.tar.gz' -mtime +"$GRAIN_FIN_JOURS" -printf '%f\n' \
        | sort \
        | awk -F'-' '{ jour = $2 } jour == precedent { print } { precedent = jour }' \
        | while read -r vieille; do rm -f "$d/$vieille"; done
    find "$d" -name '*.partiel' -mmin +60 -delete
done
FIN
sudo chmod 750 /usr/local/bin/sauvegarde-valheim.sh
```

Trois choix méritent d'être justifiés, parce qu'ils ne sautent pas aux yeux.

**L'écriture en `.partiel` puis le renommage.** Un `tar` interrompu — coupure de
courant, disque plein — laisse une archive tronquée. Sous son nom définitif,
rien ne la distingue d'une bonne, et on ne s'en aperçoit que le jour où on en a
besoin. Le renommage est atomique : le nom final n'apparaît qu'une fois
l'archive complète.

**La vérification avant publication.** `gzip -t` puis `tar tzf` coûtent quelques
millisecondes sur un monde de quelques mégaoctets. Sans eux, on accumule des
archives dont on ignore si elles sont lisibles, ce qui est pire que pas de
sauvegarde du tout : ça donne une fausse assurance.

**Les trois destinations.** Le monde vit sur le SSD (`sda3`). Les archives vont
sur les deux disques mécaniques **et** sur le SSD. Trois disques physiques :
aucune panne matérielle unique n'emporte l'ensemble.

**L'éclaircissage.** Passé trois jours, une seule archive par jour est
conservée. Sans ça, 24 archives quotidiennes finissent par saturer le disque
quand le monde grossit — un monde longuement exploré dépasse facilement 100 Mio.

**La tolérance au code de sortie 1 de `tar`.** Le jeu sauvegarde toutes les
10 minutes : une fois sur deux, l'archivage tombe pendant une sauvegarde. `tar`
signale alors « fichier modifié pendant sa lecture » et sort en 1 — un
avertissement, pas une erreur, mais `set -e` tuait le script et le service
partait en échec alors que l'archive était bonne. Seul le code 2, l'erreur
fatale, doit arrêter la sauvegarde ; l'archive reste de toute façon vérifiée
avant publication.

`Midgard.db` n'est jamais réécrit sur place — le jeu écrit `Midgard.db.new`
puis le renomme par dessus — donc ce que `tar` lit est toujours un monde
complet et cohérent, même si le renommage survient en cours d'archivage. Le
`.new`, lui, est exclu : à moitié écrit, il n'a aucune valeur, et c'est lui qui
disparaissait sous le nez de `tar`.

Ce détail n'était pas cosmétique : `jour-j-valheim.sh` et
`redemarrage-machine.sh` appellent ce script sous `set -e` avant de basculer le
monde ou de redémarrer la machine. Un échec ici les aurait arrêtés net.

### La minuterie horaire

```bash
sudo tee /etc/systemd/system/sauvegarde-valheim.service >/dev/null <<'FIN'
[Unit]
Description=Sauvegarde du monde Valheim
After=valheim.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/sauvegarde-valheim.sh
Nice=10
IOSchedulingClass=idle
FIN

sudo tee /etc/systemd/system/sauvegarde-valheim.timer >/dev/null <<'FIN'
[Unit]
Description=Sauvegarde horaire du monde Valheim

[Timer]
OnCalendar=hourly
RandomizedDelaySec=120
Persistent=true

[Install]
WantedBy=timers.target
FIN

sudo systemctl daemon-reload
sudo systemctl enable --now sauvegarde-valheim.timer
```

`Persistent=true` rattrape au démarrage une sauvegarde manquée pendant une
coupure. `Nice=10` et `IOSchedulingClass=idle` sont ici volontaires — à
l'inverse du serveur, l'archivage doit s'effacer devant la partie en cours.

### La copie hors site

Les trois copies sont sur trois disques, mais dans le même boîtier. Un
incendie, un vol ou une alimentation qui grille tout les emporte ensemble.

```bash
sudo apt install -y rclone

# Autorisation Google, une seule fois. Ouvre un navigateur sur cette machine.
# La portee « drive.file » limite rclone aux fichiers qu'il cree lui-meme :
# le reste du Drive lui reste invisible.
rclone config create gdrive drive scope=drive.file

# Le service tourne en root : il lui faut sa propre copie de la configuration,
# qui contient un jeton d'acces.
sudo mkdir -p /etc/rclone
sudo cp ~/.config/rclone/rclone.conf /etc/rclone/rclone.conf
sudo chown root:root /etc/rclone/rclone.conf && sudo chmod 600 /etc/rclone/rclone.conf
```

Le script d'envoi revalide l'archive avant de la téléverser — envoyer hors site
une archive illisible donnerait une assurance qui n'existe pas :

```bash
sudo tee /usr/local/bin/sauvegarde-valheim-hors-site.sh >/dev/null <<'FIN'
#!/bin/bash
set -euo pipefail

SOURCE=/srv/jeux/sauvegardes
DISTANT=gdrive:sauvegardes-valheim
CONF=/etc/rclone/rclone.conf
RETENTION_DISTANTE=90d

DERNIERE=$(ls -1t "$SOURCE"/valheim-*.tar.gz 2>/dev/null | head -1)
[ -n "$DERNIERE" ] || { echo "aucune archive locale a envoyer" >&2; exit 1; }

gzip -t "$DERNIERE"

OPTS=(--config "$CONF" --drive-use-trash=false --retries 3 --low-level-retries 5 --timeout 120s)
rclone copy "${OPTS[@]}" "$DERNIERE" "$DISTANT/"
rclone delete "${OPTS[@]}" --min-age "$RETENTION_DISTANTE" "$DISTANT/"
FIN
sudo chmod 750 /usr/local/bin/sauvegarde-valheim-hors-site.sh
```

Avec une minuterie quotidienne à 04 h 45, `After=network-online.target` sur le
service, et `--drive-use-trash=false` pour que les suppressions ne remplissent
pas la corbeille du Drive.

### Vérifier — et le faire pour de vrai

Une sauvegarde qu'on n'a jamais restaurée n'est pas une sauvegarde. Le test
complet, depuis la copie la plus éloignée :

```bash
T=$(mktemp -d)
rclone copy gdrive:sauvegardes-valheim/ "$T/"
A=$(ls -1 "$T"/valheim-*.tar.gz | head -1)

gzip -t "$A"                                  # l'archive est-elle intacte ?
tar tzf "$A" | grep worlds_local/             # contient-elle le monde ?

# Et la preuve : meme somme de controle que l'originale locale.
md5sum "$A"
sudo md5sum /srv/jeux/sauvegardes/$(basename "$A")

rm -rf "$T"
```

Pour restaurer réellement, serveur arrêté :

```bash
sudo systemctl stop valheim
sudo mv /var/lib/valheim/donnees /var/lib/valheim/donnees.avant-restauration
sudo mkdir -p /var/lib/valheim/donnees
sudo tar xzf /srv/jeux/sauvegardes/valheim-AAAAMMJJ-HHMMSS.tar.gz -C /var/lib/valheim/donnees
sudo chown -R valheim:valheim /var/lib/valheim
sudo systemctl start valheim
```

Ne supprime l'ancien dossier qu'après avoir vérifié en jeu que le monde
restauré est le bon.

---

## Modificateurs de monde et succès Steam, le 2026-09-12

Le groupe a reçu en jeu un message signalant un **objet de triche** — un trophée
de squelette ramassé dans le marais. Panique légitime : est-ce que tous les
succès tombent ? Non. Voici le mécanisme, lu dans `Achievements` et non déduit.

### Ce que le jeu vérifie

```csharp
triche = IsWorldCheated() || joueur.GetInventory().AnyCheatedItem()
```

**Aucune des deux n'est un état permanent.**

`IsWorldCheated()` ne regarde pas les objets : il appelle
`WorldContainsCheatedModifiers(monde)`, qui parcourt les **clés globales de
départ** du monde. Une clé qui ne commence pas par `preset` et qui ne figure pas
dans la liste des valeurs légitimes rend le monde triché. C'est donc
l'équivalent du bandeau « ceci désactivera les succès » de l'écran de création.

`AnyCheatedItem()` regarde l'inventaire du joueur **à cet instant**, avec un
cache d'une seule image. L'objet jeté, le contrôle redevient vert aussitôt.

Le contrôle ne fait qu'une chose : bloquer l'**enregistrement** de nouveaux
succès, par `ShouldSetPlatformStat`. **Rien ne retire un succès déjà acquis** —
`Achievements::ResetAchievement(id)` existe mais n'est appelé que par la
console, jamais par ce chemin.

### Comment un objet se retrouve marqué

`CharacterDrop.m_cheated` : c'est la **créature** qui porte le drapeau, et il se
propage à ce qu'elle laisse tomber — `DropItems(..., bool cheated)` recopie le
drapeau dans chaque `ItemData.m_cheated`. Un trophée ramassé sur une créature
marquée est donc marqué, sans que le joueur ait rien fait.

Et c'est l'**attaquant** qui marque la créature, pas le monde :

```csharp
attaquant = hit.GetAttacker()
joueurTriche =  arme trichée ET qui fait des dégâts, équipée
             || IsDebugFlying || InGodMode || InGhostMode
attaquantDéjàMarqué = ZDO de l'attaquant .cheated

si (joueurTriche || attaquantDéjàMarqué || dégâts > 99999)
   et que s_bypassCheatChecks est faux
alors : ZDO de la VICTIME -> cheated = true
```

**`attaquantDéjàMarqué` est le terme qui explique tout le reste** : une créature
marquée marque celles qu'elle frappe. La contagion ne passe donc pas seulement
par les joueurs, elle circule de mob à mob. Un squelette tout frais peut être
marqué parce qu'il s'est battu contre un greydwarf qui l'était — sans que
personne n'ait triché.

C'est l'objection qu'Alexandre a soulevée le 2026-09-12 — « c'est un mob frais,
je ne comprends pas » — et elle était juste : ma première lecture avait manqué
ce terme, et `InGhostMode` avec.

**La contagion passe par une arme — mais pas seulement. Corrigé le 2026-09-12
au soir : voir plus bas, `TryPlacePiece` et `DoCrafting` propagent aussi, par
les matériaux.** `CheatedDamagingItemEquipped`
vérifie explicitement `GetDamage().GetTotalDamage() > 0` — un trophée, un
minerai, une plante ne peuvent rien marquer. Ils bloquent l'enregistrement des
succès tant qu'ils sont portés, et rien de plus.

Ce qui propage, c'est une arme trichée équipée : chaque créature frappée est
marquée, et ses butins avec. D'où l'importance d'auditer les coffres — et de
faire vider les sacs par moitiés chez qui reçoit le message, le contrôle étant
instantané.

Dans le format de sauvegarde, c'est le **bit 0 du second masque** d'un objet,
le tout dernier octet de son enregistrement. On peut donc auditer un monde
entier sans le jeu.

### Ce qui est bloqué, et pour qui

```csharp
Player.m_localPlayer.GetInventory().AnyCheatedItem()
```

**`m_localPlayer`** : le joueur LOCAL, chez lui. Chacun est jugé sur son propre
sac et sur rien d'autre. Un objet marqué dans l'inventaire d'un joueur ne peut
pas bloquer les succès des autres — il n'existe aucun mécanisme collectif.
C'était la vraie inquiétude du groupe, et la réponse est non.

Et le blocage ne vaut que **pendant** que l'objet est porté : le cache ne dure
qu'une image. L'objet jeté, l'enregistrement des succès reprend a la seconde.

### L'audit, quand la question se repose

```bash
# tous les objets poses dans le monde, avec leur drapeau de triche
# (le decodeur est dans artisan-valheim.py ; voir sa docstring pour le format)
```

Le 2026-09-12 : **0 objet marqué sur 3280** dans les coffres, supports et objets
posés. Le trophée avait déjà été jeté.

On peut aussi auditer les CRÉATURES et les objets du monde, dont le drapeau est
un champ de ZDO repéré par `hash("cheated")` — soit `-153476768`. Chercher cet
entier dans les `.chunk` donne les porteurs ; **l'octet qui suit est la valeur**,
et il faut la lire : le champ existe parfois à `0`. Le 2026-09-12 sur
NordheimV2 : trois occurrences, **une seule à 1**, vers `x=-1385, z=-2712`.

Ce que le ZDO ne garde pas, et qu'aucune analyse ne rendra : **qui** a posé la
marque. On peut dire quoi et où, jamais qui.

Attention à la portée : cet audit ne voit **pas les inventaires personnels**,
qui vivent dans les fichiers de personnage, chez chaque joueur. Si le message
revient chez quelqu'un, qu'il vide son sac progressivement — le contrôle étant
instantané, on trouve le coupable en quelques essais.

### Deux mécanismes séparés, à ne pas confondre

**Erreur commise le 2026-09-12, corrigée le jour même.** J'avais expliqué le
trophée marqué par les modificateurs `resources_more` et `raids_more` posés le
2026-09-09 : la coïncidence des dates était tentante. C'est faux, et la lecture
du code le dit sans ambiguïté.

| | ce qui le déclenche | ce que ça fait | comment ça s'annule |
|---|---|---|---|
| Monde triché | une clé globale de départ hors liste légitime | suspend l'enregistrement des succès | `-resetmodifiers` |
| Objet triché | un attaquant en triche a marqué la créature | suspend les succès tant qu'il est porté ; propage s'il fait des dégâts | jeter l'objet |

Les deux suspendent les succès, par le même `||`, mais ils n'ont **aucun lien de
cause à effet**. Un modificateur de monde ne marque aucune créature.

**Avant d'ajouter un modificateur à un monde où le groupe tient aux succès, il
faut savoir que ça les suspend.** Et les retirer ne suffit pas : `SetKeys`
n'ajoute que des clés, ne retire jamais. Seul `-resetmodifiers` efface.

Pour l'objet triché, l'origine est forcément un joueur : mode dieu, vol de
débogage, `devcommands`, ou une arme déjà marquée héritée de cette occasion.

### La nuit du 2026-09-12 : la contagion datée, et deux portes de plus

Le soir même, la contamination s'est mise à grossir toute seule et la section
ci-dessus s'est révélée incomplète sur deux points. Ce qui suit est mesuré.

**Dater vaut mieux que supposer.** Le balayage des **120 archives**, du 28/08
au 12/09, a donné une réponse nette là où quatre hypothèses successives
s'étaient déjà trompées :

| moment | entités marquées |
|---|---|
| 09/09 → 12/09 **21:00:42** | **0** — trois jours entiers |
| 12/09 **21:32:26** | 2, toutes deux dans le marais |
| 12/09 22:48 | 2 |
| 12/09 **23:20** | **23**, dont 21 pièces de construction |

Une archive coûte 1,4 s à dépouiller en flux, sans rien extraire sur le
disque. Deux minutes pour cent vingt archives : c'est toujours moins cher que
de raisonner à vide. Et ça a écarté d'un coup l'idée que le problème venait de
l'épée fabriquée ce soir-là — le monde était déjà propre une demi-heure avant.

**Deux portes de propagation manquaient**, lues dans l'IL :

```csharp
// Player::TryPlacePiece
cheated = inventaire.ItemCheated(piece.m_resources) || joueur.NoCostCheat()
// puis PlacePiece pose ZDO.cheated = true sur la construction

// InventoryGui::DoCrafting : idem pour l'objet fabriqué
```

**Construire ou fabriquer avec un matériau marqué marque le résultat.** C'est
ce qui a fait passer le monde de 2 à 23 marques en quarante minutes : le
groupe avait rangé le butin contaminé dans des coffres, puis bâti avec. Et
comme `Piece::DropResources` recopie le drapeau, casser un mur marqué rend du
bois marqué. La boucle se referme.

Conséquence pratique : **ranger un objet marqué dans un coffre n'est pas
neutre**. C'est sans effet sur les succès — le contrôle ne regarde que le sac
du joueur — mais le matériau reste disponible pour contaminer la prochaine
construction. J'avais dit « les coffres sont inoffensifs » : c'est faux dès
qu'on y puise.

### Les clés `eventrate` et `resourcerate` suspendaient les succès

Le `.fwl2` du monde contenait, jusqu'au 2026-09-12 19:52:53, deux clés de
départ **non-preset** : `eventrate 60` et `resourcerate 150`. Or :

```csharp
foreach (string cle in world.m_startingGlobalKeys) {
    if (cle.StartsWith("preset")) continue;
    if (GetPossibleGlobalKeyValues().Contains(cle)) continue;
    return true;   // monde triché
}
```

La liste légitime est construite à partir des curseurs de modificateurs du
jeu, dont les valeurs ont la forme `resources_more`. Un `resourcerate 150`
n'en fait pas partie. **Aucun succès ne pouvait donc être enregistré** tant
que ces clés étaient présentes. Le `-resetmodifiers` de 19:53 les a effacées :
le fichier est passé de 1613 à 284 octets.

C'est un effet de bord des réglages de serveur qu'on ne soupçonne pas : ces
deux clés-là ne venaient pas de l'écran de création du monde.

### La restauration, et la surveillance

Le monde a été restauré à 23:21:41 depuis `valheim-20260912-210042.tar.gz`,
dernière archive **prouvée saine** — 0 ZDO marqué, 0 objet marqué, aucune clé
de modificateur. Coût : 2 h 40 de jeu. Après restauration : 557 163 ZDO
rechargés, 0 marque.

`restaure-monde-valheim.sh` fait ce travail avec deux garde-fous appris le
soir même :

- il **audite l'archive avant** de toucher au monde en place, et refuse sans
  `--force` ;
- il exige au moins un `.chunk` et un `.fwl2` dans l'extraction. Le premier
  essai avait utilisé `--strip-components=2` là où il en faut **3** — le `./`
  de tête compte comme un composant. L'audit avait alors répondu « 0 marque »
  sur un dossier vide. Sans ce garde-fou, le monde se faisait écraser par du
  vide, en silence, avec un message rassurant.

Il **déplace** le monde courant au lieu de l'effacer : c'est la seule copie de
ce qui a été joué depuis la dernière archive, et la pièce à conviction.

`triche-valheim.py`, lancé toutes les 15 minutes, compte séparément les ZDO
marqués et les piles d'objets marquées, les enregistre dans `triche_releves`,
et publie sur Discord **dès que le compte monte**. Quinze minutes parce que la
propagation va vite : 2 → 23 en quarante minutes. Une alerte horaire serait
arrivée après la soirée.

### Douze agents, quatre conclusions cassees — la nuit du 2026-09-13

Six pistes lancees en parallele, chacune suivie d'un agent charge de la
**refuter**. Quatre conclusions sur six sont tombees, dont deux des miennes.
Le dispositif a paye : les erreurs trouvees sont exactement du genre qui ne se
voit jamais tout seul.

**1. Mon lecteur d'objets etait aveugle aux objets AU SOL.** Un objet pose
n'a pas l'en-tete d'inventaire (`int32 109` puis `uint16 nombre`) sur lequel
je m'ancrais. `ItemDrop::SaveToZDO` (il.txt 250961) ecrit un simple **octet**
`0x6d` puis l'`ItemData`, dans le champ ZDO `itemData`. Consequence chiffree :
sur le monde de 23:21, je comptais **4** piles marquees, il y en avait **50**.
Un facteur douze, et aucune erreur pour le signaler.

C'est ainsi qu'on a retrouve, dans l'archive de 21:32:26, le
`TrophySkeleton` par lequel le groupe avait decouvert le probleme — marque,
par terre, la ou il avait ete jete.

**2. La table des prefabs vivait dans `/var/tmp`.** Le service a
`PrivateTmp=yes` : il voyait un `/var/tmp` prive et vide, et affichait
`{'-500516295': 1}` au lieu de `AncientSeed`. Une alerte Discord illisible,
sans la moindre erreur. La table est desormais cherchee dans
`/usr/local/share/valheim/`, puis le `StateDirectory`, puis `/var/tmp` en
dernier recours — et son absence est dite sur la sortie d'erreur. `/var/tmp`
est de toute facon purge periodiquement.

**3. « Un chunk reecrit = un joueur present » est faux.** Cinq sauvegardes
depuis le 11/09 ont au moins un chunk sale avec zero joueur connecte. Et dans
chaque chunk reecrit, 100 % des identifiants de connexion des spawners sont
re-estampilles : un diff naif fait donc passer une region parfaitement inerte
pour une region « reveillee ». Sur les trois regions que j'avais annoncees
reveillees le soir du 12/09, **une seule l'etait vraiment**.

Le bon test n'est pas l'horodatage du fichier, c'est le diff des ZDO :
ajouts, suppressions, champs modifies. Sur `1e_24`, 15 641 ZDO, **0 ajout,
0 suppression, aucun champ modifie**.

**4. Le decodage region -> coordonnees est decale de 32 m** :
`[1024·i − 32, 1024·(i+1) − 32]`, et non `[1024·i, 1024·(i+1)]`.

**5. Une preuve circulaire, a ne pas refaire.** « La distribution du dernier
octet est strictement binaire, donc c'est bien un drapeau » ne prouve rien :
`lis_objet` rejette tout lot dont un `masque2` sort de `{0,1}`. C'est le
lecteur qui impose la distribution. Verifie depuis en neutralisant le filtre :
sur le monde vivant, `{0: 11618}` — le filtre ne perd rien ici, mais
l'argument etait sans valeur.

### La liste complete des ecritures du drapeau

Enumeration exhaustive de l'assembly : **22 methodes**, pas une de plus.
Celles qui manquaient a la section precedente :

```
Destructible::Destroy     attaquant est un Joueur && CheatedDamagingItemEquipped()
                          -> abattre un arbre, casser un rocher avec une arme
                             marquee marque ce qu'ils lachent
Ragdoll::Setup/SpawnLoot  recopie depuis le cadavre
ZoneSystem::SpawnLocation false en generation normale ; true seulement depuis
                          TestSpawnLocation, une commande console
Terminal g__spawn         marque TOUJOURS ce qu'elle cree
```

**Sur un objet, la marque est definitive.** Les dix ecritures de
`ItemData::m_cheated` posent `true` ou recopient une valeur ; **aucune ne pose
`false`**. Et `Inventory::AddItem` (il.txt 244402) propage :

```csharp
if (objet_entrant.m_cheated && !s_bypassCheatChecks)
    pile_existante.m_cheated = true;
```

Empiler une unite marquee sur une pile propre contamine la pile. Le conseil
qui circule sur les forums — « fusionner avec des objets propres enleve la
marque » — est donc l'exact inverse de ce que fait le code, et aggrave le
probleme. Le seul moyen de se debarrasser d'un objet marque est de le
detruire.

Detail au passage : a la deserialisation (il.txt 248291), un objet dont
`GetTotalDamage() > 10000` est marque d'office. Seuil different du 99999 de
`ApplyDamage`.

### Un modificateur de monde PEUT marquer — mais pas celui du butin

La question posee etait : « est-ce que ca vient du fait qu'on a augmente puis
diminue le loot ? ». Reponse mesuree : **non**, et les deux chemins sont
disjoints. Le taux s'applique dans `Game::ScaleDrops` pendant la generation
de la liste de butin ; le drapeau est pose plus tard dans
`CharacterDrop::DropItems` a partir du seul ZDO du cadavre.

Mais le « categoriquement non, aucun modificateur ne peut marquer » etait
trop large, et l'agent refuteur a eu raison de le casser :

```
Character::ApplyDamage
  IL_0056  hit.ApplyModifier(Game::m_playerDamageRate)   <- cle « playerdamage »
  ...
  IL_017d  si hit.GetTotalDamage() > 99999  ->  ZDO.cheated = true
```

`trySetScalarKey` divise par 100 et **n'ecrete rien**. Une cle `playerdamage`
extreme franchirait donc le seuil et marquerait la victime. Mesure : ce monde
n'a jamais porte cette cle — seulement `eventrate 60`, `resourcerate 150` et
des presets en `combat_default`. Le chemin existe, il n'etait pas arme.

### Ce que le popup ne prouve pas

Tant que `eventrate 60` et `resourcerate 150` etaient dans le `.fwl2`,
`IsWorldCheated()` etait vrai, et le popup « objet triche ramasse » ne
**pouvait pas** s'afficher : `Inventory` s'en sert pour ETEINDRE l'alerte.
Il n'est redevenu possible qu'apres le `-resetmodifiers` de 19:53 le 12/09.
Un joueur qui dit « on vient d'avoir un message » temoigne donc de la
disponibilite du message, pas forcement de la nouveaute du probleme.

### L'evenement du 2026-09-12, date et localise

Diff des ZDO de `1a_1c` entre 21:00:42 et 21:32:26 : **494 apparitions et
disparitions**, centrees sur `(-1250, -2600)`, a cote du `LocationProxy`
Bonemass mesure a `(-1148.20, 30.10, -3014.62)`.

```
+ 5 SerpentScale     <- un Serpent a ete tue
− 5 Skeleton_Swamps
− 5 Draugr
− 20 Leech
− 4 Greydwarf
```

Les deux premieres entites marquees du monde sortent de ce combat : le
Serpent et un Blob. Le butin marque — 4 `Entrails` et le `TrophySkeleton` —
est au sol au meme endroit.

Le fichier ne dit pas **qui** tenait l'arme, et ne le dira jamais.

### Ce que disent les autres joueurs

Le groupe n'est pas un cas isole. Des fils Steam de septembre 2026 decrivent
le meme symptome sur des **mondes vanilla neufs, sans mod** : du bois coupe,
des pierres, des butins de greydwarfs et de greylings etiquetes « summoned
through cheating means ». La theorie dominante y est celle a laquelle la
lecture du code menait : un joueur amenant un ancien personnage sur un
serveur neuf propage le statut. **Aucune communication d'Iron Gate** dans ces
fils a la date du 2026-09-13.

Deux conseils qui y circulent et que le code dement :

- « fusionner avec des objets propres nettoie » : faux, voir plus haut ;
- « la commande `devopts` reactive les succes » : elle n'existe pas en 1.0.12.
  Le mecanisme reel est une cle de joueur, `bypasscheatchecks = "1"`, posee
  par la commande `yesiuseddevcommandsbutiwantmyachievementsanyway`. Elle
  n'efface rien de deja marque, elle empeche les marquages futurs — et c'est
  un contournement delibere du controle.

Enfin, l'hypothese « pas d'admin, donc pas de console » est plus faible qu'il
n'y parait : `Terminal::TryRunCommand` **relaie au serveur** les commandes
marquees `RemoteCommand` dont la validation locale echoue, et le serveur les
execute des qu'un admin a lance `devcommands`. La commande `spawn`, elle,
exige `ZNet.IsServer()` et reste hors de portee d'un client.

### Comment auditer un sac, et ce que « le monde est propre » ne dit pas

Le 2026-09-13 vers 1 h du matin, Alexandre signale que son epee fait apparaitre
des objets marques partout, y compris a la base, sur des cerfs et des
sangliers — et **apres** la restauration. La surveillance, elle, affiche zero
depuis 23:25. Les deux peuvent etre vrais en meme temps :

**Un butin ramasse ne touche jamais le monde.** La creature est marquee, meurt,
lache son butin, le joueur le ramasse dans la seconde. Ni le ZDO de la
creature (detruit) ni les objets (jamais poses) n'atteignent une sauvegarde.
Un monde a zero marque ne prouve donc **rien** sur ce que les joueurs portent.

La seule facon d'auditer un sac est de le faire vider dans un coffre, puis
d'attendre la sauvegarde suivante — le jeu ecrit toutes les dix minutes. Lire
avant, c'est lire l'etat d'avant le depot et conclure a tort qu'il n'y a rien.

Resultat de cet audit, en deux temps :

```
equipement complet (11 pieces, epee iron, maces, boucliers, armure, cape) : PROPRE
butin entier rapporte du marais depuis le reset
  (306 Entrails, 315 BoneFragments, 147 WitheredBone, 85 Bloodbag,
   72 DeerHide, 59 Ooze, 13 TrophySkeleton, 16 TrophyDraugr, ...) : PROPRE
```

**Le drapeau ne se transmet pas par le personnage.** Aucune methode
`Player::Save` ni `PlayerProfile` n'ecrit `cheated` : seuls les objets de
l'inventaire le portent. Le drapeau qu'un joueur recoit sur son ZDO de
personnage — `ApplyDamage` marque la victime, joueur compris — est **volatil**.
Le ZDO d'un joueur est non persistant : le journal du serveur le dit a chaque
deconnexion (« Destroying abandoned non persistent zdo »). Une reconnexion
repart donc d'un personnage propre, et le redemarrage du serveur pendant une
restauration remet tout le monde a zero.

Consequence : il n'existe aucun etat « joueur contamine » durable. Ce qui
voyage d'une session a l'autre, ce sont seulement les OBJETS du sac.

**Pourquoi le message semble se repeter.** Le popup se declenche sur un
CHANGEMENT d'etat de l'inventaire, pas sur chaque objet. Porter un objet
marque et en ramasser d'autres donne l'impression que tout ce qu'on touche est
contamine, alors que le message parle de l'etat du sac.

**Conclusion du 2026-09-13 01:25.** Trois mesures independantes concordent :
equipement propre, sac propre, monde a zero marque en continu de 23:25 a 01:25.
La contamination n'a pas survecu a la restauration ; les symptomes decrits
dataient d'avant. Il restait un seul objet marque dans tout le monde, la graine
ancienne d'un joueur, dans un coffre.

Ce qui a marque le Serpent a 21h20 ne sera jamais su : le fichier ne garde pas
qui pose la marque. Ca n'a plus de portee pratique — la source a disparu avec
la restauration, et la surveillance signale toute reapparition en un quart
d'heure, avec le nom de l'objet et sa region.

**Ce qu'aucun de ces outils ne voit : les sacs des joueurs.** Ils vivent dans
les fichiers de personnage, chez chacun. Une restauration du monde ne les
nettoie pas, et l'audit ne les lit pas. C'est la seule façon dont la
contamination peut revenir après une restauration — et c'est l'hypothèse
restante sur l'origine : un personnage utilisé sur un autre monde, dont les
objets gardent leur drapeau. Verifie le 2026-09-13 : quatre comptes Steam
seulement se sont jamais connectes, et aucun monde anterieur de cette machine
(Midgard, NordheimV1 et leurs sauvegardes) ne porte la moindre marque — le
hash `cheated` n'y apparait meme pas. L'origine est donc exterieure a cette
machine.

### L'origine est un poste client — audit du 2026-09-13

Le marquage vient de **l'attaquant**, par l'objet qu'il a equipe. Le serveur
n'en est jamais la source : il enregistre ce que le client lui envoie. Chercher
plus loin cote serveur ne peut donc rien donner tant que les postes ne sont pas
passes au meme test.

**Premier poste audite, celui d'Alexandre.** Un chargeur BepInEx y est en place
depuis le 2025-08-28, et il est toujours actif :

```
.doorstop_version      4.4.0
doorstop_config.ini    enabled = true
                       target_assembly = BepInEx\core\BepInEx.Preloader.dll
winhttp.dll            26 112 o
doorstop_libs\         libdoorstop_x64.so / .dylib
start_game_bepinex.sh  start_server_bepinex.sh
changelog.txt          « 3 commits since v5.4.23.2 »
```

Le dossier `BepInEx\` lui-meme a ete supprime, et `valheim_Data\Managed` ne
contient aucun assembly etranger — ni `0Harmony.dll`, ni `BepInEx.*.dll`. Le
chargeur est donc **ampute** : `winhttp.dll` est charge a chaque lancement,
doorstop cherche le preloader, ne le trouve pas, et echoue en silence.

Ce que ca n'etablit pas : que ce poste est la cause du marquage. Un preloader
dont la cible a disparu n'injecte rien. Ce que ca etablit : ce poste a heberge
BepInEx, son etat actuel est un reliquat et non une installation propre, et il
suffit d'y reposer un dossier `BepInEx\` pour que tout se recharge. « Vanilla »
ne s'y verifie pas par l'absence de mods, seulement par l'absence de chargeur.

**Empreinte du client**, a comparer sur les autres postes :

```
buildid (appmanifest_892970.acf)  25253764
assembly_valheim.dll              2 568 192 o
                                  sha256 27a766a8d23a7bd8...
                                  2026-09-11 15:19:42
```

Une empreinte differente n'est pas suspecte si le buildid differe — Steam met a
jour. C'est un binaire modifie **a buildid identique** qui serait le signal.

### La commande de contournement, verifiee

Ce qui etait annonce plus haut sur la foi des forums est desormais lu dans le
binaire du client. Desassemblage IL de l'enregistrement des commandes console :

```
ldstr 'achievements'
ldstr 'yesiuseddevcommandsbutiwantmyachievementsanyway'
ldstr "[1 = true/ 0 = false] Normally cheated items / pieces don't trigger
       achievements. Turn this on to disable cheat checks."
ldstr 'getstat'
```

Syntaxe `yesiuseddevcommandsbutiwantmyachievementsanyway 1`, la valeur est
persistee sous la cle joueur `bypasscheatchecks`, le retour console est
`Set cheat bypass to true/false`. Le nom qui circule est donc exact,
litteralement. Elle n'efface rien de deja marque : elle desactive les controles
futurs.

**Un piege de methode, qui a produit un faux negatif dans ce dossier.** Lire les
chaines d'un assembly .NET en decodant le fichier entier en UTF-16 depuis
l'octet 0 — `[Text.Encoding]::Unicode.GetString()`, ou tout equivalent — ne voit
que les chaines a offset **pair**. Celles a offset impair disparaissent sans le
moindre avertissement. Il faut chercher la sequence d'octets UTF-16 LE dans les
octets bruts, aux deux alignements. Et un temoin ne vaut que s'il existe aux
deux : `devcommands` existe en double cote client, un pair un impair, donc il
ressort present quelle que soit la methode et ne valide rien.

La copie serveur de `assembly_valheim.dll`, elle, ne contient reellement pas la
chaine — verifie aux deux alignements sur les octets bruts. Elle est simplement
anterieure au patch : 2 557 952 o, sha256 `6ebcb5ce3742b3f6...`, datee du
2026-09-10, contre 2 568 192 o cote client le 11/09. Dix kilo-octets d'ecart, et
`devcommands` en un seul exemplaire au lieu de deux.

**Ce qui reste a faire :** les trois autres postes n'ont pas ete audites.
Chargeur doorstop et empreinte du binaire, le meme test pour chacun. Tant que ce
n'est pas fait, le combat du 2026-09-12 a 21h00 reste non attribue — et corriger
le seul poste connu expose a voir le marquage revenir au combat suivant, puis a
repartir sur la piste « bug d'Iron Gate ».

---

## Reconstruire depuis rien — la machine est perdue

Le cas que les archives horaires ne couvrent pas : la machine ne redémarre
plus, ou n'existe plus. La copie hors site est alors la seule qui reste, et
elle ne contient **que le monde**. Le reste se reconstitue, et c'est l'ordre
qui compte.

### Ce qui n'est pas sauvegardé, et qu'il faut savoir d'avance

| Ce qui manquera | Où ça vivait | Comment le retrouver |
|---|---|---|
| Nom du serveur, nom du monde, **mot de passe**, modificateurs | `/etc/valheim.env`, en `0600 root` | **À retaper à la main.** Hors dépôt — il contient le mot de passe — et hors archive, qui ne couvre que `/var/lib/valheim/donnees`. Voir l'étape 4. |
| Jeton Google Drive de `rclone` | `/etc/rclone/rclone.conf`, sur la machine perdue | Ne se restaure pas : on se **réauthentifie**. Le Drive appartient au compte Google, pas à la machine. |
| Le binaire du serveur, 2 Gio | `/srv/jeux/valheim/serveur` | Réinstallé par SteamCMD, étape 3. Ce n'est pas de la donnée, on ne l'archive pas. |
| Programmes, unités systemd, page Cockpit | `/usr/local/bin`, `/etc/systemd/system`, `/usr/share/cockpit/valheim` | Le dépôt. C'est sa raison d'être. |

**Le mot de passe est le seul point vraiment fragile** : il ne vit que dans
`/etc/valheim.env`, sur la machine, et nulle part ailleurs — c'est volontaire,
un mot de passe n'a pas sa place dans un dépôt, et il n'est donc pas écrit dans
ce document non plus. Sans lui, le monde se restaure très bien mais personne ne
s'y connecte tant qu'on n'en a pas choisi un nouveau, ce qui oblige à le redire
à tout le groupe. Le garder en double dans un gestionnaire de mots de passe,
hors de cette machine, évite ce détour.

### L'ordre

**1. Le dépôt d'abord.** Tout ce qui suit s'y trouve.

```bash
git clone https://github.com/stefanialex/stefanialex.git ~/stefanialex
cd ~/stefanialex/serveur
```

**2. Les étapes 1 à 5 de ce document**, dans l'ordre : dépendances, compte
système `valheim`, installation par SteamCMD, `/etc/valheim.env`, unité
systemd. L'unité, elle, ne se retape pas — elle est dans le dépôt :

```bash
sudo install -o root -g root -m 644 valheim-serveur/valheim.service /etc/systemd/system/
sudo systemctl daemon-reload
```

**Ne démarre pas encore le serveur.** Lancé sur un nom de monde qui n'existe
pas, il en génère un neuf avec une seed au hasard — et le monde restauré à
l'étape suivante se retrouverait à côté, inutilisé, ce qui se voit mal.

**3. Réauthentifier `rclone`.** C'est l'étape que rien ne remplace.

```bash
sudo apt install -y rclone
rclone config                    # remote de type « drive », nommé gdrive
sudo mkdir -p /etc/rclone
sudo cp ~/.config/rclone/rclone.conf /etc/rclone/rclone.conf
sudo chmod 600 /etc/rclone/rclone.conf
```

Le remote **doit** s'appeler `gdrive` et le fichier atterrir dans
`/etc/rclone/rclone.conf` : c'est ce que `sauvegarde-valheim-hors-site.sh`
attend, en dur.

**4. Rapatrier l'archive, et la vérifier avant d'y toucher.**

```bash
rclone --config /etc/rclone/rclone.conf ls gdrive:sauvegardes-valheim/
rclone --config /etc/rclone/rclone.conf copy \
  gdrive:sauvegardes-valheim/valheim-AAAAMMJJ-HHMMSS.tar.gz /tmp/

gzip -t /tmp/valheim-AAAAMMJJ-HHMMSS.tar.gz
tar tzf /tmp/valheim-AAAAMMJJ-HHMMSS.tar.gz | grep worlds_local/
```

La dernière ligne doit nommer ton monde. Depuis la 1.0 c'est un **dossier** —
`./worlds_local/NordheimV2/_main.12.db2` et son `.fwl2` — et non plus deux
fichiers. Une archive d'avant le 2026-09-09 contient l'ancienne forme,
`./worlds_local/Midgard.db` : le serveur 1.0 la lit et la convertit, mais
vérifie alors que la conversion a bien eu lieu avant de laisser le groupe
jouer dessus.

**5. Restaurer le monde.** L'archive contient le **contenu** de `donnees`, pas
le dossier lui-même — `tar` l'a créée avec `-C "$SOURCE" .`. Elle se déplie
donc *dans* un `donnees` vide, pas un niveau au-dessus.

```bash
sudo mkdir -p /var/lib/valheim/donnees
sudo tar xzf /tmp/valheim-AAAAMMJJ-HHMMSS.tar.gz -C /var/lib/valheim/donnees
sudo chown -R valheim:valheim /var/lib/valheim
sudo chmod 750 /var/lib/valheim
```

**6. Réinstaller les programmes et les unités**, depuis le dépôt. Deux lots :
les dix-huit programmes ouverts en `755`, et les cinq qui touchent au monde ou
aux sauvegardes en `750` — eux ne doivent rester lisibles que par root.

```bash
sudo install -o root -g root -m 755 \
  monde-valheim/monde-valheim.py \
  valheim-artisan/artisan-valheim.py \
  valheim-artisan/noms-prefabs-valheim.py \
  valheim-cles/cles-monde-valheim.py \
  valheim-discord/bilan-discord-valheim.py \
  valheim-discord/soiree-discord-valheim.py \
  valheim-discord/pret-discord-valheim.py \
  valheim-discord/file-claude-valheim.sh \
  valheim-discord/lit-discord-valheim.py \
  valheim-discord/notifie-discord-valheim.py \
  valheim-discord/salon-valheim.py \
  valheim-kpi/chantier-valheim.py \
  valheim-meteo/meteo-valheim.py \
  valheim-meteo/oracle-valheim.py \
  valheim-monde/lecteur-monde-valheim.py \
  valheim-stats/collecte-valheim.py \
  valheim-stats/stats-valheim.py \
  valheim-steam/succes-steam-valheim.py \
  /usr/local/bin/

sudo install -o root -g root -m 750 \
  jour-j/jour-j-valheim.sh \
  monde-valheim/bascule-monde-valheim.sh \
  monde-valheim/nouveau-monde-valheim.sh \
  valheim-sauvegarde/sauvegarde-valheim.sh \
  valheim-sauvegarde/sauvegarde-valheim-hors-site.sh \
  /usr/local/bin/

sudo install -o root -g root -m 644 $(find . -name '*.service' -o -name '*.timer') \
  /etc/systemd/system/
sudo systemctl daemon-reload
```

La page Cockpit, si tu la veux :

```bash
sudo mkdir -p /usr/share/cockpit/valheim
sudo install -o root -g root -m 644 cockpit-valheim/* /usr/share/cockpit/valheim/
```

Le contrôle qui dit que le lot est complet — il doit ne rien afficher :

```bash
for f in $(ls /usr/local/bin/ | grep -iE 'valheim|oracle|salon|chantier'); do
    src=$(find . -name "$f" -not -path '*/__pycache__/*' | head -1)
    [ -n "$src" ] && sudo cmp -s "$src" "/usr/local/bin/$f" || echo "manque ou differe : $f"
done
```

Aucune unité ne porte de secret : tout passe par `/etc/valheim.env` et
`/etc/valheim-discord.conf`, à recréer à la main.

**7. Armer les minuteries et démarrer.** Trois services et treize minuteries,
c'est la liste exacte de ce qui était armé sur la machine :

```bash
sudo systemctl enable --now valheim collecte-valheim profil-performance

# L'annonce de disponibilite n'a pas de minuterie : elle est liee au serveur et
# part avec lui. Sans « enable » elle ne serait jamais accrochee a valheim.service.
sudo systemctl enable pret-discord-valheim.service

sudo systemctl enable --now \
  sauvegarde-valheim.timer sauvegarde-valheim-hors-site.timer \
  bilan-discord-valheim.timer notifie-discord-valheim.timer \
  lit-discord-valheim.timer file-claude-valheim.timer \
  cles-monde-valheim.timer succes-steam-valheim.timer \
  oracle-valheim.timer soiree-discord-valheim.timer \
  redemarrage-valheim.timer redemarrage-machine.timer
```

`guette-valheim-1.0.timer` manque à cette liste **exprès** : elle guettait la
sortie de la 1.0, arrivée le 2026-09-09 à 15 h. Elle est encore armée sur la
machine par simple inertie ; sur une machine neuve, elle n'a plus d'objet.

Et si tu comptes, tu comptes bien : douze minuteries armées ici, treize sur
la machine, la treizième étant celle-là.

**8. Vérifier, dans cet ordre.**

```bash
systemctl status valheim                       # actif, pas de redemarrage en boucle
journalctl -u valheim -n 30 | grep -i "Load world"
stats-valheim.py                               # le monde, le jour, les joueurs connus
sudo systemctl start sauvegarde-valheim        # une archive neuve, verifiee
```

La ligne `Load world:` doit nommer **ton** monde. Si elle en nomme un autre, le
serveur en a généré un neuf : arrête-le, vérifie `NOM_MONDE` dans
`/etc/valheim.env`, et compare-le au nom du dossier sous `worlds_local/`.

La table des noms de prefabs ne se restaure pas non plus, elle se refabrique --
elle vit dans `/var/tmp`, exprès, parce qu'elle dépend de la version du jeu :

```bash
noms-prefabs-valheim.py          # ~50 s, deplie 1,7 Go de bundles
```

Sans elle, le relevé des artisans affiche des hashes au lieu des noms d'objets.
À relancer après chaque mise à jour de Valheim.

Enfin, la base de statistiques ne se restaure pas et n'a pas à l'être : le
collecteur relit tout le journal `systemd` à chaque démarrage et se
reconstitue seul. Ce qui est perdu, c'est ce que le journal ne garde plus —
l'historique ancien, pas l'état courant.

---

## Performances

Mesuré sur cette machine — i5-7500 quatre cœurs, 16 Gio — avec quelques
joueurs : **1,1 Gio de mémoire et 10 à 35 % d'un cœur**, charge moyenne sous 1.
À cette échelle rien n'est saturé, et la plupart des conseils qu'on trouve en
ligne visent des serveurs qui le sont. Ce qui suit corrige deux pièges réels
plutôt que d'optimiser dans le vide.

### Le piège de l'ordonnanceur Pop!_OS

`com.system76.Scheduler` est actif par défaut sur Pop!_OS, et sa configuration
classe tout ce qui vit dans `/system.slice` ainsi :

```
system-services nice=12 io="idle" {
    include cgroup="/system.slice/*"
}
```

Le serveur Valheim, étant un service systemd, hérite donc de `nice=12` et
surtout d'**entrées-sorties en classe `idle`** : ses écritures de sauvegarde
passent après tout le reste de la machine. C'est le point le plus gênant, et il
est invisible tant qu'on ne va pas le chercher.

Un `Nice=` dans l'unité systemd **ne suffit pas** : l'ordonnanceur repasse
toutes les 60 secondes et le réécrit. Une assignation par nom de processus ne
suffit pas non plus — la règle par cgroup l'emporte. Il faut exclure le service
de la règle, en repartant d'une copie complète de la configuration par défaut :

```bash
sudo mkdir -p /etc/system76-scheduler
sudo cp /usr/share/system76-scheduler/config.kdl /etc/system76-scheduler/config.kdl
# Dans le bloc system-services, ajouter :
#     exclude cgroup="/system.slice/valheim.service"

sudo mkdir -p /etc/system76-scheduler/process-scheduler
sudo tee /etc/system76-scheduler/process-scheduler/valheim.kdl >/dev/null <<'FIN'
assignments {
	games {
		include name="valheim_server*"
	}
}
FIN

sudo systemctl restart com.system76.Scheduler
```

**Vérification** — le profil `games` donne `nice=-5` et `io=(best-effort)0` :

```bash
P=$(pgrep -f valheim_server.x86_64 | head -1)
awk '{print $19}' /proc/$P/stat      # doit afficher -5, pas 12
sudo ionice -p $P                    # doit afficher best-effort, priorité 0
```

Dans l'unité systemd, `CPUWeight=500` complète le dispositif : il agit au
niveau du cgroup, hors de portée de l'ordonnanceur comme de l'application.
Il ne joue qu'en cas de contention, ce qui n'arrive pas à cette échelle — c'est
une assurance, pas un gain mesurable aujourd'hui.

### Le monde sur le SSD

`/srv/jeux` est un disque mécanique. Les sauvegardes automatiques d'un monde
qui y réside provoquent des micro-blocages perceptibles en jeu. Le monde tient
dans quelques mégaoctets : il vit donc sur le SSD, en `/var/lib/valheim`, et
seules les **archives** vont sur les disques mécaniques — où leur lenteur n'a
aucune importance.

Le déplacement se fait serveur arrêté, et se vérifie avant de basculer :

```bash
sudo systemctl stop valheim
sudo find /srv/jeux/valheim/donnees -type f -exec md5sum {} \; | sort > /tmp/avant
sudo cp -a /srv/jeux/valheim/donnees /var/lib/valheim/donnees
sudo chown -R valheim:valheim /var/lib/valheim
# comparer /tmp/avant aux empreintes de la copie AVANT de modifier l'unite
```

Puis `-savedir`, `ReadWritePaths` et le `SOURCE` du script de sauvegarde. Ce
dernier est le piège : oublié, on archive indéfiniment une copie figée.

### Fréquence processeur

Pop!_OS démarre en profil *Balanced*, gouverneur `powersave`, soit environ
2400 MHz sur les 3800 disponibles. Le gain du profil `performance` n'est pas la
vitesse brute — avec `intel_pstate`, `powersave` monte aussi en charge — mais la
suppression du délai de montée en régime, qui se traduit par des à-coups.

`system76-power` ne mémorise pas le profil : sans unité dédiée, la machine
repart en *Balanced* à chaque redémarrage.

```bash
sudo tee /etc/systemd/system/profil-performance.service >/dev/null <<'FIN'
[Unit]
Description=Applique le profil processeur « performance » au demarrage
After=com.system76.PowerDaemon.service
Wants=com.system76.PowerDaemon.service

[Service]
Type=oneshot
ExecStart=/usr/bin/system76-power profile performance
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
FIN
sudo systemctl enable --now profil-performance.service
```

### Redémarrage hebdomadaire

Valheim accumule de la mémoire au fil des jours ; les hébergeurs s'accordent à
dire que le redémarrage régulier est le remède le plus efficace. Une minuterie
le lundi à 5 h, précédée d'une sauvegarde, ne dérange personne.

### Ce qu'on n'a pas fait : le plafond de 60 ko/s

Valheim bride ses envois à environ 60 ko/s par joueur, ce qui est la cause
n°1 de désynchronisation à plusieurs. Aucune ligne, si rapide soit-elle, n'y
change quoi que ce soit : le plafond est interne au jeu.

Le contourner exige un mod — BepInEx plus *BetterNetworking* — **installé sur le
serveur et sur chaque client**, à remettre à jour à chaque version du jeu. À
garder sous le coude si de la désynchronisation apparaît réellement à plusieurs.
Pas à faire par précaution.

### Ce qui pèse dans le monde — recensement du 2026-09-03

Le monde comptait **232 292 ZDOs** ce jour-là, pour 11 Mo de `Midgard.db`. La
répartition, mesurée et non supposée :

| Ce que c'est | Nombre | Part |
|---|---|---|
| Arbres et buissons debout | 105 991 | 46 % |
| Rochers et filons | 45 612 | 20 % |
| Cueillettes (pierres, branches, pissenlits…) | 39 287 | 17 % |
| Construction | ~12 135 | 5 % |
| Contrôleurs de zone (`_ZoneCtrl`) | 2 377 | 1 % |
| Objets au sol | 2 670 | 1,1 % |
| Générateurs de monstres | 1 152 | 0,5 % |
| Coffres (dont 135 de crypte) | 411 | 0,2 % |
| Troncs et souches abattus | 237 | 0,1 % |

**Le seul chiffre à retenir : 85 ZDOs par zone explorée.** 2 377 zones générées
× 85 ≈ 200 000, soit 86 % du monde. Autrement dit le poids du monde suit
l'**exploration**, pas la construction ni le désordre : 83 % de ces ZDOs sont
du décor naturel intact, que personne ne doit supprimer. Six donjons générés
en seize minutes ont ajouté 4 670 ZDOs le soir du recensement — les cryptes
sont le deuxième facteur.

Conséquence pratique : quand le serveur paraîtra poussif, ne cherchez pas des
objets à nettoyer. Un monde à 230 000 ZDOs tient sans effort (4 % de charge
processeur mesurés avec trois joueurs connectés).

#### Refaire le recensement

Le `.db` de la version 37 ne se parcourt pas en champ à champ sans se tromper.
La méthode fiable est de compter les empreintes de prefabs : Valheim stocke
chaque objet sous l'entier 32 bits de `GetStableHashCode()` de son nom, et sur
11 Mo la probabilité qu'une empreinte donnée apparaisse par hasard est de
0,003 — aucun faux positif. **Travailler sur une copie extraite d'une archive
de sauvegarde, jamais sur le monde en service.**

```python
import struct
def hs(s):                                    # GetStableHashCode() de C#
    h1 = h2 = 5381; i = 0
    while i < len(s):
        h1 = (((h1 << 5) + h1) & 0xFFFFFFFF) ^ ord(s[i])
        if i == len(s) - 1: break
        h2 = (((h2 << 5) + h2) & 0xFFFFFFFF) ^ ord(s[i+1])
        i += 2
    return (h1 + h2 * 1566083941) & 0xFFFFFFFF

b = open("Midgard.db", "rb").read()
print(struct.unpack_from("<i", b, 24)[0], "ZDOs")        # le compte est a l'offset 24
for nom in ("Beech1", "Rock_4", "Pickable_Stone", "wood_floor", "_ZoneCtrl"):
    print(b.count(struct.pack("<I", hs(nom))), nom)
```

Les noms de prefabs ne sont **pas** tous dans `resources.assets` du serveur :
arbres, rochers et végétation en sont absents, il faut les écrire à la main.
Les compteurs de *champs* sont plus parlants que les noms pour certaines
catégories : `support` donne le bâti (12 135), `stack` et `quality` donnent les
objets au sol et se valident l'un l'autre (2 670 chacun), `picked` les
cueillettes déjà ramassées.

### Les objets au sol : le jeu s'en occupe déjà

Valheim détruit tout objet posé au sol au bout de **3 600 secondes**, sauf dans
le rayon d'une « base » — établi, feu de camp, lit. C'est du comportement de
base, sans mod.

Donc ce qui reste au sol est, par construction, **dans vos bases** : là où le
jeu refuse de supprimer pour ne pas jeter ce qu'on y a déposé exprès. Un mod de
nettoyage ne trie pas, il jette ça. Pour 1,1 % de la charge.

Les mods vérifiés le 2026-09-03, pour ne pas refaire le tour :

- **DropCleaner** — annoncé côté client, chaque joueur doit l'installer.
- **WorldCleaner** — l'auteur écrit lui-même « encore en développement, à
  utiliser à vos risques », décline toute responsabilité en cas de corruption
  de monde, et n'a aucune protection des bases.
- **TrashCleanup** — le seul honnête : `trashscan` compte avant, `trashclean`
  supprime dans un rayon de 100 m. Manuel et sous contrôle, mais exige BepInEx
  sur le serveur, donc un redémarrage et une remise à jour à chaque patch.
- **ValheimPlus** — permet de régler le délai des 3 600 s, mais touche à tout
  le reste du jeu.

Décision : **aucun mod installé.** Dix minutes de ramassage en jeu font le même
travail sans risque.

### Diagnostiquer un lag : l'ordre qui marche

Établi le 2026-09-03 sur un cas réel — monstres qui se téléportent et loot qui
refuse de se ramasser.

**La clé est mécanique :** dans Valheim, un monstre comme un objet au sol est un
ZDO dont la **propriété appartient à un client**, pas au serveur. Ramasser exige
un transfert de propriété. Si le détenteur est un client à la traîne, la demande
reste sans réponse et l'objet « refuse » d'être pris ; l'IA des monstres qu'il
possède saute d'une position à l'autre. **Un seul joueur mal connecté dégrade la
partie de tout le monde**, et rien côté serveur ne le montre.

L'ordre de dépouillement, du moins coûteux au plus coûteux :

```bash
# 1. La machine est-elle en cause ? Trois chiffres suffisent.
cat /proc/pressure/{cpu,io,memory}     # « some avg60 » proche de 0 = innocente
ps -o pid,ni,pcpu -p $(pgrep -f valheim_server.x86_64)
sudo ionice -p $(pgrep -f valheim_server.x86_64)   # doit rester best-effort 0

# 2. Le lien local ? Erreurs et file d'attente.
ip -s link show enp0s31f6              # errors/dropped doivent rester negligeables
tc qdisc show dev enp0s31f6            # fq_codel attendu

# 3. Chaque joueur, un par un. C'est ici que ca se joue.
tailscale status --json                # « CurAddr » vide = relais DERP, mauvais signe
for ip in $(tailscale status | awk '/active|direct/ {print $1}'); do
  echo -n "$ip : "; tailscale ping -c 1 --timeout 3s $ip | grep -o 'in .*'
done
```

Le verdict est venu de vingt sondes rapprochées vers chaque joueur : **médiane
752 ms, pointe à 1 626 ms, gigue 324 ms, et 0 % de perte** chez l'un, contre
**22 ms très stables** chez l'autre, au même instant et par le même chemin
direct. Perte nulle avec une latence énorme et erratique = **file d'attente
saturée chez le joueur** (bufferbloat), pas un problème de serveur. Le débit le
confirmait : le serveur n'arrivait plus à lui envoyer que 2 à 3 ko/s, contre 31
à 51 ko/s aux autres.

Le test qui tranche sans rien redémarrer : **que le joueur suspect quitte cinq
minutes.** Le serveur réattribue la propriété de ses ZDOs ; si les symptômes
disparaissent, c'est réglé. Côté joueur, dans l'ordre : câble plutôt que wifi,
chercher qui sature sa ligne en émission, redémarrer sa box.

**Ne pas se faire piéger par le journal.** Les lignes `Connections 4` du journal
Valheim **ne comptent pas les joueurs** : elles appartiennent au générateur de
donjons, où « connections » désigne les liaisons entre salles. Elles arrivent
entourées de `Available rooms:18`, `placed 10 doors`, `Placed 26 rooms`. Le
compte réel des joueurs est dans les lignes `Connections N ZDOS:… sent:… recv:…`
(une toutes les dix minutes), ou en comptant les `Got character ZDOID from` sans
`Closing socket` correspondant.

---

## Après une coupure de courant

Trois couches, et la réponse diffère à chaque étage.

| Couche | Reprend seule ? |
|---|---|
| Le processus Valheim, s'il plante | **Oui** — `Restart=on-failure`, `RestartSec=10s` |
| Les services, au démarrage de la machine | **Oui** — tout est `enabled`, et les minuteries ont `Persistent=true` |
| La machine elle-même, au retour du courant | **Oui depuis le 2026-08-28** — réglage BIOS fait |

Le dernier point ne se règle pas depuis Linux, et ne se relit pas non plus : le
réglage a été fait à la main dans le BIOS de la carte MSI B250M MORTAR le
2026-08-28. L'emplacement, pour le jour où il faudra le refaire — remise à zéro
du BIOS, changement de la pile de la carte mère :

> `Suppr` au démarrage → **Settings → Advanced → Power Management Setup →
> Restore after AC Power Loss** → **Power On**. **ErP Ready**, dans le même
> menu, doit rester désactivé : il coupe l'alimentation de veille et empêche le
> rallumage.

Si le réglage se perd, une coupure laisse la machine éteinte jusqu'à ce que
quelqu'un appuie sur le bouton — et aucune commande Linux ne le signale.

---

## Exploitation courante

```bash
sudo systemctl start valheim
sudo systemctl stop valheim          # laisse jusqu'à 120 s pour sauvegarder
sudo systemctl restart valheim
sudo journalctl -u valheim -f        # journal en direct
```

Mettre le serveur à jour après un patch du jeu :

```bash
sudo systemctl stop valheim
sudo -u valheim /usr/games/steamcmd \
  +force_install_dir /srv/jeux/valheim/serveur \
  +login anonymous +app_update 896660 validate +quit
sudo systemctl start valheim
```

Restaurer un monde :

```bash
sudo systemctl stop valheim
sudo mv /var/lib/valheim/donnees /var/lib/valheim/donnees.avant-restauration
sudo mkdir -p /var/lib/valheim/donnees
sudo tar xzf /srv/jeux/sauvegardes/valheim-AAAAMMJJ-HHMMSS.tar.gz \
     -C /var/lib/valheim/donnees
sudo chown -R valheim:valheim /var/lib/valheim
sudo systemctl start valheim
```

---

## Si ça ne démarre pas

```bash
sudo journalctl -u valheim -n 50
```

Les deux causes les plus fréquentes, de loin :

| Symptôme | Cause |
|---|---|
| Le serveur s'arrête aussitôt, sans erreur nette | `SteamAppId=892970` absent ou mal orthographié |
| Le serveur démarre puis quitte | Mot de passe de moins de 5 caractères, ou contenu dans le nom du serveur |

Ensuite, dans l'ordre :

- `error while loading shared libraries` → `LD_LIBRARY_PATH` incorrect, vérifier
  que `/srv/jeux/valheim/serveur/linux64` existe ;
- permission refusée sur le dossier de sauvegarde → `ReadWritePaths` de l'unité
  ne couvre pas le chemin de `-savedir` ;
- personne n'arrive à se connecter → vérifier `sudo ufw status`, puis que le
  client utilise bien **UDP 2456** et non un autre port.

### Côté Tailscale

| Symptôme | Cause probable |
|---|---|
| Le serveur a disparu du réseau après des mois | Expiration de la clé — la désactiver dans la console (étape 6) |
| Un joueur ne voit pas la machine | Partage non accepté, ou connecté avec un autre compte que celui de l'invitation |
| Ça se connecte mais ça rame | Connexion passée par un relais : `tailscale ping 100.76.246.124` indique `via DERP` au lieu de `direct` |
| `Logged out` après un redémarrage | `sudo systemctl enable --now tailscaled` |

Diagnostic général :

```bash
sudo tailscale status          # qui est joignable, et par quel chemin
sudo tailscale netcheck        # qualité de la traversée de NAT
```

---

## Cohabitation avec le serveur IA

> **Périmé depuis le 28 août 2026.** La pile IA a été désinstallée de cette
> machine (voir [`desinstaller-ia.md`](desinstaller-ia.md)) : Valheim y est
> désormais seul et dispose des 16 Gio. Section conservée au cas où l'IA serait
> réinstallée.

Valheim occupe environ 3 Gio. Un modèle de langage en occupe 5 à 16 selon sa
taille. Sur une machine de 16 Gio, les deux tiennent avec un modèle 7–8B, mais
sans marge.

Pour libérer la mémoire avant une session de jeu :

```bash
sudo systemctl stop ollama
```

Voir [`exploitation.md`](exploitation.md) pour plafonner la mémoire de chaque
service plutôt que d'alterner à la main.
