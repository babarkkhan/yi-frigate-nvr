# Offline tests: Invoke-RestMethod is replaced; no camera receives audio.
$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot '../scripts/camera-speak.ps1'
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('speaker-test-' + [Guid]::NewGuid().ToString('N') + '.pcm')
$global:speakerTestRequest = $null
$global:speakerTestError = 'false'
function global:Invoke-RestMethod {
  param($Uri,$Method,[byte[]]$Body,$ContentType,$TimeoutSec)
  $global:speakerTestRequest = @{ Uri=$Uri; Body=$Body; ContentType=$ContentType }
  return @{error=$global:speakerTestError;description='test response'}
}
try {
  [byte[]]$pcm = 0..255
  [IO.File]::WriteAllBytes($fixture,$pcm)
  & $target -Camera cam1 -File $fixture -RawPcm
  $request = $global:speakerTestRequest
  if (-not $request -or $request.Uri -notmatch 'speaker\.sh\?vol=1$') { throw 'Wrong endpoint or default gain.' }
  $boundary = ($request.ContentType -split 'boundary=')[1]
  $prefix = [Text.Encoding]::ASCII.GetBytes("--$boundary`r`nContent-Disposition: form-data; name=`"file`"; filename=`"message.pcm`"`r`nContent-Type: application/octet-stream`r`n`r`n")
  $suffix = [Text.Encoding]::ASCII.GetBytes("`r`n--$boundary--`r`n")
  [byte[]]$expected = $prefix + $pcm + $suffix
  if ([Convert]::ToBase64String($expected) -ne [Convert]::ToBase64String($request.Body)) { throw 'Multipart framing changed the PCM bytes or header ordering.' }
  Write-Output 'PASS binary multipart format and default gain'
  $global:speakerTestRequest = $null
  & $target -Camera cam1 -File $fixture -RawPcm -PrepareOnly
  if ($global:speakerTestRequest) { throw 'PrepareOnly sent audio.' }
  Write-Output 'PASS prepare-only performs no HTTP request'
  foreach ($case in @(@{Name='empty';Bytes=[byte[]]@()},@{Name='odd size';Bytes=[byte[]]@(1,2,3)},@{Name='WAV header';Bytes=[Text.Encoding]::ASCII.GetBytes('RIFF0000')},@{Name='oversized';Bytes=(New-Object byte[] 320002)})) {
    [IO.File]::WriteAllBytes($fixture,$case.Bytes)
    $global:speakerTestRequest = $null
    $rejected = $false
    try { & $target -Camera cam1 -File $fixture -RawPcm } catch { $rejected=$true }
    if (-not $rejected -or $global:speakerTestRequest) { throw "Invalid PCM was not rejected: $($case.Name)" }
    Write-Output "PASS rejects $($case.Name) before sending"
  }
  [IO.File]::WriteAllBytes($fixture,$pcm)
  $global:speakerTestError = 'true'
  $rejected = $false
  try { & $target -Camera cam1 -File $fixture -RawPcm } catch { $rejected=$true }
  if (-not $rejected) { throw 'Camera error was reported as success.' }
  Write-Output 'PASS camera rejection becomes an error'
} finally {
  Remove-Item -LiteralPath $fixture -ErrorAction SilentlyContinue
  Remove-Item Function:\Invoke-RestMethod
  Remove-Variable speakerTestRequest,speakerTestError -Scope Global
}
