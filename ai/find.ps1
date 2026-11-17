param([string]$LaptopIP = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$localPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$taskPython = if (Test-Path -LiteralPath $localPython) { $localPython } else { "python" }
Push-Location -LiteralPath $projectRoot
try {
  $networkArgs = @("-B", "-X", "utf8", "-m", "ai.network", "--find")
  if ($LaptopIP) { $networkArgs += @("--laptop-ip", $LaptopIP) }
  & $taskPython @networkArgs
  if ($LASTEXITCODE -ne 0) { throw "Khong tim duoc dia chi. Kiem tra Wi-Fi cua laptop." }
} finally {
  Pop-Location
}
