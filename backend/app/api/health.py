"""
Health Check API - Checks system and component running status
"""

from fastapi import APIRouter

from app.core.logger import logger
from app.models.database import neo4j_conn, milvus_conn
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the system running status and checks connectivity to Neo4j and Milvus",
)
async def health_check():
    """Health check endpoint"""
    # Check Neo4j connectivity
    neo4j_ok = False
    try:
        neo4j_ok = await neo4j_conn.is_connected()
    except Exception as e:
        logger.warning("Health check - Neo4j connection error: %s", str(e))

    # Check Milvus connectivity
    milvus_ok = False
    try:
        milvus_ok = milvus_conn.is_connected()
    except Exception as e:
        logger.warning("Health check - Milvus connection error: %s", str(e))

    # Determine overall status
    overall_status = "ok" if (neo4j_ok and milvus_ok) else "degraded"

    return HealthResponse(
        status=overall_status,
        neo4j_connected=neo4j_ok,
        milvus_connected=milvus_ok,
    )