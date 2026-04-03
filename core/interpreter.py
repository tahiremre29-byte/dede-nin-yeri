"""
core/interpreter.py
DD1 Ortak Intake / Interpreter Katmanı

GÖREVİ:
- İlk kullanıcı mesajını alır (history ile birleştirilmiş halini).
- Domain belirler (car_audio, home_audio, outdoor).
- Temel entiteleri çıkarır (çap, woofer modeli, bagaj ölçüsü vb.).
- Canonical slot/state üretir.
- Eksik alanları tespit eder (missing_fields).
- Ajanlara yönlendirme (routing) için standart bir yapı (örneğin IntakePacket veya dict) sağlar.

KURAL:
Bu katman uzman karar vermez (örn. litre hesaplamaz, montaj tavsiyesi vermez).
Sadece normalize eder ve yönlendirme için "Tek Gerçek Kaynak" (Source of Truth) üretir.
"""

from __future__ import annotations
import re

from core.router import classify_intent

_BASS_CHAR_MAP = {
    r"patlamalı|pump|agresif":      "patlamalı",
    r"tok|derin|sql|warm":          "tok",
    r"spl|yarış|sert|impact":       "SPL",
    r"günlük|daily|müzik|clean":    "günlük",
    r"flat|ntr|referans":           "flat",
}

def extract_bass_char(message: str) -> str:
    """Mesajdan bas karakterini çıkarır."""
    for pattern, char in _BASS_CHAR_MAP.items():
        if re.search(pattern, message, re.IGNORECASE):
            return char
    return "günlük_bas"  # fallback — 'SQL' yerine tag kullan

def extract_usage_domain(message: str) -> str:
    """Mesajdan kullanım alanını çıkarır."""
    if re.search(r"açık.?hava|acik.?hava|dış.?sistem|dis.?sistem|dış.?mekan|dis.?mekan|outdoor|pro.?audio|sahne.?ses|pa.?sistem|anfi|konser|atölye|atolye|dükkan|dukkan|home.?audio|ev.?sistemi", message, re.IGNORECASE):
        if re.search(r"pro.?audio|pa.?sistem|sahne|konser|anfi", message, re.IGNORECASE):
            return "pro_audio"
        if re.search(r"ev.?sistemi|home.?audio", message, re.IGNORECASE):
            return "home_audio"
        return "outdoor"
    return "car_audio"

# -- Domain Sinyalleri --
_HOME_SIGNALS = [
    'evde', 'ev kullan', 'ev için', 'odam', 'oda', 'salon', 'metrekare', 'm2',
    'apartman', 'müstakil', 'yatak oda', 'oturma', 'ev sistemi', 'home',
    'hi-fi', 'hifi', 'stereo', 'living room', 'müzik odası',
]
_OUTDOOR_SIGNALS = [
    'açık hava', 'outdoor', 'sahne', 'konser', 'festival', 'sokak',
    'dış mekan', 'taşıma', 'etkinlik', 'park', 'pro ses', 'pro audio',
    'line array', 'subwoofer array', 'dış sistem',
]
_CAR_SIGNALS = [
    'araç', 'araba', 'sedan', 'suv', 'hatchback', 'bagaj', 'torpido',
    'oto', 'otomobil', 'car', 'kapı', 'kafe', 'kasa', 'panelvan',
]

# -- Enclosure Preferences --
_SEALED_PATTERNS = [
    r'\bkap[aâ]l[ıi]\b', r'\bsealed\b', r'\bseale[d]?\b',
    r'\bclosed\b', r'\binfra[- ]bass\b', r'\bkapalı kutu\b', r'\bkabin kapal',
]
_PORTED_PATTERNS = [
    r'\bportlu\b', r'\bported\b', r'\breflex\b',
    r'\bbas reflexi\b', r'\bport(?:lu)?\s*kutu\b', r'\bventted\b', r'\bvented\b',
]
_BANDPASS_PATTERNS = [r'\bbandpass\b', r'\bbant\s*geç\b']

# -- Boyut / Çap Kalıpları --
_SIZE_PATTERNS = [
    (r'(\d{2,4})\s*(?:mm\b|milim(?:etre)?)', 'mm', 1/25.4),
    (r'(\d{1,3})\s*(?:cm\b|santim(?:etre)?)', 'cm', 1/2.54),
    (r'(\d{1,2})\s*(?:inç|inch|inc\b|")',    'inch', 1.0),
]

