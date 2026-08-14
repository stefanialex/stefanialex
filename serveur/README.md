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

*Mis à jour le 2026-08-14 (SSH passé en clé uniquement). Rien de tout
ceci n'est déductible du dépôt : `rapport-audit.md` est ignoré par git et les
scripts ne laissent pas de trace versionnée. D'où cette section.*

| Étape | État | Détail |
|---|---|---|
| 0 — audit | ✅ | Rejoué après l'installation du pilote, la synthèse est fiable |
| 1 — disques | ✅ | `sdb1` → `/srv/ia` (916 Gio), `sdc1` → `/srv/jeux` (146 Gio), ext4, `fstab` par UUID, remontage vérifié après redémarrage |
| 2 — pilotes | ✅ | `nvidia-driver-580` (580.173.02, CUDA 13.0), GTX 1070 et ses 8 Gio de VRAM reconnues |
| 3 — pile IA | ✅ | Voir ci-dessous |
| 4 — jeux | ⬜ | Pas commencée. `/srv/jeux` est vide, aucune unité `minecraft`/`valheim` |

Détail de l'étape 3 :

- **Ollama** 0.32.7, service actif, API sur `*:11434`, modèles dans
  `/srv/ia/ollama` : `hermes3:8b` et `nomic-embed-text`, à 100 % sur le GPU.
- **Open WebUI** en conteneur Docker, port 8080. Il voit bien les modèles
  d'Ollama depuis le 2026-08-12 — ce n'était pas le cas avant, voir le point 2.
- **LM Studio** 0.4.21, moteur `llama.cpp-linux-x86_64-nvidia-cuda-avx2` 2.28.2,
  modèles dans `/srv/ia/lmstudio` : Qwen3.5 9B (multimodal), Qwen2.5-Coder 7B,
  Gemma 3 4B (multimodal), tous en `Q4_K_M`.
- **Mesuré** le 2026-08-12 : Gemma 3 4B en contexte 8192 charge en 3,0 s, occupe
  4168 Mio de VRAM (donc entièrement sur le GPU) et produit 42 jetons/seconde.
  Débit d'`hermes3:8b` sur Ollama, mesuré le même jour : 36,5 jetons/seconde.

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

**`sudo` est inutilisable sans terminal** : il exige un tty pour son mot de
passe. Toute commande privilégiée lancée depuis un contexte non interactif doit
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

### À trancher au début de l'étape 4

`04-jeux.sh` ouvre les ports de jeu sans restriction de provenance
(`ufw allow 25565/tcp`, `ufw allow 2456:2458/udp`), alors que le tableau plus bas
affirme que rien n'est exposé au-delà du réseau local. Les deux ne peuvent pas
être vrais en même temps. Jouer avec des gens hors de la maison suppose une
exposition assumée ; sinon il faut restreindre ces règles comme les autres. Rien
n'a été modifié : c'est un choix d'usage, pas un bug à corriger d'office.

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

| Service | Adresse | Remarque |
|---|---|---|
| Interface de chat (Open WebUI) | `http://<ip-du-pc>:8080` | Depuis n'importe quel appareil du réseau |
| API Ollama | `http://<ip-du-pc>:11434` | Compatible avec le format d'API OpenAI |
| LM Studio | application de bureau | Nécessite un écran branché |
| API LM Studio | `http://127.0.0.1:1234` | Format OpenAI. Machine locale seulement, sauf activation explicite dans l'application |
| Administration à distance | `ssh <toi>@<ip-du-pc>` | IPv4 et réseau local uniquement |
| Minecraft | `<ip-du-pc>:25565` | Voir la réserve sur la provenance, plus haut |
| Valheim | `<ip-du-pc>:2456` | Idem |

Les ports des services d'IA et de SSH ne sont ouverts **que pour le réseau
local**, en IPv4 comme en IPv6, y compris pour ce qui tourne en conteneur.
Aucun n'est exposé sur Internet : l'API Ollama n'a pas d'authentification, et
une API de modèle ouverte au monde est utilisée par des tiers en quelques heures.

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
