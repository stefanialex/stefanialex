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

## PIÈCE N°3 — BOUCLE DE JEU

### Vue d'ensemble (un run = 25 à 40 minutes)

**0. L'ORDRE DE MISSION** *(~40 s)*
Le seigneur Aymeric de Fresnes-les-Tourbes dicte l'objectif à un scribe qui n'écoute pas. Les motifs sont générés et systématiquement dérisoires : sa belle-mère arrive et le donjon « gâche la vue depuis la salle à manger » ; il y a un problème d'écoulement ; les gobelins font du bruit le dimanche ; il a promis à quelqu'un, il ne sait plus à qui. L'objectif réel (3 étages, 1 boss) est identique — seule la justification change, et elle conditionne le **modificateur de run**.

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
| **Contenu** | 4 classes au lancement (+4 en déblocage méta), 3 biomes, 6 boss, ~2 800 lignes |
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

*Document de travail. Ne constitue pas un engagement contractuel. Établi en trois exemplaires, dont deux ont été perdus.*
