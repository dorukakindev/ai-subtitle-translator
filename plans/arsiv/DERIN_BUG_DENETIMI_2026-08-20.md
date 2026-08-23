# Derin Bug Denetimi — 20 Ağustos 2026

## Kapsam ve yöntem

Bu denetim **salt okunur** yapıldı. Üretim kodu, testler, ayarlar, altyazılar ve çalışan süreç değiştirilmedi.

- İncelenen güncel sürüm: `b9be6fc`
- Karşılaştırma tabanı: son doğrulanmış El Pico teslim düzeltmesi `125317a`
- Bu aralıkta değişim: 81 dosya, yaklaşık 14.175 ekleme ve 1.070 silme
- Ana inceleme alanları:
  - çeviri/anlam ve post-pass güvenliği,
  - teslim temizliği, yapısal denetim ve recovery,
  - API sağlayıcıları, profil/ayar durumu ve kullanım muhasebesi,
  - yeni Cue-fill, rapor-only ve crash-resume davranışları.
- Denetim sırasında `20260820-072142-aee85794` kimlikli gerçek çeviri çalışıyordu. Bu nedenle GUI `App()` kurulmadı ve çalışma durumunu etkileyebilecek tam test paketi çalıştırılmadı. Bulgular; güncel kod akışı, saf/headless karşı örnekler, mevcut regresyon kapsamı ve gerçek çalışma logu ile doğrulandı.

## Yönetici özeti

Toplam **21 doğrulanmış hata** bulundu:

- **11 P1:** sessiz anlam kayması, gerçek cue silinmesi, yanlış final kabulü, eski API anahtarının kullanılmaya devam etmesi veya crash-resume sırasında kullanıcı ayarının tersine metin değiştirilmesi riski.
- **10 P2:** recovery döngüsü, gereksiz yeniden işlem/API maliyeti, yanlış sağlayıcı/rol kullanımı, eksik maliyet raporu veya Stop/durum makinesi tutarsızlığı.

En acil beş kök neden:

1. Yeni Cue-fill Taşıma bağımsız kaynak cümlelerini birbirine karıştırabiliyor.
2. Teslim temizliği gerçek ekran yazısı/diyaloğu SDH veya kredi sanıp silebiliyor.
3. Nihai Teslim Denetimi cue-sahipliği kaymasını bulduğu hâlde sert hata saymıyor.
4. Crash-resume kaydı `quality_report_only`, `term_normalize_apply` ve `cue_fill_move` ayarlarını kaybediyor.
5. Silinen API profilinin anahtarı widget/credential fallback yolunda yaşamaya devam edebiliyor.

---

## P1 — Sessiz anlam, içerik, kimlik veya teslim güvenliği hataları

### 1. Cue-fill bağımsız kaynak cümlesini önceki cue'ya taşıyabiliyor

**Kod:** `subtitle_translator_gui.py:4093-4149`

Planlayıcı yalnız hedef Türkçe metinde önceki cue'nun noktalama ile bitip bitmediğine ve CPS kazancına bakıyor. Kaynaktaki iki cue'nun aynı cümle/fragment grubuna ait olduğunu doğrulamıyor.

Saf karşı örnek:

```text
Kaynak #1: I left.
Kaynak #2: Fire!
Hedef #1: Eve gittim
Hedef #2: Yangın çıktı hemen kaçmalıyız
```

Mevcut plan şu sonucu üretebiliyor:

```text
#1 Eve gittim Yangın çıktı hemen
#2 kaçmalıyız
```

Bu yalnız biçim değişikliği değildir; ikinci cue'nun anlamı daha erken zaman damgasına taşınır. Önceki cue bir başlık/ekran yazısıysa, taşınan diyalog sonraki SDH temizliğinde tamamen de kaybolabilir.

**Düzeltme ölçütü:** Taşıma yalnız aynı doğrulanmış fragment/sentence grubundaki komşular arasında yapılmalı. Önceki kaynak cue tam cümle kapatıyorsa kesinlikle taşıma olmamalı.

### 2. Condense iki ayrı konuşmacıyı tek konuşmacı gibi birleştirebiliyor

**Kod:** `hybrid_translate.py:4748-4764`, `hybrid_translate.py:11979-12025`

Doğrulanmış karşı örnek:

```python
validate_condense_candidate(
    "- Merhaba\n- Nasılsın?",
    "- Merhaba, nasılsın?",
    "- Hello\n- How are you?",
    tgt_lang="Turkish",
)
# mevcut sonuç: (True, "")
```

Validator yalnız ilk başlangıç çizgisini ve genel biçimi kontrol ediyor; satır/konuşmacı sayısını korumuyor. Sonraki line-break veya SDH katmanı kaynakta iki konuşmacı bulunduğunu güvenle geri kuramaz.

**Düzeltme ölçütü:** Kaynak/hedef iki konuşmacılı cue'larda satır sayısı ve her satırın diyalog çizgisi korunmalı; tek satıra birleştirme reddedilmeli.

### 3. Türkçe dışındaki hedef diller Türkçe kurallar ve Türkçe sözlükle kirleniyor

**Kod:** `subtitle_translator_gui.py:5996-6124`, `subtitle_translator_gui.py:6586-6594`, `hybrid_translate.py:3757-3985`, `hybrid_translate.py:7245-7252`, `hybrid_translate.py:13664-13672`

Sync ve hybrid promptlarının önemli bölümü hedef dilden bağımsız biçimde Türkçe alfabe, Türkçe söz dizimi, Türkçe ek ve Türkçe özel ad kuralları içeriyor. Sabit kalite sözlüğü de her hedef dile koşulsuz ekleniyor.

Somut etkiler:

- Almanca hedefte `taxidermy → taksidermi` kilidi verilebiliyor.
- Rusça hedef promptuna Kiril kullanmama kuralı girebiliyor.
- `Sisyphus → Sisifos` gibi Türkçe kanonlar Almanca/Rusça hedefe taşınabiliyor.

**Düzeltme ölçütü:** Hedefe özel prompt/sözlük/alfabe katmanları açıkça hedef dil ile dallanmalı; Türkçe kalite sözlüğü ve Türkçe kanonlar yalnız Türkçe hedefte kullanılmalı.

### 4. Latin dışı kaynaklarda otomatik özel-ad kilidi, çevrilmesi gereken sözcükleri kaynak yazısıyla kilitliyor

**Kod:** `subtitle_translator_gui.py:4600-4687`

`auto_locked_proper_nouns` hedef dili ve hedef yazı sistemini bilmiyor. İngilizce ağırlıklı stop/exonym listelerine takılmayan, tekrarlanan büyük harfli Unicode sözcükleri kimlik eşlemesiyle kilitliyor.

Gerçek çalışan logdaki örnekler:

```text
Ελλάδα → Ελλάδα
Έλληνες → Έλληνες
Γερμανία → Γερμανία
Πλάτωνα → Πλάτωνα
```

Aynı çalışmanın hedefi Türkçe; ana prompt bir yandan sözlüğü aynen uygulamayı, diğer yandan Yunanca yazı bırakmamayı istiyor. Bu kendi içinde çelişkili bir talimat üretir. Canlı koşuda kaynak dili ayrıca `English` seçili olduğundan risk görünür hâle gelmiş olsa da, kilit üreticisinin hedef-yazı sistemi kontrolü olmaması bağımsız bir kod açığıdır.

**Düzeltme ölçütü:** Kimlik kilidi yalnız hedef yazı sisteminde zaten geçerli olan gerçek özel adlara uygulanmalı; Latin dışı kaynakta güvenilir transliterasyon/kanon yoksa otomatik kimlik kilidi yapılmamalı.

### 5. Aynı timestamp'i paylaşan kredi ve gerçek diyalog birlikte silinebiliyor

**Kod:** `subtitle_translator_gui.py:4924-4938`, `subtitle_translator_gui.py:5290-5294`, `subtitle_translator_gui.py:5337`

Silinecek kaynak cue'lar yalnız ID ile değil timestamp kümesiyle de işaretleniyor. Aynı zaman aralığında bir kredi cue'su ve gerçek diyalog varsa gerçek diyalog da krediyle birlikte düşüyor.

Karşı örnek:

```text
00:00:01,000 --> 00:00:02,000  Subtitles by Example
00:00:01,000 --> 00:00:02,000  Hello.
```

