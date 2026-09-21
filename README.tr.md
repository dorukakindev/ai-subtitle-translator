# Altyazı Çevirisi

[![Testler](https://github.com/dorukakindev/ai-subtitle-translator/actions/workflows/tests.yml/badge.svg)](https://github.com/dorukakindev/ai-subtitle-translator/actions/workflows/tests.yml) [![Lisans: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE) [![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)

[English](README.md) · [Kullanım kılavuzu](KILAVUZ.md) · [Gizlilik](PRIVACY.md) · [Güvenlik](SECURITY.md)

OpenAI ve OpenAI uyumlu sağlayıcılarla `.srt`, `.vtt`, `.ass` ve `.ssa`
altyazılarını bağlamı koruyarak çeviren bir Windows masaüstü uygulamasıdır.
Arayüz İngilizce açılır; üst bölümdeki dil seçicisinden Türkçeye çevrilebilir.

Program replikleri birbirinden kopuk çevirmek yerine yakın diyalogları, sahne
geçişlerini, daha önce verilmiş çeviri kararlarını, karakter ilişkilerini ve
proje sözlüğünü birlikte değerlendirir. Çıktı yine de insan denetimi isteyen
bir taslaktır; uygulama profesyonel çevirmenin yerine geçmez.

## İçindekiler

- [Öne çıkanlar](#öne-çıkanlar)
- [Gereksinimler](#gereksinimler)
- [Kurulum](#kurulum)
- [İlk kullanım](#i̇lk-kullanım)
- [Sağlayıcılar ve çalışma kipleri](#sağlayıcılar-ve-çalışma-kipleri)
- [Ortam değişkenleri](#ortam-değişkenleri)
- [Gizlilik ve API anahtarları](#gizlilik-ve-api-anahtarları)
- [Yerel veriler](#yerel-veriler)
- [Ayarlar, geliştirme ve test](#ayarlar-geliştirme-ve-test)
- [Sınırlamalar](#sınırlamalar)
- [Lisans](#lisans)

## Öne çıkanlar

- 60 dil seçeneği ve 74 içerik türü şeması
- Kodlama ve biçim etiketlerini koruyan SRT, WebVTT ve ASS/SSA desteği
- Önceki çevirileri sonraki parçalara taşıyan zincirleme bağlam
- Karakter, hitap, ton, terim ve sahne analizi yapan yardımcı akış
- Bölüm/dizi kapsamında onaylı terim, ad ve `sen`/`siz` tercihleri
- Yerel çeviri belleği; Critic, Polish, Native Reader ve QC geçişleri
- Eksik diyalog ve yapısal bozulma dahil 39 adreslenebilir bulgu sınıfı
- Kaynağı değiştirmeyen yedekleme, kurtarma ve yalnız-raporla çalışma
- İsteğe bağlı OpenAI Batch API ve FFmpeg ile gömülü altyazı çıkarma
- Deneme çevirisi, geçiş geçmişi inceleme ve kontrollü geri alma

## Gereksinimler

- Windows 10 veya 11
- Tk destekli Python 3.11 veya daha yeni kararlı sürüm
- Kullanılacak uzak sağlayıcı için API hesabı/anahtarı veya çalışan bir yerel
  Ollama/LM Studio sunucusu
- Yalnız video içinden altyazı çıkarılacaksa FFmpeg ve ffprobe

CI, Python 3.11 ve 3.13 üzerinde çalışır. Yerel geliştirme ortamı Python 3.13
ile doğrulanmıştır. Tk destekli bir Python (`python3-tk`) ile Linux/X'te de
açılır, ancak desteklenen hedef Windows'tur — sürükle-bırak ve kimlik
deposu davranışı farklılık gösterebilir.

## Kurulum

PowerShell'de:

```powershell
git clone https://github.com/dorukakindev/ai-subtitle-translator.git
cd ai-subtitle-translator
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe subtitle_translator_gui.py
```

Sonraki açılışlarda `Başlat.bat` kullanılabilir. Başlatıcı çalışma anında paket
indirmez; bağımlılık eksikse kurulum komutunu gösterip durur.

Video altyazısı çıkarmak için `ffmpeg.exe` ve `ffprobe.exe` PATH üzerinde veya
proje kökündeki `tools/ffmpeg/` klasöründe bulunmalıdır. Normal altyazı çevirisi
için FFmpeg gerekmez.

## İlk kullanım

1. **API Anahtarları → Yeni Profil** ile sağlayıcı profilini oluşturun.
2. Ana çeviri ve isteğe bağlı yardımcı roller için profil/model seçin.
3. Dosya veya klasör ekleyip kaynak ve hedef dili belirleyin.
4. İçerik türünü seçin veya **Otomatik** bırakın.
5. Maliyet tahminini inceleyip çeviriyi başlatın.
6. Çıktıyla oluşan kalite raporunu kontrol edin.

Kuyruktan bir öğeyi kaldırmak kaynak dosyayı diskten silmez.

## Sağlayıcılar ve çalışma kipleri

OpenAI dışında Google AI Studio, OpenRouter, Groq, DeepSeek, Mistral, xAI,
Together, Cerebras, Fireworks, Nebius, Anthropic ve OpenAI uyumlu özel uç
noktalar kullanılabilir. Ollama ve LM Studio için yerel profiller de vardır.
Model listesi sağlayıcıdan dinamik alınır.

| Kip | Kullanım | Önemli not |
| --- | --- | --- |
| Eşzamanlı | Normal çeviri | Zincirleme bağlamın tamamını kullanır. |
| Toplu (Batch) | Büyük kuyruklar | Yalnız resmi OpenAI Batch API ile çalışır. |
| Yardımcı Analiz | Kalite öncelikli | Etkin analiz ve kalite geçişlerini çalıştırır. |

Her yardımcı rol farklı bir sağlayıcı profiline bağlanabilir. Ana çeviri yerel
modelde olsa bile Critic veya QC uzak profildeyse ilgili metin o sağlayıcıya
gönderilir.

## Ortam değişkenleri

API anahtarları ortam yerine sağlayıcı profillerinde (kimlik deposunda)
saklanır. Uygulama yalnızca birkaç isteğe bağlı değişken okur:

| Ad | Gerekli | Varsayılan | Açıklama |
| --- | --- | --- | --- |
| `SUBTITLE_TRANSLATOR_STATE_DIR` | hayır | depo dizini | Ayarların, önbelleklerin ve bellek dosyalarının tutulduğu dizini değiştirir. Testler ve pilot koşular kullanır. |
| `AWS_DEFAULT_REGION` / `AWS_REGION` | hayır | `eu-north-1` | AWS Bedrock yardımcı profillerinin bölgesi. |

## Gizlilik ve API anahtarları

Altyazı metni, bağlam ve etkin analiz verileri seçtiğiniz uzak sağlayıcılara
gönderilebilir. Batch kipinde istek dosyası OpenAI'a yüklenir. Gizli içerik
işlemeden önce [PRIVACY.md](PRIVACY.md) dosyasını okuyun.

Anahtarlar normalde Windows Kimlik Bilgisi Yöneticisi'nde `keyring` ile
saklanır. Bu kullanılamazsa uygulama kullanıcıya özel dosya izinleriyle
korunan, fakat yalnızca **karartılmış (obfuscated)** bir yerel dosyaya düşer.
Bu yedek kriptografik şifreleme değildir. Paylaşılan bilgisayarda güvenli
kimlik deposu olmadan anahtar saklamayın.

Güvenlik açığını herkese açık issue yerine [SECURITY.md](SECURITY.md) içindeki
yolla bildirin.

## Yerel veriler

Uygulama aşağıdaki dosyalarda altyazı metni veya çalışma bilgisi tutabilir;
bunlar `.gitignore` ile kaynak deposundan ayrılır:

- `translation_memory.db`: kaynak/çeviri eşleşmeleri
- `.context_cache/` ve `.precontext.json`: analiz önbellekleri
- `Raporlar/` ve `logs/`: kalite bulguları ve çalışma kayıtları
- Batch ve eşzamanlı kurtarma kayıtları

Sorun raporuna ham dosya eklemeden önce kişisel içeriği temizleyin.

## Ayarlar, geliştirme ve test

Önemli ayarlar: **Yalnız Raporla**, **Zincirleme Bağlam** ve **Ham Çeviri
Yedeği**. Bütün ayarlar için [KILAVUZ.md](KILAVUZ.md) kullanılmalıdır.

```powershell
.\.venv\Scripts\python.exe belge_uret.py --kontrol
.\.venv\Scripts\python.exe -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Testler ücretli API çağrısı gerektirmez. Katkı yapmadan önce
[CONTRIBUTING.md](CONTRIBUTING.md) ve [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
dosyalarını okuyun.

## Sınırlamalar

Arayüz İngilizce açılır ve üst bölümden Türkçeye çevrilebilir; çeviri
raporları ve bazı tanı çıktıları Türkçe kalır. Kalite seçilen modellere
bağlıdır; otomatik kontroller her anlam hatasını yakalayamaz. Yayınlanacak
altyazılar insan tarafından gözden geçirilmelidir.

## Lisans

[GNU General Public License v3.0](LICENSE). Dağıtılan türev çalışmalar için
GPLv3 kaynak sağlama yükümlülükleri geçerlidir.
