# Grava src\jefrey\build_info.py com a data/hora e o commit desta compilacao (aparece na tela do Jefrey).
$root = Split-Path -Parent $PSScriptRoot
$rev = (git -C $root rev-parse --short HEAD)
$stamp = (Get-Date -Format 'yyyy-MM-dd HH:mm')
$line = 'BUILD = "' + $stamp + ' ' + $rev + '"'
Set-Content -Encoding ascii -Path (Join-Path $root 'src\jefrey\build_info.py') -Value $line
