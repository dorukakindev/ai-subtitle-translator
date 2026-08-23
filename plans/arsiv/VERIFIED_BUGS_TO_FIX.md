# Doğrulanmış Bug Düzeltme Listesi

Bu belge, 24 Temmuz 2026 tarihindeki mevcut kod üzerinde doğrulanan ve
düzeltilmesi gereken bulguları içerir. Yanlış pozitifler özellikle bu listeye
alınmamıştır.

## Çalışma kuralları

- Önce mevcut `git status --short` ve son commitleri kontrol et.
- `stash@{0}` içeriğini uygulama, silme veya değiştirme.
- Mevcut untracked dosyalara dokunma. Özellikle çalışan çeviriye ait olabilecek
  `.sync_checkpoint.json.lock`, batch, session, log ve ayar dosyalarını temizleme.
- Büyük refaktör yapma. Her bug için küçük, yerel bir düzeltme ve doğrudan
  regresyon testi tercih et.
- Dört çeviri akışındaki etkileri kontrol et:
  `_run_sync`, `_run_batch`/`_write_results`, `_run_sync_hybrid`,
  `_run_hybrid` ve resume yolları.
- GUI değişikliğinde, gerçek bir çevirinin çalışmadığı kesinleşmeden `App()`
  oluşturan test veya headless smoke testi çalıştırma.
- İlgili testler, `py_compile` ve mümkünse tam `unittest` paketi başarılı
  olmadan commit oluşturma.
- Her mantıksal düzeltme grubunu ayrı commit et; yalnız dokunulan dosyaları
  stage et. `git add .` veya `git add -A` kullanma.

---

## P0 — Önce düzeltilmesi gerekenler

### 1. Batch resume çalışan durumuna geçmiyor

**Dosya:** `subtitle_translator_gui.py`, `_resume`

`_resume()` worker başlatmadan önce `_set_running(True)` çağırmıyor. Bu nedenle
resume sırasında Stop düğmesi devre dışı kalabiliyor ve ikinci bir işlem
başlatılabiliyor.

**Kabul ölçütleri:**

- Geçerli batch ID'leri doğrulandıktan sonra, worker başlamadan önce uygulama
  running durumuna geçmeli.
- Erken validation/bozuk batch ID dönüşlerinde running durumu yanlışlıkla açık
  kalmamalı.
- Başarı, hata ve stop yolları running durumunu tekrar kapatmalı.
- Resume sırasında ikinci Start/Resume engellenmeli ve Stop etkin olmalı.

### 2. Anthropic kök URL'si yanlış `/messages` adresi üretiyor

**Dosya:** `helper_models.py`, `call_anthropic_messages`

`base_url="https://api.anthropic.com"` verilirse mevcut koşul `/v1` eklemiyor
ve `https://api.anthropic.com/messages` oluşturuyor. Doğru adres
`https://api.anthropic.com/v1/messages`.

**Kabul ölçütleri:**

- Aşağıdaki girişlerin tamamı doğru ve tek bir `/messages` ile bitmeli:
  `https://api.anthropic.com`,
  `https://api.anthropic.com/v1`,
  `https://api.anthropic.com/v1/messages`.
- Mevcut proxy/OpenCode `/v1/messages` adresleri bozulmamalı.
- URL kurulumunu saf bir yardımcı fonksiyonla test etmek tercih edilir; ağ
  çağrısı yapılmamalı.

### 3. Credential migration ayar dosyasını atomik yazmıyor

**Dosya:** `credential_store.py`, `migrate_from_settings`

Anahtarlar credential store'a taşındıktan sonra `.gui_settings.json` doğrudan
`open(..., "w")` ile yeniden yazılıyor. Yazma sırasında çökme diğer GUI
ayarlarını truncate edebilir.

**Kabul ölçütleri:**

- Aynı klasörde geçici dosyaya UTF-8 JSON yazılmalı, flush/fsync uygun biçimde
  tamamlandıktan sonra `replace` kullanılmalı.
- Başarısız yazmada mevcut ayar dosyası korunmalı.
- Credential store'a başarıyla taşınan sırlar yeni JSON'da bulunmamalı.
- Mevcut dosya izinleri ve Windows replace davranışı gözetilmeli.

### 4. Hybrid-batch başarı kuyruğunda son eksik-çeviri güvenlik adımı yok

**Dosya:** `subtitle_translator_gui.py`, `_run_hybrid` Phase 2 başarı yolu

Başlangıçtaki eksik sonuç kontrolü bulunuyor; ancak kalite geçişlerinden sonra
canonical tail içinde `_fill_hata_with_source` tekrar uygulanmıyor. Bir kalite
geçişi boş veya `[HATA]` sonuç üretirse final yazım öncesi ortak güvenlik
invariantı diğer akışlarla aynı değil.

**Kabul ölçütleri:**

- Final sırası şu invariantı korumalı:
  kalite geçişleri → eksik çeviri işaretleme → tag restore → term normalization
  → final yazım.
- Kaynak diyalog asla sessizce silinmemeli; `[ÇEVİRİ EKSİK]` görünür kalmalı.
- Saf SFX/boş kaynak cue'ları yanlışlıkla eksik çeviri olarak eklenmemeli.
- Rapor sayacı son aşamada işaretlenen satırları doğru saymalı.

### 5. API'ye giden iki hybrid prompt parçası mojibake

**Dosya:** `hybrid_translate.py`

İki gerçek bozuk runtime string bulunuyor:

- `build_system_prompt` içindeki SCRIPT GUARD'ın Arapça, Tamil, Devanagari ve
  Kiril örnekleri.
- `native_reader_pass` içindeki “Şu deyimleri doğal Türkçe karşılığıyla oku...”
  cümlesi.

Sync SCRIPT GUARD örnekleri sağlamdır; onları bozma.

**Kabul ölçütleri:**

- Runtime promptunda gerçek Unicode örnekleri ve doğru Türkçe görünmeli.
- Kaynak dosyayı topluca yeniden encode etme; yalnız bozuk stringleri düzelt.
- Testler dosya kaynak metnini değil, oluşturulan runtime promptunu denetlemeli.

### 6. Review kilitli glossary bloğu sanitizasyondan geçmiyor

