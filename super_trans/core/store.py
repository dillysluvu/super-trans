"""
Lưu trữ cục bộ bằng SQLite cho SuperTrans.

Ba mục đích:
  1. Cache bản dịch để lặp lại cùng một câu không cần gọi mạng.
  2. Lưu lịch sử dịch (có thể xem, tìm kiếm, xóa).
  3. Lưu lần thay thế tại chỗ gần nhất để hỗ trợ hoàn tác (undo).

Toàn bộ dữ liệu nằm trong ``$XDG_DATA_HOME/super-trans/history.db``
(mặc định ``~/.local/share/super-trans/history.db``). Module này được thiết kế
để *không bao giờ* làm hỏng luồng dịch chính: mọi lỗi SQLite/OS đều được nuốt
và trả về ``None``/``False`` thay vì ném ngoại lệ.
"""

import hashlib
import os
import sqlite3
import time
from contextlib import closing
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(
    os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
    "super-trans",
)
DB_FILE = os.path.join(DATA_DIR, "history.db")

SCHEMA_VERSION = 1
DEFAULT_HISTORY_LIMIT = 500
DEFAULT_REPLACEMENT_LIMIT = 100
MAX_CACHE_TEXT_CHARS = 100_000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS translations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key       TEXT    NOT NULL UNIQUE,
    source_text     TEXT    NOT NULL,
    translated_text TEXT    NOT NULL,
    source_lang     TEXT    NOT NULL,
    detected_lang   TEXT    NOT NULL DEFAULT '',
    target_lang     TEXT    NOT NULL,
    engine          TEXT    NOT NULL,
    created_at      INTEGER NOT NULL,
    last_used_at    INTEGER NOT NULL,
    use_count       INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_translations_last_used
    ON translations(last_used_at DESC);

CREATE TABLE IF NOT EXISTS replacements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text   TEXT    NOT NULL,
    translated_text TEXT    NOT NULL,
    app_id          TEXT    NOT NULL DEFAULT '',
    source_lang     TEXT    NOT NULL DEFAULT 'auto',
    target_lang     TEXT    NOT NULL DEFAULT 'vi',
    engine          TEXT    NOT NULL DEFAULT 'fast',
    created_at      INTEGER NOT NULL,
    undone_at       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_replacements_created
    ON replacements(created_at DESC);
