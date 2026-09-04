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

**État actuel, vérifié le 2026-09-03 : plus aucune règle de port de jeu dans
`ufw`.** Le choix du 2026-08-28 a été rétabli entre-temps : les joueurs passent
tous par Tailscale, et c'est mesuré — les trois connexions du soir arrivaient
sur des adresses `100.x`. C'est le montage à conserver.

**Ce que le doc Valheim ne dit pas, et qui compte ici :** la machine a une IPv6
publique routable, sans NAT pour la masquer. Contrairement à l'IPv4 — qui
exigerait encore une redirection sur la box — un simple `ufw allow 2456:2458/udp`
rendrait le serveur **immédiatement joignable depuis Internet**, du seul fait de
cette règle. Si un jour il faut ouvrir le jeu à quelqu'un qui refuse Tailscale,
borner la provenance plutôt que d'ouvrir à tous :

```bash
sudo ufw allow from 192.168.1.0/24 to any port 2456:2458 proto udp
```

---

### Administration web, installée le 2026-09-03 : Cockpit

Console d'administration de la machine dans le navigateur : état des trois
disques avec leur usure SMART, services systemd — donc **démarrer, arrêter,
redémarrer `valheim.service` et lire son journal sans terminal** —, mises à
jour, réseau, et un gestionnaire de fichiers pour récupérer une archive de
`/srv/ia/sauvegardes-valheim`.

**L'installation ne marche pas avec le dépôt principal.** Noble est resté en
Cockpit 314, alors que `cockpit-files` exige un `cockpit-bridge` ≥ 318. Il faut
prendre l'ensemble en backports, où vit la branche réellement maintenue :

```bash
sudo apt-get install -y -t noble-backports \
  cockpit cockpit-ws cockpit-bridge cockpit-system cockpit-storaged cockpit-files
```

Sans `-t noble-backports`, apt garde la priorité 100 des backports et refuse de
bouger, avec un message de dépendance non satisfaite qui n'explique rien.
Installé ici : Cockpit **362**, `cockpit-files` **39**, plus
`cockpit-networkmanager` et `cockpit-packagekit` venus en dépendance.

**Le point de sécurité, et il n'est pas évident.** Le paquet active
`cockpit.socket` tout seul, qui écoute sur `*:9090` — donc aussi sur
`tailscale0`. Or le pare-feu autorise **tous les ports** sur cette interface
(`allow in on tailscale0`), et le tailnet ne contient pas que les machines de la
maison : les PC des autres joueurs y sont partagés pour pouvoir se connecter au
jeu. Laissé en l'état, ça revient à publier un formulaire de connexion root à
leur intention.

L'écoute est donc bornée au réseau local :

```bash
sudo mkdir -p /etc/systemd/system/cockpit.socket.d
sudo tee /etc/systemd/system/cockpit.socket.d/ecoute-locale.conf >/dev/null <<'FIN'
[Socket]
ListenStream=
ListenStream=192.168.1.120:9090
FreeBind=yes
FIN
sudo systemctl daemon-reload && sudo systemctl restart cockpit.socket
sudo ufw allow from 192.168.1.0/24 to any port 9090 proto tcp \
  comment 'Cockpit, reseau local uniquement'
```

Le `ListenStream=` vide est indispensable : il annule la valeur du paquet au
lieu de s'y ajouter, les sockets systemd étant cumulatives.

Accès : **`https://192.168.1.120:9090`**, compte `lapserv` avec le mot de passe
du compte. Cockpit passe par PAM — la dispense `sudo` sans mot de passe ne s'y
applique pas. Le certificat est auto-signé, le navigateur avertit une fois.

