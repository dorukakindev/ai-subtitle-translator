# Güvenlik Politikası

## Desteklenen sürüm

Proje henüz kararlı sürüm etiketleri yayımlamıyorsa yalnız varsayılan dalın en
son commit'i güvenlik düzeltmeleri alır. Eski commitler için destek garantisi
yoktur.

## Açık bildirme

API anahtarı sızıntısı, keyfi dosya yazma/okuma, kişisel altyazı veya log
ifşası, komut çalıştırma ya da sağlayıcı yönlendirme açığını herkese açık issue
olarak yayımlamayın.

GitHub deposundaki **Security → Report a vulnerability** düğmesiyle özel bir
güvenlik bildirimi gönderin. Özel bildirim seçeneği kullanılamıyorsa ayrıntıyı
ve gerçek kimlik bilgisini issue'ya koymayın; yalnız depo sahibinin GitHub
profili üzerinden özel iletişim kanalı isteyin.

Raporda şunlar yeterlidir:

- etkilenen commit/sürüm ve işletim sistemi;
- güvenli, mümkünse sentetik yeniden üretim adımları;
- beklenen ve gerçekleşen davranış;
- olası etki;
- önerilen düzeltme varsa kısa açıklama.

Gerçek API anahtarı, özel altyazı, ham kullanıcı yolu veya kişisel log
göndermeyin. Kanıtı sentetik değerlerle küçültün.

## Kimlik bilgisi olayı

Gerçek bir anahtar repoya, issue'ya veya loga girdiyse geçmişten silinmesini
beklemeden önce sağlayıcı panelinden iptal edin/yenileyin. Ardından GitHub
secret-scanning uyarılarını ve ilgili geçmişi ayrıca inceleyin.

## Güvenlik sınırları

- Windows Credential Manager/keyring tercih edilen anahtar deposudur.
- Yerel fallback yalnız karartmadır; kriptografik şifreleme değildir.
- OpenAI uyumlu özel base URL, altyazı ve anahtarın gideceği sunucuyu belirler;
  güvenmediğiniz bir adresi kullanmayın.
- Uygulama çıktılarının doğruluğunu veya üçüncü taraf sağlayıcıların kesintisiz
  çalışmasını güvenlik garantisi olarak sunmaz.
