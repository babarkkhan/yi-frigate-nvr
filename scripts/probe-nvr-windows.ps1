<#
Read-only Windows health probe. No WSL/Docker commands, restarts or notifications.
Run with Windows PowerShell 5.1 or PowerShell 7. Exit 0 healthy, 1 unhealthy.
File freshness plus API frames is not a media decode or remote-phone test.
#>
param(
    [string]$ApiUrl = 'http://127.0.0.1:5000/api/stats',
    [string]$RecordingRoot = 'D:\frigate\media\recordings',
    [string[]]$ExpectedCameras = @('cam1_mensroom','cam2_living','cam3_kitchen','cam4_hallway','cam5_laundry','cam6_extra')
)

function Get-NvrCameraAssessment {
    param($Stats, [string]$Root, [string[]]$Expected, [datetime]$Now = [datetime]::UtcNow)
    $problems = New-Object 'System.Collections.Generic.List[string]'
    $cameras = @()
    if (-not $Expected -or $Expected.Count -eq 0) { $problems.Add('No expected cameras configured') }
    foreach ($name in $Expected) {
        if ($name -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid expected camera name' }
        $value = $Stats.cameras.$name
        $fps = if ($null -ne $value) { $value.camera_fps } else { $null }
        if ($null -eq $fps -or $fps -is [string] -or $fps -is [bool] -or
            [double]::IsNaN([double]$fps) -or [double]::IsInfinity([double]$fps) -or
            [double]$fps -lt 1 -or [double]$fps -ge 1000) {
            $problems.Add("${name}: missing/invalid frame rate")
        }
        # UTC directories; inspect only this and the previous hour, including midnight.
        $latest = $null
        foreach ($hour in @($Now, $Now.AddHours(-1))) {
            $path = Join-Path (Join-Path (Join-Path $Root $hour.ToString('yyyy-MM-dd')) $hour.ToString('HH')) $name
            if (-not (Test-Path -LiteralPath $path -PathType Container)) { continue }
            $file = Get-ChildItem -LiteralPath $path -Filter '*.mp4' -File -ErrorAction Stop |
                Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
            if ($file -and (-not $latest -or $file.LastWriteTimeUtc -gt $latest.LastWriteTimeUtc)) { $latest = $file }
        }
        $age = if ($latest) { ($Now - $latest.LastWriteTimeUtc).TotalSeconds } else { $null }
        if (-not $latest -or $latest.Length -eq 0 -or $age -gt 120 -or $age -lt -30) {
            $problems.Add("${name}: missing/stale/invalid recording file")
        }
        $cameras += [pscustomobject]@{camera=$name; fps=$fps; recordingAgeSeconds=$age}
    }
    [pscustomobject]@{ok=($problems.Count -eq 0); problems=@($problems.ToArray()); cameras=$cameras}
}

if ($MyInvocation.InvocationName -ne '.') {
    $ErrorActionPreference = 'Stop'
    try {
        $stats = Invoke-RestMethod -Uri $ApiUrl -TimeoutSec 8
        $result = Get-NvrCameraAssessment -Stats $stats -Root $RecordingRoot -Expected $ExpectedCameras
        $result | ConvertTo-Json -Depth 5 -Compress
        if (-not $result.ok) { exit 1 }
        exit 0
    } catch {
        [pscustomobject]@{ok=$false; problems=@('Probe failed'); errorType=$_.Exception.GetType().Name} |
            ConvertTo-Json -Compress
        exit 1
    }
}