**Dosya:** `subtitle_translator_gui.py`, `_locked_terms_hint`

Dosya glossary'si ve proje hafızası glossary'si doğrudan review system promptuna
ekleniyor. Diğer çeviri yollarındaki
`hybrid_translate.sanitize_glossary_for_turkish()` burada uygulanmıyor.
Analizden kalan açıklama, seçenek veya talimat benzeri hedefler review modeline
kilitli terim gibi gönderilebilir.

**Kabul ölçütleri:**

- Kilitli terimler hedef dile uygun sanitizer'dan geçirilmeli.
- Karakter isimleri ayrı ve güvenli biçimde korunmalı.
- Temiz glossary girdileri değişmemeli.
- Parantezli açıklama, uzun meta-not, yabancı-script ve toplu dil kayması
  örnekleri review promptuna girmemeli.
- Sanitizer logları API anahtarı veya hassas veri içermemeli.

### 7. Translation Memory içerik şemasını kimliğe katmıyor

**Dosyalar:** `subtitle_translator_gui.py`, `translation_memory.py`

`_store_tm_pairs()` `schema_name` iletmiyor. Ancak yalnız bunu iletmek yeterli
değildir: TM hash/fingerprint ve lookup fonksiyonları da schema'yı kullanmıyor.
Aynı kaynak cümle farklı tür/şemalarda farklı üslup gerektirse bile aynı TM
kaydına çarpabilir.

**Kabul ölçütleri:**

- `store`, `store_batch`, `lookup`, `lookup_batch` ve `fuzzy_lookup` aynı
  schema-aware fingerprint politikasını kullanmalı.
- Çağrı noktaları dosyanın etkin şema adını iletmeli.
- Eski schema'sız kayıtlar için bilinçli ve güvenli bir geriye uyumluluk
  politikası belirlenmeli; başka şemaya ait kayıt sessizce sızmamalı.
- Aynı kaynak+hedef dil+model fakat farklı schema için iki ayrı TM sonucu
  regresyon testiyle doğrulanmalı.

---

## P1 — Önemli fakat P0 sonrasında

### 8. Hybrid resume Native ve QC analiz bağlamını almıyor

**Dosya:** `subtitle_translator_gui.py`, `_wait_batch_hybrid`

Resume yolu context cache'i yüklüyor ve Critic/Polish'e `analysis_result`
aktarıyor. Native Reader ve `quality_check_with_helper` çağrıları ise aynı
değeri almıyor. “Bütün pass'ler bağlamsız” değildir; eksik yalnız bu iki çağrı
noktasındadır.

**Kabul ölçütleri:**

- Native ve QC çağrıları `_analysis_result` almalı.
- Cache bulunmazsa mevcut `None` davranışı korunmalı.
- Normal hybrid ve resume davranışları için çağrı argümanı testi eklenmeli.

### 9. Dosya logu da 500 karaktere kesiliyor

**Dosya:** `subtitle_translator_gui.py`, `_log`

Mesaj, hem UI'ya hem log dosyasına yazılmadan önce 500 karaktere kırpılıyor.
Uzun API hata gövdeleri ve traceback ayrıntıları kalıcı logdan kayboluyor.

**Kabul ölçütleri:**

- UI satırı okunabilirlik için kırpılabilir.
- Disk loguna tam, redakte edilmiş mesaj yazılmalı.
- API anahtarları ve bilinen secret kalıpları tam logda görünmemeli.

### 10. Eski batch fmap resume fallback'i mevcut UI ayarlarına bağımlı

**Dosya:** `subtitle_translator_gui.py`, `_resume_batches`

Yeni fmap dosyaları kaydedilmiş request'leri kullandığı için normalde güvenli.
Ancak request taşımayan eski fmap'lerde retry request'leri mevcut UI'dan yeniden
oluşturuluyor; chunk ayarları değiştiyse custom ID/file-map eşleşmesi bozulabilir.

**Kabul ölçütleri:**

- Kaydedilmiş request varsa her zaman o kullanılmalı.
- Eski fmap güvenli biçimde yeniden oluşturulamıyorsa yanlış final yazmak yerine
  açık hata verip recovery verisini korumalı.
- Değişmiş chunk size/context/UI state ile legacy fmap regresyonu eklenmeli.

### 11. Resume post-processing hatası ham yedeği atlayabiliyor

**Dosya:** `subtitle_translator_gui.py`, `_wait_batch_hybrid`

Ham bloklar kalite geçişlerinden önce yakalanıyor; bu kısım doğrudur. Ancak
`_save_raw_backup()` geniş post-processing `try` bloğunun sonundadır. Önceki bir
pass exception verirse ham yedek hiç yazılmayabilir.

**Kabul ölçütleri:**

- Ham yedek, kalite pass'lerinin başarısından bağımsız yazılabilmeli.
- Yedek pre-quality blokları kullanmalı; final kalite değişikliklerini
  içermemeli.
- Hata işaretleme ve tag restore dışında ham içeriği değiştirmemeli.

### 12. ASS Events Format araması `[` karakteriyle erken kesiliyor

**Dosya:** `subtitle_formats.py`, `parse_ass`

`[Events][^\[]*?Format:` regex'i, `Format:` satırından önce `[` içeren Comment
veya metadata olduğunda formatı bulamıyor. Varsayılan kolon sırası tesadüfen
çalışabilir; özel kolon sırası boş parse ediliyor.

**Kabul ölçütleri:**

- Önce gerçek `[Events]` section sınırları çıkarılmalı, ardından o bölümdeki
  ilk gerçek `Format:` satırı satır bazında bulunmalı.
- Dialogue metnindeki `[` karakterleri parserı etkilememeli.
- Özel kolon sırası + Format öncesi köşeli parantezli Comment testi eklenmeli.

### 13. Virgüllü ve boş satırsız VTT cue'ları birleşiyor

**Dosya:** `subtitle_formats.py`, `parse_vtt`

Timestamp parser hem `.` hem `,` kabul ediyor; fakat cue ayırma guard'ı yalnız
`.` kabul ediyor. Boş satırları olmayan virgüllü VTT'de sonraki timestamp ve
metin önceki cue'nun metnine karışıyor.

**Kabul ölçütleri:**

