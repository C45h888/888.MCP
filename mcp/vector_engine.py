"""
Vector Engine - Lightweight abstraction for external vector databases.

Provides adapter pattern for swapping vector DB backends (Pinecone, Weaviate, Upstash).
NO heavy ML dependencies - all embedding/search happens via external APIs.

Design:
- Abstract base class: VectorEngine
- MockVectorEngine: Returns fake results for testing/dev
- RemoteVectorEngine: Generic HTTP adapter for external vector DBs
- Factory: get_vector_engine() reads env vars and returns correct engine
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class VectorEngine(ABC):
    """
    Abstract base class for vector database adapters.

    All implementations must support semantic search via the search() method.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search over vector database.

        Args:
            query: Natural language search query
            limit: Maximum number of results to return (default 5)
            min_score: Minimum similarity score threshold (0.0-1.0)
            filters: Optional metadata filters (e.g., {"pair": "BTC-ETH"})

        Returns:
            List of search results, each containing:
                - id: Document ID
                - score: Similarity score (0.0-1.0)
                - text: Document text
                - metadata: Document metadata (timestamp, source, etc.)
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if vector database is accessible.

        Returns:
            True if healthy, False otherwise
        """
        pass


class MockVectorEngine(VectorEngine):
    """
    Mock vector engine for testing and development.

    Returns fake search results without requiring external dependencies.
    Safe for local testing and CI environments.
    """

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Return mock search results for testing.

        Generates synthetic results based on query keywords.
        """
        logger.info(f"MockVectorEngine search: query='{query}', limit={limit}")

        # Generate mock results
        mock_results = [
            {
                "id": f"doc_{i}",
                "score": 0.95 - (i * 0.1),
                "text": f"Mock document {i} about {query}",
                "metadata": {
                    "source": "mock_data",
                    "timestamp": 1678886400 + i,
                    "pair": "BTC-ETH"
                }
            }
            for i in range(min(limit, 3))  # Return max 3 mock results
        ]

        # Filter by min_score
        results = [r for r in mock_results if r["score"] >= min_score]

        logger.info(f"MockVectorEngine returned {len(results)} results")
        return results

    async def health_check(self) -> bool:
        """Mock engine is always healthy."""
        return True


