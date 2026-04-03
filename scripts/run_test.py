import sys
import os
os.environ["APP_ENV"] = "test"
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.ai_assistant import get_ai_response
from services.history_service import history_db
import json
import sqlite3

session_id = history_db.start_session('web_ui')
print(f"Started session: {session_id}")

print('=== SENARYO 1: Muğlak Model (JBL 1000) ===')
q1 = 'Abi clio 4 araca JBL 1000 takıcam bagajı inletir mi?'
history_db.log_message(session_id, 'user', q1)
r1 = get_ai_response(q1)
ans1 = json.dumps(r1['content'], indent=2, ensure_ascii=False) if isinstance(r1['content'], dict) else r1['content']
print(ans1)
history_db.log_message(session_id, 'assistant', ans1)

print('\n=== SENARYO 2: Loaded Enclosure ===')
q2 = 'Kicker Dual 12 CompR Loaded Enclosure aldım buna portlu özel Litre uydurur musun?'
history_db.log_message(session_id, 'user', q2)
r2 = get_ai_response(q2)
ans2 = json.dumps(r2['content'], indent=2, ensure_ascii=False) if isinstance(r2['content'], dict) else r2['content']
print(ans2)
history_db.log_message(session_id, 'assistant', ans2)

print('\n=== SENARYO 3: Driver-Only (Aynı Litre Çakışması) ===')
q3 = 'Alpine Type R SWR-12D4 var. Piyasada herkes kapalı 50L diyor, sence?'
history_db.log_message(session_id, 'user', q3)
r3 = get_ai_response(q3)
ans3 = json.dumps(r3['content'], indent=2, ensure_ascii=False) if isinstance(r3['content'], dict) else r3['content']
print(ans3)
history_db.log_message(session_id, 'assistant', ans3)

# Print IDs
conn = sqlite3.connect(history_db._db_path)
c = conn.cursor()
c.execute("SELECT id FROM messages WHERE session_id=? AND role='assistant' ORDER BY id ASC", (session_id,))
print('\n[DEBUG] Last 3 Assistant Message IDs for tagging:', [x[0] for x in c.fetchall()])
