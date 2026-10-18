param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Config,
    [string]$Script = (Join-Path $PSScriptRoot 'nvr-monitor.py')
)
$ErrorActionPreference = 'Stop'
foreach ($path in @($Python,$Config,$Script)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing required deployment file" }
    if ($path.Contains('"')) { throw 'Invalid deployment path' }
}
$name = 'HomeNVR-Health-Recovery'
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
# Commission only after the actual scheduled account passes native health,
# heartbeat delivery, and a read-only WSL diagnosis. No intentional outage here.
$cfg = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$cfg | Add-Member -NotePropertyName commission_on_success -NotePropertyValue $true -Force
$cfg.recovery_enabled = $false
$cfg | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Config -Encoding UTF8
$action = New-ScheduledTaskAction -Execute $Python -Argument ('"{0}" --config "{1}"' -f $Script,$Config)
$boot = New-ScheduledTaskTrigger -AtStartup
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $me -LogonType S4U -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -Hidden -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger @($boot,$repeat) `
    -Principal $principal -Settings $settings -Description 'Observe capture and recording before WSL; bounded recovery with independent VPS heartbeat.' -Force -ErrorAction Stop | Out-Null
Start-ScheduledTask -TaskName $name -ErrorAction Stop
Write-Output 'Registered and started HomeNVR-Health-Recovery'
