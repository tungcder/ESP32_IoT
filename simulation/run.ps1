param(
    [ValidateRange(1024, 65535)][int]$Port = 8081,
    [string]$WebotsPath
)

$ErrorActionPreference = 'Stop'
$worldPath = Join-Path $PSScriptRoot 'webots\worlds\esp32_car.wbt'
if (-not (Test-Path -LiteralPath $worldPath -PathType Leaf)) {
    throw "Khong tim thay world: $worldPath"
}
if (-not $WebotsPath) {
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Webots\msys64\mingw64\bin\webots.exe'),
        'G:\Webots\msys64\mingw64\bin\webots.exe'
    )
    if ($env:WEBOTS_HOME) {
        $candidates = @((Join-Path $env:WEBOTS_HOME 'msys64\mingw64\bin\webots.exe')) + $candidates
    }
    $WebotsPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $WebotsPath -or -not (Test-Path -LiteralPath $WebotsPath -PathType Leaf)) {
    throw 'Khong tim thay Webots. Dung -WebotsPath de chi dinh duong dan webots.exe.'
}
$previousPort = [Environment]::GetEnvironmentVariable('ESP32_WEBOTS_PORT', 'Process')
try {
    $env:ESP32_WEBOTS_PORT = [string]$Port
    Write-Host "World: $worldPath"
    Write-Host "Web dieu khien: http://127.0.0.1:$Port"
    Write-Host 'Neu cong dang duoc dung, dong world cu hoac chon -Port 8082.'
    & $WebotsPath --mode=realtime --stdout --stderr $worldPath
} finally {
    [Environment]::SetEnvironmentVariable('ESP32_WEBOTS_PORT', $previousPort, 'Process')
}