Vérification, la deuxième ligne devant échouer :

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://192.168.1.120:9090/   # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://100.76.246.124:9090/  # 000
```

**Reste à faire si l'accès à distance devient utile :** ajouter l'adresse
Tailscale à `ListenStream`, mais **seulement après** avoir restreint la
politique d'accès du tailnet dans la console Tailscale, pour que les appareils
partagés n'aient droit qu'à l'UDP 2456-2458 du jeu au lieu de tout. Dans cet
ordre, jamais l'inverse.

---

### Module Cockpit « Valheim », ajouté le 2026-09-03

Cockpit administre la machine, pas la partie. Le complément vit dans
[`cockpit-valheim/`](cockpit-valheim/) : deux fichiers statiques, aucun service,
aucun port supplémentaire, et **l'authentification est celle de Cockpit** — donc
rien de nouveau à protéger.

```bash
sudo mkdir -p /usr/share/cockpit/valheim
sudo cp cockpit-valheim/index.html cockpit-valheim/manifest.json /usr/share/cockpit/valheim/
sudo chown root:root /usr/share/cockpit/valheim/*
sudo chmod 644 /usr/share/cockpit/valheim/*
cockpit-bridge --packages | grep valheim    # doit lister le module
```

Un onglet « Valheim » apparaît dans la barre latérale après rechargement de la
page. Aucun redémarrage de service : Cockpit relit ses modules à chaque session.
Pour modifier la page, éditer `/usr/share/cockpit/valheim/index.html` et
recharger — pas de compilation, pas d'outillage.

Ce qu'il affiche : l'état du service et sa mémoire, **qui est en jeu par pseudo**,
la latence et le débit de chaque appareil du tailnet, le compte de ZDOs du monde
avec l'estimation des zones explorées, les prochaines sauvegardes et les
dernières archives. Deux boutons : sauvegarder maintenant, et redémarrer la
partie avec confirmation.

**Les pseudos ne sont pas dans une base, ils se déduisent du journal.** Aucune
ligne ne relie un pseudo à un compte Steam : il faut suivre la séquence
`Got connection SteamID <compte>` → `Got character ZDOID from <pseudo>`, puis
`Closing socket <compte>` pour le départ. C'est ce que fait `analyseJournal()`,
et c'est pour ça qu'elle lit le journal dans l'ordre au lieu de filtrer.

**Deux pièges rencontrés en l'écrivant :**

`NextElapseUSecRealtime` ne renvoie **pas** des microsecondes malgré son nom,
mais une date lisible (`Thu 2026-09-03 21:01:36 CEST`). La convertir côté
serveur avec `date -d "$n" +%s` évite en plus toute ambiguïté de fuseau entre la
machine et le navigateur.

Les appels privilégiés utilisent `superuser: "require"`. Au premier chargement,
Cockpit affiche un bandeau « accès limité » : il faut activer l'accès
administrateur, sinon les cartes restent vides avec une erreur. La dispense
`sudo` sans mot de passe de cette machine rend l'opération immédiate.

---

### La page Cockpit était cassée, pas moche : la CSP, le 2026-09-04

Symptôme : page en Times New Roman, boutons bruts du navigateur, `chargement…`
figé, toutes les données affichées `…`. Diagnostiqué deux fois de travers avant
d'être compris, ce qui vaut d'être écrit noir sur blanc.

Cockpit sert les pages de modules avec cette politique de sécurité de contenu,
lisible dans le binaire `cockpit-ws` :

```
default-src 'self'; connect-src 'self' ws: wss:; form-action 'self';
base-uri 'self'; object-src 'none'; font-src 'self' data:; img-src 'self' data:
```

Pas de `'unsafe-inline'`. Or le module mettait tout son CSS dans un `<style>` et
tout son JavaScript dans un `<script>` sans `src` : **le navigateur bloquait les
deux**, sans que le serveur voie quoi que ce soit. D'où deux fausses pistes —
d'abord un décalage PatternFly 5 / 6, ensuite l'empreinte de session de Cockpit
qui aurait servi une vieille page depuis le cache. Ni l'une ni l'autre n'était la
cause : la page n'avait jamais été affichée stylée une seule fois.

Le signe qui aurait dû trancher tout de suite : **aucun module officiel de
Cockpit n'utilise d'inline.** `systemd`, `storaged` et `networkmanager` chargent
tous leur CSS par `<link rel="stylesheet">` et leur script par `<script src>`.
Ce n'est pas une préférence de style, c'est imposé par la CSP.

Le module est donc en trois fichiers :

```
/usr/share/cockpit/valheim/index.html     structure seule
/usr/share/cockpit/valheim/valheim.css    <link rel="stylesheet" href="valheim.css">
/usr/share/cockpit/valheim/valheim.js     <script src="valheim.js"></script>
```

Les chemins relatifs des `@font-face` (`../../static/fonts/`) restent valides :
dans une feuille de style, ils se résolvent par rapport au fichier CSS, qui vit
dans le même répertoire que la page.

**À retenir pour tout ajout au module :** un `style=` ou un `onclick=` dans le
HTML sera bloqué de la même façon, silencieusement. Tout passe par les fichiers
externes.

---

### Redémarrage du jeu passé en quotidien, le 2026-09-04

`redemarrage-valheim.timer` existait depuis le 2026-08-28 en hebdomadaire
(lundi 5 h). Passé à tous les jours à 5 h, heure sans joueur connecté :

```bash
sudo mkdir -p /etc/systemd/system/redemarrage-valheim.timer.d
sudo tee /etc/systemd/system/redemarrage-valheim.timer.d/quotidien.conf >/dev/null <<'FIN'
[Timer]
OnCalendar=
OnCalendar=*-*-* 05:00:00
FIN
sudo systemctl daemon-reload
```

**Le `OnCalendar=` vide est indispensable**, exactement comme le `ListenStream=`
vide de Cockpit : les valeurs de minuterie s'ajoutent au lieu de se remplacer.
Sans cette ligne, le lundi 5 h resterait en plus du quotidien.

Le service fait une sauvegarde avant de redémarrer, et l'arrêt propre
(`KillSignal=SIGINT`, `TimeoutStopSec=120`) écrit le monde sur disque.
Indisponibilité constatée : moins d'une minute.

**Ce n'est pas un redémarrage de la machine**, seulement du service de jeu.
C'est ce qui règle la dérive mémoire de Valheim ; un redémarrage système reste
à ajouter si les mises à jour de noyau doivent être prises en compte
automatiquement.

---

### Statistiques de joueurs, sans aucun mod, le 2026-09-04

Le journal du serveur suffit à mesurer l'essentiel. Ce qu'il contient
réellement, vérifié sur trois jours de journal de cette machine :

| Ligne du journal | Ce qu'elle donne |
|---|---|
| `Got connection SteamID 765611980…` | arrivée d'un joueur, avec son identifiant Steam |
| `Got character ZDOID from Beware : 2503316426:7` | apparition, avec le **pseudo** |
| `Got character ZDOID from Beware : 0:0` | **mort** — le `0:0` est la signature |
| `Closing socket 765611980…` | départ, appariable à l'arrivée par le SteamID |
| `Random event set:army_theelder` | raid de l'Ancien, **donc l'Ancien est vaincu** |
| `Saved 302321 ZDOs` | poids du monde |
| `Time 12345,6, day:154 …` | jour dans le monde |

Deux trouvailles portent tout le reste :

**Les raids datent la progression.** Valheim ne déclenche le raid d'un boss
qu'une fois ce boss vaincu. Le journal ne dit rien des *global keys*, qui vivent
dans le fichier de monde sans horodatage — mais la première occurrence de
`army_theelder` donne une borne haute datée de la victoire sur l'Ancien. C'est
indirect et il faut le présenter comme tel : « vaincu avant le … ».

**Le pseudo et le SteamID n'apparaissent jamais sur la même ligne.** Le pseudo
n'est écrit que sur les lignes ZDOID, le SteamID que sur les connexions. Le
rapprochement se fait par la séquence : une apparition suit toujours de quelques
secondes la connexion qui l'a provoquée. L'association n'est retenue que si
**une seule** connexion est en attente dans la fenêtre de 180 s — sinon deux
joueurs entrant ensemble produiraient une correspondance fausse.

Deux scripts et un service :

```bash
sudo install -o root -g root -m 755 valheim-stats/collecte-valheim.py \
  valheim-stats/stats-valheim.py /usr/local/bin/
sudo install -o root -g root -m 644 valheim-stats/collecte-valheim.service \
  /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now collecte-valheim
stats-valheim.py            # rapport texte
stats-valheim.py --json     # même chose pour la page Cockpit
```

Le collecteur tourne sous l'utilisateur `valheim` avec
`SupplementaryGroups=systemd-journal` — sans ce groupe il ne peut pas lire le
journal — et `StateDirectory=valheim-stats`, qui crée `/var/lib/valheim-stats`
au bon propriétaire et fournit `STATE_DIRECTORY` au script.

**Le collecteur relit tout le journal à chaque démarrage** au lieu de suivre un
curseur. C'est volontaire : l'insertion est idempotente, donc une relecture ne
crée pas de doublon, et le service se répare seul après une coupure ou une base
supprimée. Pas de curseur à maintenir, pas d'état qui puisse se désynchroniser.

**Le piège qui a été attrapé au test.** L'idempotence reposait d'abord sur une
contrainte `UNIQUE (horodatage, type, joueur, steamid, detail)`. Elle ne
marchait pas : dans SQLite, **deux `NULL` ne sont jamais considérés égaux dans
une contrainte d'unicité**, et la plupart des lignes ont des colonnes nulles
(pas de pseudo sur une connexion, pas de SteamID sur une mort). Chaque relecture
dupliquait donc tout le journal. Remplacée par un index sur expressions :

```sql
CREATE UNIQUE INDEX idx_ev_unique ON evenements (
  horodatage, type, COALESCE(joueur, ''), COALESCE(steamid, ''), COALESCE(detail, '')
);
```

Relancer `collecte-valheim.py --rattrapage-seul` deux fois de suite doit
annoncer « 0 nouveaux » la seconde fois. C'est le test.

**Ce que le serveur ne peut pas savoir.** Les fichiers de personnage (`.fch`)
vivent chez le joueur : compétences, morts cumulées et succès Steam sont hors
de portée. Tout ce qui est mesuré ici l'est à l'échelle du monde et des sessions.

---

### Lire et fabriquer la seed d'un monde, le 2026-09-04

Le serveur dédié n'a **pas** de paramètre `-seed` : lancé sur un nom de monde
inexistant, il tire une seed au hasard. La méthode répandue consiste à créer le
monde sur un PC client puis à copier les fichiers, ce qui suppose un joueur
disponible et sur la bonne version du jeu.

`monde-valheim/monde-valheim.py` évite ce détour en écrivant directement le
`.fwl`, qui ne contient que des métadonnées — 48 octets :

```bash
monde-valheim.py lire /var/lib/valheim/donnees/worlds_local/Midgard.fwl
monde-valheim.py creer Nouveau.fwl --monde Nouveau --seed HHcLC5acQt
```

Le format est un « package » Unity : entier de longueur, version de format,
nom du monde, nom de la seed, seed entière, identifiant unique, version du
générateur de monde, **un booléen `besoin_db`, puis un compteur de clés
globales initiales**.

**Les deux derniers champs ont d'abord été oubliés, et le serveur a refusé le
fichier** — `Failed to load world with name "Essai", data error LoadError`,
suivi d'une régénération silencieuse du monde avec une seed au hasard. Le piège
est que la lecture *semblait* réussir : les champs précédents tombaient juste, et
il restait simplement 5 octets non lus en queue. D'où le champ
`octets_restants` dans la sortie de `lire` : **il doit valoir 0**, c'est le seul
contrôle qui attrape ce genre d'erreur.

Vérifié en conditions réelles sur un serveur jetable, port 2466, répertoire de
sauvegarde séparé :

```
Load world: Fabrique (Fabrique)      <- accepté, aucun LoadError
Fabrique.db                          <- 89 Ko, monde généré par le serveur
monde                Fabrique
seed                 HHcLC5acQt      <- ma seed, conservée
besoin_db            True            <- passé de False à True tout seul
```

Le serveur a donc chargé le fichier fabriqué, généré le monde correspondant, et
mis à jour `besoin_db` de lui-même. **On peut imposer la seed entièrement côté
serveur**, sans passer par un PC client — ce que la documentation communautaire
donne pourtant comme impossible.

**La seed entière doit concorder avec le nom de seed.** Valheim stocke les deux,
et c'est l'entier que le générateur utilise. L'entier se calcule par
`GetStableHashCode()`, réimplémentée dans le script et **vérifiée contre le
monde en place** : `m24VpSVsVw` donne bien `2007084186`. Cette vérification est
le test à refaire si le format change.

Relevé du monde actuel, à conserver comme référence avant la 1.0 :

| | |
|---|---|
| monde | `Midgard` |
| seed | `m24VpSVsVw` |
| version de format | 37 |
| **version du générateur** | **2** |

Le dernier champ est le plus intéressant à l'approche du 9 septembre : **s'il
passe à 3 avec la 1.0, la génération de monde a changé** et aucune seed
conseillée avant le lancement n'est fiable. C'est une vérification objective,
faisable en une commande sur un monde créé par la 1.0, là où la documentation
communautaire ne fait que spéculer.

---

### Page Cockpit « Valheim — défis », le 2026-09-04

Deuxième page du même module, deuxième entrée de menu dans `manifest.json`.
Elle affiche les joueurs (sessions, temps de jeu, morts, morts par heure), le
monde avec sa seed, la progression des boss, et les défis calculés.

**Les défis sont mesurés, pas déclarés.** Un défi qu'on ne peut pas vérifier
automatiquement finit en dispute : « pas de portail » ou « pacifiste » restent
donc volontairement dehors. Ce qui est calculé depuis le journal :

| Défi | Métrique |
|---|---|
| Intact depuis *boss* | morts enregistrées après le premier raid de ce boss |
| Le plus solide | morts par heure de session — plus juste qu'un total brut, qui ne punirait que celui qui joue le plus |
| Série en cours | temps écoulé depuis la dernière mort, en direct |
| Rythme du groupe | écart entre les premiers raids de deux boss consécutifs |

Le défi proposé par Bab-y — n'être jamais mort après avoir battu l'Ancien —
correspond à la première ligne, généralisée à chaque boss dont on a la date.

**La page ne demande aucun privilège**, contrairement aux cartes de la page
principale qui utilisent `superuser: "require"`. C'est délibéré : une page de
consultation ne devrait pas exiger l'accès administrateur. C'est ce qui a
décidé de l'endroit où la seed est relevée — voir plus haut, le collecteur
l'inscrit en base parce que lui seul peut lire `/var/lib/valheim` (0750).

**Aucun `innerHTML` dans `stats.js`** : les pseudos viennent du journal du
serveur, donc d'une source non maîtrisée. Tout passe par `createElement` et
`textContent`.

---

### Bascule vers un monde neuf, automatisée, le 2026-09-04

Prévu pour la 1.0 du 9 septembre : monde neuf, personnages neufs, compteurs de
défis remis à zéro. Une commande, avec simulation par défaut :

```bash
sudo nouveau-monde-valheim.sh --nom Nordheim --seed HHcLC5acQt     # simulation
sudo nouveau-monde-valheim.sh --nom Nordheim --seed HHcLC5acQt --confirm
```

Sans `--seed`, dix caractères sont tirés au hasard comme le fait le jeu.

Ce que le script enchaîne : sauvegarde complète et vérifiée sur trois disques,
arrêt propre du serveur (qui écrit le monde en s'arrêtant), déplacement des
fichiers de l'ancien monde vers `anciens-mondes/`, fabrication du `.fwl` avec
la seed choisie, bascule de `NOM_MONDE` dans `/etc/valheim.env`, redémarrage,
puis **attente d'une preuve dans le journal** — la ligne `Load world: <nom>`,
ou l'erreur de format. Il ne se déclare pas satisfait sur un simple code de
retour.

**Il refuse de tourner si un joueur est en jeu** (`--force` outrepasse). Le
garde-fou a servi dès le premier essai : DjOsE était connecté.

**Le champ `--generateur` est la précaution pour le 9 septembre.** Le script
inscrit par défaut la version du générateur du monde actuel (2). Si la 1.0
change ce nombre, le serveur refusera le fichier fabriqué — et le message
d'erreur dit quoi faire : lire le `.fwl` d'un monde créé par la 1.0, puis
relancer avec la bonne valeur. L'ancien monde reste intact dans
`anciens-mondes/` en attendant.

Les joueurs, eux, créent leur personnage eux-mêmes : le fichier `.fch` vit chez
eux, le serveur n'y touche jamais.

---

### Le nom du monde ne se devine plus, le 2026-09-04

Le collecteur déduisait le monde courant en listant les `.fwl` du répertoire de
sauvegarde. Ça marchait avec un seul monde ; dès que l'ancien traîne à côté du
nouveau, le classement alphabétique désigne n'importe lequel des deux — et les
statistiques du monde neuf se seraient retrouvées étiquetées au nom de l'ancien.

Le nom est maintenant lu sur la **ligne de commande du serveur**, dans
`/proc/<pid>/cmdline`, où l'argument `-world` figure déjà développé. Le
collecteur tourne sous le même utilisateur que le jeu, donc `/proc` lui est
ouvert — là où `/etc/valheim.env`, qui contient le mot de passe, ne l'est pas.
Repli sur le `.fwl` le plus récemment écrit si le serveur est arrêté.

---

### Événements publiés sur Discord, le 2026-09-04

```bash
sudo install -o root -g root -m 755 valheim-discord/notifie-discord-valheim.py /usr/local/bin/
sudo install -o root -g root -m 644 valheim-discord/notifie-discord-valheim.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now notifie-discord-valheim.timer
```

Arrivées, morts avec le compte à jour, raids. Un passage par minute.

**Les départs et leur durée de session ont été retirés le 2026-09-04**, à la
demande du groupe : « je me sens fliqué, elle est où la pointeuse ? ». Le
message était `👋 Beware repart après 52 min de jeu` — annoncer à tout le
salon combien de temps chacun a joué, à chaque déconnexion, transformait un
outil de jeu en pointeuse. Le grief était juste.

**Les sessions restent mesurées en base** : les KPI de temps de jeu et le calcul
des jalons en dépendent. Ce qui a changé, c'est la publication au fil de l'eau,
pas la mesure. À noter que le bilan de 19 h mentionne encore le temps de jeu par
joueur, indirectement, via le défi « le plus solide » (`5 morts en 39 h 26`) —
à retirer aussi si ça gêne.

**Le notifieur ne relit pas le journal : il consomme la base du collecteur.**
Les deux morceaux restent indépendants — un seul code connaît le format des
logs — et surtout le curseur n'avance qu'**après** publication réussie, donc
une coupure réseau chez Discord ne fait perdre aucun événement.

**Au premier démarrage, le curseur se cale sur le présent** sans rien publier.
Sans cette précaution, tout l'historique du monde partirait d'un coup dans le
salon. Au-delà de dix événements en retard, un résumé remplace la rafale.

L'adresse du webhook vit dans `/etc/valheim-discord.conf`, **hors du dépôt** :
c'est un secret, quiconque l'a peut écrire dans le salon. Le fichier est en
`640 root:valheim`. Sans adresse configurée, le script sort en succès sans rien
faire — il peut donc être armé avant que l'adresse existe, ce qui est le cas
ici.

Testé de bout en bout contre un faux salon local sur `127.0.0.1:8899`, avec les
vrais événements de la base, plutôt que sur Discord :

```
🛡️  **Beware** arrive sur le serveur. (13:42)
⚔️  Raid : l'armee de Bonemass attaque la base. (13:57)
👋  **Beware** repart apres 52 min de jeu.
```

---

### Cockpit joignable même si la box change l'adresse, le 2026-09-04

Appliqué. **`https://192.168.1.253:9090` est désormais l'adresse à retenir** :
elle ne dépend plus de la box. `192.168.1.120` reste valide et continue de
servir la redirection de ports du jeu.

Le problème : Cockpit écoute sur `192.168.1.120` en dur, adresse venue du DHCP,
et la box est inaccessible donc aucune réservation n'est possible. Avec
`FreeBind=yes`, le socket se lierait quand même à une adresse absente — Cockpit
démarrerait sans être joignable, sans erreur.

La solution : une **deuxième adresse fixe sur la même carte**, `192.168.1.253`,
vérifiée libre par sonde ARP, et Cockpit écoute sur les deux. L'ancienne reste
en place pour la redirection de ports du jeu, que seule la box pourrait changer.

**Pourquoi pas le pare-feu.** L'autre approche — faire écouter Cockpit partout
et refuser le port 9090 sur `tailscale0` — a été écartée pour une raison de
vérifiabilité : depuis la machine, un appel à sa propre adresse Tailscale passe
par la boucle locale et non par l'interface, donc **aucune commande locale ne
peut prouver** que les PC des autres joueurs, pour lesquels le pare-feu
autorise tous les ports sur le tailnet, n'atteignent pas le formulaire de
connexion. En gardant une écoute liée à des adresses précises, la preuve
redevient locale : `ss -tln | grep 9090` doit ne montrer que du `192.168.1.x`.

**Deux raisons pour lesquelles ce script existe au lieu d'avoir été lancé.**
D'abord `cockpit.service` a `Requires=cockpit.socket` : redémarrer le socket
arrête Cockpit, et la console web par laquelle passait le travail avec lui.
Ensuite la modification réseau a été refusée par le garde-fou de sécurité de
l'outil, à juste titre s'agissant de la connectivité de la machine.

Le script se vérifie donc lui-même — écoute effective sur les deux adresses,
code 200 sur chacune, aucune écoute au-delà du réseau local — et **revient en
arrière tout seul** si l'un de ces contrôles échoue, en restaurant le fichier
d'écoute sauvegardé dans `/var/backups/`.

**Le filet s'est déclenché au premier lancement, sur une fausse alarme.** La
bascule avait réussi — les deux adresses répondaient 200 — mais le contrôle
« aucune écoute au-delà du réseau local » était écrit ainsi :

```bash
ss -tln | grep 9090 | grep -qE '0\.0\.0\.0|100\.'      # FAUX
```

`ss -tln` sort **deux** colonnes d'adresses, et la distante vaut toujours
`0.0.0.0:*` sur une socket en écoute :

```
LISTEN 0 4096   192.168.1.120:9090        0.0.0.0:*
                ^ adresse locale          ^ adresse distante, toujours ce joker
```

Le test ne pouvait donc jamais passer, même avec une écoute parfaitement bornée.
Il lit maintenant la seule colonne qui compte :

```bash
ECOUTES=$(ss -Hltn 'sport = :9090' | awk '{ print $4 }')
HORS=$(printf '%s\n' "$ECOUTES" | grep -vE '^192\.168\.1\.[0-9]+:9090$')
```

Vérifié sur les quatre cas qui comptent : `192.168.1.120 + .253` accepté,
`0.0.0.0:9090`, `[::]:9090` et une adresse `100.x` du tailnet refusés.

Second défaut du même lancement : `nmcli device reapply` rend la main **avant**
que la nouvelle adresse soit effectivement posée. Le script affichait la liste
trop tôt et n'y voyait que l'ancienne adresse. Il attend maintenant la preuve,
quinze secondes au plus, et abandonne si l'adresse n'apparaît pas.

Résultat du second lancement, celui qui est passé :

```
inet 192.168.1.120/24 ... enp0s31f6
inet 192.168.1.253/24 ... secondary enp0s31f6
ecoutes : 192.168.1.120:9090 192.168.1.253:9090
https://192.168.1.120:9090/ -> 200
https://192.168.1.253:9090/ -> 200
```

**Persistance vérifiée**, et pas seulement l'état courant. Le fichier netplan
porte bien les deux adresses, le keyfile régénéré dans `/run/` les reproduit —
`address1=192.168.1.120/24,192.168.1.254` puis `address2=192.168.1.253/24` — et
`netplan generate` rend un fichier au md5 identique, donc le démarrage
reproduira cet état. La règle `ufw` existante n'a rien demandé : elle porte sur
le port de destination et la source `192.168.1.0/24`, pas sur l'adresse
d'arrivée.

---

### Le jour J : `jour-j-valheim.sh`, le 2026-09-04

Un script pour le 9 septembre, parce qu'il n'y a **aucune branche de test
public** pour le serveur dédié — vérifié en listant les branches Steam de
l'app 896660 : `public`, plus cinq branches de retour arrière
(`default_old`, `default_preal`, `default_prebw`, `default_precta`,
`default_preml`). La 1.0 arrivera donc sans préavis observable, et mieux vaut
être prêt qu'improviser.

```bash
jour-j-valheim.sh --verifier                       # audit, ne modifie rien
jour-j-valheim.sh --attendre                       # guette la publication
sudo jour-j-valheim.sh --maj --confirm             # met à jour
sudo jour-j-valheim.sh --sonde --confirm           # mesure ce qui a changé
sudo jour-j-valheim.sh --monde --nom X --seed Y --confirm
sudo jour-j-valheim.sh --tout --nom X --seed Y --confirm
sudo jour-j-valheim.sh --retour-arriere --confirm  # si la 1.0 casse tout
```

**La détection de la sortie se fait par comparaison de buildid**, et elle est
déjà fonctionnelle :

```
buildid installe   21981590     ← "buildid" dans steamapps/appmanifest_896660.acf
buildid publie     21981590     ← branches/public dans app_info_print
                   identiques : la 1.0 n'est pas encore publiee
```

Deux précautions dans la lecture du buildid distant. `app_info_update 1` force
le rafraîchissement du cache, sans quoi SteamCMD peut resservir une valeur
vieille de plusieurs heures et la détection passerait à côté. Et l'extraction
ne lit **que** la branche `public` : les branches `default_pre*` portent des
buildid plus anciens qui feraient croire à un changement.

**`--sonde` est la pièce la plus utile, et elle remplace toutes les
spéculations sur les seeds.** Elle laisse le serveur créer un monde tout seul,
dans un répertoire jetable sur un port séparé, puis lit le `.fwl` qu'il écrit.
La version du générateur y est inscrite : si elle passe de 2 à autre chose, la
génération de monde a changé et aucune seed repérée avant la 1.0 ne donne plus
la même carte. C'est une mesure, pas une hypothèse — la documentation
communautaire, elle, n'a rien pu confirmer sur ce point.

La sonde prévient si des joueurs sont en jeu : un second serveur Unity prend un
cœur et quelques Go le temps de générer son monde, et au-delà de 150 ms de
latence les monstres se téléportent pour tout le monde. Le jour J elle passe
juste après la mise à jour, serveur vide.

**`--retour-arriere` s'appuie sur la branche `default_old`**, « previous
stable ». Avertissement inclus dans le script : un monde déjà ouvert par la
nouvelle version peut ne plus être lisible par l'ancienne.

**Deux pièges rencontrés en l'écrivant.**

Un motif `pgrep -f` finit par se reconnaître lui-même dans sa propre ligne de
commande : `pkill -f 'port 2466'` a tué le shell qui l'exécutait. La sonde
garde donc le PID retourné par `$!` au lieu de chercher son processus.

En `awk`, un saut de ligne entre le motif et l'accolade **termine la règle** :
`/motif/` seul déclenche l'action par défaut, qui est d'imprimer la ligne, et
le bloc suivant s'applique alors à toutes les lignes. L'audit affichait tout
en double.

---

### Succès Steam : une seule clé, mais des profils publics, le 2026-09-04

Les succès vivent dans le fichier de personnage, chez le joueur — le serveur ne
les verra jamais. La seule voie est l'API Web de Steam, et les quatre
identifiants Steam sont déjà en base, relevés dans le journal du serveur.

**Être amis sur Steam ne suffit pas.** L'API Web ne respecte pas la visibilité
« amis seulement » : elle ne répond que pour les profils **publics**, quelle
que soit la relation entre le détenteur de la clé et la personne interrogée.
Une seule clé d'API suffit donc pour tout le groupe, mais **chacun doit passer
« Détails du jeu » en Public** dans ses paramètres de confidentialité, sinon la
réponse est vide.

Rien d'autre n'en dépend : morts, sessions et progression des boss sont mesurés
côté serveur et ne demandent rien aux joueurs.

---

### KPI et objectifs, le 2026-09-04

Les indicateurs et leurs cibles vivent dans `/etc/valheim/objectifs.json`, pas
dans le code : les objectifs d'un groupe changent en cours de partie, et les
recompiler n'aurait pas de sens. Le fichier absent n'est pas une erreur — la
page affiche alors les statistiques brutes.

```bash
stats-valheim.py               # KPI, jalons et défis au terminal
stats-valheim.py --json        # même chose pour la page Cockpit
```

Affichés dans la page **Valheim — défis** en cartes avec jauge, et résumés
chaque jour à 19 h sur Discord — avant la session du soir, pour que le bilan
serve à se fixer un objectif plutôt qu'à constater après coup.

**Les jalons se mesurent en temps de jeu cumulé du groupe**, pas en calendrier.
Les sessions qui se chevauchent sont comptées plusieurs fois, et c'est voulu :
on mesure l'effort du groupe, pas la durée écoulée. Une semaine sans se
connecter ne doit pas dégrader un indicateur de progression.

**Trois pièges corrigés en écrivant ça, tous les trois des erreurs de sens
plutôt que de code.**

*Deux unités mélangées.* « Temps du dernier palier de boss » comparait un écart
de dates à un objectif exprimé en heures de jeu : 77 h affichées contre 25 h
visées, alors que le groupe n'avait joué que 29 h 56 entre les deux boss. Le
KPI est maintenant calculé en temps de jeu, comme les jalons.

*Un raid absent ne prouve rien.* Le jalon Eikthyr affichait « pas encore
vaincu » alors qu'Eikthyr était forcément tombé — l'Ancien et Bonemass l'étaient.
Son raid `army_eikthyr` ne s'était simplement jamais déclenché en 154 jours. Les
raids donnent donc une **borne inférieure** de la progression, et le libellé le
dit désormais : « aucun raid observé ». La source exacte serait les *global
keys* du fichier de monde, mais elles vivent dans un binaire de 14 Mo, sans
horodatage.

*Un meneur sur un défi que personne ne tient.* Le bilan Discord annonçait
« Intact depuis l'Ancien — en tête : DjOsE » alors que DjOsE avait deux morts :
il était seulement le moins mauvais. Quand un défi est binaire et que personne
ne le tient, le message le dit au lieu de désigner un vainqueur.

**Cloisonnement par monde.** Les requêtes filtrent sur le nom du monde, avec le
monde en cours par défaut (`--monde` pour un autre, `--tous-mondes` pour tout
additionner). Ce n'est pas cosmétique : à partir du 9 septembre, les événements
de `Midgard` et de `NordheimV1` cohabitent en base, et sans filtre les morts de
l'ancien monde compteraient dans les défis du nouveau.

**La jauge de la page Cockpit est un `<progress>`**, pas une `<div>` dont on
fixerait la largeur. La valeur est un attribut et non du style : rien ne dépend
alors de ce que la CSP autorise, et si la feuille de style ne chargeait pas, le
navigateur affiche quand même sa barre native. Après deux échecs silencieux dus
à cette CSP, autant choisir l'élément qui ne peut pas échouer.

---

### Rôles et chantiers de la feuille de Baby, le 2026-09-04

La feuille que Baby a préparée n'est pas un tableau de KPI : c'est une matrice
de **rôles** et de **chantiers de construction** par joueur. Transcrite dans
`/etc/valheim/chantiers.json` — dix fonctions, onze chantiers — libellés
d'origine conservés.

```bash
chantier-valheim.py liste
sudo chantier-valheim.py etat portails fait
sudo chantier-valheim.py qui "avant poste marais" Djoose
sudo chantier-valheim.py pseudo Lapin Brewtmoiminou
```

**Rien de tout cela n'est mesurable depuis le serveur.** Il ne voit ni la
cuisine, ni le bûcheronnage, ni un port achevé — ce sont des actions de jeu qui
vivent chez le client. Ces objectifs sont donc **déclaratifs**, tenus à la main,
et exposés sous une clé JSON distincte des KPI mesurés. La page Cockpit et le
bilan Discord le disent explicitement : un affichage ne doit pas pouvoir faire
passer un déclaratif pour une mesure.

C'est le point qui a orienté toute la réponse. Un tableau de bord qui
mélangerait « 19 morts » (compté par le serveur) et « armurerie construite »
(coché à la main) sans le dire perdrait toute valeur de preuve dès la première
contestation — or ce groupe se lance des défis, donc les chiffres doivent
pouvoir être opposés à quelqu'un.

Le fichier écrit par renommage atomique : une interruption ne doit pas laisser
une configuration tronquée que plus rien ne lirait.

**La correspondance des noms**, confirmée par Alexandre le 2026-09-04. La
feuille nomme les joueurs par leur surnom, le serveur ne connaît que les
pseudos en jeu, et rien ne les relie automatiquement :

| feuille | pseudo en jeu | Discord |
|---|---|---|
| Lapin | `Brewtmoiminou` | aixlelapin |
| Beny | `Beware` | BenXL |
| Djoose | `DjOsE` | Djoose |
| Baby | `Bab-y` | Baby |

`Djoose` et `Baby` étaient évidents ; `Lapin` et `Beny` se partageaient `Beware`
et `Brewtmoiminou` sans certitude. La question a été posée plutôt que tranchée
au feeling : toute l'attribution des KPI en dépendait, et une erreur aurait
attribué huit morts à la mauvaise personne.

---

### Bot Discord : lire le salon et exécuter les commandes, le 2026-09-04

Un webhook est à sens unique. Pour **lire** le salon il faut un bot, avec son
propre token et l'intent *Message Content*.

```bash
sudo systemctl enable --now lit-discord-valheim.timer     # un passage par minute
```

Le token va dans `/etc/valheim-discord.conf` à côté du webhook —
`TOKEN=`, `SALON=` (l'identifiant du salon), et `AUTORISES=` en option pour
restreindre les commandes à certains comptes.

**L'identifiant du salon n'a pas eu besoin d'être demandé** : le token permet
de lister les serveurs (`/users/@me/guilds`) puis leurs salons, et de trouver
`valheim` — `1542942710657454130`, le même que celui du webhook, vérifié en
interrogeant le webhook lui-même, qui renvoie son `channel_id`.

**Le salon `valheim` est privé, et c'est ce qui bloque.** Une surcharge y refuse
« voir le salon » à `@everyone` et l'accorde nommément à trois membres et un
rôle ; le bot n'en fait pas partie. Il lit `général`, `sw` et `jdr-bot` sans
problème — son rôle global est donc correct. Il faut l'ajouter aux permissions
de ce salon précis. Le script le dit maintenant explicitement dans le journal
plutôt que de laisser un `HTTP 403 code 50001` opaque. **Sans token, le script sort en
succès sans rien faire** : il peut donc être armé avant que le token existe.

**La distinction qui structure le programme.** Deux sortes de demandes :

| | Traitement |
|---|---|
| `!chantier`, `!qui`, `!objectif`, `!stats`, `!bilan`, `!chantiers`, `!aide` | exécutées par le code, réponse dans la minute |
| `!defi <idée>` | rangée en file d'attente — **Claude ne tourne pas en permanence** et la traitera à sa prochaine invocation |

C'est le point à ne pas maquiller : « on demande dans le salon et Claude
répond » ne peut être immédiat que pour ce qu'un script sait faire seul. Le
reste attend un humain ou une invocation programmée, et le bot le dit
explicitement en accusant réception.

**Le contenu des messages est traité comme une donnée, jamais comme une
commande.** Aucun shell n'est invoqué : les sous-processus reçoivent des listes
d'arguments, et chaque commande est reconnue par une grammaire fermée. Le
service tourne sous l'utilisateur `valheim` avec `ProtectSystem=strict` et
`ReadWritePaths=/etc/valheim` — les deux seuls fichiers qu'il peut modifier.

**Permissions.** `/etc/valheim/` est passé en `775 root:valheim` et ses deux
JSON en `664` : le bot et la CLI tournent sous `valheim` et doivent les écrire.
Ils ne contiennent aucun secret. Le secret, lui, reste dans
`/etc/valheim-discord.conf` en `640 root:valheim`, que le bot lit sans pouvoir
le modifier.

**Le rapprochement des noms tolère l'orthographe.** Les libellés sont ceux de
la feuille de Baby — « Armurie », pas « armurerie » — et personne ne tapera son
orthographe. `chantier-valheim.py` tente le fragment exact, puis un
rapprochement approximatif via `difflib`, en ignorant les accents. Et il
n'accepte le résultat que s'il désigne **une seule** entrée : `!chantier port
fait` répond « correspond à 3 entrées » plutôt que de cocher au hasard.

**Le premier passage se cale sur le présent** sans rejouer l'historique du
salon, qui rejouerait d'anciennes commandes.

Seuls les messages commençant par `!` sont conservés. Le reste de vos
conversations n'est pas stocké — c'est le minimum nécessaire pour ce qui a été
demandé, et ça se change si vous voulez que je lise le contexte.

---

### Détection automatique de la sortie de la 1.0, le 2026-09-04

```bash
sudo systemctl enable --now guette-valheim-1.0.timer      # un contrôle par quart d'heure
```

`jour-j-valheim.sh --controle` compare le buildid publié au buildid installé et
annonce sur Discord **la première fois** qu'ils divergent. Un marqueur dans
`/var/lib/valheim-stats/` évite de réannoncer la même sortie tous les quarts
d'heure. `Persistent=true` : si la machine était éteinte à l'heure du contrôle,
il a lieu au démarrage suivant.

**Passée en chaîne complète le 2026-09-04, à la demande.** La minuterie
exécute maintenant `--automatique --confirm` : mise à jour, sonde, puis monde
`NordheimV1` avec une **seed tirée au hasard**, et une annonce Discord à chaque
étape. L'argument qui justifiait de garder la main — la sonde peut révéler que
la génération de monde a changé — tombe dès lors que la seed est aléatoire :
aucune carte repérée d'avance n'est en jeu.

**Trois garde-fous, parce que personne ne lira la sortie au moment où elle
passe :**

*Une barrière de date.* La chaîne ne fait rien avant le `2026-09-09` ; avant,
elle se contente de prévenir. Sans cette barrière, **un simple correctif publié
par Iron Gate d'ici là suffirait à archiver la partie en cours** — le buildid
aurait changé, et la chaîne aurait conclu à la sortie de la 1.0.

*Un monde déjà là arrête tout.* Si `NordheimV1.fwl` existe, la bascule a déjà
eu lieu et la chaîne ne recommence pas.

*Chaque échec s'arrête et le dit.* Si la mise à jour échoue, le monde n'est pas
touché et Discord l'annonce. Si la sonde échoue, la version du générateur est
inconnue, donc **le monde neuf n'est pas créé** — écrire un `.fwl` avec la
mauvaise valeur produirait un `LoadError` dont le message parlerait de seed
alors que le problème serait ailleurs.

**Deux bugs corrigés en écrivant cette chaîne**, tous deux invisibles en
lecture :

`action_sonde` effaçait le répertoire jetable que `action_monde` lisait ensuite
pour connaître la version du générateur. `--tout` retombait donc silencieusement
sur la valeur par défaut. Le résultat est maintenant écrit hors du répertoire,
dans `/var/lib/valheim-stats/generateur-sonde`.

Le message d'échec de la mise à jour utilisait `$ACTUEL`, variable qui
n'appartient qu'à l'autre script. Sous `set -u`, la chaîne aurait planté **au
moment précis où elle annonce une erreur**. Le nom du monde est désormais relu
depuis `/etc/valheim.env`.

**La seed annoncée est relue dans le fichier créé**, et non recopiée depuis les
arguments : sans `--seed` elle est tirée au hasard, et c'est cette valeur-là
qu'il faut publier pour que le groupe puisse regarder la carte.

---

### La progression était fausse d'un boss, le 2026-09-04

**L'erreur.** La progression était déduite du nom des raids : `army_theelder`
était lu comme « l'Ancien est vaincu ». C'est faux. **Un raid est débloqué par
le boss précédent, pas par celui dont il porte le nom** — `army_theelder` exige
`defeated_eikthyr`, `army_bonemass` exige `defeated_gdking`. Toute la lecture
était donc décalée d'un cran, et le défi de Bab-y comptait les morts à partir
d'une date trop précoce.

**Comment elle a été trouvée.** En cherchant les *global keys* dans le fichier
de monde : `defeated_eikthyr` et `defeated_gdking` présentes, `defeated_bonemass`
**absente** — alors que `army_bonemass` s'était déclenché le 1er septembre.
L'incohérence ne laissait qu'une explication. Confirmé ensuite par le
[wiki des événements](https://valheim.fandom.com/wiki/Events).

Conséquence concrète : **Bonemass n'est pas vaincu**, contrairement à ce que la
page affichait depuis le début.

**La source exacte.** `cles-monde-valheim.py`, toutes les 5 minutes :

```bash
cles-monde-valheim.py            # relève et annonce les nouvelles clés
cles-monde-valheim.py --liste    # l'état
```

Le fichier fait 14 Mo et son format complet exige de parcourir tous les ZDO. On
ne le parcourt pas : on cherche les chaînes connues sous leur **forme Unity**,
un octet de longueur suivi du texte. Vérifié sur le monde en place — chaque clé
présente apparaît exactement une fois, à 97,7 % du fichier, là où vivent les
global keys.

**On lit `.db.old`, pas `.db`.** La sauvegarde précédente est complète par
construction, alors que le fichier actif peut être en cours d'écriture — 14 Mo
ne s'écrivent pas instantanément. Le retard vaut au plus un intervalle de
sauvegarde, dix minutes, sans conséquence pour détecter la chute d'un boss.

**Les clés n'ont pas d'horodatage**, d'où la routine : en relevant
régulièrement, on date le passage d'absente à présente. Ce qui était déjà là au
premier relevé est marqué **incertain**, et la date affichée devient alors la
meilleure borne haute disponible — le premier raid qui exigeait cette clé.
L'affichage distingue « vaincu **le** » de « vaincu **avant le** » : dire le
premier quand on ne sait que le second serait une précision inventée.

---

### Le caillou de Benny, et ce qu'un serveur ne peut pas voir, le 2026-09-04

Demande reçue par `!defi trouver le caillou rare`. Il s'agit du **trophée de
Golem de pierre**, le trophée au plus faible taux de chute du jeu.

**Non mesurable côté serveur, vérifié et non supposé :**

- le journal du serveur ne contient **aucune** mention d'objet — zéro
  occurrence sur `trophy|item|loot|pickup|inventory` ;
- le fichier de monde range les objets par **empreinte numérique**, pas par
  nom : `TrophyStoneGolem` n'y apparaît nulle part en clair ;
- et surtout, **un objet dans un sac n'est pas dans le monde** : il vit dans le
  `.fch` du joueur, sur sa machine, que le serveur ne reçoit jamais.

Suivi en déclaratif, donc, comme les chantiers. **Avec des alias** :
`chantier-valheim.py` cherche une entrée par les mots qu'on emploie pour elle
et non par son libellé officiel — Benny dira « caillou », pas « trophée de
Golem de pierre ». Le rapprochement porte sur le nom **et** sur les alias,
tolère les accents et l'orthographe, et refuse toujours une correspondance
multiple.

---

### Adresse IP fixée en statique, le 2026-09-04

L'adresse `192.168.1.120` venait du DHCP de la box et n'était pas réservée.
Cockpit, lui, écoute sur cette adresse en dur (`ListenStream=192.168.1.120:9090`),
et la redirection de ports du jeu la désigne aussi. Le jour où la box aurait
attribué autre chose, le service aurait démarré sans être joignable — le socket
a `FreeBind=yes`, donc il se lie quand même à une adresse absente, et l'échec
serait resté silencieux.

La connexion filaire est passée en manuel sur la même adresse, pour ne rien
casser d'autre :

```bash
UUID=$(nmcli -g UUID,DEVICE -t connection show --active | grep enp0s31f6 | cut -d: -f1)
sudo nmcli connection modify "$UUID" \
  ipv4.method manual \
  ipv4.addresses 192.168.1.120/24 \
  ipv4.gateway 192.168.1.254 \
  ipv4.dns 192.168.1.254 \
  ipv4.dns-search lan
sudo nmcli device reapply enp0s31f6
```

**`device reapply`, pas `connection up`.** L'adresse ne changeant pas, `reapply`
reconfigure l'interface sans la désactiver : les sessions en cours — dont la
console web Cockpit par laquelle passait l'opération — survivent. Un
`connection up` aurait coupé le lien.

**Cette machine est sans écran : la manipulation a été faite sous filet.** Un
minuteur transitoire armé avant de toucher au réseau remettait le DHCP
automatiquement, désarmé seulement après vérification de la passerelle, du DNS
et de Cockpit :

```bash
sudo systemd-run --unit=net-rollback --on-active=300 /var/tmp/net-rollback.sh
# ... modification, puis vérifications ...
sudo systemctl stop net-rollback.timer
```

**Où la configuration est réellement écrite.** Pop!_OS fait passer
NetworkManager par netplan : la connexion filaire n'a **pas** de fichier dans
`/etc/NetworkManager/system-connections/`, elle est décrite dans
`/etc/netplan/90-NM-<uuid>.yaml` et le keyfile est régénéré dans
`/run/NetworkManager/` à chaque démarrage. Chercher au premier endroit laisse
croire que `nmcli` n'a rien persisté. La passerelle est stockée en deuxième
champ de `ipv4.address1` (`192.168.1.120/24,192.168.1.254`), pas dans une clé à
elle. Vérification que le démarrage reproduira bien l'état courant :

```bash
sudo netplan generate   # le keyfile de /run doit rester identique
```

**Ce qui reste dépendant de la box.** `.120` est probablement *dans* la plage
DHCP (passerelle en `.254`, domaine `lan`). Rien n'empêche donc la box de louer
`.120` à un autre appareil pendant que le serveur est éteint, et le conflit
d'adresses ferait tomber les deux. Le statique côté serveur ne se substitue pas
à une **réservation dans l'interface de la box** — à faire pour être vraiment
tranquille, ou à défaut déplacer le serveur hors de la plage.

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
