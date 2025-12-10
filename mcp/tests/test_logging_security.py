"""
Security tests for structured logging.

Ensures no sensitive information (API keys, passwords, AWS credentials) leak into logs.
"""

import os
import logging
from mcp.logging_config import get_sanitized_extra, setup_logging


def test_sanitize_api_key():
    """Test that API keys are redacted from logs."""
    extra = get_sanitized_extra(user="alice", api_key="secret123", MCP_API_KEY="prod-key-456")

    assert extra["user"] == "alice"
    assert extra["api_key"] == "<REDACTED>"
    assert extra["MCP_API_KEY"] == "<REDACTED>"


def test_sanitize_aws_credentials():
    """Test that AWS credentials are redacted."""
    extra = get_sanitized_extra(
        region="us-east-1",
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    )

    assert extra["region"] == "us-east-1"
    assert extra["aws_access_key_id"] == "<REDACTED>"
    assert extra["aws_secret_access_key"] == "<REDACTED>"


def test_sanitize_passwords():
    """Test that passwords are redacted."""
    extra = get_sanitized_extra(
        username="bob",
        password="mypassword",
        passwd="old_pw",
        pwd="another"
    )

    assert extra["username"] == "bob"
    assert extra["password"] == "<REDACTED>"
    assert extra["passwd"] == "<REDACTED>"
    assert extra["pwd"] == "<REDACTED>"


def test_sanitize_tokens():
    """Test that tokens are redacted."""
    extra = get_sanitized_extra(
        user_id=123,
        token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        access_token="Bearer xyz",
        refresh_token="refresh_abc"
    )

    assert extra["user_id"] == 123
    assert extra["token"] == "<REDACTED>"
    assert extra["access_token"] == "<REDACTED>"
    assert extra["refresh_token"] == "<REDACTED>"


def test_sanitize_case_insensitive():
    """Test that field name matching is case-insensitive."""
    extra = get_sanitized_extra(
        API_KEY="should_be_redacted",
        Api_Key="also_redacted",
        aPi_KeY="redacted_too"
    )

    assert extra["API_KEY"] == "<REDACTED>"
    assert extra["Api_Key"] == "<REDACTED>"
    assert extra["aPi_KeY"] == "<REDACTED>"


def test_safe_fields_not_sanitized():
    """Test that non-sensitive fields are not modified."""
    extra = get_sanitized_extra(
        channel="market:data",
        pair="BTC-ETH",
        price=30000.0,
        timestamp=1678886400,
        message_count=100
    )

    assert extra["channel"] == "market:data"
    assert extra["pair"] == "BTC-ETH"
    assert extra["price"] == 30000.0
    assert extra["timestamp"] == 1678886400
    assert extra["message_count"] == 100


def test_logging_setup():
    """Test that structured logging can be set up without errors."""
    logger = setup_logging(log_level="INFO")
    assert logger is not None
    assert logger.level == logging.INFO


def test_logging_setup_invalid_level():
    """Test that invalid log level defaults to INFO."""
    logger = setup_logging(log_level="INVALID")
    assert logger.level == logging.INFO


def test_logging_setup_from_env(monkeypatch):
    """Test that log level can be set from environment variable."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logger = setup_logging()
    assert logger.level == logging.DEBUG
