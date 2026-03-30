#define MyAppName "ORC"
#define MyAppVersion "0.9.8.1"
#define MyAppExeName "ORC.exe"
#define MySourceDir "..\dist\ORC"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName=C:\ORC
DefaultGroupName=ORC
OutputDir=output
OutputBaseFilename=ORC_Instalador_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
SetupIconFile=icone.ico
PrivilegesRequired=admin

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir ORC"; Flags: nowait postinstall skipifsilent