import sqlite3
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import settings

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or settings.DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[str] = None):
    """Initializes the database tables."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_uuid TEXT UNIQUE NOT NULL,
        channel_id TEXT NOT NULL,
        thread_ts TEXT,
        message_ts TEXT NOT NULL,
        sender_id TEXT NOT NULL,
        sender_name TEXT,
        incoming_text TEXT NOT NULL,
        drafted_reply TEXT NOT NULL,
        final_reply TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING',
        approval_message_ts TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def create_draft(
    channel_id: str,
    message_ts: str,
    sender_id: str,
    incoming_text: str,
    drafted_reply: str,
    sender_name: Optional[str] = None,
    thread_ts: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Creates a new draft entry and returns its dictionary."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    draft_uuid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
    INSERT INTO drafts (
        draft_uuid, channel_id, thread_ts, message_ts, sender_id,
        sender_name, incoming_text, drafted_reply, status, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
    """, (
        draft_uuid, channel_id, thread_ts, message_ts, sender_id,
        sender_name or sender_id, incoming_text, drafted_reply, now, now
    ))
    conn.commit()
    draft_id = cursor.lastrowid
    conn.close()
    
    return get_draft(draft_id, db_path)

def get_draft(draft_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_draft_by_uuid(draft_uuid: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drafts WHERE draft_uuid = ?", (draft_uuid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def set_approval_message_ts(draft_id: int, approval_ts: str, db_path: Optional[str] = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    UPDATE drafts
    SET approval_message_ts = ?, updated_at = ?
    WHERE id = ?
    """, (approval_ts, now, draft_id))
    conn.commit()
    conn.close()

def update_draft_status(
    draft_id: int,
    status: str,
    final_reply: Optional[str] = None,
    db_path: Optional[str] = None
):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    if final_reply is not None:
        cursor.execute("""
        UPDATE drafts
        SET status = ?, final_reply = ?, updated_at = ?
        WHERE id = ?
        """, (status, final_reply, now, draft_id))
    else:
        cursor.execute("""
        UPDATE drafts
        SET status = ?, updated_at = ?
        WHERE id = ?
        """, (status, now, draft_id))
        
    conn.commit()
    conn.close()

def list_pending_drafts(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drafts WHERE status = 'PENDING' ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def is_message_already_drafted(message_ts: str, db_path: Optional[str] = None) -> bool:
    """Checks if a draft has already been generated for a specific Slack message_ts."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM drafts WHERE message_ts = ?", (message_ts,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

