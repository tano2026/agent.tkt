"""
RAG Knowledge Base — ChromaDB vector search cho ABTrip.

Cung cấp semantic search trên:
- Chính sách hãng bay (hành lý, đổi vé, hủy vé, giấy tờ)
- Câu trả lời mẫu (FAQ)
- Kiến thức hàng không

Seed: python -c "from app.services.rag_knowledge import seed_knowledge; seed_knowledge()"
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLLECTION_NAME = "abtrip_knowledge"
CHROMA_DIR = "data/chroma"  # relative to backend/

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_rag: "RAGKnowledge | None" = None


def get_rag() -> "RAGKnowledge":
    global _rag
    if _rag is None:
        _rag = RAGKnowledge()
    return _rag


def reset_rag():
    global _rag
    _rag = None


# ---------------------------------------------------------------------------
# RAG Knowledge class
# ---------------------------------------------------------------------------


class RAGKnowledge:
    """Vector knowledge base for ABTrip aviation domain."""

    def __init__(self, persist_dir: str = CHROMA_DIR):
        self.ef = ONNXMiniLM_L6_V2()
        self.client = chromadb.PersistentClient(path=persist_dir)

        # Create or get collection
        try:
            self.collection = self.client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=self.ef,
            )
            self._count = self.collection.count()
            logger.info("RAG: loaded collection '%s' with %d docs", COLLECTION_NAME, self._count)
        except (ValueError, chromadb.errors.NotFoundError):
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.ef,
            )
            self._count = 0
            logger.info("RAG: created empty collection '%s'", COLLECTION_NAME)

    @property
    def count(self) -> int:
        return self._count

    def seed(self, documents: list[dict[str, Any]]):
        """Seed knowledge base with documents.
        
        Each doc: {"id": str, "content": str, "metadata": dict}
        """
        existing_ids = set(self.collection.get()["ids"]) if self._count > 0 else set()

        new_docs = [d for d in documents if d["id"] not in existing_ids]
        if not new_docs:
            logger.info("RAG seed: all %d docs already exist, skipping", len(documents))
            return

        self.collection.add(
            ids=[d["id"] for d in new_docs],
            documents=[d["content"] for d in new_docs],
            metadatas=[d["metadata"] for d in new_docs],
        )
        self._count = self.collection.count()
        logger.info("RAG seeded: added %d new docs (total: %d)", len(new_docs), self._count)

    def query(self, query: str, n_results: int = 3) -> list[dict]:
        """Search knowledge base for relevant context."""
        if self._count == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, self._count),
        )

        docs = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                docs.append({
                    "content": doc,
                    "metadata": metadata,
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })
        return docs

    def format_context(self, query: str, n_results: int = 3) -> str:
        """Query RAG and return formatted context string for prompt injection."""
        docs = self.query(query, n_results=n_results)
        if not docs:
            return ""

        ctx_parts = []
        for i, d in enumerate(docs, 1):
            tag = d["metadata"].get("tag", "")
            header = f"[{i}] {tag}" if tag else f"[{i}]"
            ctx_parts.append(f"{header}\n{d['content']}")

        return "THÔNG TIN TRA CỨU:\n" + "\n---\n".join(ctx_parts)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def _build_documents() -> list[dict[str, Any]]:
    """Build seed documents from aviation_db knowledge."""
    from app.services.aviation_db import POLICIES

    docs = []

    # ── Chính sách hành lý ─────────────────────────────────────────
    baggage_content = "CHÍNH SÁCH HÀNH LÝ:\n"
    for airline, text in POLICIES.get("hành lý", {}).items():
        if airline == "chung":
            baggage_content += f"\nLưu ý chung: {text}"
        else:
            baggage_content += f"\n- {airline}: {text}"
    docs.append({
        "id": "policy_baggage",
        "content": baggage_content,
        "metadata": {"tag": "🧳 Hành lý", "topic": "baggage"},
    })

    # ── Chính sách đổi vé ──────────────────────────────────────────
    change_content = "CHÍNH SÁCH ĐỔI VÉ:\n"
    for airline, text in POLICIES.get("đổi vé", {}).items():
        if airline == "chung":
            change_content += f"\nLưu ý chung: {text}"
        else:
            change_content += f"\n- {airline}: {text}"
    docs.append({
        "id": "policy_change",
        "content": change_content,
        "metadata": {"tag": "🔄 Đổi vé", "topic": "change"},
    })

    # ── Chính sách hủy vé ──────────────────────────────────────────
    cancel_content = "CHÍNH SÁCH HỦY VÉ:\n"
    for airline, text in POLICIES.get("hủy vé", {}).items():
        if airline == "chung":
            cancel_content += f"\nLưu ý chung: {text}"
        else:
            cancel_content += f"\n- {airline}: {text}"
    docs.append({
        "id": "policy_cancel",
        "content": cancel_content,
        "metadata": {"tag": "❌ Hủy vé", "topic": "cancel"},
    })

    # ── Giấy tờ thủ tục ────────────────────────────────────────────
    doc_content = "GIẤY TỜ & THỦ TỤC SÂN BAY:\n"
    for subtype, text in POLICIES.get("giấy tờ", {}).items():
        doc_content += f"\n- {subtype}: {text}"
    docs.append({
        "id": "policy_documents",
        "content": doc_content,
        "metadata": {"tag": "📋 Giấy tờ", "topic": "documents"},
    })

    # ── Thông tin mẹo bay ──────────────────────────────────────────
    docs.append({
        "id": "tip_checkin",
        "content": """MẸO CHECK-IN:
