<#
  Sauvegarde-Prizm.ps1
  Rassemble sur le disque externe tout ce qui compte sur ce PC (Claude + documents),
  rangé, indexé, sans doublons (contrôle par empreinte SHA-256, y compris contre ce
  qui est DÉJÀ sur le disque externe).

  1) Simulation (ne copie rien, produit l'inventaire) :
       powershell -ExecutionPolicy Bypass -File .\Sauvegarde-Prizm.ps1
  2) Copie réelle :
       powershell -ExecutionPolicy Bypass -File .\Sauvegarde-Prizm.ps1 -Execute

  Fermer Claude Desktop avant la copie réelle (sinon ses bases locales sont verrouillées).
  Relançable sans risque : ce qui est déjà copié est reconnu et ignoré.
#>
param(
    [string]$Dest = 'D:\a garder\Brasserie\Prizm',
    [switch]$Execute,
    [int]$MaxFileMB = 500,
    [switch]$SkipOneDrive
)

$ErrorActionPreference = 'Continue'
$U      = $env:USERPROFILE
$Stamp  = Get-Date -Format 'yyyy-MM-dd_HHmm'
$Mode   = if ($Execute) { 'COPIE' } else { 'SIMULATION' }

# --- Dossiers jamais parcourus (caches, dépendances, corbeille) ---------------------
$ExcludeDirs = @('node_modules', '.git', '$Recycle.Bin', 'Cache', 'Code Cache', 'GPUCache',
    'DawnCache', 'DawnGraphiteCache', 'DawnWebGPUCache', 'Crashpad', 'ShaderCache',
    'CacheStorage', 'ScriptCache', 'blob_storage', '__pycache__', '.venv', 'venv',
    'vm_bundles', 'claude-code-vm')

# --- Extensions retenues pour les dossiers personnels (Bureau, Documents...) ----------
$DocExt = @('.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt', '.md', '.xls', '.xlsx', '.xlsm',
    '.ods', '.csv', '.ppt', '.pptx', '.odp', '.json', '.xml', '.html', '.htm', '.eml', '.msg',
    '.jpg', '.jpeg', '.png', '.heic', '.webp', '.svg', '.ai', '.psd', '.indd', '.eps',
    '.zip', '.7z', '.rar', '.bsmx', '.beerxml', '.py', '.ps1', '.skill', '.pages', '.numbers', '.key')

