"""
RAG Service — Vector search for aviation knowledge.

Uses ChromaDB with local embedding model to index airports, airlines,
policies, and aviation rules. On query, returns relevant documents
as context for the LLM.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

logger = logging.getLogger(__name__)

# ─── Paths ───────────────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BACKEND_DIR, ".chroma")

# ─── Collection names ────────────────────────────────────────────────────────
COLL_AVIATION = "aviation_kb"


# ─── Custom embedding function (ONNX all-MiniLM-L6-v2) ───────────────────────
# Chroma ships its own ONNX-based embedding. We override to use the same model
# but expose the class properly.
class MiniLMEmbedding(EmbeddingFunction):
    """Wrapper around Chroma's default ONNX embedding for type safety."""

    _model = None

    def __call__(self, texts: Documents) -> Embeddings:
        if self._model is None:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            self._model = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        return self._model(texts)


# ─── RAG Service ─────────────────────────────────────────────────────────────


class RagService:
    """Retrieval-Augmented Generation service for aviation knowledge."""

    def __init__(self, persist: bool = True) -> None:
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        self._embed_fn = MiniLMEmbedding()
        self._persist = persist
        self._ready = False

    # ── Setup ────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Create Chroma client + collection, seed if empty."""
        try:
            settings = chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=False,
            )
            if self._persist:
                self._client = chromadb.PersistentClient(
                    path=CHROMA_DIR, settings=settings
                )
            else:
                self._client = chromadb.EphemeralClient(settings=settings)

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=COLL_AVIATION,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )

            # Seed if empty
            count = self._collection.count()
            if count == 0:
                logger.info("Chroma collection empty — seeding aviation knowledge...")
                self._seed()
                logger.info("Seeded %d documents.", self._collection.count())
            else:
                logger.info("Chroma ready with %d documents.", count)

            self._ready = True
        except Exception as exc:
            logger.warning("Chroma init failed (will run without RAG): %s", exc)
            self._ready = False

    # ── Seed data ────────────────────────────────────────────────────────

    def _seed(self) -> None:
        """Index aviation data from aviation_db.py into Chroma."""
        from app.services.aviation_db import AIRPORTS, AIRLINES

        docs: list[dict[str, Any]] = []

        # ── Airports ─────────────────────────────────────────────────────
        for code, info in AIRPORTS.items():
            aliases = ", ".join(info.get("aliases", []))
            location = "Việt Nam" if info.get("vietnam") else "Quốc tế"
            docs.append({
                "text": (
                    f"Sân bay {info['name']} (IATA: {code}). "
                    f"Thành phố: {info['city']}. "
                    f"Vị trí: {location}. "
                    f"Tên gọi khác: {aliases}."
                ),
                "metadata": {
                    "type": "airport",
                    "code": code,
                    "city": info["city"],
                    "vietnam": info.get("vietnam", False),
                },
            })

        # ── Airlines + policies ─────────────────────────────────────────
        for code, info in AIRLINES.items():
            policy = info.get("policy", {})
            baggage = policy.get("baggage", {})
            docs.append({
                "text": (
                    f"Hãng bay {info['name']} (mã IATA: {code}). "
                    f"Tên đầy đủ: {info.get('full_name', info['name'])}. "
                    f"Chính sách hành lý: "
                    f"Ký gửi: {baggage.get('checked', 'Liên hệ hãng')}. "
                    f"Xách tay: {baggage.get('carry_on', 'Liên hệ hãng')}. "
                    f"Phí đổi vé: {policy.get('change_fee', 'Liên hệ hãng')}. "
                    f"Phí hủy: {policy.get('cancel', 'Liên hệ hãng')}. "
                    f"Check-in: {policy.get('checkin', 'Liên hệ hãng')}. "
                    f"Suất ăn: {policy.get('meal', 'Liên hệ hãng')}."
                ),
                "metadata": {
                    "type": "airline",
                    "code": code,
                    "name": info["name"],
                },
            })

            # Also add individual policy items as separate docs
            for policy_key, policy_value in policy.items():
                if isinstance(policy_value, dict):
                    for sub_key, sub_val in policy_value.items():
                        docs.append({
                            "text": (
                                f"Hãng {info['name']} ({code}): "
                                f"{_policy_label(policy_key, sub_key)}: {sub_val}."
                            ),
                            "metadata": {
                                "type": "policy",
                                "airline_code": code,
                                "airline_name": info["name"],
                                "category": policy_key,
                                "subcategory": sub_key,
                            },
                        })
                else:
                    docs.append({
                        "text": (
                            f"Hãng {info['name']} ({code}): "
                            f"{_policy_label(policy_key)}: {policy_value}."
                        ),
                        "metadata": {
                            "type": "policy",
                            "airline_code": code,
                            "airline_name": info["name"],
                            "category": policy_key,
                        },
                    })

        # Add to Chroma
        ids = [f"doc-{i}" for i in range(len(docs))]
        texts = [d["text"] for d in docs]
        metadatas = [d["metadata"] for d in docs]
        self._collection.add(documents=texts, metadatas=metadatas, ids=ids)

    # ── Query ────────────────────────────────────────────────────────────

    def query(self, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search aviation knowledge, return relevant documents."""
        if not self._ready or not self._collection:
            return []

        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=top_k,
            )
            docs = []
            if results.get("documents"):
                for i, doc_list in enumerate(results["documents"]):
                    for j, doc in enumerate(doc_list):
                        meta = {}
                        if results.get("metadatas"):
                            meta = results["metadatas"][i][j]
                        docs.append({
                            "text": doc,
                            "metadata": meta,
                            "distance": results["distances"][i][j]
                            if results.get("distances")
                            else 0.0,
                        })
            return docs
        except Exception as exc:
            logger.warning("Chroma query failed: %s", exc)
            return []

    def format_context(self, query_text: str, top_k: int = 5) -> str:
        """Query and format results as a context string for LLM prompts."""
        docs = self.query(query_text, top_k=top_k)
        if not docs:
            return ""

        lines = ["Dưới đây là thông tin tra cứu được — hãy dùng để trả lời chính xác:\n"]
        for i, doc in enumerate(docs):
            meta = doc.get("metadata", {})
            prefix = ""
            if meta.get("type") == "airport":
                prefix = f"📍 Sân bay {meta.get('code', '')}:"
            elif meta.get("type") == "airline":
                prefix = f"✈️ Hãng {meta.get('name', '')}:"
            elif meta.get("type") == "policy":
                prefix = f"📋 {meta.get('airline_name', '')} - {meta.get('category', '')}:"
            lines.append(f"{i+1}. {prefix} {doc['text']}")
        return "\n".join(lines)

    # ── Cleanup ──────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Tear down Chroma client."""
        if self._client:
            self._client = None
            self._ready = False


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _policy_label(category: str, subcategory: str | None = None) -> str:
    """Map policy keys to readable Vietnamese labels."""
    labels = {
        "baggage": "Hành lý",
        "checked": "Ký gửi",
        "carry_on": "Xách tay",
        "change_fee": "Phí đổi vé",
        "cancel": "Phí hủy",
        "checkin": "Check-in",
        "meal": "Suất ăn",
    }
    if subcategory:
        return f"{labels.get(category, category)} - {labels.get(subcategory, subcategory)}"
    return labels.get(category, category)


# ─── Singleton ───────────────────────────────────────────────────────────────

_service: RagService | None = None
_initialized = False


def get_rag_service() -> RagService | None:
    """Get or create the singleton RAG service."""
    global _service, _initialized
    if not _initialized:
        _service = RagService(persist=True)
        _initialized = True
    return _service


async def init_rag() -> None:
    """Initialize RAG (called at app startup)."""
    svc = get_rag_service()
    if svc:
        await svc.initialize()


async def close_rag() -> None:
    """Close RAG service (called at app shutdown)."""
    global _service, _initialized
    if _service:
        await _service.close()
        _service = None
        _initialized = False
