"""
System Statistics API - Returns Milvus vector count, Neo4j node/edge counts, and processed PDF count
"""

from fastapi import APIRouter, HTTPException

from app.core.logger import logger
from app.models.schemas import SystemStats
from app.services.graph_rag_service import get_graph_rag_service

router = APIRouter(prefix="/v1/system", tags=["System"])


@router.get(
    "/stats",
    response_model=SystemStats,
    summary="System Statistics",
    description=(
        "Returns the following statistics:"
        "- Total vector count in Milvus (Total Chunks)"
        "- Total node count (Nodes) and edge count (Edges) in Neo4j"
        "- Total number of processed PDF files"
    ),
)
async def get_system_stats():
    """Get system statistics"""
    try:
        graph_rag = get_graph_rag_service()
        stats = await graph_rag.get_system_stats()
        return stats
    except Exception as e:
        logger.error("Failed to get system stats: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system stats: {str(e)}",
        )