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

#ifndef MyAppName
  #define MyAppName "BarByBar"
#endif
#define MyAppPublisher "BarByBar"
#define MyAppExeName "BarByBar.exe"
#ifndef MyAppId
  #define MyAppId "{{A516BBBA-3B66-4A27-9F44-03D52CB9D89D}"
#endif
#ifndef MyProgramGroupName
  #define MyProgramGroupName "BarByBar"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\BarByBar
DefaultGroupName={#MyProgramGroupName}
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
Name: "chinesesimplified"; MessagesFile: ".\ChineseSimplified.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BarByBar"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "打开 {#MyAppName}"; Flags: nowait postinstall skipifsilent
