"""
MCP Server - Message & Compute Protocol Server

FastAPI-based HTTP gateway for the MCP message bus.
Provides validation, publishing, and health check endpoints.

NOT to be confused with Anthropic's Model Context Protocol.
This is a CUSTOM Redis-based pub/sub system.
"""

import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, status, Header, Depends, Request, Query
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
import jsonschema
from jsonschema import validate, ValidationError as JSONSchemaValidationError
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .redis_client import RedisClient
from .retrieval import retrieve_historical_data, is_retrieval_enabled, MAX_RETRIEVE_LIMIT
from .uploader.archiver import Archiver
from . import metrics
from .logging_config import setup_logging, set_request_id, clear_request_id, log_with_context
from .auth import APIKeyManager, has_permission
from .rate_limiter import RateLimiter, RateLimitExceeded, RateLimitConfig

# Configure structured JSON logging
logger = setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Message & Compute Protocol Server for Agentic Trading System",
    version="1.0.0"
)

# Configure CORS (Cross-Origin Resource Sharing)
# Optional: Enable only if needed for web clients
CORS_ENABLED = os.getenv("CORS_ENABLED", "false").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []

if CORS_ENABLED and CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["x-api-key", "content-type", "authorization"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )
    logger.info(f"CORS enabled for origins: {CORS_ORIGINS}")
elif CORS_ENABLED:
    # CORS enabled but no origins specified = allow all (DANGEROUS in production)
    logger.warning("CORS_ENABLED=true but CORS_ORIGINS not set. CORS will NOT be enabled for security.")
else:
    # CORS disabled (default, recommended)
    logger.info("CORS disabled (default). Set CORS_ENABLED=true and CORS_ORIGINS to enable.")

