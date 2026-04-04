"""
joint_generator.py — DD1 Lazer Agent
Bağımsız Geçme (Finger Joint) Algoritması
"""

def generate_finger_joint_edge(length, material_thickness, finger_width, kerf, is_male):
    """
    Belirtilen uzunlukta, kerf kompanzasyonu uygulanmış finger joint profilini üretir.
    Daima 2D (x, y) polyline listesi döndürür. Başlangıç (0,0) noktasıdır ve sadece X ekseninde ilerler.
    
    Argümanlar:
    - length: Kenar uzunluğu (mm)
    - material_thickness: Malzeme kalınlığı (mm). (Tab derinliği/Slot derinliği)
    - finger_width: Hedef parmak genişliği (mm)
    - kerf: Lazer yakma payı (mm). (0.15mm vb.)
    - is_male: True ise dışa taşan (Tab) yapı ile başlar, False ise içe giren (Slot) yapı ile başlar.
               None ise düz bir çizgi döndürür.
               
    Dönüş:
    - points: [(x0, y0), (x1, y1), ...]
    """
    
    if is_male is None:
        return [(0, 0), (length, 0)]
        
    if is_male == "PORT_EDGE_MALE":
        # TAMAMEN MALE (Hiçbir boşluk yok). 
        # Bu sayede port boşluğu tarafından kesilen kısımlar havada yüzen parçalar (floating islands) oluşturmaz.
        # Boydan boya 10mm (material_thickness) kalınlığında sapağlam, zayıf noktası olmayan bir sütun oluşturur.
        return [(0, material_thickness), (length, material_thickness)]
        
    if is_male == "PORT_EDGE_FEMALE":
        # TAMAMEN FEMALE (Düz kenar).
        # Ön paneldeki boydan boya erkek sütunu karşılayacak temiz, düm düz birleştirme yüzeyi.
        return [(0, 0), (length, 0)]
        
    if isinstance(is_male, tuple) and is_male[0] == "PORT_MOUTH":
        # Bu kenarda DEV BİR DELİK (Port Ağzı) açacağız!
        # Parametreler is_male = ("PORT_MOUTH", port_start_y, port_end_y, port_depth)
        _, start_y, end_y, depth = is_male
        
        # Kerf compensation (Deliği kerf kadar büyüt)
        k_half = kerf / 2.0
        s_y = start_y - k_half
        e_y = end_y + k_half
        
        points = []
        points.append((0, 0))
        points.append((s_y, 0))
        # İçeri doğru kes (Negative Y in local edge space, but edge space Y is outward. So negative depth)
        points.append((s_y, -depth))
        points.append((e_y, -depth))
        points.append((e_y, 0))
        points.append((length, 0))
        return points
        
    if isinstance(is_male, list) and len(is_male) > 0 and is_male[0] == "PORT_SLOTS":
        # Birden fazla slot (delik) varsa, bunları sırayla kenar üzerinde negatif olarak açarız.
        # Parametreler: is_male = ["PORT_SLOTS", (start, end, depth), (start, end, depth), ...]
        points = [(0,0)]
        slots = sorted(is_male[1:], key=lambda x: x[0])
        
        last_x = 0
        k_half = kerf / 2.0
        
        for s_start, s_end, s_depth in slots:
            # Kerf compensation
            sx = s_start - k_half
            ex = s_end + k_half
            
            if sx > last_x:
                points.append((sx, 0))
            
            # İçeri doğru Slot (Negatif Y)
            points.append((sx, -s_depth))
            points.append((ex, -s_depth))
            points.append((ex, 0))
            
            last_x = ex
            
        points.append((length, 0))
        return points
    
    if isinstance(is_male, tuple) and is_male[0] == "ARMOR":
        # ARMOR Pattern: 3 adet sabit erkek/dişi kilit (Üst, Orta, Alt).
        # is_male = ("ARMOR", j_sex)
        _, j_sex = is_male
        H = length
        tab_size = 25.0
        margin = 15.0
        
        tab_y = material_thickness if j_sex else 0
        
        # Sabit 3 nokta (Armor Tab mantığı)
        pos = [
            (margin, margin + tab_size),
            (H/2.0 - tab_size/2.0, H/2.0 + tab_size/2.0),
            (H - margin - tab_size, H - margin)
        ]
        
        # Polarity check: Eğer j_sex=False (Female) ise bu noktalar yuva (slot) olur, 
        # ama bu fonksiyon KENAR çizgisini (edge) döner.
        # Kenar çizgisinde Female demek y=0 demektir.
        
        pts = [(0, 0)]
        for s, e in pos:
            pts.append((s, 0))
            pts.append((s, tab_y))
            pts.append((e, tab_y))
            pts.append((e, 0))
        pts.append((H, 0))
        return pts

    if isinstance(is_male, tuple) and is_male[0] == "GAPPED":
        # GAPPED Joint logic: Kenarın belli bir bölümünü acoustic koruma için DÜZ bırakır.
        # is_male = ("GAPPED", gap_start, gap_end, joint_sex, gap_sex)
        _, gs, ge, j_sex, g_sex = is_male
        
        # V17 GÜNCELLEMESİ: Slivers (ince kıymıklar) oluşmaması için gap sınırlarını rhythm'e daya.
        # Bu 'çakışma' sorununu kökten çözer.
        gs = round(gs / finger_width) * finger_width
        ge = round(ge / finger_width) * finger_width
        
        # Gap yüksekliği g_sex tipine göre sabitlenir (True=t, False=0)
        gap_y = material_thickness if g_sex else 0
        
        # 1. Parça (0'dan gs'ye)
        pts1 = generate_finger_joint_edge(gs, material_thickness, finger_width, kerf, j_sex)
        
        # 2. Parça (DÜZ ARA: gs'den ge'ye)
        pts_gap = [(gs, gap_y), (ge, gap_y)]
        
        # 3. Parça (ge'den length'e)
        pts2_raw = generate_finger_joint_edge(length - ge, material_thickness, finger_width, kerf, j_sex)
        pts2 = [(px + ge, py) for px, py in pts2_raw]
        
        return pts1 + pts_gap + pts2

    # Normal Array Logic
    min_width = material_thickness * 1.5
    f_width = max(finger_width, min_width)
    n_fingers = int(length / f_width)
    if n_fingers % 2 == 0: n_fingers -= 1
    if n_fingers < 1: n_fingers = 1
    actual_f_width = length / n_fingers
    k_half = kerf / 2.0
    
    boundaries = [0]
    for i in range(1, n_fingers):
        x_nom = i * actual_f_width
        is_prev_tab = (i - 1) % 2 == 0 if is_male else (i - 1) % 2 != 0
        if is_prev_tab:
            boundaries.append(x_nom + k_half) # Expand right
        else:
            boundaries.append(x_nom - k_half) # Expand left
    boundaries.append(length)
    
    points = []
    for i in range(n_fingers):
        is_tab = (i % 2 == 0) if is_male else (i % 2 != 0)
        offset_y = material_thickness if is_tab else 0
        
        x_start = boundaries[i]
        x_end = boundaries[i+1]
        
        points.append((x_start, offset_y))
        points.append((x_end, offset_y))
        
    return points
