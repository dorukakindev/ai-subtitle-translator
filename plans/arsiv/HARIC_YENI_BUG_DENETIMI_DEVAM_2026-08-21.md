# Hariç Tutulan Raporların Dışında Yeni Bug Denetimi — Devam

**Tarih:** 2026-08-21  
**Doğrulanan sürüm:** `9b860e6`  
**Çalışma biçimi:** Salt okunur kod denetimi ve saf/geçici dosyalı karşı örnekler. API çağrısı yapılmadı, GUI `App()` oluşturulmadı, üretim kodu/testleri değiştirilmedi.

## Dışlama tabanı

Bu devam raporu aşağıdaki belgelerdeki maddeleri ve bunların şu anda uygulanmakta olan düzeltmelerini yeniden raporlamaz:

- `C:\Users\K\Desktop\ALTYAZI_CEVIRI_TUM_BUGLAR_VE_DUZELTME_REHBERI.md` — 71 başlık
- `C:\Users\K\Desktop\YENI_DERIN_BUGLAR_VE_DUZELTME_REHBERI.md` — 48 başlık
- `DERIN_BUG_DENETIMI_2026-08-20.md` — 48 başlık
- `HARIC_YENI_BUG_DENETIMI_2026-08-21.md` — 39 başlık

Toplam 206 eski başlık, yalnız başlığı farklı olduğu için yeniden sayılmadı. Aynı kök nedenin başka belirtisi bu rapora alınmadı. Aşağıdaki altı bulgunun her biri güncel kodda ayrıca yeniden üretildi.

## Özet

| No | Öncelik | Alan | Kısa sonuç |
|---:|:---:|---|---|
| 1 | P1 | Kaynak metin temizliği | `<br>` ve inline VTT zaman etiketleri iki ayrı sözcüğü API'ye gitmeden birleştiriyor |
| 2 | P2 | Görünür-anlam / teslim kapısı | `{username}` gibi gerçek yer tutucular ASS etiketi sanılıp boş çeviri sayılıyor |
| 3 | P2 | WebVTT / Unicode | Sayısal entity decoder surrogate kod noktası üreterek UTF-8 yazımını kırabiliyor |
| 4 | P1 | Hybrid Batch recovery | `submitted` batch sahipliği güncel kaynak hash'i ve yeni ayar fingerprint'iyle bağlanmıyor |
| 5 | P1 | Çevrilmemiş içerik denetimi | Kanıtsız “nakarat / alıntı / özel ad” muafiyetleri gerçek İngilizce replik ve tabelaları hazır sayıyor |
| 6 | P1 | `YÜKLEMEYE HAZIR` işareti | `output_path` oluşmamış başarısız dosya klasörün hazır kararına hiç katılmıyor |

---

## Doğrulanmış yeni bulgular

## 1. `<br>` ve inline VTT zaman etiketleri kaynak sözcükleri birbirine yapıştırıyor

**Kod:**

- `subtitle_formats.py:21-24` — `_SOURCE_HTML_TAG`, `br` etiketini tanıyor
- `subtitle_formats.py:128-141` — `clean_translation_source_text`, etiketi ve inline VTT zamanını boş dizeyle siliyor
- `hybrid_translate.py:331` ve `subtitle_translator_gui.py:6964` — aynı temizleyici hybrid ve normal request yollarında kullanılıyor

**Kök neden:** Görsel biçim etiketi ile sözcük ayıran yapısal etiket aynı silme davranışını kullanıyor. `<i>` kabuğunu boş dizeyle kaldırmak doğrudur; fakat `<br>` ve `<00:00:01.000>` iki metin parçası arasında gerçek sınırdır. Bu sınır boş dizeye dönünce komşu sözcükler birleşir.

**Saf karşı örnek — güncel çıktı:**

```text
clean_translation_source_text('Wait<br/>here.')
  -> 'Waithere.'

clean_translation_source_text('Hello<00:00:01.000>world')
  -> 'Helloworld'
```

**Etki:** Model `Wait here` yerine sözlükte bulunmayan `Waithere`, `Hello world` yerine `Helloworld` görür. Bu, çeviri sonrası bir kozmetik sorun değildir; normal ve hybrid ana çevirinin ortak kaynak metni API çağrısından önce bozulur. Özel ad, terim, fragment ve bağlam analizi de aynı bozuk tokenı kullanabilir.

