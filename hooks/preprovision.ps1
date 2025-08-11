# Pre-provision hook for Azure Developer CLI
# This script automatically converts Google Cloud credentials to base64 before deployment

Write-Host "Running pre-provision hook: Converting credentials to base64..." -ForegroundColor Cyan

# Check if we already have base64 credentials set
$existingB64 = azd env get-value GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_B64 2>$null

if ($existingB64) {
    Write-Host "Base64 credentials already configured" -ForegroundColor Green
    exit 0
}

# Check for raw JSON credentials in environment
$rawCreds = azd env get-value GOOGLE_SERVICE_ACCOUNT_CREDENTIALS 2>$null

if (-not $rawCreds) {
    # Try to find a key file in common locations
    $possiblePaths = @(
        ".\key-file.json",
        ".\gcp-credentials.json",
        ".\credentials.json",
        ".\service-account.json",
        ".\.azure\key-file.json"
    )
    
    $foundPath = $null
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $foundPath = $path
            Write-Host "Found credentials file at: $foundPath" -ForegroundColor Yellow
            break
        }
    }
    
    if ($foundPath) {
        # Read the credentials from file
        $rawCreds = Get-Content -Raw $foundPath
        
        # Extract project ID from the JSON
        try {
            $jsonObj = $rawCreds | ConvertFrom-Json
            if ($jsonObj.project_id) {
                azd env set GOOGLE_CLOUD_PROJECT_ID $jsonObj.project_id 2>&1 | Out-Null
                Write-Host "Set GOOGLE_CLOUD_PROJECT_ID to: $($jsonObj.project_id)" -ForegroundColor Green
            }
        } catch {
            Write-Host "Warning: Could not parse project_id from credentials" -ForegroundColor Yellow
        }
    } else {
        Write-Host "ERROR: No Google Cloud credentials found!" -ForegroundColor Red
        Write-Host "Please either:" -ForegroundColor Yellow
        Write-Host "  1. Place your service account JSON file as 'key-file.json' in the project root" -ForegroundColor Yellow
        Write-Host "  2. Run: azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS '<your-json-content>'" -ForegroundColor Yellow
        exit 1
    }
}

# Convert to base64
Write-Host "Converting credentials to base64..." -ForegroundColor Yellow
try {
    $base64Credentials = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($rawCreds))
    
    # Set the base64 version
    azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_B64 $base64Credentials 2>&1 | Out-Null
    Write-Host "Successfully set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_B64" -ForegroundColor Green
    
    # Remove the raw JSON version to avoid confusion
    azd env unset GOOGLE_SERVICE_ACCOUNT_CREDENTIALS 2>&1 | Out-Null
    
} catch {
    Write-Host "ERROR: Failed to convert credentials to base64: $_" -ForegroundColor Red
    exit 1
}

# Ensure other required variables have defaults
$envName = azd env get-value AZURE_ENV_NAME 2>$null
if (-not $envName) {
    azd env set AZURE_ENV_NAME "python-bq-mcp" 2>&1 | Out-Null
    Write-Host "Set AZURE_ENV_NAME to default: python-bq-mcp" -ForegroundColor Green
}

$location = azd env get-value AZURE_LOCATION 2>$null
if (-not $location) {
    azd env set AZURE_LOCATION "centralus" 2>&1 | Out-Null
    Write-Host "Set AZURE_LOCATION to default: centralus" -ForegroundColor Green
}

$enableAuth = azd env get-value ENABLE_AUTH 2>$null
if (-not $enableAuth) {
    azd env set ENABLE_AUTH "false" 2>&1 | Out-Null
    Write-Host "Set ENABLE_AUTH to default: false" -ForegroundColor Green
}

# Ensure empty strings for optional auth parameters
$apiKeys = azd env get-value API_KEYS 2>$null
if ($null -eq $apiKeys) {
    azd env set API_KEYS "" 2>&1 | Out-Null
}

$jwtSecret = azd env get-value JWT_SECRET 2>$null
if ($null -eq $jwtSecret) {
    azd env set JWT_SECRET "" 2>&1 | Out-Null
}

Write-Host "Pre-provision hook completed successfully!" -ForegroundColor Green
