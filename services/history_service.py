import sqlite3
import json
from datetime import datetime
from pathlib import Path
import logging
import uuid
import os

logger = logging.getLogger("dd1.history")

class HistoryService:
    def __init__(self):
        from core.config import cfg
        db_filename = "audit_history_test.db" if getattr(cfg, "debug", False) or os.environ.get("APP_ENV", "").lower() == "test" else "audit_history.db"
        self._db_path = Path(__file__).resolve().parents[1] / "knowledge" / db_filename
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database with the session-based schema."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                # 1. SESSIONS
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        client_info TEXT
                    )
                ''')
                
                # 2. MESSAGES
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                # 3. DESIGN EVENTS (Append-only per event_type)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS design_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        design_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        input_payload TEXT,
                        acoustic_packet TEXT,
                        output_file TEXT,
                        warnings_errors TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                # 4. KNOWLEDGE LOOKUPS
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS knowledge_lookups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        query TEXT,
                        matched_sources TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                # 5. MESSAGE REVIEWS (Aşama 7 - Supervisor Loop)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS message_reviews (
                        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER NOT NULL,
                        error_tag TEXT NOT NULL,
                        suggested_fix TEXT,
                        reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (message_id) REFERENCES messages (id)
                    )
                ''')
                
                # 6. REGISTERED USERS
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS registered_users (
                        session_id TEXT PRIMARY KEY,
                        name TEXT,
                        email TEXT,
                        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize History DB: {e}")

    # =========================================================================
    # SESSIONS
    # =========================================================================
    def start_session(self, client_info: str = "web_ui") -> str:
        """Creates a new session and returns the session_id."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (session_id, client_info) VALUES (?, ?)", 
                    (session_id, client_info)
                )
                conn.commit()
            return session_id
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return session_id

    def ensure_session(self, session_id: str) -> str:
        """If session doesn't exist, create it as fallback to satisfy FK dependencies."""
        if not session_id:
            return self.start_session(client_info="auto_fallback")
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO sessions (session_id, client_info) VALUES (?, ?)", (session_id, "auto_fallback"))
                conn.commit()
        except Exception:
            pass
        return session_id

    def register_user(self, session_id: str, name: str, email: str) -> bool:
        session_id = self.ensure_session(session_id)
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO registered_users (session_id, name, email) VALUES (?, ?, ?)",
                    (session_id, name, email)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to register user: {e}")
            return False

    # =========================================================================
    # MESSAGES
    # =========================================================================
    def log_message(self, session_id: str, role: str, content: str):
        session_id = self.ensure_session(session_id)
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, role, content)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    # =========================================================================
    # DESIGN EVENTS
    # =========================================================================
    def log_design_event(self, session_id: str, design_id: str, event_type: str, status: str, 
                         input_payload: dict = None, acoustic_packet: dict = None, 
                         output_file: str = None, error: str = None):
        """Append-only logging for calculate, produce, download."""
        session_id = self.ensure_session(session_id)
            
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO design_events 
                    (session_id, design_id, event_type, status, input_payload, acoustic_packet, output_file, warnings_errors) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    design_id,
                    event_type,
                    status,
                    json.dumps(input_payload, ensure_ascii=False) if input_payload else None,
                    json.dumps(acoustic_packet, ensure_ascii=False) if acoustic_packet else None,
                    output_file,
                    error
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log design event {event_type} for {design_id}: {e}")

    # For API compat logic
    def log_calculation(self, session_id: str, design_id: str, input_payload: dict, acoustic_packet: dict):
        self.log_design_event(session_id, design_id, "calculate", "success", input_payload=input_payload, acoustic_packet=acoustic_packet)

    def log_production(self, session_id: str, design_id: str, status: str, output_file: str = None, error: str = None):
        self.log_design_event(session_id, design_id, "produce", status, output_file=output_file, error=error)

    def log_download(self, session_id: str, design_id: str, status: str, access_mode: str = "open"):
        self.log_design_event(session_id, design_id, "download", status, input_payload={"access_mode": access_mode})
        
    # =========================================================================
    # KNOWLEDGE LOOKUPS
    # =========================================================================
    def log_knowledge_lookup(self, session_id: str, query: str, matched_sources: list):
        if not session_id or not matched_sources:
            return
            
        session_id = self.ensure_session(session_id)
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                sources_str = ", ".join([f"{m.get('source')}::{m.get('match_id')}" for m in matched_sources])
                cursor.execute(
                    "INSERT INTO knowledge_lookups (session_id, query, matched_sources) VALUES (?, ?, ?)",
                    (session_id, query, sources_str)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log knowledge lookup: {e}")

history_db = HistoryService()
