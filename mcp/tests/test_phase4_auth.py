"""
Phase 4 Testing Suite: Multi-Key Authentication

Tests the API key management system including:
- Key generation and storage
- Role-based permissions
- Key validation and hashing
- Key lifecycle (create, revoke, rotate)
- Permission checking
"""

import pytest
import time
from unittest.mock import Mock, MagicMock
from mcp.auth import APIKeyManager, has_permission, ROLE_PERMISSIONS


class TestAPIKeyGeneration:
    """Test API key generation and format."""

    def test_generate_key_format(self):
        """Test that generated keys follow correct format."""
        manager = APIKeyManager(Mock())

        # Test each role
        for role in ["admin", "feeder", "brain", "ops", "readonly"]:
            key = manager.generate_key(role)

            # Should start with mcp_<role>_
            assert key.startswith(f"mcp_{role}_")

            # Should be 32 characters of random hex after prefix
            parts = key.split("_", 2)
            assert len(parts) == 3
            assert len(parts[2]) == 64  # 32 bytes = 64 hex chars

            # Should be valid hex
            int(parts[2], 16)  # Will raise if not valid hex

    def test_generate_key_uniqueness(self):
        """Test that generated keys are unique."""
        manager = APIKeyManager(Mock())

        keys = set()
        for _ in range(100):
            key = manager.generate_key("admin")
            assert key not in keys, "Duplicate key generated"
            keys.add(key)

    def test_generate_key_invalid_role(self):
        """Test that invalid roles are rejected."""
        manager = APIKeyManager(Mock())

        with pytest.raises(ValueError, match="Invalid role"):
            manager.generate_key("invalid_role")


class TestAPIKeyHashing:
    """Test API key hashing and validation."""

    def test_hash_key_sha256(self):
        """Test that keys are hashed with SHA256."""
        manager = APIKeyManager(Mock())

        test_key = "mcp_admin_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        key_hash = manager.hash_key(test_key)

        # SHA256 produces 64 character hex string
        assert len(key_hash) == 64
        assert all(c in "0123456789abcdef" for c in key_hash)

    def test_hash_key_deterministic(self):
        """Test that same key produces same hash."""
        manager = APIKeyManager(Mock())

        test_key = "mcp_admin_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        hash1 = manager.hash_key(test_key)
        hash2 = manager.hash_key(test_key)

        assert hash1 == hash2

    def test_hash_key_different_for_different_keys(self):
        """Test that different keys produce different hashes."""
        manager = APIKeyManager(Mock())

        key1 = "mcp_admin_1111111111111111111111111111111111111111111111111111111111111111"
        key2 = "mcp_admin_2222222222222222222222222222222222222222222222222222222222222222"

        hash1 = manager.hash_key(key1)
        hash2 = manager.hash_key(key2)

        assert hash1 != hash2


class TestAPIKeyCreation:
    """Test API key creation and storage."""

    def test_create_key_success(self):
        """Test successful key creation."""
        mock_redis = Mock()
        mock_redis.hset = MagicMock()

        manager = APIKeyManager(mock_redis)
        result = manager.create_key("feeder", "Test feeder key")

        # Check response structure
        assert "api_key" in result
        assert "key_hash" in result
        assert "role" in result
        assert "description" in result
        assert "created_at" in result
        assert "key_suffix" in result

        # Check values
        assert result["role"] == "feeder"
        assert result["description"] == "Test feeder key"
        assert result["api_key"].startswith("mcp_feeder_")

        # Check Redis was called to store key
        assert mock_redis.hset.called

    def test_create_key_with_created_by(self):
        """Test key creation with created_by tracking."""
        mock_redis = Mock()
        mock_redis.hset = MagicMock()

        manager = APIKeyManager(mock_redis)
        result = manager.create_key(
            "ops",
            "Test ops key",
            created_by="admin_key_hash_123"
        )

        assert result["role"] == "ops"
        # created_by should be stored but not returned in response
        assert "created_by" not in result

    def test_create_key_invalid_role(self):
        """Test that invalid roles are rejected."""
        manager = APIKeyManager(Mock())

        with pytest.raises(ValueError, match="Invalid role"):
            manager.create_key("invalid", "Test key")

    def test_create_key_empty_description(self):
        """Test that empty descriptions are rejected."""
        manager = APIKeyManager(Mock())

        with pytest.raises(ValueError, match="Description cannot be empty"):
            manager.create_key("admin", "")


