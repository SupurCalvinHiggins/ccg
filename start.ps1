Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path encrypted-volume | Out-Null

function Invoke-Quiet {
    param([ScriptBlock]$Script)
    if ($env:DEBUG -eq '1') {
        & $Script
    } else {
        & $Script *> $null
    }
}

$ComposeFiles = @("-f", "compose.yml", "-f", "compose.vnc.yaml")

$env:LOG_DRIVER = if ($env:DEBUG -eq '1') { 'json-file' } else { 'none' }

try {
    Invoke-Quiet { docker compose @ComposeFiles build }
    Invoke-Quiet { docker compose @ComposeFiles up -d api proxy vnc-relay }
    Write-Host "Open http://localhost:8080 for the app."

    Invoke-Quiet { docker compose @ComposeFiles create browser }
    $container = docker compose @ComposeFiles ps -a -q browser
    docker start -ai $container
} finally {
    Invoke-Quiet { docker compose @ComposeFiles down }
}
