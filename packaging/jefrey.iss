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
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"

[Files]
; "extensao-chrome" ja vem dentro de dist\Jefrey (copiada pelo build_exe.bat): fica numa pasta visivel para a extensao do WhatsApp
Source: "..\dist\Jefrey\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Jefrey"; Filename: "{app}\Jefrey.exe"
Name: "{autoprograms}\Reiniciar o Jefrey"; Filename: "{app}\Jefrey.exe"; Parameters: "--restart"; Comment: "Fecha o Jefrey e abre de novo"
Name: "{autodesktop}\Jefrey"; Filename: "{app}\Jefrey.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Jefrey.exe"; Description: "Abrir o Jefrey agora"; Flags: nowait postinstall skipifsilent

; Os dados da pessoa (conversas, memorias, notas) ficam em %LOCALAPPDATA%\Jefrey e NAO sao apagados ao desinstalar.

[Code]
// Atualizar com o Jefrey aberto: pede para ele fechar (arquivo-sinal que o proprio programa observa) e espera ate 20 s.
// Sem isto o Inno nao consegue fechar a janela do app e a instalacao por cima falha.
function JefreyRodando(): Boolean;
var
  Code: Integer;
  Tmp: String;
  Txt: AnsiString;
begin
  Tmp := ExpandConstant('{tmp}\jf_run.txt');
  DeleteFile(Tmp);
  Exec(ExpandConstant('{cmd}'), '/C tasklist /FI "IMAGENAME eq Jefrey.exe" /NH > "' + Tmp + '"', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := LoadStringFromFile(Tmp, Txt) and (Pos('Jefrey.exe', String(Txt)) > 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  I: Integer;
  Sig: String;
begin
  Result := '';
  Sig := ExpandConstant('{localappdata}\Jefrey\config\quit.signal');
  ForceDirectories(ExtractFileDir(Sig));
  SaveStringToFile(Sig, '1', False);
  for I := 1 to 40 do
  begin
    if not JefreyRodando() then Break;
    Sleep(500);
  end;
end;

// Ao desinstalar, pergunta se a pessoa quer MANTER o que o Jefrey aprendeu. O padrao e manter (e no modo silencioso tambem).
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Quer manter suas conversas, memórias e notas do Jefrey neste computador?' + #13#10 + #13#10 +
              'Escolha Sim para guardar (recomendado: se instalar de novo, tudo volta). Escolha Não para apagar tudo.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON1) = IDNO then
      DelTree(ExpandConstant('{localappdata}\Jefrey'), True, True, True);
  end;
end;
