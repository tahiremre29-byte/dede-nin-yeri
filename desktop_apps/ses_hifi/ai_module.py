# ai_module.py — DD1 Workshop Tools
# Ses Ustası sekmesi: Groq AI (Llama 3.3 70B) — Ücretsiz & Türkiye'de çalışır
# Ücretsiz anahtar: https://console.groq.com  →  "Create API Key"

import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QTextCursor, QFont

# ── Sistem Promptu ──────────────────────────────────────────────
SISTEM_PROMPTU = """Sen DD1'in Ses Ustası asistanısın. DD1, Türkiye'de profesyonel hoparlör, subwoofer ve HiFi ses sistemleri üretimi yapan bir atölyedir.

Uzmanlık alanların:
- HiFi ve audiofil ses sistemleri
- Subwoofer ve bass yönetimi (Thiele-Small parametreleri, kabin hesabı)
- Hoparlör tasarımı ve akustik
- Amplifikatör seçimi ve empedans eşleştirme
- Oda akustiği ve oda modu analizi
- Lazer kesim ve ahşap kabin yapımı (DD1 üretim süreci)
- Ses mühendisliği (EQ, crossover, DSP)

Kurallar:
- Türkçe cevap ver
- Teknik ve pratik ol
- Gerektiğinde hesaplamalar yap
- Kısa ve net cevaplar ver
- Emin olmadığın şeyleri "tahmin" olarak belirt
"""

GROQ_MODEL = "llama-3.3-70b-versatile"   # Ücretsiz, çok güçlü

# ── Groq Worker ──────────────────────────────────────────────────
class GroqWorker(QObject):
    """Groq API'ye arka planda istek gönderir (Llama 3.3 70B, ücretsiz)."""
    result_ready   = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, message: str, api_key: str, gecmis: list):
        super().__init__()
        self.message = message
        self.api_key = api_key
        self.gecmis  = gecmis

    def run(self) -> None:
        if not self.api_key:
            self.error_occurred.emit(
                "❌ API anahtarı girilmedi!\n"
                "Ücretsiz Groq anahtarı almak için:\n"
                "  → https://console.groq.com → 'API Keys' → 'Create API Key'"
            )
            return
        try:
            from groq import Groq
            client = Groq(api_key=self.api_key)

            # Mesaj listesi oluştur
            mesajlar = [{"role": "system", "content": SISTEM_PROMPTU}]
            for msg in self.gecmis[-12:]:   # Son 12 mesaj geçmiş
                mesajlar.append({"role": msg["role"], "content": msg["content"]})
            mesajlar.append({"role": "user", "content": self.message})

            yanit = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=mesajlar,
                temperature=0.7,
                max_tokens=1024,
            )
            self.result_ready.emit(yanit.choices[0].message.content.strip())

        except Exception as e:
            hata = str(e)
            if "api_key" in hata.lower() or "invalid" in hata.lower() or "401" in hata:
                self.error_occurred.emit(
                    "❌ Geçersiz API anahtarı.\n"
                    "Ücretsiz anahtar: https://console.groq.com → API Keys"
                )
            elif "rate" in hata.lower() or "429" in hata:
                self.error_occurred.emit("❌ Çok fazla istek gönderildi. Birkaç saniye bekleyin.")
            elif "connect" in hata.lower():
                self.error_occurred.emit("❌ İnternet bağlantısı hatası.")
            else:
                self.error_occurred.emit(f"❌ Hata: {hata}")


