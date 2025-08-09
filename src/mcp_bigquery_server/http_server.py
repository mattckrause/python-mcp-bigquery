"""
HTTP Transport for MCP BigQuery Server

Provides FastAPI-based HTTP endpoints for the MCP protocol including:
- REST API endpoints
- WebSocket support  
- Server-Sent Events streaming
"""

import json
import logging
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

# Pydantic models for request/response validation
class MCPRequest(BaseModel):
    """MCP JSON-RPC request model."""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version (must be '2.0')")
    id: Optional[Any] = Field(None, description="Request ID (can be string, number, or null)")
    method: str = Field(..., description="MCP method name", 
                       examples=["initialize", "resources/list", "resources/read", "tools/list", "tools/call"])
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Method-specific parameters")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "my-app", "version": "1.0.0"}
                    }
                },
                {
                    "jsonrpc": "2.0", 
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "query",
                        "arguments": {
                            "sql": "SELECT COUNT(*) FROM `bigquery-public-data.usa_names.usa_1910_current`"
                        }
                    }
                }
            ]
        }
    }

class MCPResponse(BaseModel):
    """MCP JSON-RPC response model."""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[Any] = Field(None, description="Request ID matching the request")
    result: Optional[Any] = Field(None, description="Success result data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error information (code, message, data)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "mcp-server/bigquery", "version": "0.1.0"}
                    }
                },
                {
                    "jsonrpc": "2.0",
                    "id": 2, 
                    "result": {
                        "content": [{"type": "text", "text": '[{"count": 42}]'}]
                    }
                }
            ]
        }
    }

class MCPBatchRequest(BaseModel):
    """MCP batch request model."""
    requests: List[MCPRequest] = Field(..., description="List of MCP requests to execute", min_length=1)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "requests": [
                    {
                        "jsonrpc": "2.0",
                        "id": 1, 
                        "method": "tools/list",
                        "params": {}
                    },
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "resources/list", 
                        "params": {}
                    }
                ]
            }
        }
    }

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(default="healthy", description="Server health status")
    server: str = Field(default="mcp-bigquery", description="Server name")
    version: str = Field(default="1.0.0", description="Server version")