- Ayırma regex'i parserın kabul ettiği timestamp grameriyle aynı olmalı.
- Noktalı ve virgüllü, saatli ve saatsiz timestamp biçimleri denenmeli.
- Boş satırlı geçerli VTT davranışı değişmemeli.

### 14. Pending batch açılış kontrolü hataları görünmez

**Dosya:** `subtitle_translator_gui.py`, `_check_pending_batches`

Dış `except Exception: pass`, batch recovery dialogunun neden açılmadığını
tamamen gizleyebilir.

**Kabul ölçütleri:**

- Uygulama açılışını düşürmeden kısa bir warning loglanmalı.
- API anahtarı veya batch içerikleri loga sızmamalı.
- Widget kapanışı/shutdown kaynaklı beklenen hatalar gürültülü log
  üretmemeli.

### 15. Tek haneli VTT dakikası malformed SRT zamanı üretiyor

**Dosya:** `subtitle_formats.py`, `_vtt_ts_to_srt`

`1:23.456` girdisi `00:1:23,456` oluyor. SRT dakika alanı iki haneli olmalı.

**Kabul ölçütleri:**

- `1:23.456` → `00:01:23,456`.
- Saatli biçim, milisaniye padding ve mevcut geçerli biçimler bozulmamalı.

### 16. Düz `_write_results` condense yanlış helper rolünü kullanıyor

**Dosya:** `subtitle_translator_gui.py`, `_write_results`

Bu akış `_maybe_condense` için `qc` key/url/model kullanırken diğer akışlar
`analysis` rolünü kullanıyor.

**Kabul ölçütleri:**

- Condense için belirlenen tek rol bütün akışlarda aynı olmalı.
- Kullanıcıya özel analysis provider/key/model yönlendirmesi korunmalı.
- Ana API anahtarı yanlışlıkla helper çağrısına sızmamalı.

### 17. İçerik tespit promptunda listede olmayan örnek kategoriler var

**Dosya:** `subtitle_translator_gui.py`, `detect_content_type_with_ai`

Örneklerde `Gaming` ve `Akademik Anlatım` geçiyor fakat bunlar oluşturulan
kategori listesinde yok. Modelden aynı anda hem örneğe uyması hem listeden birebir
seçmesi isteniyor.

**Kabul ölçütleri:**

- Örnek kategoriler `_detect_categories()` çıktısında gerçekten bulunan
  adlardan seçilmeli veya yanıltıcı örnekler kaldırılmalı.
- Yeni schema eklendiğinde yeniden sabit ad uyumsuzluğu oluşmamalı.

### 18. Düz akış kalite raporunda gerçek sayaçlar eksik

**Dosya:** `subtitle_translator_gui.py`, `_write_results`

Rapor satırı `pass_fix`, `qc` ve `qc_auto` alanlarını üretmiyor. Rapor
oluşturucu eksik alanları tolere ediyor fakat akışlar arası rapor bilgisi
tutarsız.

**Kabul ölçütleri:**

- Yalnız gerçekten uygulanan değişiklikler sayılmalı; issue sayısı değişiklik
  sayısı sanılmamalı.
- Düz ve hybrid raporlarının ortak alanları aynı anlamı taşımalı.

---

## P2 — Düşük öncelikli gerçek buglar ve sağlamlık açıkları

### 19. Batch iptalinde owner dosyası hemen güncellenmiyor

**Dosya:** `subtitle_translator_gui.py`, `_cancel_active_batches`

`_active_batches.clear()` sonrasında `_write_batch_owner()` çağrılmıyor. Etkisi
sınırlıdır; recovery ID'leri ayrıca temizlenir ve ölü PID dosyaları sonraki
açılışta kaldırılır. Yine de owner state invariantı bozuluyor.

**Kabul ölçütleri:**

- Clear işleminden sonra owner dosyası güncellenmeli/silinmeli.
- Lock sırası deadlock üretmemeli (`_batch_lock` davranışını koru).

### 20. Başarısız SRT yazımı `.srt.tmp` bırakabiliyor

**Dosya:** `subtitle_translator_gui.py`, `write_srt`

Atomik yazım final dosyayı koruyor fakat exception halinde geçici dosya
kalabiliyor.

**Kabul ölçütleri:**

- Başarısızlıkta yalnız bu çağrının kesin hedefi olan temp dosyası best-effort
  temizlenmeli.
- Mevcut final SRT asla silinmemeli.

### 21. Eski batch session dosyaları için sınırlı garbage collection yok

**Dosya:** `hybrid_translate.py`, `_batch_sessions`

Session dosyalarının kalıcı olması resume tasarımının parçasıdır; körlemesine
silinmemelidir. Bununla birlikte artık var olmayan input klasörlerine ait veya
uzun süredir tamamen terminal durumda olan JSON'lar süresiz birikir.

**Kabul ölçütleri:**

- `submitted`, canlı veya recovery için gerekli session asla otomatik
  silinmemeli.
- Yalnız açıkça güvenli, eski terminal/nonexistent-input session'lar yaş ve
  durum kontrolüyle temizlenmeli.
- Bozuk JSON temizliği diğer session'ları etkilememeli.

### 22. Türkçe `İ` kategori eşleşmesinde casing varyantını kaçırıyor

**Dosya:** `subtitle_translator_gui.py`, `_match_category`,
`normalize_schema_name`

Model kategori adını listede yazıldığı biçimde döndürürse eşleşme çalışıyor.
Ancak `Dini İçerik / Vaaz` yerine farklı casing ile
`dini içerik / vaaz` dönerse Unicode dotted-I nedeniyle eşleşme kaçabiliyor.

**Kabul ölçütleri:**

- NFC/NFKC ve Türkçe-dostu karşılaştırma anahtarı kullanılmalı.
- Tam ad, küçük harf ve büyük harf varyantları aynı canonical schema'ya
  dönmeli.
- Diğer schema adları bozulmamalı.

### 23. Standalone batch script boş çeviriyi hata metnine çeviriyor

**Dosya:** `subtitle_batch_translate.py`, `process_results`

`translations.get(cid) or "[ÇEVIRI HATASI]"`, bilinçli boş string ile eksik/None
sonucunu ayıramıyor.

**Kabul ölçütleri:**

