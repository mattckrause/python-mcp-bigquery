#!/usr/bin/env bash
set -euo pipefail

echo "Updating openapi.yaml with deployed Container App URL..."

RESOURCE_GROUP=${1:-$(azd env get-value AZURE_RESOURCE_GROUP 2>/dev/null || true)}
APP_NAME=${2:-$(azd env get-value SERVICE_API_NAME 2>/dev/null || true)}

if [[ -z "${RESOURCE_GROUP}" || -z "${APP_NAME}" ]]; then
  echo "Warning: Missing resource group or app name; skipping openapi update" >&2
  exit 0
fi

FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query 'properties.configuration.ingress.fqdn' -o tsv)
if [[ -z "$FQDN" ]]; then
  echo "Warning: Could not resolve Container App FQDN" >&2
  exit 0
fi

URL="https://$FQDN"
OPENAPI_PATH="$(dirname "$0")/../openapi.yaml"
if [[ ! -f "$OPENAPI_PATH" ]]; then
  echo "Warning: openapi.yaml not found at $OPENAPI_PATH" >&2
  exit 0
fi

# Ensure a servers section exists with the correct URL
if grep -qE '^servers:' "$OPENAPI_PATH"; then
  awk -v url="$URL" '
    BEGIN{printing=1}
    /^servers:/ { print "servers:\n  - url: " url; printing=0; skip=1; next }
    printing && !skip { print }
    !printing && /^\S/ { printing=1; print; next }
  ' "$OPENAPI_PATH" > "$OPENAPI_PATH.tmp" && mv "$OPENAPI_PATH.tmp" "$OPENAPI_PATH"
else
  printf "servers:\n  - url: %s\n\n" "$URL" | cat - "$OPENAPI_PATH" > "$OPENAPI_PATH.tmp" && mv "$OPENAPI_PATH.tmp" "$OPENAPI_PATH"
fi

echo "Updated openapi.yaml servers -> $URL"
