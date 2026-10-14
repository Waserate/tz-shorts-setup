<#
  TZ Shorts setup - installs everything the Shorts workflow needs, in one run.

  Run from the repo folder:
      powershell -ExecutionPolicy Bypass -File .\setup.ps1

  Safe to run again: anything already installed is skipped.
  Options:
      -SkipModel   do not download the 2.9 GB Thai Whisper model
#>
param([switch]$SkipModel)

$ErrorActionPreference = 'Stop'
$Repo     = $PSScriptRoot
$Pipeline = Join-Path $Repo 'shorts-pipeline'
$Tools    = Join-Path $env:USERPROFILE '.tz-tools'          # venv for yt-dlp / agent-reach / notebooklm
$XToolkit = Join-Path $env:USERPROFILE 'tools\x-scraper-toolkit'
$Skills   = Join-Path $env:USERPROFILE '.claude\skills'
$CapCut   = Join-Path $env:LOCALAPPDATA 'CapCut'
$Log      = Join-Path $Repo 'setup.log'
$Results  = [System.Collections.Generic.List[object]]::new()

Start-Transcript -Path $Log -Append | Out-Null

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Exec([string]$what, [scriptblock]$cmd) {
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" }
}

function Step([string]$name, [scriptblock]$body) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    try {
        & $body
        $Results.Add([pscustomobject]@{ Step = $name; Result = 'OK'; Detail = '' })
    } catch {
        Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
        $Results.Add([pscustomobject]@{ Step = $name; Result = 'FAIL'; Detail = $_.Exception.Message })
    }
}

function Quiet([scriptblock]$cmd) {
    # run a native command for its output/exit code only; in PS 5.1 stderr + 'Stop' would throw
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & $cmd 2>&1 | Out-String } finally { $ErrorActionPreference = $prev }
}

function Winget([string]$id) {
    Quiet { winget list --id $id -e --accept-source-agreements } | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "$id already installed"; return }
    Exec "winget $id" { winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements }
}

function Write-Utf8NoBom([string]$path, [string]$text) {
    # Windows PowerShell 5.1 writes a BOM by default; Claude Code and CapCut both choke on it.
    [IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
}

# ---------------------------------------------------------------- 1. programs
Step 'Programs (winget)' {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'winget not found - install "App Installer" from Microsoft Store, then run again'
    }
    foreach ($id in 'Git.Git', 'Microsoft.VisualStudioCode', 'OpenJS.NodeJS.LTS', 'Python.Python.3.11',
                    'Gyan.FFmpeg', 'ByteDance.CapCut', 'Oven-sh.Bun', 'GitHub.cli') {
        Winget $id
    }
    Refresh-Path
}

# ---------------------------------------------------------------- 2. Claude Code
Step 'Claude Code (CLI + VS Code extension)' {
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
        $env:Path += ";$env:USERPROFILE\.local\bin"
    }
    Exec 'claude --version' { claude --version }
    Exec 'VS Code extension' { code --install-extension anthropic.claude-code --force }
}

# ---------------------------------------------------------------- 3. web tools
Step 'yt-dlp + agent-reach + notebooklm-py' {
    if (-not (Test-Path "$Tools\Scripts\python.exe")) { Exec 'tools venv' { py -3.11 -m venv $Tools } }
    $py = "$Tools\Scripts\python.exe"
    Exec 'pip upgrade' { & $py -m pip install --upgrade pip -q }
    Exec 'pip tools'   { & $py -m pip install -U yt-dlp agent-reach notebooklm-py playwright rookiepy -q }
    Exec 'playwright chromium (for notebooklm login)' { & $py -m playwright install chromium }
    # put the tools on the user PATH so Claude can call them by name
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath -notlike "*$Tools\Scripts*") {
        [Environment]::SetEnvironmentVariable('Path', "$userPath;$Tools\Scripts", 'User')
    }
    Refresh-Path
    Exec 'agent-reach install' { agent-reach install --env local }
}

