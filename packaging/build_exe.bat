@echo off
REM Gera dist\Jefrey\Jefrey.exe (programa sem console, com icone) e, se o Inno Setup estiver instalado, o instalador.
REM Uso:  packaging\build_exe.bat [caminho_do_python_3.12]
REM Requer Python 3.12 com:  pip install -r requirements.txt pyinstaller
REM Assinatura de codigo (opcional): defina JEFREY_SIGN_PFX (caminho do certificado .pfx) e JEFREY_SIGN_PASS (senha) antes de rodar.
REM   Sem certificado o Windows mostra o aviso "editor desconhecido" (SmartScreen); ver docs\DISTRIBUICAO.md.
setlocal EnableExtensions
cd /d "%~dp0\.."
set PY=%~1
if "%PY%"=="" set PY=python

"%PY%" -c "import sys; assert sys.version_info[:2]==(3,12), 'use Python 3.12'" || (echo Use o Python 3.12. & exit /b 1)

for /f "tokens=2 delims==" %%v in ('findstr /b "__version__" "src\jefrey\__init__.py"') do set VERSION=%%v
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%
if "%VERSION%"=="" (echo [erro] nao consegui ler a versao em src\jefrey\__init__.py & exit /b 1)
echo Versao: %VERSION%

"%PY%" -m PyInstaller --noconfirm --clean --onedir --noconsole --name Jefrey ^
  --icon "%CD%\packaging\jefrey.ico" ^
  --distpath dist --workpath build --specpath build ^
  --paths . ^
  --collect-submodules src.jefrey ^
  --add-data "%CD%\src\jefrey\static;src/jefrey/static" ^
  --add-data "%CD%\src\jefrey\legal;src/jefrey/legal" ^
  --collect-all chromadb ^
  --collect-binaries ctranslate2 ^
  --collect-all faster_whisper ^
  --collect-all av ^
  --collect-all ddgs ^
  --copy-metadata chromadb --copy-metadata langchain-core ^
  --hidden-import pystray._win32 ^
  packaging\jefrey_entry.py || exit /b 1

REM A extensao do Chrome (WhatsApp) vai numa pasta visivel, para a pessoa "Carregar sem compactacao".
if exist "dist\Jefrey\extensao-chrome" rmdir /s /q "dist\Jefrey\extensao-chrome"
xcopy /e /i /y /q "extensions\whatsapp" "dist\Jefrey\extensao-chrome" >nul || exit /b 1

REM Padroes do instalador (credenciais do Google, endereco e chave das atualizacoes): so o que existir em packaging\defaults.
if exist "dist\Jefrey\defaults" rmdir /s /q "dist\Jefrey\defaults"
mkdir "dist\Jefrey\defaults"
for %%f in (google_oauth.json update_url.txt update_public_key.txt) do (
  if exist "packaging\defaults\%%f" copy /y "packaging\defaults\%%f" "dist\Jefrey\defaults\%%f" >nul
)

if defined JEFREY_SIGN_PFX (
  call :sign "dist\Jefrey\Jefrey.exe" || exit /b 1
)

set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" (
  "%ISCC%" /DAppVersion=%VERSION% packaging\jefrey.iss || exit /b 1
  if defined JEFREY_SIGN_PFX (
    call :sign "packaging\Output\Jefrey-Setup.exe" || exit /b 1
  )
  echo Instalador em packaging\Output\Jefrey-Setup.exe
) else (
  echo Inno Setup nao encontrado: so o programa foi gerado em dist\Jefrey
)
exit /b 0

:sign
set SIGNTOOL=signtool.exe
where signtool >nul 2>nul || (echo [erro] signtool nao encontrado: instale o Windows SDK. & exit /b 1)
%SIGNTOOL% sign /f "%JEFREY_SIGN_PFX%" /p "%JEFREY_SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /d "Jefrey" %1 || exit /b 1
echo Assinado: %~1
exit /b 0
