# Native PowerShell fixture checks; no network, WSL, Docker or production files.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../scripts/probe-nvr-windows.ps1')
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('nvr-probe-test-' + [guid]::NewGuid().ToString('N'))
$now = [datetime]::SpecifyKind([datetime]'2026-09-12 00:00:30', [DateTimeKind]::Utc)
$dir = Join-Path $fixture '2026-09-11/23/cam'
try {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $file = Join-Path $dir 'recording.mp4'
    [IO.File]::WriteAllBytes($file, [byte[]]@(1,2,3))
    [IO.File]::SetLastWriteTimeUtc($file, $now.AddSeconds(-60))
    $stats = [pscustomobject]@{cameras=[pscustomobject]@{cam=[pscustomobject]@{camera_fps=5}}}
    $good = Get-NvrCameraAssessment $stats $fixture @('cam') $now
    if (-not $good.ok) { throw 'Fresh previous-day recording should pass across midnight' }
    if ((Get-NvrCameraAssessment $stats $fixture @('cam','missing') $now).ok) { throw 'Missing camera passed' }
    if ((Get-NvrCameraAssessment $stats $fixture @() $now).ok) { throw 'Empty camera list passed' }
    [IO.File]::SetLastWriteTimeUtc($file, $now.AddSeconds(-300))
    if ((Get-NvrCameraAssessment $stats $fixture @('cam') $now).ok) { throw 'Stale recording passed' }
    [IO.File]::SetLastWriteTimeUtc($file, $now.AddSeconds(-60))
    $stats.cameras.cam.camera_fps = 0
    if ((Get-NvrCameraAssessment $stats $fixture @('cam') $now).ok) { throw 'Zero FPS passed' }
    Write-Output 'PASS: five Windows probe fixtures'
} finally {
    # The target is the exact unique directory created above, never user media.
    $resolved = [IO.Path]::GetFullPath($fixture)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe fixture cleanup path' }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
