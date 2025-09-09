import json
import logging
import os
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Authentication configuration (JWT disabled; using only X-API-Key header)
# Keeping HTTPBearer import to avoid breaking changes, but not used.


def get_auth_config() -> Dict[str, Any]:
    return {
        "enable_auth": os.getenv("ENABLE_AUTH", "false").lower() == "true",
        "api_keys": set(k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()),
        "jwt_secret": os.getenv("JWT_SECRET", ""),
    }


def validate_api_key(api_key: str) -> bool:
    return api_key in get_auth_config()["api_keys"]


def validate_jwt_token(token: str) -> bool:
    # JWT auth disabled
    return False


async def authenticate_request(request: Request) -> bool:
    auth = get_auth_config()
    if not auth["enable_auth"]:
        return True

    # API key in header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and validate_api_key(api_key_header):
        return True

    raise HTTPException(status_code=401, detail="Authentication required")


class HealthResponse(BaseModel):
    status: str = Field(default="healthy")
    server: str = Field(default="mcp-bigquery")
    version: str = Field(default="1.0.0")


class QueryRequest(BaseModel):
    sql: str = Field(..., description="Read-only BigQuery SQL")
    maximumBytesBilled: Optional[str] = Field(
        default=None, description="Maximum bytes billed (string). Default from server if omitted."
    )


