"""
LLM Service - Large Language Model invocation
Auto-detects backend based on API key:
  - API key == "ollama" → langchain_ollama.ChatOllama (local)
  - otherwise           → langchain_openai.ChatOpenAI (online/compatible)
Supports standard response and SSE streaming response.
"""

import json
from typing import AsyncGenerator, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

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


def _build_llm(model: str, api_key: str, base_url: str, temperature: float = 0.7, streaming: bool = False) -> BaseChatModel:
    """
    Factory: return the appropriate LangChain chat model instance.

    Args:
        model:       Model name
        api_key:     API key (use "ollama" to select the local Ollama backend)
        base_url:    Base URL from config
        temperature: Sampling temperature
        streaming:   Whether to enable streaming mode

    Returns:
        A LangChain BaseChatModel instance
    """
    if _is_ollama(api_key):
        from langchain_ollama import ChatOllama
        ollama_url = _strip_v1(base_url)
        logger.info(
            "LLM backend: Ollama  model=%s  base_url=%s  streaming=%s",
            model, ollama_url, streaming,
        )
        return ChatOllama(
            model=model,
            base_url=ollama_url,
            temperature=temperature,
            num_predict=4096,
        )
    else:
        from langchain_openai import ChatOpenAI
        logger.info(
            "LLM backend: OpenAI-compatible  model=%s  base_url=%s  streaming=%s",
            model, base_url, streaming,
        )
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=4096,
            timeout=120,
            streaming=streaming,
        )


class LLMService:
    """
    Large Language Model service.
    Automatically selects langchain_ollama or langchain_openai based on the
    LLM_API_KEY value in .env.
    """

    def __init__(self):
        settings = get_settings()
        self._model = settings.LLM_MODEL
        self._api_key = settings.LLM_API_KEY
        self._base_url = settings.LLM_BASE_URL

        # Non-streaming LLM instance (temperature 0.7 for normal chat)
        self._llm: BaseChatModel = _build_llm(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=0.7,
            streaming=False,
        )

        # Streaming LLM instance (temperature 0.7 for normal chat)
        self._llm_stream: BaseChatModel = _build_llm(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=0.7,
            streaming=True,
        )

        # Low-temperature LLM for deterministic tasks like triple extraction
        # (ChatOllama does not support .bind(temperature=...) so we create
        # a separate instance instead)
        self._llm_low_temp: BaseChatModel = _build_llm(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=0.1,
            streaming=False,
        )

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """
        Standard chat request, returns full response.

        Args:
            messages: List of messages [{"role": "...", "content": "..."}]
            temperature: Temperature parameter (only used for OpenAI backend)

        Returns:
            Model response text
        """
        try:
            lc_messages = self._dict_messages_to_langchain(messages)
            # Use .bind() only for OpenAI (ChatOllama doesn't support extra kwargs)
            llm = self._llm.bind(temperature=temperature) if not _is_ollama(self._api_key) else self._llm
            response = await llm.ainvoke(lc_messages)
            content = response.content if hasattr(response, "content") else str(response)
            logger.debug("LLM response complete, char_count=%d", len(content))
            return content

        except Exception as e:
            logger.error("LLM request failed: %s", str(e))
            raise RuntimeError(f"LLM service error: {str(e)}")

    async def chat_stream(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """
        Streaming chat request, yields response text fragments incrementally.

        Args:
            messages: List of messages
            temperature: Temperature parameter (only used for OpenAI backend)

        Yields:
            Text fragment (delta) of the model response
        """
        try:
            lc_messages = self._dict_messages_to_langchain(messages)
            llm = self._llm_stream.bind(temperature=temperature) if not _is_ollama(self._api_key) else self._llm_stream
            async for chunk in llm.astream(lc_messages):
                if chunk.content:
                    yield chunk.content

        except Exception as e:
            logger.error("LLM streaming request failed: %s", str(e))
            raise RuntimeError(f"LLM streaming service error: {str(e)}")

    async def extract_triples(self, text: str) -> list[dict]:
        """
        Extract knowledge graph triples (entity-relation-entity) from text.

        Uses LangChain ChatPromptTemplate + LCEL chain for structured extraction.

        Args:
            text: Input text

        Returns:
            List of triples [{"head": "...", "relation": "...", "tail": "..."}]
        """
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a professional knowledge graph construction assistant. "
                "Your task is to extract entity-relation triples from text. "
                "Return only a JSON array, do not include any explanation.",
            ),
            (
                "human",
                """Extract all knowledge graph triples (entity-relation-entity) from the following text.

Requirements:
1. Each triple contains head (head entity), relation (relation), tail (tail entity)
2. Entities should be specific nouns or noun phrases
3. Relations should be concise verbs or prepositional phrases
4. Return the result as a JSON array, do not include any other content
5. If no triples can be extracted, return an empty array []

Example format:
[{{"head": "Steve Jobs", "relation": "works at", "tail": "Apple"}}]

Text content:
{text}""",
            ),
        ])

        result_text = ""
        try:
            chain = prompt | self._llm_low_temp
            response = await chain.ainvoke({"text": text})
            result_text = response.content if hasattr(response, "content") else str(response)

            # Clean and parse JSON
            result_text = result_text.strip()
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1])

            triples = json.loads(result_text)

            if not isinstance(triples, list):
                logger.warning("LLM returned triples in incorrect format, returning empty list")
                return []

            valid_triples = []
            for t in triples:
                if isinstance(t, dict) and "head" in t and "relation" in t and "tail" in t:
                    valid_triples.append({
                        "head": str(t["head"]).strip(),
                        "relation": str(t["relation"]).strip(),
                        "tail": str(t["tail"]).strip(),
                    })

            logger.info("Extracted %d valid triples", len(valid_triples))
            return valid_triples

        except json.JSONDecodeError as e:
            logger.warning("Triple JSON parse failed: %s, raw response: %s", str(e), result_text[:200])
            return []
        except Exception as e:
            logger.error("Triple extraction failed: %s", str(e))
            return []

    @staticmethod
    def _dict_messages_to_langchain(messages: list[dict]) -> list:
        """
        Convert list of dict messages to LangChain message objects.

        Args:
            messages: List of {"role": "...", "content": "..."}

        Returns:
            List of LangChain BaseMessage objects
        """
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        return lc_messages


# Global singleton
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get LLM service singleton"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service