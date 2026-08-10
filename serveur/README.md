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
