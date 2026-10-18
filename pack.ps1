# cc-env one-click packer: experiences (.claude core + 1aimemory) + workspace projects.
# Big projects (models, datasets, media) are auto-skipped by lean-size threshold.
# Usage: pack.bat  [-OutDir ...] [-Workspace ...] [-Memory ...] [-MaxProjectMB 200]
# Local overrides (gitignored ccs.local.json keys: workspace / memory / out_dir)
# let each machine keep its own real paths out of source control.
param(
  [string]$OutDir = "",
  [int]$MaxProjectMB = 200,
  [string]$Workspace = "",
  [string]$Memory = ""
)
$ErrorActionPreference = 'Stop'
$HOME_DIR = $env:USERPROFILE

$localCfg = Join-Path $PSScriptRoot 'ccs.local.json'
if (Test-Path $localCfg) {
  try {
    $cfg = Get-Content $localCfg -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $Workspace -and $cfg.workspace) { $Workspace = $cfg.workspace }
    if (-not $Memory    -and $cfg.memory)    { $Memory    = $cfg.memory }
    if (-not $OutDir    -and $cfg.out_dir)   { $OutDir    = $cfg.out_dir }
  } catch { Write-Host "  ! ccs.local.json unreadable, using defaults" }
}
if (-not $Workspace) { $Workspace = Join-Path $HOME_DIR 'workspace' }
if (-not $Memory)    { $Memory    = Join-Path $HOME_DIR 'aimemory' }
if (-not $OutDir)    { $OutDir    = Join-Path $HOME_DIR 'cc-sync-out' }
$WORKSPACE = $Workspace
$MEMORY = $Memory

$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$stage = Join-Path $OutDir "stage-$stamp"
$zip   = Join-Path $OutDir "cc-env-$stamp.zip"
New-Item -ItemType Directory -Force $stage | Out-Null

# heavy dirs/files excluded everywhere (keeps code, drops artifacts)
$XD = @('node_modules','.venv','venv','__pycache__','dist','build','.git',
        '.mypy_cache','.pytest_cache','.next','target','.idea','downloads',
        'output','outputs','checkpoints')
$XF = @('*.pyc','*.log','*.mp4','*.mkv','*.avi','*.wav','*.gguf','*.safetensors',
        '*.ckpt','*.onnx','*.pt','*.pth','*.bin','*.iso','*.zip','*.7z','*.rar')

function Get-LeanSizeBytes([string]$src) {
  $out = & robocopy $src "$env:TEMP\robo-null" /L /E /BYTES /NFL /NDL /NP /NJH /XD $script:XD /XF $script:XF 2>$null
  # localized robocopy prints "Bytes :" (en) or "字节 :" (zh) — match either
  foreach ($l in $out) {
    if ($l -match '(Bytes|字节)\s*:\s*([\d,]+)') {
      return [int64]($Matches[2] -replace ',', '')
    }
  }
  throw "cannot parse lean size for $src (refusing to pack unmeasured dir)"
}

function Robo-Copy([string]$src, [string]$dst, [string[]]$extraXd = @()) {
  $xdAll = $script:XD + $extraXd
  & robocopy $src $dst /E /NFL /NDL /NP /R:1 /W:1 /XD $xdAll /XF $script:XF | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $src" }
  $global:LASTEXITCODE = 0
}

function Copy-OneFile([string]$src, [string]$dstDir) {
  if (Test-Path $src) {
    New-Item -ItemType Directory -Force $dstDir | Out-Null
    Copy-Item $src $dstDir -Force
    Write-Host "  + file  $(Split-Path $src -Leaf)"
  }
}

Write-Host "=== [1/4] .claude core ==="
$claudeSrc = Join-Path $HOME_DIR '.claude'
$claudeDst = Join-Path $stage 'claude'
foreach ($d in 'rules','agents','commands','hooks','plugins','scripts') {
  $s = Join-Path $claudeSrc $d
  if (Test-Path $s) { Write-Host "  + dir   .claude\$d"; Robo-Copy $s (Join-Path $claudeDst $d) }
}
# skills minus the 553MB youtube-clipper
$skillsSrc = Join-Path $claudeSrc 'skills'
if (Test-Path $skillsSrc) {
  Write-Host "  + dir   .claude\skills (skip youtube-clipper)"
  Robo-Copy $skillsSrc (Join-Path $claudeDst 'skills') @((Join-Path $skillsSrc 'youtube-clipper'))
}
Copy-OneFile (Join-Path $claudeSrc 'settings.json') $claudeDst
Copy-OneFile (Join-Path $claudeSrc 'settings.local.json') $claudeDst
# home-level files
$homeDst = Join-Path $stage 'home'
Copy-OneFile (Join-Path $HOME_DIR '.claude.json') $homeDst
Copy-OneFile (Join-Path $HOME_DIR 'CLAUDE.md') $homeDst

