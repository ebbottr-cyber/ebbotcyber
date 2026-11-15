#requires -Version 5.1
<#
.SYNOPSIS
  Safely verify BIST100 real Yahoo OHLCV -> isolated SQLite -> technical ranking.
.DESCRIPTION
  Must run from the PR #8 working tree on Windows with dependencies installed.
  This script NEVER writes to the production DATABASE_PATH. It always creates a
  unique, independent SQLite database and leaves reports on the local computer.
  The default checks five dated members; -Full100 runs the whole active index
  only AFTER all five passed. Neither mode places orders or calls LLM APIs.
.EXAMPLE
  .\scripts\bist100-live-validation.ps1 -AsOf 2026-11-15
.EXAMPLE
  .\scripts\bist100-live-validation.ps1 -AsOf 2026-11-15 -Full100
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
  [string]$AsOf,
  [switch]$Full100,
  [string]$PythonExe = '',
  [string]$OutputRoot = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$originalDb = [Environment]::GetEnvironmentVariable('DATABASE_PATH', 'Process')
$wasSet = $null -ne $originalDb

function Invoke-PythonToFile {
  param(
    [Parameter(Mandatory = $true)][string[]]$Arguments,
    [Parameter(Mandatory = $true)][string]$OutputFile,
    [Parameter(Mandatory = $true)][string]$ErrorFile
  )
  & $PythonExe @Arguments 1> $OutputFile 2> $ErrorFile
  if ($LASTEXITCODE -ne 0) {
    throw "Python exited with code $LASTEXITCODE. Inspect $ErrorFile"
  }
}

function Read-StrictJson {
  param([Parameter(Mandatory = $true)][string]$Path)
  $bytes = [IO.File]::ReadAllBytes($Path)
  if ($bytes.Length -ge 2 -and $bytes[0] -eq 255 -and $bytes[1] -eq 254) {
    # Windows PowerShell 5.1 native-command redirects can write UTF-16LE.
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding Unicode
  } else {
    # The screener's --output JSON is UTF-8; PowerShell 7 redirects too.
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
  }
  if (-not $raw.Trim()) { throw "Empty JSON output: $Path" }
  return ConvertFrom-Json -InputObject $raw
}

function Confirm-Import {
  param(
    [Parameter(Mandatory = $true)][object]$Report,
    [Parameter(Mandatory = $true)][int]$Expected,
    [Parameter(Mandatory = $true)][string]$ReportPath
  )
  if ($Report.mode -ne 'write_db' -or
      [int]$Report.checked -ne $Expected -or
      [int]$Report.ready_for_import -ne $Expected -or
      [int]$Report.imported -ne $Expected) {
    throw "Import gate failed ($Expected expected). Inspect $ReportPath; no ranking will be trusted."
  }
  if (@($Report.results | Where-Object { $_.storage_status -ne 'imported' }).Count -ne 0) {
    throw "Import contains missing/failed symbols. Inspect $ReportPath"
  }
}

function Confirm-Ranking {
  param(
    [Parameter(Mandatory = $true)][object]$Report,
    [Parameter(Mandatory = $true)][int]$Expected,
    [Parameter(Mandatory = $true)][string]$ReportPath
  )
  if ($Report.mode -ne 'read_only_local_sqlite' -or
      [int]$Report.checked -ne $Expected -or
      [int]$Report.analyzed -ne $Expected -or
      @($Report.ranking).Count -ne $Expected) {
    throw "Technical ranking gate failed ($Expected expected). Inspect $ReportPath"
  }
  if (@($Report.results | Where-Object { $_.status -ne 'analyzed' }).Count -ne 0) {
    throw "Ranking contains unanalyzed symbols. Inspect $ReportPath"
  }
}

