# Public Yayın Kontrol Listesi

Bu dosya, mevcut özel geliştirme deposunu doğrudan görünür yapmak yerine temiz
bir public yayın hazırlamak için kullanılır.

## Zorunlu kontroller

- [x] `README.md`, `README.en.md`, `PRIVACY.md`, `SECURITY.md`, `LICENSE` ve
      `CONTRIBUTING.md` güncel.
- [ ] Tam test paketi ve GitHub Actions yeşil.
- [x] Bütün Git geçmişi Gitleaks 8.30.1 ile tarandı (944 commit, 0 bulgu; 2026-09-15).
- [ ] Bulunan gerçek anahtarlar geçmiş temizlenmeden önce iptal edilip yenilendi.
- [ ] Kişisel altyazı, film envanteri, kullanıcı yolu, log, rapor, ayar,
      çeviri belleği, cache ve kurtarma dosyası yayın paketinde yok.
- [ ] GPLv3 ile tüm doğrudan/dağıtılan bağımlılıkların lisans uyumu incelendi.
- [ ] Windows'ta temiz bir klasörde sıfırdan kurulum ve GUI açılışı denendi.
- [x] Uzak sağlayıcı çağrısı olmadan 5.475 testin çalıştığı doğrulandı (6 atlama; 2026-09-15).
- [ ] Ekran görüntüleri sentetik veriyle üretildi ve kişisel içerik içermiyor.
- [ ] GitHub'da private vulnerability reporting, secret scanning ve push
      protection ayarları gözden geçirildi.

## Geçmiş kararı

Dosyayı son committe silmek onu Git geçmişinden çıkarmaz. Bu geliştirme deposu
kişisel çalışma belgeleri içerdiği için önerilen yayın yöntemi, doğrulanmış
kaynak ağacını **yeni ve temiz geçmişli bir public repoya** aktarmaktır. Mevcut
depoyu doğrudan public yapmak ancak bütün geçmiş taranıp kullanıcı açıkça bunu
seçerse düşünülmelidir. Force push veya geçmiş yeniden yazımı bu kontrol
listesinin otomatik bir adımı değildir.
## Yerel çalışma ağacı notu

Git geçmişi taraması temizdir. Tüm klasörü Git dışı dosyalarla birlikte taramak,
`.gitignore` kapsamındaki yerel kimlik bilgisi ve ajan çalışma klasörlerini de
bulabilir; bunlar public yayına eklenmemelidir. Yayın adayı ayrıca yalnız Git'te
izlenen dosyalardan oluşturulup tekrar taranmalıdır.