**Neden eski HTML-tag maddesi değil:** Eski madde, bilinmeyen `<Enter>`/`<x>` benzeri anlamlı içeriğin etiket sanılıp tamamen silinmesiydi. Burada etiket gerçekten desteklenen `<br>` veya VTT zaman etiketidir; hata tanıma kapsamı değil, **ayırıcı etiketin boş dizeye çevrilmesidir**.

**Düzeltme ölçütü:** `<br>`, `<br/>`, `<br ...>` ve inline VTT zaman etiketleri önce tek bir boşluk veya korunacak satır sonuna dönüştürülmeli; ardından görsel kabuklar temizlenmelidir. İşlem çift boşluk üretmemeli ve gerçek kelime içi `<i>...</i>` sarmalamasını bozmamalıdır.

**Kabul testleri:** Yukarıdaki iki örnek sırasıyla `Wait here.` ve `Hello world` olmalı; hem `build_requests` hem `ht.build_batch_requests` payload'ında birleşik token bulunmamalıdır.

---

## 2. Literal süslü-parantez yer tutucuları “görünmez biçim” sayılıp boş hedefe dönüşüyor

**Kod:**

- `subtitle_formats.py:1027-1036` — ASS temizliği `{username}` gibi şablon yer tutucularını özellikle koruyor
- `subtitle_formats.py:1467-1507` — `_VISIBLE_MARKUP_RE`, buna karşılık **her** `{...}` bloğunu görünmez sayıyor
- `translation_memory.py:156-166` — aynı karar TM kayıt kapısına taşınıyor
- `subtitle_translator_gui.py:13701,13723,14048,14062,15499` — eksik sayımı, skip/recovery ve teslim denetimleri aynı sonucu kullanıyor

**Kök neden:** Ortak görünür-anlam regex'i, geçerli ASS override komutu ile literal SRT/VTT metni arasında ayrım yapmıyor:

```python
_VISIBLE_MARKUP_RE = re.compile(r"</?[a-zA-Z][^>]*>|\{[^{}]*\}")
```

Oysa parser/temizleyici katmanının güncel ve testli sözleşmesi `{username}`, `{red}` gibi içerikleri korumaktır; yalnız `{\an8}`, `{\i1}` gibi gerçek ASS override blokları görünmezdir.

**Saf karşı örnek — güncel çıktı:**

```text
visible_semantic_text('{username}')
  -> ''

translation_failure_reason('{username}', source='{username}')
  -> 'bos_hedef'

visible_semantic_text('{\an8}')
  -> ''        # bu kısım doğru davranış
```

**Etki:** Yalnız bir şablon değişkeni, renk anahtarı veya oyundaki literal komuttan oluşan geçerli cue:

- eksik/boş çeviri sayılabilir,
- gereksiz hedefli onarıma veya partial akışına düşebilir,
- TM'ye kaydedilmeyebilir,
- nihai teslim denetiminde karantinaya alınabilir.

**Neden eski biçim-içine-sarılmış `[HATA]` maddesi değil:** Eski hata, `<i>[HATA]</i>` gibi marker'ların biçim etiketi yüzünden görünmemesiydi. Güncel ortak katman bunu çözmüş; buradaki yeni kök neden çözüm regex'inin gerçek literal veriyi de markup sanacak kadar geniş olmasıdır.

**Neden eski ASS yorum maddesi değil:** Önceki rapordaki `{TL Note: ...}` / `{Scene 2}` bulgusu yalnız ASS/Aegisub içi görünmez yorumların parser'da temizlenmesiyle ilgilidir. Buradaki karşı örnek SRT/VTT'de ekranda gerçekten görünen `{username}` benzeri içeriktir; format bilgisi kaybolduktan sonra çalışan ortak `visible_semantic_text` katmanı bunu koşulsuz olarak görünmez saymaktadır. ASS yorum temizliği daraltılsa veya genişletilse bile SRT/VTT karşı örneği bağımsız olarak sürer.

**Düzeltme ölçütü:** Görünür katman yalnız desteklenen HTML kabuklarını ve sözdizimsel olarak gerçek ASS override bloklarını (`{\...}`) çıkarmalıdır. `{username}`, `{red}`, `{1,2,3}` görünür kalmalı; gerçek ASS comment politikasına ihtiyaç varsa format bilgisi olmadan bütün süslü parantezler silinmemelidir.