class QueryResponse(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Query result rows")


class MCPStreamingHTTPServer:
    def __init__(self, mcp_server, host: str = "127.0.0.1", port: int = 8000):
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="MCP BigQuery Server",
            description="REST API for MCP (Model Context Protocol) BigQuery server.",
            version="1.0.0",
            contact={"name": "MCP BigQuery Server"},
            license_info={"name": "MIT"},
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.setup_routes()

    def setup_routes(self) -> None:
        @self.app.get("/health", response_model=HealthResponse, tags=["Health"])
        async def health_check() -> HealthResponse:
            return HealthResponse()

        @self.app.get("/openapi.yaml", tags=["Documentation"])
        async def get_openapi_yaml(request: Request):
            import yaml
            from fastapi.openapi.utils import get_openapi

            # Always use https in OpenAPI server URL
            base_url = str(request.base_url).rstrip("/")
            if base_url.startswith("http://"):
                base_url = "https://" + base_url[len("http://"):]

            def inject_auth(doc: dict) -> dict:
                try:
                    if not get_auth_config()["enable_auth"]:
                        return doc
                    components = doc.setdefault("components", {})
                    security_schemes = components.setdefault("securitySchemes", {})
                    security_schemes.setdefault(
                        "APIKeyHeader",
                        {"type": "apiKey", "in": "header", "name": "X-API-Key"}
                    )
                    # Protect REST endpoints
                    paths = doc.get("paths", {})
                    requirement = [{"APIKeyHeader": []}]
                    for p, m in [
                        ("/query", "post"),
                        ("/resources", "get"),
                        ("/resources/read", "get"),
                    ]:
                        op = paths.get(p, {}).get(m)
                        if isinstance(op, dict):
                            op["security"] = requirement
                    return doc
                except Exception as e:
                    logger.warning(f"Failed to inject auth into OpenAPI: {e}")
                    return doc

            def oas31_nullable_to_oas30(node):
                """Convert OpenAPI 3.1 nullable patterns to OpenAPI 3.0 style.
                - anyOf: [<T>, {type: null}] => T + nullable: true
                - type: [<T>, null] => type: T + nullable: true
                Works recursively across the document.
                """
                if isinstance(node, dict):
                    # Handle anyOf with null
                    any_of = node.get("anyOf")
                    if isinstance(any_of, list):
                        non_null = [s for s in any_of if not (isinstance(s, dict) and s.get("type") == "null")]
                        has_null = any(isinstance(s, dict) and s.get("type") == "null" for s in any_of)
                        if has_null and len(non_null) == 1 and isinstance(non_null[0], dict):
                            # Replace current node with non-null schema + nullable: true
                            converted = oas31_nullable_to_oas30(non_null[0].copy())
                            node.clear()
                            node.update(converted)
                            node["nullable"] = True

                    # Handle type arrays including null
                    t = node.get("type")
                    if isinstance(t, list):
                        non_null_types = [x for x in t if x != "null"]
                        if len(non_null_types) == 1 and len(non_null_types) != len(t):
                            node["type"] = non_null_types[0]
                            node["nullable"] = True

                    # Recurse
                    for k, v in list(node.items()):
                        node[k] = oas31_nullable_to_oas30(v)
                    return node
                elif isinstance(node, list):
                    return [oas31_nullable_to_oas30(x) for x in node]
                else:
                    return node

            schema = get_openapi(
                title=self.app.title,
                version=self.app.version,
                description=self.app.description,
                routes=self.app.routes,
            )
            # Force OpenAPI 3.0.4 for compatibility and remove 3.1-only fields
            schema["openapi"] = "3.0.4"
            schema.pop("jsonSchemaDialect", None)
            schema["servers"] = [{"url": base_url}]
            schema = inject_auth(schema)
            schema = oas31_nullable_to_oas30(schema)
            return Response(content=yaml.dump(schema, default_flow_style=False), media_type="application/x-yaml")

        @self.app.post(
            "/query",
            response_model=QueryResponse,
            tags=["SQL"],
            summary="Execute read-only SQL",
            description="Runs a read-only BigQuery query and returns rows.",
        )
        async def rest_query(req: QueryRequest, http_request: Request, auth: bool = Depends(authenticate_request)):
            try:
                args: Dict[str, Any] = {"sql": req.sql}
                if req.maximumBytesBilled is not None:
                    args["maximumBytesBilled"] = req.maximumBytesBilled
                # Reuse MCP tool handler logic
                result = await self.mcp_server.call_tool_handler("query", args)
                rows: List[Dict[str, Any]] = []
                if result and isinstance(result, list):
                    first = result[0]
                    text = getattr(first, "text", None)
                    if isinstance(text, str):
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, list):
                                rows = parsed
                        except json.JSONDecodeError:
                            pass
                return QueryResponse(rows=rows)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"REST /query error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get(
            "/resources",
            tags=["Resources"],
            summary="List resources",
            description="Lists available BigQuery resources (datasets and tables).",
        )
        async def rest_list_resources(http_request: Request, auth: bool = Depends(authenticate_request)):
            try:
                resource_list = await self.mcp_server.list_resources_handler()
                # Always return an object; never a top-level array
                return {
                    "resources": [
                        {"uri": r.uri, "mimeType": r.mimeType, "name": r.name}
                        for r in resource_list
                    ]
                }
            except Exception as e:
                logger.error(f"REST /resources error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get(
            "/resources/read",
            tags=["Resources"],
            summary="Read resource",
            description="Reads a resource by URI and returns its content. Provide ?uri=bigquery://project/dataset/table/schema",
        )
        async def rest_read_resource(uri: str, http_request: Request, auth: bool = Depends(authenticate_request)):
            if not uri:
                raise HTTPException(status_code=400, detail="Missing 'uri' query parameter")
            try:
                content = await self.mcp_server.read_resource_handler(uri)
                try:
                    parsed = json.loads(content)
                    # Wrap arrays to avoid top-level array responses
                    if isinstance(parsed, list):
                        return {"data": parsed}
                    # If parsed is an object, return as-is
                    return parsed
                except Exception:
                    return {"text": content}
            except Exception as e:
                logger.error(f"REST /resources/read error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def start(self) -> None:
        logger.info(f"Starting MCP BigQuery HTTP server on {self.host}:{self.port}")
        config = uvicorn.Config(app=self.app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


# For direct execution testing
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    print("HTTP server module loaded. Use main.py to start the server.")