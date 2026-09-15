<#
  camera-speak.ps1 - push an audio clip to a camera's speaker.

    powershell -ExecutionPolicy Bypass -File scripts\camera-speak.ps1 -Camera cam1 -File assets\test-message.wav

  -ExecutionPolicy Bypass is REQUIRED - this machine blocks scripts by default.

  Converts anything ffmpeg can read into the format the firmware requires
  (16 kHz, 16-bit, mono, S16LE) and uploads it as multipart form data.
  Use -RawPcm for an already-converted PCM file, or -PrepareOnly to validate
  without sending audio. Playback is limited to ten seconds per upload.

  Generate a spoken clip first with scripts\make-speech.ps1.

  Cam1 (MStar 0.5.7) audible playback was confirmed with the alternative RTSP
  daemon and ONVIF_AUDIO_BC=NONE. This is clip playback, not live intercom.
  Other cameras require their own audible pilot. HTTP acceptance alone does
  not prove sound. See docs/two-way-audio-plan.md.
#>
param(
  [Parameter(Mandatory=$true)][string]$Camera,
  [Parameter(Mandatory=$true)][string]$File,
  [ValidateRange(0,8)][int]$Volume = 1,
  [switch]$RawPcm,
  [switch]$PrepareOnly,
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

$temporaryPcm = $null
try {
  if ($RawPcm) {
    $pcm = (Resolve-Path -LiteralPath $File).Path
  } else {
    $ff = Join-Path $FfmpegDir 'ffmpeg.exe'
    if (-not (Test-Path -LiteralPath $ff)) { throw "ffmpeg not found at $ff. Set -FfmpegDir or supply 16 kHz PCM with -RawPcm." }
    $temporaryPcm = Join-Path $env:TEMP ("camspeak_{0}.pcm" -f [Guid]::NewGuid().ToString('N'))
    $pcm = $temporaryPcm
    & $ff -hide_banner -loglevel error -i $File -t 10 -ar 16000 -ac 1 -f s16le -acodec pcm_s16le -y $pcm
    if ($LASTEXITCODE -ne 0) { throw 'Audio conversion failed.' }
  }
  if ((Get-Item -LiteralPath $pcm).Length -gt 320000) { throw 'PCM exceeds the ten-second upload limit.' }
  $audioBytes = [IO.File]::ReadAllBytes($pcm)
  if ($audioBytes.Length -eq 0 -or $audioBytes.Length % 2 -ne 0 -or $audioBytes.Length -gt 320000) {
    throw 'Expected nonempty 16-bit mono PCM, at most ten seconds (320000 bytes).'
  }
  if ($RawPcm -and $audioBytes.Length -ge 4 -and [Text.Encoding]::ASCII.GetString($audioBytes,0,4) -eq 'RIFF') {
    throw '-RawPcm requires headerless PCM, not a WAV file.'
  }
  $boundary = 'nvr-speaker-' + [Guid]::NewGuid().ToString('N')
  # Firmware strips through Content-Type, so it MUST be the final part header.
  $prefix = [Text.Encoding]::ASCII.GetBytes("--$boundary`r`nContent-Disposition: form-data; name=`"file`"; filename=`"message.pcm`"`r`nContent-Type: application/octet-stream`r`n`r`n")
  $suffix = [Text.Encoding]::ASCII.GetBytes("`r`n--$boundary--`r`n")
  $buffer = New-Object IO.MemoryStream
  try {
    $buffer.Write($prefix,0,$prefix.Length)
    $buffer.Write($audioBytes,0,$audioBytes.Length)
    $buffer.Write($suffix,0,$suffix.Length)
    $body = $buffer.ToArray()
  } finally { $buffer.Dispose() }
  Write-Host ("Prepared {0:N2}s of 16 kHz mono PCM for {1}, gain {2}x." -f ($audioBytes.Length/32000),$key,$Volume)
  if ($PrepareOnly) { Write-Host 'Prepared only; no audio sent.'; return }
  $r = Invoke-RestMethod "http://$ip/cgi-bin/speaker.sh?vol=$Volume" -Method Post `
       -Body $body -ContentType "multipart/form-data; boundary=$boundary" -TimeoutSec 25
  if ($r -is [string]) { $r = $r | ConvertFrom-Json }
  if ($null -eq $r.error -or "$($r.error)".ToLowerInvariant() -ne 'false') {
    throw "Camera rejected the upload: $($r | ConvertTo-Json -Compress)"
  }
  Write-Host 'Camera accepted the clip. Confirm audible output with someone nearby.'
} finally {
  if ($temporaryPcm -and (Test-Path -LiteralPath $temporaryPcm)) { Remove-Item -LiteralPath $temporaryPcm }
}
