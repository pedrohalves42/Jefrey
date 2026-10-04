@echo off
REM Para o Jefrey sem apagar nada (dados e modelos continuam guardados).
setlocal EnableExtensions
cd /d "%~dp0"
echo Parando o Jefrey...
docker compose --profile full stop
echo Pronto. Para iniciar de novo: start_jefrey.bat
timeout /t 5 >nul
