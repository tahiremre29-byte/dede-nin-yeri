# hifi_module.py — DD1 Lazer Agent
# HiFi Stüdyo sekmesi: Frekans Analizi, EQ, Oda Hesabı, Hoparlör Eşleştirme

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QDoubleSpinBox, QSpinBox,
    QTabWidget, QGroupBox, QTextEdit, QFrame, QSizePolicy,
    QComboBox, QFileDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QLinearGradient, QBrush
import ui_interface


# ═══════════════════════════════════════════════════════════════
#  FREKANS ANALİZİ SEKMESİ
# ═══════════════════════════════════════════════════════════════

class FrequencyGraphWidget(QWidget):
    """Basit FFT frekans grafiği — numpy/matplotlib gerektirmez."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.bars = []          # 0.0–1.0 normalize genlik değerleri
        self.labels = []        # Frekans etiketleri
        self._demo_mode()

    def _demo_mode(self):
        """Demo: tipik müzik frekans dağılımı."""
        freqs = [31, 63, 125, 250, 500, "1k", "2k", "4k", "8k", "16k"]
        # Müzik içeriğini taklit eden şekil
        amps = [0.55, 0.75, 0.82, 0.70, 0.60, 0.65, 0.58, 0.45, 0.30, 0.18]
        self.bars = amps
        self.labels = [str(f) for f in freqs]
        self.update()

    def set_data(self, amplitudes: list, labels: list):
        self.bars = amplitudes
        self.labels = labels
        self.update()

    def paintEvent(self, event):
        if not self.bars:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 40, 10, 10, 30
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b

        # Arka plan
        painter.fillRect(0, 0, w, h, QColor("#0a0a1a"))

        # Izgara
        pen = QPen(QColor("#1e1e3a"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for i in range(1, 5):
            y = pad_t + chart_h * (1 - i * 0.25)
            painter.drawLine(pad_l, int(y), w - pad_r, int(y))

        # Çubuklar
        n = len(self.bars)
        bar_w = chart_w / n
        gap = max(2, int(bar_w * 0.18))

        for i, amp in enumerate(self.bars):
            x = pad_l + i * bar_w + gap
            bw = bar_w - gap * 2
            bh = chart_h * amp
            y = pad_t + chart_h - bh

            # Gradient renk
            grad = QLinearGradient(x, y, x, y + bh)
            if amp > 0.75:
                grad.setColorAt(0, QColor("#ff6b6b"))
                grad.setColorAt(1, QColor("#e94560"))
            elif amp > 0.5:
                grad.setColorAt(0, QColor("#4ecdc4"))
                grad.setColorAt(1, QColor("#2eb5ac"))
            else:
                grad.setColorAt(0, QColor("#45b7d1"))
                grad.setColorAt(1, QColor("#2980b9"))

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bw), int(bh), 3, 3)

            # Etiket
            if i < len(self.labels):
                painter.setPen(QColor("#a0a0b0"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(int(x), h - 5, self.labels[i])

        # dB ekseni
        painter.setPen(QColor("#606080"))
        painter.setFont(QFont("Segoe UI", 8))
        for i in range(5):
            val = 100 - i * 25
            y = pad_t + chart_h * (i * 0.25)
            painter.drawText(2, int(y) + 4, f"{val}")

        painter.end()


class FreqAnalizTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Başlık
        h = QHBoxLayout()
        title = QLabel("📈  Frekans Analizi")
        title.setObjectName("title")
        h.addWidget(title)
        h.addStretch()
        load_btn = QPushButton("📂  Ses Dosyası Yükle")
        load_btn.setFixedWidth(180)
        load_btn.clicked.connect(self._load_file)
        h.addWidget(load_btn)
        layout.addLayout(h)
        layout.addWidget(ui_interface.make_separator())

        # Graf
        self.graph = FrequencyGraphWidget()
        layout.addWidget(self.graph)

        # Bilgi kutusu
        info = QLabel(
            "💡  Ses dosyası yüklediğinizde FFT analizi yapılır ve frekans dağılımı grafik olarak gösterilir.\n"
            "    Şu an DEMO modu aktif — tipik müzik frekans profili görüntüleniyor."
        )
        info.setObjectName("dim")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Animasyon (demo)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate_demo)
        self._timer.start(80)
        self._tick = 0

    def _animate_demo(self):
        """Demo modunda dalgalanan çubuklar."""
        import random
        base = [0.55, 0.75, 0.82, 0.70, 0.60, 0.65, 0.58, 0.45, 0.30, 0.18]
        animated = [max(0.05, min(1.0, v + random.uniform(-0.08, 0.08))) for v in base]
        labels = ["31", "63", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
        self.graph.set_data(animated, labels)
        self._tick += 1

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ses Dosyası Seç", "",
            "Ses Dosyaları (*.wav *.mp3 *.flac *.ogg *.aac);;Tüm Dosyalar (*)"
        )
        if path:
            self._timer.stop()
            self._analyze_file(path)

    def _analyze_file(self, path: str):
        """numpy/scipy varsa gerçek FFT, yoksa simülasyon."""
        try:
            import numpy as np
            import wave, struct
            with wave.open(path, 'rb') as wf:
                n_frames = wf.getnframes()
                data = wf.readframes(min(n_frames, 44100))
                samples = np.frombuffer(data, dtype=np.int16).astype(float)
            fft = np.abs(np.fft.rfft(samples[:4096]))
            bands = 10
            chunk = len(fft) // bands
            amps = []
            for i in range(bands):
                seg = fft[i*chunk:(i+1)*chunk]
                amps.append(float(np.mean(seg)))
            mx = max(amps) or 1
            amps = [min(1.0, a/mx) for a in amps]
            labels = ["31", "63", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
            self.graph.set_data(amps, labels)
        except Exception:
            # Simülasyon
            import random
            amps = [round(random.uniform(0.2, 0.95), 2) for _ in range(10)]
            labels = ["31", "63", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
            self.graph.set_data(amps, labels)


# ═══════════════════════════════════════════════════════════════
#  10 BANTLI EQ SEKMESİ
# ═══════════════════════════════════════════════════════════════

EQ_BANDS = ["31Hz", "63Hz", "125Hz", "250Hz", "500Hz",
            "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]

EQ_PRESETS = {
    "Düz (Flat)":       [0]*10,
    "Bass Boost":       [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
    "Vokal Öne":        [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
    "HiFi Referans":    [0, 1, 2, 1, 0, 0, 1, 2, 1, 0],
    "Rock":             [3, 2, 1, 0, -1, 0, 1, 2, 3, 3],
    "Jazz":             [2, 1, 0, 2, -1, -1, 0, 1, 2, 2],
    "Klasik":           [3, 2, 1, -1, -2, -2, -1, 1, 2, 3],
    "Bass & Treble":    [5, 4, 2, 0, -2, -2, 0, 2, 4, 5],
    "Akustik":          [2, 1, 2, 3, 1, 0, 1, 2, 2, 1],
    "Sıfırla":          [0]*10,
}


class EQBandWidget(QWidget):
    """Tek EQ bandı: frekans etiketi + slider + dB değeri."""

    def __init__(self, freq_label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.db_lbl = QLabel("+0 dB")
        self.db_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.db_lbl.setStyleSheet("color:#4ecdc4; font-weight:bold; font-size:11px;")
        layout.addWidget(self.db_lbl)

        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setRange(-12, 12)
        self.slider.setValue(0)
        self.slider.setFixedHeight(160)
        self.slider.setFixedWidth(28)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.slider.setTickInterval(6)
        self.slider.valueChanged.connect(self._on_value)
        layout.addWidget(self.slider, alignment=Qt.AlignmentFlag.AlignHCenter)

        freq_lbl = QLabel(freq_label)
        freq_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        freq_lbl.setStyleSheet("color:#a0a0b0; font-size:10px;")
        layout.addWidget(freq_lbl)

    def _on_value(self, v: int):
        sign = "+" if v >= 0 else ""
        color = "#ff6b6b" if v > 3 else "#4ecdc4" if v < -3 else "#4ecdc4"
        self.db_lbl.setText(f"{sign}{v} dB")
        self.db_lbl.setStyleSheet(f"color:{color}; font-weight:bold; font-size:11px;")

    def set_value(self, v: int):
        self.slider.setValue(v)

    def get_value(self) -> int:
        return self.slider.value()


class EQTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Başlık + Önayar
        h = QHBoxLayout()
        title = QLabel("🎚  10 Bantlı Grafik Ekolayzır")
        title.setObjectName("title")
        h.addWidget(title)
        h.addStretch()
        h.addWidget(QLabel("Önayar:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(EQ_PRESETS.keys())
        self.preset_combo.setFixedWidth(160)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        h.addWidget(self.preset_combo)
        layout.addLayout(h)
        layout.addWidget(ui_interface.make_separator())

        # Bilgi etiketi
        self.info_lbl = QLabel("Önayar: Düz (Flat)  •  Tüm bantlar: 0 dB")
        self.info_lbl.setObjectName("dim")
        layout.addWidget(self.info_lbl)

        # EQ sliderları
        eq_frame = QFrame()
        eq_frame.setObjectName("card")
        eq_layout = QHBoxLayout(eq_frame)
        eq_layout.setSpacing(6)

        self.bands: list[EQBandWidget] = []
        for freq in EQ_BANDS:
            band = EQBandWidget(freq)
            band.slider.valueChanged.connect(self._update_info)
            eq_layout.addWidget(band)
            self.bands.append(band)

        layout.addWidget(eq_frame)

        # Sıfırla / Kopyala
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("↺  Sıfırla")
        reset_btn.setObjectName("secondary")
        reset_btn.clicked.connect(self._reset)
        copy_btn = QPushButton("📋  Değerleri Kopyala")
        copy_btn.setObjectName("secondary")
        copy_btn.clicked.connect(self._copy_values)
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

    def _apply_preset(self, name: str):
        vals = EQ_PRESETS.get(name, [0]*10)
        for band, val in zip(self.bands, vals):
            band.set_value(val)
        self.info_lbl.setText(f"Önayar: {name}")

    def _reset(self):
        for band in self.bands:
            band.set_value(0)
        self.preset_combo.setCurrentText("Düz (Flat)")

    def _copy_values(self):
        vals = [f"{b.get_value():+d}" for b in self.bands]
        text = "  ".join(f"{freq}: {v}" for freq, v in zip(EQ_BANDS, vals))
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _update_info(self):
        vals = [b.get_value() for b in self.bands]
        avg = sum(vals) / len(vals)
        self.info_lbl.setText(f"Ortalama: {avg:+.1f} dB  •  Min: {min(vals):+d}  Max: {max(vals):+d} dB")


# ═══════════════════════════════════════════════════════════════
#  ODA HESABI SEKMESİ
# ═══════════════════════════════════════════════════════════════

class OdaHesabiTab(QWidget):
    """Oda rezonans frekansları (oda modları) hesaplama."""

    SOUND_SPEED = 343.0  # m/s oda sıcaklığında

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("🏠  Oda Modu Analizi")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(ui_interface.make_separator())

        # Girdi
        grid = QGridLayout()
        grid.setSpacing(8)

        params = [
            ("Uzunluk (L):", "5.00", "m"),
            ("Genişlik (G):", "4.00", "m"),
            ("Yükseklik (Y):", "2.50", "m"),
        ]
        self.inputs: list[QDoubleSpinBox] = []
        for row, (lbl, default, unit) in enumerate(params):
            grid.addWidget(QLabel(lbl), row, 0)
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 30.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
            spin.setValue(float(default))
            spin.setSuffix(f"  {unit}")
            spin.setFixedWidth(150)
            grid.addWidget(spin, row, 1)
            self.inputs.append(spin)

        hesapla_btn = QPushButton("  Hesapla")
        hesapla_btn.setFixedWidth(150)
        hesapla_btn.clicked.connect(self._hesapla)
        grid.addWidget(hesapla_btn, 3, 1)

        layout.addLayout(grid)
        layout.addWidget(ui_interface.make_separator())

        # Sonuç
        self.sonuc = QTextEdit()
        self.sonuc.setReadOnly(True)
        self.sonuc.setFont(QFont("Consolas", 11))
        layout.addWidget(self.sonuc)

        # İlk hesaplama
        self._hesapla()

    def _hesapla(self):
        L = self.inputs[0].value()
        G = self.inputs[1].value()
        Y = self.inputs[2].value()
        c = self.SOUND_SPEED

        lines = []
        lines.append(f"ODA BOYUTLARI: {L:.2f}m × {G:.2f}m × {Y:.2f}m")
        lines.append(f"Ses hızı: {c} m/s")
        lines.append("─" * 50)
        lines.append(f"{'Mod (p,q,r)':<14}{'Boyut':<12}{'Frekans':>10}{'Durum':>14}")
        lines.append("─" * 50)

        dims = [("L", L), ("G", G), ("Y", Y)]
        modlar = []

        # Eksenel modlar (tek boyut)
        for n in range(1, 5):
            for ad, d in dims:
                f = (n * c) / (2 * d)
                modlar.append((f, n, ad))

        modlar.sort(key=lambda x: x[0])

        sorunlu_bolgeler = []
        for f, n, ad in modlar[:18]:
            if f < 80:
                durum = "⚠️ Çok düşük"
                sorunlu_bolgeler.append(f)
            elif f < 300:
                durum = "✅ Kontrol et"
            else:
                durum = "  —"
            lines.append(f"  n={n} ({ad:<2})       {ad:<8}  {f:>8.1f} Hz   {durum}")

        lines.append("─" * 50)
        lines.append("")
        lines.append("SCHROEDER FREKANS:  " + f"{200 * math.sqrt(0.3 / (L*G*Y*0.1)):.0f} Hz (yakl.)")
        lines.append("")

        if len(sorunlu_bolgeler) > 0:
            lines.append(f"⚠️  {len(sorunlu_bolgeler)} adet 80 Hz altı mod tespit edildi!")
            lines.append("   Köşelere akustik panel / bas tuzağı önerilir.")
        else:
            lines.append("✅  Oda geometrisi görece dengeli görünüyor.")

        lines.append("")
        lines.append("ÖNERİLEN KABIN YERLEŞİMİ:")
        lines.append(f"  Hoparlörü kapıya yakın (ön duvar ortası) yerleştirin.")
        lines.append(f"  Dinleme noktası ≈ L × 0.618 = {L*0.618:.2f}m uzakta olsun.")

        self.sonuc.setPlainText("\n".join(lines))


# ═══════════════════════════════════════════════════════════════
#  HOPARLÖR EŞLEŞTİRME SEKMESİ
# ═══════════════════════════════════════════════════════════════

class HoparlorEslestirmeTab(QWidget):
    """Thiele-Small parametrelerinden kabin türü önerisi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("🔊  Hoparlör – Kabin Eşleştirme")
        title.setObjectName("title")
        layout.addWidget(title)

        sub = QLabel("Thiele-Small parametrelerini girerek ideal kabin türünü öğrenin")
        sub.setObjectName("dim")
        layout.addWidget(sub)
        layout.addWidget(ui_interface.make_separator())

        # Parametreler
        form = QGridLayout()
        form.setSpacing(8)
        params = [
            ("Fs — Rezonans Frekansı:", 40.0, 20.0, 200.0, 1.0, " Hz"),
            ("Qts — Toplam Q:", 0.40, 0.10, 2.00, 0.01, ""),
            ("Qes — Elektriksel Q:", 0.50, 0.10, 5.00, 0.01, ""),
            ("Qms — Mekanik Q:", 3.00, 0.50, 20.0, 0.1, ""),
            ("Vas — Hava hacmi:", 20.0, 1.0, 500.0, 0.5, " L"),
            ("Xmax — Maks. sapma:", 5.0, 1.0, 50.0, 0.1, " mm"),
            ("Re — DC Direnç:", 6.0, 1.0, 32.0, 0.1, " Ω"),
        ]
        self.spins: dict[str, QDoubleSpinBox] = {}
        keys = ["Fs", "Qts", "Qes", "Qms", "Vas", "Xmax", "Re"]
        for row, (lbl, default, mn, mx, step, suf) in enumerate(params):
            form.addWidget(QLabel(lbl), row, 0)
            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setSingleStep(step)
            spin.setDecimals(2)
            spin.setValue(default)
            if suf:
                spin.setSuffix(suf)
            spin.setFixedWidth(140)
            form.addWidget(spin, row, 1)
            self.spins[keys[row]] = spin

        hesapla = QPushButton("🔍  Kabin Analizi Yap")
        hesapla.clicked.connect(self._analiz)
        form.addWidget(hesapla, len(params), 1)

        layout.addLayout(form)
        layout.addWidget(ui_interface.make_separator())

        self.sonuc = QTextEdit()
        self.sonuc.setReadOnly(True)
        self.sonuc.setFont(QFont("Consolas", 11))
        layout.addWidget(self.sonuc)

        self._analiz()

    def _analiz(self):
        fs  = self.spins["Fs"].value()
        qts = self.spins["Qts"].value()
        qes = self.spins["Qes"].value()
        qms = self.spins["Qms"].value()
        vas = self.spins["Vas"].value()
        xmax = self.spins["Xmax"].value()
        re  = self.spins["Re"].value()

        lines = []
        lines.append("THIELE-SMALL ANALİZ RAPORU")
        lines.append("─" * 52)

        # Kabin türü önerisi
        if qts < 0.3:
            kabin = "Bandpass (4. veya 6. Derece)"
            acik = "Çok düşük Qts: Bandpass kabin güçlü verim sağlar."
        elif qts <= 0.45:
            kabin = "Kapalı Kutu (Sealed)"
            acik = "İdeal sealed: sıkı, kontrollü bas — hi-fi için mükemmel."
        elif qts <= 0.70:
            kabin = "Bassreflex (Port/Vent)"
            acik = "Optimal Qts aralığı: porto açık kutu verim artırır."
        else:
            kabin = "Sonsuz Bölme (Open Baffle) veya OB Hybrid"
            acik = "Yüksek Qts: kapalı kutuda aşırı boom — açık bölme daha uygun."

        lines.append(f"ÖNERİLEN KABİN TÜRÜ:  {kabin}")
        lines.append(f"Gerekçe: {acik}")
        lines.append("")

        # Sealed kutu hacmi
        vb_sealed = vas / (((0.707 / qts)**2) - 1) if qts < 0.707 else vas * 0.5
        lines.append(f"Sealed Kutu Hacmi:    {abs(vb_sealed):.1f} L")

        # Bassreflex
        fb = fs * 0.85
        vb_port = vas * (qts / 0.4)**3.3
        lines.append(f"Bassreflex Fb:        {fb:.1f} Hz")
        lines.append(f"Bassreflex Hacim:     {vb_port:.1f} L")

        # F3 tahmini (sealed)
        f3 = fs * math.sqrt((0.5/qts**2) - 1 + math.sqrt(((0.5/qts**2)-1)**2 + 1)) if qts < 1 else fs * 1.5
        lines.append(f"Sealed F3 (tahmini): {f3:.1f} Hz")

        # Güç
        lines.append("")
        lines.append("─" * 52)
        lines.append(f"Sürücü Re:            {re:.1f} Ω")
        lines.append(f"Xmax:                 {xmax:.1f} mm")
        lines.append(f"Tahmini SPL aralığı:  85–92 dB (1W/1m tipik)")

        # Uyarı
        lines.append("")
        lines.append("─" * 52)
        if qts < 0.2:
            lines.append("⚠️  Çok düşük Qts — yüksek güç tüketimi bekleyin.")
        if vas < 10:
            lines.append("⚠️  Düşük Vas — kompakt kutu gerekir, simüle edin.")
        if xmax > 15:
            lines.append("ℹ️  Yüksek Xmax — subwoofer uygulamalarına uygundur.")
        lines.append("")
        lines.append("NOT: Bu tahminler referans amaçlıdır.")
        lines.append("     Kesin boyut için REW veya WinISD ile doğrulayın.")

        self.sonuc.setPlainText("\n".join(lines))