# -- Markalar ve Sürücü Tipleri --
_BRANDS = [
    'jbl', 'focal', 'alpine', 'pioneer', 'hertz', 'sundown', 'skar',
    'crescendo', 'kicker', 'rockford', 'infinity', 'kenwood', 'sony',
    'morel', 'scanspeak', 'dayton', 'peerless', 'tang band',
    'dd audio', 'dd', 'fi audio', 'incriminator', 'obsidian',
    'for-x', 'forx', 'mobass', 'massive', 'qline', 'reiss', 'reis', 'cadence',
    'machete', 'deaf bonce', 'pride', 'soundmax', 'edison', 'x-max',
    'mtx', 'soundstream', 'hifonics', 'cerwin', 'vega', 'punch',
    'audiobahn', 'orion', 'memphis', 'planet audio', 'audiopipe',
]

_DRIVER_TYPE_MAP = {
    'subwoofer': ['subwoofer', 'sub woofer'],
    'bas':       ['bas ', 'bass ', 'bas\b', 'bass\b'],
    'woofer':    ['woofer'],
    'hoparlör':  ['hoparlör', 'hoparlor', 'speaker'],
    'coax':      ['coax', 'takım hoparlör'],
}

from core.router import _MODEL_PATTERNS

# -- Araç Tipleri --
_VEHICLE_MAP = {
    'sedan':    ['sedan', 'saloon', 'egea', 'megane', 'corolla', 'civic', 'passat', 'focus'],
    'hatchback':['hatchback', 'hb', 'clio', 'polo', 'golf', 'fiesta', 'i20', 'corsa', 'leon', 'astra'],
    'suv':      ['suv', '4x4', 'jeep', 'qashqai', 'tucson', 'sportage', 'duster', '3008', 'tiguan', 'kodiaq'],
    'panelvan': ['transit', 'panelvan', 'panel', 'sprinter', 'doblo', 'fiorino', 'caddy', 'kangoo', 'partner', 'berlingo', 'combo', 'hafif ticari', 'ticari', 'transporter', 'vito', 'caravelle', 'custom', 'courier', 'rifter'],
    'pickup':   ['pickup', 'kamyonet', 'hilux', 'ranger', 'l200', 'amarok', 'navara', 'd-max'],
}

def _extract_vehicle_type(msg_lower: str) -> tuple[str | None, str | None]:
    """Araç tipi ve modelini tam eşleşme ile bulur."""
    generic_keys = ['sedan', 'saloon', 'hatchback', 'hb', 'suv', '4x4', 'jeep', 'panelvan', 'panel', 'hafif ticari', 'ticari', 'pickup', 'kamyonet']
    for vt, keys in _VEHICLE_MAP.items():
        for k in keys:
            if re.search(r'\b' + re.escape(k) + r'\b', msg_lower):
                model = k.title() if k not in generic_keys else None
                return vt, model
    return None, None

def _detect_usage_domain(msg_lower: str, router_domain: str = 'car_audio') -> str:
    """Domain sınıflandırmasını yapar."""
    if any(k in msg_lower for k in _HOME_SIGNALS):
        return 'home_audio'
    if any(k in msg_lower for k in _OUTDOOR_SIGNALS):
        return 'outdoor'
    if any(k in msg_lower for k in _CAR_SIGNALS):
        return 'car_audio'
        
    if router_domain in ('home_audio', 'outdoor', 'car_audio'):
        return router_domain
    if router_domain == 'pro_audio':
        return 'outdoor'
        
    return 'car_audio'

def _extract_enclosure_pref(message: str) -> tuple[str | None, str | None, str]:
    """Kabin tipini çıkarır."""
    for pat in _SEALED_PATTERNS:
        m = re.search(pat, message, re.IGNORECASE)
        if m: return m.group(0), 'sealed', 'user_explicit'
        
    for pat in _PORTED_PATTERNS:
        m = re.search(pat, message, re.IGNORECASE)
        if m: return m.group(0), 'ported', 'user_explicit'
        
    for pat in _BANDPASS_PATTERNS:
        m = re.search(pat, message, re.IGNORECASE)
        if m: return m.group(0), 'bandpass', 'user_explicit'
        
    return None, None, 'default'

