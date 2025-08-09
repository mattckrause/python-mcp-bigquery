# MCP BigQuery Python Server

A Python implementation of the Model Context Protocol (MCP) server for Google BigQuery, providing both stdio transport for local development and HTTP transport with streaming capabilities for cloud deployments.

## 🚀 Features

- **Multiple Transport Modes**: stdio for local development, HTTP with streaming for production
- **BigQuery Integration**: Execute SQL queries, browse datasets, and read table schemas
- **Authentication**: Optional API key and JWT token authentication
- **Streaming Support**: Server-Sent Events and WebSocket connections for real-time data
- **OpenAPI Documentation**: Auto-generated API specification
- **Azure Deployment**: Ready-to-deploy with Azure Container Apps
- **Health Monitoring**: Built-in health checks and monitoring endpoints

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development (stdio)](#local-development-stdio)
- [Azure Deployment (HTTP Streaming)](#azure-deployment-http-streaming)
- [Authentication](#authentication)
- [Testing with HTTP Requests](#testing-with-http-requests)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## 🔧 Prerequisites

### Google Cloud Setup

1. **Create a Google Cloud Project** or use an existing one
2. **Enable BigQuery API**:
   ```bash
   gcloud services enable bigquery.googleapis.com
   ```
3. **Create a Service Account**:
   ```bash
   gcloud iam service-accounts create mcp-bigquery-service --display-name="MCP BigQuery Service"
   ```
4. **Grant BigQuery permissions**:
   ```bash
   gcloud projects add-iam-policy-binding YOUR-PROJECT-ID \
     --member="serviceAccount:mcp-bigquery-service@YOUR-PROJECT-ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.jobUser"
   
   gcloud projects add-iam-policy-binding YOUR-PROJECT-ID \
     --member="serviceAccount:mcp-bigquery-service@YOUR-PROJECT-ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.dataViewer"
   ```
5. **Create and download service account key**:
   ```bash
   gcloud iam service-accounts keys create key.json \
     --iam-account=mcp-bigquery-service@YOUR-PROJECT-ID.iam.gserviceaccount.com
   ```

### Azure Prerequisites (for deployment)

- Azure subscription
- Azure CLI installed and authenticated
- Azure Developer CLI (azd) installed

## 🖥️ Local Development (stdio)

The stdio transport is perfect for local development and testing with MCP-compatible clients.

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd python-mcp-bigquery
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server with stdio transport**:
   ```bash
   python main.py --project-id YOUR-PROJECT-ID --key-file path/to/key.json
   ```

### stdio Usage Example

The server communicates via JSON-RPC over stdio. Here's how to test it:

```bash
# Start the server
python main.py --project-id bigquery-468015 --key-file ./key.json

# The server will read JSON-RPC requests from stdin and write responses to stdout
# Example request (send via stdin):
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test-client", "version": "1.0.0"}, "capabilities": {}}}
```

### Available MCP Methods

- `initialize` - Initialize the MCP session
- `tools/list` - List available tools (returns the "query" tool)
- `tools/call` - Execute SQL queries
- `resources/list` - List BigQuery datasets and tables
- `resources/read` - Read table schemas

## ☁️ Azure Deployment (HTTP Streaming)

Deploy the server to Azure Container Apps with HTTP transport and streaming capabilities.

### Setup Environment

1. **Copy the environment template**:
   ```bash
   cp .env.sample .env
   ```

2. **Configure your `.env` file**:
   ```bash
   # Azure Configuration
   AZURE_ENV_NAME=mcp-bigquery
   AZURE_LOCATION=centralus
   
   # Google Cloud Configuration
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account",...}
   
   # Authentication (optional)
   ENABLE_AUTH=true
   API_KEYS=your-secure-api-key-here
   ```

### Deploy to Azure

1. **Initialize azd** (first time only):
   ```bash
   azd init
   ```

2. **Deploy the application**:
   ```bash
   azd up
   ```

3. **Access your deployed server**:
   - The deployment will provide you with a URL like: `https://mcpbigquerypy-api-abc123.azurecontainerapps.io`
   - Health check: `GET /health`
   - API documentation: `GET /docs`
   - OpenAPI spec: `GET /openapi.yaml`

### Streaming Features

The HTTP deployment includes advanced streaming capabilities:

- **Server-Sent Events**: `/mcp/stream` endpoint for real-time updates
- **WebSocket**: `/mcp/ws` endpoint for bidirectional communication
- **Batch Processing**: `/mcp/batch` endpoint for multiple requests

## 🔐 Authentication

Authentication is optional but recommended for production deployments.

### Enable Authentication

Set `ENABLE_AUTH=true` in your `.env` file and choose your authentication method:

### Option 1: API Key Authentication (Recommended)

```bash
# Generate a secure API key
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Add to .env file
ENABLE_AUTH=true
API_KEYS=a1b2c3d4e5f6789012345678901234567890abcdef1234567890123456789012
```

**Usage**: Include the API key in the `X-API-Key` header:
```bash
curl -H "X-API-Key: your-api-key" https://your-server.com/mcp
```

### Option 2: JWT Token Authentication

```bash
# Generate a JWT secret
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"

# Add to .env file
ENABLE_AUTH=true
JWT_SECRET=your-super-secret-jwt-key-here
```

**Usage**: Include the JWT token in the `Authorization` header:
```bash
curl -H "Authorization: Bearer your-jwt-token" https://your-server.com/mcp
```

### Option 3: Both API Keys and JWT

```bash
ENABLE_AUTH=true
API_KEYS=your-api-key
JWT_SECRET=your-jwt-secret
```

### Endpoints That Require Authentication

- `POST /mcp` - MCP JSON-RPC requests
- `POST /mcp/batch` - Batch MCP requests
- `GET /mcp/stream` - Server-Sent Events
- `GET /mcp/ws` - WebSocket connections

**Note**: The `/health` endpoint is always public and doesn't require authentication.

## 🧪 Testing with HTTP Requests

Here are sample HTTP requests you can use to test your deployed server using PowerShell:

### Health Check

```powershell
Invoke-RestMethod -Uri "https://your-server.com/health" -Method Get
```

**Expected Response**:
```json
{
  "status": "healthy",
  "server": "mcp-bigquery",
  "version": "1.0.0"
}
```

### Initialize MCP Session

```powershell
$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key" = "your-api-key"
}

$body = @{
    jsonrpc = "2.0"
    id = 1
    method = "initialize"
    params = @{
        protocolVersion = "2024-11-05"
        clientInfo = @{
            name = "test-client"
            version = "1.0.0"
        }
        capabilities = @{}
    }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "https://your-server.com/mcp" -Method Post -Headers $headers -Body $body
```

### List Available Tools

```powershell
$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key" = "your-api-key"
}

$body = @{
    jsonrpc = "2.0"
    id = 2
    method = "tools/list"
    params = @{}
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://your-server.com/mcp" -Method Post -Headers $headers -Body $body
```

### Execute SQL Query

```powershell
$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key" = "your-api-key"
}

$body = @{
    jsonrpc = "2.0"
    id = 3
    method = "tools/call"
    params = @{
        name = "query"
        arguments = @{
            sql = "SELECT COUNT(*) as total_names FROM ``bigquery-public-data.usa_names.usa_1910_current`` LIMIT 1"
            maximumBytesBilled = "1000000000"
        }
    }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "https://your-server.com/mcp" -Method Post -Headers $headers -Body $body
```

**Expected Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"total_names\": 5647426}]"
      }
    ]
  }
}
```

### List BigQuery Resources

```powershell
$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key" = "your-api-key"
}

