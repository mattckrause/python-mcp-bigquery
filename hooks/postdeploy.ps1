param(
    [string]$ResourceGroup,
    [string]$AppName
)

Write-Host "Updating openapi.yaml with deployed Container App URL..." -ForegroundColor Cyan

try {
    if (-not $ResourceGroup) { $ResourceGroup = (azd env get-value AZURE_RESOURCE_GROUP 2>$null) }
    if (-not $AppName) { $AppName = (azd env get-value SERVICE_API_NAME 2>$null) }

    if (-not $ResourceGroup -or -not $AppName) {
        throw "Missing resource group or app name"
    }

    $fqdn = az containerapp show --name $AppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    if (-not $fqdn) { throw "Could not resolve Container App FQDN" }

    $url = "https://$fqdn"
    $openapiPath = Join-Path $PSScriptRoot "..\openapi.yaml" | Resolve-Path
    if (-not (Test-Path $openapiPath)) { throw "openapi.yaml not found at $openapiPath" }

    $content = Get-Content -Raw $openapiPath
    # Ensure a servers section exists with the correct URL
    $serversBlock = "servers:`r`n  - url: $url`r`n"
    if ($content -notmatch "(?ms)^servers:") {
        $content = "servers:`r`n  - url: $url`r`n`r`n" + $content
    } else {
        # Replace existing servers list with the new URL
        $content = [Regex]::Replace($content, "(?ms)^servers:\s*\n(\s*-.*\n)+", $serversBlock)
    }

    Set-Content -Path $openapiPath -Value $content
    Write-Host "✓ Updated openapi.yaml servers -> $url" -ForegroundColor Green
}
catch {
    Write-Host "Warning: Failed to update openapi.yaml: $_" -ForegroundColor Yellow
}
