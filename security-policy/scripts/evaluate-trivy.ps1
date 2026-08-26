param(
    [string]$ReportPath = ".\reports\trivy\baseline.json",
    [string]$PolicyPath = ".\security-gate\policy\security-policy.json"
)

$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Title)

    Write-Host ""
    Write-Host "========================================"
    Write-Host $Title
    Write-Host "========================================"
}

# Resolve paths relative to the project root
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

$ReportPath = Join-Path $ProjectRoot $ReportPath
$PolicyPath = Join-Path $ProjectRoot $PolicyPath

Write-Section "DEVSECOPS SECURITY GATE"

# Validate required files
if (-not (Test-Path $ReportPath)) {
    Write-Host "ERROR: Trivy report not found:"
    Write-Host $ReportPath
    exit 2
}

if (-not (Test-Path $PolicyPath)) {
    Write-Host "ERROR: Security policy not found:"
    Write-Host $PolicyPath
    exit 2
}

# Load JSON files
try {
    $Report = Get-Content $ReportPath -Raw | ConvertFrom-Json
    $Policy = Get-Content $PolicyPath -Raw | ConvertFrom-Json
}
catch {
    Write-Host "ERROR: Failed to parse JSON."
    Write-Host $_.Exception.Message
    exit 2
}

# Validate basic report structure
if (-not $Report.ArtifactName) {
    Write-Host "ERROR: Trivy report does not contain an ArtifactName."
    exit 2
}

Write-Host ""
Write-Host "Artifact: $($Report.ArtifactName)"
Write-Host "Type:     $($Report.ArtifactType)"

# Initialize severity counters
$Counts = @{
    CRITICAL = 0
    HIGH     = 0
    MEDIUM   = 0
    LOW      = 0
    UNKNOWN  = 0
}

# Count vulnerabilities across all Trivy result targets
foreach ($Result in $Report.Results) {

    if ($null -eq $Result.Vulnerabilities) {
        continue
    }

    foreach ($Vulnerability in $Result.Vulnerabilities) {

        $Severity = $Vulnerability.Severity.ToUpper()

        if ($Counts.ContainsKey($Severity)) {
            $Counts[$Severity]++
        }
        else {
            $Counts["UNKNOWN"]++
        }
    }
}

Write-Section "VULNERABILITY SUMMARY"

Write-Host ("CRITICAL : {0}" -f $Counts["CRITICAL"])
Write-Host ("HIGH     : {0}" -f $Counts["HIGH"])
Write-Host ("MEDIUM   : {0}" -f $Counts["MEDIUM"])
Write-Host ("LOW      : {0}" -f $Counts["LOW"])
Write-Host ("UNKNOWN  : {0}" -f $Counts["UNKNOWN"])

# Read policy thresholds
$CriticalThreshold = $Policy.vulnerabilityThresholds.CRITICAL
$HighThreshold     = $Policy.vulnerabilityThresholds.HIGH
$MediumThreshold   = $Policy.vulnerabilityThresholds.MEDIUM
$LowThreshold      = $Policy.vulnerabilityThresholds.LOW

Write-Section "SECURITY POLICY"

Write-Host ("CRITICAL allowed: {0}" -f $CriticalThreshold)
Write-Host ("HIGH allowed:     {0}" -f $HighThreshold)

if ($null -eq $MediumThreshold) {
    Write-Host "MEDIUM:           WARN"
}
else {
    Write-Host ("MEDIUM allowed:   {0}" -f $MediumThreshold)
}

if ($null -eq $LowThreshold) {
    Write-Host "LOW:              INFO"
}
else {
    Write-Host ("LOW allowed:      {0}" -f $LowThreshold)
}

# Evaluate the gate
$GateFailed = $false
$FailureReasons = @()

if (($null -ne $CriticalThreshold) -and ($Counts["CRITICAL"] -gt $CriticalThreshold)) {
    $GateFailed = $true
    $FailureReasons += "Critical vulnerabilities exceed the allowed threshold."
}

if (($null -ne $HighThreshold) -and ($Counts["HIGH"] -gt $HighThreshold)) {
    $GateFailed = $true
    $FailureReasons += "High vulnerabilities exceed the allowed threshold."
}

if (($null -ne $MediumThreshold) -and ($Counts["MEDIUM"] -gt $MediumThreshold)) {
    $GateFailed = $true
    $FailureReasons += "Medium vulnerabilities exceed the allowed threshold."
}

if (($null -ne $LowThreshold) -and ($Counts["LOW"] -gt $LowThreshold)) {
    $GateFailed = $true
    $FailureReasons += "Low vulnerabilities exceed the allowed threshold."
}

# Final decision
Write-Section "SECURITY GATE DECISION"

if ($GateFailed) {

    Write-Host "SECURITY GATE: BLOCKED"
    Write-Host ""

    foreach ($Reason in $FailureReasons) {
        Write-Host "[BLOCK] $Reason"
    }

    Write-Host ""
    Write-Host "Deployment must not proceed."

    exit 1
}
else {

    Write-Host "SECURITY GATE: PASSED"
    Write-Host ""
    Write-Host "No vulnerability threshold was violated."
    Write-Host "Deployment may proceed."

    exit 0
}