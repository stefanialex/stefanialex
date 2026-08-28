# Ancien PC → serveur IA et serveur de jeux

Scripts pour transformer un PC sous Pop!_OS en serveur maison qui fait tourner
des modèles de langage en local, et héberge des serveurs Minecraft et Valheim.

> **Ces scripts s'exécutent sur le PC lui-même**, pas depuis une session Claude
> Code distante. Copie le dépôt sur la machine, ou clone-le directement dessus.

---

## Dans quel ordre

| Étape | Script | Ce qu'il fait | Destructif |
|---|---|---|---|
| 0 | `00-audit.sh` | Inventaire du matériel, écrit `rapport-audit.md` | non |
| 1 | `01-disques.sh` | Formate les disques **secondaires**, monte `/srv/ia` et `/srv/jeux` | **oui** |
| 2 | `02-drivers.sh` | Pilotes GPU, microcode, fréquence CPU, SSH, pare-feu | non |
| 3 | `03-ia.sh` | Ollama, Open WebUI, LM Studio, modèles Hermes | non |
| 4 | `04-jeux.sh` | Minecraft (Paper) et Valheim (SteamCMD) | non |

## Où en est la machine `pop-os`

*Mis à jour le 2026-08-28 (pile IA désinstallée, serveur Valheim en service).
Rien de tout ceci n'est déductible du dépôt : `rapport-audit.md` est ignoré par
git et les scripts ne laissent pas de trace versionnée. D'où cette section.*

| Étape | État | Détail |
|---|---|---|
| 0 — audit | ✅ | Rejoué après l'installation du pilote, la synthèse est fiable |
| 1 — disques | ✅ | `sdb1` → `/srv/ia` (916 Gio), `sdc1` → `/srv/jeux` (146 Gio), ext4, `fstab` par UUID, remontage vérifié après redémarrage |
| 2 — pilotes | ✅ | `nvidia-driver-580` (580.173.02, CUDA 13.0), GTX 1070 et ses 8 Gio de VRAM reconnues |
| 3 — pile IA | ❌ | **Désinstallée le 2026-08-28**, voir ci-dessous. Les scripts restent valables pour la remonter ailleurs |
| 4 — jeux | 🟧 | Valheim en service depuis le 2026-08-28. Minecraft pas commencé, aucune unité `minecraft` |

### Étape 3 — désinstallée le 2026-08-28

Ollama, Open WebUI, LM Studio et Docker retirés en suivant
[`docs/desinstaller-ia.md`](docs/desinstaller-ia.md). `/` est passé de 32 à
24 Gio utilisés, `/srv/ia` de 24 Gio à 890 Mio. `03-ia.sh` et les docs associées
sont conservés tels quels : ils resserviront sur la machine de destination.

Ce qui **reste** sur la machine, non couvert par le doc de désinstallation —
4,8 Gio en tout :

- `/srv/ia/openwebui` (890 Mio) — conversations et comptes Open WebUI. Le doc en
  fait un choix explicite ; gardé faute de décision.
- `~/.hermes` (3,0 Gio) et `~/.lmstudio` (1,8 Gio), plus le lien mort
  `~/Modeles-IA` → `/srv/ia/lmstudio` et `~/.lmstudio-home-pointer`.
- Le groupe `docker` (vide) et le bloc `DOCKER-USER` dans `/etc/ufw/after.rules`.

`/srv/ia` lui-même n'est pas supprimé : c'est le point de montage de `sdb1`. Le
`rmdir` de l'étape 5 du doc échoue donc, sans conséquence — montage et `fstab`
intacts.

**Piège rencontré, à connaître avant de rejouer la désinstallation :**
`apt autoremove` voulait emporter `nvidia-firmware-595-595.84`, sans aucun
rapport avec Docker. Le pilote chargé est le 580.173.02 avec son
`nvidia-firmware-580` assorti ; le paquet 595 est un orphelin d'une série non
installée, sans dépendance inverse. Passé en « installé manuellement » pour le
soustraire à l'`autoremove`, qui n'a alors retiré que les cinq paquets Docker
(`containerd`, `runc`, `pigz`, `bridge-utils`, `ubuntu-fan`).

### Ce qui avait été mesuré, avant désinstallation

Gardé parce que ces chiffres valent pour la machine de destination, à VRAM
comparable.

