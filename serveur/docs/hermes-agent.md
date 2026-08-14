# Hermes Agent sur cette machine

[Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research, MIT)
est un agent : il ne discute pas, il agit — lecture et écriture de fichiers,
commandes shell, tâches planifiées, passerelles Telegram/Discord/Slack/WhatsApp,
et une boucle qui fabrique ses propres « skills ». **Ce n'est pas le modèle
`hermes3:8b`**, qui est une famille de modèles de la même équipe et qui n'a rien
à voir avec ce programme. La confusion est facile et coûte du temps.

## État au 2026-08-14

**Installé et fonctionnel côté programme, inutilisable avec les modèles locaux
de cette machine.** Les deux moitiés de cette phrase comptent.

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
| Qwen3 4B (LM Studio) | 2,50 Gio | ❌ `failed to allocate buffer for kv cache` |
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

## Le second mur : un modèle qui tient n'est pas un modèle qui sait

Gemma 3 4B charge à 64k, et **n'appelle aucun outil**. Invité à lire un fichier
témoin, il a rédigé plusieurs paragraphes d'une « déclaration d'intention de
Hermes Agent » — il a pris son prompt système pour un sujet de dissertation. Un
modèle de 4 milliards de paramètres ne produit pas d'appels d'outils structurés
de façon fiable, et aucun réglage n'y changera quoi que ce soit.

D'où la situation : le seul modèle local qui **tient** en mémoire est celui qui ne
**sait** pas s'en servir, et ceux qui sauraient ne tiennent pas. Le projet est
cohérent avec lui-même sur ce point — son README annonce « aucun GPU requis,
tourne sur un VPS à 5 $ », parce qu'il appelle par défaut une API distante.

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

## Les voies possibles

1. **Quantiser le cache KV**, la seule piste locale encore ouverte. En `q8_0` le
   cache est divisé par deux : Qwen3 4B retomberait autour de 4,5 Gio, soit ~7
   Gio avec ses poids — juste dans les 7,5 Gio disponibles. En `q4_0` c'est
   confortable, au prix de la qualité. **Le CLI `lms load` ne l'expose pas** : le
   réglage vit dans l'interface graphique de LM Studio, avec Flash Attention
   qu'il faut activer d'abord. Le dossier
   `~/.lmstudio/.internal/user-concrete-model-default-config` est vide, donc il
   n'y a pas de format connu à écrire à la main — mieux vaut la souris que du
   reverse-engineering sur un format interne.
2. **Décharger une partie en RAM** (`--gpu 0.7`) pour faire tenir un 7B. Le
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
