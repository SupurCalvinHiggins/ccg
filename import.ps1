param(
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$Files
)
# Copy one or more files into the sandboxed browser's encrypted data volume,
# then (after confirming) securely delete the originals from this machine.
# The browser must already be running (.\start.ps1).
#
#   .\import.ps1 interview_alice.csv interview_bob.csv
#
Set-Location $PSScriptRoot

if (-not $Files -or $Files.Count -eq 0) {
    Write-Error "usage: .\import.ps1 <file> [file...]"
    exit 1
}
foreach ($f in $Files) {
    if (-not (Test-Path -PathType Leaf $f)) {
        Write-Error "not a file: $f"
        exit 1
    }
}

$BrowserId = (docker ps --filter "name=browser" --format '{{.ID}}' | Select-Object -First 1)
if (-not $BrowserId) {
    Write-Error "no running 'browser' container found -- start it with .\start.ps1 first"
    exit 1
}

# Not `docker cp`: some Docker versions refuse to copy into a container with
# read_only:true regardless of the destination being on a writable mount.
# `docker exec` isn't subject to that check. Pipe raw bytes via the
# process's own stdin stream (not the PowerShell pipeline) so nothing gets
# newline/encoding-translated along the way.
function Copy-ToBrowser {
    param([string]$SourcePath, [string]$DestName)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "docker"
    foreach ($arg in @("exec", "-i", $BrowserId, "sh", "-c", "cat > '/data/$DestName'")) {
        $psi.ArgumentList.Add($arg)
    }
    $psi.RedirectStandardInput = $true
    $psi.UseShellExecute = $false
    $proc = [System.Diagnostics.Process]::Start($psi)
    $in = [System.IO.File]::OpenRead((Resolve-Path $SourcePath))
    $in.CopyTo($proc.StandardInput.BaseStream)
    $in.Close()
    $proc.StandardInput.Close()
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) {
        throw "copy failed for $SourcePath"
    }
}

Write-Host "Copying into the sandboxed browser's encrypted volume:"
foreach ($f in $Files) {
    $name = Split-Path $f -Leaf
    Write-Host "  $f -> browser:/data/$name"
    Copy-ToBrowser -SourcePath $f -DestName $name
}

Write-Host ""
$reply = Read-Host "Delete the original file(s) from this machine now? [y/N]"
if ($reply -notmatch '^(?i:y|yes)$') {
    Write-Host "Leaving original files in place."
    exit 0
}

$cipherAvailable = $null -ne (Get-Command cipher.exe -ErrorAction SilentlyContinue)
$parents = @{}
foreach ($f in $Files) {
    $dir = Split-Path -Parent $f
    if (-not $dir) { $dir = "." }
    $parents[$dir] = $true
    Remove-Item -Force $f
    Write-Host "  deleted $f"
}

if ($cipherAvailable) {
    Write-Host "Overwriting freed disk space (cipher /w) -- this can take a while..."
    foreach ($dir in $parents.Keys) {
        cipher /w:"$dir" | Out-Null
    }
    Write-Host "  done."
} else {
    Write-Host "warning: 'cipher' isn't available here -- this was a plain delete" -ForegroundColor Yellow
    Write-Host "(no overwrite guarantee; especially weak on SSDs)." -ForegroundColor Yellow
}
