<#
  harden-keepalive.ps1 - make the WSL keepalive self-healing.

    Run from an ELEVATED PowerShell:
    powershell -ExecutionPolicy Bypass -File scripts\harden-keepalive.ps1

  WHY THIS EXISTS
  ---------------
  install-boot-task.ps1 registered HomeNVR-WSL-Keepalive with an AtStartup
  trigger only. That is not enough. The keepalive action is

      wsl.exe -d Ubuntu -u root -e sleep infinity

  and ANY `wsl --shutdown` kills it with exit code 1. Task Scheduler's
  restart-on-failure does not reliably bring it back, and with only a boot
  trigger nothing re-runs it until Windows next reboots.

  Measured consequence (2026-08-29): the keepalive had been dead since
  2026-08-28 13:40. With nothing holding the distro open, WSL terminated it
  whenever it went idle - taking systemd, Docker, Frigate and Tailscale with
  it roughly every 30-60 seconds. Remote clients saw ERR_CONNECTION_ABORTED.

  This script adds a 5-minute repeating trigger alongside the boot trigger.
  MultipleInstances is IgnoreNew, so a healthy running keepalive is never
  double-started; the repeat only takes effect once the task is not running.
#>
$ErrorActionPreference = 'Stop'
$name = 'HomeNVR-WSL-Keepalive'

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
          [Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "Must run elevated (Run as administrator)." -ForegroundColor Red
  exit 1
}

$task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if (-not $task) {
  Write-Host "Task '$name' not found. Run install-boot-task.ps1 first." -ForegroundColor Red
  exit 1
}

$boot = New-ScheduledTaskTrigger -AtStartup
$rep  = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
          -RepetitionInterval (New-TimeSpan -Minutes 5) `
          -RepetitionDuration (New-TimeSpan -Days 3650)

Set-ScheduledTask -TaskName $name -Trigger @($boot, $rep) | Out-Null

$task = Get-ScheduledTask -TaskName $name
if ($task.State -ne 'Running') { Start-ScheduledTask -TaskName $name; Start-Sleep -Seconds 5 }

$task = Get-ScheduledTask -TaskName $name
$info = $task | Get-ScheduledTaskInfo
Write-Host ""
Write-Host "Triggers      : $($task.Triggers.Count) (boot + 5-minute repeat)" -ForegroundColor Green
Write-Host "MultipleInst  : $($task.Settings.MultipleInstances)" -ForegroundColor Green
Write-Host "State         : $($task.State)" -ForegroundColor Green
Write-Host "Last result   : $($info.LastTaskResult)" -ForegroundColor Green
Write-Host ""
Write-Host "Expected LastTaskResult values - both are HEALTHY:" -ForegroundColor Cyan
Write-Host "  267009      (0x41301) task is currently running" -ForegroundColor Cyan
Write-Host "  2147946720 (0x800710E0) a repeat trigger fired while the keepalive" -ForegroundColor Cyan
Write-Host "              was already running, so Task Scheduler refused to start" -ForegroundColor Cyan
Write-Host "              a second instance. That is MultipleInstances=IgnoreNew" -ForegroundColor Cyan
Write-Host "              doing its job - it is what you WANT to see every 5 min." -ForegroundColor Cyan
Write-Host "  1           the action exited - the keepalive is DEAD. The next" -ForegroundColor Cyan
Write-Host "              repeat trigger should revive it within 5 minutes." -ForegroundColor Cyan
Write-Host ""
Write-Host "Verify the distro now stays up - wait 5 minutes WITHOUT running any" -ForegroundColor Yellow
Write-Host "wsl command (each one starts the distro and hides the fault), then:" -ForegroundColor Yellow
Write-Host "  wsl -d Ubuntu -- systemctl show docker --property=ActiveEnterTimestamp --value" -ForegroundColor Yellow
Write-Host "The timestamp must be unchanged across checks." -ForegroundColor Yellow
