#!/usr/bin/env python3
import argparse
import base64
import json
import logging
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import anyio
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
from google.cloud import bigquery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServerConfig:
    """Configuration class for the BigQuery MCP server."""
    
    def __init__(
        self,
        project_id: str,
        location: str = "US",
        key_filename: Optional[str] = None,
        credentials_json: Optional[str] = None
    ):
        self.project_id = project_id
        self.location = location
        self.key_filename = key_filename
        self.credentials_json = credentials_json

async def validate_config(config: ServerConfig) -> None:
    """Validate the server configuration."""
    
    # Check if key file exists and is readable
    if config.key_filename:
        key_path = Path(config.key_filename).resolve()
        try:
            if not key_path.exists():
                raise FileNotFoundError(f"Key file not found: {key_path}")
            if not key_path.is_file():
                raise ValueError(f"Key file path is not a file: {key_path}")
            if not os.access(key_path, os.R_OK):
                raise PermissionError(f"Permission denied accessing key file: {key_path}")
            
            # Update config to use resolved path
            config.key_filename = str(key_path)
            
            # Validate file contents
            try:
                with open(key_path, 'r') as f:
                    key_data = json.load(f)
                
                # Basic validation of key file structure
                if (not key_data.get('type') or 
                    key_data['type'] != 'service_account' or 
                    not key_data.get('project_id')):
                    raise ValueError('Invalid service account key file format')
                    
            except json.JSONDecodeError:
                raise ValueError('Service account key file is not valid JSON')
                
        except Exception as error:
            logger.error(f'File access error: {error}')
            raise
    
    elif config.credentials_json:
        # Validate JSON credentials from environment variable
        try:
            key_data = json.loads(config.credentials_json)
            
            # Basic validation of credentials structure
            if (not key_data.get('type') or 
                key_data['type'] != 'service_account' or 
                not key_data.get('project_id')):
                raise ValueError('Invalid service account credentials format')
                
        except json.JSONDecodeError:
            raise ValueError('Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable')
    
    # Validate project ID format (basic check)
    if not re.match(r'^[a-z0-9-]+$', config.project_id):
        raise ValueError('Invalid project ID format')

