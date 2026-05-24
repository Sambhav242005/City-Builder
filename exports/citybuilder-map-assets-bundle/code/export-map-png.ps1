param(
  [string]$HtmlPath = "",
  [string]$OutputPng = "",
  [int]$Width = 1500,
  [int]$Height = 1250
)

$ErrorActionPreference = "Stop"

$bundleRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $HtmlPath) {
  $HtmlPath = Join-Path $bundleRoot "output\example_map.html"
}
if (-not $OutputPng) {
  $OutputPng = Join-Path $bundleRoot "output\example_map.png"
}

$browserCandidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
  "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe"
)

$browser = $browserCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $browser) {
  throw "Could not find Chrome or Edge. Install one of them, or export output\example_map.html with another browser screenshot tool."
}

$resolvedHtml = Resolve-Path -LiteralPath $HtmlPath
$resolvedOutputDir = Split-Path -Parent $OutputPng
New-Item -ItemType Directory -Force -Path $resolvedOutputDir | Out-Null

$htmlUri = ([System.Uri]$resolvedHtml.Path).AbsoluteUri
& $browser `
  "--headless=new" `
  "--disable-gpu" `
  "--hide-scrollbars" `
  "--window-size=$Width,$Height" `
  "--screenshot=$OutputPng" `
  $htmlUri | Out-Null

Write-Host $OutputPng
