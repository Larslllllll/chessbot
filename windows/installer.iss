[Setup]
AppName=Chessbot
AppVersion=1.0.0
AppPublisher=larslllllll
DefaultDirName={autopf}\Chessbot
DefaultGroupName=Chessbot
OutputBaseFilename=chessbot-setup
OutputDir={#SourcePath}\..\dist\installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; Main application bundle (PyInstaller onedir output)
Source: "{#SourcePath}\..\dist\chessbot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Stockfish engine
Source: "{#SourcePath}\..\StockFish\stockfish\stockfish-windows-x86-64-avx2.exe"; DestDir: "{app}\engine"; DestName: "stockfish.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\Chessbot"; Filename: "{app}\chessbot.exe"
Name: "{commondesktop}\Chessbot"; Filename: "{app}\chessbot.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Symbole:"

[Run]
; Install Playwright Chromium browser on first install
Filename: "{app}\install_browser.exe"; Flags: runhidden waituntilterminated; StatusMsg: "Installiere Browser (kann eine Minute dauern)..."
; Offer to launch after install
Filename: "{app}\chessbot.exe"; Description: "Chessbot jetzt starten"; Flags: nowait postinstall skipifsilent