İki hedef blok da boş sonuca düşebiliyor.

**Düzeltme ölçütü:** Kaynak kaynaklı silme ID/özdeş içerik rolüyle yapılmalı; timestamp çakışması tek başına başka cue'yu silmemeli.

### 6. Gerçek büyük harfli ekran kartları yapısal SDH sanılıp sessizce siliniyor

**Kod:** `sdh_cleaner.py:254`, `subtitle_translator_gui.py:3758-3765`, `subtitle_translator_gui.py:4867-4904`

`LONDON`, `THE END`, `BERLIN 1961`, `ACT I` gibi gerçek anlatısal ekran yazıları kısa/tümü-büyük-harfli oldukları için yapısal SDH kabul ediliyor. Teslim denetimi bunları `expected_removed` saydığı için sonuç `ok` kalabiliyor.

**Düzeltme ölçütü:** Büyük harf tek başına SDH kanıtı olmamalı. Mekân/tarih/bölüm kartları korunmalı; yalnız açık ses/konuşmacı/teknik etiketleri silinmeli.

### 7. Köşeli parantezli tarih ve oda adları konuşmacı etiketi sanılıp siliniyor

**Kod:** `sdh_cleaner.py:494-514`, `sdh_cleaner.py:929-970`, `sdh_cleaner.py:1239-1273`

`[May 1945]` ve `[Room 101]`, `numbered_speaker` dalına girerek konuşmacı/SDH etiketi gibi kaldırılabiliyor. Bunlar çoğu filmde anlatısal zaman/mekân bilgisidir.

**Düzeltme ölçütü:** Sayı içeren köşeli-parantez içeriği yalnız güçlü konuşmacı/ses sözlüğü ve kaynak bağlamı varsa silinmeli; tarih, yer ve oda kartları korunmalı.

### 8. Nihai Teslim Denetimi cue-sahipliği kaymasını buluyor fakat teslimi durdurmuyor

**Kod:** `subtitle_translator_gui.py:14208-14213`, `subtitle_translator_gui.py:14375-14408`

Denetim `delivery_owner_mismatch_ids` üretiyor; fakat `_delivery_audit_has_hard_error` bu alanı sert hata listesine katmıyor.

Karşı örnek:

```text
Kaynak #1: Alice has 17 apples.
Kaynak #2: Bob has 23 pears.
```

Türkçe çeviriler zaman damgaları arasında ters çevrildiğinde audit iki ID'yi de sahiplik kayması olarak buluyor; buna rağmen hard-error `False` dönebiliyor. Akış fingerprint ve `YÜKLEMEYE HAZIR` işareti yazabilir.

**Düzeltme ölçütü:** Doğrulanmış cue-owner mismatch finali karantinaya almalı; hazır işareti ve tamamlandı durumu üretmemeli.

### 9. Standalone batch kısmi yanıtı, çevrilmemiş kaynak metinle final `.srt` olarak yazabiliyor

**Kod:** `subtitle_batch_translate.py:442-466`, `subtitle_batch_translate.py:487-505`, `resume_batch.py:28-42`

Batch sonucu eksikse ve henüz final yoksa, eksik cue ham kaynak metniyle final `.srt` içine yazılabiliyor. Recovery kaydı kalsa bile `resume_batch.py` final dosyası var diye dosyayı atlayabiliyor. Sonuç, çevrilmemiş satırı içeren final ve bitmeyen recovery döngüsüdür.

**Düzeltme ölçütü:** Kısmi sonuç yalnız `.partial`/recovery artifact olmalı; final dosya yazılmamalı. Resume, yalnız finalin kaynak bağlı ve eksiksiz olduğu kanıtlanırsa atlamalı.

### 10. Silinen API profili eski anahtarla çalışmayı sürdürebiliyor

**Kod:** `subtitle_translator_gui.py:24239-24254`, `subtitle_translator_gui.py:24302-24310`, `subtitle_translator_gui.py:25022-25083`, `subtitle_translator_gui.py:25102-25123`

Profil bir role atanınca key/url/model ana ve helper widgetlarına kopyalanıyor. Profil silme yalnız profil/atama kaydını kaldırıyor; kopyalanmış custom değerleri temizlemiyor. Resolver profil bulunamayınca bu eski custom değere geri düşüyor ve kaydetme işlemi onu yeniden kalıcılaştırabiliyor.

**Düzeltme ölçütü:** `assign → delete → resolve` sonunda silinen profile ait hiçbir rol, widget veya credential değeri kullanılamamalı/persist edilmemeli.

### 11. Crash-resume üç kritik yazma politikasını kaybediyor

**Kod:** `subtitle_translator_gui.py:18841-18979`, `subtitle_translator_gui.py:19038-19060`, `subtitle_translator_gui.py:21837-21858`

Tam snapshot şu alanları alıyor:

```text
term_normalize_apply
cue_fill_move
quality_report_only
```

Ancak diagnostic/run record ve resume override `scalar_keys` listeleri bu üçünü içermiyor. Gerçek aktif `active_run.24928.json` dosyasında da bu alanlar yok; oysa `.gui_settings.json` değerleri sırasıyla `false`, `false`, `true`.

Çökmeden sonra ayar dosyası/profil/default değişirse resume, başlangıçtaki report-only güvenlik politikasını yeniden kuramaz ve daha önce kapalı olan metin-değiştirici katmanları açabilir.

**Düzeltme ölçütü:** Üç alan run record, fingerprint ve resume restore kapsamına alınmalı. Crash-resume başlangıçtaki değerleri byte-for-byte yeniden kurmalı.

---

## P2 — Recovery, maliyet, durum ve rapor doğruluğu hataları

### 12. Varsayılan Derin Teslim Denetimi deterministik şüpheli cue'ları önceliklendirmiyor

**Kod:** `subtitle_translator_gui.py:27152-27203`, `subtitle_translator_gui.py:27314-27330`

Default-on, örneklemeli Derin Teslim denetimi yalnız post-pass ve hizalama adaylarını alıyor. `_delivery_scan_suspect_ids` ise default-off standart Nihai Anlam akışına ekleniyor. Böylece cue-fill, yabancı kalıntı, hitap/register ve benzeri deterministik adaylar %35 örneklemin dışında kalabiliyor.

**Düzeltme ölçütü:** Her iki anlamsal denetim aynı deterministik suspect kümesini almalı; örnekleme yalnız kalan temiz cue'larda yapılmalı.

### 13. Normal batch ve batch-resume eksik cue sayısını final temizlikten önce ölçüyor

**Kod:** `subtitle_translator_gui.py:34937-34954`, `subtitle_translator_gui.py:37353-37380`

Sync/hybrid eksik sayısını `_prepare_upload_ready_blocks` sonrasında yaparken normal batch yolları önce yapıyor. Örneğin gerçek kaynak diyaloğuna karşı hedef yalnız `{\an8}` ise pre-count sıfırdır; teslim hazırlığı sonrasında cue eksik olur. Akış önce final yolunu seçer, sonra ancak teslim auditinde karantinaya düşer.

**Düzeltme ölçütü:** Bütün akışlarda eksik/hata sayımı teslim hazırlığından sonra yapılmalı; böyle dosya doğrudan partial/recovery yoluna gitmeli.

### 14. Gerçek kaynak diyaloğunun `[MUSIC]` gibi yanlış hedefi final katmanda siliniyor

**Kod:** `subtitle_translator_gui.py:5381-5383`

Kaynak `Hello.` iken çeviri `[MUSIC]` olmuşsa final SDH katmanı hedefi tamamen kaldırıyor. Nihai audit daha sonra eksik diyaloğu yakalayıp karantinaya aldığı için sessiz upload-ready bozulması değil; fakat hatanın kanıtını yok ediyor ve recovery'yi zorlaştırıyor.

**Düzeltme ölçütü:** Kaynak gerçek diyalogsa hedef SDH-benzeri metin silinmemeli; açık bozuk çeviri olarak işaretlenip rapor/recovery'ye bırakılmalı.

### 15. Tam `.partial` terfisi kaynak fingerprint'i ve Kaynak arşivi oluşturmuyor

**Kod:** `subtitle_translator_gui.py:13054-13122`, çağrılar `32175-32196`, `36396-36423`