Write-Host "=== [2/4] 1aimemory ==="
if (Test-Path $MEMORY) { Robo-Copy $MEMORY (Join-Path $stage '1aimemory'); Write-Host "  + dir   1aimemory" }

Write-Host "=== [3/4] workspace projects (threshold $MaxProjectMB MB) ==="
$wsDst = Join-Path $stage 'workspace'
New-Item -ItemType Directory -Force $wsDst | Out-Null
$skipped = @()
Get-ChildItem $WORKSPACE -Directory | ForEach-Object {
  $name = $_.Name
  if ($name -in @('cc-sync')) { return }
  $mb = [math]::Round((Get-LeanSizeBytes $_.FullName) / 1MB, 1)
  if ($mb -gt $MaxProjectMB) {
    $script:skipped += "$name ($mb MB)"
    Write-Host ("  - skip  {0,-28} {1,8} MB  (too big)" -f $name, $mb)
  } else {
    Write-Host ("  + pack  {0,-28} {1,8} MB" -f $name, $mb)
    Robo-Copy $_.FullName (Join-Path $wsDst $name)
  }
}

Write-Host "=== [4/4] installer + zip ==="
$install = @'
param([string]$WorkspaceRoot = "", [string]$MemoryRoot = "")
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $WorkspaceRoot) { $WorkspaceRoot = Join-Path $env:USERPROFILE 'workspace' }
if (-not $MemoryRoot)   { $MemoryRoot   = Join-Path $env:USERPROFILE 'aimemory' }

function Robo-Merge($src, $dst) {
  if (-not (Test-Path $src)) { return }
  & robocopy $src $dst /E /NFL /NDL /NP /R:1 /W:1 | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $src" }
  $global:LASTEXITCODE = 0
}

$claudeDst = Join-Path $env:USERPROFILE '.claude'
foreach ($f in 'settings.json','settings.local.json') {
  $old = Join-Path $claudeDst $f
  if (Test-Path $old) { Copy-Item $old "$old.bak-$(Get-Date -Format yyyyMMddHHmm)" -Force }
}
Robo-Merge (Join-Path $here 'claude') $claudeDst
Robo-Merge (Join-Path $here 'home') $env:USERPROFILE
Robo-Merge (Join-Path $here '1aimemory') $MemoryRoot
Robo-Merge (Join-Path $here 'workspace') $WorkspaceRoot

Write-Host ""
Write-Host "Done. Next steps on this laptop:"
Write-Host "  1. Install Node.js LTS  -> https://nodejs.org"
Write-Host "  2. npm i -g @anthropic-ai/claude-code"
Write-Host "  3. Check path references inside settings.json / CLAUDE.md / hooks"
Write-Host "     (they may point at the old PC user profile or data drive)"
Write-Host "  4. Run: claude   (first run will ask to trust/login)"
'@
Set-Content (Join-Path $stage 'install.ps1') $install -Encoding UTF8

$readme = @"
CC 环境同步包 ($stamp)
========================

内容：
  claude\     -> %USERPROFILE%\.claude 核心配置（settings/rules/agents/commands/hooks/plugins/scripts/skills）
  home\       -> .claude.json / CLAUDE.md
  1aimemory\  -> 经验记忆库
  workspace  -> 工作区工具项目（已排除 node_modules/.venv/.git/模型与媒体大文件）

笔记本上使用：
  1. 解压本 zip 到任意目录
  2. 右键 install.ps1 -> 使用 PowerShell 运行
     （或 powershell -ExecutionPolicy Bypass -File install.ps1）
  3. 装 Node.js LTS，再 npm i -g @anthropic-ai/claude-code

因体积过大被跳过的项目（需要时手动同步）：
$(if ($skipped) { ($skipped | ForEach-Object { "  - $_" }) -join "`n" } else { "  （无）" })

注意：
  - settings.json 内含 ark key 明文，压缩包不要外传
  - 配置里的路径（旧机用户目录、数据盘）在新机器上需按实际调整
  - 各项目依赖需在笔记本上自行重建（pip/npm 安装）
"@
Set-Content (Join-Path $stage 'README.txt') $readme -Encoding UTF8

Write-Host "compressing -> $zip"
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal -Force
Remove-Item $stage -Recurse -Force

$zipMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host ""
Write-Host "OK: $zip  ($zipMB MB)"
if ($skipped) { Write-Host "skipped (too big): $($skipped -join ', ')" }
