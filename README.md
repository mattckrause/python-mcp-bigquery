# MCP BigQuery Server

A **Model Context Protocol (MCP) server** for Google BigQuery integration, providing secure access to BigQuery datasets through both stdio and HTTP transports. Built with Python, FastAPI, and deployed on Azure Container Apps.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Azure Container Apps](https://img.shields.io/badge/Azure-Container%20Apps-blue.svg)](https://azure.microsoft.com/products/container-apps)

## 🚀 Features

- **Dual Transport Support**: Both stdio (for local MCP clients) and HTTP/WebSocket (for web applications)
- **Google BigQuery Integration**: Query datasets, explore schemas, and manage BigQuery resources
- **Azure Container Apps Deployment**: Production-ready containerized deployment with auto-scaling
- **Authentication Options**: API keys, JWT tokens, or no authentication for development
- **Real-time Streaming**: Server-Sent Events (SSE) and WebSocket support for live data feeds
- **OpenAPI Documentation**: Auto-generated API docs at `/docs` and `/openapi.json`
- **Health Monitoring**: Built-in health checks and observability

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │────│  MCP BigQuery    │────│  Google Cloud   │
│  (stdio/HTTP)   │    │     Server       │    │    BigQuery     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────────────────┐
                       │ Azure Container  │
                       │      Apps        │
                       └──────────────────┘
```

**Components:**
- **MCP Server**: Implements the Model Context Protocol specification
- **HTTP Server**: FastAPI-based REST API with streaming endpoints
- **BigQuery Client**: Google Cloud BigQuery Python SDK integration
- **Container Runtime**: Docker container deployed on Azure Container Apps
- **Authentication Layer**: Optional API key and JWT token validation

## 📋 Prerequisites

### For Local Development
- **Python 3.8+**
- **Google Cloud Project** with BigQuery API enabled
- **Service Account** with BigQuery permissions (Job User, Data Viewer)

### For Azure Deployment
- **Azure CLI** (`az`) installed and authenticated
- **Azure Developer CLI** (`azd`) installed
- **Docker Desktop** (for container building)
- **GitHub Account** (if using CI/CD)

## 🛠️ Installation & Setup

### 1. Clone and Setup Environment

```powershell
# Clone the repository
git clone https://github.com/mattckrause/python-mcp-bigquery.git
cd python-mcp-bigquery

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate    # Linux/macOS

# Install dependencies
pip install -e .
```

### 2. Google Cloud Configuration

1. **Enable BigQuery API**:
   ```powershell
   gcloud services enable bigquery.googleapis.com
   ```

2. **Create Service Account**:
   ```powershell
   gcloud iam service-accounts create mcp-bigquery-server \
     --description="Service account for MCP BigQuery Server" \
     --display-name="MCP BigQuery Server"
   ```

3. **Assign Permissions**:
   ```powershell
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:mcp-bigquery-server@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.jobUser"
   
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:mcp-bigquery-server@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.dataViewer"
   ```

4. **Download Credentials**:
   ```powershell
   gcloud iam service-accounts keys create credentials.json \
     --iam-account=mcp-bigquery-server@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

### 3. Environment Configuration

```powershell
# Copy environment template
Copy-Item .env.sample .env

# Edit .env with your values
notepad .env
```

**Required Configuration**:
```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_SERVICE_ACCOUNT_CREDENTIALS={"type":"service_account",...}

# Azure (for deployment)
AZURE_ENV_NAME=mcp-bigquery
AZURE_LOCATION=centralus

# Authentication (optional)
ENABLE_AUTH=false
API_KEYS=your-api-key-here
JWT_SECRET=your-jwt-secret-here
```

## 🏃‍♂️ Running the Server

### Local Development (stdio)

```powershell
# Run as MCP stdio server
python -m mcp_bigquery_server.main

# Or use the installed command
mcp-bigquery
```

### Local HTTP Server

```powershell
# Install HTTP dependencies
pip install -e ".[http]"

# Run HTTP server
python -m mcp_bigquery_server.http_server

# Server runs on http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Docker (Local)

```powershell
# Build container
docker build -t mcp-bigquery-server .

# Run container
docker run -p 8000:8000 --env-file .env mcp-bigquery-server
```

## ☁️ Azure Deployment

### Quick Deploy

```powershell
# Initialize Azure environment (first time only)
azd init

# Deploy to Azure
azd up
```

The deployment will:
1. Create Azure Container Registry
2. Build and push Docker image
3. Create Container Apps environment
4. Deploy your application with auto-scaling
5. Configure environment variables from `.env`

### Manual Azure Resources

If you prefer manual setup:

```powershell
# Create resource group
az group create --name rg-mcp-bigquery --location centralus

# Create container registry
az acr create --resource-group rg-mcp-bigquery \
  --name mcpbigqueryregistry --sku Basic

# Create container apps environment
az containerapp env create \
  --name mcp-bigquery-env \
  --resource-group rg-mcp-bigquery \
  --location centralus
```

### Accessing Your Deployed API

After deployment, `azd` will provide your Container Apps URL:

```
https://your-app.kindriverbank-12345678.centralus.azurecontainerapps.io
```

**Endpoints**:
- `GET /health` - Health check (always public)
- `POST /mcp` - MCP protocol endpoint
- `POST /mcp/batch` - Batch MCP requests
- `GET /mcp/stream` - Server-Sent Events stream
- `GET /mcp/ws` - WebSocket connection
- `GET /docs` - Interactive API documentation
- `GET /openapi.json` - OpenAPI specification

## 🔧 Configuration Options

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT_ID` | Yes | Google Cloud project ID | - |
| `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS` | Yes | Service account JSON (single line) | - |
| `AZURE_ENV_NAME` | For deployment | Azure environment name | `mcp-bigquery` |
| `AZURE_LOCATION` | For deployment | Azure region | `centralus` |
| `ENABLE_AUTH` | No | Enable authentication | `false` |
| `API_KEYS` | If auth enabled | Comma-separated API keys | - |
| `JWT_SECRET` | For JWT auth | JWT signing secret | - |
| `PORT` | No | HTTP server port | `8000` |
| `HOST` | No | HTTP server host | `0.0.0.0` |

### Authentication Modes

#### 1. No Authentication (Development)
```bash
ENABLE_AUTH=false
```

#### 2. API Key Authentication
```bash
ENABLE_AUTH=true
API_KEYS=key1,key2,key3
```

**Usage**:
```powershell
# Header-based
$headers = @{ "X-API-Key" = "your-api-key" }
Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/mcp" -Method POST -Headers $headers -Body $body

# Query parameter
$uri = "https://your-app.azurecontainerapps.io/mcp?api_key=your-api-key"
```

#### 3. JWT Token Authentication
```bash
ENABLE_AUTH=true
JWT_SECRET=your-secret-key
```

**Usage**:
```powershell
$headers = @{ "Authorization" = "Bearer your-jwt-token" }
Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/mcp" -Method POST -Headers $headers -Body $body
```

## 📖 API Usage Examples

### Health Check

```powershell
# Check server health
$response = Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/health" -Method GET
Write-Output $response
# Output: {"status": "healthy", "timestamp": "2025-01-15T10:30:00Z"}
```

### MCP Query Example

```powershell
# Example MCP request
$body = @{
    jsonrpc = "2.0"
    id = 1
    method = "resources/list"
    params = @{}
} | ConvertTo-Json -Depth 10

$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key" = "your-api-key"  # If authentication enabled
}

$response = Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/mcp" -Method POST -Headers $headers -Body $body
Write-Output $response
```

### Streaming Data (SSE)

```powershell
# PowerShell SSE example (requires additional setup)
$uri = "https://your-app.azurecontainerapps.io/mcp/stream"
$headers = @{ "X-API-Key" = "your-api-key" }

# Use curl for SSE streaming
curl -H "X-API-Key: your-api-key" -H "Accept: text/event-stream" $uri
```

### WebSocket Connection

```javascript
// JavaScript WebSocket example
const ws = new WebSocket('wss://your-app.azurecontainerapps.io/mcp/ws?api_key=your-api-key');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};

ws.send(JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "resources/list",
    params: {}
}));
```

## 🔍 Monitoring & Troubleshooting

### Azure Logs

```powershell
# View application logs
azd logs

# Stream live logs
azd logs --follow

# View specific container logs
az containerapp logs show --name your-app --resource-group rg-mcp-bigquery
```

### Health Monitoring

The `/health` endpoint provides detailed status information:

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "bigquery_connection": "ok",
  "auth_enabled": false,
  "version": "0.1.0"
}
```

### Common Issues

1. **BigQuery Permission Errors**:
   - Verify service account has correct IAM roles
   - Check project ID matches your Google Cloud project

2. **Authentication Failures**:
   - Ensure API keys are properly formatted
   - Verify JWT secret is set if using JWT tokens

3. **Container Startup Issues**:
   - Check environment variables are properly set
   - Verify JSON credentials are formatted as single line

4. **Network Connectivity**:
   - Ensure BigQuery API is enabled
   - Check Azure Container Apps networking configuration

## 🧪 Development

### Running Tests

```powershell
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=mcp_bigquery_server
```

### Code Quality

```powershell
# Format code
black src/

# Lint code
flake8 src/

# Type checking
mypy src/
```

### Local Development with Hot Reload

```powershell
# Install development dependencies
pip install -e ".[http,dev]"

# Run with auto-reload
uvicorn mcp_bigquery_server.http_server:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Documentation

- **API Documentation**: Available at `/docs` when running the HTTP server
- **OpenAPI Specification**: Available at `/openapi.json`
- **Model Context Protocol**: [MCP Specification](https://modelcontextprotocol.io)
- **Google BigQuery API**: [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- **Azure Container Apps**: [Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/mattckrause/python-mcp-bigquery/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mattckrause/python-mcp-bigquery/discussions)
- **Documentation**: See `/docs` endpoint when running the server

---

**Built with ❤️ for the Model Context Protocol community**