Eksiksiz hâle gelen partial final `.srt`ye taşınabiliyor; fakat normal final yollarındaki source fingerprint ve `Raporlar/Kaynak` arşivi yazılmıyor. Sonraki çalıştırma kaynağı kanıtlayamaz ve aynı dosyayı yeniden çevirebilir.

**Düzeltme ölçütü:** Partial promotion normal final ile aynı fingerprint, kaynak arşivi, audit ve marker atomikliğine sahip olmalı.

### 16. Standalone kaynak taraması üretilmiş `.tr/.ham/.partial` dosyalarını yeniden kaynak sayıyor

**Kod:** `subtitle_batch_translate.py:272-297`

Yalnız output kökü dışlanıyor. Aynı kaynak ağacında kalan `source.tr.srt`, `source.ham.srt` ve `source.partial.srt` yeniden batch girdisi olabiliyor. GUI taraması bu artifact'ları dışlıyor; standalone yolunda parite yok.

**Düzeltme ölçütü:** GUI ile ortak generated-artifact filtresi kullanılmalı; temp karşı örnekte yalnız gerçek `source.srt` keşfedilmeli.

### 17. Kaynak/içerik ön analizinin API token ve maliyeti run raporundan düşüyor

**Kod:** `subtitle_translator_gui.py:22248-22260`, `subtitle_translator_gui.py:26019-26084`, `subtitle_translator_gui.py:30083-30089`, `subtitle_translator_gui.py:30430-30457`, `subtitle_translator_gui.py:30740-30747`

Sayaçlar sıfırlanıyor, API preflight çalışıyor, fakat run record daha sonra başlıyor. Onaydan sonra `_start()` tekrar sayaç sıfırlayabiliyor. Sağlayıcı ücret yazar; session/pass ledger ve `ceviri_raporu` bu harcamayı içermez.

**Düzeltme ölçütü:** Preflight kullanımı aynı run origin'ine devredilmeli veya bağlantılı ayrı bir kayıt olmalı; final token delta ve pass tablosu her iki ön analizi içermeli.

### 18. Kısaltma UI'da Polish, gerçek çağrıda Analysis profili kullanıyor

**Kod:** rol etiketi/preflight `subtitle_translator_gui.py:82-123`; gerçek çağrılar `32964-32972`, `34749-34757`, `35638-35646`, `37139-37148`

Kullanıcı Polish=B, Analysis=A seçerse ön kontrol B'yi doğrular; gerçek Kısaltma isteği A anahtar/model/url ile gider. Maliyet ve sağlayıcı beklentisi bozulur.

**Düzeltme ölçütü:** Kısaltmanın tek bir resmi rol sözleşmesi olmalı ve bütün dört akış ile preflight aynı rolü kullanmalı.

### 19. Shuai route/failover tercihi aktif run sırasında değiştirilebiliyor

**Kod:** `subtitle_translator_gui.py:18841-19015`, `subtitle_translator_gui.py:21775-21905`, `subtitle_translator_gui.py:23957-23985`, `provider_retry.py:93-120`, `provider_retry.py:151-170`, `provider_retry.py:1517-1558`

Route değerleri snapshotta kısmen görünse de frozen getter/aktif kontrol kilidi kapsamı tam değil; comboboxlar running durumda kapatılmıyor ve provider her istekte global route adaylarını okuyabiliyor. Uzun çok-chunk koşuda kullanıcı route'u değiştirirse sonraki istekler başlangıç raporundan farklı rotaya gidebilir.

**Düzeltme ölçütü:** Route/failover run başına immutable olmalı veya kontroller koşu boyunca kilitlenmeli; değişim yapılırsa açık bir run eventi olarak kaydedilmeli.

### 20. Başlangıç doğrulaması gerçek helper rol matrisini kapsamıyor

**Kod:** `subtitle_translator_gui.py:25765-25795` ve ilgili pass çağrıları

Eksik örnekler:

- sync+hybrid Analysis gerektiriyor fakat doğrulama bunu yanlışlıkla yalnız batch bağlamında ele alabiliyor,
- Condense gerçekte Analysis kullanıyor,
- Semantic/Review Critic kullanıyor,
- Backtranslation QC kullanıyor.

Bu rollerin anahtarı yokken ücretli ana çeviri başlayabilir; ilgili pass ancak saatler sonra failed/skipped olur.

**Düzeltme ölçütü:** `özellik → gerçek rol` matrisi tek kaynaktan türetilmeli; eksik key/model/url ana çeviri API çağrısından önce bloklanmalı.

### 21. Stop, API'li preflight sırasında terminal değil; onayla çeviri yeniden başlayabiliyor

**Kod:** `request_cancellation.py:6`, `subtitle_translator_gui.py:5721-5735`, `subtitle_translator_gui.py:30284-30457`, `subtitle_translator_gui.py:30628-30678`, `subtitle_translator_gui.py:30929-30987`

Kaynak/içerik preflight, `RequestCancelled` hatasını geniş `except` içinde fallback olarak yutuyor. Integrity taraması da cooperative cancel almıyor. Worker dönünce onay dialogu açılabiliyor; kullanıcı Continue derse yeni `_start()` stop flag'ini sıfırlayıp çeviriyi başlatabiliyor.

**Düzeltme ölçütü:** Stop tüm preflight işçilerinde terminal olmalı; sonrasında dialog, `after_idle(_start)` veya API çağrısı oluşmamalı.

---

## Yanlış alarm olarak elenenler / mevcut güvenli yollar

Aşağıdakiler bu rapora bug olarak alınmadı:

- Diagnostic sanitizer ham API anahtarını rapora sızdırmıyor.
- Run snapshot, retry başlamadan önce temizlenmiyor.
- Native Reader'ın Critic rolünü kullanması mevcut tasarımda bilinçli ve akışlar arası tutarlı.
- Reseller maliyeti resmi OpenAI fiyatıymış gibi kesin gösterilmiyor; bilinmeyen route maliyeti doğrulanmamış olarak ayrılıyor.
- Project/Series/Translation Memory namespace izolasyonunda bu turda yeni, bağımsız bir açık üretilemedi.
- `repair_batches` timestamp parser'ında yeni bir bozulma bulunmadı.
- GUI kaynak keşfi generated artifact'ları doğru dışlıyor; yeniden-yutma açığı standalone batch yoluna özgü.
- Normal final kaynak arşivi/fingerprint yazımı atomik ve hash bağlı; eksik olan yol yalnız partial promotion.
- Hedefe özgü homoglyph düzelticisi target-gated; genel Türkçe-dışı hedef sorunu prompt/sözlük katmanında.
- Canlı koşudaki `Nō` için `non_turkish_target` uyarısı doğrulayıcı gürültüsüdür; bu olay tek başına metni bozmadı. Ayrı bir çıktı-koruma bugı olarak sayılmadı.
- Canlı koşuda `.ell`/Yunanca metinler için kaynak dili `English` seçilmişti. Bu doğrudan kullanıcı/koşu ayarıdır; otomatik dil dedektörü bugı diye sınıflandırılmadı. Bununla birlikte bu durum 4 numaralı otomatik-kilit açığını gerçek logda görünür kıldı.

## Önerilen düzeltme sırası

1. **Teslimde veri kaybı:** 5, 6, 7, 8.
2. **Anlamı sessiz değiştiren passler:** 1, 2, 4.
3. **Crash/recovery final güvenliği:** 9, 11, 13, 14, 15, 16.
4. **Dil-genelleme:** 3.
5. **Credential/sağlayıcı doğruluğu:** 10, 18, 19, 20.
6. **Maliyet ve gözlemlenebilirlik:** 12, 17, 21.

Her düzeltme için aynı kabul standardı uygulanmalı:

- gerçek karşı örneği önce başarısız bir regresyon testine dönüştürmek,
- ilgili sync, batch, sync-hybrid, hybrid-batch ve resume yollarının tamamını kontrol etmek,
- yalnız ilgili dosyaları değiştirmek,
- focused test + `py_compile` + canlı çeviri yokken tam `unittest` çalıştırmak,
- gerçek final audit `status=ok` ve hard-error `False` olmadan hazır işareti üretmemek.

## Bu turda yapılan değişiklik

