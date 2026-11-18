# Sauvegarde Prizm vers `D:\a garder\Brasserie\Prizm`

## 1. Le PC : lancer le script (10 min de ta part, le reste tourne seul)

1. Copier `Sauvegarde-Prizm.ps1` sur le PC (ex. dans `D:\a garder\Brasserie\`).
2. Fermer Claude Desktop (ses bases locales sont verrouillées tant qu'il tourne).
3. Simulation, rien n'est copié. Ouvrir PowerShell dans le dossier du script :
   `powershell -ExecutionPolicy Bypass -File .\Sauvegarde-Prizm.ps1`
   Ouvrir `simulation_<date>\index.csv` : vérifier qu'il ne manque rien et qu'il n'y a pas de bruit.
4. Copie réelle :
   `powershell -ExecutionPolicy Bypass -File .\Sauvegarde-Prizm.ps1 -Execute`

Options : `-MaxFileMB 2000` (au-delà de 500 Mo un fichier est ignoré par défaut), `-SkipOneDrive`
(si OneDrive est en « fichiers à la demande », le script va TOUT télécharger).

Résultat :

```
Prizm\
  _Claude\
    01_Claude_Code\            ~/.claude (CLAUDE.md, skills, plugins, historique des sessions .jsonl) + .claude.json
    02_Claude_Desktop_Cowork\  données de l'appli Claude Desktop / Cowork
    03_Instructions_projets\   CLAUDE.md / .mcp.json / .claude des projets du PC
    04_Export_claude_ai\       <- déposer l'export claude.ai (étape 2)
  _PC\                         Bureau, Documents, Téléchargements, OneDrive (arborescence d'origine)
  _Travail_Exports\            <- déposer les exports des outils (étape 2)
  _INDEX\<date>\               index.csv, doublons.csv, erreurs.csv
  LISEZMOI.md                  plan de l'archive, à donner en premier à l'IA locale
```

Doublons : chaque fichier est identifié par son empreinte SHA-256, comparée aussi à ce qui est
déjà dans `Prizm`. Un fichier identique n'est jamais copié deux fois ; la liste des doublons
écartés est dans `doublons.csv`. Le script peut être relancé : il ne recopie que les nouveautés.

## 2. Le travail : exports natifs (le seul moyen de ne rien perdre)

| Source | Où exporter | Dossier de destination |
|---|---|---|
| Conversations claude.ai | claude.ai > Settings > Privacy > Export data (lien envoyé par e-mail) | `_Claude\04_Export_claude_ai` |
| Projets claude.ai (instructions + fichiers) | non inclus dans l'export : copier à la main les instructions de chaque projet | `_Claude\04_Export_claude_ai\Projets` |
| Gmail + Google Drive + Agenda | takeout.google.com (compte de la brasserie) | `_Travail_Exports\Google_Takeout_Gmail_Drive` |
| Notion | Settings > Export all workspace content > Markdown & CSV, avec sous-pages | `_Travail_Exports\Notion` |
| Easybeer | exports CSV/Excel des modules (clients, produits, brassins, commandes, stocks) | `_Travail_Exports\Easybeer` |
| Pennylane | export FEC + grand livre + justificatifs | `_Travail_Exports\Pennylane` |
| Slack | Workspace settings > Import/Export data (droits admin requis) | `_Travail_Exports\Slack` |
| Shopify | Produits / Clients / Commandes > Exporter en CSV | `_Travail_Exports\Shopify` |

Ordre conseillé pour limiter les doublons : déposer d'abord les exports, puis lancer le script.
Il prend en compte ce qui est déjà dans `Prizm` et ne recopie pas un fichier du PC déjà présent
dans un export (ex. une pièce jointe déjà dans le Takeout). Le script ne supprime jamais rien :
les doublons internes à un export (ex. le même PDF dans deux mails) restent tels quels.
