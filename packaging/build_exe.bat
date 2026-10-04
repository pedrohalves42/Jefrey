@echo off
REM Gera dist\Jefrey\Jefrey.exe (programa sem console, com icone) e, se o Inno Setup estiver instalado, o instalador.
REM Uso:  packaging\build_exe.bat [caminho_do_python_3.12]
REM Requer Python 3.12 com:  pip install -r requirements.txt pyinstaller
setlocal EnableExtensions
cd /d "%~dp0\.."
set PY=%~1
if "%PY%"=="" set PY=python

"%PY%" -c "import sys; assert sys.version_info[:2]==(3,12), 'use Python 3.12'" || (echo Use o Python 3.12. & exit /b 1)

"%PY%" -m PyInstaller --noconfirm --clean --onedir --noconsole --name Jefrey ^
  --icon "%CD%\packaging\jefrey.ico" ^
  --distpath dist --workpath build --specpath build ^
  --paths . ^
  --collect-submodules src.jefrey ^
  --add-data "%CD%\src\jefrey\static;src/jefrey/static" ^
  --collect-all chromadb ^
  --collect-binaries ctranslate2 ^
  --collect-data faster_whisper ^
  --copy-metadata chromadb --copy-metadata langchain-core ^
  --hidden-import pystray._win32 ^
  packaging\jefrey_entry.py || exit /b 1

set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" (
  "%ISCC%" packaging\jefrey.iss || exit /b 1
  echo Instalador em packaging\Output\Jefrey-Setup.exe
) else (
  echo Inno Setup nao encontrado: so o programa foi gerado em dist\Jefrey
)