- Missing key/None/error ile mevcut fakat boş string ayrı ele alınmalı.
- Saf SFX için boş sonuç politikası açık olmalı; gerçek diyalog sessiz
  kaybolmamalı.

### 24. Geliştirici smoke scripti SDH temizliğine kaynak haritası vermiyor

**Dosya:** `_smoke_test.py`

Üretim akışları source-driven SDH kullanıyor; smoke scripti ise
`clean_sdh_blocks(sorted_blocks)` çağırıyor. Boş model çıktısındaki gerçek
diyalog cue'su geliştirici test çıktısından düşebilir.

**Kabul ölçütleri:**

- Kaynak cue map'i ve `source_driven=True` kullanılmalı.
- Üretim davranışını temsil eden küçük smoke örneği eklenmeli.

### 25. `repair_batches.py` bilinmeyen CID için teşhis vermiyor

**Dosya:** `repair_batches.py`

CID fmap'te yoksa eşlenecek cue bulunmadığından `[HATA]` üretilemez; fakat bu
durum açıkça loglanmıyor ve yalnız chunk failure sayısına karışıyor.

**Kabul ölçütleri:**

- Bilinmeyen CID açık warning olarak yazılmalı.
- Diğer geçerli CID'lerin işlenmesi devam etmeli.
- Bilinmeyen CID herhangi bir cue'ya tahminen eşlenmemeli.

### 26. Generic SDH sınıflandırıcısı `[speaks Latin]` biçimini tanımıyor

**Dosya:** `sdh_cleaner.py`, `is_sdh_descriptor`

Üretim source-driven yolu kaynak parantezlerini çoğunlukla yapısal olarak
temizler. Fakat generic sınıflandırıcı `speaking French` ve `in Spanish`
kalıplarını tanırken `speaks Latin` kalıbını tanımıyor.

**Kabul ölçütleri:**

- `speaks <known language>` güvenli biçimde descriptor sayılmalı.
- `[Latin]` gibi anlamlı tek kelimelik başlıklar körlemesine silinmemeli.

### 27. SDH bracket parserı uzun ve iç içe açıklamalarda sınırlı

**Dosya:** `sdh_cleaner.py`, `BRACKET_OR_PAREN_RE`

100 karakterden uzun veya iç içe parantezli SDH açıklamaları tam
temizlenmeyebilir.

**Kabul ölçütleri:**

- Sınırsız/katastrofik regex yazma; makul üst sınır ve lineer davranış koru.
- Gerçek nesir parantezlerini yanlışlıkla silme.
- Uzun descriptor ve iç içe örnekler için regresyon testi ekle.

### 28. Açılıştaki pending-batch `after` callback'i saklanıp iptal edilmiyor

**Dosya:** `subtitle_translator_gui.py`, `__init__`, `_on_close`

`after(500, self._check_pending_batches)` tek seferlik olsa da ID'si
saklanmıyor. Pencere ilk 500 ms içinde kapanırsa destroy edilmiş widget için
callback uyarısı oluşabilir.

**Kabul ölçütleri:**

- Callback ID saklanmalı ve close sırasında best-effort iptal edilmeli.
- Callback çalıştıktan sonra ID temizlenmeli.

### 29. Resume maliyet/token oturum sayaçlarını sıfırlamıyor

**Dosya:** `subtitle_translator_gui.py`, `_resume`

Normal Start `_token_total`, `_token_cached`, `_cost_total` ve TM session
hitlerini sıfırlıyor; Resume aynı başlangıç muhasebesini yapmıyor. Aynı GUI
oturumunda önceki işlem değerleri resume maliyetine karışabilir.

**Kabul ölçütleri:**

- Resume yeni bir kullanıcı koşusu olarak aynı sayaç reset politikasını
  uygulamalı.
- Worker başladıktan sonra geç gelen eski UI callback'leri yeni sayacı
  ezmemeli.

### 30. `_clean_src` boş ASS override tag'ini temizlemiyor

**Dosya:** `subtitle_translator_gui.py`, `_clean_src`

Regex `\{[^}]+\}` kullandığı için bozuk/boş `{}` model payloadına sızabiliyor.

**Kabul ölçütleri:**

- `{}` temizlenmeli.
- Normal metindeki eşleşmeyen süslü parantezler gereksiz yere silinmemeli.
- `subtitle_formats` ASS temizliğiyle semantik uyum korunmalı.

### 31. Glossary basit çoğul normalizasyonunda `rstrip("s")` fazla geniş

**Dosya:** `hybrid_translate.py`, `_glossary_wqx_token`

`rstrip("s")` yalnız tek bir çoğul `s` kaldırmaz; sondaki bütün `s`
karakterlerini kaldırır. Raporun `processes` örneği doğrudan bir failure
üretmese de, sonu birden fazla `s` ile biten özel isimlerde yanlış eşitlik veya
beklenmedik guard muafiyeti oluşturabilir.

**Kabul ölçütleri:**

- Yalnız açıkça desteklenen basit çoğul eki kaldırılmalı.
- `Newsweeks`/`Newsweek` mevcut regresyonu korunmalı.
- `boss`, `process`, `processes` ve w/q/x içeren özel isim örnekleriyle yanlış
  eşleşme olmadığı test edilmeli.

---

## Ek doğrulanan bulgular — 25 Temmuz 2026

### 32. Remote batch oluşturulduktan sonra fmap yazılamazsa ücretli orphan batch kalıyor

**Öncelik:** P0  
**Dosyalar:** `hybrid_translate.py`, `submit_batch`;
`subtitle_translator_gui.py`, düz batch gönderim yolu

Her iki akışta da uzak batch önce oluşturuluyor ve batch ID yerel aktif listeye
ekleniyor; dosya-cue eşlemesini taşıyan fmap bundan sonra yazılıyor. Fmap için
`atomic_write_json()` başarısız olursa batch sağlayıcıda çalışmaya devam ediyor,
fakat sonuçları güvenli biçimde dosyalara bağlayacak metadata yok. Rapor bu
problemi yalnız hybrid akışına yazmış; aynı hata düz batch yolunda da mevcut.

**Kabul ölçütleri:**

- Uzak batch oluşturulduktan sonraki her yerel metadata hatası açıkça ele
  alınmalı; batch sessizce çalışır durumda bırakılamamalı.
