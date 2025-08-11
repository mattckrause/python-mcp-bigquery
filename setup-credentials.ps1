# Setup Google Cloud Credentials for Azure Deployment
# This script converts your Google service account JSON to base64 format
# and sets it in your azd environment to avoid JSON parsing errors

param(
    [Parameter(Mandatory=$false)]
    [string]$KeyFilePath = ".\key-file.json"
)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Google Cloud Credentials Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if the key file exists
if (-not (Test-Path $KeyFilePath)) {
    Write-Host "Error: Key file not found at: $KeyFilePath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure you have your Google service account JSON file saved as:" -ForegroundColor Yellow
    Write-Host "  $KeyFilePath" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or run this script with a different path:" -ForegroundColor Yellow
    Write-Host "  .\setup-credentials.ps1 -KeyFilePath 'path\to\your\key.json'" -ForegroundColor Yellow
    exit 1
}

Write-Host "Found key file at: $KeyFilePath" -ForegroundColor Green
Write-Host ""

# Read and validate the JSON
Write-Host "Validating JSON format..." -ForegroundColor Yellow
try {
    $jsonContent = Get-Content -Raw $KeyFilePath
    $jsonObject = $jsonContent | ConvertFrom-Json
    
    # Check for required fields
    if (-not $jsonObject.project_id) {
        throw "Missing 'project_id' field in JSON"
    }
    if (-not $jsonObject.client_email) {
        throw "Missing 'client_email' field in JSON"
    }
    
    Write-Host "✓ JSON validation successful" -ForegroundColor Green
    Write-Host "  Project ID: $($jsonObject.project_id)" -ForegroundColor Gray
    Write-Host "  Client Email: $($jsonObject.client_email)" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "Error: Invalid JSON format - $_" -ForegroundColor Red
    exit 1
}

# Convert to base64
Write-Host "Converting to base64..." -ForegroundColor Yellow
$base64Credentials = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($jsonContent))
Write-Host "✓ Base64 conversion successful" -ForegroundColor Green
Write-Host ""

# Set in azd environment
Write-Host "Setting azd environment variables..." -ForegroundColor Yellow

# Set the base64 credentials
try {
    azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_B64 $base64Credentials 2>&1 | Out-Null
    Write-Host "✓ Set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_B64" -ForegroundColor Green
} catch {
    Write-Host "Error setting GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_B64: $_" -ForegroundColor Red
    exit 1
}

# Remove the old raw JSON variable if it exists
try {
    azd env unset GOOGLE_SERVICE_ACCOUNT_CREDENTIALS 2>&1 | Out-Null
    Write-Host "✓ Removed old GOOGLE_SERVICE_ACCOUNT_CREDENTIALS (if existed)" -ForegroundColor Green
} catch {
    # It's okay if this fails - the variable might not exist
}

# Also set the project ID if not already set
if ($jsonObject.project_id) {
    try {
        azd env set GOOGLE_CLOUD_PROJECT_ID $jsonObject.project_id 2>&1 | Out-Null
        Write-Host "✓ Set GOOGLE_CLOUD_PROJECT_ID to: $($jsonObject.project_id)" -ForegroundColor Green
    } catch {
        Write-Host "Warning: Could not set GOOGLE_CLOUD_PROJECT_ID: $_" -ForegroundColor Yellow
    }
}

# Set other required variables if not set
Write-Host ""
Write-Host "Checking other required environment variables..." -ForegroundColor Yellow

# Check AZURE_ENV_NAME
$envName = azd env get-value AZURE_ENV_NAME 2>$null
if (-not $envName) {
    Write-Host "Setting AZURE_ENV_NAME to default value..." -ForegroundColor Yellow
    azd env set AZURE_ENV_NAME "python-bq-mcp" 2>&1 | Out-Null
    Write-Host "✓ Set AZURE_ENV_NAME to: python-bq-mcp" -ForegroundColor Green
} else {
    Write-Host "✓ AZURE_ENV_NAME already set to: $envName" -ForegroundColor Green
}

# Check AZURE_LOCATION
$location = azd env get-value AZURE_LOCATION 2>$null
if (-not $location) {
    Write-Host "Setting AZURE_LOCATION to default value..." -ForegroundColor Yellow
    azd env set AZURE_LOCATION "centralus" 2>&1 | Out-Null
    Write-Host "✓ Set AZURE_LOCATION to: centralus" -ForegroundColor Green
} else {
    Write-Host "✓ AZURE_LOCATION already set to: $location" -ForegroundColor Green
}

# Set authentication variables to defaults if not set
$enableAuth = azd env get-value ENABLE_AUTH 2>$null
if (-not $enableAuth) {
    azd env set ENABLE_AUTH "false" 2>&1 | Out-Null
    Write-Host "✓ Set ENABLE_AUTH to: false (default)" -ForegroundColor Green
} else {
    Write-Host "✓ ENABLE_AUTH already set to: $enableAuth" -ForegroundColor Green
}

# Ensure API_KEYS and JWT_SECRET are at least empty strings
$apiKeys = azd env get-value API_KEYS 2>$null
if ($null -eq $apiKeys) {
    azd env set API_KEYS "" 2>&1 | Out-Null
    Write-Host "✓ Set API_KEYS to: (empty)" -ForegroundColor Green
}

$jwtSecret = azd env get-value JWT_SECRET 2>$null
if ($null -eq $jwtSecret) {
    azd env set JWT_SECRET "" 2>&1 | Out-Null
    Write-Host "✓ Set JWT_SECRET to: (empty)" -ForegroundColor Green
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your credentials have been successfully converted to base64" -ForegroundColor Green
Write-Host "and stored in your azd environment." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Your parameters file needs to be updated (see next output)" -ForegroundColor White
Write-Host "  2. Run 'azd up' to deploy your application" -ForegroundColor White
Write-Host ""
Write-Host "Note: Your application will need to decode the base64 credentials" -ForegroundColor Cyan
Write-Host "at runtime. See the README for implementation details." -ForegroundColor Cyan
