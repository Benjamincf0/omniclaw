; ============================================================================
; Omniclaw Installer — Inno Setup Script
;
; Produces: OmniclawSetup.exe
;
; Prerequisites: Build the PyInstaller bundle first so that
;   ..\mcp-server\dist\omniclaw\  exists.
;
; Compile with:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" omniclaw.iss
; ============================================================================

#define MyAppName      "Omniclaw"
#define MyAppVersion   "0.1.0"
#define MyAppPublisher "Omniclaw"
#define MyAppURL       "https://github.com/omniclaw"
#define MyAppExeName   "omniclaw.exe"

[Setup]
AppId={{B8A3F2D1-7C4E-4A9B-8D6F-1E2C3A4B5D6E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=OmniclawSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Bundle the entire PyInstaller output directory
Source: "..\mcp-server\dist\omniclaw\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Include the Ollama installer if it was pre-downloaded by the build script
Source: "OllamaSetup.exe"; DestDir: "{tmp}"; Flags: ignoreversion dontcopy; Check: ShouldInstallOllama

[Icons]
Name: "{group}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Launch the app after installation if the user checks the box
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
// ── Ollama detection and installation ──

function IsOllamaInstalled: Boolean;
var
  OllamaPath: String;
begin
  Result := False;

  // Check common install locations
  OllamaPath := ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe');
  if FileExists(OllamaPath) then
  begin
    Result := True;
    Exit;
  end;

  OllamaPath := ExpandConstant('{commonpf}\Ollama\ollama.exe');
  if FileExists(OllamaPath) then
  begin
    Result := True;
    Exit;
  end;

  // Check if ollama is on PATH by looking for it via registry or common env
  if RegQueryStringValue(HKCU, 'Environment', 'Path', OllamaPath) then
  begin
    if Pos('ollama', Lowercase(OllamaPath)) > 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function ShouldInstallOllama: Boolean;
begin
  Result := not IsOllamaInstalled;
end;

procedure DownloadAndInstallOllama;
var
  ResultCode: Integer;
  InstallerPath: String;
begin
  InstallerPath := ExpandConstant('{tmp}\OllamaSetup.exe');

  // If the build script pre-bundled the installer, extract it
  if not FileExists(InstallerPath) then
  begin
    ExtractTemporaryFile('OllamaSetup.exe');
  end;

  if FileExists(InstallerPath) then
  begin
    MsgBox('Omniclaw needs Ollama for local AI models.' + #13#10 +
           'The Ollama installer will now run. Please follow its instructions.',
           mbInformation, MB_OK);
    Exec(InstallerPath, '', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  end
  else
  begin
    // Fallback: direct the user to download manually
    MsgBox('Ollama was not found and the installer is not bundled.' + #13#10 +
           'Please download Ollama from https://ollama.com/download' + #13#10 +
           'and install it before using local AI models.',
           mbInformation, MB_OK);
  end;
end;

procedure InstallPlaywrightBrowsers;
var
  ResultCode: Integer;
  DriverPath: String;
  DriverCli: String;
begin
  DriverPath := ExpandConstant('{app}\_internal\playwright\driver\node.exe');
  DriverCli  := ExpandConstant('{app}\_internal\playwright\driver\package\cli.js');
  if FileExists(DriverPath) and FileExists(DriverCli) then
  begin
    Exec(DriverPath, '"' + DriverCli + '" install chromium',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if ResultCode = 0 then
      Log('Playwright Chromium installed successfully')
    else
      Log('Playwright Chromium install exited with code ' + IntToStr(ResultCode));
  end
  else
    Log('Playwright driver not found — browsers will be installed on first launch');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not IsOllamaInstalled then
    begin
      DownloadAndInstallOllama;
    end;
    InstallPlaywrightBrowsers;
  end;
end;
