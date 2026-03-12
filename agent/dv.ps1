param(
  [Parameter(Mandatory=$true, Position=0)]
  [ValidateSet("selftest","approve","run","newrun")]
  [string]$Cmd,

  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AgentSrc = Join-Path $PSScriptRoot "src"
$ContractsRoot = Join-Path $RepoRoot "contracts"

if (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = $AgentSrc
} elseif ($env:PYTHONPATH -notlike "*$AgentSrc*") {
    $env:PYTHONPATH = "$AgentSrc;$($env:PYTHONPATH)"
}

if (-not $env:ASPECTNOVA_CONTRACTS_ROOT) {
    $env:ASPECTNOVA_CONTRACTS_ROOT = $ContractsRoot
}

Set-Location $RepoRoot

function Invoke-AspectNovaCli {
    param(
        [Parameter(Mandatory=$true)]
        [string[]]$CliArgs
    )

    & python -m aspectnova_agent.cli @CliArgs
    exit $LASTEXITCODE
}

switch ($Cmd) {
    "selftest" {
        & python "$RepoRoot\contracts\tools\verify_contracts.py"
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & python -m aspectnova_agent.cli verify
        exit $LASTEXITCODE
    }

    "run" {
        if (-not $Args -or $Args.Count -lt 1) {
            throw "run requires a run id. Example: .\agent\dv.ps1 run run_20260311T224641Z_7623d59c"
        }

        $runId = $Args[0]
        $extra = @()

        if ($Args.Count -gt 1) {
            $extra = $Args[1..($Args.Count - 1)]
        }

        $cliArgs = @("run", "--run-id", $runId) + $extra
        Invoke-AspectNovaCli -CliArgs $cliArgs
    }

    "newrun" {
        $utcNow = [DateTime]::UtcNow
        $timestamp = $utcNow.ToString("yyyyMMddTHHmmssZ")
        $shortId = -join ((48..57) + (97..102) | Get-Random -Count 8 | ForEach-Object { [char]$_ })
        $runId = "run_${timestamp}_${shortId}"

        $runsRoot = Join-Path $RepoRoot "runs"
        $runRoot = Join-Path $runsRoot $runId
        $inputDir = Join-Path $runRoot "input"
        $outputDir = Join-Path $runRoot "output"
        $evidenceDir = Join-Path $outputDir "evidence"
        $logsDir = Join-Path $runRoot "logs"
        $metaPath = Join-Path $runRoot "run.meta.json"

        if (Test-Path $runRoot) {
            throw "Refusing to create run because target already exists: $runRoot"
        }

        New-Item -ItemType Directory -Path $runsRoot -Force | Out-Null
        New-Item -ItemType Directory -Path $inputDir -Force | Out-Null
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
        New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

        $meta = [ordered]@{
            run_id = $runId
            created_at_utc = $utcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
            state = "created"
            contracts_root = $env:ASPECTNOVA_CONTRACTS_ROOT
            engine = "aspectnova_agent.cli"
            version = "dv-run-meta.v1"
        }

        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        $metaJson = ($meta | ConvertTo-Json -Depth 5)
        [System.IO.File]::WriteAllText($metaPath, $metaJson, $utf8NoBom)

        $result = [ordered]@{
            status = "CREATED"
            run_id = $runId
            run_root = $runRoot
            meta_file = $metaPath
            next_command = ".\agent\dv.ps1 run $runId"
        }

        $result | ConvertTo-Json -Depth 5
        exit 0
    }

    "approve" {
        throw "approve is not part of the canonical DV baseline yet. It remains legacy/unmapped and must not be treated as stable."
    }

    default {
        throw "Unsupported command: $Cmd"
    }
}