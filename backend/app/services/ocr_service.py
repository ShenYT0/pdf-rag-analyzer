"""
OCR Service - Extracts text from PDF files
Auto-detects backend based on API key:
  - API key == "ollama" → langchain_ollama.ChatOllama (local multimodal)
  - otherwise           → langchain_openai.ChatOpenAI (online multimodal)
"""

import base64
import io
import asyncio
from typing import Optional

import fitz  # PyMuPDF

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import get_settings
from app.core.logger import logger


def _is_ollama(api_key: str) -> bool:
    """Return True when the API key signals a local Ollama backend."""
    return api_key.strip().lower() == "ollama"


def _strip_v1(url: str) -> str:
    """
    langchain_ollama expects the bare Ollama host (e.g. http://localhost:11434),
    not the OpenAI-compat path (http://localhost:11434/v1).
    """
    return url.rstrip("/").removesuffix("/v1")


def _build_ocr_llm(model: str, api_key: str, base_url: str) -> BaseChatModel:
    """
    Factory: return the appropriate LangChain chat model for OCR.

    Args:
        model:    Model name
        api_key:  API key
        base_url: Base URL from config

    Returns:
        A LangChain BaseChatModel instance
    """
    if _is_ollama(api_key):
        from langchain_ollama import ChatOllama
        ollama_url = _strip_v1(base_url)
        logger.info("OCR backend: Ollama  model=%s  base_url=%s", model, ollama_url)
        return ChatOllama(
            model=model,
            base_url=ollama_url,
            temperature=0.0,
            num_predict=4096,
        )
    else:
        from langchain_openai import ChatOpenAI
        logger.info("OCR backend: OpenAI-compatible  model=%s  base_url=%s", model, base_url)
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
            max_tokens=4096,
            timeout=120,
        )


class OCRService:
    """
    PDF OCR text extraction service.
    Automatically selects langchain_ollama or langchain_openai based on the
    OCR_API_KEY value in .env.
    """

    def __init__(self):
        settings = get_settings()
        self._model = settings.OCR_MODEL
        self._llm: BaseChatModel = _build_ocr_llm(
            model=settings.OCR_MODEL,
            api_key=settings.OCR_API_KEY,
            base_url=settings.OCR_BASE_URL,
        )

    async def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """
        Extract all text from a PDF byte stream.

        Priority: use PyMuPDF for direct extraction first; fall back to multimodal OCR
        if a page has too little text.

        Args:
            file_bytes: PDF file binary content

        Returns:
            All extracted text
        """
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text_parts: list[str] = []

        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]

                # First attempt direct text extraction
                text = page.get_text("text").strip()

                if len(text) >= 50:
                    # Sufficient text, use directly
                    all_text_parts.append(text)
                else:
                    # Too little text, likely a scanned document, use multimodal OCR
                    logger.info("Page %d has insufficient text, enabling OCR", page_idx + 1)
                    ocr_text = await self._ocr_page(page, page_idx + 1)
                    if ocr_text:
                        all_text_parts.append(ocr_text)

            full_text = "\n\n".join(all_text_parts)
            logger.info("PDF text extraction complete, total_chars: %d", len(full_text))
            return full_text

        finally:
            doc.close()

    async def _ocr_page(self, page: fitz.Page, page_num: int) -> Optional[str]:
        """
        Perform OCR on a single page using multimodal LLM.

        Args:
            page: PyMuPDF Page object
            page_num: Page number

        Returns:
            OCR extracted text
        """
        try:
            # Render page as PNG image
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")

            # Build multimodal messages
            messages = [
                SystemMessage(
                    content="You are a professional OCR assistant. "
                    "Please accurately extract all text content from the image, "
                    "preserving the original formatting."
                ),
                HumanMessage(
                    content=[
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": "Please extract all text content from this page.",
                        },
                    ]
                ),
            ]

            response = await self._llm.ainvoke(messages)
            result = response.content if hasattr(response, "content") else str(response)

            logger.info("Page %d OCR complete, char_count: %d", page_num, len(result))
            return result

        except asyncio.TimeoutError:
            logger.warning("Page %d OCR timed out", page_num)
            return ""
        except Exception as e:
            logger.error("Page %d OCR failed: %s", page_num, str(e))
            return ""


# Global singleton
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """Get OCR service singleton"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service