- Güvenli tercih: fmap yazılamazsa uzak batch best-effort iptal edilmeli, batch
  ID kaybedilmemeli ve kullanıcıya kurtarma/iptal sonucu açıkça bildirilmelidir.
- Başarısız fmap kalıcı kaydından sonra normal resume yolu bu batch'i
  tüketilebilir gibi göstermemeli.
- Hem `hybrid_translate.submit_batch` hem düz GUI batch gönderimi için, batch
  create başarılıyken fmap yazımını hata verdirecek regresyon testleri eklenmeli.

### 33. Native Reader doğrulaması ve maliyet tahmini gerçek helper rolüyle uyuşmuyor

**Öncelik:** P1  
**Dosya:** `subtitle_translator_gui.py`, `_validate`, `_estimate_cost`

Native Reader çağrıları uygulamadaki akışlarda `critic` helper anahtarı, URL'si
ve modeliyle çalışıyor. Buna karşın `_validate()` Native açıkken `qc` rolünü
doğruluyor; maliyet tahmini de Native'i QC modeli altında hesaplıyor. Critic
ayarları geçerli, QC ayarları boş olduğunda çeviri yanlış biçimde engellenebilir;
farklı modeller seçildiğinde tahmin de yanlış modele yazılır.

**Kabul ölçütleri:**

- Native Reader için tek bir kanonik helper rolü belirlenmeli ve doğrulama,
  tahmin ile dört çalıştırma akışı aynı rolü kullanmalı.
- Native açık + geçerli Critic ayarı + boş QC ayarı senaryosu yanlış hata
  vermemeli.
- Native ve QC aynı anda açıksa iki geçiş ayrı ayrı ve doğru model fiyatıyla
  tahmin edilmeli.

### 34. `ProjectMemory` eşzamanlı UI/worker erişiminde güncelleme kaybedebilir

**Öncelik:** P1  
**Dosya:** `project_memory.py`, `ProjectMemory`

Atomik `tmp.replace()` yarım JSON riskini azaltıyor, fakat aynı `_data` sözlüğünü
okuyan ve güncelleyen UI ile çeviri thread'leri arasında kilit yok. İki
`update_*()` çağrısı aynı anda mutate+save yaptığında kayıp güncelleme ve aynı
`.tmp` dosyası üzerinde yarış oluşabilir.

**Kabul ölçütleri:**

- Instance düzeyinde `threading.RLock` veya eşdeğer bir koruma kullanılmalı.
- Getter'lar tutarlı kopyayı; update+save ise tek kilitli transaction'ı görmeli.
- İç içe `save()` çağrısı deadlock üretmemeli.
- Eşzamanlı glossary, karakter ve pronoun güncellemelerinin hiçbirini
  kaybetmediğini doğrulayan deterministik test eklenmeli.

### 35. Seçili dosyada post-process geri alınabilir ham yedek oluşturmadan üzerine yazıyor

**Öncelik:** P1  
**Dosya:** `subtitle_translator_gui.py`, `_run_post_process`

Post-process seçilen SRT'yi parse edip kalite geçişlerinden sonra doğrudan aynı
`fp` üzerine yazıyor. Bu bağımsız işlem yolunda, geçişler kaynak metni bozarsa
kullanıcının işlem öncesi sürüme dönmesini sağlayan bir yedek yok. Rapordaki
“merge hiç çağrılmıyor” kısmı yanlış: bu yol AI veya hızlı merge'i kendi içinde
uyguluyor; gerçek sorun yalnız geri dönüş kopyasının olmaması.

**Kabul ölçütleri:**

- İlk değişiklikten önce dosyanın işlem öncesi hali recoverable biçimde
  saklanmalı.
- Çeviri pipeline'ındaki `.ham.srt` anlamı körlemesine ezilmemeli; post-process
  için çakışmasız ve belgelenmiş bir yedek adı/politikası kullanılmalı.
- Yedek yazılamazsa özgün dosyanın üzerine yazmaya devam edilmemeli.
- Başarılı, başarısız ve mevcut yedekle çakışma senaryoları test edilmeli.

### 36. Düz `_write_results` Native Reader tokenlarını saymıyor

**Öncelik:** P2  
**Dosya:** `subtitle_translator_gui.py`, `_write_results`

Bu akıştaki `ht.native_reader_pass()` çağrısı `token_callback` vermiyor. Aynı
geçişin diğer akışları callback verdiği için yalnız bu yolun token ve maliyet
sayacı eksik kalıyor.

**Kabul ölçütleri:**

- Çağrı `token_callback=self._update_tokens` almalı.
- Düz batch sonuç yazma yolunda Native kullanımının sayaca tam bir kez
  eklendiğini doğrulayan regresyon testi olmalı.

### 37. Proje hafızasını panoya kopyalama hatası UI callback'inden dışarı taşıyor

**Öncelik:** P2  
**Dosya:** `subtitle_translator_gui.py`, proje hafızası iletişim kutusu

`clipboard_clear()` ve `clipboard_append()` doğrudan lambda içinde çağrılıyor.
Pano kilitli/erişilemez olduğunda Tk callback exception üretir ve kullanıcıya
anlaşılır bir sonuç gösterilmez. Bu genellikle tüm uygulama prosesini
çökertmez; rapordaki “crash” ifadesi abartılıdır, fakat gerçek bir UX ve
teşhis hatasıdır.

**Kabul ölçütleri:**

- Pano işlemi adlandırılmış, test edilebilir bir handler içinde yakalanmalı.
- Başarı ve hata kullanıcıya bildirilirken hafıza içeriği loga dökülmemeli.
- Pano exception'ı için regresyon testi eklenmeli.

### 38. Gelişmiş Ayarlar penceresinin X düğmesi İptal geri yüklemesini atlıyor

**Öncelik:** P2  
**Dosya:** `subtitle_translator_gui.py`, `_show_advanced_settings`

Slider'lar `self._chunk_size` gibi canlı alanları anında değiştiriyor. İptal
düğmesi snapshot'ı geri yüklese de pencerenin `WM_DELETE_WINDOW` protokolü aynı
İptal handler'ına bağlanmamış. Kullanıcı X ile kapatınca değişiklikler bellekte
kalır ve daha sonraki normal ayar kaydında istemeden kalıcılaşabilir.

