<#
  camera-speak.ps1 - push an audio clip to a camera's speaker.

    powershell -ExecutionPolicy Bypass -File scripts\camera-speak.ps1 -Camera cam5 -File assets\test-message.wav -Volume 8

  -ExecutionPolicy Bypass is REQUIRED - this machine blocks scripts by default.

  Converts anything ffmpeg can read into the format the firmware requires
  (8 kHz, 16-bit, mono, S16LE) and POSTs it to /cgi-bin/speaker.sh.

  Generate a spoken clip first with scripts\make-speech.ps1.

  IMPORTANT - READ docs/two-way-audio-plan.md FIRST.
  Audio output is only consumed while the RTSP backchannel is active, and the
  backchannel only exists on the `rRTSPServer` daemon, which stalls. All six
  cameras run `rtsp_server_yi` for stability, so this script is expected to
  return success WITHOUT producing sound. It is kept because it is correct and
  ready if the daemon situation changes upstream.
#>
param(
  [Parameter(Mandatory=$true)][string]$Camera,
  [Parameter(Mandatory=$true)][string]$File,
  [int]$Volume = 4,
  # Directory containing ffmpeg.exe. Adjust for your machine.
  [string]$FfmpegDir = 'C:/ffmpeg/bin'
)
$ErrorActionPreference = 'Stop'

$MAP = @{
  cam1 = '192.168.3.5';  cam2 = '192.168.3.22';  cam3 = '192.168.3.3'
  cam4 = '192.168.3.4';  cam5 = '192.168.3.149'; cam6 = '192.168.3.6'
}
$key = $Camera.ToLower() -replace '_.*$',''
if (-not $MAP.ContainsKey($key)) {
  Write-Host "Unknown camera '$Camera'. Use one of: $($MAP.Keys -join ', ')" -ForegroundColor Red; exit 1
}
$ip = $MAP[$key]
if (-not (Test-Path $File)) { Write-Host "No such file: $File" -ForegroundColor Red; exit 1 }

$ff = Join-Path $FfmpegDir 'ffmpeg.exe'
if (-not (Test-Path $ff)) { Write-Host "ffmpeg not found at $ff" -ForegroundColor Red; exit 1 }

$pcm = Join-Path $env:TEMP ("camspeak_{0}.pcm" -f $key)
Write-Host "Converting to 8kHz/16-bit/mono S16LE..." -ForegroundColor Cyan
& $ff -hide_banner -loglevel error -i $File -ar 8000 -ac 1 -f s16le -acodec pcm_s16le -y $pcm
if (-not (Test-Path $pcm)) { Write-Host "conversion failed" -ForegroundColor Red; exit 1 }
$bytes = (Get-Item $pcm).Length
Write-Host ("  {0} bytes = {1:N1}s of audio" -f $bytes, ($bytes/16000)) -ForegroundColor Green

Write-Host "POSTing to $Camera ($ip) at volume $Volume..." -ForegroundColor Cyan
$r = Invoke-RestMethod "http://$ip/cgi-bin/speaker.sh?vol=$Volume" -Method Post `
       -InFile $pcm -ContentType 'application/octet-stream' -TimeoutSec 30
if ($r -is [string]) { $r = $r | ConvertFrom-Json }
if ($r.error -eq 'false') {
  Write-Host "  accepted by the camera" -ForegroundColor Green
  Write-Host "  NOTE: 'accepted' is not 'audible' - see the header of this script." -ForegroundColor Yellow
} else {
  Write-Host "  rejected: $($r | ConvertTo-Json -Compress)" -ForegroundColor Red
}
Remove-Item $pcm -ErrorAction SilentlyContinue
