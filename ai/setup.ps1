param(
  [string]$LaptopIP = "",
  [ValidateRange(1024,65534)][int]$Port = 8090,
  [string]$Python = ""
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$localPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Push-Location -LiteralPath $projectRoot
try {
  if (!(Test-Path -LiteralPath $localPython)) {
    if ($Python) { & $Python -m venv (Join-Path $PSScriptRoot ".venv") }
    else { & py -3.12 -m venv (Join-Path $PSScriptRoot ".venv") }
    if ($LASTEXITCODE -ne 0) { throw "Install Python 3.12, or pass -Python path-to-python.exe." }
  }
  & $localPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
  if ($LASTEXITCODE -ne 0) { throw "Could not install dependencies. Check network and Python version." }
  $setupArgs = @("-B", "-m", "ai.https_setup", "--port", "$Port")
  if ($LaptopIP) { $setupArgs += @("--ip", $LaptopIP) }
  & $localPython @setupArgs
  if ($LASTEXITCODE -ne 0) { throw "HTTPS setup failed. See ai/README.md." }
  Write-Host ""
  Write-Host "Next: trust ai/.certs/iphone-root.cer on Windows (see ai/README.md)."
  Write-Host "Start: .\ai\run.ps1 -Port $Port"
  Write-Host "On iPhone: scan the setup QR once, install certificate and enable full trust."
  Write-Host "Daily: scan camera QR > Enable camera > Allow."
} finally {
  Pop-Location
}
