# Hermes Agent sur cette machine

[Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research, MIT)
est un agent : il ne discute pas, il agit — lecture et écriture de fichiers,
commandes shell, tâches planifiées, passerelles Telegram/Discord/Slack/WhatsApp,
et une boucle qui fabrique ses propres « skills ». **Ce n'est pas le modèle
`hermes3:8b`**, qui est une famille de modèles de la même équipe et qui n'a rien
à voir avec ce programme. La confusion est facile et coûte du temps.

## État au 2026-08-14

**Installé, avec un modèle local qui convient — reste à finir la configuration
depuis l'interface graphique.** Le modèle retenu est
**Qwen3 4B Instruct 2507** (`lmstudio-community`, Q4_K_M, 2,5 Gio), et il coche
les trois cases que les autres ratent :

| | Résultat |
|---|---|
| Appel d'outil | ✅ `finish_reason: tool_calls`, arguments corrects |
| Temps de réponse | **0,73 s** — contre 3 min 41 s pour Qwen3 4B ordinaire |
| Jetons de raisonnement | **0** — c'est la version sans mode « thinking » |
| Contexte natif | **262 144** jetons |

Le gain de vitesse vient du raisonnement supprimé : Qwen3 4B « pense » avant
chaque réponse, ce qui est ruineux pour un agent qui enchaîne les appels. Pour
cet usage, **toujours préférer une variante `Instruct` à une variante
hybride ou `Thinking`**.

Ce qui reste à faire est listé en fin de document.

- Version **0.20.1**, dans `~/.hermes` (2,1 Gio), avec son propre `uv`, son
  propre Python 3.11.15 et son propre Node — **rien n'est installé au niveau du
  système**, et `rm -rf ~/.hermes` suffit à tout retirer.
- Installé par `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`,
  lancé avec `--skip-setup` pour éviter l'assistant interactif. Le script (3 466
  lignes) a été lu avant exécution : il n'a pas besoin de root et n'appelle `apt`
  que si `git` manque.
- La commande vit dans `~/.hermes/bin` (ajoutée à `~/.bashrc`).

## Le mur : 64 000 jetons de contexte minimum

C'est un garde-fou explicite du programme, qui refuse de démarrer en dessous :

> Model … has a context window of 16,384 tokens, which is below the minimum
> 64,000 required by Hermes Agent.

Ce n'est pas une coquetterie. Son prompt système mesuré par `hermes prompt-size`
pèse **25,7 Kio**, auxquels s'ajoutent **53,4 Kio de schémas d'outils** (18
outils) — environ **20 000 jetons avant que l'utilisateur ait écrit un mot**.

Or un cache KV de 64 000 jetons se paie en VRAM, et la GTX 1070 n'en a que 8 Gio.
Mesures réelles, contexte demandé à 65 536 :

| Modèle | Poids | Résultat |
|---|---|---|
| Gemma 3 4B (LM Studio) | 3,34 Gio | ✅ **charge** — 5 887 Mio / 8 192 utilisés |
| Qwen3 4B (LM Studio) | 2,50 Gio | ❌ cache trop lourd, **et** plafond du GGUF à 32 768 jetons |
| Qwen2.5-Coder 7B (LM Studio) | 4,68 Gio | ❌ `failed to allocate buffer for kv cache` |
| Qwen3.5 9B (LM Studio) | 6,55 Gio | ❌ le moteur `llama-server` meurt sur `SIGABRT` |
| `hermes3:8b` (Ollama) | 4,7 Gio | ❌ voir ci-dessous, pire que d'échouer |

**Gemma 3 tient grâce à son architecture**, qui alterne cinq couches d'attention
locale (fenêtre 1024) pour une globale : son cache KV croît beaucoup moins vite
que celui d'un Llama ou d'un Qwen. C'est le seul des cinq qui passe.

