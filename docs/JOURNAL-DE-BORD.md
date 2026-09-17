# Journal de bord — Donjon & Paperasse

Mémoire du projet. Ce qui a été décidé, ce qui a été testé, ce qui a échoué et
pourquoi. **À relire avant toute nouvelle session, et à compléter après chaque
test.** Un projet qui perd la mémoire de ses échecs les répète.

Format : on n'écrit ici que des faits vérifiés et des décisions actées. Les idées
vont dans le GDD, pas ici.

---

## 1. Statut au 17 septembre 2026

| | |
|---|---|
| **Étape** | P01 — banc d'essai, build 12 |
| **Question testée** | L'Engueulade est-elle amusante ? |
| **Réponse à ce jour** | **Toujours pas obtenue.** Aucun test valide n'a encore eu lieu |
| **Bloqueur** | Les deux sessions de test ont porté sur des versions où la mécanique testée ne se déclenchait pas |

---

## 2. Ce qui a été testé, et ce que ça a donné

### Test 1 — Lapinus, build ~9

```
6 tours · 3 min · 4 survivants sur 4 · 1 raté
14 répliques affichées, 14 lues (100 %) · journal rouvert : oui
Engueulades : 0
Réplique citée : AUCUNE · Décrochage : au milieu · Relancerait : non
« pas très drôle les interventions des personnages mais le concept reste à creuser »
```

**Lecture.** Test **invalide** sur sa question : zéro engueulade, donc le sujet du
jeu n'a jamais été montré. Mais deux signaux réels et durs :
1. 14 répliques lues à 100 %, journal rouvert, **zéro retenue**.
2. Décrochage à 3 minutes.

### Test 2 — l'auteur du projet, build antérieur au 12

« C'est lent, aucune engueulade, pas de rythme, l'humour est plat. »

**Lecture.** Probablement une version périmée (fichier Netlify ou cache). C'est
ce qui a motivé l'affichage d'un numéro de build. Les deux autres griefs sont
fondés et ont été corrigés.

---

## 3. Erreurs commises, leur cause, et la règle qui en sort