- **Ollama** 0.32.7, API sur `*:11434`, modèles `hermes3:8b` et
  `nomic-embed-text`, à 100 % sur le GPU.
- **LM Studio** 0.4.21, moteur `llama.cpp-linux-x86_64-nvidia-cuda-avx2` 2.28.2 :
  Qwen3.5 9B (multimodal), Qwen2.5-Coder 7B, Gemma 3 4B (multimodal), en `Q4_K_M`.
- **Mesuré** le 2026-08-12 : Gemma 3 4B en contexte 8192 charge en 3,0 s, occupe
  4168 Mio de VRAM (donc entièrement sur le GPU) et produit 42 jetons/seconde.
  Débit d'`hermes3:8b` sur Ollama, mesuré le même jour : 36,5 jetons/seconde.

### Hermes Agent (2026-08-14)

*Toujours installé dans `~/.hermes` : la désinstallation de la pile IA ne l'a pas
touché, le doc ne le mentionne pas. Sans modèle local, il n'a plus rien à
piloter sur cette machine.*

**Hermes Agent** — le programme de Nous Research, à ne pas confondre avec le
modèle `hermes3:8b` — a été installé dans `~/.hermes` (v0.20.1, 2,1 Gio, rien au
niveau système, `rm -rf` suffit à défaire). Il exige 64 000 jetons de contexte,
ce qui a éliminé quatre modèles sur cinq. **Le bon est
`qwen3-4b-instruct-2507`** : appels d'outils corrects, 0,73 s par réponse contre
3 min 41 s pour un Qwen3 à raisonnement, contexte natif de 262 144 jetons. Deux
choses restent à finir, dont une à la souris dans LM Studio :
[`docs/hermes-agent.md`](docs/hermes-agent.md).

### Étape 4 — Valheim, installé le 2026-08-28

Posé à la main en suivant [`docs/valheim.md`](docs/valheim.md), pas par
`04-jeux.sh`. Serveur **privé** (`-public 0`, absent de la liste publique) et
**sans crossplay** (pas de drapeau `-crossplay`).

- Serveur dédié app 896660 dans `/srv/jeux/valheim/serveur` (1,7 Gio), monde
  `Midgard` dans `/srv/jeux/valheim/donnees`, sous le compte système `valheim`
  (uid 995, `nologin`).
- Unité `valheim.service` active et activée au démarrage, port UDP 2456.
  Identifiants dans `/etc/valheim.env` (`600`, root).
- Sauvegarde quotidienne à 04 h 30 : `sauvegarde-valheim.timer`, archives dans
  `/srv/jeux/sauvegardes`, purge au-delà de 14 jours. Essai concluant.

**Accès distant par Tailscale (2026-08-28).** Aucune redirection de port sur la
box, aucune exposition Internet : le serveur est joignable sur `100.76.246.124`
par un tunnel Tailscale. Le pare-feu n'accepte plus que SSH depuis
`192.168.1.0/24`, l'interface `tailscale0`, et `41641/udp` pour la traversée de
NAT ; les règles `2456:2457/udp` ouvertes au monde ont été retirées.

Le choix est motivé dans [`docs/valheim.md`](docs/valheim.md), étape 6 : tous les
joueurs sont sur PC, ce qui écarte `-crossplay` et son code d'invitation
régénéré à chaque redémarrage. **L'expiration de clé du nœud `valheim-serveur` a
été désactivée** dans la console Tailscale — sans ça il quitte le réseau au bout
de 180 jours, sans prévenir.

Débit mesuré le 2026-08-28 : 273 Mb/s descendants, **107 Mb/s montants**. Valheim
consomme 1 à 2 Mb/s montants par joueur : la connexion n'est pas un facteur
limitant, même à dix.

**Sauvegardes et performances (2026-08-28, seconde passe).** Le monde a été
déplacé de `sdc1` vers le SSD, en `/var/lib/valheim/donnees` — copie vérifiée
empreinte par empreinte, ancien dossier conservé sous
`/srv/jeux/valheim/donnees.avant-deplacement`. Archivage horaire vérifié
(`gzip -t` + `tar tzf`) et répliqué sur les trois disques, éclairci à une
archive par jour au-delà de trois jours, plus une copie quotidienne sur Google
Drive via rclone en portée `drive.file`. Restauration testée de bout en bout :
l'archive retéléchargée depuis le Drive a la même somme MD5 que l'originale.

