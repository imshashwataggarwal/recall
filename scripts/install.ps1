<#
.SYNOPSIS
  Recall - one-command installer (Windows / PowerShell).

.DESCRIPTION
  Finds a suitable Python, installs Recall (pipx if available, else a local
  virtualenv), initializes the knowledge base, and runs `recall doctor`.
  Idempotent: safe to re-run.

.EXAMPLE
  ./scripts/install.ps1
  ./scripts/install.ps1 -PullModel
  irm <raw-url>/scripts/install.ps1 | iex
#>
[CmdletBinding()]
param(
  [switch]$PullModel,
  [string]$Model = "embeddinggemma"
)

$ErrorActionPreference = "Stop"
$Repo = "https://github.com/imshashwataggarwal/recall.git"

function Note($m) { Write-Host "=> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "OK $m" -ForegroundColor Green }
function Warn($m) { Write-Host "!  $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "x  $m" -ForegroundColor Red; exit 1 }

# --- 1. Find Python >= 3.10 --------------------------------------------------
function Get-Python {
  $candidates = @()
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { $candidates += $cmd.Source }
  # `py -3` launcher
  if (Get-Command py -ErrorAction SilentlyContinue) {
    try { $p = (& py -3 -c "import sys; print(sys.executable)") 2>$null; if ($p) { $candidates += $p } } catch {}
  }
  # Common per-user install location
  $candidates += (Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
  foreach ($c in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
    # Skip the Microsoft Store stub
    if ($c -like "*WindowsApps*") { continue }
    try {
      $okv = & $c -c "import sys; print(1 if sys.version_info[:2] >= (3,10) else 0)" 2>$null
      if ($okv -eq "1") { return $c }
    } catch {}
  }
  return $null
}

$Py = Get-Python
if (-not $Py) {
  Warn "Python >= 3.10 not found."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Note "Installing Python via winget..."
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements --scope user | Out-Null
    $Py = Get-Python
  }
}
if (-not $Py) { Die "Could not find or install Python >= 3.10. Install from https://python.org and re-run." }
Ok "Using $(& $Py --version 2>&1) ($Py)"

# --- 2. Locate source (clone dir or remote) ----------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = $null
if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "..\pyproject.toml"))) {
  $RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
  Note "Installing from local clone: $RepoRoot"
} else {
  Note "Installing from $Repo"
}

# --- 3. Install (pipx preferred, else venv) ----------------------------------
$RecallBin = $null
$LocalExtra  = if ($RepoRoot) { $RepoRoot + '[mcp]' } else { $null }
$RemoteExtra = 'recall[mcp] @ git+' + $Repo
$RemotePlain = 'recall @ git+' + $Repo
if (Get-Command pipx -ErrorAction SilentlyContinue) {
  Note "Installing with pipx..."
  if ($RepoRoot) {
    try { pipx install --force $LocalExtra } catch { pipx install --force $RepoRoot }
  } else {
    try { pipx install --force $RemoteExtra } catch { pipx install --force $RemotePlain }
  }
  $RecallBin = "recall"
  Ok "Installed via pipx"
} else {
  Warn "pipx not found - using a local virtualenv instead."
  $Venv = if ($RepoRoot) { Join-Path $RepoRoot ".venv" } elseif ($env:RECALL_VENV) { $env:RECALL_VENV } else { Join-Path $env:USERPROFILE ".recall-venv" }
  Note "Creating venv at $Venv"
  & $Py -m venv $Venv
  $VenvPy = Join-Path $Venv "Scripts\python.exe"
  & $VenvPy -m pip install --upgrade pip | Out-Null
  if ($RepoRoot) {
    & $VenvPy -m pip install -e $LocalExtra
  } else {
    & $VenvPy -m pip install $RemoteExtra
  }
  $RecallBin = Join-Path $Venv "Scripts\recall.exe"
  Ok "Installed into $Venv"
  Warn "Add it to PATH:  `$env:PATH = `"$Venv\Scripts;`$env:PATH`""
}

# --- 4. Initialize the knowledge base ---------------------------------------
Note "Initializing the knowledge base..."
& $RecallBin init

# --- 5. Optional: Ollama embedding model ------------------------------------
if (Get-Command ollama -ErrorAction SilentlyContinue) {
  $have = $false
  try { $have = (ollama list 2>$null | Select-String $Model) -ne $null } catch {}
  if ($have) {
    Ok "Ollama model '$Model' already present (semantic search enabled)."
  } elseif ($PullModel) {
    Note "Pulling Ollama model '$Model' (~600MB)..."
    ollama pull $Model; Ok "Model pulled."
  } else {
    Warn "Ollama found but '$Model' not pulled. For semantic search run: ollama pull $Model"
    Warn "(or re-run with -PullModel). Keyword (BM25) search works without it."
  }
} else {
  Warn "Ollama not installed - Recall will use BM25-only search."
  Warn "For semantic search, install Ollama from https://ollama.com then: ollama pull $Model"
}

# --- 6. Doctor + next steps --------------------------------------------------
Write-Host ""
Note "Running recall doctor..."
try { & $RecallBin doctor } catch {}
Write-Host ""
Ok "Recall is installed."
@"

Next steps:
  1. Register the MCP server in your agent (e.g. ~/.copilot/mcp-config.json):
       { "mcpServers": { "recall": { "command": "recall-mcp" } } }
  2. Try it:
       '### Decision   Hello, memory.' | recall append --workstream demo/test --title hello --session s1 --body -
       recall search "hello memory" --workstream demo/test
  3. Read the docs: docs\  (start with docs\installation.md and docs\mcp-and-copilot.md)
"@ | Write-Host
