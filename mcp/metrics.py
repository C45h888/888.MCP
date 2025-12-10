"""
Prometheus metrics for MCP Server.

Exposes operational metrics for monitoring, alerting, and performance analysis.
All metrics follow Prometheus naming conventions and best practices.

Metrics Categories:
- Server Info: Static metadata
- Publish Metrics: Message publishing rates and latencies
- Validation Metrics: Schema validation failures
- Control Metrics: Kill-switch and control channel events
- Archiver Metrics: S3 upload queue and performance
- Redis Metrics: Connection health
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# ============================================================================
# SERVER INFO
# ============================================================================

mcp_info = Info(
    'mcp_server',
    'MCP Server metadata and version information'
)


# ============================================================================
# PUBLISH METRICS
# ============================================================================

mcp_publish_total = Counter(
    'mcp_publish_total',
    'Total number of messages published',
    ['channel']
)

mcp_publish_latency_seconds = Histogram(
    'mcp_publish_latency_seconds',
    'Time taken to publish a message (seconds)',
    ['channel'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

mcp_publish_bytes_total = Counter(
    'mcp_publish_bytes_total',
    'Total bytes published',
    ['channel']
)


# ============================================================================
# VALIDATION METRICS
# ============================================================================

mcp_validation_failures_total = Counter(
    'mcp_validation_failures_total',
    'Total schema validation failures',
    ['channel', 'error_type']
)

mcp_validation_success_total = Counter(
    'mcp_validation_success_total',
    'Total successful schema validations',
    ['channel']
)


# ============================================================================
# CONTROL CHANNEL METRICS (Kill-Switch)
# ============================================================================

mcp_halt_total = Counter(
    'mcp_halt_total',
    'Total EMERGENCY_HALT commands received',
    []
)

mcp_resume_total = Counter(
    'mcp_resume_total',
    'Total RESUME commands received',
    []
)

mcp_kill_switch_active = Gauge(
    'mcp_kill_switch_active',
    'Current kill-switch status (1=active/halted, 0=normal)',
    []
)


# ============================================================================
# ARCHIVER METRICS (S3 Upload)
# ============================================================================

mcp_archive_queue_size = Gauge(
    'mcp_archive_queue_size',
    'Current number of messages in archiver queue',
    ['channel']
)

mcp_archive_flush_total = Counter(
    'mcp_archive_flush_total',
    'Total S3 upload flushes completed',
    ['channel']
)

mcp_archive_messages_uploaded = Counter(
    'mcp_archive_messages_uploaded',
    'Total messages successfully uploaded to S3',
    ['channel']
)

mcp_archive_upload_failures_total = Counter(
    'mcp_archive_upload_failures_total',
    'Total S3 upload failures',
    ['channel', 'error_type']
)

mcp_archive_upload_bytes_total = Counter(
    'mcp_archive_upload_bytes_total',
    'Total bytes uploaded to S3',
    ['channel']
)


# ============================================================================
# REDIS METRICS
# ============================================================================

mcp_redis_connected = Gauge(
    'mcp_redis_connected',
    'Redis connection status (1=connected, 0=disconnected)',
    []
)

mcp_redis_operations_total = Counter(
    'mcp_redis_operations_total',
    'Total Redis operations',
    ['operation']
)

mcp_redis_errors_total = Counter(
    'mcp_redis_errors_total',
    'Total Redis operation errors',
    ['operation', 'error_type']
)


# ============================================================================
# HTTP METRICS
# ============================================================================

mcp_http_requests_total = Counter(
    'mcp_http_requests_total',
    'Total HTTP requests received',
    ['method', 'endpoint', 'status_code']
)

mcp_http_request_duration_seconds = Histogram(
    'mcp_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)


# ============================================================================
# RETRIEVAL METRICS
# ============================================================================

mcp_retrieval_requests_total = Counter(
    'mcp_retrieval_requests_total',
    'Total historical data retrieval requests',
    ['channel']
)

mcp_retrieval_messages_returned = Counter(
    'mcp_retrieval_messages_returned',
    'Total messages returned from retrieval',
    ['channel']
)

mcp_retrieval_duration_seconds = Histogram(
    'mcp_retrieval_duration_seconds',
    'Time taken to retrieve historical data (seconds)',
    ['channel'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def set_server_info(version: str, environment: str) -> None:
    """
    Set server metadata information.

    Should be called once during server startup.

    Args:
        version: Server version string
        environment: Environment name (production, development, etc.)
    """
    mcp_info.info({
        'version': version,
        'environment': environment
    })


def get_kill_switch_status() -> int:
    """
    Get current kill-switch status as integer.

    Returns:
        1 if kill-switch is active (halted), 0 if normal
    """
    # This will be updated by server.py when checking kill-switch
    return int(mcp_kill_switch_active._value.get())


# ============================================================================
# METRIC GROUPS (for easy access)
# ============================================================================

PUBLISH_METRICS = {
    'total': mcp_publish_total,
    'latency': mcp_publish_latency_seconds,
    'bytes': mcp_publish_bytes_total
}

VALIDATION_METRICS = {
    'failures': mcp_validation_failures_total,
    'success': mcp_validation_success_total
}

CONTROL_METRICS = {
    'halt': mcp_halt_total,
    'resume': mcp_resume_total,
    'active': mcp_kill_switch_active
}

ARCHIVER_METRICS = {
    'queue_size': mcp_archive_queue_size,
    'flush_total': mcp_archive_flush_total,
    'messages_uploaded': mcp_archive_messages_uploaded,
    'failures': mcp_archive_upload_failures_total,
    'bytes_uploaded': mcp_archive_upload_bytes_total
}

REDIS_METRICS = {
    'connected': mcp_redis_connected,
    'operations': mcp_redis_operations_total,
    'errors': mcp_redis_errors_total
}

HTTP_METRICS = {
    'requests': mcp_http_requests_total,
    'duration': mcp_http_request_duration_seconds
}

RETRIEVAL_METRICS = {
    'requests': mcp_retrieval_requests_total,
    'messages_returned': mcp_retrieval_messages_returned,
    'duration': mcp_retrieval_duration_seconds
}
