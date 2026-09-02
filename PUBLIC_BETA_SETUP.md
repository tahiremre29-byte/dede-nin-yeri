# DD1 Halka Açık Beta Bağlantısı

Bu kurulumda web arayüzü ile hesap motoru ayrı proje değildir. FastAPI,
`public_beta/` arayüzünü ve `/api/public/*` hesap çağrılarını aynı adres ve
aynı 9000 portu üzerinden sunar.

## Yerel program konumu

`dd1_start.bat` içindeki mevcut konum:

```text
C:\Users\DDSOUND\Desktop\exemiz\dd1_sound
```

## Yapılandırma

`.env.example` dosyasını `.env` olarak kopyalayın ve en az şu alanları
doldurun:

```dotenv
DD1_PUBLIC_BETA_MODE=true
DD1_APPROVED_MODELS=ONAYLI TAM MODEL 1|ONAYLI TAM MODEL 2
DD1_ADMIN_KEY=uzun-rastgele-bir-anahtar
DD1_PREMIUM_KEY=farkli-uzun-rastgele-bir-anahtar
```

`DD1_APPROVED_MODELS` yalnızca anlaşması ve teknik verisi doğrulanmış tam
model adlarını içermelidir. Listedeki adlar woofer veritabanındaki `model`
alanıyla birebir eşleşir. Liste boş bırakılırsa sitede hiçbir ürün görünmez.

## Çalıştırma

`dd1_start.bat` çalıştırıldığında tarayıcıda aşağıdaki adres açılır:

```text
http://127.0.0.1:9000/
```

Halka açık modda yalnız şu işlevler dışarı açıktır:

- onaylı ürün listesini görüntüleme;
- seçilen ürün için DD1 akustik taslağı oluşturma;
- sonuç ve ürün talebi geri bildirimi bırakma.

Yönetim, genel katalog, arşiv, sohbet, DXF/STL üretim ve izleme uçları halka
açık modda yüklenmez.

## İnternete açma

Geçici beta bağlantısı için program çalışırken `ngrok http 9000` kullanılabilir.
Bu işlemden önce `DD1_PUBLIC_BETA_MODE=true` olduğundan emin olun.

Kalıcı alan adı için Python/FastAPI çalıştırabilen bir sunucu gerekir. Sunucuda
aynı ortam değişkenleri tanımlanır ve alan adı 9000 portundaki uygulamaya ters
proxy ile yönlendirilir. Yalnız statik site barındıran hizmetler DD1 hesap
motorunu çalıştırmaz.
