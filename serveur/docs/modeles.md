# Choisir et gérer les modèles

---

## Le principe : tout tient dans la mémoire, ou rien ne va vite

Un modèle de langage doit être entièrement chargé en mémoire pour répondre. La
question n'est donc pas « ce modèle est-il bon » mais « ce modèle tient-il dans
ma mémoire ».

Deux mémoires, dans cet ordre de préférence :

1. **La VRAM du GPU** — rapide. Un modèle qui y tient répond en quelques secondes.
2. **La RAM système** — dix à cinquante fois plus lente, mais fonctionnelle.

Quand un modèle déborde de la VRAM, une partie bascule en RAM et la vitesse
s'effondre. Mieux vaut un modèle plus petit qui tient entièrement qu'un gros
modèle à moitié déchargé.

---

## Les quantisations

Un modèle « 8B » compte 8 milliards de paramètres. En pleine précision, chacun
occupe 2 octets, soit 16 Gio — hors de portée de la plupart des machines.

La quantisation réduit la précision de chaque paramètre. C'est ce qui rend
l'exécution locale possible.

| Suffixe | Taille pour un modèle 8B | Qualité |
|---|---|---|
| `Q8_0` | ~8,5 Gio | Quasi identique à l'original |
| `Q6_K` | ~6,6 Gio | Perte imperceptible |
| `Q5_K_M` | ~5,7 Gio | Très bon compromis |
| `Q4_K_M` | ~4,9 Gio | **Le choix par défaut** — perte réelle mais faible |
| `Q3_K_M` | ~4,0 Gio | Dégradation visible |
| `Q2_K` | ~3,2 Gio | À éviter sauf contrainte forte |

Règle utile : **un modèle plus gros en Q4 bat presque toujours un modèle plus
petit en Q8**, à mémoire égale. Un 14B en Q4 est meilleur qu'un 8B en Q8.

Ollama sert du Q4_K_M par défaut quand aucune quantisation n'est précisée.

---

## Quel modèle pour ta machine

| Mémoire disponible | Taille | Exemple de commande |
|---|---|---|
| 4–6 Gio | 3–4B | `ollama pull llama3.2:3b` |
| 6–10 Gio | 7–8B | `ollama pull hermes3:8b` |
| 12–16 Gio | 14B | `ollama pull qwen2.5:14b` |
| 24 Gio et + | 32B | `ollama pull qwen2.5:32b` |
| 48 Gio et + | 70B | `ollama pull hermes3:70b` |

« Mémoire disponible » = la VRAM s'il y a un GPU, sinon environ la moitié de la
RAM installée.

---

## Les modèles Hermes

Hermes est une famille de modèles publiée par **Nous Research**, construite en
réentraînant des modèles ouverts (Llama, Qwen) sur des jeux de données orientés
suivi d'instructions et appel d'outils.

Leur intérêt ici : ils sont réputés pour le **function calling** — la capacité à
produire des appels d'outils structurés plutôt que du texte libre. C'est ce qui
fait la différence entre un modèle qui discute et un modèle utilisable comme
agent, capable de piloter des outils.

```bash
ollama pull hermes3:8b       # Le point de départ raisonnable
ollama pull hermes3:70b      # Si la machine suit
```

`03-ia.sh` essaie plusieurs variantes dans l'ordre de préférence et retient la
première réellement disponible. Les noms dans le registre changent au fil des
versions ; si aucune ne passe, cherche les variantes actuelles :

```bash
# Voir ce qui existe
# https://ollama.com/search?q=hermes
ollama pull <nom-trouvé>
```

Rien n'oblige à rester sur Hermes. À taille égale, `qwen2.5` et `llama3.1` sont
d'excellentes alternatives, souvent meilleures en français. Le plus simple est
d'en installer deux ou trois et de comparer sur tes propres questions — c'est le
seul test qui compte.

---

## Commandes utiles

```bash
ollama list                     # Modèles installés et leur taille
ollama ps                       # Modèles actuellement chargés en mémoire
ollama run hermes3:8b           # Discuter en ligne de commande
ollama rm <modèle>              # Supprimer (ils prennent beaucoup de place)
ollama pull <modèle>            # Télécharger ou mettre à jour
```

Vérifier qu'un modèle utilise bien le GPU :

```bash
ollama ps
```

La colonne `PROCESSOR` indique `100% GPU`, `100% CPU`, ou une répartition. Un
partage `50%/50%` signifie que le modèle déborde de la VRAM : prends une
quantisation plus petite ou un modèle plus léger.

---

## Mesurer la vitesse

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "hermes3:8b",
  "prompt": "Explique en trois phrases ce qu-est un serveur.",
  "stream": false
}' > /tmp/reponse.json

python3 -c '
import json
d = json.load(open("/tmp/reponse.json"))
print(d["response"])
print("%.1f tokens/seconde" % (d["eval_count"] / (d["eval_duration"] / 1e9)))
'
```

Repères d'interprétation :

| Débit | Ressenti |
|---|---|
| moins de 5 t/s | Pénible, on attend la réponse |
| 10–20 t/s | Confortable, comparable à une lecture attentive |
| plus de 30 t/s | Fluide, le texte défile plus vite qu'on ne lit |

---

## Où sont stockés les modèles

`03-ia.sh` configure Ollama pour écrire dans `/srv/ia/ollama`, sur le disque
dédié préparé à l'étape 1. Un modèle 70B pèse une quarantaine de gibioctets :
laissés sur la partition système, quelques modèles suffisent à la saturer.

```bash
du -sh /srv/ia/ollama          # Place occupée
df -h /srv/ia                  # Place restante
```

Pour LM Studio, le dossier de modèles se règle dans ses préférences — pointe-le
sur `/srv/ia/lmstudio`, pour la même raison.
