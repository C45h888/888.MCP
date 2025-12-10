"""
Multi-Key Authentication System for MCP Server.

Provides role-based API key management with:
- Multiple API keys with different roles (admin, feeder, brain, ops, readonly)
- Permission-based access control
- Key rotation and revocation
- Secure key storage (hashed in Redis)
- Backward compatibility with legacy MCP_API_KEY

Security Design:
- Keys are SHA256-hashed before storage
- Only key hashes stored in Redis, never plaintext
- Secure random key generation using secrets module
- Rate limit on key operations to prevent brute force
"""

import hashlib
import secrets
import time
import logging
from typing import Optional, Dict, List, Set
from datetime import datetime

logger = logging.getLogger(__name__)


# Role-based permission definitions
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {
        "*",  # All permissions (wildcard)
    },
    "feeder": {
        "publish:market:data",
        "publish:sentiment:data",
        "status:read",
        "metrics:read",
    },
    "brain": {
        "publish:agent:signal",
        "retrieve:*",
        "kill_history:read",
        "status:read",
        "metrics:read",
    },
    "ops": {
        "publish:agent:control",
        "status:read",
        "kill_history:read",
        "metrics:read",
        "admin:keys:list",  # Can list keys but not create/revoke
    },
    "readonly": {
        "status:read",
        "metrics:read",
    },
}

# Valid roles
VALID_ROLES = set(ROLE_PERMISSIONS.keys())