class TestAPIKeyValidation:
    """Test API key validation."""

    def test_validate_key_success(self):
        """Test successful key validation."""
        mock_redis = Mock()

        # Mock Redis response for valid key
        test_key_hash = "abc123def456"
        mock_redis.hgetall.return_value = {
            b"role": b"feeder",
            b"status": b"active",
            b"created_at": str(int(time.time())).encode(),
            b"description": b"Test key"
        }

        manager = APIKeyManager(mock_redis)

        # Create a test key (we'll mock the hash lookup)
        test_key = "mcp_feeder_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        # Validate
        result = manager.validate_key(test_key)

        assert result is not None
        assert result["role"] == "feeder"
        assert "permissions" in result
        assert result["status"] == "active"

    def test_validate_key_revoked(self):
        """Test that revoked keys are rejected."""
        mock_redis = Mock()

        # Mock Redis response for revoked key
        mock_redis.hgetall.return_value = {
            b"role": b"feeder",
            b"status": b"revoked",
            b"created_at": str(int(time.time())).encode(),
            b"description": b"Test key"
        }

        manager = APIKeyManager(mock_redis)
        test_key = "mcp_feeder_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = manager.validate_key(test_key)

        assert result is None  # Revoked keys return None

    def test_validate_key_not_found(self):
        """Test that non-existent keys are rejected."""
        mock_redis = Mock()
        mock_redis.hgetall.return_value = {}  # Key not found

        manager = APIKeyManager(mock_redis)
        test_key = "mcp_admin_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = manager.validate_key(test_key)

        assert result is None

    def test_validate_key_invalid_format(self):
        """Test that malformed keys are rejected."""
        manager = APIKeyManager(Mock())

        # Test various invalid formats
        invalid_keys = [
            "not_an_api_key",
            "mcp_invalid_format",
            "mcp_admin_short",
            "",
            None
        ]

        for invalid_key in invalid_keys:
            result = manager.validate_key(invalid_key)
            assert result is None, f"Should reject invalid key: {invalid_key}"


class TestAPIKeyRevocation:
    """Test API key revocation."""

    def test_revoke_key_success(self):
        """Test successful key revocation."""
        mock_redis = Mock()

        # Mock key exists and is active
        mock_redis.hgetall.return_value = {
            b"role": b"feeder",
            b"status": b"active",
            b"created_at": str(int(time.time())).encode()
        }
        mock_redis.hset = MagicMock()

        manager = APIKeyManager(mock_redis)
        test_key = "mcp_feeder_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        success = manager.revoke_key(test_key, revoked_by="admin_123")

        assert success is True
        # Should update status to revoked
        assert mock_redis.hset.called

    def test_revoke_key_not_found(self):
        """Test revoking non-existent key."""
        mock_redis = Mock()
        mock_redis.hgetall.return_value = {}  # Key not found

        manager = APIKeyManager(mock_redis)
        test_key = "mcp_admin_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        success = manager.revoke_key(test_key)

        assert success is False

    def test_revoke_key_already_revoked(self):
        """Test revoking already revoked key."""
        mock_redis = Mock()

        # Mock key is already revoked
        mock_redis.hgetall.return_value = {
            b"role": b"feeder",
            b"status": b"revoked",
            b"created_at": str(int(time.time())).encode()
        }

        manager = APIKeyManager(mock_redis)
        test_key = "mcp_feeder_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        success = manager.revoke_key(test_key)

        assert success is False