**La taille du modèle ne prédit pas la taille du cache**, et c'est le
contre-sens à éviter. Qwen3 4B, deuxième plus petit du lot avec ses 2,5 Gio de
poids, échoue là où Gemma 3 passe : ses 36 couches et ses 8 têtes KV lui donnent
un cache **plus lourd** que celui d'un Llama de 8 milliards de paramètres —
environ 0,14 Mio par jeton, soit près de 9 Gio pour 64 000 jetons. Ce qui compte
est `couches × têtes_KV × dimension`, pas le nombre de paramètres. Il a été
téléchargé le 2026-08-14 exprès pour ce test, en pariant sur sa petite taille :
le pari était mal posé.

Deux réglages qui *ne* sauvent *pas* les autres modèles, vérifiés : `--parallel 1`
au lieu de 4 ne change rien à l'échec, et `--estimate-only` **ne compte pas le
cache KV** — il annonçait « 6,10 GiB, chargeable » pour le Qwen3.5 9B qui meurt
en `SIGABRT`. Ne pas s'y fier pour cette question.

## Le piège d'Ollama : la troncature silencieuse

Ollama **n'échoue pas** quand le prompt dépasse son contexte : il le coupe et
répond quand même. Son contexte par défaut est de 4 096 jetons, quoi qu'annonce
le modèle (`hermes3:8b` déclare 131 072). Dans les journaux :

```
truncating input prompt  limit=2050  prompt=11368  keep=4  new=2050
```

**82 % du prompt jeté**, sans le moindre message côté client. Le symptôme visible
est un agent qui semble marcher — « bonjour » obtient une réponse polie — mais
qui produit des appels d'outils vides dès qu'on lui demande d'agir :

```
<SCRATCHPAD>
{"arguments": {"file_path": ""}, "name": "read_file"}
```

C'est la même famille de panne que l'Open WebUI qui n'affichait aucun modèle : le
composant paraît vert et ne fait rien d'utile. Pour vérifier ce qu'Ollama fait
réellement, lire ses journaux, pas sa réponse :

```bash
journalctl -u ollama --no-pager -n 200 | grep -iE "n_ctx|truncat"
```

Un modèle dérivé règle le contexte sans toucher au service, donc sans dégrader
Open WebUI ni les autres usages :

```bash
printf 'FROM hermes3:8b\nPARAMETER num_ctx 16384\n' > Modelfile
ollama create hermes3-agent:8b -f Modelfile     # ollama rm pour défaire
```

Inutile ici — 16 384 reste sous le minimum de 64 000 — mais c'est la bonne
méthode le jour où un contexte plus large sera nécessaire.

## Quantiser le cache KV : comment, et jusqu'où ça mène

