"""
MCP BigQuery Server

A Model Context Protocol server that provides BigQuery integration capabilities.
"""

from .main import BigQueryMCPServer, ServerConfig, main

__version__ = "0.1.0"
__all__ = ["BigQueryMCPServer", "ServerConfig", "main"]