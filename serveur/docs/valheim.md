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
sudo mkdir -p /srv/jeux/valheim/serveur /srv/jeux/valheim/donnees
sudo chown -R valheim:valheim /srv/jeux/valheim
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
Wants=network-online.target

[Service]
Type=simple
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
  -savedir /srv/jeux/valheim/donnees \
  -public 0 \
  -saveinterval 1800 \
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
ReadWritePaths=/srv/jeux/valheim

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
| `-savedir` | Chemin de sauvegarde explicite, au lieu de `~/.config/unity3d/…` — prévisible, et compatible avec `ProtectHome=true` |
| `-saveinterval 1800` | Sauvegarde automatique toutes les 30 minutes |
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
sudo ls -l /srv/jeux/valheim/donnees/worlds_local/
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

Valheim fait ses propres sauvegardes tournantes, mais **dans le même dossier** :
une panne de disque emporte tout. Une archive quotidienne à part :

```bash
sudo mkdir -p /srv/jeux/sauvegardes

sudo tee /etc/systemd/system/sauvegarde-valheim.service >/dev/null <<'FIN'
[Unit]
Description=Sauvegarde du monde Valheim

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'tar czf /srv/jeux/sauvegardes/valheim-$(date +%%Y%%m%%d-%%H%%M).tar.gz -C /srv/jeux/valheim/donnees . && find /srv/jeux/sauvegardes -name "valheim-*.tar.gz" -mtime +14 -delete'
FIN

sudo tee /etc/systemd/system/sauvegarde-valheim.timer >/dev/null <<'FIN'
[Unit]
Description=Sauvegarde quotidienne du monde Valheim

[Timer]
OnCalendar=*-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
FIN

sudo systemctl daemon-reload
sudo systemctl enable --now sauvegarde-valheim.timer
```

**Vérification :**

```bash
systemctl list-timers | grep sauvegarde-valheim
sudo systemctl start sauvegarde-valheim
ls -lh /srv/jeux/sauvegardes/
```

Ces archives restent sur la même machine : elles te sauvent d'une fausse
manœuvre, pas d'une panne de disque. Copie-les périodiquement ailleurs.

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
sudo tar xzf /srv/jeux/sauvegardes/valheim-AAAAMMJJ-HHMM.tar.gz \
     -C /srv/jeux/valheim/donnees
sudo chown -R valheim:valheim /srv/jeux/valheim/donnees
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