def _extract_size(message: str) -> tuple[str | None, float | None, str | None, int | None, int | None]:
    """Çap boyutunu çıkarır."""
    
    # Bagaj ölçüsü x çarpı y vs. kısımlarını metinden geçici olarak çıkaralım ki
    # 80x40x50 cm gibi bir değerdeki "80" çap sanılmasın.
    clean_msg = re.sub(r'\d{2,3}\s*[x×*\s]\s*\d{2,3}\s*[x×*\s]\s*\d{2,3}', '', message)
    clean_msg = re.sub(r'(?:en|genişlik)\s*\d{2,3}.*?yükseklik\s*\d{2,3}.*?derinlik\s*\d{2,3}', '', clean_msg, flags=re.IGNORECASE)

    for pat, unit, factor in _SIZE_PATTERNS:
        m = re.search(pat, clean_msg, re.IGNORECASE)
        if m:
            raw_val = float(m.group(1))
            ext_raw = f"{int(raw_val)} {unit}"
            inf_in = round(raw_val * factor)
            d_mm = int(raw_val) if unit == 'mm' else (int(raw_val * 10) if unit == 'cm' else round(raw_val * 25.4))
            
            # Eğer adam "80 cm" dediyse (asla subwoofer boyutu olmaz) bunu reddetme kontrolü: 
            if unit == 'cm' and raw_val > 50:
                continue
                
            return ext_raw, raw_val, unit, inf_in, d_mm

    # İkinci deneme (saha metinleri)
    m_saha = re.search(r'(\d{1,4})\s*(mm|cm|santim|milim)\s*(?:sub|subwoofer|bass|bas|hoparlor|hoparlör|woofer|kabin|kutu)', clean_msg, re.IGNORECASE)
    if m_saha:
        raw_val = float(m_saha.group(1))
        u = m_saha.group(2).lower()
        factor, norm_u = (1/25.4, 'mm') if 'm' in u else (1/2.54, 'cm')
        if norm_u == 'cm' and raw_val > 50:
            return None, None, None, None, None
            
        ext_raw = f"{int(raw_val)} {norm_u}"
        inf_in = round(raw_val * factor)
        d_mm = int(raw_val) if 'm' in u else int(raw_val * 10)
        return ext_raw, raw_val, norm_u, inf_in, d_mm

    # OBS-009: ürün kodu içinden çap (dd815→15", w12→12")
    # Kural: harf(ler)+rakamlar; rakamların endswith geçerli subwoofer çapı olmalı
    # Güvence: jbl1000w, hertz300 gibi geçersiz boyutları reddeder
    _VALID_IN = {6, 8, 10, 12, 13, 15, 18, 21}
    _CODE_PAT = r'(?<![0-9])[a-z]{1,5}(\d{1,5})(?![0-9a-z])'
    m_code = re.search(_CODE_PAT, clean_msg, re.IGNORECASE)
    if m_code:
        digits = m_code.group(1)
        for _vi in sorted(_VALID_IN, reverse=True):
            s = str(_vi)
            if digits.endswith(s):
                prefix = digits[:-len(s)]
                if prefix == '' or (prefix.isdigit() and len(prefix) <= 2):
                    _mm = round(_vi * 25.4)
                    return f"{_vi} inch", float(_vi), 'inch', _vi, _mm

    return None, None, None, None, None

def _extract_brand_model_type(message: str, msg_lower: str) -> tuple[str | None, str | None, str | None]:
    """Marka, model ve sürücü tipini çıkarır."""
    brand = None
    brand_raw = None  # orijinal case'de marka metni
    for b in _BRANDS:
        if b in msg_lower:
            brand = b.title()
            brand_raw = b
            break

    driver_type = None
    for dtype, keys in _DRIVER_TYPE_MAP.items():
        if any(k.strip().lower() in msg_lower for k in keys):
            driver_type = dtype
            break

    woofer_model = None
    for pat in _MODEL_PATTERNS:
        matches = list(pat.finditer(message))
        best_raw = None
        for m in reversed(matches):
            raw = m.group(0).strip().rstrip(",;").strip()
            stop = re.search(
                r'\s+(?:bas\b|bass\b|kabin|kutu|istiyorum|var|yok|sistem|tasar[ıi]m|yap|edelim|acik|a\u00e7\u0131k|hava|calacak|\u00e7alacak|sedan|arac|ara\u00e7|dis|d\u0131\u015f|'
                r'\d{1,4}\s*(?:mm\b|milim|inc|inch|in\u00e7|\"|inç|cm\b|santim)|'
                r'\d{2,3}\s*(?:hz|hertz|w\b|watt))',
                raw, re.IGNORECASE
            )
            if stop:
                raw = raw[:stop.start()].strip()
            if not raw: continue
            
            # Check if this raw match contains more than just the brand
            test_brand = None
            first_word = raw.split()[0].lower()
            if first_word in _BRANDS:
                test_brand = first_word.title()
            
            suffix = raw.lower().replace(str(test_brand).lower() if test_brand else "", "").strip()
            if suffix:
                best_raw = raw
                if not brand and test_brand:
                    brand = test_brand
                break
        
        if best_raw:
            woofer_model = best_raw
            break

    # Fallback: Marka bulunduysa fakat bitişik model bulunamadıysa:
    # Ayrı yazılmış model kodlarını (örn. "gt12", "ts-w304r", "l7") mesajda ara.
    if woofer_model is None and brand:
        model_like_pat = re.compile(r'\b([a-z]+-?[0-9]+[a-z0-9-]*|[0-9]+-?[a-z]+[a-z0-9-]*)\b', re.IGNORECASE)
        m_likes = model_like_pat.findall(message)
        valid_models = []
        for mf in m_likes:
            mf_low = mf.lower()
            # Ölçü birimleri, frekans ve güçleri filtrele
            if not re.fullmatch(r'\d+(cm|santim|mm|milim|inc|inch|inç|hz|w|watt)', mf_low):
                if mf_low not in ['kabin', 'arac', 'doğru', 'zaten', 'önemi']:  # safety
                    valid_models.append(mf)
        
        if valid_models:
            # En son olanı al (konuşma geçmişinde en son eklenendir)
            woofer_model = f"{brand} {valid_models[-1]}"

    model_status = "missing"
    if woofer_model:
        suffix = woofer_model.lower().replace(str(brand).lower() if brand else "", "").strip()
        if not suffix:
            model_status = "missing"
            woofer_model = None
        elif re.fullmatch(r'\d{3,4}w?', suffix):
            model_status = "partial"
        else:
            model_status = "exact"
    elif brand:
        model_status = "missing"

    return brand, driver_type, woofer_model, model_status