`smartd` est actif, auto-test court chaque nuit et long le samedi. Les deux
disques mécaniques affichent **0 secteur réalloué, 0 en attente, 0
illisible** ; `sdb` totalise 25 300 heures, `sdc` 19 293. Les deux auto-tests
lancés le 28 août se sont terminés sans erreur.

**Le piège non évident de cette machine, et il coûte cher :**
`com.system76.Scheduler`, actif par défaut sur Pop!_OS, classe tout ce qui vit
dans `/system.slice` en `system-services nice=12 io="idle"`. Le serveur Valheim
héritait donc de la **priorité d'entrées-sorties la plus basse** — ses écritures
de sauvegarde passaient après tout le reste. Un `Nice=` dans l'unité systemd ne
suffit pas : l'ordonnanceur repasse toutes les 60 secondes et le réécrit ; une
assignation par nom de processus ne suffit pas non plus, la règle par cgroup
l'emporte. Il faut exclure explicitement `valheim.service` de cette règle dans
une copie complète de `/etc/system76-scheduler/config.kdl`. Résultat vérifié :
`nice=-5`, `io=(best-effort)0`.

Autre écueil : `system76-power` ne mémorise pas son profil. Sans l'unité
`profil-performance.service`, la machine repart en *Balanced* — gouverneur
`powersave`, ~2400 MHz sur 3800 — à chaque redémarrage.

**Fait le 2026-08-28, et hors de portée depuis Linux :** le rallumage
automatique après coupure de courant. C'est un réglage du BIOS MSI B250M MORTAR
(*Settings → Advanced → Power Management Setup → Restore after AC Power Loss →
Power On*), avec *ErP Ready* laissé désactivé dans le même menu — il coupe
l'alimentation de veille et empêche le rallumage. À revérifier après toute
remise à zéro du BIOS ou changement de pile : rien, depuis Linux, ne permet de
lire cet état. Le logiciel, lui, repartait déjà seul (`Restart=on-failure`,
services `enabled`, minuteries `Persistent=true`).

Deux choses que le doc ne dit pas, vérifiées ici :

1. **`Midgard.db` n'existe pas juste après le premier démarrage** — seul le
   `.fwl`. La vérification de l'étape 7 du doc échoue donc si on la lit au pied
   de la lettre. Le `.db` n'est écrit qu'à la première sauvegarde : au bout des
   30 min de `-saveinterval`, ou à l'arrêt propre. Un `systemctl stop` suffit à
   le faire apparaître, et valide au passage le `KillSignal=SIGINT` de l'unité
   (`World saved`, 8 s, loin des 120 s de marge).
2. **Le mot de passe reste lisible par tout utilisateur local.** Le sortir de
   l'unité vers `/etc/valheim.env` atteint l'objectif annoncé, mais systemd
   développe `${MOT_DE_PASSE}` dans `ExecStart` : il atterrit dans
   `/proc/<pid>/cmdline`, et `ps -eo args` l'affiche en clair depuis un compte
   non privilégié. Sans importance à un seul utilisateur, à savoir sinon.

### Traité le 2026-08-12

Les trois points ouverts de la première passe, plus un problème découvert en
route (le n° 2). Chaque correction vit dans les scripts, pas seulement sur la
machine : relancer l'étape concernée la repose à l'identique.

1. **Docker court-circuitait `ufw`** — corrigé. `03-ia.sh` écrit désormais une
   politique « réseau local seulement » dans la chaîne `DOCKER-USER`, via
   `/etc/ufw/after.rules` et `after6.rules`. C'est la seule chaîne que Docker et
   ufw respectent tous les deux. Vérifié : les règles survivent à un
   redémarrage de `docker` comme de `ufw`, dans les deux ordres, et ne se
   dupliquent pas d'un rechargement à l'autre.

   L'IPv6 méritait autant d'attention que l'IPv4 : la machine a une adresse
   publique routable (`2001:861:…`) que rien ne masque, faute de NAT. Le volet
   IPv6 autorise `fe80::/10` et le préfixe `/64` du moment. **Ce préfixe est
   délégué par la box et peut changer** : si l'accès IPv6 au réseau local cesse
   de fonctionner, relancer `03-ia.sh --confirm` suffit à le recalculer.

