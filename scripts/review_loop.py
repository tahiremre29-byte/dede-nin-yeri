import sqlite3
import json
import csv
import argparse
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "audit_history.db"

TAGS = [
    "intent_miss",
    "tone_problem",
    "technical_error",
    "weak_clarification",
    "wrong_domain_routing",
    "product_hallucination",
    "field_knowledge_gap"
]

def get_conn():
    return sqlite3.connect(DB_PATH)

def list_unreviewed(limit=10, only_prod=True):
    """Lists recent assistant messages that haven't been reviewed yet."""
    conn = get_conn()
    cursor = conn.cursor()
    
    prod_filter = "AND s.client_info = 'web_ui'" if only_prod else ""
    
    query = f'''
        SELECT m.id, s.session_id, m.content, m.timestamp
        FROM messages m
        JOIN sessions s ON m.session_id = s.session_id
        LEFT JOIN message_reviews mr ON m.id = mr.message_id
        WHERE m.role = 'assistant' 
          AND mr.review_id IS NULL
          {prod_filter}
        ORDER BY m.id DESC LIMIT ?
    '''
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    
    print(f"\n[{'PROD' if only_prod else 'ALL'}] Son {len(rows)} İncelenmemiş Asistan Yanıtı:\n")
    for row in rows:
        msg_id, sess_id, content, tstamp = row
        
        # Get the preceding user message for context
        cursor.execute("SELECT content FROM messages WHERE session_id=? AND role='user' AND id < ? ORDER BY id DESC LIMIT 1", (sess_id, msg_id))
        user_msg = cursor.fetchone()
        user_content = user_msg[0] if user_msg else "<unknown>"
        
        print(f"--- Message ID: {msg_id} | Session: {sess_id} | Time: {tstamp} ---")
        print(f"USER : {user_content}")
        print(f"ASST : {content[:150]}...\n")
    
    conn.close()

def tag_message(message_id, tag, fix_note):
    if tag not in TAGS:
        print(f"HATA: Geçersiz tag '{tag}'. Geçerli tagler: {', '.join(TAGS)}")
        return
        
    conn = get_conn()
    cursor = conn.cursor()
    
    # Check if message exists
    cursor.execute("SELECT id FROM messages WHERE id=?", (message_id,))
    if not cursor.fetchone():
        print(f"HATA: Message ID {message_id} bulunamadı.")
        return
        
    cursor.execute('''
        INSERT INTO message_reviews (message_id, error_tag, suggested_fix) 
        VALUES (?, ?, ?)
    ''', (message_id, tag, fix_note))
    conn.commit()
    conn.close()
    print(f"Başarılı: Message {message_id} '{tag}' olarak etiketlendi.")

def export_data(format_type="json"):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT mr.review_id, mr.message_id, mr.error_tag, mr.suggested_fix, mr.reviewed_at,
               m.session_id, m.content as assistant_response,
               (SELECT content FROM messages WHERE session_id=m.session_id AND role='user' AND id < m.id ORDER BY id DESC LIMIT 1) as user_message
        FROM message_reviews mr
        JOIN messages m ON mr.message_id = m.id
        JOIN sessions s ON m.session_id = s.session_id
        WHERE s.client_info = 'web_ui'
        ORDER BY mr.reviewed_at DESC
    '''
    cursor.execute(query)
    rows = cursor.fetchall()
    
    data = [dict(row) for row in rows]
    
    if format_type == "json":
        out_path = Path(__file__).resolve().parent / "export_reviews.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"JSON Output exported to: {out_path}")
        
    elif format_type == "csv":
        out_path = Path(__file__).resolve().parent / "export_reviews.csv"
        if data:
            with open(out_path, "w", encoding="utf-8", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        print(f"CSV Output exported to: {out_path}")
        
    conn.close()

def report():
    conn = get_conn()
    cursor = conn.cursor()
    
    # Etiket Dağılımı
    cursor.execute('''
        SELECT mr.error_tag, COUNT(*) as count 
        FROM message_reviews mr
        JOIN messages m ON mr.message_id = m.id
        JOIN sessions s ON m.session_id = s.session_id
        WHERE s.client_info = 'web_ui'
        GROUP BY mr.error_tag 
        ORDER BY count DESC
    ''')
    tags = cursor.fetchall()
    
    # Son 5 Düzeltme
    cursor.execute('''
        SELECT mr.error_tag, mr.suggested_fix,
               (SELECT content FROM messages WHERE session_id=m.session_id AND role='user' AND id < m.id ORDER BY id DESC LIMIT 1) as user_msg,
               m.content as asst_msg
        FROM message_reviews mr
        JOIN messages m ON mr.message_id = m.id
        JOIN sessions s ON m.session_id = s.session_id
        WHERE s.client_info = 'web_ui'
        ORDER BY mr.reviewed_at DESC LIMIT 5
    ''')
    latest = cursor.fetchall()
    conn.close()
    
    report_md = f"# Aşama 7: Haftalık Supervisor Raporu\nTarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    report_md += "## En Çok Karşılaşılan Sorunlar\n"
    for tag, count in tags:
        report_md += f"- **{tag}**: {count} uyarı\n"
        
    report_md += "\n## Uygulama Kuyruğu (Son Düzeltme Önerileri)\n"
    for row in latest:
        tag, fix, user_msg, asst_msg = row
        report_md += f"### [{tag}]\n"
        report_md += f"> **Kullanıcı:** {user_msg}\n> \n> **Asistan:** {asst_msg[:80]}...\n\n"
        report_md += f"**Önerilen Sistem/Prompt Kuralı:** `{fix}`\n\n"
        
    out_path = Path(__file__).resolve().parent / "weekly_feedback_digest.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_md)
        
    print(f"Rapor oluşturuldu: {out_path}")
    print(report_md)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DD1 Subervisory Loop CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # List command
    p_list = subparsers.add_parser("list", help="İncelenmemiş son asistan mesajlarını listele")
    p_list.add_argument("--limit", type=int, default=10)
    p_list.add_argument("--all", action="store_true", help="Test kayıtlarını da getir")
    
    # Tag command
    p_tag = subparsers.add_parser("tag", help="Bir mesajı hatalı olarak etiketle")
    p_tag.add_argument("message_id", type=int)
    p_tag.add_argument("--tag", required=True, choices=TAGS)
    p_tag.add_argument("--fix", required=True, help="Önerilen prompt veya kural düzeltmesi")
    
    # Export command
    p_exp = subparsers.add_parser("export", help="Etiketleri dışa aktar")
    p_exp.add_argument("--format", choices=["json", "csv"], default="json")
    
    # Report command
    p_rep = subparsers.add_parser("report", help="Haftalık Markdown Raporu Üret")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_unreviewed(limit=args.limit, only_prod=not args.all)
    elif args.command == "tag":
        tag_message(args.message_id, args.tag, args.fix)
    elif args.command == "export":
        export_data(format_type=args.format)
    elif args.command == "report":
        report()
    else:
        parser.print_help()
