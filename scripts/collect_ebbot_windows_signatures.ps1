# Inspect the local Windows build without running, signing, publishing, or executing it.
# This script does not download anything, read API tokens or use a certificate key.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Dist,
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Output = "desktop-signature-observation.json"
)

$ErrorActionPreference = 'Stop'
$distRoot = [System.IO.Path]::GetFullPath($Dist)
if (-not (Test-Path -LiteralPath $distRoot -PathType Container)) {
    throw "Expected local Windows build directory is missing"
}
if ($Version -notmatch '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$') {
    throw "Invalid desktop version"
}

$targets = [ordered]@{
    nsis_installer = Join-Path $distRoot ("EBBot-windows-installer-v" + $Version + ".exe")
    electron_app = Join-Path $distRoot 'win-unpacked\EBBot.exe'
    python_backend = Join-Path $distRoot 'win-unpacked\resources\backend\stock_analysis\stock_analysis.exe'
}
$observations = [ordered]@{}

foreach ($entry in $targets.GetEnumerator()) {
    $file = $entry.Value
    $exists = Test-Path -LiteralPath $file -PathType Leaf
    $status = 'Missing'
    $thumbprint = $null
    $validFrom = $null
    $validUntil = $null
    if ($exists) {
        try {
            $signature = Get-AuthenticodeSignature -LiteralPath $file
            $status = [string]$signature.Status
            if ($null -ne $signature.SignerCertificate) {
                $thumbprint = [string]$signature.SignerCertificate.Thumbprint
                $validFrom = $signature.SignerCertificate.NotBefore.ToUniversalTime().ToString('o')
                $validUntil = $signature.SignerCertificate.NotAfter.ToUniversalTime().ToString('o')
            }
        } catch {
            $status = 'InspectionError'
        }
    }

    # Only trust Windows signature status and allowlisted thumbprint.
    # No private paths, certificate files, user environment or secrets are uploaded.
    $observations[$entry.Key] = [ordered]@{
        present = [bool]$exists
        status = $status
        thumbprint = $thumbprint
        valid_from = $validFrom
        valid_until = $validUntil
    }
}

$report = [ordered]@{
    schema_version = 1
    platform = 'windows'
    product = 'EBBot'
    version = $Version
    signatures = $observations
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Output -Encoding utf8
Write-Host "Windows Authenticode metadata collected locally without starting any exe."