Yalnız bu rapor oluşturuldu. Üretim kodu, testler, ayarlar, çalışan çeviri ve kullanıcı altyazıları değiştirilmedi; commit atılmadı.

---

# İkinci Derin Tarama Turu

İkinci tur ilk 21 bulguyu tekrar saymadan parser/encoding, video cache, standalone batch, post-pass kabul zinciri ve GUI yaşam döngüsüne yoğunlaştı. **14 yeni hata** doğrulandı: **9 P1**, **5 P2**. Toplam doğrulanmış bulgu sayısı **35** oldu.

## İkinci tur P1 bulguları

### 22. Kısa BOM'suz Japonca/Çince SRT kaynakları yanlış kodlamayla açılıyor

**Kod:** `subtitle_formats.py:152-192`, `subtitle_formats.py:331-400`

80 bayttan kısa dosyalarda hızlı decoder yalnız tek baytlı Batı kodlamalarını deniyor; CP932/GBK gibi CJK adayları uzun-dosya yoluna ulaşamıyor. CP932 `はい` ve GBK `是` içeren geçerli 35–37 bayt SRT'ler CP1254 mojibake olarak parse edildi.

**Düzeltme ölçütü:** Kısa CP932, GBK ve CP1256 SRT fixture'ları kayıpsız okunmalı; kısa dosya optimizasyonu aday kodlama ailesini daraltmamalı.

### 23. ASS `Style=Note/Credit` gerçek konuşmayı içerikten bağımsız siliyor

**Kod:** `subtitle_formats.py:791-821`

ASS parser, `Dialogue` satırının stil adı `Note` veya `Credit` ise metni incelemeden cue'yu atlıyor.

Karşı örnek:

```text
Dialogue: ...,Note,...,This sentence is spoken aloud.
```

Mevcut `parse_ass()` sonucu boş liste.

**Düzeltme ölçütü:** Keyfi stil adı taşıyan anlamlı `Dialogue` metni korunmalı; yalnız içerikle doğrulanmış kredi/not satırları temizlenmeli.

### 24. Standalone batch `custom_id` çakışması sonucu başka kaynağa bağlayabiliyor

**Kod:** `subtitle_batch_translate.py:305-310`

Kimlik aynı dosya adı ve yalnız 24-bit MD5 yol önekinden üretiliyor. Üretilmiş iki farklı, binlerce dizin uzunluğundaki `Episode.srt` yolu aynı `custom_id` değerini verdi. İki istek oluşurken `file_map` yalnız ikinci sahibini tuttu.

**Etki:** Batch yinelenen kimlik yüzünden reddedilebilir veya gelen çeviri yanlış kaynak dosyaya yazılabilir.

**Düzeltme ölçütü:** Binlerce aynı adlı farklı tam yolda tüm kimlikler benzersiz olmalı; file-map duplicate ID'de fail-closed davranmalı.

### 25. Boş fakat HTTP-başarılı standalone cevabı kaynak dilini final çıktı yapıyor

**Kod:** `subtitle_batch_translate.py:418-465`, `subtitle_batch_translate.py:487-505`

API `content: ""` döndürürse non-SDH cue için ham kaynak metin final SRT'ye yazılıyor. `failed_ids` boş kalabildiği için recovery de temizleniyor.

Doğrulanmış sonuç:

```text
Kaynak: Hello there.
API content: ""
Final: Hello there.
Durum: başarılı
```

**Düzeltme ölçütü:** Boş non-SDH cevap failed/recovery olarak kalmalı; kaynak echo hiçbir zaman tamamlanmış final oluşturmamalı.

### 26. Video altyazı cache'i videonun orta bölümündeki değişimi görmüyor

**Kod:** `video_subtitles.py:137-151`, `video_subtitles.py:220-235`, `video_subtitles.py:269-272`

Fingerprint yalnız boyut, mtime, ilk ve son 64 KiB'i kapsıyor. 256 KiB videonun ortasındaki 64 bayt değiştirilip boyut ve mtime korunduğunda fingerprint aynı kaldı; eski gömülü altyazı cache'i döndü ve FFmpeg ikinci kez çalışmadı.

**Düzeltme ölçütü:** Aynı boyut/mtime ile orta bölümü değişmiş video cache'i geçersiz kılmalı; tam hash veya güvenli çoklu örnekleme kullanılmalı.

### 27. Eski otomatik-kapanış callback'i yeni çeviri çalışırken bilgisayarı kapatabiliyor

**Kod:** `subtitle_translator_gui.py:20661-20728`, `subtitle_translator_gui.py:20819-20852`

Başarılı A koşusu `after(2500, _export_log_and_shutdown)` planlıyor fakat callback kimliği/generation saklanmıyor. Kullanıcı bu 2,5 saniyede B koşusunu başlatırsa A'nın callback'i hâlâ `shutdown.exe /s /t 30` çağırıyor. Yeni run başlangıcı pending kapanışı geçersiz kılmıyor.

**Düzeltme ölçütü:** Yeni run pending callback'i iptal etmeli; callback çalışırken yakalanan run hâlâ güncel ve uygulama idle değilse no-op olmalı.

### 28. Son Batch terminal olur olmaz run, sonuç yazımı bitmeden finalize ediliyor

**Kod:** `subtitle_translator_gui.py:33761-33803`, resume `subtitle_translator_gui.py:34329-34365`, `_wait_batch` `subtitle_translator_gui.py:35143-35216`

Son poll `_wait_batch(..., is_last=True)` çağırıyor. `_wait_batch` terminalde `_set_running(False)` kuyruğa koyuyor; fakat aynı worker daha sonra `_retry_hata`, `_write_results`, kalite geçişleri ve raporlamayı sürdürüyor.

UI callback araya girerse:

- run record finalize edilir,
- owner serbest bırakılır,
- frozen snapshot ve cancellation context temizlenir,
- kullanıcı yeni run başlatabilir,
- eski worker hâlâ aynı output üzerinde yazmaya devam eder.

**Düzeltme ölçütü:** Poll katmanı run'ı finalize etmemeli. Tek `_set_running(False)` yalnız sonuç yazımı/post-processing tamamlandıktan sonra çalışmalı; run-id bariyeri olmadan yeni çalışma başlamamalı.

### 29. Türkçe-dışı hedeflerde post-pass kabul zinciri hedef dili kaybediyor

**Kod:** `hybrid_translate.py:6523-6534`, Polish validator `hybrid_translate.py:11600+`, semantic çağrılar `hybrid_translate.py:9328-9349`, consistency `hybrid_translate.py:12194-12265`; GUI çağrıları `subtitle_translator_gui.py:27844-27851`, `28173-28180`, `32766`, `32941`, `34605`, `34740`, `35433`, `35618`, `36967`, `37127`

Birçok kabul noktası `tgt_lang` taşımıyor; boş hedef varsayılan olarak Türkçe kabul ediliyor. QC promptu da `tgt_lang` alsa bile sabit “Turkish translation/reviewer”, `turkish_errors` ve “Turkish conventions” metni üretiyor.

Doğrulanmış örnekler:

```python
validate_polish_candidate(
    "Ich weiß nicht.", "Ich weiß es nicht.", "I do not know."
)
# (False, "source_negation")

validate_polish_candidate(
    "Ich weiß nicht.", "Ich weiß es nicht.", "I do not know.",
    tgt_lang="German"
)
# (True, "")
```

Ayrıca Almanca `Nein.` için düşük severity `Hayır.` önerisi otomatik gruba girebiliyor ve QC auto-fix ile uygulanabiliyor.

**Düzeltme ölçütü:** Validator, semantic, consistency, QC ve term-normalization zincirinin tamamı hedef dili taşımalı; Türkçe-özel kontroller yalnız Türkçe hedefte çalışmalı; hedef dil dışındaki öneri otomatik uygulanmamalı.

### 30. Condense kaynakta bulunan ana nesne/olgu bilgisini silerek başarılı sayılıyor

**Kod:** `hybrid_translate.py:4751-4765`, `hybrid_translate.py:11979-12025`

İlk turdaki iki-konuşmacı birleşmesinden bağımsız olarak, validator içerik sözcüğü kaybını bilinçli biçimde kontrol etmiyor.

Mocked uçtan uca karşı örnek:

```text
Kaynak: Maria missed the red train ticket.
Eski:   Maria kırmızı tren biletini kaçırdı.
Aday:   Maria kaçırdı.
```

