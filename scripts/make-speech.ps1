<#
  make-speech.ps1 - synthesise a spoken WAV on the NVR using built-in Windows TTS.

    powershell -ExecutionPolicy Bypass -File scripts\make-speech.ps1 -Text "Hello" -Out assets\hello.wav

  The cameras have no TTS engine (nanotts needs an SD card, and they run
  cardless). Synthesising here and pushing the audio is the better design
  anyway - it keeps the cameras dumb and gives far better voices.

  Pair with camera-speak.ps1 to actually send it.
#>
param(
  [Parameter(Mandatory=$true)][string]$Text,
  [Parameter(Mandatory=$true)][string]$Out,
  [string]$Voice,
  [int]$Rate = -1
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$dir = Split-Path -Parent $Out
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($Voice) { $s.SelectVoice($Voice) }
$s.Rate = $Rate
$s.SetOutputToWaveFile($Out)
$s.Speak($Text)
$s.Dispose()
Write-Host ("  wrote {0} ({1:N0} bytes)" -f $Out, (Get-Item $Out).Length) -ForegroundColor Green
Write-Host "  voices: $(( [System.Speech.Synthesis.SpeechSynthesizer]::new().GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name } ) -join ', ')"