def _extract_trunk_dims(message: str, msg_lower: str) -> tuple[int | None, int | None, int | None, str | None]:
    """Bagaj ölçülerini ve fiziksel kısıt notlarını çıkarır. Esnek ifadelere izin verir."""
    tw, th, td = None, None, None
    m_dims = re.search(r'(\d{2,3})\s*[x×*\s]\s*(\d{2,3})\s*[x×*\s]\s*(\d{2,3})', message)
    if m_dims:
        tw, th, td = int(m_dims.group(1)), int(m_dims.group(2)), int(m_dims.group(3))
    else:
        # Tekil ölçüleri bağımsız olarak ara
        m_w = re.search(r'(?:en|geni[sş]lik)\s*(\d{2,3})', message, re.IGNORECASE)
        m_h = re.search(r'(?:y[üu]kseklik|boy)\s*(\d{2,3})', message, re.IGNORECASE)
        m_d = re.search(r'(?:derin|derinlik|uzunluk)\s*(\d{2,3})', message, re.IGNORECASE)
        
        if m_w: tw = int(m_w.group(1))
        if m_h: th = int(m_h.group(1))
        if m_d: td = int(m_d.group(1))

    # Kullanıcı esnek bir ifade kullandıysa (örn. "yükseklik farketmez", "bagaj büyük")
    flexible = bool(re.search(r'farketmez|fark\s*etmez|sorun\s*yok|s[ıi]k[ıi]nt[ıi]\s*yok|geni[sş]|b[üu]y[üu]k|esnek|salla', msg_lower))

    # Kullanıcı en az bir boyut belirttiyse veya esnekse, eksik loop'unda takılmamak için 999 (limitsiz) ata
    if (tw is not None or th is not None or td is not None) or flexible:
        if tw is None: tw = 999
        if th is None: th = 999
        if td is None: td = 999

    notes = []
    if re.search(r'dar\s*a[gğ][ıi]z', msg_lower): notes.append('dar ağız')
    if re.search(r'stepne', msg_lower): notes.append('stepne var')
    if re.search(r'e[gğ]im', msg_lower): notes.append('eğimli yüzey')
    if re.search(r'[çc][ıi]k[ıi]nt[ıi]', msg_lower): notes.append('çıkıntı var')
    if re.search(r'yer\s*yok|dar', msg_lower): notes.append('sınırlı alan')
    
    return tw, th, td, (', '.join(notes) if notes else None)

