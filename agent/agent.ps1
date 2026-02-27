param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Args
)
$S = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$exe = Join-Path $S "aspectnova.exe"
if(!(Test-Path $exe)){
  throw "aspectnova.exe not found in: $S"
}
& $exe @Args
exit $LASTEXITCODE