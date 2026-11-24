; Instalador do Monitor de Bateria (Inno Setup 6).
; Gerado por packaging\build.ps1, que passa /DAppVersion=x.y.z

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Monitor de Bateria"
#define AppExe "MonitorBateria.exe"

[Setup]
AppId={{6B3E2F4A-9C1D-4E7B-8A52-7C1F0D3B9E41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=renatopss
AppPublisherURL=https://github.com/renatopss/monitor-bateria
DefaultDirName={localappdata}\Programs\MonitorBateria
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Instala só para o usuário atual: não pede administrador.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Fecha o app (mutex da instância única) antes de atualizar/desinstalar.
AppMutex=Local\monitor-bateria-7c1f
CloseApplications=yes
OutputDir=..\dist
OutputBaseFilename=MonitorBateria-{#AppVersion}-setup
SetupIconFile=build\app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "autostart"; Description: "Abrir junto com o Windows"; GroupDescription: "Opções:"
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Opções:"; Flags: unchecked

[Files]
Source: "build\dist\MonitorBateria\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Editar cores"; Filename: "{app}\{#AppExe}"; Parameters: "--cores"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName} agora"; Flags: nowait postinstall skipifsilent

; A configuração e o log em %LOCALAPPDATA%\monitor-bateria são mantidos ao desinstalar.