# ═══════════════════════════════════════════════════════════════
#  HIZLI TAVSİYE SEKMESİ  (Woofer çapı + Oda m²)
# ═══════════════════════════════════════════════════════════════

# Yaygın woofer çaplarına göre tipik Thiele-Small aralıkları
WOOFER_DB = {
    10: {"ad": "10 cm (4\")",  "fs": (80,130), "vas": (3,8),   "xmax": (3,6),  "guc": (20,60),   "tip": "Tiz/orta — raf sistemi, PC hoparlör"},
    13: {"ad": "13 cm (5\")",  "fs": (60,100), "vas": (5,15),  "xmax": (4,8),  "guc": (30,80),   "tip": "Kompakt raf, bookshelf"},
    16: {"ad": "16 cm (6\")",  "fs": (45, 80), "vas": (10,25), "xmax": (5,10), "guc": (50,120),  "tip": "Raf/zemin, hem HiFi hem araç"},
    20: {"ad": "20 cm (8\")",  "fs": (35, 65), "vas": (15,40), "xmax": (6,14), "guc": (80,200),  "tip": "Zemin, subwoofer, küçük oda bas"},
    25: {"ad": "25 cm (10\")", "fs": (25, 50), "vas": (25,70), "xmax": (8,18), "guc": (100,350), "tip": "Subwoofer, orta oda"},
    30: {"ad": "30 cm (12\")", "fs": (18, 40), "vas": (40,120),"xmax": (10,25),"guc": (150,500), "tip": "Subwoofer — geniş oda bas uzmanı"},
    38: {"ad": "38 cm (15\")", "fs": (15, 35), "vas": (80,250),"xmax": (15,35),"guc": (200,800), "tip": "Pro subwoofer, büyük salon/sinema"},
}