class TestAPIKeyRotation:
    """Test API key rotation."""

    def test_rotate_key_success(self):
        """Test successful key rotation."""
        mock_redis = Mock()

        # Mock old key exists and is active
        mock_redis.hgetall.return_value = {
            b"role": b"feeder",
            b"status": b"active",
            b"created_at": str(int(time.time())).encode(),
            b"description": b"Old feeder key"
        }
        mock_redis.hset = MagicMock()

        manager = APIKeyManager(mock_redis)
        old_key = "mcp_feeder_1111111111111111111111111111111111111111111111111111111111111111"

        new_key_data = manager.rotate_key(old_key, created_by="admin_123")

        assert new_key_data is not None
        assert "api_key" in new_key_data
        assert new_key_data["role"] == "feeder"
        assert new_key_data["api_key"].startswith("mcp_feeder_")
        assert new_key_data["api_key"] != old_key  # New key is different

        # Should have updated old key status to revoked
        assert mock_redis.hset.called

    def test_rotate_key_not_found(self):
        """Test rotating non-existent key."""
        mock_redis = Mock()
        mock_redis.hgetall.return_value = {}  # Key not found

        manager = APIKeyManager(mock_redis)
        old_key = "mcp_admin_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = manager.rotate_key(old_key)

        assert result is None

    def test_rotate_key_already_revoked(self):
        """Test rotating already revoked key."""
        mock_redis = Mock()

        # Mock key is already revoked
        mock_redis.hgetall.return_value = {
            b"role": b"feeder",
            b"status": b"revoked",
            b"created_at": str(int(time.time())).encode()
        }

        manager = APIKeyManager(mock_redis)
        old_key = "mcp_feeder_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = manager.rotate_key(old_key)

        assert result is None


class TestPermissionChecking:
    """Test permission validation logic."""

    def test_admin_has_all_permissions(self):
        """Test that admin wildcard matches all permissions."""
        admin_key_info = {
            "role": "admin",
            "permissions": {"*"}
        }

        # Admin should have access to everything
        assert has_permission(admin_key_info, "publish:market:data")
        assert has_permission(admin_key_info, "retrieve:sentiment:data")
        assert has_permission(admin_key_info, "admin:keys:create")
        assert has_permission(admin_key_info, "any:random:permission")

    def test_exact_permission_match(self):
        """Test exact permission matching."""
        feeder_key_info = {
            "role": "feeder",
            "permissions": {"publish:market:data", "publish:sentiment:data", "status:read"}
        }

        # Should have exact matches
        assert has_permission(feeder_key_info, "publish:market:data")
        assert has_permission(feeder_key_info, "publish:sentiment:data")
        assert has_permission(feeder_key_info, "status:read")

        # Should NOT have other permissions
        assert not has_permission(feeder_key_info, "retrieve:market:data")
        assert not has_permission(feeder_key_info, "admin:keys:create")

    def test_wildcard_permission_match(self):
        """Test wildcard permission matching."""
        brain_key_info = {
            "role": "brain",
            "permissions": {"retrieve:*", "publish:agent:signal"}
        }

        # retrieve:* should match all retrieve permissions
        assert has_permission(brain_key_info, "retrieve:market:data")
        assert has_permission(brain_key_info, "retrieve:sentiment:data")
        assert has_permission(brain_key_info, "retrieve:any:collection")

        # Should have exact match
        assert has_permission(brain_key_info, "publish:agent:signal")

        # Should NOT match other patterns
        assert not has_permission(brain_key_info, "publish:market:data")
        assert not has_permission(brain_key_info, "admin:keys:create")

    def test_readonly_permissions(self):
        """Test readonly role permissions."""
        readonly_key_info = {
            "role": "readonly",
            "permissions": ROLE_PERMISSIONS["readonly"]
        }

        # Should have retrieve access
        assert has_permission(readonly_key_info, "retrieve:market:data")
        assert has_permission(readonly_key_info, "retrieve:sentiment:data")
        assert has_permission(readonly_key_info, "status:read")
        assert has_permission(readonly_key_info, "metrics:read")

        # Should NOT have write access
        assert not has_permission(readonly_key_info, "publish:market:data")
        assert not has_permission(readonly_key_info, "admin:keys:create")
        assert not has_permission(readonly_key_info, "kill:activate")

    def test_ops_permissions(self):
        """Test ops role permissions."""
        ops_key_info = {
            "role": "ops",
            "permissions": ROLE_PERMISSIONS["ops"]
        }

        # Should have retrieve and kill-switch access
        assert has_permission(ops_key_info, "retrieve:market:data")
        assert has_permission(ops_key_info, "kill:activate")
        assert has_permission(ops_key_info, "kill:deactivate")
        assert has_permission(ops_key_info, "status:read")

        # Should NOT have publish or admin access
        assert not has_permission(ops_key_info, "publish:market:data")
        assert not has_permission(ops_key_info, "admin:keys:create")