`validate_condense_candidate` adayı kabul etti; `condense_fast_lines` çıktıyı gerçekten değiştirdi ve `changed=1, status=completed` döndürdü.

**Düzeltme ölçütü:** Kaynak temelli özne/nesne/ana isim grubu koruması eklenmeli; yalnız dolgu sözcüğü düşüren veya aynı olguyu daha kısa veren aday uygulanmalı.

## İkinci tur P2 bulguları

### 31. Bozulmuş video-cache altyazısı geçerli sayılıyor

**Kod:** `video_subtitles.py:220-235`

Cache yalnız dosyanın boş olmamasını ve origin sidecar'ını denetliyor. Cache payload'ı `broken-but-nonempty` yapıldığında yeniden extraction çalışmadı.

**Düzeltme ölçütü:** Cache payload checksum'u ve parse/format bütünlüğü doğrulanmalı; bozuk payload FFmpeg extraction'ını yeniden başlatmalı.

### 32. Otomatik dosya retry'sı eski run ayarlarını kullanıcının yeni işine taşıyabiliyor

**Kod:** `subtitle_translator_gui.py:20878-20951`, yeni-run snapshot/override `subtitle_translator_gui.py:21835-21872`

A koşusunun retry planı `_selected_files`, `_resume_snapshot_override` ve `after(1500, _start)` bırakıyor. UI yeniden aktifken kullanıcı B dosyalarını/ayarlarını seçip Start'a basarsa B'nin taze snapshot'ı A'nın model/pass/terim ayarlarıyla ezilebiliyor. Eski callback daha sonra running guard ile dönse bile override zaten kullanılmış oluyor.

**Düzeltme ölçütü:** Retry generation/token ile run'a bağlanmalı. Kullanıcının manuel Start'ı pending retry'yı ve override'ı iptal etmeli; B yalnız B ayarlarıyla başlamalı.

### 33. QC `issues:null` gibi şema-dışı cevabı başarılı denetim sayıyor

**Kod:** `hybrid_translate.py:5274-5280`

`{"issues": null}`, `{}` veya string türündeki `issues`, liste olmadığı hâlde `successful_chunks += 1` yoluna girebiliyor. Sonuç `status=completed`, `successful_chunks=1`, sıfır issue; gerçekte hiçbir denetim yapılmamış.

**Düzeltme ölçütü:** `issues` mutlaka liste olmalı; null/dict/string response partial/failed sayılmalı ve neden loglanmalı.

### 34. Nihai Anlam `[null]` cevabında incelenmeyen kümeyi incelenmiş sayıyor

**Kod:** `hybrid_translate.py:9007-9031`, `hybrid_translate.py:9121`, `hybrid_translate.py:9156-9163`, `hybrid_translate.py:9173-9219`

`[null]` geçerli JSON liste olduğu için batch başarılı sayılıyor. `reviewed_cluster_ids` baştan bütün batch kümesini içeriyor; dict olmayan satır atlanıyor. Tek şüpheli kümeli saf mock sonucunda:

```text
status=completed
processed_cues=1
details=[]
```

Yani kapsam sahte biçimde %100 görünüyor.

**Düzeltme ölçütü:** Her response satırı zorunlu cluster/fixes şemasına uymalı; şema-dışı satır batch'i partial/invalid yapmalı ve ilgili kümeler yeniden istenmeli.

### 35. `ÇEVRİLDİ` işareti final dosyanın son bütünlüğünü yeniden doğrulamıyor

**Kod:** `subtitle_translator_gui.py:12470-12508`, yazım `subtitle_translator_gui.py:19467-19479`

Marker grubu yalnız dosya durumunun `done` olmasına ve output path'in mevcut bir dosya olmasına bakıyor; kayıtlı output hash/fingerprint veya yeni teslim audit'i istemiyor.

Saf karşı örnek:

```text
1. Geçerli output ile _completion_marker_groups(record) → True
2. Aynı output içeriğini "broken" ile değiştir
3. _completion_marker_groups(record) → yine True
```

Uzun çok-dosyalı koşuda daha önce tamamlanan çıktı, run finalize edilmeden dışarıdan değiştirilirse klasör yine `ÇEVRİLDİ.txt` alabilir.

**Düzeltme ölçütü:** Marker yazımından hemen önce output state/hash ile run kaydı karşılaştırılmalı; en azından source fingerprint ve parse/delivery bütünlüğü yeniden doğrulanmalı.

## İkinci turda elenen yanlış alarmlar

- Aynı adlı seçili kök klasörlerin output çakışması preflight tarafından engelleniyor.
- Kaynak arşivindeki aynı isimli farklı dosyalar hash-sonekli varyantla korunuyor.
- `atomic_write_*` üst klasörü oluşturuyor ve atomik replace kullanıyor.
- Normal Stop sonrasında retryable dosyaların active state'te kalması bilinçli recovery davranışı; tek başına stale-state bugı değil.
- Checkpoint hit'lerinin sıfır yeni token göstermesi doğru; yeni API harcaması oluşmuyor.
- Normal batch intent reconcile, intent-level süreçler-arası lock ve manifest fingerprint ile çift uzak batch oluşmasını engelliyor.
- Credential fallback ve profile migration yazma sırası bu ikinci turda yeni veri-kaybı açığı üretmedi.

## İkinci tur değişiklik özeti

Yalnız bu Markdown raporu genişletildi. Üretim kodu, testler, kullanıcı ayarları, çalışan çeviri ve altyazı/video dosyaları değiştirilmedi; commit atılmadı.

---

# Üçüncü Derin Tarama Turu

Bu turda önceki 35 maddeden bağımsız **7 yeni doğrulanmış hata** bulundu:

- **4 P1:** final içeriğinin kaynak parmak izine bağlanmaması, Yalnız Raporla modunda metin mutasyonu, Auto-Glossary JSON eşzamanlı veri kaybı ve manuel post-işlem raporunun hedef dosyayı kaynak sanması.
- **3 P2:** taşınan teslim klasöründe provenance kaybı, arşivlenmiş kaynağın post-işlemde hiç kullanılmaması ve bozuk yeni raporun eski sağlam kaynak eşleşmesini engellemesi.

Böylece bu belge toplam **42 doğrulanmış bulguya** ulaştı. Bu turda da üretim kodu, testler, ayarlar ve çalışan çeviri değiştirilmedi.

## Üçüncü tur P1 bulguları

### 36. Kaynak parmak izi onaylanmış final içeriğini bağlamıyor

**Kod:** `subtitle_translator_gui.py:12971-13027`; mevcut-çıktı atlama kapıları `subtitle_translator_gui.py:32179-32196`, `subtitle_translator_gui.py:36400-36423`

Sidecar adı output'un mutlak yolundan türetiliyor fakat dosyanın içinde yalnız kaynak SHA-256 değeri tutuluyor. Daha önce denetlenmiş Türkçe finalin hash'i/state'i kaydedilmiyor. Sonraki çalıştırmada kaynak değişmemişse, final dışarıdan anlamı değiştirilecek biçimde düzenlense bile kaynak parmak izi eşleşmeye devam ediyor.

Saf geçici-dosya karşı örneği:

```text
Kaynak: I see the red door.
Onaylanan final: Kırmızı kapıyı görüyorum.
Final sonradan: Mavi kapıyı görüyorum.

fingerprint_matches_after_mutation = True
existing_output_complete          = True
delivery_audit.status             = ok
hard_error                        = False
```

Bu durumda sonraki run yanlış değiştirilmiş finali “tamamlanmış” diye atlayabilir.

**Düzeltme ölçütü:** Sidecar kaynak SHA yanında onaylanmış output SHA/state'i de taşımalı. Atlamada hem kaynak hem diskteki güncel final hash'i doğrulanmalı; finaldeki her sonradan değişiklik marker/skip kararını geçersiz kılmalı.

### 37. `Kalite + Teslim: Yalnız Raporla` bazı kalite pass'lerinin metni değiştirmesini durdurmuyor

**Kod:** UI sözleşmesi `subtitle_translator_gui.py:17211-17229`; yalnız karantina kapısı `subtitle_translator_gui.py:18826-18839`; Polish `subtitle_translator_gui.py:32848+`, Native `subtitle_translator_gui.py:32887+`, Condense `subtitle_translator_gui.py:22127-22169`, QC `subtitle_translator_gui.py:28832+`

