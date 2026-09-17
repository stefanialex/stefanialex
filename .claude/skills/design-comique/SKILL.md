---
name: design-comique
description: Règles de conception pour un jeu tactique comique — rythme de combat, jauges qui craquent, budget de répétition des répliques, mécanismes du comique français et administratif, contraintes de droit d'auteur. À charger avant toute décision de game design, d'équilibrage ou d'écriture de dialogue sur Donjon & Paperasse, et avant d'écrire ou de retoucher un pool de répliques.
---

# Concevoir un jeu tactique comique

Règles tirées de tests réels et d'une analyse documentée de Darkest Dungeon et du
jeu Naheulbeuk. Elles priment sur l'intuition. Quand une demande les contredit,
le dire avant d'exécuter.

## 1. Le rythme tactique et le rythme comique sont antagonistes

La tactique demande de la délibération, la comédie demande de l'enchaînement.
On ne peut pas emprunter les deux.

- **Combat : 3 à 5 tours.** Au-delà, chaque blague meurt. Référence : Darkest
  Dungeon tourne à 4-5 tours par combat.
- **La tension vit ENTRE les combats**, pas dans leur durée : ressources qui se
  vident, effectif consommable, conséquences persistantes.
- **Ne jamais rallonger un combat pour ajouter de la profondeur.** Ajouter de la
  conséquence.
- Le reproche numéro un fait au jeu Naheulbeuk est la « dissonance de rythme :
  un combat lent et sérieux qui contredit le ton comique ». C'est le piège
  structurel du genre. Personne ne l'a résolu.

## 2. Une jauge qui craque doit avoir deux issues, pas une

Darkest Dungeon : à 100 de stress, **75 % d'Affliction, 25 % de Vertu**.

- Sans issue heureuse, une jauge n'est qu'une punition : le joueur apprend à
  l'éviter au lieu de la chercher.
- **Garder le ratio asymétrique, autour de 1 sur 4.** La rareté crée l'histoire
  qu'on raconte.
- **Toute jauge qui craque doit laisser au joueur un bouton pour réagir au tour
  suivant.** L'échec de Darkest Dungeon II est une spirale fermée qui
  s'auto-alimente sans levier de sortie : subie, donc plus drôle.

## 3. La jauge doit retourner le personnage contre le joueur

Modifier des chiffres est tiède. Un personnage qui **refuse un soin, refuse une
cible, recule tout seul, vole un allié** est une blague *jouée*, pas écrite.
C'est le meilleur moteur comique disponible, et il ne coûte rien en écriture.

Faire craquer, ne pas tuer.

## 4. Budget de répétition des répliques

Contre-intuitif mais documenté : **la citation naît de la répétition.** On ne
retient pas ce qu'on entend une fois. Le narrateur de Darkest Dungeon est
mémétique parce qu'il se répète.

- **5 à 8 variantes minimum** par déclencheur fréquent.
- **Temps de latence par ligne**, pas verrouillage définitif.
- **10 à 15 % du pool** réservé à des déclencheurs rares, pour récompenser les
  vétérans.
- Se taire plutôt que se répéter est une erreur.

## 5. Deux régimes de réplique, jamais un seul

- **Éclair** — réactions courtes (raté, critique, mise à mort, pillage). La
  bulle apparaît, **le jeu continue**, elle s'efface seule.
- **Bloquant** — rupture de jauge, mort, franchissement de palier, ouverture et
  fin. Là on s'arrête.

Et **commenter moins** : environ un tiers des événements fréquents passent en
silence. Tout souligner revient à ne rien souligner.

## 6. Donner une intention au hasard

Un échec commenté devient une scène. Un échec silencieux devient une injustice.
C'est le levier le plus rentable de tout Darkest Dungeon, et il s'applique
directement au ressort comique de l'échec.

## 7. L'humour est systémique, pas cinématique

Les commentaires se déclenchent sur l'action du joueur — et notamment sur ce
qu'il **ne fait pas**. Approche validée par les deux jeux de référence.

## 8. Les mécanismes comiques exploitables

Structures, pas textes. Les plus productifs pour un jeu :

| Mécanisme | Transposition ludique |
|---|---|
| La boucle impossible | A exige B qui exige A |
| Le contre-formulaire | Inventer une pièce qui n'existe pas ; le système se détruit à la chercher |
| La règle absurde exécutée gravement | Le rire vient du sérieux de l'exécutant |
| L'horaire souverain | L'urgence s'écrase contre la fermeture du guichet |
| Le zèle qui produit l'inverse | Appliquer parfaitement la mission cause le dommage qu'elle prévenait |
| La double hiérarchie | Deux ordres incompatibles, fautif dans les deux cas |
| Le décalage registre / enjeu | L'épique en langage de bureau, ou l'inverse |
| L'escalade réparatrice | Chaque tentative de correction aggrave d'un cran |
| L'inertie vertueuse | Ne rien faire, présenté comme la plus haute forme du devoir |
| La responsabilité liquide | Personne n'a dit non. Personne n'a dit oui |

**L'axe a bougé** : l'humour sur le fonctionnaire s'essouffle, la veine
productive est l'entreprise — réunions sans objet, jargon, indicateurs.

## 9. Le méta, précisément dosé

L'humour rôliste est méta par nature : il empile joueur, personnage, règle et
fiction, et chaque décalage entre deux niveaux est comique.

- **Interdit** : le clin d'œil au joueur, la mention des dés, des points de vie,
  des statistiques de jeu.
- **Autorisé et recommandé** : les personnages traitent les règles de leur
  propre monde comme des règles de jeu — ils contestent un arbitrage, invoquent
  une jurisprudence, discutent d'un cas non prévu au règlement.

## 10. Droit d'auteur

**Aucune réplique d'œuvre protégée**, ni citée, ni adaptée, ni déguisée. Le droit
français n'a pas d'équivalent au *fair use* et l'exception de courte citation ne
couvre pas un jeu commercial. Un éditeur fera l'audit avant signature.

Les **mécanismes** s'empruntent librement. Le domaine public — Courteline,
Allais, Jarry, Labiche, Feydeau — s'étudie sans limite, comme modèle de rythme
de phrase et de construction de scène.

## 11. Avant de livrer une modification de gameplay

- Faire tourner le pilote automatique headless (`/tmp/harn/run.js` ou équivalent
  jsdom) : aucune partie ne doit se bloquer, et la mécanique testée doit se
  déclencher au moins une fois par partie.
- **Un instrument qui ne déclenche pas le phénomène qu'il mesure ne mesure
  rien.** Vérifier la fréquence avant de conclure quoi que ce soit d'un test.
- Afficher un numéro de build : un retour de test ne vaut rien si on ignore
  quelle version a été jouée.
