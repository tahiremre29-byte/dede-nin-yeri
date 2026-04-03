# Aşama 7: Haftalık Supervisor Raporu
Tarih: 2026-04-02 00:28

## En Çok Karşılaşılan Sorunlar
- **tone_problem**: 1 uyarı
- **technical_error**: 1 uyarı
- **product_hallucination**: 1 uyarı
- **intent_miss**: 1 uyarı
- **field_knowledge_gap**: 1 uyarı

## Uygulama Kuyruğu (Son Düzeltme Önerileri)
### [intent_miss]
> **Kullanıcı:** Hocam clio 4 araca jbl 1000 koycam bagaj az yer kaplasın ama en arkadan çok fena vursun.
> 
> **Asistan:** Clio 4 için JBL 1000 subwoofer kapalı kutu ile tasarlanabilir. 45 Litre uygun ol...

**Önerilen Sistem/Prompt Kuralı:** `En arkadan fena vursun isteği 'açık alan/pancadao' dur. Kapalı kutu önerilemez!`

### [tone_problem]
> **Kullanıcı:** kabin ölçüsü 300x400 olursa tuning ne çıkar?
> 
> **Asistan:** Lütfen tam bagaj ölçülerini verin, aksi halde yardımcı olamam....

**Önerilen Sistem/Prompt Kuralı:** `Kullanıcıya 'aksi halde olamam' denmez, yönlendirici 'Şu 3 bilgiyi verirsek hemen hesaplanır' denmeli.`

### [technical_error]
> **Kullanıcı:** Pioneer Ts-w311d4 için 60 litre portlu kutu nasıl olur?
> 
> **Asistan:** Ts-w311d4 için 60L portlu kutu mükemmel bir seçimdir. Portu 50x50mm yaparsak 35H...

**Önerilen Sistem/Prompt Kuralı:** `50x50mm kare port chuffing (hava sesi) yapar. Kesit alanı 60L için çok yetersiz.`

### [field_knowledge_gap]
> **Kullanıcı:** Reis Tofaş Şahin bagajına 2 tane 30cm kicker l7 sığar mı?
> 
> **Asistan:** Tofaş Şahin bagaj ölçüleri genellikle W:900 H:450 D:600 şeklindedir. İki adet 30...

**Önerilen Sistem/Prompt Kuralı:** `Kicker L7 kare yapısı L-port veya özel köşe açıları ister, kuru sığar demek saha eksikliğidir.`

### [product_hallucination]
> **Kullanıcı:** Bana Kenwood XR-W12F sığacak en derin kutuyu çizer misin?
> 
> **Asistan:** Kenwood XR-W12F subwoofer modeli için derin seri bir kutu önerebilirim: 80 litre...

**Önerilen Sistem/Prompt Kuralı:** `Kenwood XR düz ince seridir, 80L tamamen uydurma.`

