<#
  install-boot-task.ps1 - make the NVR survive reboots.

  RUN THIS IN AN ELEVATED (Administrator) POWERSHELL:
      powershell -ExecutionPolicy Bypass -File scripts\install-boot-task.ps1

  Why this is needed
  ------------------
  WSL2 terminates the distro when nothing is using it. That takes the Docker
  daemon and every container with it, so Frigate silently stops recording.
  Setting vmIdleTimeout=-1 in .wslconfig is NOT sufficient - measured on
  2026-08-22, the distro still stopped after ~100s idle. A long-running
  process inside WSL is required to hold it open.

  This task runs `sleep infinity` inside the distro forever, which does that,
  and starts AT BOOT so it needs nobody to log in.

  Credentials
  -----------
  Uses LogonType S4U: runs as your account at boot WITHOUT storing your
  Windows password. S4U grants local resources only, which is all WSL needs.
  WSL distros are registered per-user, so this cannot run as SYSTEM - SYSTEM
  has its own registry hive and would report no distributions.
#>
$ErrorActionPreference = 'Stop'

$pr = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "STOP: run this in an elevated PowerShell (Run as Administrator)." -ForegroundColor Red
  exit 1
}

$name = "HomeNVR-WSL-Keepalive"
$me   = [Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Installing '$name' to run at boot as $me" -ForegroundColor Cyan

try { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue } catch {}

$action    = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d Ubuntu -u root -e sleep infinity"

# TWO triggers, deliberately. AtStartup alone is not enough: any `wsl --shutdown`
# kills the keepalive with exit code 1, and with only a boot trigger nothing
# re-runs it until Windows next reboots. Measured 2026-08-29 - the keepalive had
# been dead 24h, so WSL terminated the distro on every idle period and took
# Docker, Frigate and Tailscale down with it every 30-60 seconds.
# MultipleInstances=IgnoreNew (below) means the repeat never double-starts a
# healthy keepalive; it only fires once the task has actually stopped.
$bootTrigger   = New-ScheduledTaskTrigger -AtStartup
$repeatTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
                   -RepetitionInterval (New-TimeSpan -Minutes 5) `
                   -RepetitionDuration (New-TimeSpan -Days 3650)
$trigger   = @($bootTrigger, $repeatTrigger)
$principal = New-ScheduledTaskPrincipal -UserId $me -LogonType S4U -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -Hidden -MultipleInstances IgnoreNew -StartWhenAvailable

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
  -Principal $principal -Settings $settings `
  -Description "Holds the WSL2 VM open so Frigate and Tailscale keep running. WSL stops the distro when idle, which stops Docker and every container." | Out-Null

Write-Host "  registered" -ForegroundColor Green

Write-Host "Starting it now to verify..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $name
Start-Sleep -Seconds 30

$state = (Get-ScheduledTask -TaskName $name).State
Write-Host "  task state : $state"
$wsl = (wsl --list --verbose 2>&1 | Out-String) -replace "`0",""
if ($wsl -match 'Running') {
  Write-Host "  wsl state  : Running" -ForegroundColor Green
} else {
  Write-Host "  wsl state  : NOT running - S4U may lack rights here." -ForegroundColor Yellow
  Write-Host "  Fallback: open Task Scheduler, edit '$name', and choose" -ForegroundColor Yellow
  Write-Host "  'Run whether user is logged on or not' (stores your password)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Waiting 100s to confirm the distro stays up..." -ForegroundColor Cyan
Start-Sleep -Seconds 100
$wsl2 = (wsl --list --verbose 2>&1 | Out-String) -replace "`0",""
if ($wsl2 -match 'Running') {
  Write-Host "  CONFIRMED: WSL stayed up. The NVR will survive reboots." -ForegroundColor Green
} else {
  Write-Host "  WSL stopped again - the keepalive is not holding. Tell Claude." -ForegroundColor Red
}