- Check-in online: mở 24h trước giờ bay, đóng 1h trước giờ bay (nội địa) hoặc 2h (quốc tế)
- Quầy sân bay: mở 3h trước giờ bay (quốc tế) hoặc 1.5h (nội địa)
- Nên check-in online để chọn chỗ ngồi đẹp
- Vé máy bay điện tử: chỉ cần mang CMND/CCCD ra sân bay""",
        "metadata": {"tag": "⏰ Check-in", "topic": "tip"},
    })

    docs.append({
        "id": "tip_booking",
        "content": """MẸO ĐẶT VÉ GIÁ RẺ:
- Đặt trước 2-4 tuần để có giá tốt nhất
- Bay ngày thường (thứ 3,4,5) rẻ hơn cuối tuần
- Tránh giờ cao điểm (6-8h sáng, 17-19h chiều)
- Vé khứ hồi thường rẻ hơn mua 2 vé một chiều
- Đặt qua ABTrip luôn có giá tốt hơn đặt trực tiếp hãng""",
        "metadata": {"tag": "💸 Mẹo rẻ", "topic": "tip"},
    })

    docs.append({
        "id": "tip_luggage",
        "content": """MẸO HÀNH LÝ:
- Chất lỏng: tối đa 100ml/lọ, để trong túi trong suốt (hành lý xách tay)
- Pin dự phòng, sạc dự phòng: KHÔNG được bỏ vào hành lý ký gửi
- Vật sắc nhọn (kéo, dao): chỉ bỏ hành lý ký gửi
- Hành lý quá cước: mua thêm online rẻ hơn tại sân bay 30-50%
- Mỗi hãng có quy định riêng về kích thước hành lý xách tay""",
        "metadata": {"tag": "🎒 Mẹo hành lý", "topic": "tip"},
    })

    # ── Fast Track VIP ─────────────────────────────────────────────
    docs.append({
        "id": "service_fasttrack",
        "content": """DỊCH VỤ FAST TRACK SÂN BAY:
- Fast Track Nội Bài (HAN): ưu tiên làm thủ tục + soi chiếu riêng, có nhân viên đón tận nơi 24/7
- Fast Track Tân Sơn Nhất (SGN): ưu tiên làm thủ tục + làn riêng
- Fast Track Đà Nẵng (DAD): ưu tiên làm thủ tục
- VIP B: phòng chờ lounge + xe đưa tận chân máy bay
- Liên hệ 0869.320.320 để đặt trước""",
        "metadata": {"tag": "⚡ Fast Track", "topic": "service"},
    })

    # ── eSIM ────────────────────────────────────────────────────────
    docs.append({
        "id": "service_esim",
        "content": """DỊCH VỤ eSIM DU LỊCH:
- Phủ sóng 200+ quốc gia
- 5 khu vực chính: Châu Á, Châu Âu, Bắc Mỹ, Châu Đại Dương, Toàn cầu
- Cài đặt đơn giản, chỉ cần điện thoại hỗ trợ eSIM
- Giá từ 30.000đ/ngày tùy khu vực
- Không cần tháo SIM vật lý, giữ số Việt Nam để liên lạc""",
        "metadata": {"tag": "📱 eSIM", "topic": "service"},
    })

    # ── Visa ────────────────────────────────────────────────────────
    docs.append({
        "id": "service_visa",
        "content": """DỊCH VỤ VISA:
- Hỗ trợ visa 8 quốc gia: Trung Quốc, Nhật Bản, Hàn Quốc, Ấn Độ, UAE, Thổ Nhĩ Kỳ, Campuchia, Thái Lan
- Dịch vụ trọn gói: tư vấn, dịch thuật, nộp hồ sơ, nhận kết quả
- Thời gian xử lý: 3-7 ngày làm việc tùy quốc gia""",
        "metadata": {"tag": "🛂 Visa", "topic": "service"},
    })

    # ── Hộ chiếu ────────────────────────────────────────────────────
    docs.append({
        "id": "service_passport",
        "content": """DỊCH VỤ HỘ CHIẾU:
- Cấp mới hộ chiếu Việt Nam (thủ tục 5-7 ngày)
- Cấp nhanh hộ chiếu (2-3 ngày)
- Gia hạn hộ chiếu
- Hỗ trợ làm hồ sơ, chụp ảnh, nộp và nhận tận nơi""",
        "metadata": {"tag": "📘 Hộ chiếu", "topic": "service"},
    })

    return docs


def seed_knowledge():
    """Seed the knowledge base with default aviation knowledge."""
    rag = get_rag()
    docs = _build_documents()
    rag.seed(docs)
    print(f"✅ Seeded {len(docs)} documents. Total: {rag.count}")
    return rag.count
