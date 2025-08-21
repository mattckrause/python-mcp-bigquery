# MCP BigQuery Server

A Model Context Protocol (MCP) server for Google BigQuery integration, providing secure access to BigQuery datasets via stdio or a simple REST API. Built with Python and FastAPI and deployable to Azure Container Apps.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Azure Container Apps](https://img.shields.io/badge/Azure-Container%20Apps-blue.svg)](https://azure.microsoft.com/products/container-apps)

## 🚀 Features

- Dual transport: stdio (for MCP clients) and HTTP (REST)
- BigQuery integration: query datasets and explore table schemas
- Azure Container Apps deployment with auto-scaling
- Authentication: API key via header (optional, dev-friendly toggle)
- OpenAPI docs: `/docs` and an OpenAPI 3.0.4 YAML at `/openapi.yaml`
- Health checks at `/health`

## 🏗️ Architecture

```text
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

- MCP server implementing the Model Context Protocol
- FastAPI-based REST layer for simple HTTP access
- Google Cloud BigQuery Python SDK client
- Docker container for Azure Container Apps
- Authentication layer: optional API key header

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

# Install dependencies (project uses standard Python packages)
pip install -r requirements.txt
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
## Google Cloud
# Project ID used by the server
GOOGLE_CLOUD_PROJECT=your-project-id
# Service account credentials (JSON string) all one line.
GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account",...}

## Azure (for deployment)
AZURE_ENV_NAME=mcp-bigquery
AZURE_LOCATION=centralus

## Authentication (optional)
# When true, all REST endpoints (except /health) require X-API-Key
ENABLE_AUTH=false
# Comma-separated list, e.g. key1,key2
API_KEYS=your-api-key-here
```

## 🏃‍♂️ Running the Server

### Local Development (stdio)

```powershell
# Run as MCP stdio server
python src/mcp_bigquery_server/main.py --project-id <project_id> --key-file <path_to_service_account_keyfile>
```

### Local HTTP Server (REST)

```powershell
# Run HTTP server (reads GOOGLE_APPLICATION_CREDENTIALS_JSON when set)
python src/mcp_bigquery_server/main.py --project-id <project_id> --http --port 8000

# Server runs on http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Docker (Local)

```powershell
# Build container
docker build -t mcp-bigquery-server .

# Run container
docker run -p 8000:8000 --env-file .env mcp-bigquery-server
```

## ☁️ Azure Deployment

```powershell
# Run preprovision script to set up Azure variables
./proprovision.ps1

# Initialize Azure environment (first time only)
azd init

# Deploy to Azure
azd up
# you need to select the Azure Subscription and Resource Group as part of the deployment.
```

The deployment will:

1. Create Azure resources (Key Vault, ACR, Container Apps)
2. Build and push the Docker image
3. Deploy the Container App with environment variables and secrets

### Accessing Your Deployed API

After deployment, `azd` will provide your Container Apps URL:

```text
https://your-app.kindriverbank-12345678.centralus.azurecontainerapps.io
```

**REST Endpoints**:

- `GET /health` - Health check (public)
- `POST /query` - Execute read-only BigQuery SQL
- `GET /resources` - List BigQuery resources (datasets/tables)
- `GET /resources/read?uri=bigquery://project/dataset/table/schema` - Read schema/content
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /openapi.yaml` - OpenAPI 3.0.4 specification (authoritative)

## 🔧 Configuration Options

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | Yes | Google Cloud project ID | - |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Yes | Service account JSON or base64 of JSON | - |
| `AZURE_ENV_NAME` | For deployment | Azure environment name | `mcp-bigquery` |
| `AZURE_LOCATION` | For deployment | Azure region | `centralus` |
| `ENABLE_AUTH` | No | Enable API key authentication | `false` |
| `API_KEYS` | If auth enabled | Comma-separated API keys | - |
| `PORT` | No | HTTP server port | `8000` |
| `HOST` | No | HTTP server host | `0.0.0.0` |

### Authentication

No Authentication (Development)

```bash
ENABLE_AUTH=false
```

API Key Authentication (header only)

```bash
ENABLE_AUTH=true
API_KEYS=key1,key2,key3
```

Usage

```powershell
$headers = @{ "X-API-Key" = "your-api-key"; "Content-Type" = "application/json" }
$body = '{"sql":"SELECT 1 AS x"}'
Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/query" -Method POST -Headers $headers -Body $body
```

## 📖 API Usage Examples (REST)

### Health Check

```powershell
# Check server health
$response = Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/health" -Method GET
Write-Output $response
# Output: {"status": "healthy", "timestamp": "2025-01-15T10:30:00Z"}
```

### Run a SQL Query

```powershell
$headers = @{ "X-API-Key" = "your-api-key"; "Content-Type" = "application/json" }
$body = '{"sql":"SELECT 1 AS x"}'
Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/query" -Method POST -Headers $headers -Body $body
```

### List Resources

```powershell
$headers = @{ "X-API-Key" = "your-api-key" }
Invoke-RestMethod -Uri "https://your-app.azurecontainerapps.io/resources" -Method GET -Headers $headers
```

### Read a Resource (Schema)

```powershell
$headers = @{ "X-API-Key" = "your-api-key" }
$uri = "https://your-app.azurecontainerapps.io/resources/read?uri=bigquery://your-project/your_dataset/your_table/schema"
Invoke-RestMethod -Uri $uri -Method GET -Headers $headers
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

### Local Development (HTTP)

```powershell
python src/mcp_bigquery_server/main.py --project-id <project_id> --http --port 8000
```

## 📚 Documentation

- API documentation: `/docs`
- OpenAPI specification (3.0.4 YAML): `/openapi.yaml`
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
