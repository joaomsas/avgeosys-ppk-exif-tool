; AVGeoSys Inno Setup Script — versão 1.0.0
; Gera: dist\installer\AVGeoSys_Setup_1.0.0.exe

#define AppName      "AVGeoSys"
#define AppVersion   "1.0.5"
#define AppPublisher "João Marcos Rezende Sasdelli Gonçalves"
#define AppExeName   "AVGeoSys.exe"
#define SourceDir    "dist\AVGeoSys"

[Setup]
AppId={{B3F2A1D4-7C8E-4F5A-9B2D-1E6C3A7F0D82}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=dist\installer
OutputBaseFilename=AVGeoSys_Setup_1.0.4
SetupIconFile=AVGeoSysIcon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Instalação por usuário (não exige admin); dialog permite escolher modo
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=6.1

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Executável principal
Source: "{#SourceDir}\{#AppExeName}";    DestDir: "{app}";            Flags: ignoreversion
; Pasta _internal com todas as dependências Python
Source: "{#SourceDir}\_internal\*";      DestDir: "{app}\_internal";  Flags: ignoreversion recursesubdirs createallsubdirs
; Ícone (para atalho)
Source: "AVGeoSysIcon.ico";              DestDir: "{app}";            Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";                    Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\AVGeoSysIcon.ico"
Name: "{group}\Desinstalar {#AppName}";        Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";              Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\AVGeoSysIcon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