def parse_args() -> ServerConfig:
    """Parse command line arguments and environment variables."""
    parser = argparse.ArgumentParser(
        description="MCP BigQuery Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --project-id my-project
  %(prog)s --project-id my-project --location EU --key-file /path/to/key.json
  %(prog)s --project-id my-project --http --port 8000
        """
    )
    
    parser.add_argument(
        '--project-id',
        required=True,
        help='Google Cloud Project ID'
    )
    
    parser.add_argument(
        '--location',
        default='US',
        help='BigQuery location/region (default: US)'
    )
    
    parser.add_argument(
        '--key-file',
        help='Path to service account key file'
    )
    
    # HTTP transport options
    parser.add_argument(
        '--http',
        action='store_true',
        help='Enable HTTP transport (instead of stdio)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='HTTP server port (default: 8000)'
    )
    
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='HTTP server host (default: 127.0.0.1)'
    )
    
    args = parser.parse_args()
    
    # Check for environment variables
    project_id = args.project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        parser.error("Missing required argument: --project-id or GOOGLE_CLOUD_PROJECT environment variable")
    
    # Try to get credentials from environment
    credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')

    # The credentials should be JSON; detect and handle base64, and validate private_key formatting early
    if credentials_json:
        decoded_bytes: Optional[bytes] = None
        # First try JSON directly
        try:
            parsed = json.loads(credentials_json)
            decoded_bytes = credentials_json.encode("utf-8")
            logger.info("Using JSON credentials from environment")
        except json.JSONDecodeError:
            # If not JSON, try strict base64 decode
            try:
                decoded_bytes = base64.b64decode(credentials_json, validate=True)
                parsed = json.loads(decoded_bytes)
                credentials_json = decoded_bytes.decode('utf-8')
                logger.info("Decoded base64-encoded credentials from environment")
            except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Invalid GOOGLE_APPLICATION_CREDENTIALS_JSON: not valid JSON or base64 ({e})")
                credentials_json = None
                parsed = None

        # If we have parsed JSON, validate service_account structure and private_key PEM formatting
        if parsed and isinstance(parsed, dict):
            if parsed.get('type') != 'service_account':
                logger.error("Credentials JSON 'type' must be 'service_account'")
            pk = parsed.get('private_key')
            if not pk or not isinstance(pk, str):
                logger.error("Credentials JSON missing 'private_key' or it's not a string")
            else:
                # Accept both escaped newlines (\n) and real newlines
                normalized = pk.replace('\\n', '\n')
                has_header = normalized.strip().startswith('-----BEGIN PRIVATE KEY-----')
                has_footer = normalized.strip().endswith('-----END PRIVATE KEY-----')
                if not (has_header and has_footer):
                    logger.error("Credentials private_key must include proper PEM header/footer: 'BEGIN PRIVATE KEY'/'END PRIVATE KEY'")
                # Ensure there is at least one newline between header and footer
                if '-----BEGIN PRIVATE KEY-----' in normalized and '-----END PRIVATE KEY-----' in normalized:
                    inner = normalized.strip()[len('-----BEGIN PRIVATE KEY-----'): -len('-----END PRIVATE KEY-----')]
                    if '\n' not in inner:
                        logger.error("Credentials private_key appears to be single-line without newlines; ensure newlines are preserved or use \\n escapes in JSON")
    
    config = ServerConfig(
        project_id=project_id,
        location=args.location,
        key_filename=args.key_file,
        credentials_json=credentials_json
    )
    
    # Store HTTP transport options
    config.use_http = args.http
    config.http_host = args.host
    config.http_port = args.port
    
    return config

class BigQueryMCPServer:
    """MCP Server implementation for BigQuery integration."""
    
    def __init__(self, config: ServerConfig):
        self.config = config
        self.bigquery_client = None
        self.resource_base_url = f"bigquery://{config.project_id}"
        self.schema_path = "schema"
        
        # Initialize MCP server
        self.server = Server("mcp-server/bigquery")
        self.setup_handlers()
    
    async def initialize_bigquery(self):
        """Initialize the BigQuery client."""
        try:
            logger.info(f"Initializing BigQuery with project ID: {self.config.project_id} and location: {self.config.location}")
            
            bigquery_config = {
                'project': self.config.project_id
            }
            
            if self.config.key_filename:
                logger.info(f"Using service account key file: {self.config.key_filename}")
                # Import google.auth for proper credential handling
                from google.oauth2 import service_account
                
                # Load credentials from service account key file
                credentials = service_account.Credentials.from_service_account_file(
                    self.config.key_filename
                )
                bigquery_config['credentials'] = credentials
                
            elif self.config.credentials_json:
                logger.info('Using service account credentials from environment variable')
                from google.oauth2 import service_account
                
                # Parse JSON credentials and create credentials object
                credentials_data = json.loads(self.config.credentials_json)
                # Normalize private_key newlines if they are escaped
                if isinstance(credentials_data, dict) and isinstance(credentials_data.get('private_key'), str):
                    pk = credentials_data['private_key']
                    credentials_data['private_key'] = pk.replace('\\n', '\n')
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_data
                )
                bigquery_config['credentials'] = credentials
                
            else:
                logger.info('Using default Google Cloud authentication')
            
            self.bigquery_client = bigquery.Client(**bigquery_config)
            
        except Exception as error:
            logger.error(f'BigQuery initialization error: {error}')
            raise
    
    def setup_handlers(self):
        """Set up MCP request handlers."""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[types.Resource]:
            """List all BigQuery resources (datasets and tables/views)."""
            try:
                logger.info('Fetching datasets...')
                datasets = list(self.bigquery_client.list_datasets())
                logger.info(f'Found {len(datasets)} datasets')
                
                resources = []
                
                for dataset in datasets:
                    logger.info(f'Processing dataset: {dataset.dataset_id}')
                    tables = list(self.bigquery_client.list_tables(dataset.reference))
                    logger.info(f'Found {len(tables)} tables and views in dataset {dataset.dataset_id}')
                    
                    for table in tables:
                        # Get the table metadata to check if it's a table or view
                        table_ref = self.bigquery_client.get_table(table.reference)
                        resource_type = 'view' if table_ref.table_type == 'VIEW' else 'table'
                        
                        # Construct proper URI - ensure it follows the bigquery://project/dataset/table/schema format
                        resource_uri = f"{self.resource_base_url}/{dataset.dataset_id}/{table.table_id}/{self.schema_path}"
                        
                        resources.append(types.Resource(
                            uri=resource_uri,
                            mimeType="application/json",
                            name=f'"{dataset.dataset_id}.{table.table_id}" {resource_type} schema'
                        ))
                
                logger.info(f'Total resources found: {len(resources)}')
                return resources
                
            except Exception as error:
                logger.error(f'Error in list_resources: {error}')
                raise
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific BigQuery resource (table/view schema)."""
            try:
                # Convert uri to string if it's not already
                uri_str = str(uri)
                parsed_url = urlparse(uri_str)
                path_components = parsed_url.path.strip('/').split('/')
                
                if len(path_components) != 3:
                    raise ValueError("Invalid resource URI format")
                
                dataset_id, table_id, schema = path_components
                
                if schema != self.schema_path:
                    raise ValueError("Invalid resource URI - expected schema path")
                
                # Get table metadata
                table_ref = self.bigquery_client.dataset(dataset_id).table(table_id)
                table = self.bigquery_client.get_table(table_ref)
                
                # Return schema fields as JSON
                schema_fields = [
                    {
                        'name': field.name,
                        'type': field.field_type,
                        'mode': field.mode,
                        'description': field.description
                    }
                    for field in table.schema
                ]
                
                return json.dumps(schema_fields, indent=2)
                
            except Exception as error:
                logger.error(f'Error in read_resource: {error}')
                raise
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List available tools."""
            return [
                types.Tool(
                    name="query",
                    description="Run a read-only BigQuery SQL query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string"},
                            "maximumBytesBilled": {
                                "type": "string",
                                "description": "Maximum bytes billed (default: 1GB)"
                            }
                        },
                        "required": ["sql"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls."""
            if name == "query":
                sql = arguments.get('sql', '')
                maximum_bytes_billed = arguments.get('maximumBytesBilled', '1000000000')
                
                # Validate read-only query
                forbidden_pattern = re.compile(
                    r'\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|MERGE|TRUNCATE|GRANT|REVOKE|EXECUTE|BEGIN|COMMIT|ROLLBACK)\b',
                    re.IGNORECASE
                )
                if forbidden_pattern.search(sql):
                    raise ValueError('Only READ operations are allowed')
                
                try:
                    # Qualify INFORMATION_SCHEMA queries
                    if 'INFORMATION_SCHEMA' in sql.upper():
                        sql = self.qualify_table_path(sql, self.config.project_id)
                    
                    # Configure and run query
                    job_config = bigquery.QueryJobConfig(
                        maximum_bytes_billed=int(maximum_bytes_billed)
                    )
                    
                    query_job = self.bigquery_client.query(
                        sql,
                        location=self.config.location,
                        job_config=job_config
                    )
                    
                    # Wait for job to complete and get results
                    results = query_job.result()
                    rows = [dict(row) for row in results]
                    
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(rows, indent=2, default=str)
                    )]
                    
                except Exception as error:
                    logger.error(f'Query execution error: {error}')
                    raise
            
            raise ValueError(f"Unknown tool: {name}")
        
        # Store handlers for HTTP server access
        self.list_resources_handler = handle_list_resources
        self.read_resource_handler = handle_read_resource
        self.list_tools_handler = handle_list_tools
        self.call_tool_handler = handle_call_tool
    
    def qualify_table_path(self, sql: str, project_id: str) -> str:
        """Qualify INFORMATION_SCHEMA table references with project ID."""
        # Match FROM INFORMATION_SCHEMA.TABLES or FROM dataset.INFORMATION_SCHEMA.TABLES
        unqualified_pattern = re.compile(
            r'FROM\s+(?:(\w+)\.)?INFORMATION_SCHEMA\.TABLES',
            re.IGNORECASE
        )
        
        def replace_match(match):
            dataset = match.group(1)
            if dataset:
                return f'FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.TABLES`'
            else:
                raise ValueError("Dataset must be specified when querying INFORMATION_SCHEMA (e.g. dataset.INFORMATION_SCHEMA.TABLES)")
        
        return unqualified_pattern.sub(replace_match, sql)
    
    async def run_stdio(self):
        """Run the server with stdio transport."""
        try:
            # Use stdin/stdout for MCP communication
            from mcp.server.stdio import stdio_server
            
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="mcp-server/bigquery",
                        server_version="0.1.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
        except Exception as error:
            logger.error(f'Stdio server error: {error}')
            raise
    
    async def run_http(self):
        """Run the server with HTTP transport."""
        try:
            # Import HTTP server here to avoid import issues if not needed
            from .http_server import MCPStreamingHTTPServer
            
            http_server = MCPStreamingHTTPServer(self, self.config.http_host, self.config.http_port)
            await http_server.start()
            
        except ImportError:
            # Fallback import for direct execution
            import sys
            import os
            sys.path.append(os.path.dirname(__file__))
            
            from http_server import MCPStreamingHTTPServer
            
            http_server = MCPStreamingHTTPServer(self, self.config.http_host, self.config.http_port)
            await http_server.start()
        
        except Exception as error:
            logger.error(f'HTTP server error: {error}')
            raise

async def main():
    """Main entry point."""
    try:
        # Parse configuration
        config = parse_args()
        await validate_config(config)
        
        # Create and initialize server
        server = BigQueryMCPServer(config)
        await server.initialize_bigquery()
        
        # Run server based on transport mode
        if getattr(config, 'use_http', False):
            logger.info("Starting MCP BigQuery server with HTTP transport")
            await server.run_http()
        else:
            logger.info("Starting MCP BigQuery server with stdio transport")
            await server.run_stdio()
            
    except Exception as error:
        logger.error(f'Server error: {error}')
        sys.exit(1)

if __name__ == "__main__":
    anyio.run(main)