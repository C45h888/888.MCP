"""
MCP Server - Message & Compute Protocol Server

FastAPI-based HTTP gateway for the MCP message bus.
Provides validation, publishing, and health check endpoints.

NOT to be confused with Anthropic's Model Context Protocol.
This is a CUSTOM Redis-based pub/sub system.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, status, Header, Depends, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
import jsonschema
from jsonschema import validate, ValidationError as JSONSchemaValidationError

from .redis_client import RedisClient
from .retrieval import retrieve_historical_data, is_retrieval_enabled, MAX_RETRIEVE_LIMIT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Message & Compute Protocol Server for Agentic Trading System",
    version="1.0.0"
)

# Environment variables
MCP_DEV = os.getenv("MCP_DEV", "").lower() == "true"
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

# Initialize Redis client
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = RedisClient(REDIS_URL)

# Load JSON schemas
SCHEMA_DIR = Path(__file__).parent / "schemas" / "v1"
SCHEMAS: Dict[str, Dict[str, Any]] = {}


def load_schemas() -> None:
    """Load all v1 JSON schemas from the schemas/v1 directory."""
    global SCHEMAS

    schema_files = {
        "market:data": "market.schema.json",
        "sentiment:data": "sentiment.schema.json",
        "agent:control": "control.schema.json",
        "agent:signal": "signal.schema.json"
    }

    for channel, filename in schema_files.items():
        schema_path = SCHEMA_DIR / filename
        try:
            with open(schema_path, 'r') as f:
                SCHEMAS[channel] = json.load(f)
            logger.info(f"Loaded schema for {channel}")
        except Exception as e:
            logger.error(f"Failed to load schema {filename}: {e}")
            raise


# Load schemas on startup
load_schemas()


# Authentication dependency
async def verify_api_key(x_api_key: str = Header(None)) -> None:
    """
    Verify API key for production mode.

    In dev mode (MCP_DEV=true), authentication is bypassed.
    In production, requires x-api-key header matching MCP_API_KEY env var.

    Args:
        x_api_key: API key from x-api-key header

    Raises:
        HTTPException: 401 if authentication fails
    """
    if MCP_DEV:
        return  # Skip auth in dev mode

    if not MCP_API_KEY or x_api_key != MCP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )


# Pydantic models for request/response
class PublishRequest(BaseModel):
    """Request model for publishing messages."""
    channel: str
    message: Dict[str, Any]


class PublishResponse(BaseModel):
    """Response model for publish operations."""
    success: bool
    channel: str
    subscriber_count: int
    timestamp: int


class StatusResponse(BaseModel):
    """Response model for status checks."""
    status: str
    redis_connected: bool
    kill_switch: Dict[str, Any]
    channels: Dict[str, int]
    timestamp: int


class CollectionsResponse(BaseModel):
    """Response model for listing available channels."""
    channels: List[str]
    total: int


class RetrieveRequest(BaseModel):
    """Request model for historical data retrieval."""
    collection: str
    pair: Optional[str] = None
    from_timestamp: Optional[int] = None
    to_timestamp: Optional[int] = None
    limit: int = 100


class SearchRAGRequest(BaseModel):
    """Request model for RAG search."""
    query: str
    k: int = 5


# Endpoints

@app.get("/.well-known/mcp", response_model=Dict[str, Any])
async def mcp_info():
    """
    MCP Server information endpoint.

    Returns server metadata and available channels.
    """
    return {
        "name": "MCP Trading Server",
        "version": "1.0.0",
        "type": "custom-redis-pubsub",
        "description": "Message & Compute Protocol for Agentic Trading System",
        "channels": list(RedisClient.VALID_CHANNELS),
        "endpoints": {
            "publish": "/tool/publish",
            "list_channels": "/tool/list_collections",
            "status": "/tool/get_status"
        },
        "architecture": {
            "feeder_agent": "n8n - data ingestion",
            "mcp_server": "Redis pub/sub message bus",
            "brain_agent": "Python - statistical/ML trading"
        }
    }


@app.post("/tool/publish", response_model=PublishResponse, status_code=status.HTTP_200_OK, dependencies=[Depends(verify_api_key)])
async def publish_message(request: PublishRequest):
    """
    Publish a message to an MCP channel.

    Validates schema_version and message against the channel's JSON schema before publishing.
    Requires authentication in production mode (x-api-key header).

    Args:
        request: PublishRequest with channel and message

    Returns:
        PublishResponse with success status and subscriber count

    Raises:
        HTTPException: If validation fails or channel is invalid
    """
    channel = request.channel
    message = request.message

    # Validate channel exists
    if channel not in RedisClient.VALID_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel '{channel}'. Valid channels: {list(RedisClient.VALID_CHANNELS)}"
        )

    # Validate schema_version field
    message_version = message.get("schema_version")
    if message_version != "v1":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or missing schema_version. Expected 'v1', got '{message_version}'"
        )

    # Validate message against schema
    schema = SCHEMAS.get(channel)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema not found for channel '{channel}'"
        )

    try:
        validate(instance=message, schema=schema)
    except JSONSchemaValidationError as e:
        logger.warning(f"Schema validation failed for {channel}: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Message validation failed: {e.message}"
        )

    # Publish to Redis
    try:
        subscriber_count = redis_client.publish(channel, message)
    except Exception as e:
        logger.error(f"Failed to publish message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish message: {str(e)}"
        )

    return PublishResponse(
        success=True,
        channel=channel,
        subscriber_count=subscriber_count,
        timestamp=int(datetime.now().timestamp())
    )


@app.get("/tool/list_collections", response_model=CollectionsResponse)
async def list_collections():
    """
    List all available MCP channels.

    Returns:
        CollectionsResponse with channel names
    """
    channels = list(RedisClient.VALID_CHANNELS)
    return CollectionsResponse(
        channels=channels,
        total=len(channels)
    )


@app.get("/tool/get_status", response_model=StatusResponse, dependencies=[Depends(verify_api_key)])
async def get_status():
    """
    Get MCP server status and health information.
    Requires authentication in production mode (x-api-key header).

    Returns:
        StatusResponse with Redis health, kill-switch status, and channel info
    """
    redis_connected = redis_client.health_check()
    kill_switch = redis_client.get_kill_switch_status()
    channels = redis_client.get_channel_info()

    server_status = "healthy" if redis_connected else "degraded"
    if kill_switch.get("active"):
        server_status = "EMERGENCY_HALT"

    return StatusResponse(
        status=server_status,
        redis_connected=redis_connected,
        kill_switch=kill_switch,
        channels=channels,
        timestamp=int(datetime.now().timestamp())
    )


@app.post("/tool/retrieve")
async def retrieve(
    request: Request,
    retrieve_request: RetrieveRequest
):
    """
    Retrieve historical messages from S3 storage.

    Requires S3_DATA_BUCKET configuration. Returns 501 if not configured.
    Enforces pagination limits and timestamp filtering for safety.

    Args:
        request: FastAPI Request object
        retrieve_request: Retrieval parameters

    Returns:
        Dict with messages array and metadata

    Raises:
        HTTPException: 501 if S3 not configured, 400 for invalid params, 500 for errors
    """
    # Check if retrieval is enabled
    if not is_retrieval_enabled():
        logger.warning("Retrieval attempted but S3 not configured")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Historical data retrieval not configured. Set S3_DATA_BUCKET and AWS credentials."
        )

    # Validate collection
    if retrieve_request.collection not in RedisClient.VALID_CHANNELS:
        logger.warning(f"Invalid collection for retrieval: {retrieve_request.collection}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid collection. Must be one of: {list(RedisClient.VALID_CHANNELS)}"
        )

    # Enforce limit cap
    if retrieve_request.limit > MAX_RETRIEVE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limit exceeds maximum allowed ({MAX_RETRIEVE_LIMIT})"
        )

    try:
        messages = retrieve_historical_data(
            collection=retrieve_request.collection,
            pair=retrieve_request.pair,
            from_timestamp=retrieve_request.from_timestamp,
            to_timestamp=retrieve_request.to_timestamp,
            limit=retrieve_request.limit
        )

        logger.info(
            f"Retrieval successful: {len(messages)} messages",
            extra={
                'collection': retrieve_request.collection,
                'count': len(messages)
            }
        )

        return {
            "messages": messages,
            "count": len(messages),
            "collection": retrieve_request.collection,
            "filters": {
                "pair": retrieve_request.pair,
                "from_timestamp": retrieve_request.from_timestamp,
                "to_timestamp": retrieve_request.to_timestamp,
                "limit": retrieve_request.limit
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {str(e)}"
        )


@app.post("/tool/search_rag")
async def search_rag(
    request: Request,
    search_request: SearchRAGRequest
):
    """
    Search RAG knowledge base (placeholder for future vector DB integration).

    Currently returns 501 Not Implemented. This endpoint is reserved for
    future integration with vector databases (Pinecone, Weaviate, etc.) for
    semantic search over historical market data and sentiment.

    Args:
        request: FastAPI Request object
        search_request: Search parameters (query, k)

    Returns:
        501 Not Implemented
    """
    logger.info(
        f"RAG search attempted (not yet implemented): {search_request.query}"
    )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="RAG search not yet implemented. Future integration planned for vector database (Pinecone/Weaviate)."
    )


@app.get("/health", include_in_schema=False)
async def health():
    """
    Minimal unauthenticated health check for platform probes.

    Used by Render.com and other platforms for liveness checks.
    Does NOT expose secrets, internal metrics, or require authentication.
    For detailed status, use /tool/get_status (requires auth).

    Returns:
        Dict with minimal health info: status, time (UTC ISO), archiver_enabled
    """
    archive_enabled = os.getenv("ARCHIVE_ENABLED", "false").lower() == "true"
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "archiver_enabled": str(archive_enabled).lower()
    }


# Lifecycle events

@app.on_event("startup")
async def startup_event():
    """Run on server startup."""
    logger.info("MCP Server starting...")
    logger.info(f"Connected to Redis at {REDIS_URL}")
    logger.info(f"Loaded {len(SCHEMAS)} channel schemas")
    logger.info("MCP Server ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown."""
    logger.info("MCP Server shutting down...")
    redis_client.close()
    logger.info("MCP Server stopped")


# Error handlers

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    # Note: When running as a package, use "mcp.server:app"
    # This __main__ block is for local development only
    uvicorn.run(
        "mcp.server:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
