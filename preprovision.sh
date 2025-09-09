#!/bin/bash
# Pre-provision hook for Azure Developer CLI (Linux/Mac)
# This script automatically converts Google Cloud credentials to base64 before deployment

echo -e "\033[36mRunning pre-provision hook: Converting credentials to base64...\033[0m"

# Check if we already have base64 credentials set
existingB64=$(azd env get-value GOOGLE_SERVICE_ACCOUNT_CREDENTIALS 2>/dev/null)

if [ -n "$existingB64" ]; then
    echo -e "\033[32mBase64 credentials already configured\033[0m"
    exit 0
fi

# Check for raw JSON credentials in environment
rawCreds=$(azd env get-value GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_RAW 2>/dev/null)

if [ -z "$rawCreds" ]; then
    # Try to find a key file in common locations
    possiblePaths=(
        "./key-file.json"
        "./gcp-credentials.json"
        "./credentials.json"
        "./service-account.json"
        "./.azure/key-file.json"
    )
    
    foundPath=""
    for path in "${possiblePaths[@]}"; do
        if [ -f "$path" ]; then
            foundPath="$path"
            echo -e "\033[33mFound credentials file at: $foundPath\033[0m"
            break
        fi
    done
    
    if [ -n "$foundPath" ]; then
        # Read the credentials from file
        rawCreds=$(cat "$foundPath")
        
        # Extract project ID from the JSON
        projectId=$(echo "$rawCreds" | grep -o '"project_id"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:[[:space:]]*"\([^"]*\)"/\1/')
        if [ -n "$projectId" ]; then
            existingProj=$(azd env get-value GOOGLE_CLOUD_PROJECT_ID 2>/dev/null)
            if [ -n "$existingProj" ]; then
                echo -e "\033[33mSkipping GOOGLE_CLOUD_PROJECT_ID: already set to '$existingProj'\033[0m"
            else
                azd env set GOOGLE_CLOUD_PROJECT_ID "$projectId" 2>&1 >/dev/null
                echo -e "\033[32mSet GOOGLE_CLOUD_PROJECT_ID to: $projectId\033[0m"
            fi
        fi
    else
        echo -e "\033[31mERROR: No Google Cloud credentials found!\033[0m"
        echo -e "\033[33mPlease either:\033[0m"
        echo -e "\033[33m  1. Place your service account JSON file as 'key-file.json' in the project root\033[0m"
        echo -e "\033[33m  2. Run: azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS '<your-json-content>'\033[0m"
        exit 1
    fi
fi

# Convert to base64
echo -e "\033[33mConverting credentials to base64...\033[0m"
base64Credentials=$(echo -n "$rawCreds" | base64 | tr -d '\n')

if [ $? -eq 0 ]; then
    # Set the base64 version
    azd env set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS "$base64Credentials" 2>&1 >/dev/null
    echo -e "\033[32mSuccessfully set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS\033[0m"
    # Remove the old variable name if present
    azd env unset GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_B64 2>&1 >/dev/null
else
    echo -e "\033[31mERROR: Failed to convert credentials to base64\033[0m"
    exit 1
fi

# Ensure other required variables have defaults

# Always set AZURE_ENV_NAME and AZURE_LOCATION from .env if present
if [ -f .env ]; then
    source .env
    if [ -n "$AZURE_ENV_NAME" ]; then
        existingEnvName=$(azd env get-value AZURE_ENV_NAME 2>/dev/null)
        if [ -n "$existingEnvName" ]; then
            echo -e "\033[33mSkipping AZURE_ENV_NAME: already set to '$existingEnvName'\033[0m"
        else
            azd env set AZURE_ENV_NAME "$AZURE_ENV_NAME" 2>&1 >/dev/null
            echo -e "\033[32mSet AZURE_ENV_NAME from .env: $AZURE_ENV_NAME\033[0m"
        fi
    fi
    if [ -n "$AZURE_LOCATION" ]; then
        existingLocation=$(azd env get-value AZURE_LOCATION 2>/dev/null)
        if [ -n "$existingLocation" ]; then
            echo -e "\033[33mSkipping AZURE_LOCATION: already set to '$existingLocation'\033[0m"
        else
            azd env set AZURE_LOCATION "$AZURE_LOCATION" 2>&1 >/dev/null
            echo -e "\033[32mSet AZURE_LOCATION from .env: $AZURE_LOCATION\033[0m"
        fi
    fi
fi

enableAuth=$(azd env get-value ENABLE_AUTH 2>/dev/null)
if [ -z "$enableAuth" ]; then
    azd env set ENABLE_AUTH "false" 2>&1 >/dev/null
    echo -e "\033[32mSet ENABLE_AUTH to default: false\033[0m"
else
    echo -e "\033[33mSkipping ENABLE_AUTH: already set to '$enableAuth'\033[0m"
fi

# Ensure empty strings for optional auth parameters
apiKeys=$(azd env get-value API_KEYS 2>/dev/null)
if [ -z "$apiKeys" ]; then
    azd env set API_KEYS "" 2>&1 >/dev/null
    echo -e "\033[32mSet API_KEYS to: (empty)\033[0m"
else
    echo -e "\033[33mSkipping API_KEYS: already set to '$apiKeys'\033[0m"
fi

jwtSecret=$(azd env get-value JWT_SECRET 2>/dev/null)
if [ -z "$jwtSecret" ]; then
    azd env set JWT_SECRET "" 2>&1 >/dev/null
    echo -e "\033[32mSet JWT_SECRET to: (empty)\033[0m"
else
    echo -e "\033[33mSkipping JWT_SECRET: already set to '$jwtSecret'\033[0m"
fi

echo -e "\033[32mPre-provision hook completed successfully!\033[0m"
