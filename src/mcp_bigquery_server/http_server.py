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

# Authentication configuration
security = HTTPBearer(auto_error=False)


def get_auth_config() -> Dict[str, Any]:
    return {
        "enable_auth": os.getenv("ENABLE_AUTH", "false").lower() == "true",
        "api_keys": set(k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()),
        "jwt_secret": os.getenv("JWT_SECRET", ""),
    }


def validate_api_key(api_key: str) -> bool:
    return api_key in get_auth_config()["api_keys"]


def validate_jwt_token(token: str) -> bool:
    auth = get_auth_config()
    if not auth["jwt_secret"]:
        return False
    # Minimal check; use PyJWT in production
    return bool(token)


async def authenticate_request(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> bool:
    auth = get_auth_config()
    if not auth["enable_auth"]:
        return True

    # API key in header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and validate_api_key(api_key_header):
        return True

    # API key in query
    api_key_query = request.query_params.get("api_key")
    if api_key_query and validate_api_key(api_key_query):
        return True

    # Bearer JWT
    if credentials and validate_jwt_token(credentials.credentials):
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

            base_url = str(request.base_url).rstrip("/")

            def inject_auth(doc: dict) -> dict:
                try:
                    if not get_auth_config()["enable_auth"]:
                        return doc
                    components = doc.setdefault("components", {})
                    security_schemes = components.setdefault("securitySchemes", {})
                    security_schemes.setdefault("APIKeyHeader", {"type": "apiKey", "in": "header", "name": "X-API-Key"})
                    security_schemes.setdefault("APIKeyQuery", {"type": "apiKey", "in": "query", "name": "api_key"})
                    security_schemes.setdefault("BearerAuth", {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"})
                    # Protect REST endpoints
                    paths = doc.get("paths", {})
                    requirement_or = [{"APIKeyHeader": []}, {"APIKeyQuery": []}, {"BearerAuth": []}]
                    for p, m in [("/query", "post"), ("/resources", "get"), ("/resources/read", "get")]:
                        op = paths.get(p, {}).get(m)
                        if isinstance(op, dict):
                            op["security"] = requirement_or
                    return doc
                except Exception as e:
                    logger.warning(f"Failed to inject auth into OpenAPI: {e}")
                    return doc

            schema = get_openapi(
                title=self.app.title,
                version=self.app.version,
                description=self.app.description,
                routes=self.app.routes,
            )
            schema["servers"] = [{"url": base_url}]
            schema = inject_auth(schema)
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
                return [
                    {"uri": r.uri, "mimeType": r.mimeType, "name": r.name}
                    for r in resource_list
                ]
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
                    return json.loads(content)
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