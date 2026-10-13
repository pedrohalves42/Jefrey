@echo off
REM Avaliacao noturna do Jefrey: roda a bateria de pedidos de pessoa comum contra o app em execucao
REM e grava o relatorio em evals\reports (acerto, tempo, cerebros e qual e o melhor para cada funcao).
REM Para agendar toda noite as 3h:  schtasks /create /tn "Jefrey avaliacao" /tr "%~f0" /sc daily /st 03:00
setlocal
cd /d "%~dp0\.."
set PY=C:\Users\Pedro\jv312\Scripts\python.exe
if not exist "%PY%" set PY=python
"%PY%" evals\run_evals.py --only leigos --base http://127.0.0.1:8000 --min-pass 0.0 >> evals\reports\noturna.log 2>&1
exit /b 0