def _infer_goal(msg_lower: str) -> str | None:
    """
    Kullanıcının birincil frekans yönünü çıkarır.

    DD1 Dil Doktrini (§9.2) + Taksonomi v2:
      Dönüş: 'bas' | 'mid' | 'tiz' | None
      - 'bas' : Düşük frekans odaklı (20–100 Hz). Sub, midbass, punch, saha bas ifadeleri.
      - 'mid' : Orta frekans odaklı (100–5k Hz). SQ, sahne, detay, spor, midrange.
      - 'tiz' : Yüksek frekans / hava / detay (5k+ Hz).
      - None  : Sinyal yetersiz, soru gerekiyor.

    NOT: 'sert' gibi belirsiz saha ifadeleri direkt teknik alta sınıfa çakılmaz.
    _goal_needs_clarification() bağlam sorusu için ayrıca çağrılır.
    """
    # ── Katman 1: Bas odaklı — güç / alt frekans / SPL sinyalleri ───────────
    if re.search(r'\bsql\b|sound\s*quality\s*level', msg_lower):
        return 'bas'   # SQL güç gerektirir — bas yönelim
    if re.search(r'\bspl\b|yar[iı][şs]|impact', msg_lower):
        return 'bas'

    # Saha dili — dışa dönük / sahne / görünürlük sinyalleri
    if re.search(r'bagaj\s*a[çc]t[ıi]|bagaj[ıi]\s*a[çc]|dışa\s*[çc]al|d[ıi][şs]ar[ıi]\s*ver', msg_lower):
        return 'bas'
    if re.search(r'geldi[gğ]im\s*belli|geld[ıi]m\s*belli|gelince\s*belli|duyulsun|cadde\s*mod', msg_lower):
        return 'bas'
    if re.search(r'\bpanca\b|brezilya\s*sistem|pancad[aã]o|d[iı][şs]a\s*d[oö]n[üu]k', msg_lower):
        return 'bas'
    if re.search(r'canavar[ıi]m\s*olsun|canavar\s*kur|maksimum\s*g[üu][çc]', msg_lower):
        return 'bas'

    # OBS-009: saha vuruş sinyalleri — belirsiz ama bas yönelimli başlangıç
    if re.search(r'iyi\s*vur|iyivur|vursun|sert\s*vur|agresif|punch|bass\s*head|titretsin|inletsin|ci[gğ]er', msg_lower):
        return 'bas'

    # Günlük / konfor bas
    if re.search(r'tok|g[üu]nl[üu]k|daily|normal\s*bas|ses\s*dolsun|yumu[sş]ak', msg_lower):
        return 'bas'
    if re.search(r'\bbas\b|\bbass\b', msg_lower):
        return 'bas'

    # ── Katman 2: Mid odaklı — kalite / sahne / müzik sinyalleri ────────────
    if re.search(r'\bsound\s*quality\b|\bsq\b', msg_lower):
        return 'mid'   # SQ/SQL ayrımı _goal_needs_clarification ile yapılır
    if re.search(r'm[üu]zik\s*g[üu]zel|detay|sahne|vokal\s*belli|midrange', msg_lower):
        return 'mid'
    if re.search(r'spor|sport|orta', msg_lower):
        return 'mid'
    if re.search(r'\bm[üu]zik\b', msg_lower):
        return 'mid'

    # ── Katman 3: Tiz odaklı — hava / açıklık / tiz detay ──────────────────
    if re.search(r'tiz\s*a[çc]|vokal\s*a[çc]|hava\s*var|\btiz\b', msg_lower):
        return 'tiz'

    return None




# Bağlam netleştirme gerektiren saha ifadeleri (DD1 Dil Doktrini §9.2/§9.3)
_CLARIFICATION_PATTERNS: list[tuple[str, str]] = [
    # (regex, hint_key)
    (r'bagaj\s*a[çc]t[ıi]|bagaj[ıi]\s*a[çc]|dışa\s*[çc]al',      'ambiguous_scene'),
    (r'geldi[gğ]im\s*belli|geld[ıi]m\s*belli|duyulsun',            'ambiguous_visibility'),
    (r'\bpanca\b|brezilya\s*sistem|pancad[aã]o',                    'ambiguous_scene'),
    (r'canavar[ıi]m\s*olsun|canavar\s*kur',                         'ambiguous_aggressive'),
    (r'vursun\s*gitsin|sert\s*vur(?!uş)|(?<!\w)sert(?!\w)',         'ambiguous_aggressive'),
    (r'\bsq\b(?!\s*l)',                                              'sq_sql'),
    (r'ses\s*dolsun',                                                'ambiguous_fill'),
]


def _goal_needs_clarification(msg_lower: str) -> tuple[bool, str | None]:
    """
    Belirsiz saha ifadesi var mı kontrol eder.

    Döner: (needs_clarification: bool, hint: str | None)
      hint → ustabasi._format_question("goal") için bağlam ipucu:
        'ambiguous_aggressive' → sub bass mı midbass kick mı?
        'ambiguous_visibility' → araç içi derin bas mı cadde modu mu?
        'ambiguous_scene'      → dışa mı içe mi çalıyor?
        'sq_sql'               → SQ mu SQL mi?
        'ambiguous_fill'       → midrange mi sub mu?
    """
    for pattern, hint in _CLARIFICATION_PATTERNS:
        if re.search(pattern, msg_lower):
            return True, hint
    return False, None



