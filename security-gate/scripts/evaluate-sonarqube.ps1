param(
    [string]$SonarHostUrl = "https://sonarcloud.io",
    [string]$Organization = "king-wealth247",
    [string]$ProjectKey = "King-Wealth247_Automated-DevSecOps-Security-Gate",
    [string]$Token = $env:SONAR_TOKEN
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       SONARQUBE SECURITY GATE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 1. Validate token
# ------------------------------------------------------------

if ([string]::IsNullOrWhiteSpace($Token)) {
    Write-Host "ERROR: SONAR_TOKEN environment variable is not set." `
        -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# 2. Retrieve Quality Gate status
# ------------------------------------------------------------

$qualityGateUrl = `
    "$SonarHostUrl/api/qualitygates/project_status?projectKey=$ProjectKey&organization=$Organization"

try {
    $qualityGateResponse = Invoke-RestMethod `
        -Uri $qualityGateUrl `
        -Headers @{
            Authorization = "Bearer $Token"
        }
}
catch {
    Write-Host "ERROR: Unable to retrieve SonarQube Quality Gate." `
        -ForegroundColor Red

    Write-Host $_.Exception.Message `
        -ForegroundColor Red

    exit 1
}

$status = $qualityGateResponse.projectStatus.status
$conditions = @($qualityGateResponse.projectStatus.conditions)

# ------------------------------------------------------------
# 3. Display project summary
# ------------------------------------------------------------

Write-Host "PROJECT SUMMARY" -ForegroundColor White
Write-Host "========================================"
Write-Host "Organization:        $Organization"
Write-Host "Project Key:         $ProjectKey"
Write-Host "Quality Gate Status: $status"
Write-Host ""

# ------------------------------------------------------------
# 4. Display Quality Gate conditions
# ------------------------------------------------------------

Write-Host "QUALITY CONDITIONS" -ForegroundColor Yellow
Write-Host "========================================"

if ($conditions.Count -eq 0) {
    Write-Host "No Quality Gate conditions were returned."
}
else {
    foreach ($condition in $conditions) {

        $metric = $condition.metricKey
        $actual = $condition.actualValue
        $threshold = $condition.errorThreshold
        $conditionStatus = $condition.status

        Write-Host ("Metric:    {0}" -f $metric)
        Write-Host ("Actual:    {0}" -f $actual)
        Write-Host ("Threshold: {0}" -f $threshold)
        Write-Host ("Status:    {0}" -f $conditionStatus)
        Write-Host ""
    }
}

# ------------------------------------------------------------
# 5. Security Gate decision
# ------------------------------------------------------------

Write-Host "========================================"

if ($status -eq "OK") {

    Write-Host "SONARQUBE GATE DECISION" -ForegroundColor Green
    Write-Host "========================================"
    Write-Host "SECURITY GATE: PASSED" -ForegroundColor Green
    Write-Host ""

    Write-Host "SonarQube Quality Gate requirements were satisfied."
    Write-Host "Pipeline may continue."
    Write-Host ""

    exit 0
}
else {

    Write-Host "SONARQUBE GATE DECISION" -ForegroundColor Red
    Write-Host "========================================"
    Write-Host "SECURITY GATE: FAILED" -ForegroundColor Red
    Write-Host ""

    Write-Host "SonarQube Quality Gate requirements were not satisfied."
    Write-Host "Deployment must be blocked."
    Write-Host ""

    exit 1
}