“Yalnız Raporla” ayarı teslimde karantinayı ve bazı consistency/Critic uygulamalarını engelliyor; fakat Polish, Native, Condense ve QC'ye ortak bir `apply_changes=False` politikası taşımıyor.

Saf `App.__new__` karşı örneğinde aktif snapshot `quality_report_only=True` iken mocked Condense `Maria kırmızı tren biletini kaçırdı.` satırını `Maria kaçırdı.` olarak değiştirdi ve `_maybe_condense` değiştirilmiş blokları döndürdü:

```text
report_only=True
changed_despite_report_only=True
```

Bu, kullanıcının “kendisi düzeltmesin, rapora yazsın” çalışma biçimiyle doğrudan çelişiyor.

**Düzeltme ölçütü:** Tek bir immutable report-only politikası bütün mutasyon yapan pass'lere taşınmalı. Pass aday/ret raporu üretebilmeli fakat giriş bloklarını byte/anlam olarak korumalı. Alternatif olarak ayar adı ve açıklaması yalnız karantina davranışını anlattığını açıkça belirtmeli; mevcut “güvenli mod” sözleşmesi korunacaksa mutasyon olmamalı.

### 38. Auto-Glossary JSON yazımı API/dialog sırasında yapılan kullanıcı değişikliklerini siliyor

**Kod:** `subtitle_translator_gui.py:29563-29678`

JSON sözlük ilk başta `existing` olarak okunuyor. API çağrısı ve kullanıcı onay penceresi bittikten sonra dosyanın güncel hâli yeniden okunmadan `dict(existing) + approved` atomik olarak yazılıyor. Bu sırada başka bir çeviri, editör veya kullanıcı aynı JSON'a terim eklediyse son yazım bu yeni terimleri sessizce yok ediyor.

Saf geçici-dosya karşı örneği:

```json
İlk okuma:       {"old": "eski"}
Eşzamanlı düzen: {"old": "eski", "concurrent": "korunmalı"}
Auto-Glossary:   {"new": "yeni"}
Gerçek final:    {"old": "eski", "new": "yeni"}
```

`concurrent` anahtarı kayboldu. Metin-sözlük dalı yazmadan önce dosyayı yeniden okurken JSON dalı okumuyor.

**Düzeltme ölçütü:** API/dialog öncesi state hash'i alınmalı; yazmadan hemen önce geçerli JSON yeniden ve strict okunmalı; dosya değişmişse üç-yollu merge veya fail-closed uyarı uygulanmalı. Aynı anahtardaki çelişki kullanıcı onayı olmadan ezilmemeli.

### 39. Manuel post-işlem raporu sonraki çalışmada Türkçe finali kaynak altyazı sanıyor

**Kod:** kaynak resolver `subtitle_translator_gui.py:5529-5556`; manuel rapor satırı `subtitle_translator_gui.py:28420-28429`

Manuel post-işlem rapor satırı:

```text
source_path = seçilen Türkçe output dosyası
delivery_source_path = gerçek kaynak altyazı
output_path = seçilen Türkçe output dosyası
```

olarak yazılıyor. Buna karşılık `_resolve_postprocess_source` yalnız `source_path` alanını okuyor ve `delivery_source_path` alanını hiç kullanmıyor. En yeni manuel rapor, önceki doğru çeviri raporundan önce seçildiği için ikinci manuel post-işlemde Türkçe finali kaynak olarak döndürüyor.

Saf rapor sırası karşı örneği:

```text
Eski rapor : output=Movie.srt, source=Source.srt
Yeni rapor : output=Movie.srt, source=Movie.srt, delivery_source=Source.srt
Resolver   : Movie.srt
is_output  : True
```

Sidecar varsa kaynak-drift kontrolü işlemi gereksiz yere durdurabilir; sidecar yoksa Critic/Polish/Native/QC Türkçe hedefi kaynak sanarak yanlış değerlendirme yapabilir.

**Düzeltme ölçütü:** Resolver öncelikle doğrulanmış `delivery_source_path` kullanmalı; kaynak ve output aynı resolve path ise reddetmeli; rapor şeması manuel ve normal akışlarda aynı provenance sözleşmesini taşımalı.

## Üçüncü tur P2 bulguları

### 40. Tamamlanmış klasör taşınınca kaynak parmak izi ve post-işlem eşleşmesi kayboluyor

**Kod:** `_output_source_fingerprint_path` `subtitle_translator_gui.py:12971-12974`; `_resolve_postprocess_source` `subtitle_translator_gui.py:5529-5556`

Fingerprint sidecar adı output'un **mutlak eski yolundan** türetiliyor. Rapor eşleşmesi de rapordaki eski mutlak `output_path` ile güncel yolu birebir karşılaştırıyor.

Saf taşıma karşı örneği:

```text
OLD/Movie/ içindeki final + Raporlar + kaynak fingerprint'i geçerli
Klasör bütünü YUKLENECEK/Movie/ altına taşındı

fingerprint_after_move       = False
postprocess_source_after_move = None
```

Bu, tamamlanan klasörlerin `G:\HAZIR FİLMLER\YÜKLENECEK` veya `DONE` altına taşındığı gerçek teslim iş akışında provenance ve güvenli yeniden-denetim kabiliyetini kaybettiriyor.

**Düzeltme ölçütü:** Artifact kimliği mutlak konumdan bağımsız olmalı; yerel göreli output yolu veya output/source hash çifti kullanılmalı. Resolver taşınmış klasördeki yerel rapor ve Kaynak arşivinden güvenli fallback yapmalı.

### 41. Arşivlenen orijinal kaynak, asıl dosya silinince manuel post-işlemde kullanılmıyor

**Kod:** arşiv yazımı `subtitle_translator_gui.py:12986-13012`; kaynak resolver `subtitle_translator_gui.py:5529-5556`

Program kaynak altyazıyı finalin yanındaki `Raporlar/Kaynak` klasörüne başarıyla kopyalıyor. Ancak resolver yalnız rapordaki eski `source_path` hâlâ diskteyse onu kabul ediyor; `Raporlar/Kaynak` içindeki doğrulanmış kopyayı aramıyor ve raporda onun kesin yol/hash eşleşmesini kullanmıyor.

Saf karşı örnek:

```text
archive_exists = True   (Raporlar/Kaynak/source.srt)
orijinal giriş source.srt silindi
resolved_after_original_deleted = None
```

Sonuçta orijinal girdiyi çeviri bittikten sonra silme şeklindeki normal iş akışında daha sonraki Critic/Polish/Native/QC ve kaynak-temelli teslim denetimi kaynak yok diye atlanıyor.

**Düzeltme ölçütü:** Rapor arşiv yolunu ve hash'ini kaydetmeli; orijinal yol yoksa aynı hash'li yerel `Raporlar/Kaynak` kopyası kullanılmalı. Klasör taşınması sonrasında da göreli yol çözülmeli.

### 42. Şema-dışı yeni bir kalite raporu eski sağlam kaynak eşleşmesini tamamen engelliyor

**Kod:** `_resolve_postprocess_source` `subtitle_translator_gui.py:5529-5556`

JSON okuma hatası yakalanıyor fakat parse edilen payload'ın dict, `files` alanının liste ve satırların dict olduğu doğrulanmıyor. En yeni `ceviri_raporu*.json` içeriği geçerli JSON `[]` ise `payload.get(...)` doğrudan `AttributeError` fırlatıyor; resolver sonraki eski ve sağlam rapora geçemiyor.

Saf karşı örnekte aynı `Raporlar` klasöründe:

```text
ceviri_raporu_older.json -> doğru source/output eşleşmesi
ceviri_raporu_newer.json -> []

_resolve_postprocess_source -> AttributeError: 'list' object has no attribute 'get'
```

**Düzeltme ölçütü:** Her rapor için payload/files/row şeması fail-soft doğrulanmalı; bozuk veya beklenmeyen rapor loglanıp atlanmalı ve resolver daha eski sağlam raporları taramaya devam etmeli.

## Üçüncü turda elenen yanlış alarmlar

