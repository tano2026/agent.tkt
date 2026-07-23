import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, List, Optional
import uuid

from app.services.conversation_memory import get_memory, ConversationMemory

logger = logging.getLogger(__name__)

class FlightWatcher:
    """
    Quản lý các yêu cầu canh vé máy bay.
    Sử dụng SQLite-backed ConversationMemory để lưu trữ dữ liệu canh vé.
    """
    def __init__(self, memory: ConversationMemory):
        self._memory = memory

    def create_flight_watch(
        self,
        session_id: str,
        original_flight_details: dict,
        search_params: dict,
        target_price_threshold: float = 5.0 # Mặc định 5%
    ) -> dict:
        """
        Tạo một yêu cầu canh vé mới.
        """
        watch_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat()
        
        # Lấy giá gốc từ original_flight_details
        original_price = original_flight_details.get("price")
        if original_price is None:
            raise ValueError("original_flight_details must contain 'price'")

        watch_data = {
            "watch_id": watch_id,
            "session_id": session_id,
            "original_flight_details": json.dumps(original_flight_details, ensure_ascii=False),
            "search_params": json.dumps(search_params, ensure_ascii=False),
            "target_price_threshold": target_price_threshold,
            "last_checked_price": original_price, # Ban đầu, giá thấp nhất đã thấy là giá gốc
            "last_check_time": current_time,
            "status": "active",
            "notify_on_new_price": 1, # Luôn thông báo
            "created_at": current_time,
            "updated_at": current_time,
        }

        conn = self._memory._conn
        try:
            conn.execute(
                """
                INSERT INTO flight_watches (
                    watch_id, session_id, original_flight_details, search_params,
                    target_price_threshold, last_checked_price, last_check_time,
                    status, notify_on_new_price, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    watch_data["watch_id"],
                    watch_data["session_id"],
                    watch_data["original_flight_details"],
                    watch_data["search_params"],
                    watch_data["target_price_threshold"],
                    watch_data["last_checked_price"],
                    watch_data["last_check_time"],
                    watch_data["status"],
                    watch_data["notify_on_new_price"],
                    watch_data["created_at"],
                    watch_data["updated_at"],
                ),
            )
            conn.commit()
            logger.info("Created flight watch %s for session %s", watch_id, session_id)
            return watch_data
        except sqlite3.Error as e:
            logger.error("Error creating flight watch: %s", e)
            conn.rollback()
            raise

    def get_active_watches(self) -> List[dict]:
        """
        Lấy tất cả các yêu cầu canh vé đang hoạt động.
        """
        conn = self._memory._conn
        cursor = conn.execute(
            "SELECT * FROM flight_watches WHERE status = 'active'"
        )
        watches = []
        for row in cursor.fetchall():
            watch = dict(row)
            watch["original_flight_details"] = json.loads(watch["original_flight_details"])
            watch["search_params"] = json.loads(watch["search_params"])
            watches.append(watch)
        return watches

    def update_watch_status(
        self,
        watch_id: str,
        status: str,
        last_checked_price: Optional[float] = None,
        last_check_time: Optional[str] = None,
    ) -> None:
        """
        Cập nhật trạng thái và thông tin của một yêu cầu canh vé.
        """
        conn = self._memory._conn
        set_clauses = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [status]
        if last_checked_price is not None:
            set_clauses.append("last_checked_price = ?")
            params.append(last_checked_price)
        if last_check_time is not None:
            set_clauses.append("last_check_time = ?")
            params.append(last_check_time)
        
        params.append(watch_id)

        try:
            conn.execute(
                f"""
                UPDATE flight_watches
                SET {", ".join(set_clauses)}
                WHERE watch_id = ?
                """,
                tuple(params),
            )
            conn.commit()
            logger.info("Updated flight watch %s with status %s", watch_id, status)
        except sqlite3.Error as e:
            logger.error("Error updating flight watch %s: %s", watch_id, e)
            conn.rollback()
            raise

# Singleton instance
_instance: FlightWatcher | None = None

def get_flight_watcher() -> FlightWatcher:
    global _instance
    if _instance is None:
        _instance = FlightWatcher(get_memory())
    return _instance
