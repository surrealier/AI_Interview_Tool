; AI Interviewer per-user installer.
; Build (from the project root, after build_release.ps1 stages dist\AIInterview):
;   ISCC.exe scripts\setup.iss /DAppVersion=v1.0.0
; AppVersion defaults to dev when not passed.

#ifndef AppVersion
  #define AppVersion "dev"
#endif

#define AppName "AI Interviewer"
#define AppPublisher "Surrealier"
#define AppExeName "AIInterview.exe"
#define DistDir "..\\dist\\AIInterview"

[Setup]
; Never change AppId after the first public release; upgrades depend on it.
AppId={{8E4C2F41-9B7D-4A53-BD10-4B4A15B2E7C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\AIInterview
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\releases
OutputBaseFilename=AIInterview-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\TERMS.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Korean.isl ships with Inno Setup's language pack; fall back to English-only
; builds by commenting this line out if the file is missing.
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]

[Code]
// Downloaded model weights live under {app}\models and can be multiple GB.
// Ask before leaving them behind; user documents/settings are never touched.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ModelsDir: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ModelsDir := ExpandConstant('{app}\models');
    if DirExists(ModelsDir) then
    begin
      if MsgBox('Downloaded TTS models remain in:' + #13#10 + ModelsDir + #13#10#13#10 +
                'Delete them as well? (They are several GB; keep them if you plan to reinstall.)',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(ModelsDir, True, True, True);
    end;
  end;
end;
