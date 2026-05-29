"""
PDF Upload API - Receives PDF files and executes the complete knowledge graph construction pipeline
"""

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.config import get_settings
from app.core.logger import logger
from app.models.schemas import PDFUploadResponse, PDFListResponse, DeleteAllResponse
from app.services.graph_rag_service import get_graph_rag_service

router = APIRouter(prefix="/v1/index", tags=["PDF Indexing"])


@router.get(
    "/pdfs",
    response_model=PDFListResponse,
    summary="Get Uploaded PDF List",
    description="Returns file info for all uploaded PDFs, including filename, upload time, chunk count, entity count, and relation count",
)
async def list_pdfs():
    """Get information list of all uploaded PDFs"""
    try:
        graph_rag = get_graph_rag_service()
        return await graph_rag.list_pdfs()
    except Exception as e:
        logger.error("Failed to get PDF list: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get PDF list: {str(e)}",
        )


@router.delete(
    "/pdfs",
    response_model=DeleteAllResponse,
    summary="Delete All PDFs and Database Data",
    description="Clears all uploaded PDF vector data (Milvus) and knowledge graph data (Neo4j)",
)
async def delete_all_pdfs():
    """Delete all PDF data, clear Milvus and Neo4j"""
    try:
        graph_rag = get_graph_rag_service()
        return await graph_rag.clear_all()
    except Exception as e:
        logger.error("Failed to delete all data: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete all data: {str(e)}",
        )


@router.post(
    "/pdf",
    response_model=PDFUploadResponse,
    summary="PDF Upload and Knowledge Graph Construction",
    description=(
        "Accepts a PDF file and executes the following pipeline:"
        "1. OCR text extraction → 2. Text chunking → 3. Vector embedding & Milvus storage "
        "→ 4. Triple extraction → 5. Knowledge graph storage to Neo4j"
    ),
)
async def upload_pdf(file: UploadFile = File(..., description="PDF file")):
    """
    PDF upload, OCR, and knowledge graph construction

    - Supports .pdf format files
    - Automatic text extraction, chunking, vectorization, and graph construction
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF format files are supported",
        )

    # Validate file size
    file_bytes = await file.read()
    settings = get_settings()
    if len(file_bytes) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE // (1024 * 1024)}MB limit",
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="File is empty",
        )

    logger.info("Received PDF upload: %s (%.2f MB)", file.filename, len(file_bytes) / (1024 * 1024))

    try:
        graph_rag = get_graph_rag_service()
        result = await graph_rag.process_pdf(file_bytes, file.filename)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("PDF processing error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(e)}",
        )