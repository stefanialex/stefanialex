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

*Mis à jour le 2026-08-12. Rien de tout ceci n'est déductible du dépôt :
`rapport-audit.md` est ignoré par git et les scripts ne laissent pas de trace
versionnée. D'où cette section.*

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
- **Open WebUI** en conteneur Docker, port 8080.
- **LM Studio** 0.4.21, moteur `llama.cpp-linux-x86_64-nvidia-cuda-avx2` 2.28.2,
  modèles dans `/srv/ia/lmstudio` : Qwen3.5 9B (multimodal), Qwen2.5-Coder 7B,
  Gemma 3 4B (multimodal), tous en `Q4_K_M`.
- **Mesuré** le 2026-08-12 : Gemma 3 4B en contexte 8192 charge en 3,0 s, occupe
  4168 Mio de VRAM (donc entièrement sur le GPU) et produit 42 jetons/seconde.

### Points ouverts, à traiter avant d'aller plus loin

1. **Docker court-circuite `ufw`.** Ses règles s'insèrent dans `FORWARD` avant
   celles d'ufw : la restriction « 8080 depuis `192.168.1.0/24` seulement » ne
   protège donc pas le conteneur Open WebUI. Sans redirection sur la box la
   portée reste le réseau local, mais c'est à corriger avant toute ouverture
   vers l'extérieur.
2. **`openssh-server` n'est pas installé** — toute l'administration se fait
   devant la machine.
3. **LM Studio :** le garde-fou `modelLoadingGuardrails` est en mode `high` et
   peut refuser un chargement que la VRAM permettrait ; et le contexte par
   défaut de Qwen3.5 (262 000 jetons) dépasse de loin la VRAM — rester entre
   8 000 et 16 000.
4. **`sudo` est inutilisable sans terminal** sur cette machine (il exige un tty
   pour le mot de passe). Pour toute commande privilégiée lancée depuis un
   contexte non interactif, passer par `pkexec`, qui s'appuie sur l'agent polkit
   de COSMIC — en pensant à repasser les variables d'environnement, que `pkexec`
   réinitialise.

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
| Minecraft | `<ip-du-pc>:25565` | |
| Valheim | `<ip-du-pc>:2456` | |

Les ports ne sont ouverts **que pour le réseau local**. Aucun service n'est
exposé sur Internet : l'API Ollama n'a pas d'authentification, et une API de
modèle ouverte au monde est utilisée par des tiers en quelques heures.

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
