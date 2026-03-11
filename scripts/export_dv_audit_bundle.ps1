param(
    [string]$RepoRoot = "C:\dev\AspectNova",
    [string]$OutDir = "C:\dev\AspectNova\_audit_bundle"
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Content
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Append-Utf8NoBom {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Content
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    if (-not (Test-Path $Path)) {
        [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
    } else {
        [System.IO.File]::AppendAllText($Path, $Content, $utf8NoBom)
    }
}

if (-not (Test-Path $RepoRoot)) {
    throw "Repo root not found: $RepoRoot"
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$manifestPath = Join-Path $OutDir "audit_manifest_$timestamp.txt"

Write-Utf8NoBom -Path $manifestPath -Content @"
DV Audit Bundle
Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
RepoRoot: $RepoRoot
OutDir: $OutDir

"@

# 1) Core top files
$coreFiles = @(
    "README.md",
    "REPO_SCOPE.md",
    "PROJECT_INDEX.md",
    "dv.ps1",
    "scanner.py"
)

foreach ($rel in $coreFiles) {
    $src = Join-Path $RepoRoot $rel
    $dst = Join-Path $OutDir ("core_" + ($rel -replace '[\\/:*?""<>|]', '_'))
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Append-Utf8NoBom -Path $manifestPath -Content "COPIED CORE FILE: $src`r`n"
    } else {
        Append-Utf8NoBom -Path $manifestPath -Content "MISSING CORE FILE: $src`r`n"
    }
}

Append-Utf8NoBom -Path $manifestPath -Content "`r`n"

# 2) Top tree
$treeOut = Join-Path $OutDir "audit_tree_top_$timestamp.txt"
$treeText = (cmd /c "tree `"$RepoRoot`" /F /A" | Out-String)
Write-Utf8NoBom -Path $treeOut -Content $treeText
Append-Utf8NoBom -Path $manifestPath -Content "CREATED TREE: $treeOut`r`n"

# 3) Key dirs listing
$keyDirs = @(
    "agent",
    "api",
    "core",
    "eii_engine",
    "contracts",
    "docs",
    "runs",
    "tests",
    "scripts"
)

$keyDirsOut = Join-Path $OutDir "audit_key_dirs_$timestamp.txt"
Write-Utf8NoBom -Path $keyDirsOut -Content "AspectNova key directories`r`nGenerated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`r`n`r`n"

foreach ($d in $keyDirs) {
    $p = Join-Path $RepoRoot $d
    Append-Utf8NoBom -Path $keyDirsOut -Content "===== $p =====`r`n"
    if (Test-Path $p) {
        $items = Get-ChildItem -Path $p -Recurse -Force | Select-Object FullName
        $txt = ($items | Format-Table -HideTableHeaders | Out-String)
        Append-Utf8NoBom -Path $keyDirsOut -Content ($txt + "`r`n")
        Append-Utf8NoBom -Path $manifestPath -Content "LISTED DIR: $p`r`n"
    } else {
        Append-Utf8NoBom -Path $keyDirsOut -Content "[MISSING]`r`n`r`n"
        Append-Utf8NoBom -Path $manifestPath -Content "MISSING DIR: $p`r`n"
    }
}

Append-Utf8NoBom -Path $manifestPath -Content "`r`n"

# 4) ADR files
$adrTargets = @(
    (Join-Path $RepoRoot "docs\adr"),
    (Join-Path $RepoRoot "agent\docs\adr"),
    (Join-Path $RepoRoot "eii_engine\contracts\adr")
)

$adrOutDir = Join-Path $OutDir "adr"
New-Item -ItemType Directory -Path $adrOutDir -Force | Out-Null

foreach ($adrDir in $adrTargets) {
    if (Test-Path $adrDir) {
        $files = Get-ChildItem -Path $adrDir -Filter *.md -File -Recurse
        foreach ($f in $files) {
            $safeName = ($f.FullName.Substring($RepoRoot.Length).TrimStart('\') -replace '[\\/:*?""<>|]', '__')
            $dst = Join-Path $adrOutDir $safeName
            Copy-Item $f.FullName $dst -Force
            Append-Utf8NoBom -Path $manifestPath -Content "COPIED ADR: $($f.FullName)`r`n"
        }
    } else {
        Append-Utf8NoBom -Path $manifestPath -Content "MISSING ADR DIR: $adrDir`r`n"
    }
}

Append-Utf8NoBom -Path $manifestPath -Content "`r`n"

# 5) Latest reports
$reportsOutDir = Join-Path $OutDir "reports"
New-Item -ItemType Directory -Path $reportsOutDir -Force | Out-Null

$latestReports = Get-ChildItem -Path (Join-Path $RepoRoot "runs") -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "dv_report.md" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 5

$reportIndex = 0
foreach ($r in $latestReports) {
    $reportIndex++
    $parentName = Split-Path (Split-Path $r.FullName -Parent) -Leaf
    $dstName = "{0:D2}_{1}_dv_report.md" -f $reportIndex, $parentName
    $dst = Join-Path $reportsOutDir $dstName
    Copy-Item $r.FullName $dst -Force
    Append-Utf8NoBom -Path $manifestPath -Content "COPIED REPORT: $($r.FullName) -> $dst`r`n"
}

Append-Utf8NoBom -Path $manifestPath -Content "`r`n"

# 6) Latest zip artifacts
$artifactsOutDir = Join-Path $OutDir "artifacts"
New-Item -ItemType Directory -Path $artifactsOutDir -Force | Out-Null

$latestZips = Get-ChildItem -Path (Join-Path $RepoRoot "runs") -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "dv_run_*.zip" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 3

foreach ($z in $latestZips) {
    $dst = Join-Path $artifactsOutDir $z.Name
    Copy-Item $z.FullName $dst -Force
    Append-Utf8NoBom -Path $manifestPath -Content "COPIED ZIP: $($z.FullName)`r`n"
}

Append-Utf8NoBom -Path $manifestPath -Content "`r`n"

# 7) Summary inventory
$inventoryPath = Join-Path $OutDir "inventory_$timestamp.txt"
$inventory = Get-ChildItem -Path $OutDir -Recurse -Force |
    Select-Object FullName, Length, LastWriteTime |
    Sort-Object FullName |
    Format-Table -AutoSize | Out-String

Write-Utf8NoBom -Path $inventoryPath -Content $inventory
Append-Utf8NoBom -Path $manifestPath -Content "CREATED INVENTORY: $inventoryPath`r`n"

Write-Host ""
Write-Host "DV audit bundle created." -ForegroundColor Green
Write-Host "OutDir: $OutDir" -ForegroundColor Cyan
Write-Host "Manifest: $manifestPath" -ForegroundColor Yellow