"""


def _db_path() -> str:
    """Đường dẫn DB hiện tại (cho phép test ghi đè qua biến môi trường)."""
    return os.environ.get("SUPERTRANS_DB") or DB_FILE


def _connect() -> sqlite3.Connection:
    """Mở kết nối SQLite, tạo thư mục/schema nếu cần."""
    path = _db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, mode=0o700, exist_ok=True)

    conn = sqlite3.connect(path, timeout=3.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.executescript(_SCHEMA)

    # Migration nhẹ cho DB được tạo bởi bản thử nghiệm trước đó.
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(translations)").fetchall()
    }
    if "detected_lang" not in columns:
        conn.execute(
            "ALTER TABLE translations ADD COLUMN "
            "detected_lang TEXT NOT NULL DEFAULT ''"
        )

    conn.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)
    conn.commit()

    # Lịch sử dịch có thể chứa văn bản riêng tư: chỉ chủ sở hữu được đọc.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return conn


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def make_cache_key(source_text: str, source_lang: str, target_lang: str,
                   engine: str) -> str:
    """Tạo khóa cache ổn định, không phụ thuộc thứ tự từ điển."""
    parts = (
        (source_text or "").strip(),
        source_lang or "auto",
        target_lang or "vi",
        engine or "fast",
    )
    payload = bytearray()
    for part in parts:
        data = part.encode("utf-8", "surrogatepass")
        payload.extend(len(data).to_bytes(8, "big"))
        payload.extend(data)
    return hashlib.sha256(bytes(payload)).hexdigest()


def lookup(source_text: str, source_lang: str, target_lang: str,
           engine: str, touch: bool = True) -> Optional[Dict[str, Any]]:
    """Tìm bản dịch đã lưu. Trả về dict hoặc None."""
    if not source_text or not source_text.strip():
        return None

    key = make_cache_key(source_text, source_lang, target_lang, engine)
    now = int(time.time())
    try:
        with closing(_connect()) as conn, conn:
            row = conn.execute(
                "SELECT * FROM translations WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            if touch:
                conn.execute(
                    "UPDATE translations SET last_used_at = ?, "
                    "use_count = use_count + 1 WHERE id = ?",
                    (now, row["id"]),
                )
            result = dict(row)
            result["last_used_at"] = now if touch else result["last_used_at"]
            return result
    except (sqlite3.Error, OSError, ValueError):
        return None


def save_translation(source_text: str, translated_text: str, source_lang: str,
                     target_lang: str, engine: str,
                     detected_lang: str = "",
                     history_limit: int = DEFAULT_HISTORY_LIMIT) -> Optional[int]:
    """Lưu/cập nhật một bản dịch và dọn bớt mục cũ nếu vượt giới hạn."""
    if not source_text or not source_text.strip():
        return None
    if not translated_text or not translated_text.strip():
        return None
    if len(source_text) > MAX_CACHE_TEXT_CHARS:
        return None

    key = make_cache_key(source_text, source_lang, target_lang, engine)
    now = int(time.time())
    try:
        with closing(_connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO translations (
                    cache_key, source_text, translated_text, source_lang,
                    detected_lang, target_lang, engine, created_at,
                    last_used_at, use_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(cache_key) DO UPDATE SET
                    translated_text = excluded.translated_text,
                    source_lang     = excluded.source_lang,
                    detected_lang   = excluded.detected_lang,
                    target_lang     = excluded.target_lang,
                    engine          = excluded.engine,
                    last_used_at    = excluded.last_used_at,
                    use_count       = translations.use_count + 1
                """,
                (
                    key, source_text.strip(), translated_text.strip(),
                    source_lang or "auto", detected_lang or "",
                    target_lang or "vi", engine or "fast", now, now,
                ),
            )
            row = conn.execute(
                "SELECT id FROM translations WHERE cache_key = ?", (key,)
            ).fetchone()

            if history_limit > 0:
                conn.execute(
                    """
                    DELETE FROM translations
                    WHERE id NOT IN (
                        SELECT id FROM translations
                        ORDER BY last_used_at DESC, id DESC
                        LIMIT ?
                    )
                    """,
                    (int(history_limit),),
                )

            return int(row["id"]) if row is not None else None
    except (sqlite3.Error, OSError, ValueError):
        return None


def recent(limit: int = 20) -> List[Dict[str, Any]]:
    """Trả về các bản dịch gần đây, mới nhất trước."""
    limit = max(1, min(int(limit), 1000))
    try:
        with closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM translations "
                "ORDER BY last_used_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    except (sqlite3.Error, OSError, ValueError):
        return []


def search(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Tìm trong văn bản gốc hoặc bản dịch (không phân biệt hoa/thường)."""
    query = (query or "").strip()
    if not query:
        return []
    limit = max(1, min(int(limit), 200))
    needle = query.casefold()
    try:
        with closing(_connect()) as conn:
            # SQLite LIKE chỉ không phân biệt hoa/thường với ASCII, nên lọc
            # bằng Python để tìm đúng cả tiếng Việt có dấu.
            rows = conn.execute(
                "SELECT * FROM translations "
                "ORDER BY last_used_at DESC, id DESC LIMIT 5000"
            ).fetchall()
            matches = []
            for row in rows:
                record = dict(row)
                if (
                    needle in (record.get("source_text") or "").casefold()
                    or needle in (record.get("translated_text") or "").casefold()
                ):
                    matches.append(record)
                    if len(matches) >= limit:
                        break
            return matches
    except (sqlite3.Error, OSError, ValueError):
        return []


def record_replacement(original_text: str, translated_text: str,
                       app_id: str = "", source_lang: str = "auto",
                       target_lang: str = "vi", engine: str = "fast",
                       keep_last: int = DEFAULT_REPLACEMENT_LIMIT) -> Optional[int]:
    """Lưu lần thay thế tại chỗ để có thể hoàn tác sau đó."""
    if not original_text or not translated_text:
        return None

    now = int(time.time())
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.execute(
                """
                INSERT INTO replacements (
                    original_text, translated_text, app_id, source_lang,
                    target_lang, engine, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    original_text, translated_text, app_id or "",
                    source_lang or "auto", target_lang or "vi",
                    engine or "fast", now,
                ),
            )

            if keep_last > 0:
                conn.execute(
                    """
                    DELETE FROM replacements
                    WHERE id NOT IN (
                        SELECT id FROM replacements
                        ORDER BY created_at DESC, id DESC
                        LIMIT ?
                    )
                    """,
                    (int(keep_last),),
                )

            return int(cursor.lastrowid)
    except (sqlite3.Error, OSError, ValueError):
        return None