- Kalite API yanıt checkpoint anahtarı model, sağlayıcı/base URL, tam request kwargs ve requested formatı hash'e katıyor; profil/model değişiminde eski cevap çapraz kullanılmıyor.
- Checkpoint response tüketimi namespace ve generation ile sınırlandırılmış; aynı oturumda aynı kayıt ikinci kez sessizce uygulanmıyor.
- Kaynak arşivinde aynı adlı fakat farklı içerikli iki dosya hash-sonekli ayrı adaylarla korunuyor; bu turda burada overwrite üretilemedi.
- Manuel post-işlem yazma öncesi hedef hash guard'ı, işlem sırasında kullanıcı tarafından değiştirilen finalin üzerine eski belleği yazmıyor.
- `atomic_write_json` tek başına yarım JSON bırakmıyor; Auto-Glossary bulgusu atomiklik değil, eski snapshot'ın güncel verinin üzerine atomik biçimde yazılmasıdır.

## Üçüncü tur değişiklik özeti

Yalnız bu Markdown raporuna üçüncü tur bulguları eklendi. Üretim kodu, testler, kullanıcı ayarları, aktif çeviri, kaynak altyazılar ve final çıktılar değiştirilmedi; commit atılmadı.

---

# Dördüncü Derin Tarama Turu

Bu turda önceki 42 maddeden bağımsız **6 yeni doğrulanmış hata** bulundu:

- **3 P1:** eski kaynağa ait tamamlanmış partial'ın yeni kaynağın finaline terfi edebilmesi, 1 ms'de başlayan ilk cue için sıfır süreli imza üretilmesi ve kronolojik olmayan cue sıralamasında imzaların üst üste bindirilip teslim denetiminden geçmesi.
- **3 P2:** beş kalite pass'inin şema-dışı satırları başarı sayması, partial fingerprint yazma hatasının sessizce recovery'yi devre dışı bırakması ve bozuk öncelikli partial'ın sağlam legacy partial'ı gölgelemesi.

Böylece bu belge toplam **48 doğrulanmış bulguya** ulaştı. Bu turda da üretim kodu, testler, ayarlar ve çalışan çeviri değiştirilmedi.

## Dördüncü tur P1 bulguları

### 43. Kaynağa bağlı olmayan tamamlanmış `.partial`, değişmiş kaynağın finaline terfi edebiliyor

**Kod:** `subtitle_translator_gui.py:13054-13122`

`promote_complete_partial_outputs`, partial adayının source-fingerprint'ini doğrulamıyor. Yalnız cue/timestamp kapsamı ve boş/eksik işareti bulunmamasına bakıyor. Aynı zamanlara sahip kaynak metin değişmişse eski çeviri, yeni kaynağın nihai `.srt` yoluna yazılabiliyor.

Saf geçici-dosya karşı örneği:

```text
Güncel kaynak : I like tea.
Eski partial  : Kahveyi severim.
Timestamp     : ikisinde de 00:00:01,000 --> 00:00:03,000

promoted                  = True
final                     = Kahveyi severim.
delivery_audit.status     = ok
delivery_audit.hard_error = False
```

Mevcut akış daha sonra fingerprint bulunmadığı için çoğu kez yeniden çeviriye devam eder; ancak eski metni önce gerçek final yoluna yazıyor. Run bu noktadan sonra durur/çökerse ana klasörde yanlış kaynak için üretilmiş, imzalı bir `.srt` kalıyor. Ayrıca 15. madde düzeltilirken terfiye fingerprint yazımı eklenirse bu kaynak-doğrulama açığı doğrudan sessiz yanlış-atlama hâline gelir.

**Düzeltme ölçütü:** Terfi öncesinde partial'ın kaydedilmiş kaynak SHA'sı güncel kaynağın SHA'sıyla eşleşmeli. Sidecar'ı olmayan legacy partial otomatik final yapılmamalı; kaynak-temelli kapsamlı denetim veya açık kullanıcı onayı olmadan yalnız recovery adayı olarak kalmalı.

### 44. İlk gerçek cue `00:00:00,001`de başlıyorsa sıfır süreli baş imzası üretiliyor

**Kod:** `_prepare_upload_ready_blocks`, `subtitle_translator_gui.py:5409-5429`; teslim zamanı kapısı `subtitle_translator_gui.py:14131-14140`

Başlangıç zamanı sıfırdan büyükse imza sonu `first_start - 1` yapılıyor. İlk cue 1 ms'de başladığında hem başlangıç hem bitiş 0 ms oluyor:

```text
Gerçek cue : 00:00:00,001 --> 00:00:02,000
Baş imza   : 00:00:00,000 --> 00:00:00,000

delivery_audit.status         = review
delivery_audit.hard_error     = True
reversed_timestamp_ids        = ["0"]
```

Sıfırda başlayan cue için özel 0–1 ms istisnası var; 1 ms başlangıcı bu dala girmediği için geçerli kaynak her çalıştırmada teslim hard-error'ına düşüyor. Bu sessiz bozulma değil, garantili ve gereksiz teslim/recovery başarısızlığıdır.

**Düzeltme ölçütü:** `first_start < 2 ms` aynı güvenli istisnaya bağlanmalı veya baş imza atlanmalı; hiçbir koşulda `end <= start` imza üretilmemeli. 0 ms, 1 ms ve 2 ms başlangıçları ayrı regresyon fixture'larıyla doğrulanmalı.

### 45. Kronolojik olmayan cue sıralamasında üç imza üst üste bindirilip teslim denetiminden `ok` geçiyor

**Kod:** baş/son imza seçimi `subtitle_translator_gui.py:5409-5454`; kronolojik orta slot `subtitle_translator_gui.py:4978-5018`; imza overlap denetimi `subtitle_translator_gui.py:14141-14155`

Orta imza slotu cue'ları zamana göre sıralıyor; baş ve son imza ise listenin fiziksel ilk/son cue'sunun zamanını kullanıyor. Kaynak cue'ları dosyada kronolojik değilse baş, orta ve son imza aynı boşluğa düşebiliyor. Denetim yalnız imza–diyalog çakışmasını kontrol ediyor, imza–imza çakışmasını görmüyor.

Saf karşı örnek:

```text
Liste sırası: 10–12 sn, 1–3 sn, 5–7 sn

Baş imza : 7.999–9.999
Orta imza: 7.500–9.500
Son imza : 7.001–9.001

Üç imza birbirine çakışıyor.
delivery_audit.status     = ok
delivery_audit.hard_error = False
```

Diyalog zamanları değiştirilmediği hâlde final dosya kronolojik olmayan sırada kalıyor ve üç imza aynı anda gösteriliyor. Mevcut test yalnız orta slotun diyalogla çakışmamasını kontrol ediyor; baş/son sınırı ve imzaların birbirleriyle çakışması kapsanmıyor.

**Düzeltme ölçütü:** Başlangıç için tüm gerçek cue'ların minimum start'ı, son için maksimum end'i kullanılmalı. İmza yerleşimi tek kronolojik zaman çizelgesinden üretilmeli; audit imza–imza çakışmasını ve imzaların kronolojik sırasını da doğrulamalı.

## Dördüncü tur P2 bulguları

### 46. Critic, Native, Condense, Bağlam İncelemesi ve Geri Çeviri `[null]` cevabını tamamlandı sayıyor

**Kod:** Native `hybrid_translate.py:4349-4364`; Condense `hybrid_translate.py:4717-4733`; Geri Çeviri stage-2 `hybrid_translate.py:5039-5055`; Critic `hybrid_translate.py:13152-13169`; Bağlam İncelemesi `subtitle_translator_gui.py:27773-27784,27877`

Bu geçişler üst seviyenin JSON liste olmasını yeterli sayıyor. Liste satırlarının gerekli nesne şemasına uyup uymadığı başarı sayılmadan önce doğrulanmıyor. `[null]` geçerli bir liste olduğu için `null` satırı sonradan sessizce atlanıyor, chunk ise başarılı kabul ediliyor.

Saf mock sonuçları:

```text
Native              -> status=completed, successful=1/1, changed=0
Condense            -> status=completed, successful=1/1, changed=0
Critic              -> status=completed, successful=1/1, changed=0
Bağlam İncelemesi   -> status=completed, successful=1/1, changed=0
Geri Çeviri stage-2 -> status=completed, successful=1/1, flagged=[]
```