Step 'x-scraper-toolkit (fxtweet.py)' {
    if (Test-Path "$XToolkit\.git") { Exec 'git pull' { git -C $XToolkit pull --ff-only } }
    else { Exec 'git clone' { git clone https://github.com/alienrelics/x-scraper-toolkit $XToolkit } }
}

# ---------------------------------------------------------------- 4. Shorts pipeline
Step 'Shorts pipeline venv' {
    # scripts print Thai + emoji; without this a non-UTF-8 console crashes with UnicodeEncodeError
    [Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User'); $env:PYTHONUTF8 = '1'
    # the shorts-edit skill finds the pipeline through this
    [Environment]::SetEnvironmentVariable('TZ_SHORTS_HOME', $Repo, 'User'); $env:TZ_SHORTS_HOME = $Repo
    if (-not (Test-Path "$Pipeline\venv\Scripts\python.exe")) { Exec 'venv' { py -3.11 -m venv "$Pipeline\venv" } }
    $py = "$Pipeline\venv\Scripts\python.exe"
    Exec 'pip upgrade' { & $py -m pip install --upgrade pip -q }
    Exec 'requirements' { & $py -m pip install -r "$Pipeline\requirements.txt" -q }
    $gpu = (Get-CimInstance Win32_VideoController).Name -match 'NVIDIA'
    if ($gpu) { Exec 'nvidia wheels' { & $py -m pip install -r "$Pipeline\requirements-nvidia.txt" -q } }
    else { Write-Host 'No NVIDIA card - Whisper will run on CPU (slow). CapCut Auto Caption is unaffected.' }
    Exec 'test_chunker' { & $py "$Pipeline\test_chunker.py" }
}

Step 'Thai Whisper model (2.9 GB)' {
    if ($SkipModel) { Write-Host 'skipped (-SkipModel)'; return }
    $py = "$Pipeline\venv\Scripts\python.exe"
    $dest = Join-Path $Pipeline 'models\ct2'
    Exec 'download' { & $py -c "from huggingface_hub import snapshot_download as d; print(d('Vinxscribe/biodatlab-whisper-th-large-v3-faster', cache_dir=r'$dest'))" }
}

# ---------------------------------------------------------------- 5. CapCut donors
Step 'CapCut donor drafts + effects' {
    if (-not (Test-Path "$CapCut\Apps")) { throw 'CapCut not installed yet - install it, open it once, run setup again' }
    $drafts  = Join-Path $CapCut 'User Data\Projects\com.lveditor.draft'
    $effects = Join-Path $CapCut 'User Data\Cache\effect'
    New-Item -ItemType Directory -Force $drafts, $effects | Out-Null
    $me = $env:USERPROFILE
    foreach ($d in Get-ChildItem "$Repo\capcut-donor\drafts" -Directory) {
        $target = Join-Path $drafts $d.Name
        if (Test-Path $target) { Write-Host "draft $($d.Name) exists - left alone"; continue }
        New-Item -ItemType Directory -Force $target | Out-Null
        foreach ($f in Get-ChildItem $d.FullName -File) {
            # the donors were saved on another account; point their cache paths at this one
            $text = [IO.File]::ReadAllText($f.FullName)
            $text = $text.Replace('C:/Users/Admin/', ($me -replace '\\', '/') + '/')
            $text = $text.Replace('C:\\Users\\Admin\\', ($me -replace '\\', '\\') + '\\')
            Write-Utf8NoBom (Join-Path $target $f.Name) $text
        }
    }
    foreach ($e in Get-ChildItem "$Repo\capcut-donor\effects" -Directory) {
        $target = Join-Path $effects $e.Name
        if (-not (Test-Path $target)) { Copy-Item $e.FullName $target -Recurse }
    }
    Exec 'config check' { & "$Pipeline\venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, r'$Pipeline'); import config; print('CapCut', config.APP_VER, config.FONT_DIR)" }
}

# ---------------------------------------------------------------- 6. Claude skills + plugins
Step 'Claude skills (shorts-edit, notebooklm, diagnosing-bugs)' {
    New-Item -ItemType Directory -Force $Skills | Out-Null
    foreach ($s in Get-ChildItem "$Repo\skills" -Directory) {
        Copy-Item $s.FullName (Join-Path $Skills $s.Name) -Recurse -Force
    }
}

Step 'Remotion Agent Skill' {
    Exec 'skills add' { npx -y skills add remotion-dev/skills -g -a claude-code -s '*' -y --copy }
}

Step 'Claude plugins (superpowers, caveman, claude-mem)' {
    $known = Quiet { claude plugin marketplace list }
    foreach ($m in 'anthropics/claude-plugins-official', 'JuliusBrussee/caveman', 'thedotmack/claude-mem') {
        if ($known -notmatch [regex]::Escape($m.Split('/')[1])) { Exec "marketplace $m" { claude plugin marketplace add $m } }
    }
    foreach ($p in 'superpowers@claude-plugins-official', 'caveman@caveman', 'claude-mem@thedotmack') {
        Exec "plugin $p" { claude plugin install $p }
    }
}

# ---------------------------------------------------------------- 7. Remotion
Step 'Remotion + Chrome Headless Shell' {
    Push-Location "$Repo\remotion"
    try {
        Exec 'npm install' { npm install --no-fund --no-audit }
        Exec 'browser ensure' { npx remotion browser ensure }
    } finally { Pop-Location }
}

# ---------------------------------------------------------------- summary
Write-Host "`n================ SUMMARY ================" -ForegroundColor Cyan
$Results | Format-Table -AutoSize -Wrap
$failed = @($Results | Where-Object Result -eq 'FAIL')
Stop-Transcript | Out-Null
if ($failed.Count) {
    Write-Host "$($failed.Count) step(s) FAILED - send setup.log to your brother / paste it to Claude." -ForegroundColor Red
    exit 1
}
Write-Host @"
All steps OK. Still to do by hand (needs your own logins):
  1. Open VS Code > Claude panel > sign in with your Claude account
  2. Open CapCut once and sign in
  3. notebooklm login            (Google account, for YouTube transcripts)
  4. gh auth login               (only if you need to pull updates of this repo)
Then: VS Code > File > Open Folder > this repo folder, and type /shorts-edit in Claude.
"@ -ForegroundColor Green
