$atlasProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$atlasHealthUrl = 'http://127.0.0.1:5173/'
$atlasOutLog = Join-Path $atlasProjectPath 'vite-background.log'
$atlasErrorLog = Join-Path $atlasProjectPath 'vite-background-error.log'

function Test-AtlasWebsite {
    try {
        $atlasResponse = Invoke-WebRequest -UseBasicParsing -Uri $atlasHealthUrl -TimeoutSec 2
        return $atlasResponse.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (Test-AtlasWebsite) {
    Write-Host 'Website is already running: http://127.0.0.1:5173/#/'
    exit 0
}

$atlasListener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($atlasListener) {
    throw 'Port 5173 is occupied by another program. Close that program, then run this starter again.'
}

$atlasUserProfilePath = [Environment]::GetFolderPath('UserProfile')
$atlasWorkspaceUserPath = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $atlasProjectPath))
$atlasNodeCandidates = @(
    (Join-Path $atlasUserProfilePath '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'),
    (Join-Path $atlasWorkspaceUserPath '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
)
$atlasNode = $atlasNodeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$atlasVite = Join-Path $atlasProjectPath 'node_modules\vite\bin\vite.js'

if (-not $atlasNode) {
    $atlasSystemNode = Get-Command node -ErrorAction SilentlyContinue
    if ($atlasSystemNode) { $atlasNode = $atlasSystemNode.Source }
}
if (-not $atlasNode) {
    throw 'Node.js was not found. Reopen the project in Codex and ask it to start the website.'
}
if (-not (Test-Path -LiteralPath $atlasVite)) {
    throw 'Website dependencies are missing. Reopen the project in Codex and ask it to restore the website.'
}

Start-Process -FilePath $atlasNode `
    -ArgumentList @($atlasVite, '--host', '127.0.0.1', '--port', '5173', '--strictPort') `
    -WorkingDirectory $atlasProjectPath `
    -WindowStyle Hidden `
    -RedirectStandardOutput $atlasOutLog `
    -RedirectStandardError $atlasErrorLog | Out-Null

for ($atlasAttempt = 0; $atlasAttempt -lt 30; $atlasAttempt++) {
    Start-Sleep -Milliseconds 250
    if (Test-AtlasWebsite) {
        Write-Host 'Website started successfully: http://127.0.0.1:5173/#/'
        exit 0
    }
}

Write-Host 'Website did not start. Recent error output:'
Get-Content -LiteralPath $atlasErrorLog -Tail 20 -ErrorAction SilentlyContinue
exit 1