| Erreur | Cause réelle | Règle adoptée |
|---|---|---|
| Blocage de partie au tour de Florimond | Toutes ses capacités avaient un coût ; à ressource nulle, aucune action possible | **Chaque classe doit avoir au moins une action gratuite.** Plus un filet « passer le tour » universel |
| Zéro engueulade sur le premier test | Jauges trop basses au départ, gains trop faibles, combat trop court | **Un instrument qui ne déclenche pas le phénomène qu'il mesure ne mesure rien.** Vérifier la fréquence avant de conclure |
| « C'est lent, pas de rythme » | Densité de dialogue multipliée par 5 sans changer le modèle de rythme : tout bloquait | **Deux régimes obligatoires** — éclair et bloquant. Et commenter moins |
| Répliques plates (« Il avait des bottes. Il n'en a plus. ») | Constat sans retournement. Lots écrits vite en fin de session | **Toute réplique a besoin d'un angle** : retournement, décalage de registre, ou chute. Un lot écrit à la chaîne se relit |
| Torches qui « se baladaient » | `transform-origin` sur un élément SVG se résout sur le viewBox sans `transform-box: fill-box` | Vérifier les transformations SVG sur cible réelle |
| Test sur version périmée | Aucun moyen de savoir quelle version était jouée | **Numéro de build affiché en permanence** |

---

## 4. Décisions actées

| # | Décision | Motif |
|---|---|---|
| D01 | L'Engueulade se résout sur un **choix du joueur**, pas un dé imposé | Un dé au pic de tension dans un jeu tactique se lit comme une punition |
| D02 | Titre verrouillé : **Donjon & Paperasse** | Fonctionne aussi en anglais — réduit le risque de localisation |
| D03 | **Aucune réplique d'œuvre protégée**, jamais | Droit français, pas de *fair use*. Audit éditeur avant signature |
| D04 | Un biome par étage, **un boss par étage**, deux boss possibles par biome | Sinon cinq boss sur six ne sont jamais vus |
| D05 | Chaque classe déblocable **confisque un système orphelin**, sans hausser le plafond de puissance | Sinon les quatre classes de départ deviennent obsolètes |
| D06 | **Combats de 3 à 5 tours** | Rythme tactique et rythme comique sont antagonistes (voir §5) |
| D07 | L'Engueulade se scinde : **75 % Dispute, 25 % Sursaut** | Sans issue heureuse, une jauge n'est qu'une punition |
| D08 | **La citation naît de la répétition** — 5 à 8 variantes par déclencheur, latence par ligne | Renverse la règle initiale « se taire plutôt que se répéter » |
| D09 | Méta autorisé **à l'intérieur de la fiction** seulement | L'humour rôliste est méta par nature ; l'interdire tuait le moteur |
| D10 | Les personnages **démarrent avec de la Rouspétance** | Met la jauge à portée, et c'est juste : ils ont déjà eu une journée |

---

## 5. Le fait le plus important du projet

> **Le rythme tactique et le rythme comique sont antagonistes.**
> La tactique demande de la délibération, la comédie demande de l'enchaînement.

Documenté sur un concurrent direct — *Le Donjon de Naheulbeuk : L'Amulette du
Désordre* (2020), Metacritic ~72 — dont les deux critiques dominantes sont, mot
pour mot, les deux retours de nos propres testeurs : **l'humour s'use** et **le
combat est lent**, avec la formule « dissonance de rythme entre un combat lent et
sérieux et un ton comique ».

**Personne n'a résolu ce problème.** C'est simultanément la raison d'abandonner
et la seule vraie opportunité du projet.

---

## 6. Ce qui ne marche pas, à ce jour

- **L'humour ne s'accroche pas.** Un testeur extérieur, 14 répliques lues
  intégralement, journal rouvert, aucune citation. Non résolu.
- **Les figurines et la scène ne font pas « jeu ».** Plafond atteint sur du SVG
  écrit à la main ; au-delà c'est un illustrateur et un animateur.
- **La Rouspétance ne fait que modifier des chiffres.** Elle doit retourner le
  personnage contre le joueur — refuser un soin, une cible, un rang. Non
  implémenté.
- **Aucune donnée sur la rentabilité du genre.** Les ventes des deux jeux
  Naheulbeuk sont introuvables.

## 7. Ce qui marche, à ce jour

- La **structure de l'Engueulade** avec ses trois choix : validée par l'échec de
  Darkest Dungeon II, dont la spirale fermée n'offrait aucun levier de sortie.
- Les **gobelins syndiqués** en incarnation du guichet : le registre le plus sûr
  du document.
- La **scène de Vermicule**, qui applique sans le savoir le mécanisme de
  l'escalade réparatrice.
- Le **rapport d'incident** en fin de partie : produit des données exploitables
  au lieu de politesses.

## 8. Ce qui reste à prouver, par ordre d'urgence

1. Un testeur extérieur peut-il **citer une réplique**, journal fermé, après
   trois combats sur une version où l'Engueulade se déclenche ?
2. Le combat de 3 à 5 tours tient-il tactiquement, ou devient-il trivial ?
3. Le Sursaut à 25 % produit-il le souvenir attendu ?
4. Le genre est-il rentable ? *(aucune donnée)*

---

## 9. Protocole de test — à ne pas assouplir

1. Rythme **Manuel**. Sinon on mesure une vitesse de lecture.
2. **Aucune explication** préalable. Si le testeur demande quoi faire, c'est un
   résultat.
3. **Trois combats.** La blague a une demi-vie ; c'est au troisième qu'on voit.
4. Une seule question : **« cite-moi une réplique »**, journal fermé. Jamais
   « c'était bien ? », qui ne produit que de la politesse.
5. **Le test de l'auteur ne compte pas.** Il reconnaît ses propres blagues.
6. Des amis dans une pièce rient par contagion : noter **qui rit le premier**.
7. Vérifier le **numéro de build** avant de commencer.
