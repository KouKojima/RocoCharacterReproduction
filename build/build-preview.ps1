<#
.SYNOPSIS
    装配 → 构建 → 打包：三角色预览单文件。

.DESCRIPTION
    假设第 1 步（dotnet run 提取）和第 2 步（prepare_anim*）已经完成，
    产物放在 -Work 下：

        work/
          npc00401/  npc01101/  npc06201/     各角色提取结果
          materials/                          材质解析结果（MI_*.json）
          materials/shaders/                  BasePass 常量缓冲（*-evaluated.json）

.PARAMETER Work
    工作目录，默认仓库根下的 work/。

.PARAMETER Manifest
    角色清单，默认 manifest/characters.manifest.json。

.EXAMPLE
    pwsh build/build-preview.ps1
    pwsh build/build-preview.ps1 -Work D:\somewhere\work
#>
[CmdletBinding()]
param(
    [string]$Work = (Join-Path $PSScriptRoot '..' 'work'),
    [string]$Manifest = (Join-Path $PSScriptRoot '..' 'manifest' 'characters.manifest.json'),
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Work = [IO.Path]::GetFullPath($Work)
$out = Join-Path $Work 'preview'

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }

if (-not (Test-Path -LiteralPath $Work)) {
    throw "工作目录不存在：$Work（先跑完提取步骤，见 docs/04-复现步骤.md）"
}
$materials = Join-Path $Work 'materials'
$shaders = Join-Path $materials 'shaders'
foreach ($p in @($materials, $shaders)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "缺少 $p" }
}

Step '装配角色（prepare_multi.py）'
& $Python (Join-Path $repo 'tools/charextract/prepare_multi.py') `
    --data $Work --materials $materials --shaders $shaders --manifest $Manifest --out $out
if ($LASTEXITCODE -ne 0) { throw "prepare_multi 失败 ($LASTEXITCODE)" }

Step '构建前端（esbuild）'
Push-Location (Join-Path $repo 'preview')
try {
    if (-not (Test-Path -LiteralPath 'node_modules')) { npm.cmd install }
    node build.mjs
    if ($LASTEXITCODE -ne 0) { throw "build 失败 ($LASTEXITCODE)" }
} finally { Pop-Location }

Step '打包单文件（pack_multi.py）'
& $Python (Join-Path $repo 'tools/charextract/pack_multi.py') --data $out --code (Join-Path $repo 'preview')
if ($LASTEXITCODE -ne 0) { throw "pack_multi 失败 ($LASTEXITCODE)" }

$built = Join-Path $out '原版人物渲染预览.html'
if (-not (Test-Path -LiteralPath $built)) { throw "没有产出 $built" }
$hash = (Get-FileHash -LiteralPath $built -Algorithm SHA256).Hash.ToLower()
$mb = [math]::Round((Get-Item -LiteralPath $built).Length / 1MB, 1)
Write-Host "`n完成：$built`n  大小：$mb MB`n  sha256：$hash" -ForegroundColor Green
Write-Host '  双击即可离线打开；控制台应为 0 error。'
