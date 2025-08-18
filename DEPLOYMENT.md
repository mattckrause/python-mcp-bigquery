# Deployment Guide for Azure

This project includes automatic handling of Google Cloud credentials during Azure deployment to avoid JSON parsing errors.

## How It Works

1. **Automatic Base64 Conversion**: When you run `azd up`, a pre-provision hook automatically:
   - Looks for your Google Cloud service account credentials
   - Converts them to base64 format (avoiding JSON parsing issues)
   - Sets up all required environment variables

2. **Automatic Decoding**: The application automatically:
   - Detects base64-encoded credentials in the environment
   - Decodes them at runtime
   - Uses them to authenticate with Google Cloud BigQuery

## Setup Steps

### 1. Place Your Google Cloud Credentials

Save your Google Cloud service account JSON file as `key-file.json` in the project root:

```bash
# Copy your service account JSON to the project root
cp ~/Downloads/your-service-account.json ./key-file.json
```

The hook will also look for these alternative filenames:
- `gcp-credentials.json`
- `credentials.json`
- `service-account.json`
- `.azure/key-file.json`

### 2. Initialize Azure Developer CLI

```bash
# Initialize a new azd environment
azd init

# Or use an existing environment
azd env select <your-environment>
```

### 3. Deploy

Simply run:

```bash
azd up
```

The pre-provision hook will:
- Find your credentials file
- Convert it to base64
- Set up all required environment variables
- Deploy your application

## Manual Setup (Optional)

If you prefer to set up credentials manually:

### PowerShell
```powershell
# Convert credentials to base64
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw .\key-file.json)))
azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS $b64

# Set other required variables
azd env set GOOGLE_CLOUD_PROJECT_ID "your-project-id"
azd env set AZURE_ENV_NAME "python-bq-mcp"
azd env set AZURE_LOCATION "centralus"
```

### Bash (Linux/Mac)
```bash
# Convert credentials to base64
export B64=$(cat key-file.json | base64 | tr -d '\n')
azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS "$B64"

# Set other required variables
azd env set GOOGLE_CLOUD_PROJECT_ID "your-project-id"
azd env set AZURE_ENV_NAME "python-bq-mcp"
azd env set AZURE_LOCATION "centralus"
```

## Files Involved

- **`hooks/preprovision.ps1`**: PowerShell hook for Windows
- **`hooks/preprovision.sh`**: Bash hook for Linux/Mac
- **`infra/main.parameters.json`**: Uses `${GOOGLE_SERVICE_ACCOUNT_CREDENTIALS}`
- **`src/mcp_bigquery_server/main.py`**: Automatically decodes base64 credentials

## Troubleshooting

### "No Google Cloud credentials found" Error
- Ensure your service account JSON file is in the project root
- Check that it's named `key-file.json` or one of the alternative names

### "Invalid JSON" Error
- Verify your service account JSON file is valid
- Try: `python -m json.tool key-file.json`

### Manual Testing
To test the base64 conversion manually:

```powershell
# PowerShell
.\setup-credentials.ps1

# Or if your file has a different name
.\setup-credentials.ps1 -KeyFilePath "path\to\your\credentials.json"
```

## Security Notes

- The credentials are stored securely in Azure Key Vault after deployment
- The base64 encoding is only used during deployment to avoid JSON parsing issues
- Never commit your `key-file.json` or any credentials file to version control
- Add `*.json` containing credentials to your `.gitignore`
