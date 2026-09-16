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