**Kabul testleri:** Literal yer tutucular `translation_failure_reason == ''` vermeli ve TM/teslim kapılarından geçmeli; `{\an8}`, `<i></i>` ve `<i>[HATA]</i>` için mevcut hata testleri aynen korunmalıdır.

---

## 3. WebVTT sayısal entity decoder geçersiz Unicode surrogate üretebiliyor

**Kod:**

- `subtitle_formats.py:834-866` — `_VTT_ENTITY_RE`, `decode_vtt_entities`
- `subtitle_formats.py:1262` civarı — çözülen değer `parse_vtt` cue metnine giriyor

**Kök neden:** Sayısal karakter referansı için tek sınır `0 < code <= 0x10ffff`. Unicode surrogate aralığı (`U+D800–U+DFFF`) ve noncharacter değerleri elenmiyor. Python `chr(0xD800)` ile surrogate taşıyan bir `str` üretebilir; fakat bu değer geçerli UTF-8'e yazılamaz.

**Saf karşı örnek — güncel çıktı:**

```text
decode_vtt_entities('&#xD800;')  -> '\ud800'
decode_vtt_entities('&#xFFFE;')  -> '\ufffe'
decode_vtt_entities('&#x1F600;') -> geçerli U+1F600
decode_vtt_entities('&#X1F600;') -> literal kalıyor

'Hello \ud800 world'.encode('utf-8')
  -> UnicodeEncodeError: surrogates not allowed
```

**Etki:** Bozuk veya kötü üretilmiş tek bir WebVTT entity'si parser'dan geçip prompt JSONL'i, logu, cache'i ya da nihai SRT'nin UTF-8 atomik yazımını kırabilir. Hata dosyanın çok sonraki aşamasında görülebileceği için kullanıcı bunu VTT entity kaynağıyla ilişkilendiremez; öncesinde API harcaması yapılmış olabilir.

**Neden eski “VTT entity hiç çözülmüyor” maddesi değil:** Eski madde geçerli `&amp;`, `&nbsp;`, `&lrm;` değerlerinin literal kalmasıydı. Güncel decoder bunları çözüyor. Buradaki yeni açık, **sayısal decoderın geçersiz Unicode scalar değerini kabul etmesi** ve yazılamaz Python metni üretmesidir.

**Düzeltme ölçütü:** NUL, disallowed kontrol değerleri, surrogate aralığı, `> U+10FFFF` ve Unicode noncharacter değerleri WebVTT/HTML karakter referansı politikasına göre reddedilmeli veya `U+FFFD` ile değiştirilmelidir. Büyük `X` kullanılan hex biçimi de aynı politikaya girmelidir.

**Kabul testleri:** Decimal ve hex surrogate/noncharacter girdileri nihai Python stringinde surrogate bırakmamalı; çıktı UTF-8'e kodlanabilmeli; geçerli BMP ve astral örnekler korunmalıdır.

---

## 4. Hybrid Batch `submitted` kaydı güncel kaynak ve ayar sahipliğini kaybedebiliyor

**Kod:**

- `hybrid_translate.py:1311-1356` — `_recover_submitted_batch_links`
- `hybrid_translate.py:1393-1396,1411-1430` — mevcut oturumda fingerprint/source değişimi
- `hybrid_translate.py:1447-1452` — fingerprint değişince eski `submitted` girdisinin yeni oturuma kopyalanması
- `hybrid_translate.py:1462` — fmap üzerinden yeniden bağlama
- `subtitle_translator_gui.py:38330-38366` — yeniden bağlanan fmap yalnız istek haritası olarak yükleniyor
- `subtitle_translator_gui.py:39175-39185` — source drift ancak bütün bekleme/post-passlerden sonra son yazım kapısında kontrol ediliyor

**Kök neden:** `completed` girdi için kaynak hash'i yeniden hesaplanıyor; `submitted` girdi için aynı kontrol yok. Üç ayrı yol eski uzaktan işi güncel çalışma gibi sahiplenebiliyor:

1. Aynı session fingerprint'inde kaynak dosya değişse bile `submitted` giriş olduğu gibi korunuyor.
2. Ayar fingerprint'i değiştiğinde yeni session oluşturuluyor; fakat eski session'daki `submitted + batch_id` doğrudan yeni session'a kopyalanıyor.
3. `_recover_submitted_batch_links`, fmap `source_hash` değerini güncel dosya/session hash'iyle karşılaştırmadan `pending` girdiyi tekrar `submitted` yapıyor.

**Geçici dosyalı karşı örnekler — güncel çıktı:**

```text
session: pending, source_hash=NEW_HASH
fmap   : same path/fingerprint, source_hash=OLD_HASH, batch_old123

_recover_submitted_batch_links(...)
  -> recovered=1
  -> status='submitted', batch_id='batch_old123'
  -> session source_hash hâlâ NEW_HASH
```

Fingerprint değişimi örneği:

```text
old session fingerprint = OLD_SETTINGS
old entry = submitted / batch_123
create_batch_session(... fingerprint=NEW_SETTINGS)
  -> yeni session entry yine submitted / batch_123
```

**Etki:**

- Kaynak değişmişse son yazım guard'ı eski hash'i en sonunda yakalayabilir; fakat uzaktaki sonucu bekleme/indirme ve Critic/terim/semantic gibi ücretli post-passler bundan önce çalışabilir ve boşa harcanabilir.
- Hedef dil, model, stil, şema, glossary veya pass ayarları değişmişse kaynak hash'i aynı kalır. Eski ayarlarla oluşturulmuş batch sonucu güncel `tgt` ve güncel post-pass ayarları altında yazılabilir; session bunu yeni ayar oturumunun işi gibi raporlar.

**Neden eski fingerprint/recovery maddeleri değil:** Önceki raporlar tamamlanmış final/partial dosyanın kaynak fingerprint'i, output yolu ve checkpoint payload'ını kapsıyordu. Burada henüz sonuçlanmamış **uzak `submitted` işinin sahipliği** yeni session'a taşınırken kaynak+ayar kimliği kayboluyor.

**Düzeltme ölçütü:** Bir remote batch yalnız şu kanıtların tamamı aynıysa yeniden bağlanmalıdır:

- fmap `session_fingerprint` == güncel session fingerprint,
- fmap `source_hash` == session entry source hash == diskteki güncel kaynak SHA-256,
- kaynak yolu/çıktı yolu ve request sahipliği geçerli,
- hedef/model/şema gibi batch üretim ayarları fmap/run context ile güncel snapshot'a eşit.

Fingerprint değişmiş eski `submitted` iş yeni session'ın current girdisi yapılmamalı; ayrı orphan/review/cancel kaydı olarak korunmalıdır. Source drift, API/post-pass başlamadan önce kontrol edilmelidir.

**Kabul testleri:** (1) aynı fingerprint + değişmiş kaynak, (2) aynı kaynak + değişmiş hedef/model, (3) fmap eski hash + session yeni hash senaryolarının üçünde de eski batch yeniden bağlanmamalı; eşleşen gerçek crash-resume yine tek batch'e bağlanmalıdır.

---

## 5. Kanıtsız “yabancı ifade” muafiyetleri gerçek İngilizce içeriği çevrilmiş sayıyor

**Kod:**

- `subtitle_translator_gui.py:12135-12145` — `_repeated_foreign_refrain_word`
- `subtitle_translator_gui.py:12291-12297` — kalite taramasında tekrar eden kelime muafiyeti
- `subtitle_translator_gui.py:15298-15318` — tırnaklı yabancı referans muafiyeti
- `subtitle_translator_gui.py:15330-15341` — Title Case satırı özel ad sayma
- `subtitle_translator_gui.py:15363-15370` — nihai delivery untranslated kapısından toplu muafiyet

**Kök neden:** Bir ifadenin gerçekten yabancı nakarat, eser adı veya korunacak özel ad olduğuna dair pozitif kanıt aranmıyor. Yalnız biçim kullanılıyor:

- aynı Latin kelimesinin iki kez yazılması,
- İngilizce cümlenin tırnak içine alınması,
- iki veya daha fazla Title Case kelime.

Küçük bir yaygın-fiil blacklist'i dışında her kelime “yabancı nakarat” olabilir. Teslim fonksiyonu locked glossary, içerik türü, şarkı işareti, kaynak dil içi yabancı-dil bağlamı veya özel-ad analizi almıyor.

