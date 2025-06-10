[Setup]
AppName=AVGeoSys – PPK & EXIF Tool V0.3.02
AppVersion=0.3.02
DefaultDirName={pf}\AVGeoSys
DefaultGroupName=AVGeoSys
OutputBaseFilename=AVGeoSys_Installer
Compression=lzma
SolidCompression=yes

[Files]
; Copia o executável para a pasta de instalação
Source: "dist\AVGeoSys.exe"; DestDir: "{app}"; Flags: ignoreversion
; Copia o icon para criar o atalho
Source: "AVGeoSysIcon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Atalho no menu Iniciar
Name: "{group}\AVGeoSys"; Filename: "{app}\AVGeoSys.exe"; WorkingDir: "{app}"
; Ícone na área de trabalho
Name: "{commondesktop}\AVGeoSys"; Filename: "{app}\AVGeoSys.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar ícone na área de trabalho"; GroupDescription: "Tarefas adicionais:"