# Request ID middleware for tracing
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """
    Add unique request ID to each request for distributed tracing.

    The request ID is:
    - Generated as UUID4
    - Stored in request-scoped context
    - Included in all logs for that request
    - Returned in X-Request-ID response header
    """
    request_id = str(uuid.uuid4())
    set_request_id(request_id)

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        # Clear request ID after request completes
        clear_request_id()


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff (prevent MIME sniffing)
    - X-Frame-Options: DENY (prevent clickjacking)
    - X-XSS-Protection: 1; mode=block (XSS protection)
    - Strict-Transport-Security: HTTPS enforcement (31536000s = 1 year)
    """
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Remove server header (security through obscurity)
    response.headers.pop("Server", None)

    return response


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Global rate limiting middleware.

    Applies two layers of rate limiting:
    1. Per-IP global rate limit (prevent DoS)
    2. Per-endpoint specific rate limits (applied after per-IP check)

    Returns 429 Too Many Requests if rate limit exceeded.
    Adds X-RateLimit-* headers to all responses.
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Get API key from header (for per-key rate limiting)
    api_key = request.headers.get("x-api-key")

    # Check per-IP global rate limit
    ip_allowed, ip_headers = rate_limiter.check_rate_limit(
        f"ip:{client_ip}",
        rate_limit_config.global_ip
    )

    if not ip_allowed:
        # Track rate limit violation metric
        metrics.mcp_validation_failures_total.labels(
            channel="rate_limit",
            error_type="ip_limit_exceeded"
        ).inc()

        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded: {rate_limit_config.global_ip}",
                "retry_after": int(ip_headers.get("Retry-After", 60))
            },
            headers=ip_headers
        )

    # Check per-key global rate limit (if API key provided)
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        key_allowed, key_headers = rate_limiter.check_rate_limit(
            f"key:{key_hash}",
            rate_limit_config.global_key
        )

        if not key_allowed:
            # Track rate limit violation metric
            metrics.mcp_validation_failures_total.labels(
                channel="rate_limit",
                error_type="key_limit_exceeded"
            ).inc()

            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded: {rate_limit_config.global_key}",
                    "retry_after": int(key_headers.get("Retry-After", 60))
                },
                headers=key_headers
            )

    # Process request
    response = await call_next(request)

    # Add rate limit headers to response
    for key, value in ip_headers.items():
        if key.startswith("X-RateLimit-"):
            response.headers[key] = value

    return response

# Environment variables
MCP_DEV = os.getenv("MCP_DEV", "").lower() == "true"
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

# Initialize Redis client
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = RedisClient(REDIS_URL)

# Initialize API Key Manager (multi-key auth system)
api_key_manager = APIKeyManager(redis_client)

# Initialize Rate Limiter
rate_limiter = RateLimiter(redis_client)
rate_limit_config = RateLimitConfig()

# Initialize Archiver for S3 uploads
archiver = Archiver()

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
            log_with_context(logger, 'info', "Schema loaded successfully", channel=channel, filename=filename)
        except Exception as e:
            log_with_context(logger, 'error', "Failed to load schema", channel=channel, filename=filename, error=str(e))
            raise


# Load schemas on startup
load_schemas()


# Authentication dependencies

async def verify_api_key(x_api_key: str = Header(None)) -> Dict[str, Any]:
    """
    Verify API key using multi-key authentication system.

    Supports both:
    1. New multi-key system (mcp_<role>_<random>)
    2. Legacy MCP_API_KEY (backward compatibility)

    In dev mode (MCP_DEV=true), authentication is bypassed.

    Args:
        x_api_key: API key from x-api-key header

    Returns:
        Dict with key metadata (role, permissions, etc.)

    Raises:
        HTTPException: 401 if authentication fails
    """
    if MCP_DEV:
        # Dev mode: return admin permissions
        return {
            "role": "admin",
            "permissions": {"*"},
            "dev_mode": True
        }

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key"
        )

    # Try multi-key system first
    key_info = api_key_manager.validate_key(x_api_key)

    if key_info:
        # Update last used timestamp
        api_key_manager.touch_key(x_api_key)

        log_with_context(
            logger, 'debug', "API key validated",
            role=key_info["role"],
            key_suffix=key_info["key_suffix"]
        )

        return key_info

    # Fallback to legacy MCP_API_KEY for backward compatibility
    if MCP_API_KEY and x_api_key == MCP_API_KEY:
        log_with_context(logger, 'debug', "Legacy API key used")
        return {
            "role": "admin",
            "permissions": {"*"},
            "legacy": True
        }

    # Invalid key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked API key"
    )


def verify_permission(required_permission: str):
    """
    Create a dependency that verifies API key has required permission.

    Usage:
        @app.post("/tool/publish")
        async def publish(key_info: dict = Depends(verify_permission("publish:market:data"))):
            ...

    Args:
        required_permission: Permission string (e.g., "publish:market:data")

    Returns:
        Dependency function that validates permission
    """
    async def permission_checker(key_info: Dict[str, Any] = Depends(verify_api_key)) -> Dict[str, Any]:
        """Check if key has required permission."""
        if not has_permission(key_info, required_permission):
            log_with_context(
                logger, 'warning', "Permission denied",
                role=key_info.get("role"),
                required=required_permission
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_permission}"
            )
        return key_info

    return permission_checker


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


class KillHistoryResponse(BaseModel):
    """Response model for kill history retrieval."""
    events: List[Dict[str, Any]]
    count: int
    current_status: Dict[str, Any]


class CreateKeyRequest(BaseModel):
    """Request model for creating API keys."""
    role: str
    description: str


class CreateKeyResponse(BaseModel):
    """Response model for API key creation."""
    api_key: str
    key_hash: str
    role: str
    description: str
    created_at: int
    key_suffix: str
    warning: str = "Store this API key securely. It will not be shown again."


class RevokeKeyRequest(BaseModel):
    """Request model for revoking API keys."""
    api_key: str


class RotateKeyRequest(BaseModel):
    """Request model for rotating API keys."""
    old_api_key: str


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
            "status": "/tool/get_status",
            "kill_history": "/tool/kill_history",
            "retrieve": "/tool/retrieve",
            "metrics": "/metrics",
            "admin": {
                "create_key": "/admin/keys/create",
                "list_keys": "/admin/keys/list",
                "revoke_key": "/admin/keys/revoke",
                "rotate_key": "/admin/keys/rotate"
            }
        },
        "security": {
            "authentication": "Multi-key role-based authentication",
            "rate_limiting": "Per-IP and per-key rate limits",
            "roles": list(api_key_manager.VALID_ROLES) if hasattr(api_key_manager, 'VALID_ROLES') else ["admin", "feeder", "brain", "ops", "readonly"]
        },
        "observability": {
            "metrics": "Prometheus-compatible metrics at /metrics",
            "health": "Simple health check at /health"
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
    # Start latency timer
    start_time = time.time()

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
        metrics.mcp_validation_failures_total.labels(
            channel=channel,
            error_type="missing_schema_version"
        ).inc()
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
        metrics.mcp_validation_success_total.labels(channel=channel).inc()
    except JSONSchemaValidationError as e:
        log_with_context(logger, 'warning', "Schema validation failed", channel=channel, error=e.message)
        metrics.mcp_validation_failures_total.labels(
            channel=channel,
            error_type="schema_validation"
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Message validation failed: {e.message}"
        )

    # Publish to Redis
    try:
        subscriber_count = redis_client.publish(channel, message)

        # Track publish metrics
        metrics.mcp_publish_total.labels(channel=channel).inc()

        # Track message size (approximate)
        message_size = len(json.dumps(message).encode('utf-8'))
        metrics.mcp_publish_bytes_total.labels(channel=channel).inc(message_size)

        # Track control channel events (kill-switch)
        if channel == "agent:control":
            command = message.get("command")
            if command == "EMERGENCY_HALT":
                metrics.mcp_halt_total.inc()
                metrics.mcp_kill_switch_active.set(1)
            elif command == "RESUME":
                metrics.mcp_resume_total.inc()
                metrics.mcp_kill_switch_active.set(0)

        # Enqueue for S3 archiving (fire-and-forget)
        # Only archive data channels, not control messages
        if channel in ["market:data", "sentiment:data", "agent:signal"]:
            archiver.enqueue(channel, message)

    except Exception as e:
        log_with_context(logger, 'error', "Failed to publish message", channel=channel, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish message: {str(e)}"
        )

    # Record publish latency
    latency = time.time() - start_time
    metrics.mcp_publish_latency_seconds.labels(channel=channel).observe(latency)

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


@app.get("/tool/kill_history", response_model=KillHistoryResponse, dependencies=[Depends(verify_api_key)])
async def get_kill_history(limit: int = Query(default=100, ge=1, le=100)):
    """
    Get kill-switch history (ordered list of control events).

    Returns historical record of all agent:control messages (EMERGENCY_HALT, RESUME, etc.)
    ordered by most recent first. Useful for Brain agent to understand control event timeline.

    Requires authentication in production mode (x-api-key header).

    Args:
        limit: Maximum number of history entries to return (1-100, default 100)

    Returns:
        KillHistoryResponse with:
            - events: List of control events (most recent first)
            - count: Number of events returned
            - current_status: Current kill-switch status
    """
    history = redis_client.get_kill_history(limit=limit)
    current_status = redis_client.get_kill_switch_status()

    logger.info(f"Kill history retrieved: {len(history)} events")

    return KillHistoryResponse(
        events=history,
        count=len(history),
        current_status=current_status
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

    # Validate timestamp ranges
    if retrieve_request.from_timestamp and retrieve_request.to_timestamp:
        # Ensure from_timestamp < to_timestamp
        if retrieve_request.from_timestamp >= retrieve_request.to_timestamp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_timestamp must be less than to_timestamp"
            )

        # Prevent unreasonably large time ranges (> 1 year)
        MAX_TIME_RANGE_SECONDS = 365 * 24 * 60 * 60  # 1 year
        time_range = retrieve_request.to_timestamp - retrieve_request.from_timestamp

        if time_range > MAX_TIME_RANGE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Time range too large. Maximum: {MAX_TIME_RANGE_SECONDS} seconds (1 year)"
            )

    # Validate timestamps are not in the future
    now = int(time.time())
    if retrieve_request.from_timestamp and retrieve_request.from_timestamp > now + 3600:  # Allow 1 hour clock skew
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_timestamp cannot be in the future"
        )
    if retrieve_request.to_timestamp and retrieve_request.to_timestamp > now + 3600:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="to_timestamp cannot be in the future"
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


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.

    Exposes operational metrics in Prometheus text format for scraping.
    Public endpoint (no authentication required) for monitoring systems.

    Updates dynamic metrics (Redis connection, archiver queues, kill-switch status)
    before returning the metrics snapshot.

    Returns:
        Response with Prometheus-formatted metrics
    """
    # Update Redis connection status
    redis_connected = redis_client.health_check()
    metrics.mcp_redis_connected.set(1 if redis_connected else 0)

    # Update kill-switch status from Redis
    kill_switch_status = redis_client.get_kill_switch_status()
    metrics.mcp_kill_switch_active.set(1 if kill_switch_status.get("active") else 0)

    # Update archiver queue sizes (if enabled)
    if archiver.enabled:
        try:
            # Get queue depths for each channel
            for channel in ["market:data", "sentiment:data", "agent:signal"]:
                # Note: archiver.queues is a dict[str, list] in archiver.py
                queue_size = len(archiver.queues.get(channel, []))
                metrics.mcp_archive_queue_size.labels(channel=channel).set(queue_size)
        except Exception as e:
            logger.warning(f"Failed to update archiver queue metrics: {e}")

    # Generate Prometheus output
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Admin endpoints for API key management