**Saf karşı örnek — güncel nihai denetim sonucu:**

```text
Kaynak == hedef         delivery untranslated ID
-------------------------------------------------
Danger danger          []
Fire fire              []
Freedom freedom        []
Money money            []
"Danger!"              []
"Fire!"                []
Fire Exit              []
Emergency Exit         []
Danger Ahead           []
```

Aynı helper `Help help` ve `Go go` için blacklist nedeniyle ID döndürüyor; yani karar semantik kanıttan değil elle yazılmış birkaç sözcükten oluşuyor. `Bamboleo bamboleo` gibi gerçek olası nakaratla `Danger danger` arasında veri temelli ayrım yok.

**Etki:** Gerçek İngilizce replik, slogan veya tabela Türkçeye hiç çevrilmeden finalde kalabilir. `Danger danger` kalite taramasında da muaf olduğu için uyarı bile üretmez. `Fire Exit` gibi Title Case tabela kalite raporunda görünse dahi sert teslim kapısında muaf kalabilir; dosya source fingerprint ve hazır işareti alabilir.

**Neden eski “İngilizce kalıntı” yanlış pozitif maddeleri değil:** Eski düzeltmeler gerçek kişi adı, URL, teknik terim veya kaynakta kanıtlı yabancı alıntının yanlış uyarılmasını azaltıyordu. Buradaki yeni kök neden, bu istisnaların **pozitif kanıt olmadan sıradan İngilizce içerik sınıflarına genişletilmesi** ve gerçek false-negative üretmesidir.

**Düzeltme ölçütü:** Muafiyet yalnız pozitif kanıtla verilmeli: locked/analysis terimi, doğrulanmış kişi/yer adı, açık şarkı/nakarat bağlamı, kaynak dil içinde başka dil etiketi veya komşu cue'da alıntı açıklaması. Sırf tekrar, tırnak veya Title Case yeterli olmamalı. Belirsiz içerik en azından report-only şüphe olarak kalmalı; upload-ready hard gate'ten sessiz geçmemelidir.

**Kabul testleri:** Yukarıdaki İngilizce örneklerin tamamı Türkçe hedefte şüpheli/çevrilmemiş sayılmalı; `New York`, locked `Bureau International des Poids et Mesures` ve kaynakta gerçek yabancı nakarat kanıtı bulunan örnekler korunmalıdır.

---

## 6. `output_path` oluşmamış başarısız dosya, klasörün upload-ready kararına hiç katılmıyor

**Kod:**

- `subtitle_translator_gui.py:13477-13513` — `upload_ready_marker_plan`
- `subtitle_translator_gui.py:13516-13545` — marker yazma/silme

**Kök neden:** Plan her run dosyasını dolaşıyor; fakat `state.output_path` boşsa doğrudan `continue` ediyor:

```python
output_value = str((state or {}).get("output_path") or "").strip()
if not output_value:
    continue
```

Bu dosya `status='error'` veya `partial` olsa bile hangi final klasörünü bloklaması gerektiği hesaplanmıyor. Run-level başarısızlık da hazır kararına katılmıyor.

**Geçici klasörlü saf karşı örnek — güncel çıktı:**

```text
aynı output klasöründe:
  A.srt -> status=done, output_path=A.tr.srt, provenance doğrulandı
  B.srt -> status=error, output_path=''

upload_ready_marker_plan(record)
  -> ready = {klasör: [('A.tr.srt', 'abc')]}
  -> stale = []
```

Yalnız başarısız/no-output dosya bulunan eski bir klasörde ise plan ne `ready` ne `stale` üretir; önceden kalmış `YÜKLEMEYE HAZIR.txt` kaldırılmayabilir.

**Etki:** Çok dosyalı aynı film/dizi tesliminde bir dosya daha output yolu oluşmadan çökerken diğer dosya başarılıysa klasör yine hazır işareti alabilir. Kullanıcı marker'a bakarak bütün klasörü tamamlanmış sanabilir. Bu doğrudan operasyonel yanlış-onaydır; dosya hash'i doğrulaması tek başarılı final için doğru olsa bile klasörün bütünlüğü yanlıştır.

