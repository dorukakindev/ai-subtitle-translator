# Gizlilik Bildirimi

Bu uygulama yerel çalışan bir masaüstü istemcisidir. Proje geliştiricisi
altyazıları merkezi bir sunucuda toplamaz; ancak seçtiğiniz model sağlayıcıları
ile yerel çalışma dosyaları veri işleyebilir.

## Uzak sağlayıcılara gönderilebilen veriler

Etkin ayarlara ve rol profillerine göre aşağıdakiler ana çeviri, analiz,
Critic, Polish, Native Reader veya QC sağlayıcısına gönderilebilir:

- çevrilecek altyazı metni ve cue kimlikleri;
- önceki/sonraki replikler ile sahne bağlamı;
- önceki çeviriler, sözlük ve onaylı terminoloji;
- karakter, hitap, ton, sahne ve tutarlılık analizleri;
- kalite denetimi için kaynak ve çeviri parçaları.

Toplu kipte istek dosyası resmi OpenAI Batch API'ye yüklenir. Her yardımcı rol
ayrı profil kullanabildiğinden yalnız ana modeli yerel seçmek bütün veri akışını
yerel yapmaz. Gizli içerikte bütün rollerin profil ve anahtarlarını kontrol edin.
Sağlayıcının saklama, eğitim ve gizlilik koşulları kendi politikasına tabidir.

## Yerelde saklanan veriler

Uygulama aşağıdaki türlerde dosya oluşturabilir:

- API anahtarı içermeyen arayüz ayarları;
- Windows Kimlik Bilgisi Yöneticisi kayıtları;
- keyring yoksa kullanıcıya özel izinlerle korunan karartılmış anahtar dosyası;
- kaynak/çeviri çiftleri içeren SQLite çeviri belleği;
- analiz önbellekleri, raporlar, loglar, yedekler ve kurtarma kayıtları;
- bölüm/dizi tercihleri ve onaylı terminoloji.

Karartılmış anahtar dosyası kriptografik şifreleme değildir. Paylaşılan bir
bilgisayarda güvenli kimlik deposu olmadan hassas anahtar saklamayın.

## Kullanıcının kontrolü

- Uzak aktarımı azaltmak için Ollama/LM Studio profilleri kullanın ve bütün
  yardımcı rolleri de yerel seçin veya kapatın.
- Çeviri belleği, rapor, log ve önbellekleri paylaşmadan önce inceleyin.
- Bir sağlayıcı anahtarının sızdığından şüpheleniyorsanız sağlayıcı panelinden
  hemen iptal edip yenileyin.
- Uygulamayı ve etkin yazma işlemlerini kapatmadan SQLite dosyalarını elle
  taşımayın veya silmeyin.

Bu belge hukuki gizlilik taahhüdü değil, uygulamanın veri akışını açıklayan
teknik bir özettir. Davranışla belge arasında fark bulursanız
[SECURITY.md](SECURITY.md) üzerinden bildirin.