2. **Open WebUI ne voyait aucun modèle** — corrigé, et c'était invisible depuis
   l'interface. Le conteneur joint Ollama par `host.docker.internal`, donc par
   l'adresse de la passerelle Docker : la destination est l'hôte, ce trafic
   traverse `INPUT` et non `FORWARD`, et il se heurtait à la règle n'ouvrant le
   port 11434 qu'à `192.168.1.0/24` — alors que le conteneur sort en
   `172.17.0.x`. Rejet silencieux, délai d'attente, liste de modèles vide.
   `03-ia.sh` autorise maintenant explicitement l'entrée sur `docker0`.

3. **`openssh-server` est installé et actif** (depuis le 2026-08-10), et
   restreint au réseau local. Le profil `OpenSSH` d'ufw ouvrait le port 22 à
   tout Internet, en v4 comme en v6 : avec l'IPv6 publique et le mot de passe
   encore actif, cela revenait à offrir une invite de connexion au monde
   entier. `02-drivers.sh` pose désormais la règle pour `192.168.1.0/24`
   seulement et retire l'ancienne. Aucune tentative d'intrusion dans les
   journaux des sept jours précédents.

   **Réglé le 2026-08-14 :** la clé publique du portable `stefa@PClapin`
   (ED25519, `SHA256:N2uHKXqg0tvnbDNictzQk6re5VlHQP0QQcu4vrFStDc`) est déposée
   dans `/home/lapserv/.ssh/authorized_keys`, et `02-drivers.sh --confirm` l'a
   détectée : `/etc/ssh/sshd_config.d/99-serveur.conf` porte
   `PasswordAuthentication no`. Vérifié autrement qu'en lisant le fichier — une
   connexion forçant `PreferredAuthentications=password` se fait renvoyer
   « Permission denied (**publickey**) », donc sshd n'annonce plus le mot de
   passe du tout.

   L'accès SSH en IPv6 est fermé, y compris depuis le réseau local : l'IPv4
   suffit à la maison, et cela évite de dépendre d'un préfixe qui change.

4. **LM Studio** — `03-ia.sh` écrit maintenant les trois réglages qui n'étaient
   posés qu'à la main, donc irreproductibles : dossier de modèles sur
   `/srv/ia/lmstudio`, contexte par défaut à 8192 jetons, et
   `alwaysAllowLoadAnyway`. Le mode `high` du garde-fou est conservé — son
   avertissement est utile — mais il ne bloque plus un chargement que la VRAM
   permettrait. Le fichier `settings.json` est fusionné, jamais écrasé : il
   porte aussi tout l'état de l'interface.

   Le contexte par défaut reste le piège à connaître : Qwen3.5 annonce 262 000
   jetons, très au-delà de ce que 8 Gio de VRAM encaissent. Rester entre 8 000
   et 16 000.

### Mises à jour de sécurité automatiques (2026-08-12)

Activées par `02-drivers.sh`. Vérifié en bout de chaîne : les deux correctifs qui
attendaient (`yelp`, `libyelp0`) ont été installés par `unattended-upgrades`
lui-même, pas par un `apt upgrade` à la main. Prochain passage automatique tous
les jours vers 06 h 40.

**Le piège de Pop!_OS, qui aurait rendu tout ça décoratif.** `lsb_release -is`
répond `Pop`, alors que les correctifs sont des paquets Ubuntu
(`o=Ubuntu,a=noble-security`) servis par le miroir `apt.pop-os.org`. Le modèle
livré avec le paquet cible `${distro_id}:${distro_codename}-security`, soit
`Pop:noble-security` — qui ne correspond à aucune origine existante. Installé
sans rien changer, `unattended-upgrades` aurait tourné chaque nuit sans jamais
rien appliquer, et `systemctl status` aurait affiché un service parfaitement
vert. D'où l'origine désignée explicitement par `origin=` dans
`/etc/apt/apt.conf.d/52serveur-ia-securite`.

**Le redémarrage reste manuel** (`Automatic-Reboot "false"`) : un redémarrage
nocturne couperait net les serveurs de jeu et les sessions d'inférence. En
contrepartie, un correctif de noyau n'est actif qu'après un redémarrage.
Surveiller `/var/run/reboot-required`.

**Seize paquets resteront en retard, et c'est voulu par la distribution.**
Pop!_OS épingle son dépôt à la priorité 1001, au-dessus de tout : là où il livre
sa propre version, celle du dépôt de sécurité Ubuntu ne s'installe jamais. Au
2026-08-12 il s'agit de toute la famille systemd, en `255.4-1ubuntu8.15pop0…`
face à `255.4-1ubuntu8.17` côté Ubuntu. Rien d'autre n'est concerné.

