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

$env:LOG_DRIVER = if ($env:DEBUG -eq '1') { 'json-file' } else { 'none' }

if (Get-Command xpra.exe -ErrorAction SilentlyContinue) {
    $env:XPRA_CLIENT = '1'
} else {
    $env:XPRA_CLIENT = '0'
}

try {
    Write-Host "Building (this can take several minutes)..."
    Invoke-Quiet { docker compose create --build }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed - rerun with DEBUG=1 to see why." -ForegroundColor Red
        exit 1
    }
    Invoke-Quiet { docker compose start api xpra-relay }

    # Output from inside a job never reaches the console; the container's own
    # banner prints the link and the "native client not found" hint.
    # Set-Location inside the job: Windows PowerShell 5.1 starts jobs in the
    # user's Documents folder, where `docker compose` can't find compose.yml.
    Start-Job -ScriptBlock {
        param($xpraClient, $root)
        Set-Location $root
        $linkUrl = 'http://127.0.0.1:10001/'
        docker compose logs -f browser 2>$null | Select-String -Pattern 'Code Co-occurrence Graphs is ready' -SimpleMatch | Select-Object -First 1 | Out-Null
        if ($xpraClient -eq '1') {
            Start-Process xpra.exe -ArgumentList 'attach', 'tcp://127.0.0.1:10001/', '--speed=100', '--min-speed=100' -WindowStyle Hidden
        } else {
            Start-Process $linkUrl
        }
    } -ArgumentList $env:XPRA_CLIENT, $PSScriptRoot | Out-Null

    $container = docker compose ps -a -q browser
    docker start -ai $container
} finally {
    Invoke-Quiet { docker compose down }
}
