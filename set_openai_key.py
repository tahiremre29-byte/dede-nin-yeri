"""
DD1 — OpenAI Key Güvenli Ayarlayıcı
Çalıştır: python set_openai_key.py
Key terminale yazılır ama görünmez (getpass).
"""
import getpass
import re
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"

print("=" * 55)
print("  DD1 — OpenAI API Key Güncelleme")
print("=" * 55)
print()

key = getpass.getpass("OpenAI API Key'i yapıştır (görünmeyecek): ").strip()

if not key.startswith("sk-"):
    print("HATA: Geçersiz key formatı (sk- ile başlamalı).")
    exit(1)

print(f"Key uzunluğu: {len(key)} karakter — son 6: ...{key[-6:]}")

content = ENV_PATH.read_text(encoding="utf-8")

# OPENAI_API_KEY satırını güncelle veya ekle
if re.search(r"^OPENAI_API_KEY=", content, re.MULTILINE):
    content = re.sub(r"^OPENAI_API_KEY=.*$", f"OPENAI_API_KEY={key}", content, flags=re.MULTILINE)
else:
    content = content.rstrip() + f"\nOPENAI_API_KEY={key}\n"

# AI_PROVIDER=openai yap
if re.search(r"^AI_PROVIDER=", content, re.MULTILINE):
    content = re.sub(r"^AI_PROVIDER=.*$", "AI_PROVIDER=openai", content, flags=re.MULTILINE)
else:
    content = content.rstrip() + "\nAI_PROVIDER=openai\n"

ENV_PATH.write_text(content, encoding="utf-8")

# Doğrula
saved = re.search(r"^OPENAI_API_KEY=(.+)$", content, re.MULTILINE)
saved_key = saved.group(1).strip() if saved else ""
prov = re.search(r"^AI_PROVIDER=(.+)$", content, re.MULTILINE)

print()
print("✅ .env güncellendi:")
print(f"   Key uzunluğu : {len(saved_key)}")
print(f"   Key sonu     : ...{saved_key[-6:]}")
print(f"   AI_PROVIDER  : {prov.group(1).strip() if prov else '?'}")
print()
print("Şimdi sunucuyu yeniden başlat:")
print("  Stop-Process -Name python -Force")
print("  python -m uvicorn main:app --host 127.0.0.1 --port 8000")