@app.post("/admin/keys/create", response_model=CreateKeyResponse, dependencies=[Depends(verify_permission("admin:keys:create"))])
async def create_api_key(
    request: CreateKeyRequest,
    key_info: Dict[str, Any] = Depends(verify_permission("admin:keys:create"))
):
    """
    Create a new API key (admin only).

    Generates a new API key with the specified role and stores it securely.
    The API key is only returned in this response - it cannot be retrieved later.

    Requires: admin:keys:create permission (admin role or ops role)

    Args:
        request: CreateKeyRequest with role and description
        key_info: Authenticated key info from dependency

    Returns:
        CreateKeyResponse with the new API key and metadata

    Raises:
        HTTPException: 400 if role is invalid, 403 if insufficient permissions
    """
    try:
        # Create the key
        new_key = api_key_manager.create_key(
            role=request.role,
            description=request.description,
            created_by=key_info.get("key_hash")
        )

        log_with_context(
            logger, 'info', "API key created",
            role=request.role,
            key_suffix=new_key["key_suffix"],
            created_by=key_info.get("role")
        )

        return CreateKeyResponse(**new_key)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_with_context(logger, 'error', "Failed to create API key", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@app.get("/admin/keys/list", dependencies=[Depends(verify_permission("admin:keys:list"))])
async def list_api_keys(
    include_revoked: bool = Query(default=False),
    key_info: Dict[str, Any] = Depends(verify_permission("admin:keys:list"))
):
    """
    List all API keys (admin only).

    Returns metadata for all keys (API keys themselves are NOT included).

    Requires: admin:keys:list permission (admin or ops role)

    Args:
        include_revoked: Whether to include revoked keys in results
        key_info: Authenticated key info from dependency

    Returns:
        Dict with keys list and count
    """
    try:
        keys = api_key_manager.list_keys(include_revoked=include_revoked)

        return {
            "keys": keys,
            "count": len(keys),
            "include_revoked": include_revoked
        }

    except Exception as e:
        log_with_context(logger, 'error', "Failed to list API keys", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@app.post("/admin/keys/revoke", dependencies=[Depends(verify_permission("admin:keys:revoke"))])
async def revoke_api_key(
    request: RevokeKeyRequest,
    key_info: Dict[str, Any] = Depends(verify_permission("admin:keys:revoke"))
):
    """
    Revoke an API key (admin only).

    Marks the key as revoked. The key will no longer be valid for authentication.
    This is a soft delete - key metadata is retained for audit purposes.

    Requires: admin:keys:revoke permission (admin role only)

    Args:
        request: RevokeKeyRequest with api_key to revoke
        key_info: Authenticated key info from dependency

    Returns:
        Dict with success status

    Raises:
        HTTPException: 404 if key not found, 403 if insufficient permissions
    """
    try:
        success = api_key_manager.revoke_key(
            request.api_key,
            revoked_by=key_info.get("key_hash")
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        return {
            "success": True,
            "message": "API key revoked successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        log_with_context(logger, 'error', "Failed to revoke API key", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key"
        )


@app.post("/admin/keys/rotate", response_model=CreateKeyResponse, dependencies=[Depends(verify_permission("admin:keys:rotate"))])
async def rotate_api_key(
    request: RotateKeyRequest,
    key_info: Dict[str, Any] = Depends(verify_permission("admin:keys:rotate"))
):
    """
    Rotate an API key (admin only).

    Creates a new key with the same role and revokes the old key.
    Useful for security best practices (regular key rotation).

    Requires: admin:keys:rotate permission (admin role only)

    Args:
        request: RotateKeyRequest with old_api_key to rotate
        key_info: Authenticated key info from dependency

    Returns:
        CreateKeyResponse with the new API key

    Raises:
        HTTPException: 404 if key not found, 403 if insufficient permissions
    """
    try:
        new_key = api_key_manager.rotate_key(
            request.old_api_key,
            created_by=key_info.get("key_hash")
        )

        if not new_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found or already revoked"
            )

        log_with_context(
            logger, 'info', "API key rotated",
            new_key_suffix=new_key["key_suffix"],
            rotated_by=key_info.get("role")
        )

        return CreateKeyResponse(**new_key)

    except HTTPException:
        raise
    except Exception as e:
        log_with_context(logger, 'error', "Failed to rotate API key", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate API key"
        )


# Lifecycle events

@app.on_event("startup")
async def startup_event():
    """Run on server startup."""
    log_with_context(logger, 'info', "MCP Server starting")
    log_with_context(logger, 'info', "Connected to Redis", redis_url=REDIS_URL)
    log_with_context(logger, 'info', "Schemas loaded", schema_count=len(SCHEMAS))

    # Register legacy MCP_API_KEY for backward compatibility
    if MCP_API_KEY and not MCP_DEV:
        api_key_manager.register_legacy_key(
            MCP_API_KEY,
            description="Legacy MCP_API_KEY (backward compatibility)"
        )
        log_with_context(logger, 'info', "Legacy MCP_API_KEY registered")

    # Set Prometheus server info
    environment = "development" if MCP_DEV else "production"
    metrics.set_server_info(version="1.0.0", environment=environment)
    log_with_context(logger, 'info', "Metrics initialized", environment=environment)

    # Start archiver background worker
    archiver.start()
    log_with_context(logger, 'info', "Archiver started", enabled=archiver.enabled, bucket=archiver.bucket_name)

    log_with_context(logger, 'info', "MCP Server ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown."""
    log_with_context(logger, 'info', "MCP Server shutting down")

    # Stop archiver and flush remaining messages
    archiver.stop()
    log_with_context(logger, 'info', "Archiver stopped")

    redis_client.close()
    log_with_context(logger, 'info', "MCP Server stopped")


# Input validation middleware

@app.middleware("http")
async def validate_content_type(request: Request, call_next):
    """
    Validate Content-Type header for POST/PUT requests.

    Ensures JSON endpoints only accept application/json.
    Prevents content-type confusion attacks.
    """
    # Only validate POST/PUT requests
    if request.method in ["POST", "PUT"]:
        content_type = request.headers.get("content-type", "")

        # Extract base content type (ignore charset)
        base_content_type = content_type.split(";")[0].strip().lower()

        # Allow application/json for JSON endpoints
        if not base_content_type.startswith("application/json"):
            # Special exception for /metrics (accepts no body)
            if not request.url.path.startswith("/metrics"):
                return JSONResponse(
                    status_code=415,
                    content={
                        "detail": "Unsupported Media Type. Content-Type must be application/json"
                    }
                )

    response = await call_next(request)
    return response


# Error handlers

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Handle unexpected exceptions.

    In production: Returns generic error message (no stack trace)
    In development: Returns detailed error for debugging
    """
    # Log full exception details
    log_with_context(
        logger, 'error',
        "Unhandled exception",
        error_type=type(exc).__name__,
        error_message=str(exc)
    )

    # Log full stack trace (for debugging)
    logger.error("Exception details:", exc_info=True)

    # Determine error detail based on environment
    if MCP_DEV:
        # Development: Show detailed error
        detail = f"{type(exc).__name__}: {str(exc)}"
    else:
        # Production: Generic message (don't leak internals)
        detail = "An unexpected error occurred. Please contact support if this persists."

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": detail,
            "error_id": get_request_id() if 'get_request_id' in dir() else None
        }
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    """
    Handle Pydantic validation errors.

    Returns clear validation error messages (safe to expose).
    """
    log_with_context(
        logger, 'warning',
        "Validation error",
        errors=str(exc.errors())
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors()
        }
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
