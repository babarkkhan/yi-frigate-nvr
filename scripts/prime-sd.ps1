<#
  prime-sd.ps1 - copy yi-hack firmware onto a prepared SD card.
  Run on the machine with the SD card reader.

  Usage:
    powershell -ExecutionPolicy Bypass -File prime-sd.ps1 -Drive G -Model MStar
    powershell -ExecutionPolicy Bypass -File prime-sd.ps1 -Drive G -Model Allwinner

  MStar     -> cams 1 (men's room), 2 (living room), 4 (hallway), 5 (extra)
  Allwinner -> cam 3 (kitchen)

  This script COPIES only. It never formats and never deletes.
#>
param(
  [Parameter(Mandatory=$true)][string]$Drive,
  [ValidateSet('MStar','Allwinner')][string]$Model = 'MStar',
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

$EXPECTED = @{
  'MStar' = @{
    'Source' = 'MStar_y203c__cams_1_2_4_5'
    'Files'  = @{
      'home_y203c' = '576123CA2D3DCD7B781B149E91E2B926A51F0FB1472DC3000A69CED47F2D4F9F'
      'sys_y203c'  = '70706AD6ACCFD1F3AA296CFEF8B080EF77ACBD4ADF945A3AA92208475029672A'
    }
  }
  'Allwinner' = @{
    'Source' = 'Allwinner_y20ga__cam3_kitchen'
    'Files'  = @{
      'Factory\config.sh'              = 'EF7E7203C7A00794315530697A941A1A65F7CCA4EA6A6012F493735ECE23F3EE'
      'Factory\configure_wifi.cfg.ori' = '9D17DB0FC99E4E6ED9669770366149FCD38CEBDD6EA8957025177CAC770E8DBC'
      'Factory\configure_wifi.sh'      = '00C86ADC8947A9C748A2A9E88FAFAA83E68D5F8C2DE1973AB482F3F520627FC0'
      'Factory\factory_test.sh'        = 'E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855'
      'home_y20gam.stage'              = '9DC3AE9ABA7A0A90E8AFD1E48D10F1AF6BA22B429AC0CBD37F75D5CA0030391B'
      'newhome\base\tools\extpkg.sh'   = '2E8F8E772EBFA27D68861A1FB8FFACC1DA609249DF6C784983CFBF20BC1837E9'
    }
  }
}

function Fail($msg) { Write-Host ""; Write-Host "STOP: $msg" -ForegroundColor Red; Write-Host ""; exit 1 }
function Ok($msg)   { Write-Host "  OK   $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  WARN $msg" -ForegroundColor Yellow }

$letter = $Drive.Trim().TrimEnd(':').ToUpper()
if ($letter.Length -ne 1) { Fail "Drive must be a single letter, e.g. -Drive G" }
$root = "${letter}:\"

Write-Host ""
Write-Host "=== prime-sd.ps1 : $Model -> ${letter}: ===" -ForegroundColor Cyan
Write-Host ""

# --- checks -----------------------------------------------------------------
$vol = Get-Volume -DriveLetter $letter -ErrorAction SilentlyContinue
if (-not $vol) { Fail "No volume at ${letter}:. Check the drive letter." }

Write-Host "Target: ${letter}:  label='$($vol.FileSystemLabel)'  fs=$($vol.FileSystem)  type=$($vol.DriveType)  size=$([math]::Round($vol.Size/1GB,2))GB"
Write-Host ""

if ($vol.DriveType -ne 'Removable') {
  if (-not $Force) { Fail "${letter}: is '$($vol.DriveType)', not Removable. This does not look like an SD card. Re-run with -Force only if you are certain." }
  Warn "Not a removable drive, continuing because -Force was given"
} else { Ok "Removable drive" }

if ($vol.FileSystem -ne 'FAT32') {
  Fail "Filesystem is '$($vol.FileSystem)', but the hack REQUIRES FAT32. exFAT will silently fail to flash. Reformat as FAT32 and re-run."
}
Ok "FAT32"

if ($vol.Size -gt 34359738368) { Warn "Card is larger than 32GB. Smaller/older cards are more reliable for this." }
else { Ok "Card size within the usual 32GB guidance" }

$existing = @(Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue |
              Where-Object { $_.Name -notin @('System Volume Information','$RECYCLE.BIN') })
if ($existing.Count -gt 0) {
  Write-Host ""
  Write-Host "Card is not empty. Existing items:" -ForegroundColor Yellow
  $existing | ForEach-Object { Write-Host "    $($_.Name)" }
  Write-Host ""
  if (-not $Force) { Fail "The card must contain ONLY the firmware files. Delete the above (or reformat FAT32), then re-run. Use -Force to copy anyway." }
  Warn "Copying onto a non-empty card because -Force was given"
} else { Ok "Card is empty" }

# --- copy -------------------------------------------------------------------
$srcDir = Join-Path $PSScriptRoot $EXPECTED[$Model].Source
if (-not (Test-Path $srcDir)) { Fail "Source folder not found: $srcDir" }

Write-Host ""
Write-Host "Copying from: $srcDir" -ForegroundColor Cyan
Copy-Item -Path (Join-Path $srcDir '*') -Destination $root -Recurse -Force
Ok "Copy complete"

# --- verify -----------------------------------------------------------------
Write-Host ""
Write-Host "Verifying SHA-256 on the card..." -ForegroundColor Cyan
$bad = 0
foreach ($rel in $EXPECTED[$Model].Files.Keys) {
  $path = Join-Path $root $rel
  if (-not (Test-Path -LiteralPath $path)) { Write-Host "  MISSING  $rel" -ForegroundColor Red; $bad++; continue }
  $h = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
  if ($h -eq $EXPECTED[$Model].Files[$rel]) { Ok "$rel" }
  else { Write-Host "  BAD HASH $rel" -ForegroundColor Red; Write-Host "      got      $h"; Write-Host "      expected $($EXPECTED[$Model].Files[$rel])"; $bad++ }
}

Write-Host ""
if ($bad -gt 0) { Fail "$bad file(s) failed verification. Do NOT flash with this card." }

Write-Host "=== CARD READY for $Model ===" -ForegroundColor Green
Write-Host ""
if ($Model -eq 'MStar') {
  Write-Host "Next: power OFF the camera, insert card, power ON."
  Write-Host "  yellow LED flashes ~30s  -> writing, camera reboots"
  Write-Host "  yellow LED again <=2 min -> final stage"
  Write-Host "  blue LED                 -> wifi connected, done"
  Write-Host "  Total: about 3 minutes. Then browse to http://<camera-ip>"
} else {
  Write-Host "Next: power OFF the camera, insert card, power ON."
  Write-Host "  WAIT UP TO ONE HOUR. Several reboots are normal."
  Write-Host "  Done when the LED is solid blue for at least a full minute."
  Write-Host "  DO NOT power-cycle during this. Then browse to http://<camera-ip>"
}
Write-Host ""
