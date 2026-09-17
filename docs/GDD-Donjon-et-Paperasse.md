# DONJON & PAPERASSE
### *Sous-sol, sous-effectif.*

**Game Design Document — Concept v0.9**
Roguelite tactique au tour par tour · Gestion de campement · Comédie narrative
Public : PC (Steam) puis Switch · Runs de 25–40 min · Prix cible 19,99 €

---

## PIÈCE N°1 — PITCH

Quatre incapables notoires sont envoyés vider un donjon en ruine parce que le seigneur du coin attend sa belle-mère dans trois semaines et que « ça fait désordre depuis la salle à manger ». Entre des gobelins syndiqués en préavis de grève, des pièges hors service depuis 1214 et un marchand qui facture le devis, la vraie menace n'est pas le donjon : c'est que l'équipe ne se supporte pas. **Donjon & Paperasse** est un roguelite tactique où l'on perd rarement à cause des monstres, et très souvent à cause d'une remarque de trop.

### Les quatre piliers

1. **La blague est une mécanique, pas un habillage.** Chaque gag structurant a une conséquence chiffrée : les gobelins en grève arrêtent vraiment de taper, le formulaire D-12 supprime vraiment un boss.
2. **L'échec doit être racontable.** On ne meurt pas d'un mauvais jet, on meurt d'une dispute sur la répartition des rations. Le joueur doit pouvoir raconter sa défaite à quelqu'un d'autre.
3. **Le groupe est l'ennemi principal.** L'IA adverse est médiocre et le sait. La pression vient de l'intérieur de la formation.
4. **Tout est administratif.** La magie a un formulaire. La mort a un formulaire. Le formulaire a un formulaire.

---

## PIÈCE N°2 — TON & ÉCRITURE

