# Désinstaller la pile IA locale

À faire si l'inférence est déplacée sur une autre machine et qu'on veut rendre
la RAM et le disque au reste du serveur.

Les scripts `03-ia.sh` et la documentation associée restent dans le dépôt : ils
serviront tels quels sur la machine de destination.

---

## Étape 1 — Faire l'inventaire avant de supprimer

**Ne saute pas cette étape.** Elle dit ce qui est réellement installé, et évite
de supprimer un conteneur Docker qui n'a rien à voir avec l'IA.

```bash
echo "=== Ollama ==="
systemctl status ollama --no-pager 2>&1 | head -3
which ollama

echo "=== Conteneurs Docker ==="
docker ps -a

echo "=== Images Docker ==="
docker images

echo "=== LM Studio ==="
ls -l /opt/lmstudio 2>/dev/null

echo "=== Place occupée ==="
du -sh /srv/ia 2>/dev/null
```

Note ce qui répond et ce qui ne répond pas : tu ne feras que les étapes
correspondantes.

---

## Étape 2 — Open WebUI

**Ne supprime que le conteneur `open-webui`.** S'il y en a d'autres dans
`docker ps -a`, ils ne concernent pas l'IA : laisse-les.

```bash
docker stop open-webui
docker rm open-webui
docker rmi ghcr.io/open-webui/open-webui:main
```

Les conversations et les comptes vivent dans un volume séparé, qui survit à la
suppression du conteneur. À effacer seulement si tu n'en veux plus :

```bash
sudo rm -rf /srv/ia/openwebui
```

> N'utilise **pas** `docker system prune -a` : cette commande supprime toutes
> les images inutilisées de la machine, y compris celles de tes autres
> conteneurs.

---

## Étape 3 — Ollama et les modèles

C'est ce qui libère le plus de place : chaque modèle pèse de 5 à 45 Gio.

```bash
sudo systemctl stop ollama
sudo systemctl disable ollama

sudo rm -f /etc/systemd/system/ollama.service
sudo rm -rf /etc/systemd/system/ollama.service.d
sudo systemctl daemon-reload

sudo rm -f "$(which ollama)"
sudo rm -rf /usr/share/ollama
sudo rm -rf /srv/ia/ollama

sudo userdel ollama 2>/dev/null
sudo groupdel ollama 2>/dev/null
```

---

## Étape 4 — LM Studio

```bash
sudo rm -rf /opt/lmstudio
sudo rm -f /usr/share/applications/lmstudio.desktop
sudo rm -rf /srv/ia/lmstudio
```

---

## Étape 5 — Nettoyer les traces

Le pare-feu garde les règles ouvertes pour les ports de l'IA. À refermer :

```bash
sudo ufw status numbered          # repérer les lignes 11434 et 8080
sudo ufw delete <numéro>          # supprimer une par une, en partant du plus grand numéro
```

Les numéros se décalent après chaque suppression : commence par le plus grand.

Puis le dossier de données, s'il est vide :

```bash
ls -la /srv/ia
sudo rmdir /srv/ia 2>/dev/null
```

---

## Étape 6 — Docker

À supprimer **seulement** si `docker ps -a` est vide, c'est-à-dire si Docker
n'avait été installé que pour Open WebUI.

```bash
docker ps -a                      # doit ne rien lister
sudo systemctl stop docker
sudo systemctl disable docker
sudo apt purge -y docker.io
sudo apt autoremove -y
sudo rm -rf /var/lib/docker
```

Si d'autres conteneurs apparaissent, **arrête-toi ici** : Docker sert à autre
chose sur cette machine.

---

## Vérification

```bash
systemctl status ollama 2>&1 | head -2     # doit dire « could not be found »
docker ps -a                                # plus de conteneur open-webui
df -h /                                     # la place récupérée
free -h                                     # la RAM rendue
```