Ce n'est pas un défaut de configuration et on n'y touche pas : forcer le systemd
d'Ubuntu par-dessus celui de Pop risque de casser COSMIC et l'intégration
System76. Mais `02-drivers.sh` le signale à chaque exécution, parce que « aucune
mise à jour en attente » se lirait sinon comme « rien à corriger », ce qui est
faux.

### Le piège permanent de cette machine

> **Levé le 2026-08-28.** `/etc/sudoers.d/99-lapserv-nopasswd` accorde
> `lapserv ALL=(ALL) NOPASSWD: ALL` : `sudo -n` fonctionne désormais depuis un
> contexte non interactif, et `pkexec` n'est plus nécessaire. La raison est
> l'usage, pas le confort — chaque `pkexec` ouvrait une fenêtre polkit sur
> l'écran physique, à valider au mot de passe, une par commande. Le revers est
> assumé : tout processus tournant sous `lapserv` peut devenir root sans
> authentification. Pour revenir en arrière,
> `sudo rm /etc/sudoers.d/99-lapserv-nopasswd`, et le paragraphe ci-dessous
> redevient vrai.

**`sudo` était inutilisable sans terminal** : il exige un tty pour son mot de
passe. Toute commande privilégiée lancée depuis un contexte non interactif devait
passer par `pkexec`, qui s'appuie sur l'agent polkit de COSMIC — en pensant à
repasser les variables d'environnement, que `pkexec` réinitialise.

Ce détail mordait les scripts eux-mêmes : ils lisaient `SUDO_USER`, que `pkexec`
ne renseigne pas, si bien que chaque `chown` vers le compte utilisateur était
silencieusement sauté et les dossiers restaient à `root` — hors de portée des
applications de bureau censées y écrire. `lib/common.sh` fournit désormais
`utilisateur_cible()`, qui retombe sur `PKEXEC_UID` puis sur le premier compte
humain.

Autre correction au passage : le test « le pare-feu est-il actif ? » cherchait
`Status: active` sur un système en français, qui répond « État : actif » — ufw
était donc réactivé à chaque exécution, en annonçant l'avoir fait. Les autres
scripts ont été relus : ni `00-audit.sh`, ni `01-disques.sh`, ni `04-jeux.sh` ne
touchent à `SUDO_USER` ou à ce motif.

### Tranché le 2026-08-28 : les ports de jeu sont ouverts à tous

`04-jeux.sh` ouvre les ports de jeu sans restriction de provenance
(`ufw allow 25565/tcp`, `ufw allow 2456:2458/udp`), alors que le tableau plus bas
affirmait que rien n'est exposé au-delà du réseau local. Les deux ne pouvaient
pas être vrais en même temps.

L'usage a tranché : le serveur Valheim est destiné à des amis hors de la maison,
donc l'exposition est assumée. `ufw allow 2456:2458/udp` est en place, sans
restriction de provenance.

**Ce que le doc Valheim ne dit pas, et qui compte ici :** la machine a une IPv6
publique routable, sans NAT pour la masquer. Contrairement à l'IPv4 — qui
exigerait encore une redirection sur la box — le serveur est donc **déjà
joignable depuis Internet en IPv6**, du seul fait de cette règle ufw. Pour
revenir au réseau local :

```bash
sudo ufw delete allow 2456:2458/udp
sudo ufw allow from 192.168.1.0/24 to any port 2456:2458 proto udp
```

---

### Deux règles qui s'appliquent partout

**Rien ne s'exécute sans `--confirm`.** Lancé sans ce drapeau, chaque script
affiche en jaune les commandes qu'il *exécuterait* et s'arrête. Prends
l'habitude de lire cette sortie avant de confirmer.

**Relancer ne casse rien.** Les scripts sont idempotents : ils détectent ce qui
est déjà en place et ne le refont pas. Si une étape échoue à mi-parcours,
corrige et relance le même script.

---

## Démarrage

```bash
git clone https://github.com/stefanialex/stefanialex.git
cd stefanialex/serveur
chmod +x *.sh

# Étape 0 — inventaire, ne modifie rien
sudo ./00-audit.sh
less rapport-audit.md
```

