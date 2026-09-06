<#
  Run this on your FRIEND'S laptop, after:
    1. installing Claude Code and logging in as you
    2. git clone <your repo> into the folder you pass as -ProjectPath

    .\import-claude-bundle.ps1 -Bundle E:\ClaudeBundle -ProjectPath "C:\Users\Friend\Desktop\Major Project"

  Claude keys its history off the ABSOLUTE project path, so the state folder is
  renamed to match wherever the clone actually lives. Pass the real path.
#>
param(
  [Parameter(Mandatory=$true)][string]$Bundle,
  [Parameter(Mandatory=$true)][string]$ProjectPath
)

$ErrorActionPreference = "Stop"
function Slug([string]$p) { return ($p -replace '[^A-Za-z0-9]', '-') }

if (-not (Test-Path $Bundle))      { throw "Bundle not found: $Bundle" }
if (-not (Test-Path $ProjectPath)) { throw "Clone the repo to $ProjectPath first." }

# Normalise: trailing slashes and 8.3 names would produce a different slug.
$ProjectPath = (Resolve-Path $ProjectPath).Path.TrimEnd('\')
$slug   = Slug $ProjectPath
$target = Join-Path $env:USERPROFILE ".claude\projects\$slug"

Write-Host "Installing into $ProjectPath" -ForegroundColor Cyan
Write-Host "  slug: $slug"

# 1. Chats + memory, renamed to this machine's path slug.
if (Test-Path $target) {
  $backup = "$target.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
  Move-Item $target $backup
  Write-Host "  [..] existing state moved to $backup"
}
New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
Copy-Item (Join-Path $Bundle "claude-project-state") $target -Recurse -Force
$n = (Get-ChildItem $target -Filter *.jsonl).Count
Write-Host "  [ok] $n chat transcripts + memory"

# 2. Merge global settings key-by-key. Overwriting would wipe his own config.
$src = Get-Content (Join-Path $Bundle "claude-global-settings.json") -Raw | ConvertFrom-Json
$dstPath = Join-Path $env:USERPROFILE ".claude\settings.json"
if (Test-Path $dstPath) {
  $dst = Get-Content $dstPath -Raw | ConvertFrom-Json
} else {
  $dst = New-Object PSObject
}
foreach ($p in $src.PSObject.Properties) {
  $dst | Add-Member -MemberType NoteProperty -Name $p.Name -Value $p.Value -Force
}
New-Item -ItemType Directory -Force -Path (Split-Path $dstPath) | Out-Null
$dst | ConvertTo-Json -Depth 20 | Out-File $dstPath -Encoding utf8
Write-Host "  [ok] global settings merged (model, effort, marketplaces)"

# 3. Project .claude/ — brings back the permission allowlist so he is not
#    clicking 'allow' in front of the examiner.
Copy-Item (Join-Path $Bundle "project-dot-claude\*") (Join-Path $ProjectPath ".claude") -Recurse -Force
Write-Host "  [ok] project .claude/ (permissions + enabled plugins)"

# 4. Gitignored runtime files.
$envSrc = Join-Path $Bundle "gitignored\.env"
if (Test-Path $envSrc) {
  Copy-Item $envSrc (Join-Path $ProjectPath ".env") -Force
  Write-Host "  [ok] .env"
}
$fixSrc = Join-Path $Bundle "gitignored\fixture"
if (Test-Path $fixSrc) {
  $fixDst = Join-Path $ProjectPath "outputs\runs\fixture"
  New-Item -ItemType Directory -Force -Path (Split-Path $fixDst) | Out-Null
  Copy-Item $fixSrc $fixDst -Recurse -Force
  Write-Host "  [ok] outputs/runs/fixture"
}

# 5. Plugins, if bundled. installed_plugins.json records absolute paths under
#    the old username, so rewrite them or Claude looks in a folder that is not
#    there and silently loads no skills.
$plugSrc = Join-Path $Bundle "claude-plugins"
if (Test-Path $plugSrc) {
  $plugDst = Join-Path $env:USERPROFILE ".claude\plugins"
  Copy-Item $plugSrc $plugDst -Recurse -Force
  $manifest = Join-Path $plugDst "installed_plugins.json"
  if (Test-Path $manifest) {
    $text = Get-Content $manifest -Raw
    # JSON-escaped backslashes: C:\Users\Sreekaran -> C:\Users\<him>
    $text = $text -replace [regex]::Escape("C:\Users\Sreekaran"), ($env:USERPROFILE -replace '\', '\')
    $text = $text -replace [regex]::Escape("Desktop\Major Project"), (($ProjectPath -replace '^.*?Users\[^\]+\', '') -replace '\', '\')
    $text | Out-File $manifest -Encoding utf8
  }
  Write-Host "  [ok] plugins (paths rewritten)"
} else {
  Write-Host "  [--] no plugins bundled - Claude will fetch them on first run (needs internet)"
}

Write-Host ""
Write-Host "Done. Now:" -ForegroundColor Green
Write-Host "  cd `"$ProjectPath`""
Write-Host "  claude --resume        # pick a past session; full history is there"
Write-Host ""
Write-Host "If --resume shows an EMPTY list, the slug did not match. Fix it:" -ForegroundColor Yellow
Write-Host "  1. run 'claude' once in the project folder, then exit"
Write-Host "  2. dir `"$env:USERPROFILE\.claude\projects`"   <- note the folder that just appeared"
Write-Host "  3. copy the .jsonl files, MEMORY.md and memory\ from"
Write-Host "     $target"
Write-Host "     into that folder, and re-run 'claude --resume'"
