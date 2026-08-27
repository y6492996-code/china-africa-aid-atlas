$atlasProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$atlasDataConfigPath = Join-Path $atlasProjectPath 'data\config\data-path.csv'
$atlasDefaultDataPath = (Import-Csv -LiteralPath $atlasDataConfigPath -Encoding UTF8 | Select-Object -First 1).path
$atlasConfiguredDataPath = [Environment]::GetEnvironmentVariable('ATLAS_RAW_DATA_DIR')
$atlasDataPath = if ($atlasConfiguredDataPath) { $atlasConfiguredDataPath } else { $atlasDefaultDataPath }
$atlasUserProfilePath = [Environment]::GetFolderPath('UserProfile')
$atlasWorkspaceUserPath = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $atlasProjectPath))
$atlasPythonCandidates = @(
    (Join-Path $atlasUserProfilePath '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    (Join-Path $atlasWorkspaceUserPath '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
)
$atlasBundledPython = $atlasPythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $atlasBundledPython) {
    throw 'The bundled Python runtime is missing. Reopen the project in Codex and ask it to rebuild the research panels.'
}
if (-not (Test-Path -LiteralPath $atlasDataPath)) {
    throw "Clean data directory was not found: $atlasDataPath"
}

Set-Location -LiteralPath $atlasProjectPath
$atlasReviewDecisionPath = Join-Path $atlasProjectPath 'data\review\match_review_decisions.csv'
$atlasBuildArguments = @(
    'scripts\build_research_panels.py',
    '--data-dir', $atlasDataPath,
    '--output-dir', 'data\generated',
    '--public-dir', 'public\data\generated',
    '--dashboard-output', 'public\data\dashboard.json'
)
if (Test-Path -LiteralPath $atlasReviewDecisionPath) {
    $atlasBuildArguments += @('--review-decisions', $atlasReviewDecisionPath)
}
& $atlasBundledPython @atlasBuildArguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $atlasBundledPython 'scripts\validate_research_panels.py' --panel-dir 'data\generated'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$atlasReviewAuditPath = Join-Path $atlasProjectPath 'data\review\match_review_batch_audit.csv'
if ((Test-Path -LiteralPath $atlasReviewDecisionPath) -and (Test-Path -LiteralPath $atlasReviewAuditPath)) {
    & $atlasBundledPython 'scripts\audit_match_review_consistency.py' `
        --decisions $atlasReviewDecisionPath `
        --audit $atlasReviewAuditPath `
        --candidates 'data\generated\match_candidates.csv' `
        --applied 'data\generated\match_review_decisions_applied.csv' `
        --entities 'data\generated\project_entity_index.csv' `
        --output 'data\generated\match_review_consistency_report.json'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

exit 0