**Neden eski marker maddeleri değil:** Eski maddeler marker'ın hiç üretilmemesi ve üretilen marker'ın output hash'ini doğrulamamasıydı. Güncel kod marker'ı doğru ad/yerde üretip var olan final hash'ini doğruluyor. Buradaki açık **henüz output yolu olmayan başarısız run üyesinin klasör toplulaştırmasından tamamen düşmesidir**.

**Düzeltme ölçütü:** Her non-done run üyesi için beklenen output yolu aynı resolver/snapshot ile hesaplanmalı veya run başında intended output klasörü kayda yazılmalıdır. Bir klasöre ait tek bir error/partial/review/pending dosya varsa o klasör ready listesinden çıkarılmalı ve eski marker silinmelidir. Run-level terminal durum da `done` değilse marker oluşturulmamalıdır.

**Kabul testleri:**

1. Aynı klasörde `done + error(output_path='')` → marker yok, eski marker stale.
2. Yalnız `error(output_path='')` → eski marker silinir.
3. İki ayrı klasörde biri tam, biri başarısızsa politika gerçekten klasör bazlıysa yalnız tam klasör marker alır.
4. Bütün üyeler done + provenance/output hash doğrulanmışsa mevcut marker davranışı korunur.

---

## Yanlış alarm / dışlama olarak elenenler

- **ProjectMemory'de `Memories/memories` ve `Şerif/Serif` çift anahtarları:** Güncel kodda yeniden üretilebiliyor; ancak kök neden önceki raporun Unicode/case canonical term identity maddesiyle aynıdır. Yeni başlık yapılmadı.
- **Aynı timestamp'li cue'ların `_source_map_for_quality_blocks` içinde ezilmesi:** Güncel fonksiyon hâlâ şüpheli görünse de önceki raporun 14. maddesinin doğrudan aynı kök nedenidir; yeniden sayılmadı.
- **Video cache'in örneklenmeyen bölgede değişikliği kaçırması:** Mevcut çoklu örnekleme olasılıksal kalır; fakat önceki video-cache fingerprint maddesinin aynı kök nedenidir.
- **Doğrudan `Raporlar\Kaynak` alt klasörünü input seçme:** Üretilmiş rapor/kaynak ağacının yeniden yutulması başlığıyla aynı discovery köküne girer; ayrı bug yapılmadı.
- **Eski source-only fingerprint sidecar'ın output hash'i olmadan kabul edilmesi:** Önceki output-fingerprint maddesinin backward-compatibility artığıdır; yeni kök neden sayılmadı.
- **Dosya başına Gelişmiş/Maksimum ayarının raw path anahtarı:** Normal UI/snapshot/resume yollarında seçilen path yazımı korunuyor; gerçek production drift zinciri kanıtlanmadığı için rapora alınmadı.
- **FFmpeg işinde anlık iptal bulunmaması:** Statik olarak doğru; fakat önceki “background preflight cancellation” kökünden yeterince bağımsız bir veri/çeviri bozulması karşı örneği üretilmedi. Spekülatif madde eklenmedi.

---

## Önerilen düzeltme sırası

1. **Madde 4:** Eski remote batch'in yeni kaynak/ayar oturumuna bağlanmasını kapat.
2. **Madde 1:** Ana modele giden kaynak metin birleşmesini düzelt.
3. **Madde 5:** Gerçek İngilizce içeriği upload-ready sayan muafiyetleri pozitif kanıta bağla.
4. **Madde 6:** Marker kararını klasördeki bütün intended run üyelerine bağla.
5. **Madde 2:** Literal `{...}` içeriği gerçek ASS override'dan ayır.
6. **Madde 3:** VTT numeric entity scalar doğrulamasını ekle.

## Asgari regresyon paketi

- `tests/test_subtitle_formats.py`: `<br>`/inline timestamp ayırıcıları, literal brace ve invalid numeric entity.
- `tests/test_haric_audit_*.py` veya yeni bağımsız modül: hybrid submitted source/settings ownership.
- `tests/test_run_log_regressions_20260821.py`: gerçek İngilizce tekrar/quote/Title Case false-negative örnekleri.
- `tests/test_upload_ready_finalization.py`: no-output başarısız run üyesiyle marker planı.
- Akış paritesi: normal sync, normal batch, sync-hybrid ve hybrid batch aynı kaynak-temizlik/görünür-anlam sözleşmesini kullanmalı.

## Denetim bütünlüğü