$body = @{
    jsonrpc = "2.0"
    id = 4
    method = "resources/list"
    params = @{}
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://your-server.com/mcp" -Method Post -Headers $headers -Body $body
```

### Batch Request Example

```powershell
$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key" = "your-api-key"
}

$body = @{
    requests = @(
        @{
            jsonrpc = "2.0"
            id = 1
            method = "tools/list"
            params = @{}
        },
        @{
            jsonrpc = "2.0"
            id = 2
            method = "resources/list"
            params = @{}
        }
    )
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "https://your-server.com/mcp/batch" -Method Post -Headers $headers -Body $body
```

## 📚 API Documentation

### Interactive Documentation

Once deployed, visit these endpoints:

- **Swagger UI**: `https://your-server.com/docs`
- **ReDoc**: `https://your-server.com/redoc` 
- **OpenAPI Spec**: `https://your-server.com/openapi.yaml`

### Streaming Endpoints

**Server-Sent Events**:
```javascript
const eventSource = new EventSource('https://your-server.com/mcp/stream');
eventSource.onmessage = function(event) {
  console.log('Received:', event.data);
};
```

**WebSocket**:
```javascript
const ws = new WebSocket('wss://your-server.com/mcp/ws');
ws.onmessage = function(event) {
  console.log('Received:', event.data);
};
ws.send(JSON.stringify({
  jsonrpc: "2.0",
  id: 1,
  method: "tools/list",
  params: {}
}));
```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | Yes | Google Cloud Project ID | `bigquery-468015` |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Yes | Service account JSON (single line) | `{"type":"service_account",...}` |
| `AZURE_ENV_NAME` | Yes (for deployment) | Unique environment name | `mcp-bigquery` |
| `AZURE_LOCATION` | Yes (for deployment) | Azure region | `centralus` |
| `ENABLE_AUTH` | No | Enable authentication | `true` or `false` |
| `API_KEYS` | No | Comma-separated API keys | `key1,key2` |
| `JWT_SECRET` | No | JWT signing secret | `your-secret-key` |

### Command Line Options

**stdio mode**:
```bash
python main.py --project-id PROJECT_ID --key-file PATH_TO_KEY.json [--port PORT]
```

**HTTP mode**:
```bash
python main.py --project-id PROJECT_ID --key-file PATH_TO_KEY.json --http [--port PORT]
```

## 🔧 Troubleshooting

### Common Issues

**1. BigQuery permissions error**
- Ensure your service account has `bigquery.jobUser` and `bigquery.dataViewer` roles
- Verify the service account JSON is properly formatted

**2. Authentication failures**
- Check that `ENABLE_AUTH=true` and API keys are set
- Verify the `X-API-Key` header is included in requests

**3. Azure deployment issues**
- Ensure all required environment variables are set in `.env`
- Check Azure subscription and CLI authentication
- Review deployment logs with `azd logs`

**4. stdio connection issues**
- Ensure proper JSON-RPC format in requests
- Check that the server is reading from stdin correctly

### Getting Help

- Check the server logs for detailed error messages
- Verify your Google Cloud setup and permissions
- Test with the health endpoint first: `GET /health`
- Use the interactive API documentation at `/docs`

## 📜 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please read the contributing guidelines and submit pull requests for any improvements.

---

**Need Help?** Check the troubleshooting section or open an issue in the repository.