**Kabul ölçütleri:**

- X düğmesi İptal ile aynı geri-yükleme ve kapatma yolunu kullanmalı.
- Kaydet davranışı değişmemeli.
- X, İptal ve Kaydet için alanların son değerini doğrulayan hedefli test
  eklenmeli.

### 39. Canlı token maliyeti helper ve harici provider çağrılarını ana model fiyatıyla yazabiliyor

**Öncelik:** P2  
**Dosya:** `subtitle_translator_gui.py`, `_update_tokens` ve helper callback
çağrıları

`_update_tokens()` çağrısına fiyat verilmezse ana modelin `MODEL_PRICE`
değerini kullanıyor. Critic, Polish, Native, QC ve analiz callback'lerinin çoğu
yalnız token sayısını gönderdiği için farklı helper modeli/provider kullanılsa
bile canlı toplam ana model fiyatından birikebilir. Bilinmeyen modeller de tek
bir varsayılan fiyata düşüyor. Ayrı maliyet tahmin penceresinin daha geniş fiyat
tablosu kullanması bu canlı sayaç sapmasını düzeltmiyor.

**Kabul ölçütleri:**

- Token callback kaynak rol/model/provider fiyat bilgisini kaybetmemeli.
- Ana model, batch indirimi ve her helper geçişi kendi seçili modeliyle
  fiyatlanmalı.
- Bilinmeyen model fiyatı kesin maliyetmiş gibi sunulmamalı; “tahmini/fiyat
  bilinmiyor” durumu açık olmalı.
- Farklı main/critic/qc modelleriyle karma bir oturum için maliyet regresyon
  testi eklenmeli.

---

## Ek doğrulanan bulgular — `BUG_RAPORU_SUPER.md`

### 40. Prompt dışındaki çalıştırılabilir mojibake kalıntıları bazı guard ve local fix'leri bozuyor

**Öncelik:** P1  
**Dosya:** `hybrid_translate.py`

Önceden doğrulanan iki prompt bozukluğuna ek olarak, doğrudan çalışan kod
içinde de çift-encode literal'lar var:

- `_POLISH_MODEL_CORRUPTION_RE` gerçek `mekişi` biçimini yakalamıyor.
- `_LOCAL_FIXES` içindeki `De Heilige Graal şatosu` özel kuralı gerçek metinle
  eşleşmiyor ve replacement metni de bozuk.
- `Bible` iyelik eki özel kuralındaki apostrof ve Türkçe ekler bozuk.
- `_ellipsis_continues`, `_looks_like_early_turkish_verb_closure`,
  `_foreign_latin_token` ve `_has_broken_fragment_flow` içindeki kıvrık
  tırnak/angle-quote temizleme kümelerinde gerçek Unicode işaretleri yerine
  mojibake karakter dizileri bulunuyor.

Rapordaki `_POLISH_CAUSATIVE_WANT_RE` “tamamen ölü” iddiası doğru değil:
karakter sınıfındaki `\w` Unicode Türkçe harfleri zaten kapsıyor ve `istet...`
deseni amaçlanan eski nedensel biçimi yakalayabiliyor. O regex körlemesine
yeniden yazılmamalı.

**Kabul ölçütleri:**

- Yalnız doğrulanmış bozuk literal'lar gerçek Unicode karşılıklarıyla
  değiştirilmeli; bütün dosyaya toplu transcoding uygulanmamalı.
- Gerçek `mekişi`, Graal şatosu, Bible iyelik ekleri, `…”`, `»`, `“` ve `‘’`
  örnekleri için davranış testi eklenmeli.
- `_has_causative_want_backslide()` mevcut doğru örnekleri korunmalı.
- Dosyada kalan şüpheli mojibake literal'ları için dar bir kaynak-tarama
  regresyonu eklenmeli; Türkçe olmayan meşru Latin-1 karakterler yasaklanmamalı.

### 41. Tek satırlık Markdown code fence içindeki geçerli JSON tamamen kayboluyor

**Öncelik:** P1  
**Dosyalar:** `hybrid_translate.py`, `_extract_json_array`,
`_salvage_json_objects`; `subtitle_translator_gui.py`, `_strip_md` ve aynı JSON
yardımcıları

Kod fence temizliği ilk satırı koşulsuz atıyor. Model yanıtı
```` ```json [{"i":"1","t":"Merhaba"}] ``` ```` biçiminde tek satır geldiyse
`split("\n")[1:]` boş kalıyor; geçerli JSON parse veya salvage edilmeden tüm
chunk hata/kayıp yoluna düşüyor.

**Kabul ölçütleri:**

- Tek satırlı ve çok satırlı ` ```json ... ``` ` / ` ``` ... ``` ` biçimleri
  aynı şekilde ayrıştırılmalı.
- Fence dışındaki preamble/postamble ve kesilmiş-array salvage davranışı
  korunmalı.
- GUI ve hybrid yardımcıları aynı vaka tablosuyla test edilmeli; mümkünse ortak
  saf yardımcıya yönlendirilmeli.

### 42. Geri-çeviri otomatik düzeltmeleri SRT'ye kalıcı yazılmıyor

**Öncelik:** P1  
**Dosya:** `subtitle_translator_gui.py`, `_maybe_backtranslation_check` ve dört
çağrı noktası

Birden fazla akışta `write_srt()` önce çağrılıyor, ardından
`_maybe_backtranslation_check()` kendisine verilen mutable `blocks` listesini
değiştiriyor. Böylece rapor “düzeltildi” diyebiliyor ve bazı akışlarda düzelmiş
metin TM'ye kaydediliyor, fakat diskteki SRT eski metni taşımaya devam ediyor.
Resume yolunda çağrı sırası farklı olduğundan düzeltme ne mevcut SRT'ye ne de
önceden yazılmış TM çiftine yansıyabiliyor.

**Kabul ölçütleri:**

- Geri-çeviri helper'ı değişen blokları ve düzeltme sayısını açıkça döndürmeli.
- Kabul edilen düzeltmelerden sonra son etiket/merge sırası korunarak SRT tam
  bir kez nihai bloklarla yazılmalı.
