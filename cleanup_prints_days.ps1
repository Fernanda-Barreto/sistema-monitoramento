$Path = Join-Path $PSScriptRoot "prints_eventos"
$Days = 14
if (Test-Path $Path) {
  Get-ChildItem $Path -File |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$Days) } |
    Remove-Item -Force -ErrorAction SilentlyContinue
}