class RemoteVectorEngine(VectorEngine):
    """
    Generic HTTP adapter for remote vector databases.

    Supports:
    - Pinecone: Set VECTOR_DB_TYPE=pinecone
    - Weaviate: Set VECTOR_DB_TYPE=weaviate
    - Upstash: Set VECTOR_DB_TYPE=upstash
    - Custom: Set VECTOR_DB_TYPE=custom with VECTOR_DB_URL

    Uses httpx for async HTTP calls to external vector DB APIs.
    NO local embedding models - assumes vector DB handles embedding internally.
    """

    def __init__(
        self,
        db_type: str,
        db_url: str,
        api_key: Optional[str] = None,
        timeout: int = 10
    ):
        """
        Initialize remote vector engine.

        Args:
            db_type: Vector DB type (pinecone, weaviate, upstash, custom)
            db_url: Vector DB endpoint URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds (default 10)
        """
        self.db_type = db_type.lower()
        self.db_url = db_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # Configure headers based on DB type
        self.headers = self._build_headers()

        logger.info(
            f"RemoteVectorEngine initialized: type={self.db_type}, url={self.db_url}"
        )

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for vector DB requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MCP-Server/1.0.0"
        }

        if self.api_key:
            if self.db_type == "pinecone":
                headers["Api-Key"] = self.api_key
            elif self.db_type == "weaviate":
                headers["Authorization"] = f"Bearer {self.api_key}"
            elif self.db_type == "upstash":
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                # Generic API key header for custom backends
                headers["X-API-Key"] = self.api_key

        return headers

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search via remote vector DB API.

        Sends query to vector DB endpoint and parses response.
        Assumes vector DB handles embedding generation internally.
        """
        logger.info(
            f"RemoteVectorEngine search: query='{query}', limit={limit}, db_type={self.db_type}"
        )

        # Build request payload (format depends on DB type)
        payload = self._build_search_payload(query, limit, min_score, filters)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.db_url}/search",
                    json=payload,
                    headers=self.headers
                )

                response.raise_for_status()
                data = response.json()

                # Parse response based on DB type
                results = self._parse_search_response(data)

                logger.info(f"RemoteVectorEngine returned {len(results)} results")
                return results

        except httpx.HTTPError as e:
            logger.error(f"Vector DB search failed: {e}")
            raise ValueError(f"Vector DB search failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during vector search: {e}")
            raise ValueError(f"Vector search error: {str(e)}")

    def _build_search_payload(
        self,
        query: str,
        limit: int,
        min_score: float,
        filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build search request payload based on DB type.

        Different vector DBs have different API formats.
        This method normalizes our internal format to their expected format.
        """
        if self.db_type == "pinecone":
            # Pinecone query format
            return {
                "query": query,
                "top_k": limit,
                "include_metadata": True,
                "filter": filters or {}
            }

        elif self.db_type == "weaviate":
            # Weaviate GraphQL-like format
            return {
                "query": query,
                "limit": limit,
                "certainty": min_score,
                "where": filters or {}
            }

        elif self.db_type == "upstash":
            # Upstash vector format
            return {
                "query": query,
                "topK": limit,
                "includeMetadata": True,
                "filter": filters or {}
            }

        else:
            # Generic format for custom backends
            return {
                "query": query,
                "limit": limit,
                "min_score": min_score,
                "filters": filters or {}
            }

    def _parse_search_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse search response based on DB type.

        Normalizes different vector DB response formats to our internal format.
        """
        results = []

        if self.db_type == "pinecone":
            # Pinecone returns: {"matches": [{"id": ..., "score": ..., "metadata": ...}]}
            matches = data.get("matches", [])
            for match in matches:
                results.append({
                    "id": match.get("id"),
                    "score": match.get("score", 0.0),
                    "text": match.get("metadata", {}).get("text", ""),
                    "metadata": match.get("metadata", {})
                })

        elif self.db_type == "weaviate":
            # Weaviate returns: {"data": {"Get": {"Document": [...]}}}
            documents = data.get("data", {}).get("Get", {}).get("Document", [])
            for doc in documents:
                results.append({
                    "id": doc.get("_additional", {}).get("id"),
                    "score": doc.get("_additional", {}).get("certainty", 0.0),
                    "text": doc.get("text", ""),
                    "metadata": {k: v for k, v in doc.items() if not k.startswith("_")}
                })

        elif self.db_type == "upstash":
            # Upstash returns: {"results": [{"id": ..., "score": ..., "metadata": ...}]}
            items = data.get("results", [])
            for item in items:
                results.append({
                    "id": item.get("id"),
                    "score": item.get("score", 0.0),
                    "text": item.get("metadata", {}).get("text", ""),
                    "metadata": item.get("metadata", {})
                })

        else:
            # Generic format (assume already normalized)
            results = data.get("results", [])

        return results

    async def health_check(self) -> bool:
        """Check if vector DB is accessible via health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # Try common health check endpoints
                health_endpoints = ["/health", "/healthz", "/ping", "/_health"]

                for endpoint in health_endpoints:
                    try:
                        response = await client.get(
                            f"{self.db_url}{endpoint}",
                            headers=self.headers
                        )
                        if response.status_code == 200:
                            logger.info(f"Vector DB health check passed: {endpoint}")
                            return True
                    except httpx.HTTPError:
                        continue

                logger.warning("Vector DB health check failed: no valid health endpoint")
                return False

        except Exception as e:
            logger.error(f"Vector DB health check error: {e}")
            return False


# Factory function

def get_vector_engine() -> VectorEngine:
    """
    Factory function to create vector engine based on environment variables.

    Environment variables:
        - VECTOR_DB_TYPE: Engine type (mock, pinecone, weaviate, upstash, custom)
        - VECTOR_DB_URL: Vector DB endpoint URL (required for remote engines)
        - VECTOR_DB_API_KEY: API key for authentication (optional)

    Returns:
        VectorEngine instance (MockVectorEngine or RemoteVectorEngine)

    Raises:
        ValueError: If configuration is invalid
    """
    db_type = os.getenv("VECTOR_DB_TYPE", "mock").lower()
    db_url = os.getenv("VECTOR_DB_URL", "")
    api_key = os.getenv("VECTOR_DB_API_KEY")

    # Mock engine (default for dev/testing)
    if db_type == "mock" or not db_type:
        logger.info("Using MockVectorEngine (dev/test mode)")
        return MockVectorEngine()

    # Remote engine (Pinecone, Weaviate, Upstash, custom)
    if db_type in ["pinecone", "weaviate", "upstash", "custom"]:
        if not db_url:
            raise ValueError(
                f"VECTOR_DB_URL required for {db_type} engine. "
                "Set VECTOR_DB_URL environment variable."
            )

        logger.info(f"Using RemoteVectorEngine: type={db_type}")
        return RemoteVectorEngine(
            db_type=db_type,
            db_url=db_url,
            api_key=api_key
        )

    # Invalid type
    raise ValueError(
        f"Invalid VECTOR_DB_TYPE: {db_type}. "
        "Valid types: mock, pinecone, weaviate, upstash, custom"
    )
