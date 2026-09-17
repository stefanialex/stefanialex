# Chaîne de fabrication — qui fait quoi

Les postes d'une équipe de jeu vidéo, et pour chacun : ce qu'une chaîne d'agents
fait réellement, ce qu'elle fait mal, et ce qui reste humain.

**Principe directeur.** Des agents sont excellents pour le **volume**, la
**vérification**, la **cohérence** et l'**équilibrage**. Ils sont mauvais pour
avoir une **voix**. Toute étape créative fonctionne donc en deux temps :
surproduction par des agents, puis **filtre impitoyable** — jamais de livraison
directe de ce qu'un agent a écrit.

---

## Les postes

| Poste | Automatisation | État |
|---|---|---|
| **Direction créative** | ✗ humain | Le ton, les arbitrages, le goût. Non délégable |
| **Game design** | ◑ mixte | Agents pour la recherche et l'analyse concurrentielle ; décisions humaines |
| **Écriture** | ◑ mixte | Atelier automatisé : 4 auteurs → 4 script-doctors → 1 chef de studio. **Le filtre fait le travail, pas la génération** |
| **Programmation** | ● agents | Fonctionne bien, à condition d'un contrôle automatique derrière |
| **QA / blocages** | ● agents | `outils/simulateur.js`. Trouve les blocages avant les humains |
| **Équilibrage** | ● agents | Même outil : taux de victoire, durée, fréquence des mécaniques |
| **Art** | ✗ humain | Plafond atteint sur du SVG écrit à la main. Au-delà : illustrateur + animateur |
| **Audio** | ◑ mixte | Effets synthétisés faisables ; musique et voix, non |
| **Localisation** | ✗ humain | Co-écriture, jamais traduction. L'humour ne survit pas au transfert |
| **Production** | ✗ humain | Arbitrage de périmètre et de budget |

---

## Les deux boucles automatisées

### Boucle 1 — Atelier d'écriture

```
4 AUTEURS  (un par personnage, voix spécifiée, surproduction assumée)
     ↓        sans barrière : chaque personnage avance à son rythme
4 SCRIPT-DOCTORS  (coupent ~50 %, une ligne sans angle saute)
     ↓
1 CHEF DE STUDIO  (voix trop proches, redites de structure, corpus final)
```

**Ce qui fait la qualité, c'est l'étage du milieu.** Un auteur-agent produit du
correct ; un doctor-agent payé pour dire non élimine le correct-mais-plat. Le
critère est unique et vérifiable : *cette ligne a-t-elle un angle — retournement,
décalage de registre, ou chute ?* Un constat n'est pas une blague.

### Boucle 2 — Simulateur de parties

```sh
cd outils && npm install && node simulateur.js 20
```

Joue N parties sans écran et répond à trois questions, dans cet ordre :

1. **Y a-t-il un blocage ?** Trouvé en secondes, là où un testeur humain le
   trouve en pleine soirée.
2. **La mécanique testée se déclenche-t-elle ?** Un instrument qui ne déclenche
   pas le phénomène qu'il mesure ne mesure rien. C'est l'erreur qui a invalidé le
   premier test extérieur.
3. **Quelles répliques ne sortent jamais ?** Un pool jamais déclenché est du
   travail payé et jamais vu.

Sort en code d'erreur 1 si le build ne doit pas être livré.

---

## Relevé du build 12 — 8 parties simulées

| Mesure | Valeur | Lecture |
|---|---|---|
| Parties bloquées | 0/8 | ✓ |
| Erreurs JS | 0 | ✓ |
| Engueulades par partie | 1,75 | ✓ la mécanique se déclenche enfin |
| Répliques par partie | 68 | ✓ densité correcte |
| Tours par partie | 6,1 | ⚠ au-dessus de la cible de 3 à 5 |
| **Taux de victoire** | **100 %** | ✗ **aucune tension** |
| **Répliques jamais vues** | **117 sur 219** | ✗ **plus de la moitié du travail est invisible** |

**Les deux derniers points sont les vrais problèmes du build, et aucun testeur ne
les aurait formulés ainsi.**

- **100 % de victoires** : le joueur ne risque rien, donc il ne ressent rien, donc
  il décroche à trois minutes. La difficulté doit monter avant toute chose.
- **117 répliques jamais déclenchées** : les pools de raté ne sortent pas parce
  que le groupe rate peu — et il rate peu parce que le combat est trop facile. Le
  même défaut produit les deux symptômes.

> Corollaire pour l'écriture : **écrire plus de répliques ne sert à rien tant que
> l'équilibrage ne les fait pas sortir.** L'atelier d'écriture produit du matériel
> ; c'est l'équilibrage qui décide si quelqu'un le verra.

---

## Ordre de travail

1. **Équilibrage d'abord.** Descendre le taux de victoire vers 55-65 %, ramener le
   combat à 3-5 tours, faire monter la fréquence des ratés.
2. **Puis intégrer le corpus** issu de l'atelier.
3. **Puis retester** avec le protocole du journal de bord, sur une version dont
   le simulateur dit qu'elle est livrable.

Faire l'inverse — écrire d'abord — revient à remplir un réservoir percé.
