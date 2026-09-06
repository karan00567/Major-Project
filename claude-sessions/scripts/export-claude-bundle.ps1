<#
  Run this on YOUR laptop. Creates a self-contained bundle you copy to a USB
  stick, then run import-claude-bundle.ps1 from on your friend's laptop.

    .\export-claude-bundle.ps1 -Out E:\ClaudeBundle
    .\export-claude-bundle.ps1 -Out E:\ClaudeBundle -IncludePlugins   # +75 MB, works offline
#>
param(
  [string]$ProjectPath = "C:\Users\Sreekaran\Desktop\Major Project",
  [Parameter(Mandatory=$true)][string]$Out,
  [switch]$IncludePlugins
)

$ErrorActionPreference = "Stop"
function Slug([string]$p) { return ($p -replace '[^A-Za-z0-9]', '-') }

$slug     = Slug $ProjectPath
$stateDir = Join-Path $env:USERPROFILE ".claude\projects\$slug"

if (-not (Test-Path $ProjectPath)) { throw "Project not found: $ProjectPath" }
if (-not (Test-Path $stateDir))    { throw "No Claude state for that path: $stateDir" }

New-Item -ItemType Directory -Force -Path $Out | Out-Null
Write-Host "Bundling from $ProjectPath" -ForegroundColor Cyan
Write-Host "  slug: $slug"

# 1. Chats + memory. THIS is what makes Claude "know" the project.
#    Excludes nothing: the .jsonl transcripts ARE the resumable history.
Copy-Item $stateDir (Join-Path $Out "claude-project-state") -Recurse -Force
Write-Host "  [ok] chats + memory"

# 2. Global settings: model, effort, plugin marketplaces. Merged on import,
#    never copied over the top of your friend's file.
Copy-Item (Join-Path $env:USERPROFILE ".claude\settings.json") `
          (Join-Path $Out "claude-global-settings.json") -Force
Write-Host "  [ok] global settings"

# 3. Project .claude/ — settings.local.json is gitignored, so a fresh clone
#    has no permission allowlist and prompts on every command mid-demo.
Copy-Item (Join-Path $ProjectPath ".claude") (Join-Path $Out "project-dot-claude") -Recurse -Force
Write-Host "  [ok] project .claude/"

# 4. Gitignored runtime files the clone will not have.
$envFile = Join-Path $ProjectPath ".env"
if (Test-Path $envFile) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Out "gitignored") | Out-Null
  Copy-Item $envFile (Join-Path $Out "gitignored\.env") -Force
  Write-Host "  [ok] .env  (API keys - keep this USB with you)"
}

# 5. The pre-baked demo run. outputs/ is gitignored; fixture mode replays this
#    and refuses live runs, so it is the entire demo payload. 1.6 MB.
$fixture = Join-Path $ProjectPath "outputs\runs\fixture"
if (Test-Path $fixture) {
  Copy-Item $fixture (Join-Path $Out "gitignored\fixture") -Recurse -Force
  Write-Host "  [ok] outputs/runs/fixture  (the demo)"
} else {
  Write-Warning "  outputs/runs/fixture MISSING - the fixture demo will not work"
}

# 6. Plugins: optional. Without this the friend's Claude re-downloads them from
#    the marketplaces on first launch, which needs internet.
if ($IncludePlugins) {
  Copy-Item (Join-Path $env:USERPROFILE ".claude\plugins") (Join-Path $Out "claude-plugins") -Recurse -Force
  Write-Host "  [ok] plugins (offline-capable)"
}

# 7. Ship the importer alongside the data.
$importer = Join-Path $PSScriptRoot "import-claude-bundle.ps1"
if (Test-Path $importer) { Copy-Item $importer $Out -Force }

$size = [math]::Round(((Get-ChildItem $Out -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ""
Write-Host "Bundle ready: $Out  ($size MB)" -ForegroundColor Green
Write-Host "NOT included (on purpose): .credentials.json - log in on his laptop instead."
