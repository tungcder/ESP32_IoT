param(
  [ValidateRange(1024,65534)][int]$Port = 8090,
  [string]$Python = ""
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (!$Python) {
  $localPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
  $Python = if (Test-Path -LiteralPath $localPython) { $localPython } else { "python" }
}
Push-Location -LiteralPath $projectRoot
try {
  if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot ".certs\server.pem"))) {
    throw "Run .\ai\setup.ps1 first. See ai/README.md for HTTPS and iPhone setup."
  }
  & $Python -B -m ai.server --port $Port
  if ($LASTEXITCODE -ne 0) { throw "AI server stopped with an error. See the message above." }
} finally {
  Pop-Location
}
