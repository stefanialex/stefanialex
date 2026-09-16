# Auto-hébergement du banc d'essai

Sert le prototype et **collecte les rapports d'incident tout seul**. Aucune dépendance :
uniquement les modules fournis avec Node 18 ou plus.

Quand le jeu est servi par ce serveur, il détecte qu'il est chez nous et poste le
rapport automatiquement — le testeur n'a plus rien à copier-coller. Sur claude.ai,
l'appel échoue sans bruit et le copier-coller reste disponible. Le même fichier HTML
fonctionne dans les deux cas, sans version séparée à maintenir.

## Démarrer

```sh
cd prototypes/serveur
PORT=8787 CLE=choisis-un-mot-de-passe node serveur.js
```

- le jeu : `http://localhost:8787/`
- les résultats : `http://localhost:8787/rapports?cle=choisis-un-mot-de-passe`
- les données brutes : `/rapports.jsonl?cle=...` (une ligne JSON par rapport)

Les rapports sont écrits dans `rapports.jsonl`, à côté du script. Ce fichier n'est
pas versionné : c'est de la donnée de test, pas du code.

## Poster automatiquement dans Discord

Dans le salon : **Paramètres du salon → Intégrations → Webhooks → Nouveau webhook**,
puis copier l'URL.

```sh
DISCORD_WEBHOOK='https://discord.com/api/webhooks/...' \
PORT=8787 CLE=... node serveur.js
```

Chaque rapport arrive dans le salon, mis en forme, signé « Service des Donjons ».
C'est la boucle complète : un pote joue, le salon reçoit le rapport, personne n'a
rien à faire.

## Exposer le Mac mini sans ouvrir de port

**Ne redirige pas de port sur ta box.** Un tunnel sortant fait le travail, sans
ouvrir quoi que ce soit sur ton réseau domestique, et fournit le HTTPS :

```sh
brew install cloudflared
cloudflared tunnel --url http://localhost:8787
```

La commande affiche une URL en `https://…trycloudflare.com` : c'est le lien à
envoyer. Elle change à chaque redémarrage — pour une adresse stable, il faut un
compte Cloudflare et un tunnel nommé, mais pour une soirée de tests l'URL
temporaire suffit largement.

`ngrok http 8787` fait la même chose si tu l'as déjà installé.

## Garder le Mac éveillé

```sh
caffeinate -s node serveur.js
```

Ou **Réglages Système → Batterie / Économiseur d'énergie → empêcher la mise en veille
automatique**. Un Mac mini en veille, c'est un lien mort au milieu de la soirée.

## Le laisser tourner en permanence

Le plus simple, si tu as déjà `pm2` pour Belzebrew :

```sh
pm2 start serveur.js --name banc-essai --env PORT=8787 --env CLE=...
pm2 save
```

Sinon un `launchd` classique dans `~/Library/LaunchAgents/`.

## Ce que le serveur accepte, et rien d'autre

| Route | Méthode | Accès |
|---|---|---|
| `/` | GET | public — la page du jeu |
| `/rapport` | POST | public, JSON, 32 Ko maximum, 20 envois par minute et par IP |
| `/rapports` | GET | clé obligatoire |
| `/rapports.jsonl` | GET | clé obligatoire |
| tout le reste | — | 404 |

Aucun fichier n'est servi depuis le disque en dehors du HTML du jeu : pas de
traversée de répertoire possible. Sans `CLE` définie, la page des résultats reste
fermée.

## Limites assumées

C'est un serveur de test, pas de production. Il n'y a ni authentification des
testeurs, ni chiffrement au repos, ni sauvegarde : n'y mets rien que tu ne
publierais pas. Pour une soirée avec des amis, c'est exactement le bon niveau.
