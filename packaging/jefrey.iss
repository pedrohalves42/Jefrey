; Instalador do Jefrey (Inno Setup 6). Gerado por packaging\build_exe.bat a partir de dist\Jefrey.
; Instala por usuario (sem pedir administrador), cria atalhos e desinstala sem apagar os dados da pessoa.

#define AppName "Jefrey"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6F1B7E2A-3C44-4D5B-9A21-7E8C0D1F4B93}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Jefrey
DefaultDirName={localappdata}\Programs\Jefrey
DefaultGroupName=Jefrey
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Jefrey-Setup
SetupIconFile=jefrey.ico
UninstallDisplayIcon={app}\Jefrey.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; Flags: unchecked

[Files]
Source: "..\dist\Jefrey\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Jefrey"; Filename: "{app}\Jefrey.exe"
Name: "{autodesktop}\Jefrey"; Filename: "{app}\Jefrey.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Jefrey.exe"; Description: "Abrir o Jefrey agora"; Flags: nowait postinstall skipifsilent

; Os dados da pessoa (conversas, memorias, notas) ficam em %LOCALAPPDATA%\Jefrey e NAO sao apagados ao desinstalar.