Le rapport d'audit détermine tout le reste : taille de modèle chargeable,
présence d'un GPU utilisable, état des disques. Lis-le avant de continuer.
Voir [`docs/materiel.md`](docs/materiel.md) pour l'interpréter.

```bash
# Étape 1 — disques. D'abord en simulation, toujours.
sudo ./01-disques.sh
sudo ./01-disques.sh --confirm

# Étape 2 — pilotes et réglages système
sudo ./02-drivers.sh
sudo ./02-drivers.sh --confirm
sudo reboot          # nécessaire si un pilote ou zram a été installé

# Étape 3 — pile IA
sudo ./03-ia.sh
sudo ./03-ia.sh --confirm

# Étape 4 — serveurs de jeu, quand la partie IA est validée
sudo ./04-jeux.sh --confirm minecraft
```

---

## Ce que tu obtiens

*Ce que les scripts installent. Sur `pop-os` au 2026-08-28, seules les deux
dernières lignes sont en service : la pile IA a été désinstallée.*

| Service | Adresse | Remarque |
|---|---|---|
| ~~Interface de chat (Open WebUI)~~ | ~~`http://<ip-du-pc>:8080`~~ | Désinstallé le 2026-08-28 |
| ~~API Ollama~~ | ~~`http://<ip-du-pc>:11434`~~ | Désinstallé le 2026-08-28 |
| ~~LM Studio~~ | ~~application de bureau~~ | Désinstallé le 2026-08-28 |
| ~~API LM Studio~~ | ~~`http://127.0.0.1:1234`~~ | Désinstallé le 2026-08-28 |
| Administration à distance | `ssh <toi>@<ip-du-pc>` | IPv4 et réseau local uniquement |
| Minecraft | `<ip-du-pc>:25565` | Pas installé |
| **Valheim** | `<ip-du-pc>:2456` (UDP) | **En service.** Ouvert à tous, voir la section « Tranché » |

SSH n'est ouvert que pour le **réseau local**, en clé uniquement. Les ports d'IA
ont été refermés avec la désinstallation.

Les ports de jeu font exception et sont ouverts sans restriction de provenance :
c'est le choix acté plus haut. La seule authentification devant le serveur
Valheim est donc son mot de passe — il tient le rôle d'une serrure exposée sur
la rue, à choisir en conséquence.

Deux réflexes à garder si tu ajoutes un service plus tard. Un port publié par un
conteneur Docker n'est **pas** protégé par une règle `ufw allow from … to any
port …` : il faut passer par `DOCKER-USER`, comme le fait `03-ia.sh`. Et l'IPv6
n'est pas un doublon de l'IPv4 — sans NAT pour masquer la machine, une règle
posée seulement en v4 ne protège rien.

---

## Options

Chaque script accepte des variables d'environnement pour dévier des défauts :

```bash
# Ne pas installer LM Studio (machine sans écran)
sudo SAUTER_LMSTUDIO=1 ./03-ia.sh --confirm

# Ne pas télécharger de modèle tout de suite
sudo SAUTER_MODELES=1 ./03-ia.sh --confirm

# Choisir où vivent les données
sudo RACINE_IA=/mnt/gros-disque ./03-ia.sh --confirm

# Fixer la mémoire allouée à Minecraft
sudo RAM_MINECRAFT=8G ./04-jeux.sh --confirm minecraft
```

`./<script>.sh --help` liste les options de chacun.

---

## Documentation

- [`docs/materiel.md`](docs/materiel.md) — lire le rapport d'audit, décider
  d'une réinstallation complète, savoir quoi améliorer sur la machine
- [`docs/modeles.md`](docs/modeles.md) — quel modèle pour quelle mémoire,
  comprendre les quantisations, les modèles Hermes
- [`docs/exploitation.md`](docs/exploitation.md) — démarrer/arrêter, lire les
  journaux, sauvegardes, faire cohabiter IA et serveur de jeu, accès distant
- [`docs/hermes-agent.md`](docs/hermes-agent.md) — l'agent Hermes (le programme,
  pas le modèle) : installé, mais 64k de contexte minimum contre 8 Gio de VRAM

---

## En cas de problème

Chaque script journalise tout dans `/var/log/serveur-ia/`. Pour la dernière
exécution d'un script :

```bash
ls -t /var/log/serveur-ia/ | head
less /var/log/serveur-ia/03-ia-*.log
```

L'état des services :

```bash
systemctl status ollama
docker logs open-webui
journalctl -u minecraft -f
```