try {
  $dateValue = [datetime]::MinValue
  $parsed = [datetime]::TryParseExact(
    $AsOf, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::None, [ref]$dateValue
  )
  if (-not $parsed -or $dateValue -lt [datetime]'2026-10-01' -or
      $dateValue -gt [datetime]'2026-12-31') {
    throw 'The currently reviewed BIST100 2026-Q4 roster is only valid 2026-10-01 through 2026-12-31.'
  }

  $branch = (& git -C $repository branch --show-current).Trim()
  if ($LASTEXITCODE -ne 0 -or $branch -ne 'feat/bist100-mvp') {
    throw "Run from the checked-out feat/bist100-mvp branch. Current branch: $branch"
  }

  if (-not $PythonExe) {
    $PythonExe = Join-Path $repository '.venv\Scripts\python.exe'
  }
  if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python environment not found at $PythonExe. Install project dependencies into the .venv environment first."
  }
  $PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path

  if (-not $OutputRoot) {
    if (-not $env:LOCALAPPDATA) {
      throw 'LOCALAPPDATA not defined; provide -OutputRoot'
    }
    $OutputRoot = Join-Path $env:LOCALAPPDATA 'EBBOTCYBER\BIST100-Validation'
  }
  $unique = [guid]::NewGuid().ToString('N').Substring(0, 8)
  $runFolder = Join-Path $OutputRoot ("smoke-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + "-" + $unique)
  New-Item -ItemType Directory -Force -Path $runFolder | Out-Null
  $stageDatabase = Join-Path $runFolder 'isolated-bist100.db'
  if (Test-Path -LiteralPath $stageDatabase) {
    throw 'Refusing to overwrite a database, even in the staging workspace.'
  }
  # Changing the environment variable only in this PowerShell process keeps
  # the user's DATABASE_PATH and real application DB completely untouched.
  $env:DATABASE_PATH = $stageDatabase

  Push-Location $repository
  try {
    $fiveSymbols = 'THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS'
    $fiveImportFile = Join-Path $runFolder 'import-5.json'
    $fiveRankFile = Join-Path $runFolder 'technical-5.json'

    Write-Host "Stage 1/2: fetching five real Yahoo tickers -> isolated SQLite: $stageDatabase"
    Invoke-PythonToFile -Arguments @(
      '-m', 'src.services.bist100_import', '--as-of', $AsOf,
      '--symbols', $fiveSymbols, '--lookback-days', '365',
      '--min-bars', '60', '--delay-seconds', '1.5', '--write-db'
    ) -OutputFile $fiveImportFile -ErrorFile (Join-Path $runFolder 'import-5.stderr.log')
    Confirm-Import -Report (Read-StrictJson -Path $fiveImportFile) -Expected 5 -ReportPath $fiveImportFile

    Write-Host 'Stage 2/2: ranking five imported tickers with the existing technical engine'
    Invoke-PythonToFile -Arguments @(
      '-m', 'src.services.bist100_screener', '--as-of', $AsOf,
      '--symbols', $fiveSymbols, '--db-path', $stageDatabase,
      '--lookback-days', '365', '--min-bars', '60', '--output', $fiveRankFile
    ) -OutputFile (Join-Path $runFolder 'technical-5.stdout.json') -ErrorFile (Join-Path $runFolder 'technical-5.stderr.log')
    Confirm-Ranking -Report (Read-StrictJson -Path $fiveRankFile) -Expected 5 -ReportPath $fiveRankFile
    Write-Host 'PASS: 5/5 real imports and 5/5 existing-engine technical rankings.'

    if ($Full100) {
      Write-Host 'Full100 explicitly requested; fetching all 100 constituents into SAME isolated database.'
      $fullImportFile = Join-Path $runFolder 'import-100.json'
      $fullRankFile = Join-Path $runFolder 'technical-100.json'
      Invoke-PythonToFile -Arguments @(
        '-m', 'src.services.bist100_import', '--as-of', $AsOf,
        '--lookback-days', '365', '--min-bars', '60',
        '--delay-seconds', '1.5', '--write-db'
      ) -OutputFile $fullImportFile -ErrorFile (Join-Path $runFolder 'import-100.stderr.log')
      Confirm-Import -Report (Read-StrictJson -Path $fullImportFile) -Expected 100 -ReportPath $fullImportFile

      Invoke-PythonToFile -Arguments @(
        '-m', 'src.services.bist100_screener', '--as-of', $AsOf,
        '--db-path', $stageDatabase, '--lookback-days', '365',
        '--min-bars', '60', '--output', $fullRankFile
      ) -OutputFile (Join-Path $runFolder 'technical-100.stdout.json') -ErrorFile (Join-Path $runFolder 'technical-100.stderr.log')
      Confirm-Ranking -Report (Read-StrictJson -Path $fullRankFile) -Expected 100 -ReportPath $fullRankFile
      Write-Host 'PASS: all 100 imported and all 100 ranked in isolated SQLite.'
    }
    Write-Host "Reports and logs: $runFolder"
  }
  finally {
    Pop-Location
  }
}
finally {
  if ($wasSet) {
    $env:DATABASE_PATH = $originalDb
  } else {
    Remove-Item Env:DATABASE_PATH -ErrorAction SilentlyContinue
  }
}