def _get_missing_fields(domain: str, ext: dict) -> list[str]:
    """Domain'e göre eksik (zorunlu) alanları hesaplar."""
    missing = []
    
    brand = ext.get('brand')
    model_status = ext.get('model_status', 'missing')
    
    # Kullanıcı markayı verdiyse ama modeli vermediyse modelini sormalıyız.
    if model_status == 'missing':
        if not brand:
            missing.append('brand_or_model')
        else:
            missing.append('partial_model')
    elif model_status == 'partial':
        missing.append('partial_model')
        
    has_diameter = bool(ext.get('diameter_raw') or ext.get('diameter_mm') or ext.get('diameter_inch'))

    if not has_diameter: missing.append('diameter')
    
    if domain == 'home_audio':
        if not ext.get('room_size_m2'): missing.append('room_size')
        if not ext.get('goal'): missing.append('goal')
        if not ext.get('placement_notes'): missing.append('placement')
    elif domain == 'outdoor':
        if not ext.get('goal'): missing.append('goal')
        if not ext.get('target_hz'): missing.append('target_hz')
    else: # car_audio
        if not ext.get('vehicle_type'): missing.append('vehicle_type')
        if not (ext.get('trunk_width_cm') is not None): missing.append('trunk_dims')
        
    return missing

def _get_field_labels(domain: str) -> dict[str, str]:
    if domain == 'home_audio':
        return {
            'brand_or_model': 'marka / model', 'diameter': 'sürücü çapı',
            'room_size': 'oda boyutu (m²)', 'goal': 'müzik karakteri',
            'placement': 'kutu yerleşimi', 'living_sit': 'yaşam durumu',
        }
    elif domain == 'outdoor':
        return {
            'brand_or_model': 'marka / model', 'diameter': 'sürücü çapı',
            'goal': 'atış karakteri', 'target_hz': 'hedef frekans',
            'mounting': 'montaj tipi',
        }
    return { # car_audio
        'vehicle_type': 'araç tipi', 'brand_or_model': 'marka / model',
        'diameter': 'sürücü çapı', 'goal': 'hedef kullanım',
        'trunk_dims': 'bagaj ölçüsü',
    }

def _next_questions(missing: list[str], domain: str) -> list[str]:
    """Eksik alanlara göre sorulacak soruları belirler (ilk 2'sini döner)."""
    if domain == 'home_audio':
        PRIORITY = ['room_size', 'placement', 'goal', 'brand_or_model', 'diameter']
        Q_TEXT = {
            'room_size': 'Odanın boyutu ne kadar? (m² olarak söyleyebilirsin)',
            'placement': 'Kutuyu nereye koymayı düşünüyorsun? (köşe / duvara yakın / orta?)',
            'goal': 'Müzik karakteri ne olsun? (tok bas / geniş hacim / referans kalite?)',
            'brand_or_model': 'Sürücü markası veya modeli nedir?',
            'diameter': 'Sürücü çapı ne? (cm / inch)',
        }
    elif domain == 'outdoor':
        PRIORITY = ['goal', 'brand_or_model', 'diameter', 'target_hz']
        Q_TEXT = {
            'goal': 'Atış karakteri ne olsun? (SPL / sürekli müzik / geniş alan?)',
            'brand_or_model': 'Sürücü markası veya modeli?',
            'diameter': 'Sürücü çapı ne?',
            'target_hz': 'Hedef tuning frekansı? (Hz olarak)',
        }
    else:  # car_audio
        PRIORITY = ['partial_model', 'brand_or_model', 'diameter', 'vehicle_type', 'goal', 'trunk_dims']
        Q_TEXT = {
            'partial_model': 'Tamam, bu işi halledebiliriz. Markanın tam modelini yaz, sana uygun kabini çıkaralım.',
            'brand_or_model': 'Tamam, buna uygun kabin çıkarabiliriz. Basın marka ve tam modelini yaz, doğru yerden başlayalım.',
            'diameter': 'Sürücü çapı ne kadar?',
            'vehicle_type': 'Güzel, cihaz belli oldu. Şimdi aracına uygun litreli kabini kuralım. Aracı söyle, oradan devam edelim.',
            'goal': 'Önceliğin temiz dinlemek mi yoksa daha yüksek ses mi?',
            'trunk_dims': 'Tamam, cihaz ve araç belli oldu. Bu cihaza göre elimizde mantıklı kabin yolları var. Şimdi bagajda ne kadar yer ayırabileceğini söyle, sana uygun yapıyı netleştirelim.',
        }
    questions = [Q_TEXT[f] for f in PRIORITY if f in missing]
    return questions[:1]

