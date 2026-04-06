param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$OrtLibDir = "",
    [switch]$NoBackup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PackagePaths {
    param(
        [string]$PythonPath
    )

    if (-not (Test-Path $PythonPath)) {
        throw "未找到 Python 可执行文件: $PythonPath"
    }

    $pyOut = & $PythonPath -c @"
import json
from pathlib import Path
import sherpa_onnx

try:
    import onnxruntime
    ort_dir = str(Path(onnxruntime.__file__).resolve().parent / "capi")
except Exception:
    ort_dir = ""

sherpa_dir = Path(sherpa_onnx.__file__).resolve().parent / "lib"
if not sherpa_dir.is_dir():
    sherpa_dir = Path(sherpa_onnx.__file__).resolve().parent

print(json.dumps({"sherpa_lib": str(sherpa_dir), "onnxruntime_capi": ort_dir}))
"@

    return $pyOut | ConvertFrom-Json
}

function Test-SM61Tag {
    param(
        [string]$DllPath
    )

    if (-not (Test-Path $DllPath)) {
        return $false
    }

    $bytes = [System.IO.File]::ReadAllBytes($DllPath)
    $tag = [System.Text.Encoding]::ASCII.GetBytes("sm_61")

    for ($i = 0; $i -le $bytes.Length - $tag.Length; $i++) {
        $matched = $true
        for ($j = 0; $j -lt $tag.Length; $j++) {
            if ($bytes[$i + $j] -ne $tag[$j]) {
                $matched = $false
                break
            }
        }
        if ($matched) {
            return $true
        }
    }
    return $false
}

Write-Host "正在解析 sherpa-onnx/onnxruntime 路径..."
$paths = Get-PackagePaths -PythonPath $PythonExe
$sherpaLibDir = [string]$paths.sherpa_lib

if (-not (Test-Path $sherpaLibDir)) {
    throw "未找到 sherpa_onnx lib 目录: $sherpaLibDir"
}

if ([string]::IsNullOrWhiteSpace($OrtLibDir)) {
    $OrtLibDir = [string]$paths.onnxruntime_capi
}

if ([string]::IsNullOrWhiteSpace($OrtLibDir)) {
    throw "未提供 --OrtLibDir，且未检测到 onnxruntime/capi 目录。"
}

if (-not (Test-Path $OrtLibDir)) {
    throw "未找到 ORT 库目录: $OrtLibDir"
}

Write-Host "sherpa_onnx 目标目录: $sherpaLibDir"
Write-Host "ORT 源目录: $OrtLibDir"

$dllNames = @(
    "onnxruntime.dll",
    "onnxruntime_providers_shared.dll",
    "onnxruntime_providers_cuda.dll"
)

$optionalDllNames = @(
    "onnxruntime_providers_tensorrt.dll"
)

foreach ($dll in $dllNames) {
    $src = Join-Path $OrtLibDir $dll
    if (-not (Test-Path $src)) {
        throw "源目录缺少必要 DLL: $src"
    }
}

$cudaDllPath = Join-Path $OrtLibDir "onnxruntime_providers_cuda.dll"
if (-not (Test-SM61Tag -DllPath $cudaDllPath)) {
    Write-Warning "当前 CUDA DLL 未检测到 sm_61 标记。对 GTX 1050 Ti 仍可能报 no kernel image。"
}

if (-not $NoBackup) {
    $backupDir = Join-Path $sherpaLibDir ("backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    foreach ($dll in ($dllNames + $optionalDllNames)) {
        $targetPath = Join-Path $sherpaLibDir $dll
        if (Test-Path $targetPath) {
            Copy-Item -Path $targetPath -Destination (Join-Path $backupDir $dll) -Force
        }
    }
    Write-Host "已备份原始 DLL 到: $backupDir"
}

foreach ($dll in $dllNames) {
    $src = Join-Path $OrtLibDir $dll
    $dst = Join-Path $sherpaLibDir $dll
    Copy-Item -Path $src -Destination $dst -Force
    Write-Host "已替换: $dll"
}

foreach ($dll in $optionalDllNames) {
    $src = Join-Path $OrtLibDir $dll
    if (Test-Path $src) {
        $dst = Join-Path $sherpaLibDir $dll
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "已替换(可选): $dll"
    }
}

Write-Host "完成。建议立即执行一次 GPU 冒烟测试。"