# --- Sources ------------------------------------------------------------------------
$Desktop   = [Environment]::GetFolderPath('Desktop')
$Documents = [Environment]::GetFolderPath('MyDocuments')
$ProjFilter = {
    param($p)
    $n = [IO.Path]::GetFileName($p)
    if ($p.StartsWith("$U\.claude\", 'OrdinalIgnoreCase')) { return $false }
    if ($p -like '*\AppData\*') { return $false }
    return ($n -in @('CLAUDE.md', 'CLAUDE.local.md', '.mcp.json', 'AGENTS.md')) -or ($p -like '*\.claude\*')
}
$DocFilter = { param($p) $DocExt -contains [IO.Path]::GetExtension($p).ToLower() }
$AllFilter = { param($p) $true }

$Sources = @(
    # ---- Tout Claude dans _Claude ----
    @{ Src = "$U\.claude";              Rel = '_Claude\01_Claude_Code\dot-claude';           Filter = $AllFilter }
    @{ Src = "$U\.claude.json";         Rel = '_Claude\01_Claude_Code';                      Filter = $AllFilter }
    @{ Src = "$env:APPDATA\Claude";     Rel = '_Claude\02_Claude_Desktop_Cowork\AppData_Roaming_Claude'; Filter = $AllFilter }
    @{ Src = "$env:LOCALAPPDATA\Claude";Rel = '_Claude\02_Claude_Desktop_Cowork\AppData_Local_Claude';   Filter = $DocFilter }
    @{ Src = $U;                        Rel = '_Claude\03_Instructions_projets';             Filter = $ProjFilter; Skip = @('AppData', 'OneDrive') }
    # ---- Fichiers du PC dans _PC ----
    @{ Src = $Desktop;                  Rel = '_PC\Bureau';          Filter = $DocFilter }
    @{ Src = $Documents;                Rel = '_PC\Documents';       Filter = $DocFilter }
    @{ Src = "$U\Downloads";            Rel = '_PC\Telechargements'; Filter = $DocFilter }
)
if (-not $SkipOneDrive) {
    foreach ($od in @($env:OneDrive, $env:OneDriveCommercial) | Where-Object { $_ } | Select-Object -Unique) {
        $Sources += @{ Src = $od; Rel = '_PC\OneDrive_' + (Split-Path $od -Leaf); Filter = $DocFilter }
    }
}

# --- Outils -------------------------------------------------------------------------
function Get-FilesPruned([string]$root, [string[]]$extraExclude = @()) {
    $stack = New-Object System.Collections.Stack
    $stack.Push($root)
    while ($stack.Count -gt 0) {
        $d = $stack.Pop()
        try { $subs = [IO.Directory]::GetDirectories($d) } catch { continue }
        foreach ($s in $subs) {
            $dn = [IO.Path]::GetFileName($s)
            if ($ExcludeDirs -contains $dn -or $extraExclude -contains $dn) { continue }
            if ($s.StartsWith($Dest, 'OrdinalIgnoreCase')) { continue }
            try { $li = Get-Item -LiteralPath $s -Force -ErrorAction Stop } catch { continue }
            if ($li.LinkType) { continue }   # jonctions / liens symboliques : évite boucles et doublons
            $stack.Push($s)
        }
        try { $files = [IO.Directory]::GetFiles($d) } catch { continue }
        foreach ($f in $files) { $f }
    }
}

function Get-Sha([string]$path) {
    (Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash
}

function Get-FreeTarget([string]$target) {
    if (-not (Test-Path -LiteralPath $target)) { return $target }
    $dir  = Split-Path $target -Parent
    $base = [IO.Path]::GetFileNameWithoutExtension($target)
    $ext  = [IO.Path]::GetExtension($target)
    $i = 2
    do { $cand = Join-Path $dir ('{0}_v{1}{2}' -f $base, $i, $ext); $i++ } while (Test-Path -LiteralPath $cand)
    return $cand
}

# --- 1. Empreintes de ce qui est déjà sur le disque externe -------------------------
$Known   = @{}   # hash -> chemin sur le disque externe (existant ou prévu)
$Index   = New-Object System.Collections.Generic.List[object]
$Doubles = New-Object System.Collections.Generic.List[object]
$Errors  = New-Object System.Collections.Generic.List[object]
$Planned = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

Write-Host "[$Mode] Destination : $Dest" -ForegroundColor Cyan
if (Test-Path -LiteralPath $Dest) {
    Write-Host 'Empreintes du contenu déjà présent sur le disque externe...'
    Get-ChildItem -LiteralPath $Dest -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notlike "$Dest\_INDEX\*" -and $_.Length -gt 0 } |
        ForEach-Object {
            $ef = $_.FullName
            try { $h = Get-Sha $ef; if (-not $Known.ContainsKey($h)) { $Known[$h] = $ef } }
            catch { $Errors.Add([pscustomobject]@{ Fichier = $ef; Erreur = $_.Exception.Message }) }
        }
    Write-Host ("  {0} fichiers uniques déjà présents" -f $Known.Count)
}

# --- 2. Parcours des sources --------------------------------------------------------
$copied = 0; $bytes = 0L
foreach ($s in $Sources) {
    $src = $s.Src
    if (-not $src -or -not (Test-Path -LiteralPath $src)) { Write-Host "  (absent) $src" -ForegroundColor DarkGray; continue }
    Write-Host "Analyse : $src" -ForegroundColor Yellow
    $isFile = Test-Path -LiteralPath $src -PathType Leaf
    $root   = if ($isFile) { Split-Path $src -Parent } else { $src.TrimEnd('\') }
    $skip   = if ($s.Skip) { $s.Skip } else { @() }
    $list   = if ($isFile) { @($src) } else { Get-FilesPruned $root $skip }

    foreach ($f in $list) {
        if (-not (& $s.Filter $f)) { continue }
        if ($f.StartsWith($Dest, 'OrdinalIgnoreCase')) { continue }
        try {
            $fi = Get-Item -LiteralPath $f -Force -ErrorAction Stop
            if ($fi.Length -gt ($MaxFileMB * 1MB)) {
                $Errors.Add([pscustomobject]@{ Fichier = $f; Erreur = "Ignoré : > $MaxFileMB Mo" }); continue
            }
            $rel    = $f.Substring($root.Length).TrimStart('\')
            $target = Join-Path (Join-Path $Dest $s.Rel) $rel

            if ($fi.Length -gt 0) {
                $h = Get-Sha $f
                if ($Known.ContainsKey($h)) {
                    $Doubles.Add([pscustomobject]@{ Ignore = $f; DejaPresentDans = $Known[$h]; Taille = $fi.Length }); continue
                }
            } else { $h = '' }

            if ($Execute) {
                $target = Get-FreeTarget $target
                $dir = Split-Path $target -Parent
                if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
                Copy-Item -LiteralPath $f -Destination $target -Force -ErrorAction Stop
            } elseif ($Planned.Contains($target)) {
                $target = $target + ' (renommé _vN à la copie)'
            }
            [void]$Planned.Add($target)
            if ($h) { $Known[$h] = $target }
            $copied++; $bytes += $fi.Length
            $Index.Add([pscustomobject]@{
                Categorie = $s.Rel; Destination = $target; Origine = $f
                Taille = $fi.Length; Modifie = $fi.LastWriteTime.ToString('yyyy-MM-dd HH:mm'); SHA256 = $h })
        } catch {
            $Errors.Add([pscustomobject]@{ Fichier = $f; Erreur = $_.Exception.Message })
        }
    }
}

# --- 3. Rapports --------------------------------------------------------------------
$repDir = if ($Execute) { Join-Path $Dest "_INDEX\$Stamp" } else { Join-Path $PSScriptRoot "simulation_$Stamp" }
New-Item -ItemType Directory -Path $repDir -Force | Out-Null
$Index   | Export-Csv -LiteralPath (Join-Path $repDir 'index.csv')    -NoTypeInformation -Encoding UTF8 -Delimiter ';'
$Doubles | Export-Csv -LiteralPath (Join-Path $repDir 'doublons.csv') -NoTypeInformation -Encoding UTF8 -Delimiter ';'
$Errors  | Export-Csv -LiteralPath (Join-Path $repDir 'erreurs.csv')  -NoTypeInformation -Encoding UTF8 -Delimiter ';'

if ($Execute) {
    foreach ($d in @('_Claude\04_Export_claude_ai', '_Travail_Exports\Google_Takeout_Gmail_Drive',
                     '_Travail_Exports\Notion', '_Travail_Exports\Easybeer', '_Travail_Exports\Pennylane',
                     '_Travail_Exports\Slack', '_Travail_Exports\Shopify')) {
        New-Item -ItemType Directory -Path (Join-Path $Dest $d) -Force | Out-Null
    }
    $readme = @"
# Archive Prizm — mode d'emploi pour une IA locale

Générée le $Stamp depuis le PC $env:COMPUTERNAME.

- _Claude\01_Claude_Code : dossier ~/.claude (CLAUDE.md global, skills, agents, commandes,
  plugins, et projects\*\*.jsonl = historique complet des sessions Claude Code) + .claude.json.
- _Claude\02_Claude_Desktop_Cowork : données de l'application Claude Desktop / Cowork.
- _Claude\03_Instructions_projets : CLAUDE.md, .mcp.json et dossiers .claude des projets du PC
  (arborescence d'origine conservée, relative au profil utilisateur).
- _Claude\04_Export_claude_ai : export des conversations claude.ai (à déposer à la main).
- _PC : documents du Bureau, de Documents, Téléchargements, OneDrive (arborescence d'origine).
- _Travail_Exports : exports des outils (Gmail/Drive, Notion, Easybeer, Pennylane, Slack, Shopify).
- _INDEX\<date> : index.csv (origine -> destination, date, SHA-256), doublons.csv, erreurs.csv.

Chaque fichier n'existe qu'une fois (dédoublonnage par empreinte SHA-256).
ATTENTION : .claude.json et claude_desktop_config.json peuvent contenir des clés d'API.
"@
    $readme | Out-File -LiteralPath (Join-Path $Dest 'LISEZMOI.md') -Encoding UTF8
}

Write-Host ''
Write-Host ("[$Mode] {0} fichiers {1}, {2:N1} Go" -f $copied, $(if ($Execute) { 'copiés' } else { 'à copier' }), ($bytes / 1GB)) -ForegroundColor Green
Write-Host ("        {0} doublons ignorés, {1} erreurs/ignorés" -f $Doubles.Count, $Errors.Count)
Write-Host "        Rapports : $repDir"
if (-not $Execute) { Write-Host 'Vérifier index.csv puis relancer avec -Execute.' -ForegroundColor Cyan }