- TM, rapor ve diskteki SRT aynı nihai metni görmeli.
- Düz sync, düz batch/resume, sync-hybrid ve hybrid-batch için sıra/parite
  regresyonları eklenmeli.
- Tag-sarmalı satırda helper etiketi düşürse bile gerçek metin güvenli
  doğrulanıp kaynak format etiketi tekrar uygulanabilmeli; genel polish
  validator'ının tag güvenliği gevşetilmemeli.

### 43. Çekirdek snapshot düzeltmesine rağmen yardımcı worker yolları hâlâ Tk değişkenleri okuyor

**Öncelik:** P1  
**Dosya:** `subtitle_translator_gui.py`

Ana çeviri worker'ları için `_active_snapshot` eklenmiş olsa da aşağıdaki
yardımcı/asenkron yollar doğrudan `StringVar.get()`/`BooleanVar.get()` veya
snapshot'a düşemeyen resolver çağrıları yapıyor:

- Test çevirisi worker'ı (`_test_translate._run`)
- Kaynak dil ve içerik türü preflight worker'ları
- Mevcut SRT post-process worker'ı
- Series-memory resolver ve bu yolların çağırdığı bazı helper/toggle okumaları

Preflight aşamasında `_active_snapshot` henüz oluşturulmadığından resolver
içindeki “worker ise snapshot kullan” koruması da yeterli değil.

**Kabul ölçütleri:**

- Worker başlamadan önce gerekli bütün Tk değerleri ana thread'de immutable bir
  iş tanımına/snapshot'a alınmalı.
- Worker fonksiyonları Tk widget/variable nesnelerine erişmemeli.
- Test translate, iki preflight ve post-process için “worker Tk `.get()` çağırmaz”
  regresyonları eklenmeli.
- Gerçek `App()` oluşturmadan saf/stub test tercih edilmeli.

### 44. Uygulama kapanırken log ve Translation Memory çalışan worker'la yarışabiliyor

**Öncelik:** P1  
**Dosyalar:** `subtitle_translator_gui.py`, `_on_close`;
`translation_memory.py`, `close`

Kullanıcı çalışan çeviri sırasında kapanışı onayladığında stop işareti
veriliyor, fakat worker'ın bitmesi beklenmeden `_tm.close()` ve
`_log_file.close()` çağrılıyor. Log dosyası `_log_lock` alınmadan; SQLite
bağlantısı ise kendi `RLock`'ı alınmadan kapatılıyor. Worker aynı anda yazıyorsa
son log/TM transaction'ı kaybolabilir veya kapalı kaynağa erişebilir.

**Kabul ölçütleri:**

- TranslationMemory `close()` aynı kilitle serileştirilmeli ve close sonrasında
  worker'ın bağlantıyı sessizce yeniden açması engellenmeli.
- Log kapatma/yazma aynı yaşam-döngüsü kilidi altında olmalı.
- Uygulama worker thread'lerini takip etmeli; kapanışta sınırlı ve UI'yi
  dondurmayan bir drain/join politikası kullanılmalı.
- Kapanış sırasında devam eden log ve TM yazımını kontrollü event/barrier ile
  yeniden üreten testler eklenmeli.

### 45. Hybrid-batch Faz 2 dosyaları arasında Duraklat kontrol noktası yok

**Öncelik:** P1  
**Dosya:** `subtitle_translator_gui.py`, `_run_hybrid`

Faz 2, `submitted` dosyalarını sırayla bekleyip yazıyor; dosya tamamlandıktan
sonra diğer ana akışlardaki `_wait_between_files()` kontrolünü çağırmıyor.
Kullanıcı “Duraklat”a bastığında log “mevcut dosya bitince duracak” dese de
hybrid-batch sonuç işleme bir sonraki dosyaya geçebiliyor.

**Kabul ölçütleri:**

- Her Faz 2 dosyasının tamamlanma/başarısızlık sınırında, son dosya hariç,
  `_wait_between_files(si, n_sub, fname)` uygulanmalı.
- Duraklat sırasında uzak batch durumları veya recovery metadata kaybedilmemeli.
- Stop, pause→continue ve son dosyada beklememe senaryoları test edilmeli.

### 46. `write_srt` hedef dil Türkçe değilken de Türkçe local fix ve etiket normalizasyonu uyguluyor

**Öncelik:** P1  
**Dosya:** `subtitle_translator_gui.py`, `write_srt`

Serileştirici hedef dilden habersiz biçimde her metne
`hybrid_translate._apply_local_fixes`, `normalize_turkish_artifacts`,
Türkçe SDH descriptor ve Türkçe speaker-label dönüşümleri uyguluyor. Kullanıcı
hedef dili İspanyolca, İtalyanca veya başka bir dil seçtiğinde doğru hedef
metin kısmen Türkçeleştirilebilir. Bu, yalnız “İngilizce kalite pass çıktısı”
değil; bütün Türkçe-dışı hedefler için akış seviyesinde bir sorundur.

**Kabul ölçütleri:**

- Genel SRT serileştirme ile Türkçe-hedef normalizasyonu ayrılmalı.
- Türkçe özel local fix/artefact/speaker dönüşümleri yalnız hedef dil gerçekten
  Türkçe olduğunda çalışmalı.
- Tüm çağrı yolları hedef dili açıkça taşımalı veya serileştirmeden önce
  hedefe-özel finalize adımı uygulamalı.
- Türkçe davranışı korunurken en az İngilizce, İspanyolca ve İtalyanca hedef
  örnekleri Türkçeleştirilmeden yazılmalı.

### 47. Ana ve genel-helper API alanını boşaltmak eski credential'ı silmiyor

**Öncelik:** P1  
**Dosya:** `subtitle_translator_gui.py`, `_save_settings`

Role-specific ve main-custom anahtarlar boşsa `delete_key()` çağrılıyor. Buna
karşın ana `openai` ve genel `openai_helper` alanları yalnız doluysa
`save_key()` çağırıyor; kullanıcı alanı temizleyip kaydettiğinde eski secret
Windows Credential Manager/fallback store içinde kalıyor ve sonraki açılışta
yeniden yüklenebiliyor.

**Kabul ölçütleri:**

- Boş ana OpenAI ve genel helper alanı ilgili credential slotunu silmeli.
- `_helper_keys_cache` de silinen genel anahtarı taşımaya devam etmemeli.
- Kaydet→temizle→yeniden yükle döngüsü gerçek credential backend'i çağırmadan
  mock ile test edilmeli.