class SesUstasiTab(QWidget):
    """Ses Ustası sekmesi — Gemini 2.0 Flash destekli AI sohbet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread   = None
        self._worker   = None
        self._gecmis: list = []   # Sohbet geçmişi
        self._api_key  = os.environ.get("GROQ_API_KEY", "")
        self._setup_ui()

    # ── UI kurulumu ──────────────────────────────────────────
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        from ui_interface import make_separator

        # ── Başlık ──
        header = QHBoxLayout()
        icon_lbl = QLabel("🎙")
        icon_lbl.setStyleSheet("font-size: 22px;")
        title = QLabel("Ses Ustası  —  Groq Llama 3.3 70B")
        title.setObjectName("title")
        self._status_lbl = QLabel("● Hazır")
        self._status_lbl.setObjectName("dim")
        header.addWidget(icon_lbl)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._status_lbl)
        layout.addLayout(header)

        # ── API Key satırı ──
        api_row = QHBoxLayout()
        api_lbl = QLabel("Groq API Key:")
        api_lbl.setObjectName("dim")
        api_lbl.setFixedWidth(110)
        self._api_input = QLineEdit()
        self._api_input.setPlaceholderText("gsk_...  (https://console.groq.com → API Keys)")
        self._api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_input.setMinimumHeight(34)
        if self._api_key:
            self._api_input.setText(self._api_key)
        self._api_input.textChanged.connect(self._on_api_key_change)
        api_row.addWidget(api_lbl)
        api_row.addWidget(self._api_input)
        layout.addLayout(api_row)

        layout.addWidget(make_separator())

        # ── Sohbet alanı ──
        self._chat_area = QTextEdit()
        self._chat_area.setReadOnly(True)
        self._chat_area.setMinimumHeight(340)
        self._chat_area.setFont(QFont("Segoe UI", 11))
        self._chat_area.setPlaceholderText("Sohbet geçmişi burada görünecek...")
        layout.addWidget(self._chat_area)

        # ── Mesaj giriş satırı ──
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._msg_input = QLineEdit()
        self._msg_input.setPlaceholderText("Sorunuzu yazın... (örn: 30cm subwoofer için kaç litrelik kabin gerekir?)")
        self._msg_input.setMinimumHeight(40)
        self._msg_input.returnPressed.connect(self._send_message)

        self._send_btn = QPushButton("Gönder ➤")
        self._send_btn.setMinimumHeight(40)
        self._send_btn.setFixedWidth(110)
        self._send_btn.clicked.connect(self._send_message)

        clear_btn = QPushButton("Temizle")
        clear_btn.setObjectName("secondary")
        clear_btn.setMinimumHeight(40)
        clear_btn.setFixedWidth(90)
        clear_btn.clicked.connect(self._clear_chat)

        input_row.addWidget(self._msg_input)
        input_row.addWidget(self._send_btn)
        input_row.addWidget(clear_btn)
        layout.addLayout(input_row)

        # Karşılama
        if self._api_key:
            self._append_message("sistem", "DD1 Ses Ustası hazır ✓  Groq bağlı — sorunuzu yazın.")
        else:
            self._append_message("sistem",
                "Merhaba! DD1 Ses Ustası'na hoş geldiniz.\n"
                "Başlamak için üstteki alana Groq API anahtarınızı yapıştırın.\n"
                "Ücretsiz anahtar: https://console.groq.com → API Keys → Create API Key"
            )

    # ── Slot metodları ──────────────────────────────────────────
    def _on_api_key_change(self, text: str):
        self._api_key = text.strip()
        os.environ["GROQ_API_KEY"] = self._api_key  # Hem envvar hem instance güncellenir

    def _send_message(self) -> None:
        text = self._msg_input.text().strip()
        if not text:
            return

        self._msg_input.clear()
        self._append_message("sen", text)
        self._set_busy(True)

        # Geçmişe ekle (Groq formatı: role + content)
        self._gecmis.append({"role": "user", "content": text})

        # Worker thread
        self._thread = QThread()
        self._worker = GroqWorker(text, self._api_key, list(self._gecmis[:-1]))
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.result_ready.connect(self._thread.quit)
        self._worker.error_occurred.connect(self._thread.quit)
        self._thread.finished.connect(lambda: self._set_busy(False))

        self._thread.start()

    def _on_result(self, text: str) -> None:
        self._gecmis.append({"role": "model", "parts": text})
        self._append_message("asistan", text)

    def _on_error(self, text: str) -> None:
        self._append_message("hata", text)

    def _clear_chat(self) -> None:
        self._chat_area.clear()
        self._gecmis.clear()
        self._append_message("sistem", "Sohbet temizlendi. Yeni konuşma başlatıldı.")

    def _set_busy(self, busy: bool) -> None:
        self._send_btn.setEnabled(not busy)
        self._msg_input.setEnabled(not busy)
        self._status_lbl.setText("⏳ Yanıt bekleniyor..." if busy else "● Hazır")
        self._status_lbl.setStyleSheet(
            "color: #f39c12;" if busy else "color: #a0a0b0;"
        )

    def _append_message(self, role: str, text: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        colors = {
            "sen":      ("#e94560", "SİZ"),
            "asistan":  ("#4ecdc4", "SES USTASI"),
            "sistem":   ("#a0a0b0", "SİSTEM"),
            "hata":     ("#ff6b6b", "HATA"),
        }
        color, label = colors.get(role, ("#eaeaea", role.upper()))

        html = (
            f'<div style="margin-bottom:12px; padding:8px; '
            f'background:rgba(255,255,255,0.03); border-radius:6px;">'
            f'<span style="color:{color}; font-weight:bold;">{label}</span>'
            f' <span style="color:#606080; font-size:10px;">{ts}</span><br>'
            f'<span style="color:#eaeaea; white-space:pre-wrap;">{self._escape(text)}</span>'
            f'</div>'
        )
        self._chat_area.append(html)
        cursor = self._chat_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._chat_area.setTextCursor(cursor)

    @staticmethod
    def _escape(text: str) -> str:
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>"))

