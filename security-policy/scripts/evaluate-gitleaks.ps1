param(
    [string]$ReportPath = "./reports/gitleaks/final.json"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "        GITLEAKS SECURITY GATE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 1. Validate report
# ------------------------------------------------------------

if (-not (Test-Path $ReportPath)) {
    Write-Host "ERROR: Gitleaks report not found." -ForegroundColor Red
    Write-Host "Expected report: $ReportPath" -ForegroundColor Yellow
    exit 1
}

try {
    $gitleaks = Get-Content $ReportPath -Raw | ConvertFrom-Json
}
catch {
    Write-Host "ERROR: Unable to parse Gitleaks JSON report." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# 2. Normalize findings
# ------------------------------------------------------------

if ($null -eq $gitleaks) {
    Write-Host "ERROR: Gitleaks report is empty." -ForegroundColor Red
    exit 1
}

# Gitleaks JSON output is normally an array of findings.
# If there is only one finding, PowerShell may treat it as
# a single object, so @() ensures consistent handling.

$findings = @($gitleaks)

# ------------------------------------------------------------
# 3. Security policy
# ------------------------------------------------------------

Write-Host "SECURITY POLICY" -ForegroundColor White
Write-Host "========================================"
Write-Host "Unapproved secrets allowed: 0"
Write-Host "Known test secrets:          ALLOWLISTED"
Write-Host "Unknown secrets:             BLOCK"
Write-Host ""

# ------------------------------------------------------------
# 4. Display summary
# ------------------------------------------------------------

$findingCount = $findings.Count

Write-Host "GITLEAKS SCAN SUMMARY" -ForegroundColor White
Write-Host "========================================"
Write-Host "Total findings: $findingCount"
Write-Host ""

if ($findingCount -eq 0) {
    Write-Host "No secrets detected." -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "GITLEAKS GATE DECISION" -ForegroundColor Green
    Write-Host "========================================"
    Write-Host "SECURITY GATE: PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "No secret threshold was violated."
    Write-Host "Deployment may proceed."
    Write-Host ""

    exit 0
}

# ------------------------------------------------------------
# 5. Group findings by rule
# ------------------------------------------------------------

Write-Host "FINDINGS BY RULE" -ForegroundColor Yellow
Write-Host "========================================"

$findings |
    Group-Object RuleID |
    Sort-Object Count -Descending |
    ForEach-Object {
        Write-Host ("{0,-25} {1,5}" -f $_.Name, $_.Count)
    }

Write-Host ""

# ------------------------------------------------------------
# 6. Display affected files
# ------------------------------------------------------------

Write-Host "AFFECTED FILES" -ForegroundColor Yellow
Write-Host "========================================"

$findings |
    Group-Object File |
    Sort-Object Count -Descending |
    Select-Object -First 20 |
    ForEach-Object {
        Write-Host ("{0,5}  {1}" -f $_.Count, $_.Name)
    }

Write-Host ""

# ------------------------------------------------------------
# 7. Security gate decision
# ------------------------------------------------------------

Write-Host "========================================" -ForegroundColor Red
Write-Host "GITLEAKS GATE DECISION" -ForegroundColor Red
Write-Host "========================================"
Write-Host "SECURITY GATE: FAILED" -ForegroundColor Red
Write-Host ""
Write-Host "Unapproved secret findings were detected." -ForegroundColor Red
Write-Host "Deployment must be blocked until the findings"
Write-Host "are reviewed and appropriately resolved."
Write-Host ""

exit 1