- Başka provider/role credential'ları yanlışlıkla silinmemeli.

### 48. Kaynak speaker-label regex'i `CHAPTER 1:` gibi ekran başlıklarını konuşmacı sanıyor

**Öncelik:** P1  
**Dosya:** `sdh_cleaner.py`, `_SRC_PLAIN_SPEAKER_LABEL_RE`,
`strip_labels_by_source`

Kaynak satırın başındaki 2–31 karakterlik büyük-harf+dijit etiketi konuşmacı
sayılıyor. `CHAPTER 1:`, `BREAKING NEWS:` veya benzeri gerçek ekran başlığı
eşleştiğinde çeviri tarafındaki `BÖLÜM 1:`/başlık prefix'i speaker etiketi gibi
silinerek içerik kaybı oluşabilir.

**Kabul ölçütleri:**

- Speaker kararı yalnız casing regex'ine dayanmamalı; bölüm, haber, konum,
  tarih/saat ve ekran başlığı biçimleri korunmalı.
- Gerçek `JOHN:`, `DR. SMITH:` ve kaynak-güdümlü speaker temizliği korunmalı.
- `CHAPTER 1: The Beginning`, `BREAKING NEWS: Markets Fall` ve gerçek speaker
  örnekleri birlikte test edilmeli.

### 49. Sync moda geçiş hybrid'i zorla açarken karşılıklı toggle durumunu tamamlamıyor

**Öncelik:** P2  
**Dosya:** `subtitle_translator_gui.py`, `_on_mode_change`

Sync seçildiğinde hybrid kapalıysa kod `hybrid_var.set(True)` ve
`hybrid_frame.grid()` yapıyor, fakat `_toggle_hybrid()` çağırmıyor. Bu nedenle
ön-bağlam kapatılıp devre dışı bırakılmıyor ve helper-role kontrolleri aynı
state'e senkronlanmıyor. Kullanıcı arayüzü iki karşılıklı dışlanan özelliği aynı
anda açık gösterebilir.

**Kabul ölçütleri:**

- Programatik hybrid değişimi kullanıcı toggle'ıyla aynı tek state-transition
  yolunu kullanmalı.
- Sync/batch geçişleri, precontext ve helper görünürlüğü için state-table testi
  eklenmeli.

### 50. Token tahmini hatasında arayüz sonsuza kadar “hesaplanıyor” kalıyor

**Öncelik:** P2  
**Dosya:** `subtitle_translator_gui.py`, `_estimate_async`

`estimate_tokens()` exception verirse worker yalnız `return` ediyor. UI'ye hata
veya önceki/geçerli dosya sayısını geri yazmadığı için bilgi satırı
“token hesaplanıyor…” durumunda kalıyor.

**Kabul ölçütleri:**

- Hata ana thread'e güvenli bir UI callback'iyle yansıtılmalı.
- Dosya sayısı korunmalı; token tahmininin yapılamadığı açıkça belirtilmeli.
- Exception ve kapanış sırasında callback düşürme senaryoları test edilmeli.

### 51. Bozuk ve eksik hybrid fmap aynı `None` sonucu ve aynı teşhisi üretiyor

**Öncelik:** P2  
**Dosyalar:** `hybrid_translate.py`, `load_fmap_for_batch`;
`subtitle_translator_gui.py`, hybrid recovery yolu

Fmap dosyasının bulunmaması, okunamaması, bozuk JSON olması ve beklenen `fmap`
şemasının bulunmaması aynı `None`/boş sonuçta birleşiyor. Recovery kullanıcıya
yalnız “eşleme yok/boş” diyor; otomatik onarım veya güvenli iptal kararı için
dosyanın eksik mi bozuk mu olduğu bilinmiyor.

**Kabul ölçütleri:**

- Loader en az `missing`, `invalid_json`, `invalid_schema` ve geçerli-boş
  durumlarını ayırt edilebilir biçimde raporlamalı.
- Batch ID ve güvenli dosya yolu dışında fmap içeriği loga dökülmemeli.
- Bozuk fmap silinmemeli; kullanıcı/onarım aracı için korunmalı.

### 52. Generic SDH sınıflandırıcısı yaygın sıfat+isim ve bare-verb ses etiketlerini kaçırıyor

**Öncelik:** P2  
**Dosya:** `sdh_cleaner.py`, `is_sdh_descriptor`, `_SDH_ACTION_VERBS`

Mevcut sınıflandırıcı `[glass breaking]` gibi eylem-sonlu örnekleri yakalıyor,
fakat `[loud crash]`, `[door slam]`, `[glass breaks]` gibi yaygın ses
açıklamalarında son kelime ne keyword ne de desteklenen action biçimi olduğunda
etiketi koruyabiliyor. Source-driven ana üretim yolu birçok bracket vakasını
yapısal olarak temizlediği için rapordaki “her akışta kritik” değerlendirmesi
abartılıdır; generic/post-process/fallback davranışı yine de eksiktir.

**Kabul ölçütleri:**

- Yaygın ses eylemlerinin yalın, üçüncü-tekil ve `-ing` biçimleri kontrollü
  biçimde tanınmalı.
- `[Soft Power]`, `[Breaking News]`, `[Chapter One]` gibi anlamlı başlıklar
  yanlışlıkla SDH sayılmamalı.
- Pozitif ve negatif vaka tablosu source-driven ve generic yollar için ayrı
  test edilmeli.

---

## Önerilen doğrulama sırası

1. Her bug için en küçük hedefli `unittest`.
2. Değişen modüller için:
   `python -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py helper_models.py credential_store.py translation_memory.py`
3. İlgili yakın test modülleri.
4. Gerçek çeviri çalışmadığı kesin ise:
   `python -m unittest discover -s tests`
5. GUI değişikliği varsa ve uygulama/çeviri kapalıysa AGENTS.md'deki headless
   `App()` smoke testi.

Tamamlandığında her madde için şu formatta rapor ver:

- Düzeltilen bug numarası
- Kök neden
- Değişen dosyalar
- Eklenen regresyon testi
- Çalıştırılan testler ve sonuçları
- Commit hash