def _calculate_fit(tw: int | None, th: int | None, td: int | None, diameter_mm: int | None, diameter_inch: int, notes: str | None) -> tuple[str | None, str | None]:
    """Araç bagajına sığma analizi (Usta-style comment)."""
    if not tw or not th or not td:
        return None, None
        
    box_w_est = diameter_mm + 60 if diameter_mm else 400
    box_h_est = diameter_mm + 80 if diameter_mm else 450
    box_d_est = 300
    
    tw_mm = int(tw) * 10 if tw is not None else 0
    th_mm = int(th) * 10 if th is not None else 0
    td_mm = int(td) * 10 if td is not None else 0
    
    orientations = [
        ('normal (yana yatık)', box_w_est <= tw_mm and box_h_est <= th_mm and box_d_est <= td_mm),
        ('dik (ayakta)', box_w_est <= tw_mm and box_d_est <= th_mm and box_h_est <= td_mm),
        ('derin (öne bakan)', box_d_est <= tw_mm and box_h_est <= th_mm and box_w_est <= td_mm),
    ]
    fitting = [o for o, fits in orientations if fits]
    
    fit_status = None
    usta_comment = None
    
    if len(fitting) >= 2:
        fit_status = 'fits_easy'
        fit_desc = 'İki yön de uygun' if len(fitting) == 2 else 'Her yönde sığıyor'
        usta_comment = f'Reis bu ölçüye {diameter_inch}" rahat oturur. {fit_desc}.'
    elif len(fitting) == 1:
        fit_status = 'fits_tight'
        fit_dir = fitting[0]
        usta_comment = f'Sıkı ama {fit_dir} yönünde sığıyor. Port yerleşimi için derinliği iyi kullanmak lazım.'
    else:
        fit_status = 'no_fit'
        usta_comment = f'Bu bagaj bu işi sıkıyor. Ya kutu tipini değiştiririz ({diameter_inch}" için kapalı kutu düşünebiliriz) ya da hedefi revize ederiz.'

    if notes:
        usta_comment += f" Not: {notes}."
    if 'dar ağız' in (notes or ''):
        usta_comment += " Bagaj ağzı dar, kutu sığsa bile montajda uğraştırır."
        
    return fit_status, usta_comment