Bu, `[]` biçimindeki meşru “öneri yok” cevabından farklıdır: `[null]` sağlayıcı/model şema ihlalidir ve hiçbir cue'nun gerçekten incelendiğini kanıtlamaz. QC'nin `issues:null` ve Nihai Anlam'ın `[null]` sorunu 33–34. maddelerde ayrı kod yolları olarak zaten kayıtlıdır.

**Düzeltme ölçütü:** Her liste satırı pass'in zorunlu ID/metin/reason şemasına uymalı. Şema-dışı tek satır chunk'ı `partial/invalid` yapmalı; eksik ID'ler hedefli yeniden istenmeli veya raporlanmalı. Gerçek boş `[]` yalnız prompt sözleşmesi açıkça buna izin veriyorsa başarılı “değişiklik yok” sayılmalı.

### 47. Stage → partial taşınırken fingerprint yazma hatası sessizce kurtarmayı kullanılamaz bırakıyor

**Kod:** `_move_stage_to_partial`, `subtitle_translator_gui.py:12798-12813`; recovery kapısı `subtitle_translator_gui.py:13030-13050`; çağrılar `subtitle_translator_gui.py:34516-34522,34587-34593`

Stage dosyası önce gerçek partial yoluna taşınıyor. Ardından `_write_output_source_fingerprint` çağrısının `False` sonucu kontrol edilmiyor; fonksiyon yine başarıyla partial path döndürüyor ve çağıran “sonuç ayrıldı/yazıldı” diye logluyor.

Saf karşı örnekte fingerprint yazıcısı disk/izin hatasını temsil edecek biçimde `False` döndürdü:

```text
partial_exists      = True
stage_exists        = False
fingerprint_written = False
recoverable_partial = None
recovery_allowed    = False
```

Çeviri metni diskte korunuyor fakat bir sonraki otomatik recovery onu kaynak bağlı kabul etmiyor; kullanıcıya bunun nedeni bildirilmeden iş yeniden çevrilebilir.

**Düzeltme ölçütü:** Taşıma ve fingerprint tek bir başarı sözleşmesi olmalı. Fingerprint yazılamazsa stage/partial korunmalı fakat durum açıkça `failed/review` kaydedilmeli; başarı logu yazılmamalı ve kullanıcıya manuel kurtarma yolu gösterilmeli. Mümkünse metadata ile dosya geçişi atomik/rollback'li olmalı.

### 48. Öncelikli bozuk partial, sağlam legacy partial adayının terfisini engelliyor

**Kod:** `subtitle_translator_gui.py:13069-13085`; aday sırası `subtitle_translator_gui.py:12792-12795`

Terfi fonksiyonu mevcut adayların ilkini `next(...)` ile seçiyor. Öncelikli `Raporlar/Kurtarma/out.partial.srt` eksikse fonksiyon o dosyayı reddedip sonraki kaynağa geçiyor; aynı output için ikinci aday olan legacy `out.partial.srt` eksiksiz olsa bile onu hiç denemiyor.

Saf karşı örnek:

```text
Raporlar/Kurtarma/out.partial.srt = 1/2 cue, eksik
out.partial.srt                   = 2/2 cue, eksiksiz

promoted  = []
out_exists = False
```

`_recoverable_partial_output_path` adayları sırayla gezerken terfi yolu aynı pariteyi taşımıyor. Sonuç gereksiz yeniden çeviri veya tamamlanmış legacy işin görünmez kalmasıdır.

**Düzeltme ölçütü:** Her partial adayı bağımsız kaynak fingerprint'i, kapsam ve teslim denetiminden geçirilmeli; ilk geçersiz aday sonraki güvenli adayı gölgelememeli. Birden fazla geçerli ama farklı aday varsa otomatik seçim yerine hash/state bilgisiyle fail-closed raporlanmalı.

## Dördüncü turda elenen yanlış alarmlar

- Tam sıfırda başlayan ilk cue için 0–1 ms imza istisnası mevcut ve audit tarafından bilinçli biçimde kabul ediliyor; 44. madde yalnız 1 ms başlangıcındaki sıfır-süre üretimidir.
- Normal `_recoverable_partial_output_path` bütün adayları geziyor ve fingerprint istiyor; 48. madde yalnız otomatik tam-partial terfi yolundaki ilk-aday davranışıdır.
- Polish Pass `[null]` satırını malformed olarak yakalayıp chunk'ı reddediyor; 46. maddedeki beş geçişle aynı açık onda yeniden üretilemedi.
- Terim Normalizasyonu eksik/çelişkili ID kümesini successful saymıyor; bu turda onun JSON kabul zincirinde yeni bağımsız şema açığı bulunmadı.
- 1 ms imza hatası nihai audit tarafından hard-error olarak yakalanıyor; sorun bozuk finalin sessizce onaylanması değil, geçerli bir kaynağın program tarafından kaçınılmaz biçimde bozuk imzaya dönüştürülmesidir.

## Dördüncü tur değişiklik özeti

Yalnız bu Markdown raporuna dördüncü tur bulguları eklendi. Üretim kodu, testler, kullanıcı ayarları, aktif çeviri, kaynak altyazılar ve final çıktılar değiştirilmedi; commit atılmadı.

---

# Uygulama durumu (2026-08-20, Opus 5)

48 bulgunun **47'si düzeltildi**, 1'i (madde 3) kısmen. Doğrulanan her madde
gerçekti; bu raporda yanlış pozitif çıkmadı. Her düzeltme önce karşı örnekle
üretildi, sonra regresyon testine dönüştürüldü:
`tests/test_deep_audit_20260820.py` (60+ test). Suite 3709 test, tamamı geçiyor.

| commit | maddeler |
|---|---|
| 0f553bd | 1, 2, 5, 6, 8, 14, 30, 44, 45 |
| ad3a6e9 | 4, 11, 22, 23, 39, 41, 42 |
| 30d6e3b | 33, 34, 46 |
| ac6ffb7 | 15, 43, 47, 48 |
| 668fcbc | 9, 16, 24, 25, 37 |
| 6def075 | 26, 27, 31, 35, 36 |
| 02ff707 | 12, 18, 20, 38, 40 |
| c299154 | 13, 19, 32 |
| 0beda38 | 29 |
| e0a286c | 10, 21 |
| 73f8c6e | 28 |
| 93299e5 | 3 (kısmi) |
| f9756f7 | 17 |

## Kapsam dışı bırakılanlar (gerekçeli)

- **Madde 3 — prompt genelleştirmesi.** Türkçe kanon tablosu artık hedef dile
  bağlı (93299e5). Sync/hybrid promptlarındaki Türkçe alfabe/söz dizimi/ek
  kurallarının hedefe göre dallandırılması YAPILMADI: proje fiilen yalnız
  Türkçeye çeviriyor, değişiklik prompt genelinde ve Türkçe yolunu bozma riski
  gerçek. Ayrı bir tur olarak açık kalıyor.
- **Madde 6 — çıplak yer adı.** `BERLIN 1961`, `THE END`, `ACT I`, `PART TWO`
  korunuyor; tek başına `LONDON` sözcük dağarcığı olmadan ses etiketinden
  ayırt edilemiyor. Bilinen sınır olarak duruyor.
- **Madde 22 — tek karakterlik Korece.** CP932/GBK/CP1256 düzeldi; 2 baytlık
  tek Korece karakter gb18030 ile örtüşüyor ve ayırt edilemiyor (önceden de
  mojibake'ti, gerileme yok).
- **Madde 37 — kapsam kararı.** "Yalnız Raporla" anahtarı Polish/Native/QC/
  Kısaltma'yı durdurmuyor; bunlar zaten kullanıcının AÇIKÇA seçtiği ve metni
  değiştirmek için var olan geçişler. Anahtarın adı ve açıklaması ne yapıp ne
  yapmadığını söyleyecek biçimde düzeltildi.

## Süreçte ortaya çıkan iki ek düzeltme

- Madde 8'in eski sözleşmesini kilitleyen test (`cross_sentence_named_content_swap`)
  güncellendi: cue sahiplik kayması artık sert hata.
- Madde 31 için `tests/test_video_subtitles.py` fixture'ları gerçek altyazı
  gövdesi yazacak biçimde düzeltildi (eskiden `"subtitle"` metniydi).
