#ifndef MyAppVersion
  #error "MyAppVersion must be defined."
#endif

#ifndef SourceDir
  #error "SourceDir must be defined."
#endif

#ifndef OutputDir
  #error "OutputDir must be defined."
#endif

#ifndef OutputBaseFilename
  #error "OutputBaseFilename must be defined."
#endif

#ifndef AssetsDir
  #error "AssetsDir must be defined."
#endif

#define MyAppName "BarByBar"
#define MyAppPublisher "BarByBar"
#define MyAppExeName "BarByBar.exe"
#define MyAppId "{{A516BBBA-3B66-4A27-9F44-03D52CB9D89D}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\BarByBar
DefaultGroupName=BarByBar
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile={#AssetsDir}\barbybar-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=no
UsedUserAreasWarning=no
DirExistsWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BarByBar"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "打开 {#MyAppName}"; Flags: nowait postinstall skipifsilent