def last_replacement() -> Optional[Dict[str, Any]]:
    """Lần thay thế gần nhất chưa được hoàn tác."""
    try:
        with closing(_connect()) as conn:
            row = conn.execute(
                "SELECT * FROM replacements WHERE undone_at IS NULL "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return _row_to_dict(row)
    except (sqlite3.Error, OSError, ValueError):
        return None


def mark_replacement_undone(replacement_id: int) -> bool:
    """Đánh dấu một lần thay thế đã được hoàn tác."""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE replacements SET undone_at = ? "
                "WHERE id = ? AND undone_at IS NULL",
                (int(time.time()), int(replacement_id)),
            )
            return cursor.rowcount > 0
    except (sqlite3.Error, OSError, ValueError):
        return False


def stats() -> Dict[str, Any]:
    """Thống kê nhanh về cache/lịch sử."""
    path = _db_path()
    result: Dict[str, Any] = {
        "path": path,
        "exists": os.path.exists(path),
        "size_bytes": 0,
        "translations": 0,
        "replacements": 0,
        "undone": 0,
        "oldest": None,
        "newest": None,
        "top_engines": [],
        "error": "",
    }

    try:
        with closing(_connect()) as conn:
            result["translations"] = int(
                conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
            )
            result["replacements"] = int(
                conn.execute("SELECT COUNT(*) FROM replacements").fetchone()[0]
            )
            result["undone"] = int(
                conn.execute(
                    "SELECT COUNT(*) FROM replacements WHERE undone_at IS NOT NULL"
                ).fetchone()[0]
            )
            row = conn.execute(
                "SELECT MIN(created_at), MAX(last_used_at) FROM translations"
            ).fetchone()
            if row is not None:
                result["oldest"], result["newest"] = row[0], row[1]
            result["top_engines"] = [
                {"engine": r[0], "count": r[1]}
                for r in conn.execute(
                    "SELECT engine, COUNT(*) FROM translations "
                    "GROUP BY engine ORDER BY COUNT(*) DESC LIMIT 5"
                ).fetchall()
            ]
        if os.path.exists(path):
            result["exists"] = True
            result["size_bytes"] = os.path.getsize(path)
    except (sqlite3.Error, OSError, ValueError) as exc:
        result["error"] = str(exc)

    return result


def clear_all() -> Dict[str, int]:
    """Xóa toàn bộ lịch sử và cache. Trả về số dòng đã xóa."""
    deleted = {"translations": 0, "replacements": 0}
    try:
        with closing(_connect()) as conn:
            with conn:
                deleted["translations"] = conn.execute(
                    "DELETE FROM translations"
                ).rowcount
                deleted["replacements"] = conn.execute(
                    "DELETE FROM replacements"
                ).rowcount
            # VACUUM không được chạy bên trong transaction.
            conn.execute("VACUUM")
    except (sqlite3.Error, OSError, ValueError):
        return {"translations": 0, "replacements": 0}
    return deleted


def available() -> bool:
    """Kiểm tra nhanh SQLite/DB có sử dụng được không (dùng cho --doctor)."""
    try:
        with closing(_connect()) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except (sqlite3.Error, OSError, ValueError):
        return False