### Registre
Anachronismes assumés (jargon RH, droit du travail, immobilier, médecine du travail) plaqués sur de la fantasy médiévale miteuse. Personne n'est héroïque. Personne n'est méchant non plus : tout le monde est fatigué, sous-payé et vaguement de mauvaise foi. Le rire naît du **décalage de registre** (un dragon qui parle comme un délégué syndical) et du **temps mort** (la réplique arrive une seconde trop tard, ou n'arrive pas).

### Règles d'écriture imposées à toute l'équipe

- **Jamais de « lol fantasy ».** Pas de références pop, pas de clins d'œil au joueur, pas de méta. L'univers se prend au sérieux ; ce sont ses habitants qui n'y arrivent pas.
- **Réplique courte = réplique drôle.** Plafond dur : 90 caractères par bark de combat. Au-delà, le joueur lit pendant qu'il joue, et ne fait ni l'un ni l'autre.
- **L'anticlimax prime.** Toute montée en tension doit retomber sur un détail administratif ou domestique.
- **Personne n'a d'arc narratif.** Aucun personnage n'apprend quoi que ce soit. C'est le sujet.

### Architecture du système de dialogue

Le piège du genre : écrire 3 000 lignes « par événement », les brûler en quatre heures de jeu, et laisser le joueur dans le silence pour les vingt-six heures restantes. On écrit donc **par état**, pas par événement.

Chaque bark est une entrée dans la matrice :

```
BARK = [ DÉCLENCHEUR ] × [ LOCUTEUR ] × [ PALIER DE ROUSPÉTANCE ] × [ CIBLE ]
```

Un même déclencheur (« attaque ratée d'un allié ») produit quatre lignes très différentes selon que Florimond est à 10 % ou à 90 % de rouspétance. On multiplie le ressenti sans multiplier l'écriture.

| Couche | Volume cible | Rôle |
|---|---|---|
| **Chamaillerie de combat** | ~1 400 lignes | Réactions aux ratés, aux critiques, aux tirs amis |
| **Répliques de mort** | ~240 lignes | Uniques par classe × cause de la mort (16 causes répertoriées) |
| **Banter de poisse** | ~300 lignes | Déclenchées par des *séries* : 3 ratés d'affilée, 2 coffres vides, 0 butin sur un étage |
| **Dialogues de salle** | ~600 lignes | Contextuelles au type de pièce et à qui est encore debout |
| **Camp & briefing** | ~450 lignes | Ordre de mission, plaintes, repas |

**Anti-répétition :** chaque ligne jouée est verrouillée pendant 3 runs. Un pool épuisé bascule sur le silence plutôt que sur une redite — le silence entre deux personnages qui viennent de s'engueuler est en soi une information.

---

## PIÈCE N°2-B — GRILLE D'ÉCRITURE : LES MÉCANISMES

> **Position juridique, tranchée une fois pour toutes.** Aucune réplique de *Kaamelott*, *Hero Corp*, ou de quelque œuvre protégée que ce soit, n'entre dans ce jeu — ni citée, ni « adaptée », ni déguisée. Les dialogues sont protégés, les auteurs sont vivants, et le droit français n'offre rien d'équivalent au *fair use* : l'exception de courte citation ne couvre pas un jeu commercial qui réemploie des répliques comme les siennes. Un éditeur fera l'audit avant signature.
>
> Ce qui s'emprunte légitimement, ce sont les **mécanismes comiques**. Un procédé n'est pas protégeable ; une réplique l'est. On étudie donc la machine, on n'emporte pas les pièces.

### Les sept mécanismes d'Astier, et ce qu'on en garde

| Mécanisme | Ce qu'il fait | Application dans le jeu |
|---|---|---|
| **Le télescopage de registres** | Un langage contemporain, souvent administratif ou managérial, dans un décor qui ne le supporte pas | Vermicule invoque sa convention collective ; Perrine réclame un registre d'entrée |
| **L'anticlimax** | La tension monte, puis retombe sur un détail domestique ou une question de procédure | Toute scène de boss doit se terminer sur un problème de calendrier, jamais sur un cri de guerre |
| **Le dialogue de sourds** | Deux personnages tiennent deux conversations différentes sans s'en apercevoir | Odon répond systématiquement à une question que personne n'a posée |
| **Le déraillement** | Une discussion importante part sur un détail secondaire et n'y revient jamais | Les Engueulades doivent bifurquer, pas se résoudre |
| **L'incompétent en position d'autorité** | Le pouvoir est détenu par quelqu'un qui ne le mérite pas et le sait | Le seigneur Aymeric, Grzznak, Frère Colas |
| **Le silence** | Le temps mort fait la moitié du travail comique | Techniquement imposé : un pool de barks épuisé se tait, il ne se répète pas |
| **La répétition excédée** | La même chose, redite, une fois de trop | Les barks de série (3 ratés d'affilée) sont construits là-dessus |

### Ce que *Hero Corp* ajoute, et qui manque encore au document

Le registre y est moins chevaleresque et plus **provincial** : le fantastique est écrasé par la banalité municipale, et le groupe fonctionne comme une thérapie collective ratée. Trois choses à importer dans le ton, sans rien emprunter d'autre :

- **Le déclassement.** Les personnages ont connu mieux, ou croient l'avoir connu. Guérin gagnerait à évoquer une époque où « c'était mieux tenu », sans qu'on sache jamais si c'est vrai.
- **La contrainte administrative locale.** Pas un empire : une commune. Fresnes-les-Tourbes doit avoir des voisins, un litige de bornage, et une rivalité de clocher.
- **Le groupe qui ne peut pas se séparer.** Personne ne part, non par loyauté, mais parce que partir demanderait des démarches.

### La veine que tu n'exploites pas encore : l'humour de table

C'est la meilleure suggestion de ton message, et c'est celle qui a le plus de valeur ici — parce que l'humour rôliste porte **sur des règles et des probabilités**, c'est-à-dire exactement ce qu'un jeu tactique peut rendre mécanique.

Les situations récurrentes des tables de jeu de rôle, qui sont des *situations* et non des textes, donc librement exploitables :

| Situation de table | Transposition diégétique — sans jamais briser le quatrième mur |
|---|---|
| Le joueur qui conteste la malchance | Guérin traite la série de ratés comme un dysfonctionnement du service |
| Le rules-lawyer | Beuzelin interrompt l'action pour un point de procédure |
| Le pillage systématique des cadavres | L'inventaire du défunt, mené comme une formalité successorale |
| Le plan de quarante minutes qui échoue en dix secondes | Une réplique d'ouverture de combat, toujours |
| Celui qui n'écoutait pas | Odon demande qu'on répète, au pire moment |
| La classe de soutien qu'on méprise | Florimond en a fait une identité, et s'en venge |
| Les notes que personne ne relit | Beuzelin consigne tout. Personne ne consulte rien |

**Règle absolue.** Ces mécanismes sont transposés **dans la fiction**, jamais en clin d'œil. Les personnages ne savent pas qu'ils sont dans un jeu, ne parlent jamais de dés, de statistiques de jeu ni de points de vie. Guérin ne dit pas « j'ai fait un 1 » : il dit que trois échecs de suite, à son avis, relèvent d'une enquête interne.

### Les sources libres de droits, et pourquoi elles sont meilleures ici

Une bibliothèque entière de comédie administrative française est dans le domaine public, donc exploitable sans limite — et elle correspond à ce jeu plus exactement que n'importe quelle série récente :

- **Georges Courteline**, *Messieurs les ronds-de-cuir* et *Le Train de 8 h 47* : la satire du bureau, du chef médiocre et de la procédure pour la procédure. C'est littéralement le sujet du jeu, écrit en 1893.
- **Alphonse Allais** : l'absurde froid, tenu avec le plus grand sérieux.
- **Alfred Jarry**, *Ubu roi* : le pouvoir grotesque, la cupidité enfantine, la cruauté administrative.
- **Eugène Labiche** et **Feydeau** : la mécanique de la scène qui déraille, le quiproquo qui s'entretient tout seul.

Ce sont des modèles d'écriture, pas des banques de répliques : on y étudie le **rythme de la phrase** et la **construction de la scène**, et on écrit le reste.

### La conséquence sur le recrutement

Une conclusion désagréable mais nécessaire : ce ton ne s'obtient pas en briefant un auteur généraliste. Il faut **une plume qui a écrit du dialogue comique pour la scène ou la série**, et il faut la budgéter comme un poste, pas comme une prestation. C'est le seul poste du projet où l'économie se paie immédiatement en qualité perçue.

---

## PIÈCE N°2-C — BANQUE DE SITUATIONS ADMINISTRATIVES

**Le titre est arrêté : *DONJON & PAPERASSE*.** Il est verrouillé, et il porte un avantage qui n'était pas prévu : *Dungeon & Paperwork* fonctionne à l'identique en anglais. Le risque « la traduction tue l'humour », classé Élevé en pièce n°10, descend d'un cran pour tout ce qui relève de ce registre.

> **Règle de non-nommage, non négociable.** Aucune institution réelle, aucun acronyme, aucun sigle, aucun nom de formulaire existant. Trois raisons cumulées : ça date le jeu, ça le fait basculer du sketch, et c'est précisément la part qui ne survivra pas à la localisation.
>
> Ce qui est universel n'est pas le nom du guichet, c'est **la forme du blocage**. Un Allemand, un Italien ou un Brésilien reconnaîtra la boucle impossible sans connaître l'administration qui la produit. On écrit donc des **mécaniques**, jamais des références.

### Les douze mécaniques du non-sens administratif

| Mécanique | Ce qu'elle produit | Où elle vit déjà dans le jeu |
|---|---|---|
| **1. La boucle impossible** | Le document A exige le document B, qui n'est délivré que sur présentation du document A | Le Bureau des Réclamations exige un formulaire de réclamation, qu'il est le seul à délivrer |
| **2. Le renvoi** | « Ce n'est pas mon service » — répété par chaque service | Les gobelins syndiqués se renvoient le joueur entre eux, en cercle |
| **3. L'horaire hostile** | Ouvert quand vous travaillez, fermé quand vous arrivez | Le système des Horaires du biome 1 ; le Bureau ouvre à 18 h et ferme à 18 h 05 |
| **4. Le justificatif du justificatif** | Il faut prouver qu'on a le droit de demander la preuve | Un objet réclame sa preuve d'achat, laquelle est fournie avec l'objet |
| **5. Le formulaire abrogé, toujours exigé** | Plus en vigueur, mais sans lui rien n'avance | La Note de service n°4417 : personne ne l'a lue, tout le monde l'applique |
| **6. Le délai à échéance inconnue** | « Avant le 31. » — Le 31 de quoi ? | Vermicule et son formulaire D-12 |
| **7. La règle non écrite, appliquée strictement** | Elle n'existe nulle part ; la demander ne la produit pas | Les gobelins invoquent des articles introuvables et s'y tiennent |
| **8. Le dossier jamais reçu** | Il a été envoyé. Il n'est pas arrivé. Personne n'est responsable | La jauge de Suspicion et le contrôle qui en découle |
| **9. Le silence qui vaut décision** | Sans réponse, c'est accepté. Ou refusé. Selon le cas | Une salle d'événement où ne rien faire produit un effet, révélé après coup |
| **10. L'interlocuteur unique, absent** | Une seule personne peut traiter le dossier. Elle est en formation | Frère Anselme : cité partout, jamais présent, remplacé par un intérimaire |
| **11. La pièce complémentaire après clôture** | Le dossier est clos, il manque une pièce | Dame Perrine réclame un consommable une fois le combat terminé |
| **12. « Il fallait le signaler avant »** | Avant quoi — jamais précisé | Réplique récurrente des gobelins, jamais explicitée |

### Le gobelin syndiqué comme incarnation du guichet

C'est l'ennemi le plus fréquent du jeu, donc celui qu'on entend le plus. Son registre est désormais fixé : **il ne menace jamais, il oppose une procédure.** Il n'est pas hostile, il est indifférent, et c'est bien pire. Extraits du pool implémenté dans le prototype :

> « Vous avez un numéro ? »
> « Ce n'est pas ce guichet. »
> « Le collègue qui s'occupe de ça est en formation. »
> « Moi je veux bien, mais ce n'est pas moi qui fais les règles. »
> « Repassez lundi. On est lundi. Repassez lundi prochain. »
> « Votre demande a bien été enregistrée. Elle ne sera pas traitée. »
> « Ah non. Ça, c'est l'ancien formulaire. »

Et en cas de défaite du groupe, c'est un gobelin qui prononce la dernière réplique du combat — jamais un héros :

> « Votre dossier est classé sans suite. »
> « Une notification vous sera adressée. Sous six semaines. »

### Deux registres à tenir séparés

Le document distingue désormais trois sources d'humour, et elles ne doivent pas se mélanger dans une même réplique :

1. **L'administratif** — porté par les ennemis, les institutions, les objets. Impersonnel, froid, indifférent.
2. **Le rôliste** — porté par le groupe. Il porte sur l'échec, la série noire, le pillage, le plan raté.
3. **Le domestique** — porté par les personnages entre eux. La fatigue, la rancune, le repas, l'heure qu'il est.

Une réplique qui tient les trois à la fois n'est pas trois fois plus drôle : elle est illisible. **Un registre par réplique.**

---

## PIÈCE N°3 — BOUCLE DE JEU

### Vue d'ensemble (un run = 25 à 40 minutes)

**0. L'ORDRE DE MISSION** *(~40 s)*
Le seigneur Aymeric de Fresnes-les-Tourbes dicte l'objectif à un scribe qui n'écoute pas. Les motifs sont générés et systématiquement dérisoires : sa belle-mère arrive et le donjon « gâche la vue depuis la salle à manger » ; il y a un problème d'écoulement ; les gobelins font du bruit le dimanche ; il a promis à quelqu'un, il ne sait plus à qui. L'objectif réel — 3 étages, un boss par étage — est identique — seule la justification change, et elle conditionne le **modificateur de run**.

**1. LA DESCENTE** *(12–18 min)*
Carte à nœuds, 3 étages de 6 à 9 salles. Types de salles : Combat, Combat d'élite, Marchand à la sauvette, Piège (souvent hors service), Événement, Salle des archives (formulaires vierges), Repos. Le joueur voit deux nœuds à l'avance — assez pour planifier, pas assez pour optimiser.

**2. LE COMBAT** *(60–120 s par affrontement)*
Tour par tour, **sans grille** : formation en 4 rangs (comme un ordre de marche). Chaque capacité impose un rang source et des rangs cibles. Trois ressources : **PV** (individuel), **Moral** (collectif, 0–100), **Rouspétance** (individuelle, 0–100). Initiative tirée en début de tour avec ±2 de variance — assez pour rater un plan, pas assez pour le rendre impossible.

**3. LE REPLI** *(~60 s)*
Sortir du donjon ne suffit pas : il faut **rendre le rapport**. Le joueur répartit le butin, choisit ce qu'il déclare et ce qu'il ne déclare pas. Sous-déclarer rapporte plus de Ferraille mais fait grimper la **Suspicion** du camp, qui déclenche à terme un contrôle — et un contrôle, c'est un run entier passé à chercher des justificatifs.

**4. LE CAMP** *(3–5 min)*
Fresnes-les-Tourbes, campement mal tenu. On y investit trois monnaies dans des bâtiments dont aucun n'est une arme.

### Monnaies

| Monnaie | Source | Usage |
|---|---|---|
| **FERRAILLE** | Ennemis, démontage de pièges | Bâtiments, réparations |
| **BUTIN INVENDABLE** | Coffres, boss | Estimé par un commissaire-priseur qui sous-évalue systématiquement de 30 à 60 % — et le dit |
| **PAPERASSE** | Salles des archives | Déblocages méta : nouvelles classes, nouvelles capacités, nouveaux motifs de mission |

### Le camp : bâtiments et niveaux

| Bâtiment | Effet | Note de design |
|---|---|---|
| **La Taverne** | Réduit la Rouspétance de départ de tout le groupe | Le seul bâtiment que les personnages réclament |
| **Le Réfectoire** | Soupe du jour = buff de run aléatoire parmi 3 au choix | La soupe est toujours décrite avec un enthousiasme injustifié |
| **L'Infirmerie** | Soins entre les runs | Niveau 1 = une tente et un seau. Niveau 3 = une tente, un seau, et quelqu'un qui a lu un livre |
| **Le Bureau des Réclamations** | Permet de relancer l'ordre de mission une fois | Ouvre à 18 h. Ferme à 18 h 05 |
| **La Forge Approximative** | Améliore les capacités | Les améliorations ont un taux d'échec assumé et annoncé |
| **Les Latrines** | +15 Moral permanent par niveau | Statistiquement l'amélioration la plus rentable du jeu. C'est volontaire, c'est une blague, et c'est vrai |

---

## PIÈCE N°4 — LA JAUGE DE ROUSPÉTANCE

Chaque personnage porte une jauge 0–100 qui monte quand la journée se passe mal.

### Gains

| Déclencheur | Rouspétance |
|---|---|
| Attaque ratée | +12 |
| Critique reçu | +15 |
| Tir ami | +25 (celui qui le subit), +10 (le tireur) |
| Piège déclenché | +10 pour tout le groupe |
| Coffre ouvert et vide | +18 |
| Allié à terre | +20 |
| Un allié rate deux fois dans le même tour | +8 par témoin |
| Insulte du Barde | +15 (variable selon la capacité) |

### Réductions

| Déclencheur | Rouspétance |
|---|---|
| Coup critique porté | −15 |
| Coup de grâce | −10 |
| « Compliment involontaire » (Barde) | −20 sur une cible |
| Repos | −25 pour tout le groupe |
| Ration au camp | −30 |

### À 100 % : L'ENGUEULADE GÉNÉRALE

Le combat se fige. Les deux personnages les plus remontés échangent deux répliques (générées selon leur historique de la run : qui a raté quoi, qui a volé quoi). **Puis le joueur tranche** — et c'est le point de design critique.

| Choix | Effet |
|---|---|
| **Prendre parti pour A** | Effet déterministe, annoncé. A : Rouspétance → 0, +25 % dégâts 2 tours. B reste à 60 et subit −2 initiative. |
| **Prendre parti pour B** | Symétrique. |
| **« Vos gueules »** | Les deux retombent à 40, **et on tire sur la table ci-dessous.** Le joueur a demandé le chaos : il l'obtient. |

> **Pourquoi ce choix existe.** Un dé imposé au pic de tension dans un jeu tactique se lit comme une punition arbitraire, pas comme une comédie. En laissant le joueur *choisir d'appuyer sur le bouton chaos*, on garde l'imprévisibilité tout en rendant le résultat racontable : « j'ai dit vos gueules, Odon a démissionné en plein combat ». C'est la différence entre subir une blague et en être l'auteur.

### Table des résultats d'engueulade (d8)

| d8 | Résultat | Effet |
|---|---|---|
| 1 | **On se calme** | Toute la Rouspétance du groupe −40. Rien d'autre. Personne n'ose parler. |
| 2 | **Ça fait du bien de le dire** | +30 % dégâts, −25 % précision, 2 tours, pour tout le groupe |
| 3 | **Bouderie** | Le vexé saute son prochain tour, puis revient avec un critique garanti |
| 4 | **Coalition** | Les deux protagonistes ciblent le même ennemi : +50 % dégâts dessus. Les autres : −1 initiative |
| 5 | **Le silence gênant** | +2 esquive pour tous, Moral −15 |
| 6 | **Escalade** | Un troisième s'en mêle. Tout le monde +25 Rouspétance, mais le groupe gagne une action supplémentaire ce tour |
| 7 | **Démission** | Le personnage quitte la formation 2 tours. Revient à PV pleins, avec une note de frais |
| 8 | **Réconciliation suspecte** | Les deux se soignent de 20 % et deviennent *Complices* : les dégâts reçus sont partagés jusqu'à la fin du combat |

---

## PIÈCE N°5 — ARCHÉTYPES

### 1. LE CHEVALIER BLASÉ — *Guérin de la Motte-Piquée*
**Rôle :** Tank / dégâts différés · **Rangs :** 1–2 · **Ressource :** RANCUNE (0–10)
Il ne protège pas le groupe. Il attend son tour. Chaque coup encaissé alimente la Rancune, qui ne décroît jamais d'elle-même : elle se dépense, d'un coup, avec une satisfaction visible.

### 2. LE MAGE DU DIMANCHE — *Odon, ex-fromager*
**Rôle :** Dégâts de zone à haute variance · **Rangs :** 3–4 · **Ressource :** CONFIANCE (0–5)
50 % de chances qu'un sort parte de travers. Chaque sort réussi ajoute +1 Confiance (+5 % de réussite chacun) ; le premier échec remet tout à zéro. Le joueur décide donc quand encaisser son échelle de risque. Les ennemis « navetisés » sont inoffensifs mais explosent à la mort.

### 3. LE BARDE CRITIQUE — *Florimond*
**Rôle :** Support offensif · **Rangs :** 2–3 · **Ressource :** MATIÈRE
Il ne soigne pas, il vexe utile. Ses buffs passent par l'insulte : +dégâts sur l'allié ciblé, +Rouspétance sur ce même allié. **Sa ressource — la Matière — se remplit des échecs du groupe.** Plus l'équipe est mauvaise, plus il est fort, et plus il la rend ingérable. C'est la meilleure blague mécanique du jeu, et c'est aussi son meilleur dilemme tactique.

### 4. LE ROUBLARD ADMINISTRATIF — *Sous-greffier Beuzelin*
**Rôle :** Distance / contrôle · **Rangs :** 3–4 · **Ressource :** FORMULAIRES
Il lance des documents. Chaque touche applique une pile de **PROCÉDURE** ; à 3 piles, l'ennemi est *convoqué* et perd son tour. Il vole de l'or — aux ennemis, et aussi aux membres de son propre groupe. L'or volé aux alliés revient au camp, minoré des frais de dossier. Techniquement, il est dans son droit.

---

## PIÈCE N°6 — CAPACITÉS DÉTAILLÉES (personnages de départ)

### GUÉRIN — LE CHEVALIER BLASÉ

**PASSIF · NOTE MENTALE**
Chaque coup encaissé : +1 Rancune (max 10). La Rancune ne diminue pas avec le temps.
> *Il ne dit rien. Il note.*

**SOUPIR APPUYÉ** — Rangs 1–2 → tous les ennemis · Sans coût
Attire 80 % de la menace pendant 2 tours. +2 Rancune.
> *Il n'a pas protesté. C'est ça, le pire.*

**COUP DE BOUCLIER, MAIS SANS Y CROIRE** — Rangs 1–2 → cibles 1–2
4–7 dégâts. 25 % d'étourdissement.
> *Le bouclier est réglementaire. L'enthousiasme, non.*

**PAR PUR DÉPIT** — Rangs 1–2 → cibles 1–3 · Consomme toute la Rancune
3 dégâts + 4 par point de Rancune dépensé (max 43).
> *Guérin ne frappe pas plus fort quand il est en forme. Il frappe plus fort quand il est vexé.*

**JE PRENDS** — Posture, 2 tours
Redirige sur lui toute attaque monocible visant un allié. +3 Rancune par coup encaissé. Riposte à 50 % des dégâts.
> *« Je prends. » Il dit toujours ça. Personne ne le lui a jamais demandé.*

**ARRÊT MALADIE** — 1 fois par combat
Guérin passe son tour, récupère 25 % de ses PV et −30 de Rouspétance. Tous les autres : +10 Rouspétance.
> *Certificat fourni. Signé par lui-même. Contresigné par lui-même.*

**Réplique de mort :** « Bon. Au moins, je ne participe plus. »

---

### ODON — LE MAGE DU DIMANCHE

**PASSIF · AUTODIDACTE**
Les sorts marqués *instable* réussissent à 50 % + 5 % par point de Confiance. Réussite : +1 Confiance. Échec : Confiance → 0.
> *Il a appris seul. Ça se voit.*

**BOULE DE FEU (PROBABLEMENT)** — *instable* · Rangs 3–4 → toutes cibles
Réussite : 8–14 dégâts. Échec : 6 dégâts sur un allié tiré au hasard, +25 Rouspétance pour ce dernier.
> *Le sort fonctionne une fois sur deux. Odon préfère dire qu'il fonctionne.*

**NAVETISATION** — *instable* · Rangs 3–4 → cibles 2–4
Réussite : l'ennemi devient un navet — 0 action, PV réduits à 30 %, et explose à sa mort pour 8 dégâts de zone. Échec : la cible est *vexée*, +20 % de dégâts pour 2 tours.
> *Réversible dans 80 % des cas. Les 20 % restants font une excellente soupe.*

**PETIT SORT DE RIEN DU TOUT** — Garanti · Rangs 3–4 → cibles 1–4
2–4 dégâts. +1 Confiance. Ne peut pas rater.
> *Le seul sort qu'Odon maîtrise réellement. Il en a honte.*

**LIRE LA NOTICE** — Passe le tour
+2 Confiance. Le prochain sort instable ne peut pas rater.
> *Odon a un grimoire. Acheté d'occasion. Il manque les pages 40 à 60.*

**TOUT DONNER** — 1 fois par run · 50 % fixe, non modifié par la Confiance
Réussite : 25–40 dégâts sur tous les ennemis. Échec : Odon tombe à 1 PV, tout le groupe +40 Rouspétance.
> *Il n'a jamais réussi ce sort à l'entraînement. Mais à l'entraînement, il n'y avait pas de dragon.*

**Réplique de mort :** « J'AVAIS DIT QUE J'ÉTAIS FROMAGER ! »

---

## PIÈCE N°6-C — CAPACITÉS : FLORIMOND, LE BARDE CRITIQUE

**Rangs 2–3 · Ressource : MATIÈRE (0–8)**

> **Le problème à résoudre.** Un support dont les buffs coûtent de la Rouspétance n'a aucune raison d'exister si la Rouspétance est uniquement une punition. Florimond n'est jouable qu'à une condition : **il donne au joueur le contrôle de l'engueulade.** Sans lui, la dispute oppose les deux personnages les plus remontés, au hasard. Avec lui, le joueur choisit au moins un des deux protagonistes. Remplir la jauge cesse d'être un accident et devient un plan.

**PASSIF · ÇA ME DONNE DE LA MATIÈRE**
Chaque échec du groupe — attaque ratée, critique reçu, coffre vide, piège déclenché — donne +1 Matière (max 8). La Matière se conserve entre les combats d'un même run et se vide au camp.
> *Il ne prend pas de notes. Il n'en a pas besoin.*

> **Correction issue du prototype.** Dans la première version, les deux capacités de Florimond avaient un coût. Résultat : à Matière zéro, il n'avait **aucune action possible** — le jeu attendait indéfiniment une entrée qui ne pouvait pas exister, et se bloquait. Le défaut n'était pas seulement technique : sa ressource ne se remplissait que des échecs du groupe, donc une équipe qui jouait bien le rendait inutile *et* muet. Il dispose désormais d'une attaque gratuite qui alimente elle-même sa Matière, et chaque classe du jeu doit avoir au moins une action sans coût.

**REMARQUE DE FOND DE SALLE** — Rangs 2–3 → cibles 1–3 · Sans coût
2–5 dégâts. +1 Matière.
> *Il ne vise pas. Il commente, et ça porte.*

**REMARQUE APPUYÉE** — Rangs 2–3 → un allié · Coût : 1 Matière
+35 % de dégâts pendant 2 tours sur l'allié ciblé. +15 Rouspétance sur ce même allié.
> *Il ne dit jamais que c'était nul. Il dit que c'était courageux d'essayer.*

**TU VAS PAS ME REFAIRE LE COUP** — Rangs 2–3 → un allié · Coût : 2 Matière
La prochaine attaque de l'allié ne peut pas rater. Si elle touche, Florimond gagne +2 Matière. Si l'allié était déjà au-dessus de 60 de Rouspétance, l'attaque inflige aussi +50 % de dégâts.
> *La menace n'est pas explicite. Elle n'a jamais besoin de l'être.*

**COMPLIMENT INVOLONTAIRE** — Rangs 2–3 → un allié · 1 fois par combat
−20 Rouspétance sur l'allié ciblé. +10 Rouspétance sur Florimond.
> *Il a dit quelque chose de gentil. Il s'est repris tout de suite, mais c'était sorti.*

**ENVENIMER** — Rangs 2–3 → deux alliés · Coût : 3 Matière
+25 Rouspétance sur les deux cibles. Si l'une d'elles atteint 100 pendant les 3 tours suivants, **le joueur désigne le second participant de l'Engueulade** au lieu de le subir.
> *Florimond ne déclenche pas les disputes. Il les oriente.*

**CHANSON DE GESTE (RÉVISÉE)** — Rangs 2–3 → tout le groupe · Coût : 4 Matière
Florimond raconte le run en cours, avec ses échecs réels. +20 % de dégâts pendant 3 tours pour tout le groupe, +3 % supplémentaires par incident enregistré dans le run (plafond +45 %). +10 Rouspétance pour tout le monde.
> *Toutes les strophes sont exactes. C'est précisément le problème.*

**LE MOT DE TROP** — Ultime · 1 fois par run · Coût : toute la Matière (minimum 6)
Déclenche immédiatement une Engueulade Générale. Le joueur choisit **les deux protagonistes** et **deux résultats** dans la table d8, puis garde celui qu'il préfère. Tous les autres membres : +30 Rouspétance.
> *Il l'avait préparé. Il l'avait gardé. Il attendait le bon moment, et le bon moment est toujours le pire.*

**Réplique de mort :** « Voilà. Maintenant, plus personne ne vous dira la vérité. »

---

## PIÈCE N°6-D — CAPACITÉS : BEUZELIN, LE ROUBLARD ADMINISTRATIF

**Rangs 3–4 · Ressources : FORMULAIRES (0–5) et LA CAISSE**

> **Le problème à résoudre.** Voler ses propres alliés est une blague à usage unique : à la dixième fois, ce n'est plus un gag, c'est un prélèvement. Le vol ne fonctionne que s'il **convertit** — l'or pris aux alliés ne disparaît pas, il alimente **La Caisse**, une réserve que Beuzelin seul peut dépenser en plein combat. Le joueur n'est pas volé : il est réaffecté. Il déteste quand même ça, mais il comprend pourquoi il le fait.

**PASSIF · FRAIS DE DOSSIER**
Tout l'or pris par Beuzelin — aux ennemis comme aux alliés — est versé à La Caisse. À la fin du run, le solde de La Caisse rejoint le butin du groupe, **minoré de 15 % de frais de dossier**. Ces 15 % ne sont jamais récupérables et ne sont jamais justifiés.
> *L'argent n'a pas disparu. Il a changé de ligne budgétaire.*

**PILES DE PROCÉDURE** — mécanique de classe
Chaque pile ralentit la cible (−1 initiative). À 3 piles, l'ennemi est **convoqué** : il perd son tour et devient inciblable pendant ce tour — il est ailleurs. Les piles persistent jusqu'à la fin du combat.

**SIGNIFICATION** — Rangs 3–4 → cibles 1–4 · Sans coût
3–6 dégâts. +1 pile de Procédure.
> *Le document est recevable. Le lancer, un peu moins.*

**MISE EN DEMEURE** — Rangs 3–4 → une cible · Coût : 1 Formulaire
+2 piles de Procédure. Aucun dégât.
> *Convoqué, pas tué. Il y a une différence, et elle est administrative.*

**PRÉLÈVEMENT À LA SOURCE** — Rangs 3–4 → un allié · Sans coût
Prend 40 % de l'or porté par un allié et le verse à La Caisse. L'allié : +20 Rouspétance. Beuzelin : +1 Formulaire.
> *Ce n'est pas du vol. C'est une avance sur la répartition finale.*

**NOTE DE FRAIS** — Action · Dépense de La Caisse
Au choix : soigner un allié de 15 % (100 po), gagner 1 Formulaire (60 po), ou annuler la prochaine attaque ennemie (200 po). **Chaque usage dans le même combat augmente tous les tarifs de 25 %.**
> *Tout est remboursable. Rien n'est remboursé.*

**CONTRÔLE INOPINÉ** — Rangs 3–4 → tous les ennemis · Coût : 2 Formulaires
+1 pile de Procédure à tous. Les ennemis porteurs d'or en perdent 25 %, versés à La Caisse. Les gobelins syndiqués répondent par un préavis de grève immédiat — c'est le risque, et il est annoncé dans l'infobulle.
> *Bonjour. Je ne vous retiendrai pas longtemps. Si.*

**CLASSEMENT SANS SUITE** — Ultime · 1 fois par run · Coût : 3 Formulaires
Retire définitivement du combat un ennemi non-boss, quel que soit son nombre de PV. Aucun butin, aucune expérience : le dossier est clos, pas gagné. Sur un boss : 3 piles de Procédure et −30 % de dégâts pendant 2 tours.
> *L'affaire n'a pas été jugée. Elle a été rangée.*

**Réplique de mort :** « Le dossier est dans la sacoche. La sacoche est sur moi. Bon courage. »

---

### SYNERGIE RÉPERTORIÉE — « L'ÉQUIPE DE NUIT »

Florimond et Beuzelin ensemble constituent la composition la plus instable du jeu, et c'est délibéré : le Barde remplit les jauges, le Roublard vide les poches. Chaque Prélèvement à la Source donne de la Matière au Barde (c'est un échec du groupe), et chaque Remarque Appuyée rapproche l'équipe de l'Engueulade que Florimond aura orientée.

Le groupe gagne vite, ou se dissout en quatre tours. Il n'y a pas de troisième issue, et c'est la composition que l'on recommandera dans le tutoriel avancé.

---

## PIÈCE N°6-E — MÉTA-PROGRESSION : L'EFFECTIF DÉBLOCABLE

> **Doctrine.** Une classe débloquable qui est simplement plus forte rend les quatre classes de départ obsolètes, et le joueur cesse de jouer les trois quarts du jeu qu'on a construit. Règle appliquée ici : **chaque classe débloquable confisque un système actuellement orphelin** — le Moral, les pièges hors service, la mort des personnages, le rapport de fin de run — au lieu d'augmenter le plafond de dégâts. Aucune n'est meilleure que les quatre de base. Toutes changent la façon dont on joue un run.
>
> Corollaire sur les conditions de déblocage : elles vérifient qu'on a **compris** un système, jamais qu'on a joué longtemps. Un déblocage à la durée est un abonnement, pas une récompense.

| Classe | Système confisqué | Condition de déblocage |
|---|---|---|
| **L'Aumônier intérimaire** | Le Moral collectif | Terminer un run avec les quatre membres au-dessus de 80 de Rouspétance — *« quelqu'un a signalé l'ambiance »* |
| **Le Géomètre assermenté** | Les pièges et la carte | Déclencher 20 pièges hors service — *« un signalement a été transmis au cadastre »* |
| **Maître Gisèle, notaire** | La mort des personnages | Perdre trois personnages dans un même run — *« il y a des formalités »* |
| **Le Stagiaire** | Le rapport de fin de run | Résoudre Vermicule par le formulaire D-12 — *« il a lu le dossier. Il a trouvé ça passionnant »* |

---

## PIÈCE N°6-F — FRÈRE COLAS, L'AUMÔNIER INTÉRIMAIRE

**Rangs 2–3 · Ressource : FOI (0–4)**

Il remplace Frère Anselme, parti en formation. Il ne sait pas exactement pour combien de temps, ni pour quelle divinité — le diocèse n'a pas été clair. C'est le premier soigneur du jeu, et il peut démissionner en cours de run.

**PASSIF · CONTRAT À DURÉE DÉTERMINÉE**
Colas gagne +1 Foi chaque fois qu'un allié passe sous 30 % de PV — il n'est utile que quand ça va mal, et il le sait. Il n'a pas de jauge de Rouspétance : il a un compteur de **Fin de Mission**. À la fin de chaque étage, 20 % de chances qu'il annonce que sa mission s'achève et qu'il quitte le run.
> *Il est là jusqu'à nouvel ordre. L'ordre peut tomber n'importe quand.*

**BÉNÉDICTION SOUS RÉSERVE** — Rangs 2–3 → un allié · Sans coût
Soigne 20 % des PV, +5 % par point de Foi.
> *Il bénit. Il précise ensuite qu'il n'est pas habilité.*

**MÉDIATION** — Pendant une Engueulade Générale · Coût : 1 Foi
Met fin à l'Engueulade immédiatement, sans jet et sans aucun effet. Moral −20.
> *Il a désamorcé la dispute. C'était la meilleure partie de la journée.*

**SERMON DE CIRCONSTANCE** — Rangs 2–3 → tout le groupe · Coût : 2 Foi
Moral +25. Mais tout allié déjà au-dessus de 50 de Rouspétance gagne +10 Rouspétance au lieu du bénéfice.
> *Il a préparé trois sermons. Il choisit systématiquement le mauvais.*

**ALORS MOI JE NE SUIS PAS CENSÉ FAIRE ÇA** — 1 fois par run · Coût : 3 Foi
Relève un allié à terre avec 20 % de ses PV. Tout le groupe : +25 Rouspétance — ils ont vu.
> *Personne ne doit le savoir. Tout le monde l'a vu.*

**PRIÈRE POUR LE MATÉRIEL** — 1 fois par run · Sans coût
Restaure un consommable déjà utilisé, ou répare un équipement endommagé.
> *Il prie surtout pour la charrette.*

**Réplique de mort :** « Je ne devais rester qu'une semaine. »

> **Note de design.** Colas est l'anti-Florimond, frontalement : l'un vend l'engueulade au joueur, l'autre la lui confisque. Les avoir tous les deux dans la même formation est jouable, coûteux, et c'est exactement la conversation qu'on veut voir sur les forums.

---

## PIÈCE N°6-G — JOSSELIN, LE GÉOMÈTRE ASSERMENTÉ

**Rangs 2–4 · Ressource : RELEVÉS (0–6)**

Il n'a pas été envoyé se battre. Il a été envoyé constater. Il constate, effectivement, et signale à voix haute chaque défaut de construction du donjon, dont il est le seul à être sincèrement affecté.

**PASSIF · TOUT EST DE TRAVERS**
Révèle en permanence les deux prochains nœuds de la carte **et leur contenu**. +1 Relevé à chaque nouvelle salle visitée, +1 supplémentaire par piège désamorcé.
> *Le donjon penche de trois degrés vers le sud. Il en parlera.*

**JALON** — Rangs 2–4 → cibles 1–4 · Sans coût
4–8 dégâts. Repousse la cible d'un rang vers l'arrière.
> *L'instrument est un outil de mesure. Il fait néanmoins un bruit très satisfaisant.*

**NON-CONFORMITÉ DE PLACEMENT** — Rangs 2–4 → formation ennemie · Coût : 2 Relevés
Réorganise entièrement les rangs adverses. Les lanceurs se retrouvent devant, les brutes derrière.
> *Leur disposition n'est pas réglementaire. Il corrige.*

**REMISE EN SERVICE** — Salles à piège uniquement · Coût : 3 Relevés
Répare le piège hors service de la salle et le retourne contre les ennemis : 12–20 dégâts de zone. Une fois par salle.
> *Le piège fonctionnait très bien. Il manquait juste l'entretien.*

**CONDAMNATION DE SALLE** — Hors combat · Coût : 4 Relevés
Déclare une salle non conforme : elle disparaît de la carte. On perd son butin, on évite son contenu.
> *Il ne l'a pas vidée. Il l'a fermée.*

**LEVÉ TOPOGRAPHIQUE** — Ultime · 1 fois par run · Coût : tous les Relevés (min. 5)
Révèle l'étage entier, boss et phases compris. +2 initiative pour tout le groupe au prochain combat.
> *Il a tout mesuré. Il est le seul à savoir ce qu'il y a derrière le mur ouest, et ça le rend insupportable.*

**Réplique de mort :** « La cote de 4,20 m… était fausse… »

---

## PIÈCE N°6-H — MAÎTRE GISÈLE, NOTAIRE DE CAMPAGNE

**Rangs 3–4 · Ressource : SUCCESSIONS (0–3)**

Elle a pris les mesures de tout le monde dès le premier jour. Elle n'est pas macabre : elle est prévoyante, et elle trouve que la distinction est évidente. C'est la seule classe du jeu pour qui un allié à terre est un actif.

**PASSIF · TESTAMENT ANTICIPÉ**
Au début de chaque combat, Gisèle enregistre les dernières volontés d'un allié désigné par le joueur. Si cet allié tombe, elle **hérite d'une de ses capacités** jusqu'à la fin du combat et gagne +1 Succession.
> *Ce n'est pas un mauvais présage. C'est une bonne pratique.*

**CLAUSE DE SAUVEGARDE** — 1 fois par run · Sans coût
Un allié à terre est relevé à 10 % de ses PV.
> *Le décès n'est pas constaté tant que le document n'est pas signé.*

**PARTAGE** — Rangs 3–4 → tout le groupe · Coût : 1 Succession
Redistribue équitablement tous les buffs et débuffs du groupe entre ses quatre membres.
> *Personne n'est content. C'est comme ça qu'on sait que c'est équitable.*

**INDIVISION** — Rangs 3–4 → deux alliés · Coût : 2 Successions
Pendant 3 tours, les deux cibles partagent une réserve de PV commune et encaissent tous les dégâts à parts égales.
> *Techniquement, ce ne sont plus deux personnes. Techniquement.*

**LIQUIDATION DE SUCCESSION** — Coût : 3 Successions
Retire **définitivement** un allié à terre de l'effectif — il ne revient pas au camp — et convertit ses biens : 40–70 dégâts sur tous les ennemis, et tout son or versé à La Caisse.
> *Il ne reviendra pas. Ses affaires, si.*

**ACTE AUTHENTIQUE** — Ultime · 1 fois par run · Coût : 2 Successions
Fige l'état du combat pendant un tour complet : aucun point de vie ne peut être perdu, des deux côtés.
> *Rien ne bouge tant que tout le monde n'a pas paraphé chaque page.*

**Réplique de mort :** « Ma propre succession… est en ordre. Évidemment. »

---

## PIÈCE N°6-I — AUBIN, LE STAGIAIRE

**Tous rangs · Ressource : ZÈLE (0–10) · Non rémunéré**

La classe la plus dangereuse du jeu, et celle qui commence avec le moins. Aubin ne sait rien faire. Aubin apprend vite. C'est un problème que personne n'avait anticipé.

**PASSIF · APPRENTISSAGE SUR LE TAS**
Aubin commence chaque run **sans aucune capacité offensive**. Chaque fois qu'un allié utilise trois fois la même capacité devant lui, Aubin l'acquiert, à 60 % de sa puissance. Maximum quatre capacités apprises par run.
Il n'a pas de jauge de Rouspétance : il ne se plaint jamais. En contrepartie, **tous les autres membres gagnent +5 Rouspétance par tour** tant qu'Aubin est en vie.
> *Il est ravi d'être là. C'est insoutenable.*

**JE PEUX AIDER ?** — Tous rangs → cibles 1–4 · Sans coût · Seule capacité de départ
1–2 dégâts. +2 Zèle. Si le coup tue un ennemi : +5 Zèle, et tous les alliés +15 Rouspétance.
> *Il a porté le coup fatal. Il ne sait pas encore que c'est un problème.*

**INITIATIVE MALHEUREUSE** — Coût : 3 Zèle
Aubin agit immédiatement, hors de son tour, avec une capacité apprise. 25 % de chances qu'il choisisse la mauvaise cible.
> *Il n'a pas attendu qu'on lui demande. On ne lui demande jamais rien.*

**NOTES DU STAGIAIRE** — Coût : 5 Zèle
Acquiert immédiatement une capacité alliée, sans attendre les trois usages.
> *Il prend des notes. Beaucoup de notes. Sur tout le monde.*

**RAPPORT DE STAGE** — Fin de run · Automatique
Si Aubin survit au run : +50 % de Paperasse. S'il meurt : le groupe perd **la totalité** de la Paperasse du run. Il y a une enquête.
> *C'est le seul document que personne ne veut avoir à rédiger.*

**Réplique de mort :** « Est-ce que ça compte quand même pour la convention ? »

> **Note de design.** Aubin n'est pas une classe plus forte, c'est un **échange de tempo** : un emplacement de formation gaspillé pendant le premier tiers du run, la meilleure unité du terrain sur le dernier. Le joueur qui le prend accepte de mal jouer pendant dix minutes. S'il finit la campagne avec Aubin vivant, l'épilogue est qu'il est embauché — et qu'il remplace le seigneur Aymeric.

---

## PIÈCE N°7 — BESTIAIRE (extraits)

**GOBELINS SYNDIQUÉS.** Combattants médiocres, organisation exemplaire. Tuer deux gobelins dans le même tour déclenche un **préavis de grève** : les survivants sautent un tour, puis reviennent à +30 % de dégâts jusqu'à la fin du combat. Le Roublard peut ouvrir une **négociation** (coût : Ferraille) pour lever le préavis. Personne n'aime payer. Tout le monde paie.

**PIÈGES HORS SERVICE.** 40 % des pièges du donjon ne fonctionnent plus. Ils portent une étiquette de maintenance datée. Les désamorcer ouvre un ticket d'incident qui rapporte de la Paperasse. Les 60 % restants fonctionnent très bien et n'ont pas d'étiquette.

**MARCHAND À LA SAUVETTE.** Vend du matériel. Le prix affiché change pendant que le joueur lit la fiche. Marchander est possible, une fois, et fait monter le prix une fois sur trois.

**LE COMMISSAIRE-PRISEUR.** Pas un ennemi. Estime le Butin Invendable. Sous-évalue de 30 à 60 %, s'en explique longuement, et a toujours raison sur le fond.

---

## PIÈCE N°7-A — STRUCTURE DE RUN, BIOMES ET BOSS

> **Correction de structure.** La version précédente de ce document annonçait « 3 étages, 1 boss » d'un côté et « 3 biomes, 6 boss » de l'autre. Avec un seul boss par run, cinq des six ne sont vus qu'au bout d'une dizaine de runs : c'est du contenu produit et jamais montré. Structure retenue : **un biome par étage, un boss à la fin de chaque étage, deux boss possibles par biome.** Soit huit formes de run distinctes, et un joueur qui a vu les six boss au bout de trois ou quatre parties.

### La colonne vertébrale : chaque boss réfute un réflexe

Un boss de roguelite qui se contente d'avoir beaucoup de points de vie enseigne au joueur ce qu'il sait déjà. Les six boss du jeu sont construits comme des **contre-exemples** : chacun casse un automatisme que le joueur vient d'acquérir.

| Boss | Biome | Réflexe réfuté |
|---|---|---|
| Le Contremaître Grzznak | Les Communs | *Tuer* |
| Dame Perrine | Les Communs | *Accumuler* |
| Le Greffier sans tête | Les Archives | *Oublier* |
| La Pile | Les Archives | *Frapper* |
| Vermicule le Terrible | Le Chantier | *Résoudre* |
| Le Seigneur Aymeric | Le Chantier | *Gagner* |

---

## PIÈCE N°7-B — BIOME 1 : LES COMMUNS

**Étage 1 · 6 à 7 salles · le donjon vu depuis les cuisines**

Ce ne sont pas les caves, ce sont les locaux de service : réserves, buanderie, couloirs du personnel, réfectoire. Le donjon fonctionne encore, à peu près, et il fonctionne à horaires fixes.

**SYSTÈME PROPRIÉTAIRE — LES HORAIRES**
Le biome tourne sur un planning affiché en haut de l'écran. Toutes les trois salles, **changement d'équipe** : les ennemis présents quittent le combat en cours et sont remplacés par une relève à pleine santé. Les pièges ne fonctionnent que pendant les heures ouvrables. Entre 12 h et 14 h, il n'y a strictement personne, les salles sont vides, et le butin aussi.

Le joueur apprend en une run à lire une pendule avant d'ouvrir une porte.

**Identité visuelle.** Vert d'eau, carrelage ébréché, affichage obligatoire punaisé partout, seaux, un torchon qui sèche. Lumière plate. **Audio :** un égouttement régulier, une cloche lointaine, et personne qui parle.

**Ennemis.** Gobelins syndiqués, rats non déclarés, le Veilleur de nuit (qui dort), la Plonge (un tas de vaisselle animé et rancunier).

---

### BOSS 1-A · LE CONTREMAÎTRE GRZZNAK
*Gobelin. Délégué du personnel. Ne se bat pas : transmet.*

**MÉCANIQUE — LA NÉGOCIATION.** Les points de vie de Grzznak ne sont pas la condition de victoire. Une piste de **Négociation** affiche quatre revendications. Le joueur peut les satisfaire — céder de la Ferraille, passer un tour, laisser un gobelin frapper sans riposter — ou refuser et se battre. En cas de combat, **tous les gobelins tués dans le biome reviennent en renfort toutes les deux salves**, indéfiniment, jusqu'à ce que le joueur accepte de discuter.

| Capacité | Effet |
|---|---|
| **Je ne fais que transmettre** | Grzznak ne subit aucun dégât ce tour. Un gobelin quelconque les prend à sa place. *« Ce n'est pas moi. C'est la base. »* |
| **Motion de soutien** | Tous les gobelins présents : +30 % de dégâts. Grzznak ne peut pas être ciblé tant qu'il en reste trois. |
| **Point d'ordre** | Interrompt l'action en cours du joueur. Une fois par combat. *« On ne peut pas décider ça sans avoir fait le tour de table. »* |

**Contre.** Beuzelin peut ouvrir la négociation avec 2 revendications déjà satisfaites. Florimond peut faire dérailler la réunion. Frère Colas ne sert à rien ici, et Grzznak le lui fera remarquer.

> *« Vous voulez vider le donjon. Très bien. Vous avez un calendrier ? »*

---

### BOSS 1-B · DAME PERRINE, INTENDANTE
*Deux cents ans de service. Zéro tolérance pour un inventaire faux.*

**MÉCANIQUE — LE RÉCOLEMENT.** Chaque tour, Perrine **confisque un consommable** du groupe et l'utilise contre lui le tour suivant. Chaque confiscation remplit sa jauge d'Inventaire ; à 100 %, elle annonce un **RÉCOLEMENT** et récupère la totalité de ses points de vie.

Le joueur qui a thésaurisé ses potions pendant tout l'étage vient de constituer l'arsenal du boss. Celui qui a tout consommé avant d'entrer affronte une vieille dame avec un trousseau de clés.

| Capacité | Effet |
|---|---|
| **Ça n'a pas été signé** | Confisque un consommable. +20 Rouspétance sur son propriétaire. *« Il y a un registre. À l'entrée. Depuis toujours. »* |
| **Sur vos mains** | 6–10 dégâts sur le rang 1. Ignore les protections. Ne peut pas être esquivée. |
| **Récolement** | Soins complets. Ne peut se déclencher qu'une fois — la seconde fois, elle renonce et s'assoit. |

**Contre.** Vider ses poches avant le combat. *Contrôle inopiné* de Beuzelin récupère la moitié du stock confisqué. *Liquidation de succession* de Gisèle transforme les biens d'un allié tombé en dégâts avant que Perrine ne mette la main dessus.

> *« Je ne vous en veux pas. Je note, simplement. »*

---

## PIÈCE N°7-C — BIOME 2 : LES ARCHIVES ENSEVELIES

**Étage 2 · 7 à 9 salles · vingt centimètres d'eau et quatre siècles de dossiers**

Sous les communs, la mémoire administrative du donjon. Des casiers jusqu'au plafond, une crue ancienne jamais résorbée, et un classement que plus personne ne comprend — sauf ceux qui y vivent encore.

**SYSTÈME PROPRIÉTAIRE — LA COTE**
Les salles ne sont pas placées, elles sont **classées**. Chaque nœud porte une cote (*4-B/17*) qui détermine réellement son contenu. Le joueur peut lire les cotes, et surtout **reclasser** : échanger les cotes de deux salles échange leur contenu. Deux reclassements par étage.

En parallèle, la **Poussière** : chaque salle traversée ajoute +1 Poussière au groupe (−1 précision par point, cumul jusqu'à 8). On s'en débarrasse uniquement dans la salle de dépoussiérage, qui n'apparaît qu'une fois par étage. C'est un minuteur souple : il ne tue personne, il rend simplement tout le monde de plus en plus mauvais.

**Identité visuelle.** Bleu-gris, papier gonflé d'humidité, reflets d'eau au plafond, étiquettes illisibles. **Audio :** clapotis, papier qui se déchire quelque part, aucune musique — seulement un bourdon.

**Ennemis.** Greffiers noyés, Dossiers animés, Chariots de classement lancés à pleine vitesse, le Silence (un ennemi qui inflige des dégâts quand un personnage parle — donc en permanence).

---

### BOSS 2-A · LE GREFFIER SANS TÊTE
*Il a perdu la tête. Surtout, il a perdu le dossier correspondant.*

**MÉCANIQUE — LA QUESTION.** Le Greffier est insensible aux dégâts tant qu'il **cherche**. Chaque tour, il pose au joueur une question factuelle sur le run en cours : *« Dans quelle salle avez-vous trouvé la lanterne ? »*, *« Combien de coffres avez-vous ouverts à cet étage ? »* Le journal de run est masqué pendant le combat. Une bonne réponse lève son immunité pendant un tour.

Les questions ne portent jamais sur plus de trois salles en arrière, et une mauvaise réponse ne coûte qu'un tour — jamais un personnage. On demande de l'attention, pas de la mémorisation.

| Capacité | Effet |
|---|---|
| **Je cherche** | Immunité totale aux dégâts pendant un tour. *« Je l'avais il y a un instant. »* |
| **Pièce manquante** | Retire au hasard un objet de l'inventaire du groupe et le classe. Récupérable en gagnant. |
| **Vous êtes sûr ?** | Après une bonne réponse, il la remet en cause. Le joueur peut maintenir — l'immunité tombe — ou se corriger, et se tromper. |

**Contre.** Josselin conserve un relevé de chaque salle et peut répondre à sa place, une fois par combat. Gisèle a tout consigné, évidemment.

> *« Ce n'est pas un piège. Je voudrais juste savoir. »*

---

### BOSS 2-B · LA PILE
*Ce n'est pas quelqu'un. C'est une pile.*

**MÉCANIQUE — LA SCISSION.** Chaque fois que La Pile subit des dégâts, elle **se scinde en deux piles plus petites**, jusqu'à occuper les quatre rangs adverses avec huit unités. Frapper est strictement contre-productif : c'est le seul boss du jeu que l'on ne peut pas tuer.

La condition de victoire est le **volume total**, réduit uniquement par le classement : piles de Procédure de Beuzelin, Relevés de Josselin, et le chariot de classement présent dans la salle, actionnable par n'importe quel personnage à la place de son action.

Un groupe composé de quatre gros frappeurs peut littéralement perdre en jouant parfaitement. C'est délibéré, c'est annoncé par le nom de la salle — *Dépôt légal* — et c'est le seul contrôle de composition du jeu.

| Capacité | Effet |
|---|---|
| **Éboulement** | 5–9 dégâts sur toute la formation. Se déclenche chaque fois que le nombre de piles augmente. |
| **Classement vertical** | Une pile avale un consommable du groupe. Il n'est pas détruit : il est classé. |
| **Appel d'air** | Les piles se réorganisent. Toutes les piles de Procédure en cours tombent. Une fois par combat. |

**Le seul boss du jeu qui n'a aucune réplique.** Aucun dialogue, aucun bark, aucun cri de victoire. Uniquement un bruit de papier. Les personnages, eux, commentent — et c'est nettement plus inquiétant sans interlocuteur.

---

## PIÈCE N°7-D — BIOME 3 : LE CHANTIER

**Étage 3 · 6 à 8 salles · mise aux normes en cours depuis 1214**

Le haut du donjon est en travaux. Il l'est depuis trois cent onze ans. Des échafaudages, des bâches, des panneaux d'information périmés, et un seul ouvrier, quelque part, qui regarde.

**SYSTÈME PROPRIÉTAIRE — LE DEVIS**
Avant chaque salle, un panneau annonce le coût et le délai de la mise en sécurité. Le joueur choisit : **payer** en Ferraille pour entrer dans une salle sécurisée — pièges neutralisés, ennemis réduits, butin réduit d'autant — ou entrer **en l'état**, avec la salle telle qu'elle est.

En parallèle, **les travaux avancent** : revenir dans une salle déjà visitée ne garantit rien. Un échafaudage s'est effondré, un passage est muré, une salle est devenue inaccessible. Le retour en arrière cesse d'être une option de repli.

**Identité visuelle.** Ocre, poussière en suspension, bâches qui claquent, panneaux jaunes, une grue en bois arrêtée en plein mouvement. Première fois du jeu qu'on voit le ciel — par un trou dans le toit. **Audio :** vent, une bâche, un marteau très loin, qui ne se rapproche jamais.

**Ennemis.** Ouvriers-squelettes en intérim, le Conducteur de travaux, les Gravats (dégâts de zone passifs), la Réunion de chantier (un combat d'élite dont personne ne sort avant huit tours).

---

### BOSS 3-A · VERMICULE LE TERRIBLE
*Dragon allergique à l'or. Techniquement, un lézard.*

Scène scriptée intégrale en **pièce n°8**, mécaniques de combat et issue administrative comprises. Il niche dans le chantier parce que « c'est plus aéré, et il y a moins d'or au mètre carré ».

**Garantie de rencontre.** Vermicule est toujours le boss du premier étage 3 d'une partie : la scène est le cœur du ton du jeu, elle ne peut pas dépendre d'un tirage.

---

### BOSS 3-B · LE SEIGNEUR AYMERIC DE FRESNES-LES-TOURBES
*Le commanditaire. Boss final de campagne, disponible dans la rotation après trois runs.*

Le donjon est vide. Le rapport est prêt. Et Aymeric comprend, trop tard, que si le donjon est vidé, sa belle-mère viendra vraiment. Il arrive à cheval pour empêcher la livraison du travail qu'il a lui-même commandé.

**MÉCANIQUE — L'ANNULATION.** Aymeric ne frappe pas. Chaque tour, il produit un **motif d'irrecevabilité** qui annule un acquis du run : un buff, un objet, le solde de La Caisse, une capacité apprise par Aubin. Les dégâts ne font que retarder l'inévitable.

Le joueur doit **invalider les motifs** : Formulaires de Beuzelin, Relevés de Josselin, *Acte authentique* de Gisèle, insultes de Florimond, *Médiation* de Colas. Quatre motifs invalidés et Aymeric doit signer le **procès-verbal de réception**.

| Capacité | Effet |
|---|---|
| **L'ordre n'était pas contresigné** | Annule un acquis du run, au choix d'Aymeric. Toujours le plus utile. |
| **Ce n'est pas ce que j'avais demandé** | Réinitialise la Rouspétance de tout le groupe à 80. *« J'avais dit débroussailler. Pas vider. »* |
| **Proposition d'embauche** | Offre un contrat permanent à un membre du groupe. Si le joueur accepte, ce personnage quitte définitivement l'effectif et le combat s'arrête là : c'est une fin, ce n'est pas la victoire. |

**Dénouement.** Aymeric signe. Le donjon est déclaré *réceptionné avec réserves*. Les réserves sont quarante mille navets.

> *« Je ne dis pas que c'est mal fait. Je dis que je n'aurais pas dû demander. »*

---

## PIÈCE N°7-E — SALLES D'ÉVÉNEMENT

> **Règle.** Une salle d'événement qui se contente de distribuer un bonus n'est pas un événement, c'est un coffre avec du texte. Chacune des dix salles ci-dessous impose **un choix dont les deux branches coûtent quelque chose**.

**1 · LE MARCHAND À LA SAUVETTE**
Le prix affiché change pendant qu'on lit la fiche. Marchander est possible une fois et augmente le prix une fois sur trois. Il propose un devis gratuit, facturé 20 Ferraille.
> *« C'est le dernier. J'en ai trois comme ça. »*

**2 · LE PUITS À VŒUX (HORS SERVICE)**
Y jeter une pièce : 60 % rien, 30 % un objet au hasard, 10 % un gobelin en sort, contrarié. Josselin peut le remettre en service — il devient alors une installation permanente du camp.
> *L'écriteau est là depuis plus longtemps que le puits.*

**3 · LA RÉUNION D'INFORMATION**
Obligatoire. Y assister coûte l'équivalent de deux salles de progression — les horaires avancent, la Poussière s'accumule — et rapporte un bonus de run permanent plus un Formulaire vierge. Partir coûte +15 Rouspétance à tout le groupe : quelqu'un le signalera.

**4 · LE COLLÈGUE**
Un aventurier d'un autre groupe, assis, ici depuis trois semaines, qui ne dira pas ce qui s'est passé. Le recruter : cinquième emplacement pour l'étage, très efficace, il repart avec 30 % du butin. L'interroger : révèle le boss de l'étage. Le laisser : il est toujours là au run suivant.

**5 · LA FONTAINE D'EAU POTABLE (ANALYSE EN COURS)**
Boire : −40 Rouspétance pour tout le monde, 25 % de chances d'un Dérangement durable. Les résultats d'analyse sont affichés à côté. Ils sont datés de 1198.

**6 · LE FORMULAIRE MURAL**
Un formulaire cloué au mur, partiellement lisible. Le remplir donne un Formulaire vierge et révèle les cotes de l'étage. Il demande le nom de jeune fille de la mère du déclarant, ce qui pose un problème à trois membres du groupe sur quatre.

**7 · LE MONTE-CHARGE**
Contrôle annuel effectué depuis jamais. L'emprunter saute deux salles — leur butin comme leur danger. 30 % de chances qu'il s'arrête entre deux étages : 15 % de PV pour tout le monde et un objet perdu. Josselin peut l'inspecter avant.

**8 · LA BOÎTE À IDÉES**
Scellée, pleine. Elle contient cinq suggestions, chacune étant une offre — un bonus, une malédiction, un échange. On peut en accepter exactement une, et il faut refuser les quatre autres à voix haute : +10 Rouspétance par refus.

**9 · LE PRÉDÉCESSEUR**
Le groupe précédent envoyé par Aymeric. Les dépouiller : bon équipement, +25 Rouspétance pour tout le monde. Les enterrer : rien, −30 Rouspétance, et Maître Gisèle gagne une Succession.
> *Personne ne demande depuis combien de temps ils sont là.*

**10 · LE CHAT DU DONJON**
Il y a un chat. C'est la seule entité du jeu dont la situation est satisfaisante. Le caresser : +20 Moral, une fois par run. Il ne peut pas être attaqué ; tenter de le faire fixe le Moral du run à zéro, définitivement. Les joueurs essaieront, et c'est prévu.

---

## PIÈCE N°7-F — OBJETS

> **Règle.** Un objet qui se contente d'un « +X % dégâts » n'est pas un objet, c'est un nombre avec une illustration. Plafond imposé : **40 % du pool peut être purement statistique**, le reste doit poser un dilemme ou dire quelque chose sur l'institution.

### Équipement — passif, un par personnage

| Objet | Effet |
|---|---|
| **Gantelet de service minimum** | −20 % dégâts subis, −10 % dégâts infligés. *« Il protège. Il ne s'investit pas. »* |
| **Bottes de fonction** | +3 initiative. Le porteur ne peut plus quitter le rang 1. *« Fournies avec le poste. Non reprises. »* |
| **Plastron réformé** | +25 PV maximum. Se brise définitivement au premier critique reçu. *« Il a été retiré du service pour une raison. »* |
| **Lorgnon du commissaire-priseur** | Révèle la valeur réelle du butin avant estimation. *« On voit tout de suite qu'on se fait avoir. C'est déjà ça. »* |
| **Écharpe de fonction** | +15 % dégâts. Le porteur parle deux fois plus : tous les autres, +3 Rouspétance par tour. |

### Consommables

| Objet | Effet |
|---|---|
| **Ration réglementaire** | Soigne 30 %. Goût : aucun. *« Conforme. »* |
| **Petit vin de table** | −40 Rouspétance, −2 précision pendant 3 tours. |
| **Sifflet de fin de journée** | Met fin au combat en cours. Aucun butin. Une fois par run. |
| **Bandage approximatif** | Soigne 20 %. 20 % de chances d'infecter : −5 PV par tour pendant 3 tours. |
| **Pot-de-vin** | Un ennemi quitte le combat. Il reviendra, plus cher. |
| **Trombone** | Répare n'importe quoi, une fois. Littéralement n'importe quoi. *« Personne ne pose de questions sur le trombone. »* |

### Documents — la catégorie signature

| Objet | Effet |
|---|---|
| **Formulaire vierge** | Matière première : D-12, réclamations, mises en demeure. Trois exemplaires suppriment un boss. |
| **Ordre de réquisition** | Prend un objet chez le marchand sans payer. Le marchand le note. |
| **Attestation sur l'honneur** | Annule un effet négatif. N'est vérifiée par personne. *« Elle est vraie parce qu'elle est signée. »* |
| **Copie conforme** | Duplique un autre document. Ne fonctionne pas sur elle-même, et tout le monde a essayé. |
| **Note de service n°4417** | Illisible. Effet aléatoire tiré parmi douze à chaque combat. *« Personne ne l'a lue. Tout le monde l'applique. »* |
| **Procuration** | Un personnage joue le tour d'un autre. Le mandant gagne +20 Rouspétance. |

### Reliques de camp — permanentes, achetées en Paperasse

| Objet | Effet |
|---|---|
| **La pendule du réfectoire** | Révèle les horaires du biome 1. *« Elle avance de onze minutes. Depuis toujours. »* |
| **Le registre d'entrée** | Dame Perrine ne peut plus confisquer qu'un objet par combat. |
| **Le chariot de classement personnel** | Réduit passivement le volume de La Pile de 10 % par tour. |
| **La clé des communs** | Ouvre une salle supplémentaire par étage. |
| **Le panneau « ne pas déranger »** | Annule la première Engueulade de chaque run. Beaucoup de joueurs le revendront. |

---

## PIÈCE N°8 — SCÈNE DE BOSS : VERMICULE LE TERRIBLE

> **Salle 12 — LE TRÉSOR** *(classé insalubre par arrêté seigneurial)*
> **VERMICULE LE TERRIBLE** — Dragon. Techniquement.

---

*Le couloir débouche sur une salle immense. Au centre, un tas d'or. Sur le tas d'or, un dragon. Le dragon a les yeux gonflés, le museau à vif, et une serviette nouée autour du cou.*

**VERMICULE** *(nasillard)* — Halte ! Qui ose pénétrer dans l'antre de Vermicule le Terrible, fléau des cieux, dévoreur de— *(il inspire)* — de— *(il inspire encore)*

**GUÉRIN** — Il va éternuer.

**FLORIMOND** — Il ne va pas éternuer.

*VERMICULE éternue. Une gerbe de flammes traverse la salle. Tout le monde plonge au sol, sauf ODON, qui n'a pas suivi.*

**ODON** — Pourquoi tout le monde est par terre ?

**GUÉRIN** — Ta manche brûle.

**ODON** — Ah.

**VERMICULE** — Pardon. Pardon. C'est l'or.

**BEUZELIN** — Comment ça, c'est l'or ?

**VERMICULE** — Je suis allergique à l'or.

*Un silence.*

**FLORIMOND** — Vous êtes un dragon.

**VERMICULE** — Oui.

**FLORIMOND** — Vous dormez sur un tas d'or.

**VERMICULE** — Oui.

**FLORIMOND** — Et vous êtes allergique à l'or.

**VERMICULE** — Écoutez, ce n'est pas moi qui fais les règles.

**BEUZELIN** — Qui fait les règles ?

**VERMICULE** — La Convention. Article 4. *« Tout dragon reconnu constitue et maintient un amoncellement de métal précieux d'une valeur minimale de quarante mille pièces. »* En dessous, je perds le statut.

**GUÉRIN** — Et alors ?

**VERMICULE** — Et alors je redeviens un lézard. Un gros lézard. Avec une grotte.

**ODON** — C'est pas si différent.

**VERMICULE** *(long silence)* — Non. C'est très différent.

**BEUZELIN** *(sortant un document)* — Vous avez déposé une inaptitude ?

**VERMICULE** — Une quoi ?

**BEUZELIN** — Formulaire D-12. Aménagement du poste pour allergie professionnelle. Vous pouvez demander la substitution de l'or par un matériau de valeur équivalente. Le cuivre, typiquement.

**VERMICULE** — … On peut faire ça ?

**BEUZELIN** — On peut tout faire. Il faut le demander par écrit. En trois exemplaires. Avant le 31.

**VERMICULE** — Le 31 de quoi ?

**BEUZELIN** — C'est ce qui bloque, oui.

*VERMICULE se redresse lentement. Pour la première fois depuis quatre cents ans, il a de l'espoir. C'est une émotion qu'il gère mal.*

**VERMICULE** — Trois exemplaires. Je peux avoir trois exemplaires.

**FLORIMOND** — Moi je dis ça, je dis rien, mais vous avez surtout une tête de cheminée mal ramonée.

**GUÉRIN** — Florimond.

**FLORIMOND** — Je constate.

**GUÉRIN** — Tu ne constates jamais. Tu commentes.

**ODON** — Attendez. Attendez. J'ai une idée.

**GUÉRIN** — Non.

**ODON** — Si je transforme l'or en légume, il n'y a plus d'allergène.

**GUÉRIN** — Non.

**BEUZELIN** — Techniquement il n'a pas tort.

**GUÉRIN** — Il a toujours tort. C'est sa fonction.

*ODON lève les mains. Un éclair verdâtre. Le tas d'or devient un tas de navets. Quarante mille pièces de navets.*

*Silence.*

**VERMICULE** *(très calme)* — Qu'est-ce que vous avez fait.

**ODON** — Vous respirez mieux, non ?

**VERMICULE** — Je respire très bien. Je suis un lézard. *(un temps)* Je suis un lézard avec une grotte.

**FLORIMOND** — Et quarante mille navets.

**VERMICULE** — **ET QUARANTE MILLE NAVETS.**

**GUÉRIN** *(dégainant, sans se presser)* — Voilà. On y est.

**BEUZELIN** — Je note que j'étais contre.

**FLORIMOND** — Tu n'étais pas contre.

**BEUZELIN** — Je le note quand même.

**→ COMBAT**

---

### Mécaniques du combat

**Phase 1 — Congestionné.** Vermicule télégraphie **L'ÉTERNUEMENT** sur deux tours (animation d'inspiration, impossible à manquer). À la détente : dégâts sur toute la formation, sauf si un personnage occupe seul le rang 1 — il encaisse tout, les autres sont épargnés. C'est la mécanique de Guérin, et c'est la seule fois où « Je prends » n'est pas une pose.

**Phase 2 — Urticaire.** À 60 % de PV, les navets commencent à repousser en or. Chaque tour, une pile d'or réapparaît : Vermicule gagne +10 % de dégâts et subit 5 dégâts de sa propre allergie. Le joueur peut détruire les piles — mais chaque pile détruite, c'est du butin en moins à la fin.

**Phase 3 — Demande de reclassement.** À 25 %, Vermicule cesse d'attaquer un tour pour rédiger une réclamation. S'il la termine, il soigne 30 %. L'interrompre demande 3 actions offensives dans le tour.

### Résolution administrative (issue alternative)

Si **Beuzelin est vivant** et que le joueur détient **3 Formulaires vierges** (ramassés dans les salles d'archives du run), le D-12 peut être déposé avant le déclenchement du combat. Vermicule obtient sa substitution cuivre, quitte le donjon, et devient **fournisseur du camp** : −20 % sur toutes les réparations de la Forge Approximative, de façon permanente.

Le joueur qui découvre cette issue a compris le jeu : le jeu récompense la paperasse, pas le courage. C'est le message, et il est chiffré.

---

## PIÈCE N°9 — PRODUCTION

| Poste | Hypothèse |
|---|---|
| **Moteur** | Godot 4 (2D) — pipeline léger, pas de besoin 3D |
| **Direction artistique** | Marionnettes de papier découpé, attaches parisiennes visibles aux articulations. L'animation est volontairement raide : le monde entier est monté à l'économie |
| **Palette** | Papier administratif vert d'eau, encre de tampon violette, crayon rouge de correction |
| **Audio** | Cuivres grinçants, cordes pincées, et un seul instrument par personnage. La musique s'arrête net pendant les engueulades |
| **Équipe** | 5–7 personnes, 24–30 mois |
| **Contenu** | 4 classes au lancement (+4 en déblocage méta), 3 biomes, 6 boss (2 par biome), ~2 800 lignes |
| **Localisation** | FR et EN **co-écrits**, jamais traduits. Budget d'écriture dédié par langue, pas de ligne de traduction |

---

## PIÈCE N°10 — RISQUES

| Risque | Gravité | Mitigation |
|---|---|---|
| **La blague s'use au run 3** | Critique | Barks écrits par *état* et non par événement ; verrouillage 3 runs ; le silence comme option valide |
| **L'Engueulade est perçue comme arbitraire** | Critique | Le joueur choisit : deux options déterministes annoncées, le dé uniquement sur demande explicite |
| **« C'est Darkest Dungeon en moins bien »** | Élevé | Runs de 30 min contre 60+, aucun stress persistant entre les runs, ton diamétralement opposé. Le pitch marketing doit attaquer par la comédie, pas par la tactique |
| **La traduction tue l'humour** | Élevé | Co-écriture, pas de traduction. Si le budget ne le permet pas : sortir en une seule langue |
| **La comédie ne se vend pas en trailer** | Moyen | Le trailer d'annonce montre **une engueulade complète**, du déclencheur au résultat. C'est le seul argument de vente qui ne se résume pas |
| **Le joueur ne comprend pas que l'issue administrative existe** | Moyen | Beuzelin commente les formulaires ramassés. Trois fois. Il est insupportable à ce sujet. C'est le tutoriel |

---

---

## PIÈCE N°11 — CE QU'ON CODE, ET DANS QUEL ORDRE

> **Constat.** Ce document fait maintenant une trentaine de pages et le jeu a été joué zéro minute. Sa thèse centrale — *une dispute entre alliés est plus intéressante qu'un combat* — n'est vérifiée par personne. Tant qu'elle ne l'est pas, les biomes, les boss, les objets et les huit classes sont du décor posé sur du vide.

### Prototype 01 — « Le banc d'essai » *(1 à 2 semaines)*

**Question unique à laquelle il doit répondre :** l'Engueulade est-elle amusante ?

**Ce qu'il contient.** Un combat. Quatre personnages, trois gobelins, quatre rangs, deux capacités par personnage, la jauge de Rouspétance, l'Engueulade avec ses trois choix, la table d8, et une quarantaine de répliques contextuelles.

**Ce qu'il ne contient pas, et c'est le plus important.** Pas de génération procédurale. Pas de carte. Pas de camp. Pas de méta-progression. Pas de biome. Pas de boss. Pas d'art. Des rectangles gris et des chiffres visibles.

**Critère d'arrêt.** Cinq personnes y jouent trois combats chacune, sans explication préalable. Si moins de trois d'entre elles relisent spontanément le journal de combat pour retrouver une réplique, la mécanique ne porte pas le jeu. On ne l'ajuste pas : on la remplace, et ce document est à réécrire.

### Ordre de bataille

| Étape | Durée | Question posée | Abandonné si |
|---|---|---|---|
| **P01 — Banc d'essai** | 1–2 sem. | L'Engueulade est-elle amusante ? | Personne ne relit les répliques |
| **P02 — Le run** | 3–4 sem. | Trente minutes tiennent-elles ? | L'ennui apparaît avant l'étage 3 |
| **P03 — Le camp** | 2 sem. | Veut-on repartir ? | Le joueur s'arrête après une défaite |
| **P04 — La verticale** | 6 sem. | Un étage complet, avec art et son | — |

Rien ne commence tant que l'étape précédente n'a pas répondu. Un prototype qui échoue a fait son travail ; un prototype qu'on refuse d'abandonner a coûté un an.

### Le choix technique, et pourquoi il n'est pas encore à faire

Godot reste le moteur de production. Mais **le prototype 01 ne doit pas être fait dans le moteur de production** : on teste ici du rythme, du texte et une table de résultats, pas du rendu. Une page web se modifie en quinze secondes et se fait tester par un lien envoyé le soir même. Le moteur se choisit à l'étape P02, quand la question devient « est-ce que ça tient trente minutes ».


*Document de travail. Ne constitue pas un engagement contractuel. Établi en trois exemplaires, dont deux ont été perdus.*