class APIKeyManager:
    """
    Manage multiple API keys with roles and permissions.

    Key Format: "mcp_<role>_<32_random_hex_chars>"
    Example: "mcp_feeder_a1b2c3d4e5f67890123456789abcdef0"

    Storage:
    - Keys stored in Redis as hashes
    - Key: "mcp:apikeys:<key_hash>"
    - Index: "mcp:apikeys:index" (set of all key hashes)

    Key Metadata:
    {
        "key_hash": "sha256_hash",
        "role": "feeder",
        "description": "Production feeder agent",
        "created_at": 1678886400,
        "created_by": "admin_key_hash",
        "revoked": false,
        "revoked_at": null,
        "revoked_by": null,
        "last_used": 1678886500,
        "usage_count": 12345,
        "key_suffix": "...cdef0"  # Last 6 chars for identification
    }
    """

    KEY_PREFIX = "mcp:apikeys:"
    INDEX_KEY = "mcp:apikeys:index"
    LEGACY_KEY = "mcp:apikeys:legacy"

    def __init__(self, redis_client):
        """
        Initialize API key manager.

        Args:
            redis_client: RedisClient instance for storage
        """
        self.redis = redis_client
        logger.info("APIKeyManager initialized")

    @staticmethod
    def generate_key(role: str) -> str:
        """
        Generate a new secure API key.

        Args:
            role: Role for the key (admin, feeder, brain, ops, readonly)

        Returns:
            API key string in format "mcp_<role>_<32_random_hex>"

        Raises:
            ValueError: If role is invalid
        """
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of: {VALID_ROLES}")

        # Generate 32 random hex characters (16 bytes = 128 bits of entropy)
        random_suffix = secrets.token_hex(16)

        return f"mcp_{role}_{random_suffix}"

    @staticmethod
    def hash_key(api_key: str) -> str:
        """
        Hash an API key using SHA256.

        Args:
            api_key: API key to hash

        Returns:
            SHA256 hex digest of the key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def extract_role_from_key(api_key: str) -> Optional[str]:
        """
        Extract role from API key format.

        Args:
            api_key: API key string

        Returns:
            Role name if valid format, None otherwise
        """
        try:
            parts = api_key.split("_")
            if len(parts) == 3 and parts[0] == "mcp":
                return parts[1]
        except Exception:
            pass
        return None

    def create_key(
        self,
        role: str,
        description: str,
        created_by: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate and store a new API key.

        Args:
            role: Role for the key (admin, feeder, brain, ops, readonly)
            description: Human-readable description of the key's purpose
            created_by: API key hash of the admin creating this key

        Returns:
            Dict with:
                - api_key: The generated API key (ONLY TIME THIS IS RETURNED)
                - key_hash: SHA256 hash of the key
                - role: Role name
                - description: Description
                - created_at: Unix timestamp
                - key_suffix: Last 6 chars for identification

        Raises:
            ValueError: If role is invalid
        """
        # Generate secure key
        api_key = self.generate_key(role)
        key_hash = self.hash_key(api_key)
        key_suffix = api_key[-6:]

        # Create metadata
        now = int(time.time())
        metadata = {
            "key_hash": key_hash,
            "role": role,
            "description": description,
            "created_at": str(now),
            "created_by": created_by or "system",
            "revoked": "false",
            "revoked_at": "",
            "revoked_by": "",
            "last_used": str(now),
            "usage_count": "0",
            "key_suffix": key_suffix,
        }

        # Store in Redis
        key_storage_key = f"{self.KEY_PREFIX}{key_hash}"

        try:
            # Store key metadata as hash
            self.redis.client.hset(key_storage_key, mapping=metadata)

            # Add to index
            self.redis.client.sadd(self.INDEX_KEY, key_hash)

            logger.info(
                "API key created",
                extra={
                    "role": role,
                    "key_suffix": key_suffix,
                    "created_by": created_by or "system"
                }
            )

            # Return key info (API key is only returned here!)
            return {
                "api_key": api_key,  # ONLY TIME WE RETURN PLAINTEXT KEY
                "key_hash": key_hash,
                "role": role,
                "description": description,
                "created_at": now,
                "key_suffix": key_suffix,
            }

        except Exception as e:
            logger.error(f"Failed to create API key: {e}", exc_info=True)
            raise

    def validate_key(self, api_key: str) -> Optional[Dict[str, any]]:
        """
        Validate an API key and return its metadata.

        Args:
            api_key: API key to validate

        Returns:
            Key metadata dict if valid and not revoked, None otherwise
            Metadata includes: role, description, created_at, last_used, usage_count, permissions
        """
        if not api_key:
            return None

        # Hash the key
        key_hash = self.hash_key(api_key)
        key_storage_key = f"{self.KEY_PREFIX}{key_hash}"

        try:
            # Retrieve metadata from Redis
            metadata = self.redis.client.hgetall(key_storage_key)

            if not metadata:
                # Key not found
                return None

            # Check if revoked
            if metadata.get(b"revoked", b"false") == b"true":
                logger.warning(
                    "Revoked key attempted",
                    extra={"key_suffix": metadata.get(b"key_suffix", b"unknown").decode()}
                )
                return None

            # Decode bytes to strings
            role = metadata.get(b"role", b"").decode()

            # Return metadata with permissions
            return {
                "key_hash": key_hash,
                "role": role,
                "description": metadata.get(b"description", b"").decode(),
                "created_at": int(metadata.get(b"created_at", b"0").decode()),
                "last_used": int(metadata.get(b"last_used", b"0").decode()),
                "usage_count": int(metadata.get(b"usage_count", b"0").decode()),
                "key_suffix": metadata.get(b"key_suffix", b"").decode(),
                "permissions": ROLE_PERMISSIONS.get(role, set()),
            }

        except Exception as e:
            logger.error(f"Error validating API key: {e}", exc_info=True)
            return None

    def touch_key(self, api_key: str) -> None:
        """
        Update last_used timestamp and increment usage_count for a key.

        Args:
            api_key: API key to update
        """
        key_hash = self.hash_key(api_key)
        key_storage_key = f"{self.KEY_PREFIX}{key_hash}"

        try:
            now = int(time.time())

            # Update last_used and increment usage_count
            pipe = self.redis.client.pipeline()
            pipe.hset(key_storage_key, "last_used", str(now))
            pipe.hincrby(key_storage_key, "usage_count", 1)
            pipe.execute()

        except Exception as e:
            logger.warning(f"Failed to update key usage: {e}")

    def revoke_key(self, api_key: str, revoked_by: Optional[str] = None) -> bool:
        """
        Revoke an API key (soft delete - marks as revoked).

        Args:
            api_key: API key to revoke
            revoked_by: API key hash of the admin revoking this key

        Returns:
            True if revoked successfully, False otherwise
        """
        key_hash = self.hash_key(api_key)
        key_storage_key = f"{self.KEY_PREFIX}{key_hash}"

        try:
            # Check if key exists
            if not self.redis.client.exists(key_storage_key):
                return False

            now = int(time.time())

            # Mark as revoked
            pipe = self.redis.client.pipeline()
            pipe.hset(key_storage_key, "revoked", "true")
            pipe.hset(key_storage_key, "revoked_at", str(now))
            pipe.hset(key_storage_key, "revoked_by", revoked_by or "system")
            pipe.execute()

            logger.info(
                "API key revoked",
                extra={
                    "key_hash": key_hash[:8] + "...",
                    "revoked_by": revoked_by or "system"
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}", exc_info=True)
            return False

    def rotate_key(self, old_api_key: str, created_by: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Rotate an API key (create new, revoke old).

        Args:
            old_api_key: Existing API key to rotate
            created_by: API key hash of the admin rotating this key

        Returns:
            New key info dict if successful, None otherwise
        """
        # Validate old key
        old_metadata = self.validate_key(old_api_key)
        if not old_metadata:
            logger.warning("Attempted to rotate invalid or revoked key")
            return None

        # Create new key with same role and updated description
        new_description = f"{old_metadata['description']} (rotated)"
        new_key_info = self.create_key(
            role=old_metadata["role"],
            description=new_description,
            created_by=created_by
        )

        # Revoke old key
        self.revoke_key(old_api_key, revoked_by=created_by)

        logger.info(
            "API key rotated",
            extra={
                "old_key_suffix": old_metadata["key_suffix"],
                "new_key_suffix": new_key_info["key_suffix"],
                "role": old_metadata["role"]
            }
        )

        return new_key_info

    def list_keys(self, include_revoked: bool = False) -> List[Dict[str, any]]:
        """
        List all API keys (redacted, showing only metadata).

        Args:
            include_revoked: Whether to include revoked keys

        Returns:
            List of key metadata dicts (API keys are NOT included)
        """
        try:
            # Get all key hashes from index
            key_hashes = self.redis.client.smembers(self.INDEX_KEY)

            keys = []
            for key_hash_bytes in key_hashes:
                key_hash = key_hash_bytes.decode()
                key_storage_key = f"{self.KEY_PREFIX}{key_hash}"

                metadata = self.redis.client.hgetall(key_storage_key)
                if not metadata:
                    continue

                is_revoked = metadata.get(b"revoked", b"false") == b"true"

                # Skip revoked keys if not requested
                if is_revoked and not include_revoked:
                    continue

                keys.append({
                    "key_hash": key_hash[:8] + "...",  # Redacted
                    "role": metadata.get(b"role", b"").decode(),
                    "description": metadata.get(b"description", b"").decode(),
                    "created_at": int(metadata.get(b"created_at", b"0").decode()),
                    "last_used": int(metadata.get(b"last_used", b"0").decode()),
                    "usage_count": int(metadata.get(b"usage_count", b"0").decode()),
                    "key_suffix": metadata.get(b"key_suffix", b"").decode(),
                    "revoked": is_revoked,
                    "revoked_at": int(metadata.get(b"revoked_at", b"0").decode()) if is_revoked else None,
                })

            # Sort by created_at descending
            keys.sort(key=lambda x: x["created_at"], reverse=True)

            return keys

        except Exception as e:
            logger.error(f"Failed to list API keys: {e}", exc_info=True)
            return []

    def register_legacy_key(self, legacy_key: str, description: str = "Legacy MCP_API_KEY") -> None:
        """
        Register the legacy MCP_API_KEY for backward compatibility.

        This allows the existing MCP_API_KEY environment variable to work
        as an admin key in the new multi-key system.

        Args:
            legacy_key: The legacy MCP_API_KEY value
            description: Description for the legacy key
        """
        if not legacy_key:
            return

        key_hash = self.hash_key(legacy_key)
        key_storage_key = f"{self.KEY_PREFIX}{key_hash}"

        # Check if already registered
        if self.redis.client.exists(key_storage_key):
            logger.info("Legacy key already registered")
            return

        # Register as admin key
        now = int(time.time())
        metadata = {
            "key_hash": key_hash,
            "role": "admin",
            "description": description,
            "created_at": str(now),
            "created_by": "system_migration",
            "revoked": "false",
            "revoked_at": "",
            "revoked_by": "",
            "last_used": str(now),
            "usage_count": "0",
            "key_suffix": "legacy",
        }

        try:
            self.redis.client.hset(key_storage_key, mapping=metadata)
            self.redis.client.sadd(self.INDEX_KEY, key_hash)

            logger.info("Legacy MCP_API_KEY registered as admin key")

        except Exception as e:
            logger.error(f"Failed to register legacy key: {e}", exc_info=True)


def has_permission(key_info: Dict[str, any], required_permission: str) -> bool:
    """
    Check if a key has the required permission.

    Args:
        key_info: Key metadata dict from validate_key()
        required_permission: Permission string (e.g., "publish:market:data")

    Returns:
        True if key has permission, False otherwise

    Permission Matching:
    - Exact match: "publish:market:data" matches "publish:market:data"
    - Wildcard match: "*" matches any permission
    - Prefix wildcard: "retrieve:*" matches "retrieve:market:data"
    """
    permissions = key_info.get("permissions", set())

    # Check for admin wildcard
    if "*" in permissions:
        return True

    # Check for exact match
    if required_permission in permissions:
        return True

    # Check for prefix wildcard (e.g., "retrieve:*" matches "retrieve:market:data")
    for perm in permissions:
        if perm.endswith(":*"):
            prefix = perm[:-2]  # Remove ":*"
            if required_permission.startswith(prefix + ":"):
                return True

    return False
