$atlasProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $atlasProjectPath

$atlasUserProfilePath = [Environment]::GetFolderPath('UserProfile')
$atlasWorkspaceUserPath = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $atlasProjectPath))
$atlasNodeCandidates = @(
    (Join-Path $atlasUserProfilePath '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'),
    (Join-Path $atlasWorkspaceUserPath '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
)
$atlasBundledNode = $atlasNodeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$atlasVite = Join-Path $atlasProjectPath 'node_modules\vite\bin\vite.js'

if (-not (Test-Path -LiteralPath $atlasVite)) {
    throw 'Website dependencies are missing. Please reopen this project in Codex and ask it to restore the local environment.'
}

if ($atlasBundledNode) {
    $atlasNode = $atlasBundledNode
} else {
    $atlasSystemNode = Get-Command node -ErrorAction SilentlyContinue
    if (-not $atlasSystemNode) {
        throw 'Node.js was not found. Please reopen this project in Codex and ask it to start the website.'
    }
    $atlasNode = $atlasSystemNode.Source
}

Write-Host ''
Write-Host 'China-Africa Aid Database is starting...'
Write-Host 'Open: http://127.0.0.1:5173/#/'
Write-Host 'Keep this window open while using the website.'
Write-Host ''

& $atlasNode $atlasVite --host 127.0.0.1 --port 5173 --strictPort