class TestAPIKeyListing:
    """Test listing API keys."""

    def test_list_keys_active_only(self):
        """Test listing only active keys."""
        mock_redis = Mock()

        # Mock Redis SCAN to return multiple keys
        mock_redis.scan_iter.return_value = [
            b"mcp:key:hash1",
            b"mcp:key:hash2",
            b"mcp:key:hash3"
        ]

        # Mock key data
        def mock_hgetall(key):
            if key == b"mcp:key:hash1":
                return {
                    b"role": b"admin",
                    b"status": b"active",
                    b"created_at": b"1678886400",
                    b"last_used": b"1678886500",
                    b"description": b"Admin key"
                }
            elif key == b"mcp:key:hash2":
                return {
                    b"role": b"feeder",
                    b"status": b"revoked",
                    b"created_at": b"1678886300",
                    b"description": b"Old feeder key"
                }
            elif key == b"mcp:key:hash3":
                return {
                    b"role": b"brain",
                    b"status": b"active",
                    b"created_at": b"1678886350",
                    b"last_used": b"1678886600",
                    b"description": b"Brain key"
                }
            return {}

        mock_redis.hgetall.side_effect = mock_hgetall

        manager = APIKeyManager(mock_redis)
        keys = manager.list_keys(include_revoked=False)

        # Should only return active keys
        assert len(keys) == 2
        assert all(k["status"] == "active" for k in keys)

    def test_list_keys_include_revoked(self):
        """Test listing all keys including revoked."""
        mock_redis = Mock()

        # Mock Redis SCAN to return multiple keys
        mock_redis.scan_iter.return_value = [
            b"mcp:key:hash1",
            b"mcp:key:hash2"
        ]

        # Mock key data
        def mock_hgetall(key):
            if key == b"mcp:key:hash1":
                return {
                    b"role": b"admin",
                    b"status": b"active",
                    b"created_at": b"1678886400",
                    b"description": b"Admin key"
                }
            elif key == b"mcp:key:hash2":
                return {
                    b"role": b"feeder",
                    b"status": b"revoked",
                    b"created_at": b"1678886300",
                    b"revoked_at": b"1678886450",
                    b"description": b"Old feeder key"
                }
            return {}

        mock_redis.hgetall.side_effect = mock_hgetall

        manager = APIKeyManager(mock_redis)
        keys = manager.list_keys(include_revoked=True)

        # Should return all keys
        assert len(keys) == 2
        assert any(k["status"] == "revoked" for k in keys)


class TestLegacyKeyRegistration:
    """Test legacy MCP_API_KEY registration."""

    def test_register_legacy_key(self):
        """Test registering legacy API key."""
        mock_redis = Mock()
        mock_redis.hset = MagicMock()

        manager = APIKeyManager(mock_redis)
        legacy_key = "legacy-api-key-12345"

        manager.register_legacy_key(legacy_key, description="Legacy key")

        # Should have stored key in Redis
        assert mock_redis.hset.called

    def test_legacy_key_has_admin_permissions(self):
        """Test that legacy key gets admin permissions."""
        mock_redis = Mock()

        # Mock legacy key lookup
        mock_redis.hgetall.return_value = {
            b"role": b"admin",
            b"status": b"active",
            b"created_at": str(int(time.time())).encode(),
            b"description": b"Legacy key",
            b"legacy": b"true"
        }

        manager = APIKeyManager(mock_redis)
        legacy_key = "legacy-api-key-12345"

        result = manager.validate_key(legacy_key)

        assert result is not None
        assert result["role"] == "admin"
        assert "*" in result["permissions"]


class TestKeySuffix:
    """Test key suffix extraction for logging."""

    def test_get_key_suffix(self):
        """Test extracting last 8 chars for logging."""
        manager = APIKeyManager(Mock())

        test_key = "mcp_admin_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        suffix = manager.get_key_suffix(test_key)

        assert suffix == "90abcdef"
        assert len(suffix) == 8

    def test_get_key_suffix_short_key(self):
        """Test suffix extraction for short keys."""
        manager = APIKeyManager(Mock())

        short_key = "mcp_adm"
        suffix = manager.get_key_suffix(short_key)

        assert suffix == "mcp_adm"  # Returns full key if too short


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