def parse_message(message: str, context: dict | None = None) -> dict:
    """
    Ana public fonksiyon. Gelen mesajı analiz edip,
    canonical state'i döner. chat_service._rule_based_extract'ın drop-in değişimidir.
    """
    msg_lower = message.lower()
    
    from core.router import quick_route

    _CLARIFICATION_TERMS = [
        'bagaj önceli', 'bagaj onceligi', 'bagaj ne demek', 'ne demek', 'ne anlama',
        'nasıl seçilir', 'ne oluyor', 'nedir', 'ne fark', 'açıkla', 'anlat',
        'sql nedir', 'sbp nedir', 'tuning nedir', 'port nedir',
        'kapalı ne', 'portlu ne', 'enclosure ne',
    ]
    _GLOSSARY_TERMS = [
        'bagaj önceliği nedir', 'bagaj onceligi nedir', 'bagaj nedir',
        'portlu nedir', 'kapalı nedir', 'sql nedir', 'sbp nedir',
        'tuning nedir', 'qts nedir', 'fs nedir', 'vas nedir', 'xmax nedir',
        'port nedir', 'faz ne', 'verimlilik nedir',
    ]

    if any(g in msg_lower for g in _GLOSSARY_TERMS):
        intent, conf = 'glossary_explanation', 0.97
    elif any(c in msg_lower for c in _CLARIFICATION_TERMS):
        intent, conf = 'clarification_request', 0.88
    else:
        intent, conf = classify_intent(message)

    agent, _, _ = quick_route(message)
    bass_char = extract_bass_char(message)
    router_domain = extract_usage_domain(message)

    usage_domain = _detect_usage_domain(msg_lower, router_domain)
    enc_raw, enc_norm, enc_src = _extract_enclosure_pref(message)
    if not enc_norm:
        enc_norm, enc_src = 'ported', 'inferred'

    size_raw, size_val, size_unit, size_in, size_mm = _extract_size(message)
    diameter_inch = size_in if size_in else 12

    brand, driver_type, woofer_model, model_status = _extract_brand_model_type(message, msg_lower)
    
    target_hz = None
    m_hz = re.search(r'(\d{2,3})\s*(?:hz|hertz)', message, re.IGNORECASE)
    if m_hz: target_hz = float(m_hz.group(1))

    rms_power = None
    m_rms = re.search(r'(\d{2,4})\s*(?:[Ww](?:att)?|rms)', message, re.IGNORECASE)
    if m_rms: rms_power = float(m_rms.group(1))

    # Details
    room_size_m2, placement_notes, living_situation = None, None, None
    vehicle_type, tw, th, td, trunk_notes = None, None, None, None, None
    
    if usage_domain == 'home_audio':
        m_rm = re.search(r'(\d{1,3})\s*(?:m2|m²|metrekare|metre kare)', message, re.IGNORECASE)
        if m_rm: room_size_m2 = int(m_rm.group(1))
        
        _PLACE_HINTS = {'köşe': 'köşe yerleşim', 'duvar': 'duvara yakın', 'orta': 'oda ortası', 'dolap': 'dolap yanı', 'yatak': 'yatak odası'}
        for k, v in _PLACE_HINTS.items():
            if k in msg_lower:
                placement_notes = v; break
                
        if 'apartman' in msg_lower: living_situation = 'apartment'
        elif 'müstakil' in msg_lower or 'villa' in msg_lower: living_situation = 'standalone'
        elif 'stüdyo' in msg_lower or 'studio' in msg_lower: living_situation = 'studio'
    elif usage_domain == 'car_audio':
        vehicle_type, vehicle_model = _extract_vehicle_type(msg_lower)
        tw, th, td, trunk_notes = _extract_trunk_dims(message, msg_lower)

    goal = _infer_goal(msg_lower)
    goal_needs_clarification, goal_hint = False, None  # DEVRE DIŞI: gereksiz soru açıyor

    # Core output panel
    normalized_panel = {
        "domain": usage_domain,
        "brand": brand,
        "woofer_model": woofer_model or None,   # tam model adı — ses_ustasi bu key'i okur
        "driver_type": driver_type,
        "diameter_raw": size_raw,
        "diameter_mm": size_mm,
        "diameter_inch": size_in,
        "model_status": model_status,
        "enclosure_preference": enc_norm if (usage_domain == 'car_audio' and enc_src == 'user_explicit') else "Belirtilmedi (Tahmini Portlu)" if usage_domain == 'car_audio' else None,
        "enclosure_preference_raw": enc_raw,
        "constraint_source": enc_src,
        "goal": goal,
        "goal_hint": goal_hint,                         # DD1 Dil Doktrini §9.3
        "goal_needs_clarification": goal_needs_clarification,
        "constraint_conflicts": []
    }

    if usage_domain == 'car_audio':
        fit_status, fit_comment = _calculate_fit(tw, th, td, size_mm, diameter_inch, trunk_notes)
        normalized_panel.update({
            "vehicle_type": vehicle_type,
            "vehicle_model": vehicle_model,
            "trunk_width_cm": tw, "trunk_height_cm": th, "trunk_depth_cm": td,
            "trunk_notes": trunk_notes,
            "fit_status": fit_status,
            "usta_fit_comment": fit_comment
        })
    elif usage_domain == 'home_audio':
        normalized_panel.update({
            "room_size_m2": room_size_m2,
            "placement_notes": placement_notes,
            "living_situation": living_situation
        })

    missing_fields = _get_missing_fields(usage_domain, normalized_panel)
    labels = _get_field_labels(usage_domain)
    missing_labels = [labels.get(f, f) for f in missing_fields]
    next_questions = _next_questions(missing_fields, usage_domain)

    normalized_panel.update({
        "missing_fields": missing_fields,
        "missing_labels": missing_labels,
        "next_questions": next_questions,
    })

    return {
        "intent": intent,
        "confidence": round(conf, 2),
        "route_to": agent,
        "usage_domain": usage_domain,
        "woofer_model": woofer_model or None,
        "diameter_inch": diameter_inch,
        "target_hz": target_hz,
        "bass_char": bass_char,
        "goal_hint": goal_hint,                         # DD1 Dil Doktrini §9.3
        "goal_needs_clarification": goal_needs_clarification,
        "extracted_entities": {
            "woofer_model": woofer_model,
            "size_raw": size_raw,
            "target_hz": target_hz,
            "rms_power": rms_power,
            "usage_domain": usage_domain,
            "bass_char": bass_char,
            "enclosure_preference_raw": enc_raw,
        },
        "normalized_entities": {
            "diameter_inch": diameter_inch,
            "normalized_size_value": size_val,
            "normalized_size_unit": size_unit,
            "inferred_diameter_inch": diameter_inch,
            "enclosure_preference_normalized": enc_norm,
            "constraint_source": enc_src,
        },
        "normalized_panel": normalized_panel,
    }