class MCPStreamingHTTPServer:
    """HTTP server implementation for MCP BigQuery server."""
    
    def __init__(self, mcp_server, host: str = "127.0.0.1", port: int = 8000):
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="MCP BigQuery Server",
            description="""
            HTTP transport for MCP (Model Context Protocol) BigQuery server with streaming support.
            
            This API provides access to Google BigQuery through the Model Context Protocol,
            allowing you to execute SQL queries, browse datasets, and read table schemas.
            
            ## MCP Methods
            
            - **initialize** - Initialize MCP session
            - **resources/list** - List available BigQuery datasets and tables  
            - **resources/read** - Read table schema information
            - **tools/list** - List available tools (query tool)
            - **tools/call** - Execute SQL queries against BigQuery
            
            ## Authentication
            
            The server uses Google Cloud service account authentication configured at startup.
            
            ## Query Safety
            
            All SQL queries are validated to ensure only read-only operations (SELECT statements) are allowed.
            """,
            version="1.0.0",
            contact={
                "name": "MCP BigQuery Server",
            },
            license_info={
                "name": "MIT",
            },
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.setup_routes()
        self.active_connections: List[WebSocket] = []
    
    def setup_routes(self):
        """Set up HTTP routes."""
        
        @self.app.get("/health", response_model=HealthResponse, tags=["Health"])
        async def health_check():
            """Health check endpoint."""
            return HealthResponse()
        
        @self.app.get("/openapi.yaml", tags=["Documentation"])
        async def get_openapi_yaml():
            """Serve OpenAPI specification in YAML format."""
            import yaml
            from pathlib import Path
            
            # Try to read the OpenAPI spec file
            openapi_file = Path(__file__).parent.parent.parent / "openapi.yaml"
            if openapi_file.exists():
                return Response(
                    content=openapi_file.read_text(),
                    media_type="application/x-yaml"
                )
            else:
                # Fallback to FastAPI's built-in OpenAPI
                from fastapi.openapi.utils import get_openapi
                openapi_schema = get_openapi(
                    title=self.app.title,
                    version=self.app.version,
                    description=self.app.description,
                    routes=self.app.routes,
                )
                return Response(
                    content=yaml.dump(openapi_schema, default_flow_style=False),
                    media_type="application/x-yaml"
                )
        
        @self.app.post("/mcp", 
                      response_model=MCPResponse, 
                      tags=["MCP"],
                      summary="Execute MCP JSON-RPC request",
                      description="""
                      Execute Model Context Protocol commands via JSON-RPC over HTTP.
                      
                      **Supported MCP methods:**
                      - `initialize` - Initialize MCP session
                      - `resources/list` - List available BigQuery datasets and tables
                      - `resources/read` - Read table schema information  
                      - `tools/list` - List available tools (query tool)
                      - `tools/call` - Execute SQL queries against BigQuery
                      """)
        async def handle_mcp_request(request: MCPRequest):
            """Handle MCP JSON-RPC requests via HTTP POST."""
            try:
                response_data = await self.process_mcp_request(request.dict())
                return MCPResponse(**response_data)
            except Exception as e:
                logger.error(f"Error processing MCP request: {e}")
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                )
        
        @self.app.post("/mcp/batch", tags=["MCP"])
        async def handle_mcp_batch(batch_request: MCPBatchRequest):
            """Handle batch MCP requests."""
            try:
                responses = []
                for req in batch_request.requests:
                    response_data = await self.process_mcp_request(req.dict())
                    responses.append(MCPResponse(**response_data))
                return responses
            except Exception as e:
                logger.error(f"Error processing batch MCP request: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/mcp/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """
            WebSocket endpoint for real-time MCP communication.
            
            Establish a WebSocket connection for bidirectional MCP JSON-RPC communication.
            Send MCP requests and receive responses in real-time.
            
            **Usage:**
            1. Connect to `ws://localhost:8000/mcp/ws`
            2. Send MCP JSON-RPC messages as text
            3. Receive MCP responses as JSON text
            """
            await websocket.accept()
            self.active_connections.append(websocket)
            
            try:
                while True:
                    # Receive MCP request from WebSocket
                    data = await websocket.receive_text()
                    request_data = json.loads(data)
                    
                    # Process MCP request
                    response_data = await self.process_mcp_request(request_data)
                    
                    # Send response back through WebSocket
                    await websocket.send_text(json.dumps(response_data))
                    
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.active_connections.remove(websocket)
        
        @self.app.get("/mcp/stream", tags=["Streaming"])
        async def stream_endpoint():
            """
            Server-Sent Events endpoint for streaming MCP responses.
            
            Establish a Server-Sent Events connection for streaming responses.
            Useful for long-running queries or real-time updates.
            
            **Usage:**
            - Connect to GET /mcp/stream
            - Receive events in text/event-stream format
            - Events include connection status and streaming data
            """
            async def event_generator():
                # This is a basic implementation - you can extend this
                # to stream query results or other long-running operations
                yield {
                    "event": "connected",
                    "data": json.dumps({"message": "Stream connected"})
                }
            
            return EventSourceResponse(event_generator())
    
    async def process_mcp_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an MCP request and return the response."""
        try:
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "resources/list":
                result = await self.handle_list_resources()
            elif method == "resources/read":
                result = await self.handle_read_resource(params)
            elif method == "tools/list":
                result = await self.handle_list_tools()
            elif method == "tools/call":
                result = await self.handle_call_tool(params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error processing MCP request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
    
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "resources": {
                    "subscribe": False,
                    "listChanged": False
                },
                "tools": {},
                "prompts": {}
            },
            "serverInfo": {
                "name": "mcp-server/bigquery",
                "version": "0.1.0"
            }
        }
    
    async def handle_list_resources(self) -> Dict[str, Any]:
        """Handle resources/list request."""
        # Get the handler from the MCP server
        resources = []
        try:
            # Call the server's list_resources handler
            resource_list = await self.mcp_server.list_resources_handler()
            resources = [
                {
                    "uri": resource.uri,
                    "mimeType": resource.mimeType,
                    "name": resource.name
                }
                for resource in resource_list
            ]
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            raise
        
        return {"resources": resources}
    
    async def handle_read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Missing required parameter: uri")
        
        try:
            # Call the server's read_resource handler
            content = await self.mcp_server.read_resource_handler(uri)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": content
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            raise
    
    async def handle_list_tools(self) -> Dict[str, Any]:
        """Handle tools/list request."""
        try:
            # Call the server's list_tools handler
            tool_list = await self.mcp_server.list_tools_handler()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                for tool in tool_list
            ]
            return {"tools": tools}
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise
    
    async def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not name:
            raise ValueError("Missing required parameter: name")
        
        try:
            # Call the server's call_tool handler
            result = await self.mcp_server.call_tool_handler(name, arguments)
            return {
                "content": [
                    {
                        "type": content.type,
                        "text": content.text
                    }
                    for content in result
                ]
            }
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            raise
    
    async def start(self):
        """Start the HTTP server."""
        logger.info(f"Starting MCP BigQuery HTTP server on {self.host}:{self.port}")
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()

# For direct execution testing
if __name__ == "__main__":
    import sys
    import os
    
    # Add parent directory to path for imports
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    # This would need the main server to be initialized
    print("HTTP server module loaded. Use main.py to start the server.")