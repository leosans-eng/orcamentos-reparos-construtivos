#define MyAppName "ORC"
#define MyAppVersion "0.9.8.5"
#define MyAppExeName "ORC.exe"
#define MySourceDir "..\dist\ORC"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}

AppPublisher=Léo Santos
VersionInfoCompany=Léo Santos
VersionInfoDescription=Instalador do ORC
VersionInfoProductName=ORC
VersionInfoProductVersion={#MyAppVersion}

DefaultDirName=C:\ORC
DefaultGroupName=ORC
OutputDir=output
OutputBaseFilename=ORC_Instalador_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
SetupIconFile=icone.ico
PrivilegesRequired=admin

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir ORC"; Flags: nowait postinstall skipifsilent