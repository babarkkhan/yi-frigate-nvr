<#
  configure-cam.ps1 - apply post-flash settings to a yi-hack-MStar camera.

  DRY RUN BY DEFAULT. Nothing is changed unless you pass -Apply.

    .\configure-cam.ps1 -Ip 192.168.3.149 -Name yi-cam5
    .\configure-cam.ps1 -Ip 192.168.3.149 -Name yi-cam5 -Apply

  API (from upstream src/www/httpd/cgi-bin/):
    GET  /cgi-bin/get_configs.sh?conf=system
    POST /cgi-bin/set_configs.sh?conf=system   body = flat JSON of KEY:VALUE
    GET  /cgi-bin/reboot.sh
#>
param(
  [Parameter(Mandatory=$true)][string]$Ip,
  [string]$Name,
  [string]$SshPassword,
  [switch]$Apply,
  [switch]$SkipReboot
)

$ErrorActionPreference = 'Stop'

# Desired state. RTSP_STREAM stays 'high' on purpose - upstream warns that
# enabling both RTSP streams is not recommended, so Frigate downscales instead.
$desired = [ordered]@{
  'DISABLE_CLOUD' = 'yes'   # the entire point - stop talking to Yi's servers
  'TELNETD'       = 'no'    # open with no credentials otherwise
  'FTPD'          = 'no'    # same
  'RTSP'          = 'yes'
  'RTSP_STREAM'   = 'high'
  'SSHD'          = 'no'    # not needed; password is empty on all cams
}
if ($Name)        { $desired['HOSTNAME']     = $Name }
if ($SshPassword) { $desired['SSH_PASSWORD'] = $SshPassword }

function Get-CamConfig($ip) {
  $raw = Invoke-RestMethod "http://$ip/cgi-bin/get_configs.sh?conf=system" -TimeoutSec 15
  if ($raw -is [string]) { $raw = $raw | ConvertFrom-Json }
  return $raw
}

Write-Host ""
Write-Host "=== configure-cam : $Ip ===" -ForegroundColor Cyan
Write-Host ""

# identity
$st = Invoke-RestMethod "http://$Ip/cgi-bin/status.json" -TimeoutSec 15
if ($st -is [string]) { $st = $st | ConvertFrom-Json }
Write-Host ("  serial   : {0}" -f $st.serial_number)
Write-Host ("  model    : {0}" -f $st.model_suffix)
Write-Host ("  hack fw  : {0}" -f $st.fw_version)
Write-Host ("  stock fw : {0}" -f $st.home_version)
Write-Host ""

$cur = Get-CamConfig $Ip

$changes = [ordered]@{}
Write-Host "Planned changes:" -ForegroundColor Cyan
foreach ($k in $desired.Keys) {
  $now = $cur.$k
  $want = $desired[$k]
  if ($k -eq 'SSH_PASSWORD') {
    if ([string]::IsNullOrEmpty($now)) { $changes[$k] = $want; Write-Host "  $k : (empty) -> (set)" -ForegroundColor Yellow }
    else { Write-Host "  $k : already set, leaving alone" -ForegroundColor DarkGray }
    continue
  }
  if ($now -ne $want) { $changes[$k] = $want; Write-Host "  $k : '$now' -> '$want'" -ForegroundColor Yellow }
  else { Write-Host "  $k : already '$want'" -ForegroundColor DarkGray }
}

if ($changes.Count -eq 0) { Write-Host ""; Write-Host "Nothing to change." -ForegroundColor Green; Write-Host ""; exit 0 }

Write-Host ""
if (-not $Apply) {
  Write-Host "DRY RUN - nothing sent. Re-run with -Apply to make these changes." -ForegroundColor Magenta
  Write-Host ""
  exit 0
}

$body = ($changes | ConvertTo-Json -Compress)
Write-Host "POST /cgi-bin/set_configs.sh?conf=system" -ForegroundColor Cyan
Write-Host "  body: $body"
$resp = Invoke-RestMethod "http://$Ip/cgi-bin/set_configs.sh?conf=system" -Method Post -Body $body -TimeoutSec 20
if ($resp -is [string]) { $resp = $resp | ConvertFrom-Json }
if ($resp.error -eq 'false') { Write-Host "  accepted" -ForegroundColor Green }
else { Write-Host "  REJECTED: $($resp | ConvertTo-Json -Compress)" -ForegroundColor Red; exit 1 }

# verify written
Start-Sleep -Seconds 2
$after = Get-CamConfig $Ip
Write-Host ""
Write-Host "Verifying written config:" -ForegroundColor Cyan
$bad = 0
foreach ($k in $changes.Keys) {
  if ($k -eq 'SSH_PASSWORD' -or $k -eq 'HOSTNAME') { Write-Host "  $k : set (CGI handles separately, not verified)" -ForegroundColor DarkGray; continue }
  if ($after.$k -eq $changes[$k]) { Write-Host "  OK   $k = $($after.$k)" -ForegroundColor Green }
  else { Write-Host "  BAD  $k = '$($after.$k)' expected '$($changes[$k])'" -ForegroundColor Red; $bad++ }
}
if ($bad -gt 0) { Write-Host ""; Write-Host "$bad setting(s) did not stick. Not rebooting." -ForegroundColor Red; exit 1 }

if ($SkipReboot) { Write-Host ""; Write-Host "Config written. Reboot skipped - changes apply on next boot." -ForegroundColor Yellow; Write-Host ""; exit 0 }

Write-Host ""
Write-Host "Rebooting camera to apply..." -ForegroundColor Cyan
try { Invoke-RestMethod "http://$Ip/cgi-bin/reboot.sh" -TimeoutSec 10 | Out-Null } catch { }
Write-Host "  reboot issued. Camera returns in ~60s." -ForegroundColor Green
Write-Host ""
