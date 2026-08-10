# Comprendre le matériel

Comment lire le rapport produit par `00-audit.sh`, et quoi en conclure.

---

## Les quatre chiffres qui comptent

### 1. La VRAM (mémoire de la carte graphique)

C'est **le** facteur déterminant. Un modèle qui tient entièrement dans la VRAM
répond en quelques secondes ; le même modèle qui déborde en RAM répond dix à
cinquante fois plus lentement.

| VRAM | Ce qui devient possible |
|---|---|
| aucune | Inférence sur CPU uniquement, lente mais utilisable en 7–8B |
| 6–8 Gio | Modèles 7–8B quantifiés, confortable |
| 12–16 Gio | Modèles 14B, nettement meilleurs en raisonnement |
| 24 Gio et + | Modèles 32B, proches de ce qu'on attend d'un assistant sérieux |

### 2. La RAM

Sans GPU, c'est elle qui plafonne la taille de modèle. Compte environ la moitié
de la RAM installée comme budget réellement utilisable : le système, le cache
disque et les autres services occupent le reste.

Elle compte aussi pour la cohabitation avec un serveur de jeu — un serveur
Minecraft familial réclame 4 Gio à lui seul.

### 3. AVX2

Un jeu d'instructions du processeur. Présent sur tout ce qui est postérieur à
2013 environ. **Absent, l'inférence CPU tombe sous le token par seconde**, ce
qui rend l'usage conversationnel impraticable — un GPU devient alors obligatoire,
pas optionnel.

### 4. La santé des disques (SMART)

Dans la sortie `smartctl` de chaque disque, deux lignes méritent un regard :

- `Power_On_Hours` — au-delà de 40 000 heures sur un disque mécanique, la fin
  de vie approche.
- `Reallocated_Sector_Ct` — toute valeur non nulle et qui **augmente** annonce
  une panne. Ne mets rien d'important sur ce disque.

Un `SMART overall-health self-assessment test result: PASSED` ne garantit rien
à lui seul : un disque peut passer le test la veille de mourir. Les sauvegardes
restent nécessaires.

---

## Faut-il réinstaller Pop!_OS complètement ?

`01-disques.sh` ne formate **jamais** le disque système : c'est techniquement
impossible pendant que le système tourne dessus, et le script refuse même de le
cibler.

Sur une installation fraîche comme la tienne, une réinstallation n'apporte rien.
Elle ne se justifie que dans deux cas :

- Le disque système est un disque mécanique et tu veux passer sur un SSD.
- Le partitionnement actuel est inadapté (partition racine trop petite).

Dans ce cas, la marche à suivre :

1. Créer une clé USB avec l'image Pop!_OS depuis <https://pop.system76.com/>.
   Prendre l'image **NVIDIA** si la machine a une carte NVIDIA — les pilotes
   propriétaires sont alors inclus, ce qui évite bien des ennuis.
2. Démarrer dessus, choisir « Custom (Advanced) » au partitionnement.
3. Partitionnement recommandé pour un serveur :

   | Partition | Taille | Format | Point de montage |
   |---|---|---|---|
   | EFI | 512 Mio | fat32 | `/boot/efi` |
   | racine | 100 Gio minimum | ext4 | `/` |
   | reste | tout le reste | ext4 | non monté, `01-disques.sh` s'en occupe |

   100 Gio pour la racine peut sembler large : Docker, les images de conteneurs
   et les paquets s'accumulent vite. Les modèles, eux, iront sur `/srv/ia`.

4. Ne pas activer le chiffrement complet du disque. Il impose de saisir une
   phrase de passe à chaque démarrage, ce qui est incompatible avec un serveur
   censé redémarrer seul après une coupure de courant.

---

## Qu'améliorer sur la machine

Par ordre de rentabilité pour un serveur IA :

1. **Une carte graphique NVIDIA d'occasion.** Rien d'autre n'a autant d'effet.
   Une carte de 12 Gio de VRAM fait passer d'« inutilisable » à « agréable ».
   Vérifier avant achat : la longueur de la carte contre le boîtier, les
   connecteurs d'alimentation disponibles, et la puissance de l'alimentation
   (compter 550 W minimum pour une carte de milieu de gamme).
2. **De la RAM.** Le rapport indique les slots libres et le type de barrettes.
   Passer de 16 à 32 Gio permet de faire tourner l'IA et un serveur de jeu
   simultanément sans arbitrage.
3. **Un SSD pour le système**, si ce n'est pas déjà le cas. N'accélère pas
   l'inférence, mais rend la machine agréable à administrer.
4. **Un câble Ethernet.** Si le rapport signale une connexion Wi-Fi, c'est le
   changement le moins cher de la liste. Un serveur de jeu en Wi-Fi, ce sont
   des micro-coupures que tous les joueurs subissent.

---

## Pourquoi ext4 et pas autre chose

`01-disques.sh` formate en ext4 par défaut. C'est le système de fichiers le
mieux éprouvé sous Linux, réparable avec des outils que tout le monde connaît,
et sans surprise de comportement.

XFS est disponible via `SYSTEME_FICHIERS=xfs` et se défend mieux sur de très
gros volumes avec de gros fichiers — ce qui décrit assez bien un stockage de
modèles. Le gain reste marginal à cette échelle.

Btrfs et ZFS offrent des instantanés très pratiques, mais demandent une
administration qu'il faut vouloir assumer. Ils ne sont pas proposés ici.
