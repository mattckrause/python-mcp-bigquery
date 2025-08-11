#!/bin/bash
set -e

# Default values
HTTP_HOST=${HTTP_HOST:-"0.0.0.0"}
HTTP_PORT=${HTTP_PORT:-"8000"}

# Validate required environment variables
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "ERROR: GOOGLE_CLOUD_PROJECT environment variable is required"
    exit 1
fi

if [ -z "$GOOGLE_APPLICATION_CREDENTIALS_JSON" ]; then
    echo "ERROR: GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable is required"
    exit 1
fi

# Log configuration (without sensitive data)
echo "Starting MCP BigQuery Server..."
echo "Project ID: $GOOGLE_CLOUD_PROJECT"
echo "HTTP Host: $HTTP_HOST"
echo "HTTP Port: $HTTP_PORT"
echo "Authentication enabled: ${ENABLE_AUTH:-false}"

# Run the HTTP server with proper arguments
exec python -m mcp_bigquery_server.main \
    --project-id "$GOOGLE_CLOUD_PROJECT" \
    --http \
    --host "$HTTP_HOST" \
    --port "$HTTP_PORT"
