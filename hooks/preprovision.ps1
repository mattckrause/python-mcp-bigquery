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

# First, try to read from .env file
$envFile = join-path -Path (split-path -Parent $PSScriptRoot) -ChildPath ".env"
$jsonContent = $null
$dotenv = @{}

if (Test-Path $envFile) {
    Write-Host "Reading .env for overrides..." -ForegroundColor Yellow
    $lineRegex = '^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=(.*)$'
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^[ \t]*#') { continue }
        if ($line -match $lineRegex) {
            $key = $matches[1]
            $val = $matches[2].Trim()
            # Strip surrounding quotes if present
            if ($val.StartsWith('"') -and $val.EndsWith('"')) { $val = $val.Substring(1, $val.Length - 2) }
            $dotenv[$key] = $val
        }
    }
    # Extract credentials JSON if provided inline in .env
    if ($dotenv.ContainsKey('GOOGLE_SERVICE_ACCOUNT_CREDENTIALS')) {
        $jsonContent = $dotenv['GOOGLE_SERVICE_ACCOUNT_CREDENTIALS']
        Write-Host "Found GOOGLE_SERVICE_ACCOUNT_CREDENTIALS in .env" -ForegroundColor Green
    }
}

# Fallback to key file if .env doesn't have credentials
if (-not $jsonContent) {
    # Check if the key file exists
    if (-not (Test-Path $KeyFilePath)) {
        Write-Host "Error: No credentials found in .env file and key file not found at: $KeyFilePath" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please either:" -ForegroundColor Yellow
        Write-Host "  1. Add GOOGLE_SERVICE_ACCOUNT_CREDENTIALS=<json> to your .env file" -ForegroundColor Yellow
        Write-Host "  2. Ensure you have your Google service account JSON file saved as:" -ForegroundColor Yellow
        Write-Host "     $KeyFilePath" -ForegroundColor Yellow
        Write-Host "  3. Run this script with a different path:" -ForegroundColor Yellow
        Write-Host "     .\setup-credentials.ps1 -KeyFilePath 'path\to\your\key.json'" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Reading from key file at: $KeyFilePath" -ForegroundColor Green
    $jsonContent = Get-Content -Raw $KeyFilePath
}

Write-Host ""

# Read and validate the JSON
Write-Host "Validating JSON format..." -ForegroundColor Yellow
try {
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
    azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS $base64Credentials 2>&1 | Out-Null
    Write-Host "✓ Set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS (base64)" -ForegroundColor Green
} catch {
    Write-Host "Error setting GOOGLE_SERVICE_ACCOUNT_CREDENTIALS: $_" -ForegroundColor Red
    exit 1
}

# Remove any old variables to avoid confusion
try {
    azd env unset GOOGLE_APPLICATION_CREDENTIALS_JSON 2>&1 | Out-Null
    Write-Host "✓ Removed old GOOGLE_APPLICATION_CREDENTIALS_JSON (if existed)" -ForegroundColor Green
} catch {
    # It's okay if this fails - the variable might not exist
}

# Apply .env overrides for common variables first (preferred over defaults)
Write-Host "Applying .env overrides (if present)..." -ForegroundColor Yellow
foreach ($k in @('GOOGLE_CLOUD_PROJECT_ID','ENABLE_AUTH','API_KEYS','JWT_SECRET')) {
    if ($dotenv.ContainsKey($k)) {
        $v = $dotenv[$k]
        if ($k -eq 'ENABLE_AUTH') { $v = ($v.ToLower() -eq 'true') ? 'true' : 'false' }
        try {
            azd env set $k $v 2>&1 | Out-Null
            Write-Host "✓ Set $k from .env" -ForegroundColor Green
        } catch {
            Write-Host "Warning: Could not set $k from .env: $_" -ForegroundColor Yellow
        }
    }
}

# Also set the project ID from the credentials JSON if not already set via .env
$existingProj = azd env get-value GOOGLE_CLOUD_PROJECT_ID 2>$null
if (-not $existingProj -and $jsonObject.project_id) {
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

# Set authentication variables to defaults if not set (after .env overrides)
$enableAuth = azd env get-value ENABLE_AUTH 2>$null
if (-not $enableAuth) {
    azd env set ENABLE_AUTH "false" 2>&1 | Out-Null
    Write-Host "✓ Set ENABLE_AUTH to: false (default)" -ForegroundColor Green
} else {
    Write-Host "✓ ENABLE_AUTH set to: $enableAuth" -ForegroundColor Green
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

# Set container registry endpoint if registry name exists
$registryName = azd env get-value AZURE_REGISTRY_NAME 2>$null
if ($registryName) {
    $registryEndpoint = azd env get-value AZURE_CONTAINER_REGISTRY_ENDPOINT 2>$null
    if (-not $registryEndpoint) {
        azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT "$registryName.azurecr.io" 2>&1 | Out-Null
        Write-Host "✓ Set AZURE_CONTAINER_REGISTRY_ENDPOINT to: $registryName.azurecr.io" -ForegroundColor Green
    } else {
        Write-Host "✓ AZURE_CONTAINER_REGISTRY_ENDPOINT already set to: $registryEndpoint" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your credentials have been converted to base64 and stored as:" -ForegroundColor Green
Write-Host "  - GOOGLE_SERVICE_ACCOUNT_CREDENTIALS" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run 'azd up' to deploy your application" -ForegroundColor White
Write-Host "  2. The application will decode the base64 credentials at runtime" -ForegroundColor White
Write-Host ""
