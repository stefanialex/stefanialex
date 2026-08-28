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
FIN
sudo chmod 600 /etc/valheim.env
sudo nano /etc/valheim.env
```

Mets un vrai mot de passe dans `nano`, puis `Ctrl+O`, `Entrée`, `Ctrl+X`.

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
tar czf "$PRIMAIRE/$NOM.partiel" -C "$SOURCE" .

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
tar tzf "$A" | grep Midgard                   # contient-elle le monde ?

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
