#define MyAppName "ORC"
#define MyAppVersion "0.9.8.6"
#define MyAppPublisher "Léo Santos"
#define MyAppExeName "ORC.exe"
#define MySourceDir "..\dist\ORC"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}

AppPublisher={#MyAppPublisher}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Instalador do ORC
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=© 2026 {#MyAppPublisher}

DefaultDirName=C:\ORC
DefaultGroupName=ORC
OutputDir=output
OutputBaseFilename=ORC_Instalador_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; \
Description: "Criar atalho na área de trabalho"; \
GroupDescription: "Atalhos:"

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; \
Description: "Abrir ORC"; \
Flags: nowait postinstall skipifsilent