Le cache se quantise, ce qui le divise par deux (`q8_0`) ou par quatre (`q4_0`).
**Le CLI `lms load` ne l'expose pas** — sa seule option mémoire est `--gpu`. Le
réglage se fait dans l'interface graphique de LM Studio, ou en écrivant
directement le fichier de configuration par modèle, dont voici le format (il
n'apparaît qu'après un premier réglage par l'interface) :

```
~/.lmstudio/.internal/user-concrete-model-default-config/<éditeur>/<modèle>.json
```

```json
{ "load": { "fields": [
  { "key": "llm.load.llama.kCacheQuantizationType", "value": {"checked": true, "value": "q8_0"} },
  { "key": "llm.load.llama.vCacheQuantizationType", "value": {"checked": true, "value": "q4_0"} },
  { "key": "llm.load.contextLength", "value": 65536 }
] } }
```

Les deux caches se règlent **séparément**, et n'en régler qu'un ne sert presque à
rien : K et V pèsent autant l'un que l'autre. Quand la mémoire manque, quantiser
K en `q8_0` et V en `q4_0` est le bon compromis — le cache K souffre davantage de
la quantisation.

Les messages d'erreur se lisent comme un thermomètre, du plus grave au plus
proche du but :

| Message | Ce qu'il veut dire |
|---|---|
| `unable to allocate CUDA0 buffer` | il y a autre chose sur le GPU — vérifier `nvidia-smi` avant tout |
| `failed to allocate buffer for kv cache` | le cache lui-même ne rentre pas |
| `failed to allocate compute pp buffers` | le cache rentre, ce sont les tampons de calcul qui manquent — on y est presque |

Avec K en `q8_0` et V en `q4_0`, Qwen3 4B charge en 2,1 s et occupe 6 673 Mio sur
8 192. **Et ça ne suffit toujours pas**, pour une raison qui n'a rien à voir avec
la mémoire : ce GGUF plafonne à 32 768 jetons.

```bash
curl -s http://127.0.0.1:1234/api/v0/models | python3 -m json.tool | grep context
# "max_context_length": 32768
```

**Toujours vérifier `max_context_length` avant de se battre avec la VRAM.**
Demander 65 536 à `lms load` ne provoque aucune erreur : le modèle charge, et
`lms ps` affiche tranquillement 32768. Une heure peut se perdre à optimiser la
mémoire pour un plafond qui est dans le fichier du modèle.

## Le second mur : un modèle qui tient n'est pas un modèle qui sait

Gemma 3 4B charge à 64k, et **n'appelle aucun outil**. Invité à lire un fichier
témoin, il a rédigé plusieurs paragraphes d'une « déclaration d'intention de
Hermes Agent » — il a pris son prompt système pour un sujet de dissertation. Un
modèle de 4 milliards de paramètres ne produit pas d'appels d'outils structurés
de façon fiable, et aucun réglage n'y changera quoi que ce soit.

**Mais ce n'est pas une fatalité de taille.** Qwen3 4B, à nombre de paramètres
égal, produit un appel parfaitement formé :

```json
{"name": "read_file", "arguments": {"path": "temoin.txt"}}   finish_reason: tool_calls
```

Un 4B peut donc outiller ; c'est Gemma 3 qui ne sait pas le faire, pas les
petits modèles en général. La piste locale reste ouverte, et le critère de choix
d'un modèle est triple, chaque terme ayant éliminé au moins un candidat ici :
savoir appeler des outils, avoir un contexte natif ≥ 64k, tenir en mémoire.

### Tester la compétence sans passer par Hermes

Inutile de déboguer l'agent pour savoir si un modèle sait outiller. Une requête
suffit, et elle isole la question :

```bash
curl -s http://127.0.0.1:1234/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "<modèle>",
  "messages": [{"role":"user","content":"Lis le fichier temoin.txt et dis-moi ce qu'"'"'il contient."}],
  "tools": [{"type":"function","function":{"name":"read_file","description":"Lit un fichier",
    "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}}],
  "max_tokens": 300, "stream": false
}' | python3 -m json.tool
```

Un `finish_reason: "tool_calls"` avec des arguments corrects vaut réponse. Du
texte libre, ou des arguments vides, signent un modèle inapte — quels que soient
les réglages.

### La vitesse, second critère et vraie difficulté

L'appel ci-dessus a pris **3 min 41 s**. Deux causes : Qwen3 est un modèle à
raisonnement, qui « réfléchit » longuement avant chaque réponse (le serveur le
signale — `Reasoning setting … Falling back to 'on'`), et le cache quantisé coûte
du temps de calcul sur une Pascal, génération que Flash Attention n'accélère pas.

Un agent enchaîne cinq à dix appels pour une tâche : à ce rythme, une demande
simple prendrait une demi-heure. **La compétence ne suffit pas, il faut aussi le
débit** — d'où l'intérêt des variantes `Instruct` sans raisonnement.

### Le blocage d'Hermes en mode non interactif

`hermes -z "…"` reste bloqué indéfiniment : 610 secondes pour ne rien écrire, le
GPU à 1 %, une seconde de temps processeur. Le système d'approbation des
commandes attend vraisemblablement un accord sur l'entrée standard que le mode
non interactif ne fournit jamais. Non résolu ; contourné par le test direct
ci-dessus. À creuser du côté de `hermes approvals` et `hermes tools` avant de
compter s'en servir dans un script ou une tâche planifiée.

## Configuration en place

Dans `~/.hermes/config.yaml`, pointée sur LM Studio :

```yaml
model:
  provider: "lmstudio"
  base_url: "http://127.0.0.1:1234/v1"
  default: "google/gemma-3-4b"
  context_length: 65536
```

Attention, le fichier de configuration livré **se contredit** : il documente
`ollama` comme alias de `custom`, alors que `hermes doctor` le refuse — la liste
des fournisseurs valides contient `custom` et `ollama-cloud`, pas `ollama`. Pour
Ollama, écrire `provider: "custom"` avec `base_url: http://localhost:11434/v1`.
LM Studio, lui, est de première classe (`provider: "lmstudio"`, port 1234).

Le serveur LM Studio n'est pas lancé au démarrage. Il faut :

```bash
lms server start
lms load google/gemma-3-4b --context-length 65536 --gpu max
```

## Ce qui reste à faire, et pourquoi ça passe par la souris

**1. Quantiser le cache de `qwen3-4b-instruct-2507` pour atteindre 64k.** Chargé
à 32 768 jetons sans quantisation, il occupe déjà 7 534 Mio sur 8 192. Pour
doubler le contexte il faut quantiser le cache — et **écrire le fichier de
configuration à la main ne marche pas pour un modèle qui n'en a jamais eu**. Les
quatre emplacements plausibles ont été essayés, dont celui qui correspond
exactement au `modelKey` retourné par `lms ls --json`, avec redémarrage du
serveur entre chaque : le chargement échoue toujours sur
`failed to allocate buffer for kv cache`, signe que le fichier est ignoré.

Le fichier existant de `qwen/qwen3-4b` fonctionne, lui, parce qu'il a d'abord été
créé par l'interface graphique. **Conclusion : le premier réglage d'un modèle se
fait à la souris**, ensuite le fichier est modifiable au clavier. Dans LM Studio,
sur `Qwen3 4B Instruct 2507` : Flash Attention activée, K Cache en `q8_0`, V Cache
en `q4_0`, contexte `65536`.

> Vérifier le contexte après coup — une saisie à `6553` au lieu de `65536` passe
> sans aucune alerte, et `lms ps` affiche alors tranquillement le mauvais chiffre.

**2. Faire fonctionner les outils.** L'agent répond en 6-7 s via LM Studio, mais
en mode `-z` il dit ne pas avoir d'outil de lecture, et la requête envoyée au
serveur ne fait que 250 jetons — sans le prompt système de 20 000 jetons ni les
schémas. Cause non établie.

**Et elle ne s'établira pas en ligne de commande scriptée** : `hermes tools`
refuse de tourner autrement que dans un vrai terminal.

```
Error: 'hermes tools' requires an interactive terminal.
It cannot be run through a pipe or non-interactive subprocess.
```

C'est cohérent avec la nature du programme : son mode normal est une interface
interactive. Le diagnostic se fera donc en lançant `hermes` dans un terminal, où
`hermes tools` permet d'inspecter et d'activer les jeux d'outils. Le mode `-z`
reste utile pour les scripts, mais ce n'est pas le chemin principal — et il se
bloquait déjà indéfiniment sur les modèles précédents.

## Les voies possibles si le local ne suffit pas

1. **Décharger une partie en RAM** (`--gpu 0.7`) pour faire tenir un 7B. Le
   cache KV va dans les 16 Gio de RAM, le calcul retombe sur l'i5-7500 : ça
   fonctionne, c'est très lent, et un agent enchaîne beaucoup d'appels.
3. **Une API distante** (Nous Portal, OpenRouter, Anthropic). C'est ce que le
   projet suppose, ça marche vraiment — mais c'est payant à l'usage et les
   conversations quittent la maison, ce qui est l'inverse du but de ce serveur.
4. **Attendre un GPU plus grand.** 16 Gio changent complètement la donne.

## Avant de l'ouvrir sur le monde

Rien de ceci n'est fait, et rien ne doit l'être par accident. Cet agent exécute
des commandes shell et fabrique ses propres compétences ; les passerelles
Telegram/Discord/WhatsApp lui donnent une entrée depuis Internet. Sur une machine
dont on vient de fermer SSH au réseau local, brancher une passerelle de
messagerie mérite d'être décidé, pas subi. Le projet fournit de quoi le faire
correctement — approbation des commandes, appairage en message privé, sept
backends d'exécution dont Docker — mais ce sont des réglages à choisir.

À titre indicatif : 32 000 tickets ouverts pour 230 000 étoiles, sur un projet
d'un an. Très populaire, très jeune, qui bouge tous les jours.
