# Le 9 septembre 2026 : Valheim 1.0, monde neuf `NordheimV1`

Mode opératoire à suivre dans l'ordre. Tout est déjà installé et testé ; ce
document ne contient que ce qu'il reste à taper.

Rappel du contexte qui décide de la marche à suivre : il n'existe **aucune
branche de test public** pour le serveur dédié — vérifié en listant les
branches Steam de l'app 896660. Personne ne peut voir la 1.0 avant le 9, ni
tester une seed à l'avance. D'où la sonde, plus bas.

---

## Avant le jour J

À faire une fois, quand vous voulez.

**1. Chacun passe « Détails du jeu » en Public** dans ses paramètres de
confidentialité Steam. Sans ça, pas de suivi des succès — et la 1.0 en ajoute
plus de cinquante, comptabilisés à partir de l'installation, donc rien de
rétroactif : tout se joue sur `NordheimV1`.

Être amis sur Steam ne suffit pas : l'API Web ne respecte pas la visibilité
« amis seulement ». Une seule clé d'API, celle d'Alexandre, couvre le groupe.

**2. L'adresse du webhook Discord**, si ce n'est pas déjà fait :

```bash
sudo sh -c 'echo "WEBHOOK=<adresse>" >> /etc/valheim-discord.conf'
```

**3. Vérifier que tout est prêt :**

```bash
jour-j-valheim.sh --verifier
```

Doit finir par `prêt.` Les points à surveiller : place sur `/srv/jeux` au
moins 10 Go, au moins une archive de moins de 24 h, Discord configuré.

---

## Le jour J

### 1. Guetter la publication

```bash
jour-j-valheim.sh --attendre
```

Compare le buildid de la branche `public` au buildid installé, toutes les cinq
minutes, et annonce sur Discord dès qu'il change. Laisser tourner dans un
terminal, ou en tâche de fond :

```bash
sudo systemd-run --unit=guette-1.0 /usr/local/bin/jour-j-valheim.sh --attendre
journalctl -u guette-1.0 -f
```

Le paquet serveur dédié peut sortir un peu après le client : si les joueurs ont
déjà la 1.0 et que le serveur non, ils verront un refus de version et le
journal du serveur écrira `Network version check, their:X, mine:Y` avec deux
nombres différents.

### 2. Mettre à jour

```bash
sudo jour-j-valheim.sh --maj --confirm
```

Sauvegarde vérifiée sur trois disques → arrêt propre → `app_update 896660
validate` → redémarrage → attente de la ligne `Load world` dans le journal.
Annonce Discord au début et à la fin.

Si le serveur ne redémarre pas :

```bash
sudo jour-j-valheim.sh --retour-arriere --confirm
```

Réinstalle la branche `default_old`. **Attention :** un monde déjà ouvert par
la 1.0 peut ne plus être lisible par l'ancienne version. Les archives sont dans
`/srv/jeux/sauvegardes`.

### 3. Mesurer ce que la 1.0 change — l'étape qui décide de la seed

```bash
sudo jour-j-valheim.sh --sonde --confirm
```

Laisse le serveur créer un monde jetable sur le port 2466 et lit le `.fwl`
produit. Deux issues, et une seule question à trancher :

| La sonde dit | Ce que ça veut dire | Quelle seed |
|---|---|---|
| générateur **inchangé** (2) | la même seed donne la même carte qu'avant la 1.0 | `HHcLC5acQt` — recommandée sans interruption depuis 2021, la plus éprouvée dans le temps |
| générateur **changé** | aucune seed repérée avant la 1.0 ne vaut plus rien | choisir sur place : [valheim-map.world](https://valheim-map.world/) une fois l'outil à jour, ou un monde solo jetable en `debugmode` pour survoler le spawn |

Ce qu'on regarde dans une seed candidate : Eikthyr à moins de 300 m, l'Ancien
sous 1,5 km, Bonemass sous 2 km, Haldor le marchand proche, et surtout Plaines
et Mistlands accessibles sans épopée maritime. À éviter : spawn sur un îlot
sans Forêt Noire adjacente, donc sans cuivre à pied.

### 4. Créer le monde

```bash
sudo jour-j-valheim.sh --monde --nom NordheimV1 --seed HHcLC5acQt --confirm
```

Ajouter `--force` si des joueurs se sont reconnectés entre-temps.

Enchaîne : sauvegarde → arrêt → archivage de `Midgard` dans
`donnees/anciens-mondes/` → fabrication du `.fwl` avec la seed → bascule de
`NOM_MONDE` → redémarrage → **preuve dans le journal**, la ligne
`Load world: NordheimV1`. Annonce Discord.

Si le serveur refuse le fichier (`LoadError`), c'est que la version du
générateur inscrite ne convient pas : relire la sortie de la sonde et relancer
avec `--generateur N`. `Midgard` reste intact dans `anciens-mondes/` pendant
tout ce temps.

Les trois étapes d'un coup, si tout va bien :

```bash
sudo jour-j-valheim.sh --tout --nom NordheimV1 --seed HHcLC5acQt --confirm
```

### 5. Chacun crée un personnage neuf

Le fichier de personnage vit chez le joueur, le serveur n'y touche jamais. Les
compteurs de défis repartent donc de zéro tout seuls : la base des statistiques
étiquette les événements par nom de monde, `Midgard` d'un côté, `NordheimV1` de
l'autre.

---

## Après

```bash
stats-valheim.py            # au terminal
```

Ou la page **Valheim — défis** dans Cockpit.

Le défi de Bab-y — n'être jamais mort après avoir battu l'Ancien — se remet en
jeu automatiquement dès que le premier raid `army_theelder` apparaît dans le
journal du monde neuf. Sur `Midgard`, personne ne l'avait tenu.

Repères pour se fixer des objectifs, avec quatre joueurs : Eikthyr dans la
première session, l'Ancien sous 10 h cumulées, Bonemass autour de 20 h, Moder
vers 40 h. Pour situer : un run solo optimisé boucle Eikthyr → la Reine en
6 h 40, et le format officiel Trial of Tyr a été gagné en 7 h 54 sans mourir.