def _woofer_key(cap_cm: int) -> int:
    """En yakın veritabanı anahtarını bul."""
    return min(WOOFER_DB.keys(), key=lambda k: abs(k - cap_cm))


class HizliTavsiyeTab(QWidget):
    """
    Kullanıcı yalnızca woofer çapını ve oda alanını girer,
    sistem anında pratik tavsiye üretir.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Başlık
        title = QLabel("⚡  Hızlı Sistem Tavsiyesi")
        title.setObjectName("title")
        layout.addWidget(title)

        sub = QLabel("Woofer çapınızı ve oda boyutunuzu girin — anında tavsiye alın.")
        sub.setObjectName("dim")
        layout.addWidget(sub)
        layout.addWidget(ui_interface.make_separator())

        # Girdi formu
        form_frame = QFrame()
        form_frame.setObjectName("card")
        form = QGridLayout(form_frame)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        # Woofer çapı
        form.addWidget(QLabel("🔊  Woofer Çapı:"), 0, 0)
        self.woofer_combo = QComboBox()
        for k, v in WOOFER_DB.items():
            self.woofer_combo.addItem(v["ad"], k)
        # 30cm varsayılan
        idx = list(WOOFER_DB.keys()).index(30)
        self.woofer_combo.setCurrentIndex(idx)
        self.woofer_combo.setFixedWidth(180)
        form.addWidget(self.woofer_combo, 0, 1)

        # Oda alanı
        form.addWidget(QLabel("🏠  Oda Alanı:"), 1, 0)
        self.alan_spin = QDoubleSpinBox()
        self.alan_spin.setRange(5, 200)
        self.alan_spin.setSingleStep(1)
        self.alan_spin.setDecimals(0)
        self.alan_spin.setValue(20)
        self.alan_spin.setSuffix("  m²")
        self.alan_spin.setFixedWidth(180)
        form.addWidget(self.alan_spin, 1, 1)

        # Tavan yüksekliği
        form.addWidget(QLabel("📐  Tavan Yüksekliği:"), 2, 0)
        self.tavan_spin = QDoubleSpinBox()
        self.tavan_spin.setRange(2.0, 6.0)
        self.tavan_spin.setSingleStep(0.1)
        self.tavan_spin.setDecimals(1)
        self.tavan_spin.setValue(2.5)
        self.tavan_spin.setSuffix("  m")
        self.tavan_spin.setFixedWidth(180)
        form.addWidget(self.tavan_spin, 2, 1)

        # Kullanım amacı
        form.addWidget(QLabel("🎵  Kullanım Amacı:"), 3, 0)
        self.amac_combo = QComboBox()
        self.amac_combo.addItems([
            "Ev HiFi (müzik dinleme)",
            "Ev Sineması",
            "Stüdyo Referans",
            "Parti / Yüksek SPL",
            "Zemin Hoparlör Sistemi",
        ])
        self.amac_combo.setFixedWidth(180)
        form.addWidget(self.amac_combo, 3, 1)

        # Buton
        analiz_btn = QPushButton("⚡  Tavsiye Al")
        analiz_btn.setFixedWidth(180)
        analiz_btn.clicked.connect(self._analiz)
        form.addWidget(analiz_btn, 4, 1)

        layout.addWidget(form_frame)
        layout.addWidget(ui_interface.make_separator())

        # Sonuç
        self.sonuc = QTextEdit()
        self.sonuc.setReadOnly(True)
        self.sonuc.setFont(QFont("Consolas", 11))
        self.sonuc.setMinimumHeight(280)
        layout.addWidget(self.sonuc)

        # İlk çalıştırma
        self._analiz()

    def _analiz(self):
        cap_cm    = self.woofer_combo.currentData()
        alan_m2   = self.alan_spin.value()
        tavan_m   = self.tavan_spin.value()
        amac      = self.amac_combo.currentText()
        hacim_m3  = alan_m2 * tavan_m

        w = WOOFER_DB.get(cap_cm, WOOFER_DB[30])
        fs_min, fs_max   = w["fs"]
        vas_min, vas_max = w["vas"]
        xmax_min, xmax_max = w["xmax"]
        guc_min, guc_max = w["guc"]

        # ─── Hesaplamalar ───────────────────────────────────────
        # Oda hacmine göre önerilen sub sayısı
        if hacim_m3 < 30:
            sub_sayi = "1 adet yeterli"
        elif hacim_m3 < 60:
            sub_sayi = "1–2 adet önerilir"
        else:
            sub_sayi = "2 adet veya daha büyük sürücü"

        # Kabin türü (amaca göre)
        if "Stüdyo" in amac:
            kabin_tur = "Sealed (Kapalı Kutu)"
            kabin_acik = "Stüdyoda faz ve geçici yanıt kritik — sealed zorunlu."
        elif "Yüksek SPL" in amac or "Parti" in amac:
            kabin_tur = "Bassreflex veya Bandpass"
            kabin_acik = "Maksimum verim için bassreflex tercih edin."
        elif "Sinema" in amac:
            kabin_tur = "Sealed veya Bassreflex"
            kabin_acik = "Sinema için derin ve kontrollü bas — sealed önerilir."
        else:
            kabin_tur = "Bassreflex (HiFi için)"
            kabin_acik = "Müzik dinleme: bassreflex geniş frekans + verim sunar."

        # Önerilen kutu hacmi (cm çapına göre kaba tahmin)
        vb_min = vas_min * 0.6
        vb_max = vas_max * 0.8

        # Oda modu baskın frekansı (en kısa kenar)
        kisa_kenar = math.sqrt(alan_m2 * 0.6)  # kare oda tahmini
        f_oda = 343 / (2 * kisa_kenar)

        # Woofer'ın odaya uyumu
        woofer_f3_est = (fs_min + fs_max) / 2
        if woofer_f3_est < f_oda * 0.6:
            uyum = "✅  Woofer odanın bas moduyla uyumlu — derin bas bekleyin."
        elif woofer_f3_est < f_oda:
            uyum = "⚠️  Woofer oda moduna yakın — yerleşim önemli."
        else:
            uyum = "❌  Woofer odanın bas modundan yüksek — bas yetersiz kalabilir."

        # Amplifikatör gücü önerisi
        amfi_guc = int(guc_max * 0.6)

        # ─── Çıktı ─────────────────────────────────────────────
        lines = []
        lines.append("╔══════════════════════════════════════════════════╗")
        lines.append(f"║  HIZLI SİSTEM TAVSİYESİ                          ║")
        lines.append("╚══════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(f"  Woofer:        {w['ad']}")
        lines.append(f"  Oda Alanı:     {alan_m2:.0f} m²  (tavan {tavan_m:.1f}m → {hacim_m3:.0f} m³)")
        lines.append(f"  Kullanım:      {amac}")
        lines.append("")
        lines.append("─" * 52)
        lines.append("  WOOFER BİLGİSİ")
        lines.append("─" * 52)
        lines.append(f"  Tipik Fs:      {fs_min}–{fs_max} Hz")
        lines.append(f"  Tipik Vas:     {vas_min}–{vas_max} L")
        lines.append(f"  Tipik Xmax:    {xmax_min}–{xmax_max} mm")
        lines.append(f"  Güç aralığı:   {guc_min}–{guc_max} W RMS")
        lines.append(f"  Kullanım yeri: {w['tip']}")
        lines.append("")
        lines.append("─" * 52)
        lines.append("  KABİN ÖNERİSİ")
        lines.append("─" * 52)
        lines.append(f"  Tür:           {kabin_tur}")
        lines.append(f"  Gerekçe:       {kabin_acik}")
        lines.append(f"  Hacim aralığı: {vb_min:.0f}–{vb_max:.0f} L (tahmini)")
        lines.append("")
        lines.append("─" * 52)
        lines.append("  ODA–WOOFER UYUMU")
        lines.append("─" * 52)
        lines.append(f"  Oda mod frekansı (tahmini): {f_oda:.0f} Hz")
        lines.append(f"  Woofer F3 (tahmini):        {woofer_f3_est:.0f} Hz")
        lines.append(f"  {uyum}")
        lines.append(f"  Kaç woofer:    {sub_sayi}")
        lines.append("")
        lines.append("─" * 52)
        lines.append("  AMPLİFİKATÖR & SİSTEM")
        lines.append("─" * 52)
        lines.append(f"  Önerilen amfi gücü: en az {amfi_guc} W RMS / kanal")

        if cap_cm >= 25 and "HiFi" in amac:
            lines.append("  💡  30cm+ sub için ayrı subwoofer amplifikatörü öneririz.")
        if alan_m2 > 30 and cap_cm < 25:
            lines.append(f"  ⚠️  {alan_m2:.0f}m² oda için {cap_cm}cm woofer küçük kalabilir.")
            lines.append(f"      30cm (12\") veya 2×{cap_cm}cm kullanmayı düşünün.")
        if alan_m2 <= 20 and cap_cm >= 30:
            lines.append(f"  ⚠️  {cap_cm}cm woofer {alan_m2:.0f}m² için güçlü — EQ ile kontrol edin.")
            lines.append("      Oda modları sorun çıkarabilir, akustik panel ekleyin.")

        lines.append("")
        lines.append("─" * 52)
        lines.append("NOT: Değerler tipik aralıklara dayalı tahminidir.")
        lines.append("     Kesin hesap için Thiele-Small parametrelerinizi girin.")

        self.sonuc.setPlainText("\n".join(lines))


# ═══════════════════════════════════════════════════════════════
#  ANA HİFİ TAB
# ═══════════════════════════════════════════════════════════════

class HiFiTab(QWidget):
    """DD1 HiFi Stüdyo — Ana sekme, alt sekmeleri barındırır."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # İç sekmeler
        inner = QTabWidget()
        inner.setDocumentMode(True)
        inner.addTab(HizliTavsiyeTab(),       "⚡  Hızlı Tavsiye")      # ← YENİ, ilk sıra
        inner.addTab(FreqAnalizTab(),          "📈  Frekans Analizi")
        inner.addTab(EQTab(),                  "🎚  10 Bantlı EQ")
        inner.addTab(OdaHesabiTab(),           "🏠  Oda Modu Hesabı")
        inner.addTab(HoparlorEslestirmeTab(),  "🔊  Hoparlör Eşleştirme")

        inner.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 18px;
                min-width: 110px;
                font-size: 12px;
            }
        """)

        layout.addWidget(inner)

