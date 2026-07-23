; Inno Setup — versão lida de core/app_state.py via /DMyAppVersion=...
; Compile com: setup\orc_installer.bat  (ou apenas o .exe: setup\create_exe.bat)

#ifndef MyAppVersion
  #define MyAppVersion "Erro na versão, contatar suporte"
#endif

#define MyAppName "ORC"
#define MyAppPublisher "Léo Santos"
#define MyAppExeName "ORC.exe"
#define MyAppURL "https://github.com/leosans-eng/orcamento-reparos-construtivos"
#define MySourceDir "..\dist\ORC"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}

AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

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
SetupIconFile=..\icone.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin

; Se o ORC ainda estiver aberto, o instalador fecha o processo automaticamente
; (evita o usuário precisar trocar de janela e fechar manualmente).
CloseApplications=force
CloseApplicationsFilter=ORC.exe,ORC.exe*
RestartApplications=no

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; \
Description: "Criar atalho na área de trabalho"; \
GroupDescription: "Atalhos:"

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
Description: "Abrir ORC"; \
Flags: nowait postinstall skipifsilent