- API çağrısı: **yok**
- GUI `App()` oluşturma: **yok**
- Üretim kodu/test düzenlemesi: **yok**
- Commit: **yok**
- Değiştirilen tek dosya: bu Markdown raporu


---

## UYGULAMA DURUMU — 2026-08-21 (Claude Opus 5)

Altı maddenin **hepsi doğrulandı ve düzeltildi**; yanlış pozitif yok.
Yeni regresyon paketi: `tests/test_haric_audit_devam_20260821.py` (22 test).
Tam takım: **3978 test, hepsi geçiyor**; headless GUI smoke testi temiz.

| # | Konu | Düzeltme |
|---|------|----------|
| 1 | `<br>` / satır içi VTT damgası sözcükleri birleştiriyordu | `subtitle_formats._replace_word_separators` — `<br>` her zaman boşluk; inline VTT damgası YALNIZ iki sözcük karakteri arasındaysa boşluk (`<v Roger><00:00:01.500>Choose` sahte boşluk üretmesin diye) |
| 2 | Literal `{...}` metni 'boş hedef' sayılıyordu | `_VISIBLE_MARKUP_RE` artık yalnız `{\...}` biçimindeki gerçek ASS override bloğunu siliyor; `{username}`, `{red}` görünür içerik |
| 3 | Geçersiz sayısal varlık kodu çözülüyordu | `_valid_entity_codepoint` — surrogate, non-character, `\0` ve `0x110000` üstü kod noktaları literal kalıyor; `&#X...;` büyük harfli önek artık çözülüyor |
| 4 | Gönderilmiş batch'in sahipliği yalnız yola bakıyordu | üç yol da kaynak hash'i doğruluyor: bayat `fmap` yeniden bağlanmıyor, gönderimden sonra değişen kaynak batch'i bırakıyor (`orphan_batch_id` olarak kaydediliyor), ayar parmak izi değişince **ödenmiş** batch korunuyor ama `settings_fingerprint_changed` ile işaretlenip logda uyarı veriyor |
| 5 | Gerçek İngilizce içerik 'özel ad' sayılıp teslimden geçiyordu | `_has_non_ordinary_english_token` + `_src_is_proper_name_phrase` artık POZİTİF kanıt istiyor: bütün sözcükler bilinen sıradan İngilizceyse özel ad değil. `Fire Exit`, `Danger Ahead`, `Private Property` yakalanıyor; `New York`, `Baker Street`, `Göbekli Tepe` muaf kalıyor |
| 6 | Yolu hiç oluşmamış başarısız üye klasörü bloklamıyordu | `_intended_output_folder` ile hedef klasör hesaplanıp `stale`'e ekleniyor; ayrıca çalışmanın kendisi `done` değilse hiçbir işaret yazılmıyor |

### Madde 4'te denetimden sapma (bilinçli)

Rapor, ayar parmak izi değişen `submitted` işin "ayrı orphan/review/cancel
kaydı" olmasını istiyordu. Mevcut `test_settings_change_preserves_paid_
submitted_batch` testi bunun tersini **bilerek** kilitliyor: OpenAI Batch
işi ÖN ÖDEMELİDİR, bağlantı atılırsa kullanıcı aynı işi ikinci kez öder.
Bu yüzden bağlantı korunuyor ama entry `settings_fingerprint_changed` +
`origin_fingerprint` taşıyor ve batch akışı çalışma başında şu uyarıyı
veriyor: sonucun ESKİ ayarlarla üretildiği, yeni ayarlar isteniyorsa
'Yeniden Çevir' ile işaretlenmesi gerektiği. Sessiz yanlış atıf ortadan
kalkıyor, ödenmiş iş kaybolmuyor.

### Kayda değer iki ayrıntı

- Madde 1'in doğru yeri `visible_semantic_text` değil, modele giden metni
  üreten `clean_translation_source_text`; düzeltme oraya kondu.
- Madde 6'nın gerçek senaryosu, girdi ve çıktı klasörünün aynı olduğu
  (`<girdi>/ÇIKTI/`) yerleşim: bölümler tek klasöre yazıldığı için bir
  üyenin başarısızlığı bütün klasörü bloklar. Ayrı çıktı klasöründe her
  dosya kendi alt klasörüne gittiğinden blok yalnız kendi klasörünü etkiler.
