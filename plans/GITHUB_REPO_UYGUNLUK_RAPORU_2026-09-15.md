# GitHub altyazı projeleri uygunluk değerlendirmesi — 2026-09-15

## Karar özeti

Gönderilen listedeki repoların tamamı yararlı değildir. Mevcut kodla karşılaştırınca en yüksek getirili üç yön şunlardır:

1. **Parametreli, GUI ile aynı motoru kullanan CLI ve kaydedilebilir proje profili** — ana referans: [rockbenben/subtitle-translator](https://github.com/rockbenben/subtitle-translator).
2. **Referans altyazı veya video sesiyle güvenli zaman senkronu** — listedeki ağır seçeneklerden önce [smacke/ffsubsync](https://github.com/smacke/ffsubsync) denenmeli; gerekirse [baxtree/subaligner](https://github.com/baxtree/subaligner) ikinci kademe olabilir.
3. **Dış araçla isteğe bağlı format lint/dönüşüm ve ileride görsel QC** — davranış referansı: [SubtitleEdit/subtitleedit](https://github.com/SubtitleEdit/subtitleedit). Subtitle Edit'in tamamını yeniden yapmak önerilmez.

Kısa hüküm: doğrudan kod taşınacak bir “ana repo” yok. Bizim bağlam, güvenlik, tekrar deneme, kaynak sahipliği ve kalite geçişi altyapımız çoğu adaydan ileride. Dış projelerden dar ve sınanabilir yetenekler alınmalı.

## Mevcut durumla karşılaştırma

Yerel kaynak denetiminde şu yeteneklerin zaten bulunduğu doğrulandı:

- SRT/VTT/ASS okuma ve korumalı yazma, çoklu encoding, ASS/VTT özel yapıları.
- Kaynak hash'i, cue sayısı ve zaman damgası değişimini yakalayan yapısal korumalar.
- CPS/okuma hızı, iki satır dengeleme, cue-fill taşıma ve AI akıllı segmentasyon.
- Sync/Batch kurtarma, ara checkpoint, rota/anahtar yedekleme ve ücret kaydı.
- Ollama ve LM Studio dahil yerel OpenAI uyumlu sağlayıcı profilleri.
- Critic, Polish, Native Reader, semantik uzlaştırma, QC ve aday doğrulama.
- Dosya kuyruğu, deneme çevirisi, geçiş inceleme/geri alma ve onaylı tercihler.

Gerçek boşluklar:

- `subtitle_batch_translate.py` çalıştırılabilir bir dosya olsa da kaynak/hedef dil, klasör ve model değerleri dosya başındaki sabitlerden geliyor; genel amaçlı `argparse` tabanlı, GUI ayarlarıyla pariteli bir CLI değil.
- Aynı kaynaktan bir koşuda birden fazla hedef dil üretme yok.
- Video veya doğru referans altyazıya göre otomatik zaman senkronu yok.
- Waveform/video önizlemeli manuel zaman düzenleme yok.
- Klasör izleme, yerel HTTP API ve medya sunucusu otomasyonu yok.
- Mevcut kalite geçişleri karar ve değişiklik kaydı tutuyor; ayrıca her cue'yu genel bir LLM-as-judge puanından geçirip eşik altını yeniden çevirme yok. Bu son eksiklik otomatik olarak ihtiyaç anlamına gelmiyor.

## Repo bazında değerlendirme

| Repo | Uygunluk | Alınabilecek dar fikir | Neden / sınır |
| --- | --- | --- | --- |
| [rockbenben/subtitle-translator](https://github.com/rockbenben/subtitle-translator) | **Yüksek** | GUI ile aynı motoru kullanan CLI, tekrarlanabilir proje profili, çoklu hedef kuyruğu, yapılandırma dışa/içe aktarma | Bizde toplu iş ve kurtarma var; asıl eksik parametreli ürün yüzeyi. Anahtarlar ayar JSON'una konmamalı, Credential Store kimliğiyle çözülmeli. |
| [smacke/ffsubsync](https://github.com/smacke/ffsubsync) | **Yüksek** | Doğru referans SRT veya video sesiyle global/framerate ve kontrollü parçalı senkron | Önceki gerçek kullanımımızdaki kaymış Türkçe altyazı sorununa doğrudan karşılık gelir. Çıktı ayrı dosyaya yazılmalı, kaynak korunmalı, kalite düşükse fail-closed davranılmalı. |
| [SubtitleEdit/subtitleedit](https://github.com/SubtitleEdit/subtitleedit) | **Orta-yüksek, yalnız dar kapsam** | `seconv lint` benzeri dış doğrulama, “başka dosyadan zaman kodu al”, ileride browser'da görsel CPS/zaman QC | 380+ format, OCR, waveform ve tam editör kapsamını kopyalamak proje odağını bozar. C# kodunu taşımak yerine davranış veya opsiyonel CLI adaptörü kullanılmalı. |
| [baxtree/subaligner](https://github.com/baxtree/subaligner) | **Orta** | ffsubsync'in çözemediği yerel kaymalarda ikinci kademe hizalama; script/ses hizalama | FFmpeg, bazı modlarda eSpeak/aeneas ve Windows'ta WSL/Docker yükü var. Ana bağımlılık yapılmamalı. |
| [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) | **Orta-düşük** | Terim adaylarını çeviri öncesi kullanıcıya onaylatma; segmentasyon benchmark vakaları | Akıllı segmentasyon, CPS, reflection benzeri kalite geçişleri ve checkpoint bizde zaten var. WhisperX/TTS/video üretim yığını gereksiz ağırlık getirir. |
| [tkarabela/pysubs2](https://github.com/tkarabela/pysubs2) | **Düşük-orta** | Format dönüşümünde differential test oracle; ileride TTML/SAMI gibi yeni formatlar için opsiyonel adaptör | Mevcut parser özel encoding, VTT ve ASS korumaları taşıyor. Toptan değiştirmek regresyon riski yaratır. |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | **Düşük-orta, ayrı opsiyon** | Altyazı hiç yoksa kelime zamanlı transkripsiyon veya konuşmacı adayları | Büyük model/GPU ve dil hizalama modeli ister; çakışan konuşma ve diarization sınırlı. Var olan altyazı çevirisinin çekirdeğine bağlanmamalı. |
| [Jkaotlic/ollama-subtitle-translator](https://github.com/Jkaotlic/ollama-subtitle-translator) | **Düşük** | Sadece değerlendirme vakaları ve judge ölçüm fikri | Ollama, TM, tür prompt'u, ön analiz ve yeniden deneme bizde var. Repo küçük; cue başına judge yeni maliyet/latans ve mevcut doğrulayıcılarla görev tekrarı getirir. |
| [lingarr-translate/lingarr](https://github.com/lingarr-translate/lingarr) | **Düşük, ürün yönü değişirse** | İzlenen klasör ve kalıcı görev kuyruğu davranışı | Masaüstü kişisel kullanım için medya sunucusu/Docker/HTTP servis kapsamı gereksiz. AGPL kodu doğrudan alınmamalı. |
| [kaegi/alass](https://github.com/kaegi/alass) | **Teknik olarak yararlı, lisans nedeniyle referans** | Kesinti/reklam farklarında parçalı zaman hizalama davranışı | GPL-3.0; doğrudan kod alma yerine algoritma/ürün davranışı referansı. ffsubsync zaten alass tarzı parçalı kip sunuyor. |
| [Jim-Elijah/sub-align](https://github.com/Jim-Elijah/sub-align) | **Deneysel/ikinci kademe** | Aynı dildeki metni cue bazında WhisperX ile ince hizalama | Çeviri metni sesle aynı dilde değilse doğrudan forced alignment güvenilir değildir; ağır bağımlılık ve model indirmesi gerekir. |

## Önerilen uygulama sırası

### P1 — Gerçek CLI ve proje profili

En güvenli ve günlük değeri en yüksek ürün geliştirmesidir.

- Yeni bir CLI giriş noktası GUI'nin mevcut istek kurucularını ve dört akıştaki ortak yardımcıları kullanmalı; ayrı ve zamanla çürüyen ikinci çeviri motoru oluşturmamalı.
- Kaynaklar, çıktı klasörü, hedef dil, model, sağlayıcı profil kimliği, kalite profili, sync/Batch seçimi ve dry-run/maliyet tahmini argüman olmalı.
- Proje profili API anahtarı içermemeli; yalnız Credential Store'daki profil kimliğine başvurmalı.
- Önce tek hedef dilde GUI/CLI paritesi kanıtlanmalı. Çoklu hedef dil daha sonra her hedef için ayrı hafıza, cache, çıktı ve maliyet defteriyle eklenmeli.
- Başarı ölçütü: aynı sentetik dosya ve aynı snapshot ile GUI ile CLI aynı request sözleşmesini, aynı cue/timestamp yapısını ve aynı rapor alanlarını üretmeli.

### P2 — Güvenli senkron yardımcısı

Önerilen ilk motor ffsubsync'tir.

- Girdi: video veya doğru referans altyazı + kaymış altyazı.
- İlk sürüm yalnız önizleme üretmeli: tahmini offset/framerate/parçalı değişimler, değişen cue sayısı ve güven skoru.
- Kaynağın üzerine yazmamalı; `*.synced.srt` ve işlem manifesti üretmeli.
- Cue metni, kimliği ve sırası değişirse reddetmeli; yalnız zamanlar değişebilir.
- Büyük veya şüpheli değişimde kullanıcı onayı istemeli; düşük güven durumunda hiçbir çıktı terfi ettirilmemeli.
- Referans ve hedef farklı dillerdeyse etkinlik tabanlı hizalamanın sınırı açıkça gösterilmeli.
- Subaligner ancak ffsubsync benchmark'ta yetersiz kalırsa opsiyonel subprocess olarak denenmeli.

### P3 — Dar kapsamlı format/QC adaptörü

- Subtitle Edit'i yeniden yapmak yerine `seconv lint --json` benzeri opsiyonel dış kontrol değerlendirilebilir.
- Browser tarafında kaynak/ham/final görünümüne CPS, CPL, overlap, gap ve zaman farkı rozetleri eklemek daha değerlidir.
- Waveform ve OCR ancak kullanıcı iş akışında sık ihtiyaç kanıtlanırsa ayrı özellik olmalı.
- `pysubs2`, mevcut parser'ı değiştirmek için değil, sentetik format corpusunda ikinci yorumlayıcıyla differential test için kullanılabilir.

## Şimdilik yapılmaması gerekenler

1. **Yeni bir LLM kalite geçişi eklemek:** Critic/Polish/Native/QC/semantik uzlaştırma zaten var. Önce bunların gerçek katkısını benchmark ile ölçmek gerekir.
2. **VideoLingo'nun bütün akışını taşımak:** segmentasyon ve checkpoint kazanımları büyük ölçüde mevcut; TTS/Whisper yığını odağı dağıtır.
3. **WhisperX'i zorunlu bağımlılık yapmak:** kurulum, GPU, model ve diarization maliyeti ana çeviri kullanımını ağırlaştırır.
4. **Parser'ı pysubs2 ile topluca değiştirmek:** mevcut özel korumalar kaybedilebilir.
5. **Lingarr kodunu almak:** ürün yönü uyuşmuyor ve AGPL lisansı ek yük getiriyor.
6. **Her cue'yu LLM-as-judge'a göndermek:** maliyet, gecikme ve yanlış pozitif üretir; mevcut aday doğrulayıcılarla çakışır.
7. **Subtitle Edit benzeri tam editör yapmak:** kullanıcının ana amacı çeviri ve browser'da rahat incelemedir; OCR/waveform/380 format ayrı bir ürün kapsamıdır.

## Nihai öncelik

1. **rockbenben yaklaşımından CLI + güvenli proje profili**
2. **ffsubsync tabanlı, önizlemeli ve fail-closed zaman senkronu**
3. **browser görsel QC ve opsiyonel Subtitle Edit CLI lint**
4. İhtiyaç varsa çoklu hedef dil
5. Yalnız benchmark başarısızlığı kanıtlanırsa Subaligner/WhisperX ikinci kademe

Bu sıralama yıldız sayısına değil, mevcut kodda gerçekten eksik olmasına, kullanıcının günlük iş akışına etkisine, Windows kurulum yüküne ve mevcut güvenlik sözleşmelerini bozma riskine dayanır.
