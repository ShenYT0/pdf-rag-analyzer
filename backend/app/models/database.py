"""
Database Connection Management - Neo4j and Milvus connection, initialization, and lifecycle management
"""

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from pymilvus import MilvusClient, DataType
from app.core.config import get_settings
from app.core.logger import logger
from typing import Optional


# ────────────────── Neo4j Connection Management ──────────────────

class Neo4jConnection:
    """Neo4j async connection manager"""

    _instance: Optional["Neo4jConnection"] = None
    _driver: Optional[AsyncDriver] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Establish Neo4j connection"""
        settings = get_settings()
        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            # Verify connection
            async with self._driver.session() as session:
                await session.run("RETURN 1")
            logger.info("Neo4j connected successfully: %s", settings.NEO4J_URI)
        except Exception as e:
            logger.error("Neo4j connection failed: %s", str(e))
            raise

    async def close(self) -> None:
        """Close Neo4j connection"""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    def get_session(self) -> AsyncSession:
        """Get a new async session"""
        if not self._driver:
            raise RuntimeError("Neo4j is not connected, please call connect() first")
        return self._driver.session()

    async def is_connected(self) -> bool:
        """Check connection status"""
        if not self._driver:
            return False
        try:
            async with self._driver.session() as session:
                result = await session.run("RETURN 1")
                await result.consume()
            return True
        except Exception:
            return False


# ────────────────── Milvus Connection Management ──────────────────

class MilvusConnection:
    """Milvus connection manager"""

    _instance: Optional["MilvusConnection"] = None
    _client: Optional[MilvusClient] = None

    # Collection name constant
    COLLECTION_NAME = "pdf_chunks"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> None:
        """Establish Milvus connection"""
        settings = get_settings()
        try:
            self._client = MilvusClient(
                uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
            )
            logger.info(
                "Milvus connected successfully: %s:%s",
                settings.MILVUS_HOST,
                settings.MILVUS_PORT,
            )
        except Exception as e:
            logger.error("Milvus connection failed: %s", str(e))
            raise

    def close(self) -> None:
        """Close Milvus connection"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Milvus connection closed")

    def get_client(self) -> MilvusClient:
        """Get Milvus client instance"""
        if not self._client:
            raise RuntimeError("Milvus is not connected, please call connect() first")
        return self._client

    def is_connected(self) -> bool:
        """Check connection status"""
        if not self._client:
            return False
        try:
            self._client.list_collections()
            return True
        except Exception:
            return False

    def ensure_collection(self) -> None:
        """Ensure the collection exists, create if it does not"""
        settings = get_settings()
        client = self.get_client()

        if self.COLLECTION_NAME in client.list_collections():
            logger.info("Milvus collection '%s' already exists", self.COLLECTION_NAME)
            return

        # Define schema
        schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(
            field_name="chunk_id",
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=128,
        )
        schema.add_field(
            field_name="embedding",
            datatype=DataType.FLOAT_VECTOR,
            dim=settings.EMBEDDING_DIMENSION,
        )
        schema.add_field(
            field_name="content",
            datatype=DataType.VARCHAR,
            max_length=65535,
        )
        schema.add_field(
            field_name="file_id",
            datatype=DataType.VARCHAR,
            max_length=128,
        )

        # Create index parameters
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        # chunk_id is a VARCHAR primary key, no separate index required, Milvus handles it automatically

        # Create collection
        client.create_collection(
            collection_name=self.COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Milvus collection '%s' created successfully", self.COLLECTION_NAME)


# ────────────────── Global Singletons ──────────────────

neo4j_conn = Neo4jConnection()
milvus_conn = MilvusConnection()