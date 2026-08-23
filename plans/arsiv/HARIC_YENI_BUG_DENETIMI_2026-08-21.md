# Hariç Tutulan Raporların Dışında Yeni Bug Denetimi

**Tarih:** 2026-08-21  
**Denetlenen sürüm:** `f9756f7`  
**İkinci tur yeniden doğrulama:** `ae7b570`  
**Altıncı tur yeniden doğrulama:** `cfb2d3d`  
**Yedinci tur yeniden doğrulama:** `b01d126`  
**Çalışma biçimi:** Salt okunur kod denetimi ve saf/geçici dosyalı karşı örnekler. API çağrısı yapılmadı, GUI `App()` oluşturulmadı, üretim kodu değiştirilmedi.

## Dışlama tabanı

Bu rapor aşağıdaki üç belgedeki maddeleri yeniden raporlamaz:

- `DERIN_BUG_DENETIMI_2026-08-20.md` — 48 başlık
- `C:\Users\K\Desktop\ALTYAZI_CEVIRI_TUM_BUGLAR_VE_DUZELTME_REHBERI.md` — 71 başlık
- `C:\Users\K\Desktop\YENI_DERIN_BUGLAR_VE_DUZELTME_REHBERI.md` — 48 başlık

Aynı kök nedenin farklı log belirtisi yeni bug sayılmadı. Aşağıdaki maddeler güncel HEAD üzerinde ayrıca yeniden üretildi ve dışlama belgelerinde bulunmayan bağımsız kabul/teslim/provenance sorunlarıdır.

## Özet

| No | Öncelik | Alan | Kısa sonuç |
|---:|:---:|---|---|
| 1 | P1 | Nihai teslim / TM | Etiket içine gizlenmiş hata, biçimden ibaret boş çıktı ve noktalama-only çıktı hazır sayılabiliyor |
| 2 | P1 | Kaynak temizleme | Gerçek `<Enter>`, `<x>` ve `<PRIVATE_PERSON>` içeriği API'ye gitmeden siliniyor |
| 3 | P1 | Çok dilli teslim | Doğru Arapça/Rusça/Japonca/Çince çıktı yabancı alfabe diye sert hataya düşüyor |
| 4 | P1 | Çok dilli teslim | Geçerli Fransızca `â/î/û` harfleri nihai denetimde sert hata sayılıyor |
| 5 | P1 | SRT yazımı | Bidi isolate, ZWNJ/ZWJ ve emoji birleştiricileri hedef dilden bağımsız siliniyor |
| 6 | P1 | Türkçe teslim | LSD/MDMA gibi kısaltmalar ve Roma rakamları son yazımda bozuluyor |
| 7 | P2 | Provenance / post-işlem | Final SRT yeniden adlandırılınca kaynak parmak izi ve kaynak resolver eşleşmesi kayboluyor |
| 8 | P2 | Teslim işareti | İstenen `YÜKLEMEYE HAZIR.txt` hiç üretilmiyor; farklı adla kaynak köküne işaret yazılıyor |
| 9 | P1 | WebVTT ayrıştırma | `&amp;`, `&lt;`, `&nbsp;` gibi WebVTT karakter varlıkları kaynak metinde ham kalıyor |
| 10 | P1 | Çeviri Belleği | Büyük/küçük harf ve satır yapısı farklı kaynaklar aynı exact-TM kaydına çarpışıyor |
| 11 | P1 | Biçim geri yükleme / teslim | Herhangi bir HTML etiketi finale geri yazılabiliyor ve audit bunu görmüyor |
| 12 | P1 | Kaynak dil tespiti | Dosya adı dil etiketi, gerçek diyalog dilini kontrol edecek AI analizini tamamen atlıyor |
| 13 | P1 | Aynı-klasör çıktı / tarama | VTT ve ASS finalleri sonraki taramada yeniden kaynak sayılıyor |
| 14 | P2 | Kalite ve satır-satır rapor | Aynı zaman damgalı ayrı cue'lar tek sözlük girdisinde birbirini eziyor |
| 15 | P1 | WebVTT zamanlama | `X-TIMESTAMP-MAP` medya ofseti yok sayıldığı için SRT zamanı kayabiliyor |
| 16 | P2 | Başlangıç / log rotasyonu | Tek bir kaybolmuş veya erişilemez log dosyası uygulama açılışını düşürebiliyor |
| 17 | P2 | Manuel post-işlem / rapor tarama | Tek bir kaybolmuş rapor dosyası kaynak çözümlemeyi ve o dosyanın post-işlemini düşürebiliyor |
| 18 | P1 | Kaynak arşivi / provenance | Aynı adlı kaynağın eski arşiv kopyası, güncel hash'li sürümden önce seçilebiliyor |
| 19 | P1 | ASS/SSA zamanlama | `[Script Info] Timer` çarpanı yok sayıldığı için bütün altyazı zamanları sistematik kayabiliyor |
| 20 | P1 | ASS görünürlük | Tamamen saydam stil veya `\\alpha&HFF&` ile gizlenen metin görünür diyaloğa dönüşebiliyor |
| 21 | P2 | ASS satır yapısı | Küçük `\\n`, WrapStyle 0/1/3'te boşluk olması gerekirken zorunlu satır sonuna çevriliyor |
| 22 | P1 | ASS vektör çizimi | `\\p1 ... \\p0` ile gerçek metni aynı event'te taşıyan cue'nun çizim koordinatları diyaloga karışıyor |
| 23 | P1 | Türkçe nihai normalizasyon | Eser/karakter adlarındaki `Mr.` ve `Miss` kaynak bağlamı olmadan `Bay`/`Bayan` yapılıyor |
| 24 | P1 | Kaynak kodlama | Geçerli Windows-1254 Türkçe SRT, içeriğe göre MacRoman veya CP1252/Latin-1 gibi yanlış açılabiliyor |
| 25 | P2 | SRT ayrıştırma | Milisaniyesiz veya 4+ kesir haneli SRT zamanları hiç cue üretmeden atlanıyor |
| 26 | P1 | Çeviri Belleği / analiz bağlamı | Dizi kanonu, proje ipucu veya Gelişmiş/Maksimum analiz değişse de TM anahtarı değişmiyor; eski çeviri modeli bypass ediyor |
| 27 | P2 | Gömülü altyazı seçimi | İlk İngilizce stream, forced/SDH/commentary niteliği bilinmeden varsayılan seçiliyor |
| 28 | P1 | Manuel JSONL / provenance | Başka filme ait JSONL, yalnız cue ID'leri uyuştuğu için seçilen kaynak SRT'ye uygulanıp denetimden geçebiliyor |
| 29 | P1 | Dizi Hafızası / Sezon Kanonu | Aynı dizinin ayrı bölüm klasörlerinden tek tek seçilen bölümleri farklı hafıza köklerine ayrılıyor |
| 30 | P2 | Kaynak keşfi | Meşru dil etiketli `movie.tr.srt`, program çıktısı sanılarak bütün taramalardan dışlanıyor |
| 31 | P1 | Çok dilli çıktı yolu | Çıktı resolver hedef dili hiç bilmiyor; aynı-klasörde yanlış `.tr.srt` etiketi, diğer modlarda diller arası üzerine yazma oluşuyor |
| 32 | P1 | Fuzzy Çeviri Belleği | Anlamı belirleyen virgül/noktalama farkı token guard'da yok sayılıyor; yanlış eski çeviri `%95+` eşleşmeyle modeli bypass ediyor |
| 33 | P1 | Manuel JSONL / eşzamanlılık | `JSONL → SRT` global çalışma sahipliği ve output baseline kilidini almadan API/post-pass/yazım başlatıyor |
| 34 | P1 | Exact Çeviri Belleği / yerel bağlam | Aynı dosyada farklı anlam taşıyan özdeş kaynak cue'lar tek TM anahtarına çöküyor; son çeviri bütün örneklere uygulanıyor |
| 35 | P1 | Proje ve dizi hafızası / sözlük | Baş harfi büyük sıradan kaynak sözcüklerindeki kimlik eşlemeleri özel ad sanılıp kalıcı “çevirme” kilidine dönüşebiliyor |
| 36 | P2 | Dizi Hafızası / Unicode kimliği | Görsel olarak aynı NFC/NFD dizi ve terim adları farklı kanon anahtarlarına ayrılıyor |
| 37 | P1 | SRT ayrıştırma / anlam-zaman sahipliği | Numaralı cue içindeki görünür zaman kodu satırı yeni cue sanılıp ardından gelen metin yanlış zamana taşınıyor |
| 38 | P1 | Kaynak-güdümlü SDH temizliği / çok dilli kaynak | Köşeli parantez içindeki Japonca, Kiril veya Arapça anlamlı ekran yazısı yalnız ASCII'ye indirgenemediği için SFX sanılıp tüm cue siliniyor |
| 39 | P1 | WebVTT ruby / kaynak anlamı | `<rt>` okunuş içeriği etiketiyle birlikte çıkarılmadığı için ana sözcüğe bitişiyor ve modele aynı ifadenin yazımı+okunuşu tek bozuk kelime olarak gidiyor |

---

## 1. Etiket içine gizlenmiş hata ve görünür anlamı olmayan hedef teslimden geçiyor

**Kod:**

- `subtitle_translator_gui.py:12755-12781` — `_count_hata_cps`, `_blocks_have_translation_failures`
- `subtitle_translator_gui.py:13052-13112` — `_existing_output_is_complete`
- `subtitle_translator_gui.py:14509-14511,14595-14597` — nihai audit marker denetimi
- `translation_memory.py:81-83` — `_is_missing_translation`

**Kök neden:** Hata/boşluk denetimleri görünür semantik metin üzerinde değil ham string üzerinde yapılıyor. `[HATA]` yalnız string başındaysa bulunuyor; HTML/ASS biçim etiketleri temizlenmeden kontrol ediliyor. Ayrıca hedefin gerçek bir sözcük taşıması istenmiyor, yalnız kaynak timestamp'inin bir output cue tarafından kullanılmış olması yeterli.

**Saf karşı örnek:** Kaynak cue `Hello.` iken aşağıdaki dört hedef ayrı ayrı yazıldı:

```text
<i>[HATA]</i>
<i></i>
...
—
```

Dördünde de güncel sonuç:

```text
_existing_output_is_complete = True
delivery audit status         = ok
hard error                    = False
```

`<i>[HATA]</i>` için `unresolved_markers=0` oldu. `_prepare_upload_ready_blocks` hata görmediği için Discord imzalarını da ekledi. Aynı ham-string politikası Translation Memory tarafında da bulunduğundan biçim içine sarılmış hata değeri TM'ye sağlıklı çeviri gibi girebilir.

**Etki:** Gerçek diyaloğu olmayan ya da açık hata taşıyan final `YÜKLEMEYE HAZIR` kabul edilebilir, sonraki çalıştırmada atlanabilir ve TM'yi zehirleyebilir.

**Düzeltme ölçütü:** Tek bir ortak `visible_semantic_text`/`translation_failure_reason` katmanı kullanılmalı. Güvenli HTML/ASS biçim etiketleri ve görünmez kontroller çıkarıldıktan sonra:

- hata marker'ı herhangi bir biçim sarmalamasında yakalanmalı,
- kaynak wordlike diyalogsa hedef de wordlike görünür içerik taşımalı,
- kaynak yalnız noktalama/nonverbal ise bu kural bağlama göre gevşetilmeli,
- aynı karar completion, delivery audit, partial partition ve TM store kapılarında kullanılmalı.

**Kabul testleri:** Yukarıdaki dört hedef, `Hello.` kaynağı karşısında hard failure olmalı; kaynak da `...` ise `...` hedefi yanlış pozitif üretmemeli.

---

## 2. Bilinmeyen açı-parantezli gerçek kaynak içeriği HTML etiketi sanılıp siliniyor

**Kod:** `subtitle_formats.py:15,83-95`

**Kök neden:** `_SOURCE_HTML_TAG = r'</?[a-zA-Z][^>]*>'` yalnız bilinen biçim etiketlerini değil, harfle başlayan her `<...>` parçasını HTML etiketi kabul ediyor.

**Saf karşı örnek:**

```text
Press <Enter> now.                    -> Press now.
The variable <x> is unknown.          -> The variable is unknown.
Send it to <PRIVATE_PERSON>.          -> Send it to .
<i>Hello.</i>                          -> Hello.
```

Son örnekte `<i>` temizliği doğru; ilk üçünde anlam taşıyan kaynak metin API isteği kurulmadan önce geri döndürülemez biçimde kayboluyor.

**Etki:** Klavye tuşları, matematik/değişken gösterimleri, redaksiyon placeholder'ları ve açı parantezli URL/kimlikler yanlış veya eksik çevrilir. Sonraki hiçbir pass silinen kaynağı göremez.

**Düzeltme ölçütü:** Silme, `i/b/u/font` ile gerçekten desteklenen VTT biçim etiketlerinin açık allowlist'ine bağlanmalı. Bilinmeyen `<NAME>`/`<x>`/`<Enter>` parçaları veri olarak korunmalı veya prompt için güvenli biçimde escape edilmelidir.

**Kabul testleri:** Yukarıdaki ilk üç kaynak byte-anlamını korumalı; `<i>Hello.</i>` görünür `Hello.` üretmeye devam etmelidir.

---

## 3. Doğru non-Latin hedefler nihai teslimde koşulsuz karantinaya düşüyor

**Kod:**

- `subtitle_translator_gui.py:1051-1055` — desteklenen hedef diller
- `subtitle_translator_gui.py:11333-11346` — `_foreign_script_ids`
- `subtitle_translator_gui.py:11525-11534` — genel kalite taraması
- `subtitle_translator_gui.py:14496,14612-14625,14667-14704` — delivery audit ve hard gate

**Kök neden:** `_foreign_script_ids` hedef dili almıyor. Arapça, Kiril, CJK ve diğer non-Latin karakterleri her durumda “Türkçe dışı alfabe” kabul ediyor. Aynı liste nihai audit'te hard error.

**Saf karşı örnek:** İngilizce `Hello.` kaynağı için doğru tek-cue hedef dosyaları yazıldı:

```text
Arabic  : مرحبا
Russian : Привет
Japanese: こんにちは
Chinese : 你好
```

Dördünün de sonucu:

```text
status             = review
foreign_script_ids = ["1"]
hard error         = True
```

**Etki:** Arayüzün açıkça sunduğu Arapça, Rusça, Japonca, Korece ve Çince hedefler doğru üretilse bile upload-ready olamaz. Bu, önceki raporlardaki “prompt Türkçeye sabitlenmiş” hatasından bağımsızdır: model kusursuz hedef metni döndürse dahi **son teslim kapısı** reddeder.

**Düzeltme ölçütü:** Script denetimi hedef dilin izinli yazı sistemine göre çalışmalı. Türkçe hedefte Arap/Kiril/CJK kalıntısı aranabilir; Rusça hedefte Kiril, Arapçada Arabic script, Japoncada Kana/Kanji, Çincede Han normal kabul edilmelidir. Karışık Latin özel adları ve sayılar da meşru olmalıdır.

**Kabul testleri:** Yukarıdaki dört örnek hard error üretmemeli; aynı karakterler Türkçe hedefte kaynakça izin verilmeyen sızıntıysa mevcut sert koruma sürmelidir.

---

## 4. Geçerli Fransızca şapkalı harfler hard error sayılıyor

**Kod:** `subtitle_translator_gui.py:14549-14550,14619-14625,14695-14697`

**Kök neden:** Nihai audit `âîûÂÎÛ` karakterlerini hedef dilden bağımsız sayıyor ve `hatted_letters` alanını doğrudan hard gate'e bağlıyor.

**Saf karşı örnek:** `write_srt(..., target_language="French")` ile doğru biçimde korunan:

```text
Grâce à lui. Âme sûre.
```

sonrasında:

```text
hatted_letters = 3
status          = review
hard error      = True
```

**Etki:** Fransızca hedefte `grâce`, `âme`, `sûr` gibi tamamen doğru kelimeler dosyayı karantinaya alır. Önceki rehberdeki “write_srt şapkalı harfi düzleştiriyor” maddesinden farklıdır: güncel writer hedef dili alıp harfi korusa bile **audit** doğru harfi reddediyor.

**Düzeltme ölçütü:** Şapkalı-harf teslim politikası yalnız Türkçe hedefte ve açık proje kuralı varsa uygulanmalı; Fransızca ve bu harfleri kullanan diğer hedeflerde sayım/hard gate kapalı olmalıdır.

**Kabul testi:** Fransızca örnek `status=ok`, `hard=False`; Türkçe hedefte istenmeyen şapkalı harf politikası ayrıca kendi testini korumalıdır.

---

## 5. Anlamlı Unicode yön/birleştirme kontrolleri tüm hedeflerde sessizce siliniyor

**Kod:**

- `subtitle_formats.py:340-372` — `_INVISIBLE_FORMAT_CHARS`, `normalize_subtitle_control_artifacts`
- `subtitle_translator_gui.py:3334-3376,3381-3393` — iki SRT yazım yolu

**Kök neden:** ZWJ (`U+200D`), ZWNJ (`U+200C`), LRM/RLM, bidi embedding/isolate karakterleri “görünmez artefakt” grubunda toptan siliniyor. Fonksiyon hedef dili ve karakterin komşularını bilmiyor.

**Saf karşı örnek:**

```text
قال ⁦NASA⁩ اليوم  -> قال NASA اليوم
👩‍👩‍👧‍👦          -> 👩👩👧👦
A‌B               -> AB
```

İlk satırda `U+2066/U+2069` isolate, ikincide üç `U+200D`, üçüncüde `U+200C` kayboldu.

**Etki:** Arapça/RTL altyazıda Latin isim ve sayının görsel sırası oynatıcıya göre bozulabilir; ZWJ emoji tek aile glifi yerine dört ayrı glife dönüşür; ZWNJ kullanan yazımlarda harf birleşimi/ortografi değişir. Denetim bunu sonradan göremez çünkü veri yazım sırasında silinmiştir.

**Düzeltme ölçütü:** NUL/C0 ve gerçekten zararlı artefaktlarla Unicode biçim kontrolü ayrılmalı. ZWJ/ZWNJ ve bidi isolate işaretleri bağlam/target-script açısından geçerliyse korunmalı; yalnız Türkçe Latin kelime içine yanlışlıkla girmiş kanıtlı artefaktlar dar bir kuralla temizlenmelidir.

**Kabul testleri:** Aile emojisi ve Arapça isolate dizisi codepoint düzeyinde round-trip yapmalı; Latin kelime ortasındaki bilinen bozuk BOM/soft-hyphen temizliği korunmalıdır.

---

## 6. Tümü büyük kaynak normalizasyonu kısaltmaları ve Roma rakamlarını bozuyor

**Kod:** `subtitle_translator_gui.py:5248-5308,5326-5347`

**Kök neden:** `_DELIVERY_KEEP_UPPER` sonlu/sabit bir liste. Kaynak ve hedef cue toplamda all-caps ise listedeki olmayan her harf tokenı Türkçe küçük harfe çevriliyor. Roma rakamındaki ASCII `I`, Türkçe `ı`ya dönüşüyor.

**Saf karşı örnek:**

```text
Kaynak: LSD AND MDMA
Hedef : LSD VE MDMA
Sonuç : Lsd ve mdma

Kaynak: CHAPTER VIII
Hedef : BÖLÜM VIII
Sonuç : Bölüm vııı
```

Doğrudan helper sonuçları da `DMT -> Dmt`, `UNESCO -> Unesco`, `NYPD -> Nypd` oldu.

**Etki:** Özellikle farmakoloji/belgesel altyazılarında LSD, MDMA, DMT gibi terimler ve bölüm/yüzyıl Roma rakamları son teslimde, bütün AI pass'leri bittikten sonra bozulur. Değişiklik kaynak/glossary guard ve pass raporu dışında gerçekleşir.

**Düzeltme ölçütü:** Roma rakamları ayrı regex ile korunmalı. Kaynakta da aynı all-caps token bulunan kısa kısaltmalar, locked glossary/terim listesi ve yaygın acronym biçimleri dinamik korunmalı; sıradan all-caps cümle sözcükleri yine sentence-case olabilmelidir.

**Kabul testleri:** `LSD VE MDMA`, `DMT`, `UNESCO`, `NYPD`, `VIII` korunmalı; `THIS IS A SENTENCE -> Bu bir cümle` türü normalizasyon davranışı bozulmamalıdır.

---

## 7. Final dosyanın adını değiştirmek provenance ve post-işlem kaynak eşleşmesini koparıyor

**Kod:**

- `subtitle_translator_gui.py:13126-13248` — sidecar adı/adayları
- `subtitle_translator_gui.py:5621-5677` — `_resolve_postprocess_source`

**Kök neden:** Önceki “klasör taşınması” düzeltmesi sidecar'ı aynı **stem** ile arıyor. Final SRT'nin adı değişirse hem absolute-path tokenı hem stem değişiyor. Rapor resolver'ı da rapordaki eski `output_path` ile güncel yolu birebir karşılaştırıyor.

**Saf karşı örnek:** Geçerli kaynak, final, JSON rapor ve source/output hash sidecar oluşturuldu. Yalnız:

```text
Original Release.srt -> Film (1986).srt
```

yeniden adlandırıldı. Sonuç:

```text
_output_matches_source_fingerprint = False
_resolve_postprocess_source         = None
```

**Etki:** Kullanıcının standart teslim adlandırması olan yalnız “Film Adı (Yıl).srt” düzenine geçince kaynak bağlı manuel denetim, güvenli post-process, skip ve recovery kanıtı kaybolur. Kaynak arşivi diskte bulunsa bile resolver güncel finali eski rapor satırına bağlayamaz.

**Neden önceki madde değil:** Önceki raporun 40. maddesi yalnız klasör taşımasını kapsıyordu ve güncel kod aynı-stem fallback eklemiş durumda. Bu karşı örnek klasör değişmeden yalnız **dosya adı/stem** değiştiğinde devam ediyor.

**Düzeltme ölçütü:** Provenance output adına değil değişmez bir delivery UUID'sine veya doğrulanmış output hash'ine bağlanmalı. Resolver sidecar payload/output hash + kaynak hash ile yeniden adlandırılmış finali bulabilmeli; birden fazla aday varsa otomatik seçim yerine fail-closed raporlamalıdır.

**Kabul testi:** Geçerli final aynı klasörde veya başka klasörde yeniden adlandırıldıktan sonra kaynak hash'i ve output hash'iyle eşleşmeli; içerik değişirse yine reddedilmelidir.

---

## 8. İstenen upload-ready işaret sözleşmesi üretim kodunda yok

**Kod:** `subtitle_translator_gui.py:12595-12716`

**Kök neden / mevcut davranış:** Üretim kodundaki tek completion marker:

```python
_COMPLETION_MARKER_NAME = "ÇEVRİLDİ.txt"
```

Marker yolu output/final klasöründen değil `_completion_marker_root(source, roots)` ile **kaynak giriş kökünden** türetiliyor. Üretim `.py` dosyalarında `YÜKLEMEYE HAZIR.txt` yazımı bulunmuyor.

**Etki:** İstenen çalışma sözleşmesi — her gerçekten teslim-ready film/bölüm klasöründe ayrı `YÜKLEMEYE HAZIR.txt` görme — program tarafından sağlanmıyor. Kaynak klasördeki `ÇEVRİLDİ.txt`, final klasörün semantik denetimden geçip yüklenebilir olduğu anlamına gelmeyen farklı bir işaret.

**Neden önceki marker maddesi değil:** Önceki raporun 35. maddesi mevcut marker'ın yazılmadan önce output hash'ini yeniden doğrulamamasını kapsıyordu. Güncel kod bu doğrulamayı eklemiş durumda. Buradaki açık marker'ın **adı, yeri ve anlam sözleşmesi** ile ilgilidir.

**Düzeltme ölçütü:**

- `ÇEVRİLDİ.txt` kaynak/kuyruk durumu için gerekiyorsa ayrı kalabilir.
- Hard delivery audit, kaynak+çıktı fingerprint'i ve gerekli semantik denetim tamamlanınca finalin kendi teslim klasörüne tam adıyla `YÜKLEMEYE HAZIR.txt` yazılmalı.
- Dosya partial/review/quarantine olursa eski upload-ready marker kaldırılmalı.
- Marker içerik olarak run id, final SRT adı/hash'i ve denetim zamanını taşımalıdır.

**Kabul testi:** Aynı run içindeki biri `done`, biri `review` olan iki farklı final klasöründen yalnız `done` olan tam `YÜKLEMEYE HAZIR.txt` almalıdır.

---

## İkinci tur — önceki rapor ve bulgulardan bağımsız yeni maddeler

Bu turda arka plandaki eski-rapor düzeltmeleri sonrasındaki `ae7b570` HEAD yeniden okundu. Aşağıdaki karşı örneklerin hiçbiri API çağrısı veya GUI oluşturulması gerektirmedi.

## 9. WebVTT karakter varlıkları çözülmeden kaynak ve final metne taşınıyor

**Kod:** `subtitle_formats.py:776-780,785-857`

**Kök neden:** `_clean_vtt_text` yalnız WebVTT etiketlerini siliyor; WebVTT'nin desteklediği karakter referanslarını çözmüyor. Üstelik `parse_vtt`, temizlenmiş değeri yalnız boşluk kontrolünde kullanıp bloklara ham `text` değerini ekliyor.

**Saf karşı örnek:** Geçici VTT:

```vtt
WEBVTT

00:00:01.000 --> 00:00:02.000
Tom &amp; Jerry &lt;3 &nbsp; forever
```

Güncel parser sonucu:

```python
[('1', '00:00:01,000 --> 00:00:02,000',
  'Tom &amp; Jerry &lt;3 &nbsp; forever')]
```

**Etki:** Model gerçek `&`, `<` ve ayrılmaz boşluk yerine entity yazımını görür. Model bunları aynen korursa SRT oynatıcıda `&amp;`/`&nbsp;` literal görünebilir; `&lrm;`/`&rlm;` gibi yön varlıkları da doğru Unicode davranışına dönüşmez.

**Düzeltme ölçütü:** WebVTT'nin izin verdiği adlandırılmış karakter referansları parser katmanında tek kez çözülmeli. İşlem sırası, çözülen `&lt;` içeriğinin yeniden HTML etiketi sanılıp silinmesine izin vermemeli; bilinmeyen varlıklar sessizce kaybedilmemelidir.

**Kabul testleri:** `&amp;→&`, `&lt;→<`, `&gt;→>`, `&nbsp;→U+00A0` ve yön varlıkları doğrulanmalı; düz `AT&T` değişmemeli; bilinmeyen `&filmname;` güvenli biçimde korunmalı veya açıkça raporlanmalıdır.

---

## 10. Exact Translation Memory büyük/küçük harf ve satır yapısını kaybederek farklı anlamları tek kayda çarpıştırıyor

**Kod:** `translation_memory.py:249-257,300-338`

**Kök neden:** Exact-TM anahtarı oluşturulurken kaynak `lower()` ile küçük harfe indiriliyor ve `split()/join()` ile bütün whitespace tek boşluğa çevriliyor. Aynı hash'e düşen varyasyonların tamamına veritabanındaki tek hedefin dağıtılması, önceki “kaçırılan varyasyonu da döndür” düzeltmesinden sonra semantik çarpışmayı doğrudan final ikamesine dönüştürüyor.

**Saf karşı örnek:** Aynı hedef dil/model/schema/kaynak dili/bağlamda:

```python
store('US', 'ABD')
store('us', 'bize')

lookup('US')                 # 'bize'
lookup('us')                 # 'bize'
lookup_batch(['US', 'us'])   # {'US': 'bize', 'us': 'bize'}
```

Ayrıca aşağıdaki çiftlerin hash'leri güncel kodda eşittir:

```text
US                         == us
May                        == may
Polish                     == polish
- Hello\n- Goodbye         == - Hello - Goodbye
```

**Etki:** Kısaltma/ülke adı ile zamir, özel ad/ay ile yardımcı fiil veya iki konuşmacılı cue ile tek satırlı cue birbirinin çevirisini API çağrısı olmadan alabilir. Bu yanlış değer exact-TM hit'i olduğu için model tarafından yeniden değerlendirilmeyebilir.

**Neden eski BUG 47 değil:** Eski madde aynı hash'e düşen yazım varyasyonlarından birinin sonuç sözlüğüne hiç eklenmemesini ve gereksiz API çağrısını anlatıyordu. Güncel kod artık tüm varyasyonları ekliyor; buradaki yeni hata, **tek hedefi semantik olarak farklı bütün varyasyonlara dağıtmasıdır**.

**Düzeltme ölçütü:** Exact hash kaynak case ve satır/konuşmacı yapısını korumalıdır. Case-insensitive veya whitespace-insensitive eşleşme isteniyorsa yalnız ayrı bir fuzzy aday olmalı; acronym/proper-noun/common-word ve konuşmacı satırı güvenliği doğrulanmadan nihai ikame yapmamalıdır.

**Kabul testleri:** `US/us`, `May/may`, `Polish/polish` ve iki-satırlı/tek-satırlı örnekler ayrı exact kayıtlara gitmeli; yalnız gereksiz dış boşluk ve satır sonu kodlaması (`CRLF/LF`) eşdeğerliği korunmalıdır.

---

## 11. Desteklenmeyen veya tehlikeli herhangi bir HTML etiketi çeviriye geri sarılıyor; nihai audit yalnız ASS komutlarına bakıyor

**Kod:**

- `subtitle_formats.py:542-552,555-620` — `_match_full_wrap`, `restore_format_tags`
- `subtitle_translator_gui.py:14890-14900,14966-15015` — final format audit'i

**Kök neden:** `_match_full_wrap`, güvenli SRT biçimleri için allowlist kullanmıyor; harfle başlayan her `<etiket ...>...</etiket>` çiftini biçim kabul ediyor. `restore_format_tags` bunu hedefin çevresine aynen koyuyor. Nihai audit'in `residual_format_tags` sayacı ise yalnız ASS override komutlarını sayıyor, HTML benzeri etiketleri hiç taramıyor.

**Saf karşı örnek:** Kaynak `<script>alert(1)</script>`, hedef `Uyarı.` için:

```text
clean_translation_source_text -> alert(1)
restore_format_tags            -> <script>Uyarı.</script>
delivery audit status          -> ok
residual_format_tags           -> 0
hard error                     -> False
```

Aynı kök `<span class="speaker">...</span>` gibi SRT standardında güvenilir olmayan gerçek dünya etiketlerini de finale taşır.

**Etki:** Final SRT desteklenmeyen/malformed etiket taşıdığı hâlde upload-ready sayılabilir. Oynatıcı etiketi literal gösterebilir, metni gizleyebilir veya farklı yorumlayabilir; rapor bunu kullanıcıya bildirmez.

**Düzeltme ölçütü:** Geri yükleme yalnız açık SRT allowlist'ine (`i`, `b`, `u`, kontrollü `font`) ve dengeli/doğru iç içe kapanışa izin vermeli. Nihai audit kalan bütün `<...>` dizilerini taramalı; allowlist dışı, dengesiz veya öznitelik politikası dışı etiketi hard failure yapmalıdır.

**Kabul testleri:** `<i>Hello</i>` güvenle geri yüklenmeli; `<span>`, `<script>`, `<iframe>` ve `<b>...</i>` geri yüklenmemeli; bunlar diskte zaten varsa audit `review/hard-error` üretmelidir.

---

## 12. Dosya adındaki dil etiketi içerik tabanlı kaynak-dil analizini tamamen bypass ediyor

**Kod:**

- `subtitle_translator_gui.py:1279-1298` — `infer_source_language_from_filename`
- `subtitle_translator_gui.py:31047-31075` — `_detect_source_languages_parallel`

**Kök neden:** Otomatik kaynak dilinde, dosya adından tek bir dil adayı çıkarsa `_one()` doğrudan döner; cue'lar okunmaz ve `detect_source_language_with_ai` hiç çağrılmaz. Dosya adı normalde yalnız destekleyici kanıt olmalı iken fiilen otorite oluyor.

**Saf karşı örnek:** İçeriği `Bonjour tout le monde` olan `Actually.French.eng.srt` dosyasında AI çağrısını sayan sahte istemciyle:

```text
infer_source_language_from_filename = English
_detect_source_languages_parallel   = English
AI çağrısı                          = 0
```

Heuristik ayrıca `Ara.srt`, `Dan.srt`, `Fin.srt`, `Chi.srt` gibi gerçek film/kişi adlarını son token olduğu için dil kodu sayabilir.

**Etki:** Yanlış kaynak dil; ana promptu, auto-glossary kararını, dil-özel temizliği, TM namespace'ini ve kalite kontrollerini zehirleyebilir. Kullanıcının onay ekranında yüksek güvenli içerik analizi yapılmış izlenimi oluşur, oysa yalnız dosya adı kullanılmıştır.

**Düzeltme ölçütü:** Dosya adı yalnız başlangıç tahmini/hint olmalı. Otomatik modda okunabilir diyalog varsa içerik tabanlı algılama yine çalışmalı; filename ve içerik çatışırsa açık uyarı ve kullanıcı seçimi istenmelidir. Yalnız güvenilir container stream metadata'sı veya kullanıcı seçimi doğrudan otorite olabilir.

**Kabul testleri:** Fransızca içerikli `Movie.eng.srt` Fransızca bulunmalı ve çatışma raporlanmalı; İngilizce içerikli `Ara.srt` Arapça sayılmamalı; gerçek `Movie.1990.eng.srt` filename hint'ini kullanabilmeli fakat içerik tersini gösterirse sessiz bypass olmamalıdır.

---

## 13. “Kaynakla aynı klasör” modunda VTT/ASS finalleri program çıktısı olarak tanınmıyor ve yeniden kaynak oluyor

**Kod:**

- `subtitle_translator_gui.py:5986-6011` — `_resolve_output_path`
- `subtitle_formats.py:30-33,1031-1114` — generated-artifact filtresi ve klasör taraması

**Kök neden:** Aynı-klasör modunda `.srt` kaynak `<stem>.tr.srt` olurken `.vtt/.ass/.ssa` kaynaklar `source.name + '.srt'` biçiminde yazılıyor:

```text
movie.vtt -> movie.vtt.srt
movie.ass -> movie.ass.srt
```

Generated-artifact filtresi `.tr.srt/.partial.srt/.bak.srt/.ham.srt/...` desenlerini tanıyor; `.vtt.srt/.ass.srt/.ssa.srt` desenlerini tanımıyor.

**Saf karşı örnek:** Geçici klasörde `movie.vtt`, `movie.ass` ve hesaplanan iki final oluşturuldu. Güncel tarama sonucu:

```python
['movie.ass', 'movie.ass.srt', 'movie.vtt', 'movie.vtt.srt']
```

Dört dosyanın da `is_generated_subtitle_name` sonucu `False` oldu.

**Etki:** Sonraki klasör eklemede program kendi Türkçe finalini yeni kaynak diye kuyruğa alabilir; yanlış kaynak-dil uyarıları, gereksiz ücretli yeniden çeviri ve `movie.vtt.tr.srt` gibi zincir çıktılar oluşabilir.

**Neden eski standalone maddesi değil:** Eski madde standalone tarayıcının bilinen `.tr/.ham/.partial` yan-artifaktlarını dışlamamasıydı. Burada ortak filtre çalışıyor fakat GUI'nin VTT/ASS için ürettiği **çıktı adı filtre sözleşmesine hiç uymuyor**.

**Düzeltme ölçütü:** Bütün kaynak biçimleri aynı-klasör modunda açık generated suffix kullanmalı (ör. `<stem>.tr.srt`) ve legacy `.vtt.srt/.ass.srt` finalleri yalnız komşu kaynak/fingerprint ile doğrulanırsa güvenle dışlanmalıdır; meşru indirilen dosyalar sırf adı benziyor diye körlemesine atılmamalıdır.

**Kabul testi:** Aynı klasörde VTT/ASS kaynak ve bunların finalleri varken yeniden tarama yalnız iki gerçek kaynağı döndürmelidir.

---

## 14. Aynı zaman damgasını paylaşan ayrı cue'lar kalite kaynak haritasında ve satır-satır raporda birbirini eziyor

**Kod:**

- `subtitle_translator_gui.py:11664-11682` — `_source_map_for_quality_blocks`
- `subtitle_translator_gui.py:15100-15164` — `_build_line_by_line_audit_package`

**Kök neden:** İki yardımcı da timestamp'i tekil sözlük anahtarı sayıyor:

```python
by_timestamp[timestamp] = text
output_by_ts = {timestamp: (id, text) ...}
```

Aynı zaman aralığında iki ayrı cue olduğunda sonuncu öncekinin metnini eziyor.

**Saf karşı örnek:** Kaynak ve hedefte aynı `00:00:01,000 --> 00:00:02,000` aralığını paylaşan iki cue:

```text
#1 Hello.    -> Merhaba.
#2 Goodbye.  -> Hoşça kal.
```

Üretilen satır-satır denetim paketi:

```text
KAYNAK : Hello.
TÜRKÇE : Hoşça kal.
KAYNAK : Goodbye.
TÜRKÇE : Hoşça kal.
```

`_source_map_for_quality_blocks` da iki hedef ID için son kaynak metnini verir.

**Etki:** Tam da kullanıcının sonradan manuel/Codex denetimi için güvendiği rapor doğru çeviriyi gizleyip yanlış eşleşme gösterir. Kalite taraması aynı yapıyı kullanan akışlarda gerçek source-target çiftini kaybederek yanlış pozitif veya yanlış negatif üretebilir.

**Neden eski aynı-timestamp kredi maddesi değil:** Eski madde teslim temizliğinde bir kredi cue'sunun aynı zamandaki diyaloğu sildirmesiydi. Güncel kod o silme yolunu gruplayarak düzeltiyor. Buradaki açık, **kalite ve rapor eşlemesinin bire-çok zaman aralığını hâlâ tek sözlük girdisine indirmesidir**.

**Düzeltme ölçütü:** Eşleme timestamp→tek değer değil, sıralı timestamp→liste/pozisyon ilişkisi taşımalı; önce ID, sonra occurrence index ve gerekirse overlap/owner eşlemesi kullanılmalıdır. Cue birleştirilmişse kaynak span'i açık listeyle temsil edilmelidir.

**Kabul testi:** Aynı timestamp'teki iki kaynak/hedef cue raporda bire bir doğru görünmeli; tek hedefte bilinçli birleştirilmiş iki kaynak cue ise ikisi de aynı hedefe “birleştirilmiş span” olarak açıkça yazılmalıdır.

---

## 15. WebVTT `X-TIMESTAMP-MAP` medya zamanına uygulanmıyor

**Kod:** `subtitle_formats.py:488-496,785-857`

**Kök neden:** `parse_vtt` cue timestamp'lerini doğrudan `_vtt_ts_to_srt` ile biçim değiştirerek yazıyor; WebVTT başlığındaki `X-TIMESTAMP-MAP=LOCAL:...,MPEGTS:...` satırını okumuyor. Dolayısıyla HLS/WebVTT yerel zamanı ile video MPEG zaman tabanı arasındaki ofset kayboluyor.

**Saf karşı örnek:** MPEGTS 90 kHz olduğundan `900000` değeri 10 saniyedir:

```vtt
WEBVTT
X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:900000

00:00:01.000 --> 00:00:02.000
Hello
```

Haritaya göre medya zamanında cue `00:00:11,000 --> 00:00:12,000` olmalıdır. Güncel parser sonucu:

```python
[('1', '00:00:01,000 --> 00:00:02,000', 'Hello')]
```

**Etki:** HLS segmentinden veya timestamp-map kullanan WebVTT kaynağından üretilen Türkçe SRT, kaynak metindeki yerel cue zamanını korur fakat videonun gerçek timeline'ına oturmaz. Programın source-target karşılaştırması iki tarafta da aynı yanlış zamanı gördüğü için bunu kendi iç kayma denetimiyle yakalayamaz.

**Düzeltme ölçütü:** Parser header metadata'sını okuyup `media_seconds = local_cue - LOCAL + MPEGTS/90000` dönüşümünü başlangıç ve bitişe uygulamalı; 33-bit MPEGTS wraparound, negatif sonuç ve birden fazla segment birleştirme açıkça ele alınmalıdır. Düz VTT davranışı değişmemelidir.

**Kabul testleri:** Yukarıdaki örnek 11–12 saniyeye dönüşmeli; `LOCAL:00:00:05.000,MPEGTS:900000` ile 6–7 yerel cue yine 11–12 olmalı; map içermeyen VTT mevcut zamanı aynen korumalıdır.

---

## 16. Log listesi ile `stat()` arasındaki dosya yarışı uygulama başlangıcını düşürebiliyor

**Kod:**

- `subtitle_translator_gui.py:15688-15719` — `rotate_logs`
- `subtitle_translator_gui.py:16506-16515` — uygulama başlangıcındaki çağrı

**Kök neden:** İlk `glob('*.log')` çağrısı hata korumasında, tek tek silme de hata korumasında; fakat aradaki sıralama doğrudan `p.stat().st_mtime` çağırıyor. Bir log glob sonrasında başka süreç/antivirüs tarafından silinirse, kilitlenirse veya erişilemez hâle gelirse `OSError` sıralamadan dışarı taşar. `App.__init__` bu çağrıyı catch etmeden yaptığı için UI kurulmadan açılış kesilir.

**Saf karşı örnek:** Geçici iki log oluşturulup bunlardan birinin `Path.stat()` çağrısı gerçek dosya-yarışı gibi `OSError('gone')` döndürüldü:

```text
rotate_logs(...)
  candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
OSError: gone
```

**Etki:** Canlı çeviri yapmasa bile ikinci örnek/test/temizlik işlemiyle log klasöründe oluşan kısa bir yarış, uygulamanın hiç açılmamasına yol açabilir. Kullanıcı bunu çeviri veya ayar bozulması sanabilir; yeni oturum logu da henüz açılamadığı için teşhis kaydı oluşmaz.

**Düzeltme ölçütü:** Her adayın mtime'ı ayrı `try/except OSError` ile okunmalı; kaybolan/erişilemeyen aday o tur atlanmalı. `rotate_logs` hiçbir tekil dosya hatasını App başlangıcına taşımamalı ve canlı PID korumasını gevşetmemelidir.

**Kabul testi:** İki adaydan biri `stat` sırasında kaybolduğunda `rotate_logs` istisna atmadan tamamlanmalı; erişilebilen eski aday için normal keep politikası, canlı PID logları için koruma aynen sürmelidir.

---

## Üçüncü tur — güncel HEAD üzerinde eklenen bağımsız bulgular

Bu tur `ae7b570` üzerinde, önceki 16 madde ile dışlama tabanındaki 167 başlıktan farklı kök nedenler aranarak yapıldı. Üretim dosyası değiştirilmedi; karşı örnekler geçici dosya ve saf fonksiyonlarla çalıştırıldı.

## 17. Manuel post-işlem rapor sıralamasındaki dosya yarışı tek dosyanın akışını düşürüyor

**Kod:** `subtitle_translator_gui.py:5893-5913,29414-29445,29759-29764`

**Kök neden:** `_resolve_postprocess_source`, raporları `glob` ile topladıktan sonra şu ifadeyle sıralıyor:

```python
sorted(set(report_files), key=lambda path: path.stat().st_mtime, reverse=True)
```

Raporun içeriğini okuyan bölüm `OSError` yakalıyor, fakat sıralamadaki `stat()` çağrısı bu korumanın dışında. Bir rapor `glob` ile listeleme ile `stat` arasında silinir, taşınır, kilitlenir veya erişilemez olursa istisna doğrudan manuel post-işlem worker'ına çıkar.

**Saf karşı örnek:** İki rapordan birinin `Path.stat()` çağrısı gerçek dosya-yarışı gibi `OSError("gone")` döndürüldü:

```text
_resolve_postprocess_source(...)
  sorted(... key=lambda path: path.stat().st_mtime ...)
OSError: gone
```

**Etki:** Tek bir eski/antivirüsçe kilitlenmiş rapor, aynı dosyanın kaynak çözümlemesini durdurur. Dış `try` bunu genel post-işlem hatası olarak kaydeder; sağlam eski raporlar ve `Raporlar/Kaynak` arşivi hiç denenmez. API çağrısı başlamışsa dosya bazında harcama da boşa gidebilir.

**Neden 16. maddeyle aynı değil:** 16. madde `logs/` rotasyonunda uygulama açılışını düşüren ayrı bir fonksiyon ve yaşam döngüsüdür. Bu madde kalite post-işlemindeki **kaynak provenance çözümleyicisini** etkiler ve başka veri kümesi kullanır.

**Düzeltme ölçütü:** Her rapor adayı için mtime ayrı `try/except OSError` içinde okunmalı; okunamayan aday atlanmalı, kalan sağlam raporlar yeni→eski sırasıyla denenmelidir.

**Kabul testi:** En yeni aday `stat` sırasında kaybolurken daha eski sağlam rapor gerçek kaynağı göstermeli; `_resolve_postprocess_source` istisna atmadan o kaynağı döndürmelidir.

---

## 18. Kaynak arşivi birden çok sürümde yanlış dosyayı seçebiliyor

**Kod:**

- `subtitle_translator_gui.py:5952-5968` — `_archived_source_candidate`
- `subtitle_translator_gui.py:13485-13511` — farklı içeriği hash ekli adla arşivleme
- `subtitle_translator_gui.py:5875-5890` — yalnız sidecar bulunursa kaynak drift kontrolü

**Kök neden:** Arşivleyici aynı adlı kaynak değiştiğinde yeni sürümü `movie.en.<hash>.srt` olarak saklıyor. Resolver ise içerik hash'ine veya rapordaki kaynak hash'ine bakmadan önce daima düz `movie.en.srt` dosyasını döndürüyor; ancak o dosya eski sürümdür. Düz ad yoksa da hash'li adayları alfabetik ilk dosyadan başlayarak seçiyor.

**Saf karşı örnek:** Geçici `Raporlar/Kaynak` klasörüne şu iki dosya kondu:

```text
movie.en.srt                 = OLD SOURCE
movie.en.abcdef123456.srt    = NEW SOURCE
```

Güncel sonuç:

```text
_archived_source_candidate(...) -> movie.en.srt / OLD SOURCE
```

**Etki:** Orijinal giriş silindikten sonra manuel Critic/Polish/Native/QC yanlış kaynak sürümünü karşılaştırabilir. Güncel ve bulunabilir source sidecar çoğu normal akışta bunu drift olarak durdurur; fakat sidecar'ı olmayan eski teslimlerde, yeniden adlandırılan/taşınan çıktıda veya belirsiz sidecar durumunda yanlış kaynak sessizce kullanılabilir. En iyi durumda post-işlem gereksiz yere bloklanır; en kötü durumda doğru çeviri başka sürümün repliklerine göre değiştirilir.

**Neden eski arşiv fallback maddesi değil:** Eski madde, kaynak silinince arşive hiç bakılmamasını düzeltti. Buradaki açık fallback'in varlığı değil, **arşivde birden çok kaynak sürümünden doğru hash'in seçilmemesidir**.

**Düzeltme ölçütü:** Kalite raporu/source sidecar içindeki beklenen `source_sha256`, resolver'a taşınmalı; arşiv adayları içerik hash'iyle seçilmelidir. Beklenen hash yoksa birden çok farklı içerikli adayda fail-closed davranılmalı, alfabetik ilk dosya seçilmemelidir.

**Kabul testleri:** Eski düz-ad ve yeni hash-adlı iki sürüm varken yeni raporun SHA'sı yalnız yeni dosyayı seçmeli; hash bilgisi yok ve iki farklı içerik varsa resolver `None` döndürüp görünür provenance uyarısı üretmelidir.

---

## 19. ASS/SSA `Timer` değeri cue zamanlarına uygulanmıyor

**Kod:** `subtitle_formats.py:498-517,892-1009`

**Format dayanağı:** ASS/SSA `[Script Info]` içindeki `Timer`, script saatinin yüzde hız çarpanıdır; `100.0000` normal hızdır. Bu alan [Subtitle Edit ASS referansında](https://github.com/SubtitleEdit/subtitleedit/blob/main/docs/reference/assa.md) ve [SSA format açıklamasında](https://forum.videohelp.com/attachment.php?attachmentid=33290&d=1440307546) zaman çarpanı olarak tanımlanır.

**Kök neden:** `parse_ass` yalnız `[Events]`, `Format` ve `Dialogue` satırlarını okuyor. `[Script Info]` içindeki `Timer:` hiç ayrıştırılmıyor; `_ass_ts_to_srt` ham Start/End değerini doğrudan SRT'ye çeviriyor.

**Saf karşı örnek:** `Timer: 200.0000` ve `0:00:10.00 --> 0:00:12.00` cue'su taşıyan ASS dosyası güncel parser'da:

```text
00:00:10,000 --> 00:00:12,000
```

olarak döndü. Script saati yüzde 200 hızla aktığı için medya zamanında beklenen aralık `00:00:05,000 --> 00:00:06,000` olmalıdır.

**Etki:** Timer değeri 100 olmayan bütün ASS/SSA dosyasında çeviri metni doğru olsa bile SRT zamanları film boyunca sistematik ölçekte kayar. Kaynak ve hedef aynı parser çıktısını kullandığı için programın iç kaynak-hedef timestamp denetimi bu kaymayı göremez; sorun ancak videoda fark edilir.

**Düzeltme ölçütü:** `[Script Info] Timer` locale-bağımsız sayı olarak okunmalı ve cue zamanları `100 / Timer` katsayısıyla medya zamanına dönüştürülmelidir. Eksik, sıfır, negatif veya geçersiz değer güvenli biçimde `100` kabul edilmeli ve raporlanmalıdır.

**Kabul testleri:** `Timer=200` için 10–12 saniye 5–6'ya; `Timer=50` için 10–12 saniye 20–24'e dönüşmeli; `Timer=100` ve Timer'sız dosyanın mevcut çıktısı değişmemelidir.

---

## 20. ASS'te tamamen görünmez metin SRT'de görünür hâle geliyor

**Kod:**

- `subtitle_formats.py:892-974` — `parse_ass`, stil tanımlarını ve alpha görünürlüğünü okumuyor
- `subtitle_formats.py:652-659` — `_clean_ass_text`, inline alpha override'ını yalnız silip metni koruyor
- `subtitle_formats.py:531-539` — SRT yazımında güvenli olmayan override'ı atıp yazıyı bırakıyor

**Kök neden:** Parser yalnız event satırındaki stil adını saklıyor; `[V4+ Styles]` içindeki `PrimaryColour`/`SecondaryColour` alpha kanallarını çözmüyor. Ayrıca `{\alpha&HFF&}` veya kanal bazlı `{\1a&HFF&}` ile tamamen görünmez yapılmış event, override bloğu temizlendikten sonra normal metin gibi çevriliyor. ASS'te `&HFF` alpha tamamen saydamdır.

**Saf karşı örnek:** Biri `PrimaryColour=&HFFFFFFFF` kullanan `Hidden` stilinde, diğeri inline `{\alpha&HFF&}` kullanan iki event oluşturuldu. Güncel `parse_ass` sonucu ikisini de tuttu:

```text
INVISIBLE STYLE TEXT
{\alpha&HFF&}INLINE INVISIBLE TEXT
```

Son temizlik override komutunu kaldırdığı için ikinci satır da `INLINE INVISIBLE TEXT` olarak görünür SRT cue'suna dönüşür.

**Etki:** Kaynakta bilerek görünmeyen çevirmen yardımcıları, maskeleme metinleri, karaoke şablonları veya teknik event'ler final SRT'de seyirciye gösterilebilir ve gereksiz yere API'ye gönderilir. Kaynak parser bu cue'yu gerçek diyalog saydığı için teslim denetimi de varlığını bekler; kendi kendini doğrulayan yanlış final oluşur.

**Düzeltme ölçütü:** Stil tablosu alpha bilgisiyle ayrıştırılmalı; event başlangıcından tüm görünür metin boyunca effective alpha `FF` ise cue atlanmalıdır. Inline alpha daha sonra görünür değere dönüyorsa yalnız görünür segment korunmalı; `\t(...)` animasyonu ve kanal bazlı alpha için fail-closed/rapor yaklaşımı kullanılmalıdır.

**Kabul testleri:** Tamamen saydam stil ve baştan sona `\alpha&HFF&` event parser çıktısına girmemeli; `\alpha&HFF&gizli\alpha&H00&görünür` örneğinde yalnız görünür bölüm korunmalı; normal stil/renk ve yarı saydam (`80`) metin değişmemelidir.

---

## Dördüncü tur — format semantiği ve nihai metin mutasyonu

## 21. ASS küçük `\n` komutu yanlışlıkla her zaman zorunlu satır sonu yapılıyor

**Kod:** `subtitle_formats.py:634-657,681-682`

**Format dayanağı:** [Aegisub ASS Tags kılavuzuna](https://aegisubdocs.zahuczky.com/manual/ASS_Tags.html) göre büyük `\N` her WrapStyle'da zorunlu satır sonudur; küçük `\n` ise yalnız `WrapStyle: 2` altında zorunlu kırılır, diğer wrap modlarında normal boşluk gibi görünür.

**Kök neden:** `_ASS_SOFTLINE` ve `_ASS_HARDLINE` desenlerinin ikisi de `re.IGNORECASE` ile derlenmiş. Böylece iki desen de hem `\N` hem `\n` ile eşleşiyor ve `_clean_ass_text` ikisini koşulsuz `\n` karakterine dönüştürüyor. Parser `[Script Info] WrapStyle` değerini bu karar için okumuyor.

**Saf karşı örnek:** `WrapStyle: 0` taşıyan ASS event'inde görünür metin `Hello\nworld` iken güncel parser sonucu:

```text
Hello
world
```

oldu. Bu wrap modunda beklenen görünür metin `Hello world`dür.

**Etki:** Kaynakta yalnız güvenli sarım noktası olan küçük `\n`, final SRT'de zorunlu satır sonuna dönüşür. Uzun veya zaten iki satırlı cue'larda üç-dört satırlı teslim, yanlış konuşma bölünmesi ve gereksiz line-break/CPS müdahalesi oluşabilir.

**Düzeltme ölçütü:** `\N` ve `\n` büyük/küçük harfe duyarlı ayrıştırılmalı; parser event için `[Script Info] WrapStyle` değerini bilmeli. Küçük `\n`, WrapStyle 2 dışında tek boşluk; WrapStyle 2'de satır sonu olmalıdır.

**Kabul testleri:** Aynı `Hello\nworld` örneği WrapStyle 0/1/3'te `Hello world`, WrapStyle 2'de iki satır olmalı; `Hello\Nworld` bütün modlarda iki satır kalmalıdır.

---

## 22. Aynı ASS event'indeki vektör çizimi gerçek metne karışıyor

**Kod:** `subtitle_formats.py:648-659,711-715,943-953`

**Format dayanağı:** ASS `\p1` ve daha yüksek değerler vektör çizim modunu açar; `\p0` bu modu kapatır. Bu aradaki `m`, `l`, `b` ve koordinatlar görünür dil metni değil çizim komutlarıdır. Davranış [Aegisub ASS Tags kılavuzunda](https://aegisubdocs.zahuczky.com/manual/ASS_Tags.html) `\p` etiketi altında tanımlanır.

**Kök neden:** `_ass_is_drawing_only`, override bloklarını sildikten sonra **bütün** cue yalnız çizim sözdizimine benziyorsa event'i atlıyor. Bir event `\p1` çizimi kapattıktan sonra gerçek yazı içerirse tüm event tutuluyor; `_clean_ass_text` override bloklarını kaldırdığı için çizim komutları da normal kaynak kelimeleri gibi kalıyor.

**Saf karşı örnek:** Şu ASS metni:

```text
{\p1}m 0 0 l 100 0 100 100 0 100{\p0}VISIBLE TEXT
```

güncel kaynak temizleyicide şuna dönüştü:

```text
m 0 0 l 100 0 100 100 0 100VISIBLE TEXT
```

**Etki:** Vektör koordinatları yardımcı analize ve ana çeviriye gönderilir; model bunları konuşma sanabilir, sayı koruma guard'larını tetikleyebilir veya finalde koordinatları seyirciye gösterebilir. Yalnız çizim event'ini atan mevcut koruma bu karışık event'i yakalamaz.

**Düzeltme ölçütü:** ASS metni override durumu korunarak segment segment ayrıştırılmalı; drawing mode açıkkenki içerik atılmalı, `\p0` sonrasındaki görünür metin korunmalıdır. Drawing mode kapanmadan event biterse kalan bölüm tamamen çizim sayılmalıdır.

**Kabul testleri:** Saf çizim event'i yine atlanmalı; yukarıdaki karışık örnek yalnız `VISIBLE TEXT` üretmeli; `önce{\p1}...{\p0}sonra` sonucu `öncesonra` olmalı; normal `m 0 0` diyaloğu sırf metin benziyor diye düşmemelidir.

---

## 23. Eser ve karakter adlarındaki `Mr.` / `Miss` nihai yazımda bozuluyor

**Kod:** `subtitle_translator_gui.py:4626-4647,4728-4735,5697-5709`

**Kök neden:** `_FOREIGN_TITLE_MAP`, değişmiş her Türkçe cue üzerinde kaynak metinden, kilitli terimlerden ve özel-ad analizinden bağımsız çalışıyor. `Mr.` ve `Miss` sözcüklerini her bağlamda hitap sanarak `Bay` ve `Bayan` yapıyor. İşlem bütün kalite pass'lerinden sonra nihai normalizasyon zincirinde gerçekleştiği için modelin doğru özel adı son anda değişebiliyor.

**Saf karşı örnek:** Güncel saf yardımcı sonuçları:

```text
Miss Fortune geldi.  -> Bayan Fortune geldi.
Mr. Robot başladı.   -> Bay Robot başladı.
```

İlkinde `Miss Fortune` karakter adıdır; ikincisinde `Mr. Robot` eser/ad kimliğidir. İkisi de unvan çevirisi değildir.

**Etki:** Doğru çevrilmiş eser adları, lakaplar, marka/kurum adları ve karakter adları final SRT'de bağlamsız biçimde değiştirilir. Değişiklik model pass geçmişine ait değildir ve kaynak-anlam guard'ından sonra geldiği için sessizce upload-ready dosyaya yerleşebilir.

**Düzeltme ölçütü:** Unvan normalizasyonu yalnız kaynakta gerçek hitap/unvan yapısı doğrulandığında uygulanmalı; kilitli terim, analiz sözlüğü, eser adı veya çok sözcüklü özel ad eşleşmesi varsa korunmalıdır. Emin olunmayan eşleşme otomatik değiştirilmek yerine raporlanmalıdır.

**Kabul testleri:** `Mr. Smith, come in.` bağlamı `Bay Smith, içeri gelin.` olabilir; `Mr. Robot başladı.`, `Miss Fortune geldi.` ve kilitli `Mr. Nobody` aynen kalmalıdır.

---

## Beşinci tur — kaynak kodlama, toleranslı SRT ve TM kanon bağı

## 24. Geçerli Windows-1254 Türkçe SRT yanlış kodlamayla açılabiliyor

**Kod:** `subtitle_formats.py:190-221,361-376,415-477`

**Kök neden:** UTF-8 çözümlemesi başarısız olduğunda `_decode_detected_legacy` ve kısa-dosya yolu `_decode_short_legacy`, aynı baytları açabilen CP1250/CP1252/MacRoman/CP1254 adaylarını skorla seçiyor. CP1254'e özgü `İ`, `ı`, `ğ` baytları başka tek-baytlı kodlamalarda da geçerli karakterlere dönüştüğü için çözümleme istisna vermiyor; yanlış aday kazanabiliyor. Ardından `_repair_embedded_mac_roman_controls` yalnız C1 kontrol karakterlerini onardığından bu görünür ama yanlış harfler geri alınmıyor.

**Saf karşı örnek:** Tamamen geçerli CP1254 ile yazılmış tek cue:

```text
1
00:00:01,000 --> 00:00:02,000
İyi günler, nasılsın?
```

güncel `read_subtitle_text` sonucunda kısa dosyada Unicode kaçışlarıyla:

```text
\u203ayi g\xb8nler, nas\u02ddls\u02ddn?
```

olarak döndü (`›yi g¸nler, nas˝ls˝n?`). Aynı cümle dokuz cue ile uzatıldığında bu kez:

```text
\xddyi g\xfcnler, nas\xfdls\xfdn?
```

oldu (`Ýyi günler, nasýlsýn?`). Yani sorun yalnız kısa-dosya optimizasyonuyla sınırlı değil.

**Etki:** Türkçe bir kaynak veya daha önce üretilmiş CP1254 altyazı daha API'ye gitmeden bozulur. Model anlamsız karakterleri çevirmeye çalışır; özel ad, terim, soru ve bağlam kontrolleri yanlış metin üzerinde çalışır. Çıktı kaynakla aynı bozuk metne bağlandığı için source-target karşılaştırması özgün bayt anlam kaybını tespit edemez.

**Neden önceki MacRoman maddesi değil:** Önceki raporlar, Latin-1 içine C1 kontrolü olarak düşmüş Windows-1252 tırnak/tirelerinin onarımını kapsıyordu. Burada tüm dosyanın **başlangıç kodlaması yanlış seçiliyor** ve sonuç C1 kontrolü içermediği için o onarım yoluna hiç girmiyor.

**Düzeltme ölçütü:** CP1254 adayında Türkçeye özgü harf/bigram kanıtı, bu baytların rakip kodlamalarda ürettiği tipografik/özel-use karakterlerden daha güçlü ağırlık almalı. Skor kararsızsa kullanıcı kaynak dili Türkçe seçtiğinde CP1254 önceliği uygulanmalı; seçilen kodlama ve güven puanı tanı raporuna yazılmalıdır.

**Kabul testleri:** Kısa ve 80+ baytlık `İyi günler, nasılsın?`, `Çığlık, öğüt, şüphe.` fixture'ları CP1254'ten kayıpsız dönmeli; mevcut MacRoman İspanyolca ad, CP1252 akıllı tırnak, CP1250 Lehçe ve CP1251 Kiril testleri değişmeden geçmelidir.

---

## 25. Milisaniyesiz veya 4+ kesir haneli SRT zamanları bütün dosyanın boş sayılmasına yol açıyor

**Kod:**

- `subtitle_localizer/srt.py:13-15,19-69`
- `subtitle_translator_gui.py:3288-3355`
- `subtitle_formats.py:393-477`

**Kök neden:** Hem ortak SRT parser'ı hem GUI parser'ı zaman satırında tam `,mmm` veya `.mmm` alanını zorunlu tutuyor. Okuma normalizasyonu 1–3 haneli kısa kesirleri düzeltiyor; ancak kesir alanı hiç yoksa `,000` eklemiyor ve 4+ haneli kesri ilk üç haneye güvenle yuvarlamıyor/kesmiyor. SRT parse boş döndüğünde VTT fallback'i de bu biçimleri kabul etmediği için dosya tamamen boş kalıyor.

**Saf karşı örnek:** Aşağıdaki gerçek-dünya, toleransla okunabilir SRT:

```text
1
00:00:01 --> 00:00:03
Hello.
```

`subtitle_localizer.srt.parse_srt` ve GUI `parse_subtitle` tarafından sıfır cue olarak döndü.

Aynı sonuç aşağıdaki araç-üretimi mikro/ek hassasiyetli biçimlerde de saf olarak doğrulandı:

```text
00:00:01,1234   --> 00:00:03,5678
00:00:01,123456 --> 00:00:03,567890
```

Hem `subtitle_localizer.srt.parse_srt` hem GUI `parse_srt` iki örnekte de `0` cue döndürdü. Önceki dışlama belgesindeki 4+ hane maddesi yalnız ASS `_ass_ts_to_srt` yolundaydı; SRT parser'ları o düzeltmeden yararlanmıyor.

**Etki:** Program dosyayı boş/geçersiz sanarak çeviriye almıyor veya ön kontrolde atlıyor. Kullanıcı için bunun kodlama, içerik veya dosya-seçim hatası mı olduğu anlaşılmıyor; oysa güvenli dönüşüm yalnız iki tarafa `,000` eklemektir.

**Düzeltme ölçütü:** SRT zaman parser'ı kesir alanını opsiyonel kabul etmeli ve eksikse sıfır milisaniye üretmelidir. 4+ haneli geçerli sayısal kesir milisaniyeye deterministik dönüştürülmelidir (ilk üç hane veya belgelenmiş yuvarlama). Bu tolerans yalnız tam `HH:MM:SS` iki uca uygulanmalı; belirsiz serbest metin zaman satırı sanılmamalıdır.

**Kabul testleri:** `00:00:01 --> 00:00:03` değeri `00:00:01,000 --> 00:00:03,000` olmalı; `,1234` ve `,123456` belgelenen kurala göre geçerli `,123` milisaniyeye dönüşmeli; mevcut `,5`, `,12`, `,123`, noktalı ayraç ve numarasız-SRT testleri korunmalıdır.

---

## 26. Dizi kanonu, proje ipucu veya analiz derinliği değişince exact-TM hâlâ eski çeviriyi döndürüyor

**Kod:**

- `subtitle_translator_gui.py:12241-12255` — TM bağlam parmak izi
- `subtitle_translator_gui.py:6896-6918,27793-27810` — proje/dizi ipuçlarının prompt'a eklenmesi
- `subtitle_translator_gui.py:32620-32716` — exact/fuzzy TM ön taraması
- `translation_memory.py:241-339` — parmak izli lookup

**Kök neden:** `_tm_context_fingerprint` yalnız tüm kaynak dosyanın SHA-256 değerini ve kilitli terimleri kapsıyor. Oysa aynı kaynak için promptu değiştiren dizi hitap haritası (`sen/siz`), karakter üslubu, proje bağlam ipucu, yardımcı analiz sonucu ve Gelişmiş/Maksimum analiz derinliği bu özete dahil değil. Dizi hafızasındaki bazı terimler kilitli sözlüğe yansıyabilir; ancak `address_map`, karakter konuşma stili, sahne/ton analizi ve derinlik profili yansımaz.

**Saf karşı örnek:** Aynı kaynak ve aynı kilitli terimlerle iki `build_requests` çağrısında proje ipucu sırasıyla `REGISTER: informal` ve `REGISTER: formal` yapıldı. Üretilen system promptları farklıydı; `_tm_context_fingerprint('same-sha', {})` ise doğal olarak aynı kaldı. Böylece ilk koşuda TM'ye giren:

```text
You are late. -> Geç kaldın.
```

sonradan kanon `formal` olarak düzeltildiğinde de exact hit olur ve `Geç kaldınız.` için ana model hiç çağrılmaz.

Aynı biçimde dosya önce `Gelişmiş`, sonra `Maksimum` analizle çalıştırıldığında analiz cache fingerprint'i doğru biçimde değişse bile TM context fingerprint değişmez. İlk koşunun bütün cue'ları exact TM'de mevcutsa ikinci koşunun daha zengin karakter/sahne/terim bağlamı ana çeviriye uygulanmadan eski hedefler geri dönebilir.

**Etki:** Dizi hafızası/karakter analizi sonradan olgunlaştığında veya kullanıcı hitap kararını düzelttiğinde yeniden çeviri bu kararı uygulamayabilir. Exact-TM hit'i ana model ve onun sahne/karakter bağlamını bypass ettiği için eski `sen/siz`, üslup veya karakter sesi doğrudan finale taşınabilir. Gelişmiş/Maksimum A/B karşılaştırması da gerçekte iki analiz seviyesini değil, ilk koşunun TM sonucunu ölçebilir; kalite farkı ve maliyet değerlendirmesi yanıltılır.

**Düzeltme ölçütü:** TM context fingerprint, modele gerçekten enjekte edilen kanonik bağlamın kararlı özetini kapsamalı: en az analiz derinliği/analysis fingerprint, dizi `address_map`, karakter üslubu ve proje/dosya hint'inin semantik sürümü. Geçici çalışma metni değil normalize edilmiş karar verisi kullanılmalı; store ve lookup aynı yardımcıyla üretmelidir.

**Kabul testleri:** Aynı kaynak+terimlerde informal→formal address-map değişimi ve Gelişmiş→Maksimum analysis fingerprint değişimi TM miss üretmeli; yalnız JSON anahtar sırası veya gereksiz boşluk değişimi fingerprint'i değiştirmemeli; terim değişimi için mevcut izolasyon testi korunmalıdır.

---

## Altıncı tur — video seçimi, manuel JSONL kaynağı ve bölüm-kökü izolasyonu

## 27. Gömülü videoda ilk İngilizce forced/SDH/commentary stream'i yanlışlıkla varsayılan seçilebiliyor

**Kod:**

- `video_subtitles.py:36-40,94-134`
- `subtitle_translator_gui.py:24571-24576`

**Kök neden:** `ffprobe` isteği yalnız `index`, `codec_name`, `language` ve `title` alanlarını topluyor. Stream'in `default`, `forced`, `hearing_impaired`, `comment`, `descriptions` gibi `disposition` bayrakları `SubtitleStream` modeline hiç taşınmıyor. Seçim penceresi de desteklenen stream'ler içinde dili İngilizce olan **ilk** kaydı varsayılan yapıyor.

Bu nedenle aşağıdaki yaygın sıra ayırt edilemiyor:

```text
#2 eng — English Forced
#3 eng — English SDH
#4 eng — English Full [default]
```

Güncel seçim #2'dir; tam diyalog taşıyan #4 değildir. Başlıktaki `Forced`, `SDH` veya `Commentary` sözcüğü yalnız kullanıcıya gösterilen label içinde kalır, sıralama kararına girmez.

**Etki:** Kullanıcı varsayılan seçimi onaylarsa yalnız yabancı konuşmaları içeren forced track, işitme engelliler için etiketli SDH track veya yorumcu track'i kaynak olur. Program daha sonra bunu normal film altyazısı gibi analiz edip API harcar; sonuç eksik ya da yanlış program içeriğine ait olabilir. Kullanıcı seçim ekranında elle düzeltebildiği için bu madde P2'dir, ancak varsayılan davranış güvenli değildir.

**Düzeltme ölçütü:** `ffprobe` çağrısı gerekli stream disposition alanlarını istemeli ve `SubtitleStream` bunları taşımalıdır. Varsayılan sıralama en az şu şekilde olmalıdır: tam + default + non-forced + non-commentary + non-SDH; ardından normal tam track; en son forced/SDH/commentary. Başlık heuristiği yalnız disposition eksikse ikincil kanıt olmalıdır. Forced, SDH ve commentary seçimi arayüzde görünür uyarı vermelidir.

**Kabul testleri:** `[eng forced, eng full default]` dizisinde full/default seçilmeli; `[eng commentary, eng full]` dizisinde full seçilmeli; yalnız forced varsa seçilebilir ama açık uyarı göstermeli; dil tercihi olmayan tek normal stream mevcut davranışı korumalıdır.

---

## 28. Manuel `JSONL → SRT`, JSONL'nin seçilen kaynak dosyaya ait olduğunu doğrulamıyor

**Kod:** `subtitle_translator_gui.py:27144-27372`

**Kök neden:** Manuel dönüştürücü kullanıcıdan bağımsız olarak bir batch output JSONL ve bir kaynak SRT seçtiriyor. JSONL içindeki sonuçlar yalnız `custom_id`/cue ID kümesiyle kaynak cue ID'lerine yerleştiriliyor. Companion input JSONL, batch fmap/manifest, kaynak SHA-256, özgün dosya yolu veya request body hash'i doğrulanmıyor. Filmlerin çoğunda ID'ler `1..N` olduğu için başka filmin JSONL'si yapısal olarak tamamen uyumlu görünebilir.

**Saf karşı örnek:** Kaynak B şu iki cue'yu taşıdı:

```text
1  How are you?
2  Please stop.
```

Başka bir filme ait JSONL-benzeri sonuçlar ise:

```text
1  Merhaba.
2  Dur lütfen.
```

Güncel ID yerleştirmesiyle çıktı üretildi; upload-ready hazırlama ve nihai teslim denetimi sonrasında sonuç:

```text
status                         = ok
hard error                     = False
delivery_owner_mismatch_ids    = []
missing source cue             = []
```

Yani zaman damgaları ve cue sayıları kaynak B'den geldiği için yapısal audit yanlış filme ait genel cümleleri ayırt edemedi.

**Etki:** Yanlış indirilen/isimlendirilen JSONL, seçilen filmin zamanlarına uygulanıp `Tamamlandı` bildirimi alabilir. Bu yalnız birkaç cue kayması değil, bütün filmin başka içerikle sessizce eşlenebilmesidir. Son audit genel cümlelerde sayı/özel-ad çapraz kanıtı bulamayacağı için güvenilir bir provenance yerine geçemez.

**Düzeltme ölçütü:** Manuel import, batch oluşturulurken yazılmış doğrulanabilir fmap/manifest veya companion input JSONL istemelidir. Kaynak SHA-256, request custom-ID sahipliği ve beklenen cue/source hash'i eşleşmeden final yazılmamalıdır. Eski provenance'sız JSONL'ler desteklenecekse yalnız `doğrulanmamış kaynak` olarak kısmi/inceleme çıktısı üretmeli; source fingerprint, completion veya upload-ready işareti yazmamalıdır.

**Kabul testleri:** Source A'ya bağlı JSONL ile Source B seçildiğinde yazımdan önce fail-closed olmalı; aynı Source A seçildiğinde dönüşüm sürmeli; yalnız ortak `1..N` ID'leri provenance kanıtı sayılmamalıdır.

---

## 29. Aynı dizinin ayrı `Episode N` klasörlerindeki bölümleri ortak Dizi Hafızası ve Sezon Kanonu kullanmıyor

**Kod:**

- `series_memory.py:103-142,145-160`
- `subtitle_translator_gui.py:22320-22344,27775-27805,28477-28505`

**Kök neden:** `parse_series_key`, dosya adındaki `S01E01`/`S01E02` bilgisinden iki dosyayı doğru biçimde aynı `slug` ve sezona bağlayabiliyor. Ancak `_tv_root_info` ebeveyn klasör adında yalnız tanınan TV/sezon kalıbı bulamazsa `series_memory_root` doğrudan dosyanın **hemen üst klasörünü** döndürüyor. Tek tek seçilen dosyalarda `_series_mem_for` ve `_season_canon_groups`, seçili ortak kök yerine bu değeri kullanıyor.

**Saf karşı örnek:** Güncel saf fonksiyon sonucu:

```text
X:\Show\Episode 1\Show.S01E01.srt
  parse_series_key  = ('show', 1, 1)
  memory root       = X:\Show\Episode 1

X:\Show\Episode 2\Show.S01E02.srt
  parse_series_key  = ('show', 1, 2)
  memory root       = X:\Show\Episode 2

same root           = False
```

`_season_canon_groups` grup anahtarına bu farklı mutlak kökü de kattığı için iki bölüm aynı dizinin aynı sezonu olsa bile grup boyutu 1'de kalır ve sezon kanonu hiç başlamaz. `SeriesMemory.load` da ayrı klasörlerde ayrı bellek dosyaları açar.

**Etki:** Önceki bölümde öğrenilen karakter adı, terim, `sen/siz` kararı ve üslup sonraki bölüme taşınmaz. Kullanıcı “Dizi Hafızası” ve “Sezon Sonu Kanon Denetimi” açık görse de bölüm klasörü düzenine bağlı olarak özellikler sessizce parçalanır. Özellikle her bölümün ayrı klasörde tutulduğu gerçek teslim düzeninde sezon tutarlılığı güvence altında değildir.

**Düzeltme ölçütü:** Bellek kimliği fiziksel immediate-parent yerine doğrulanmış dizi kimliğiyle bağlanmalıdır. Tek tek seçilen dosyalarda aynı normalize `slug+season` taşıyan sibling episode klasörleri güvenli ortak ataya bağlanmalı; farklı diziler yalnız ortak klasörde bulundukları için birleşmemelidir. Seçili klasör kökleri/common ancestor ancak slug doğrulamasıyla kullanılmalıdır.

**Kabul testleri:** Yukarıdaki sibling `Episode 1/2` örneği aynı SeriesMemory konumunu ve sezon-canon grubunu kullanmalı; `Other.Show.S01E01` aynı ortak atada olsa bile ayrı kalmalı; tanınan `show.tv.s01` ve `Season 1` klasör düzenlerinin mevcut testleri bozulmamalıdır.

---

## 30. Gerçek bir `movie.tr.srt` kaynak dosyası program çıktısı sanılıp hiç keşfedilmiyor

**Kod:**

- `subtitle_formats.py:30-32,1031-1043,1046-1129`
- `subtitle_batch_translate.py:280-305`

**Kök neden:** `is_generated_subtitle_name`, adı `.tr.srt` ile biten **her** dosyayı provenance, komşu kaynak, sidecar veya çıktı kökü kontrolü olmadan program artifact'ı sayıyor. Bu yardımcı hem GUI klasör taramasında hem standalone batch taramasında kullanılıyor. Oysa `.tr.srt`, internetten indirilmiş veya kullanıcı tarafından adlandırılmış meşru bir Türkçe altyazının çok yaygın dil etiketidir.

**Saf karşı örnek:** Güncel yardımcı sonucu:

```text
is_generated_subtitle_name('movie.tr.srt')        = True
is_generated_subtitle_name('movie.eng.srt')       = False
is_generated_subtitle_name('movie.tr-forced.srt') = False
```

Dolayısıyla aynı klasördeki `movie.tr.srt`, izin verilen `.srt` uzantısına sahip olsa da `get_subtitle_files` ve standalone discovery sonucuna hiç girmez.

**Etki:** Türkçe kaynak altyazıyı İngilizce/Almanca gibi başka bir hedefe çevirmek isteyen kullanıcı dosyayı klasörden ekleyemez; dosya sessizce yokmuş gibi görünür. Ayrıca gerçek kaynak arşivi/haricî araç çıktısı yalnız adı `.tr.srt` olduğu için tamamlanma envanterinden düşebilir. Kendi çıktısını yeniden almama koruması gerekli olsa da salt dosya adına dayalı karar meşru girdiyi feda ediyor.

**Düzeltme ölçütü:** `.tr.srt` ancak uygulamanın kendi sidecar/fingerprint'iyle bağlıysa, aynı-klasör çıktısı olarak komşu kaynakla kanıtlanıyorsa veya açık bir output ağacındaysa generated sayılmalıdır. Provenance yoksa dosya normal kaynak olmalı; kuşkulu aynı-klasör çifti ön kontrolde kullanıcıya açıklanmalıdır.

**Kabul testleri:** İzole klasördeki yalnız `movie.tr.srt` keşfedilmeli; programın gerçekten ürettiği `movie.tr.srt` fingerprint/komşu kaynak kanıtıyla dışlanmalı; `.partial.srt`, `.ham.srt` ve `.stage.srt` korumaları değişmeden kalmalıdır.

---

## 31. Çıktı resolver hedef dili bilmediği için farklı hedef diller aynı yolu paylaşabiliyor

**Kod:** `subtitle_translator_gui.py:5989-6014`

**Kök neden:** `_resolve_output_path` fonksiyonunun hedef dil parametresi yok. Aynı-klasör modunda kaynak zaten SRT ise output adını koşulsuz `f"{src.stem}.tr.srt"` yapıyor; normal output klasöründe ise bütün hedef diller aynı `output_name` ve klasör yolunu paylaşıyor. Dolayısıyla hedef dil seçimi yalnız dosya adına değil, çıktı kimliğine hiçbir zaman yansımıyor.

**Saf karşı örnek:** Aynı kaynak ve aynı-klasör ayarında çözümleyicinin sonucu hedef dil bilgisinden bağımsızdır:

```text
source = Film.tur.srt
target = German  -> Film.tur.tr.srt
target = French  -> Film.tur.tr.srt
target = English -> Film.tur.tr.srt
```

Fonksiyon bu üç çağrıyı ayırt edecek bir argüman bile almıyor. Ayrı output klasöründe de üçü aynı `<output>/<source-key>/<source-key>.srt` yoluna çözülüyor.

**Etki:** Haricî oynatıcı, medya sunucusu veya yükleme aracı `.tr` dil etiketine güvenirse Almanca/Fransızca/İngilizce altyazıyı Türkçe sanır. Aynı dosya daha sonra bu uygulamaya verilirse 30. maddede açıklanan generated-artifact filtresine de düşer. Daha önemlisi, kullanıcı aynı kaynağı önce Almanca sonra Fransızca çevirdiğinde normal output modunda da ikinci çalışma aynı final yolunu hedefleyip ilk dili arşiv/overwrite akışına sokabilir; iki dil ayrı teslim artifact'ı olarak korunmaz.

**Düzeltme ölçütü:** Çıktı resolver hedef dili açık parametre olarak almalı ve bütün output kimliğini ISO-639-1 etiketiyle ayırmalıdır (`.de.srt`, `.fr.srt`, `.en.srt`, `.tr.srt` veya hedefe özel klasör). Aynı kaynak-hedef-yol çakışması ön kontrolünde hedef dili de kimliğe katmalıdır. Eski `.tr.srt` dosyaları yalnız doğrulanmış provenance ile legacy output sayılmalıdır.

**Kabul testleri:** Turkish/German/French hedefleri aynı kaynak için sırasıyla üç farklı `.tr/.de/.fr.srt` yolu üretmeli; aynı hedefin yeniden çalışması aynı kararlı yolu kullanmalı; kaynak zaten `film.de.srt` iken German hedefi kaynakla çakışmayacak ayrı ve açık bir output adı üretmelidir.

---

## 32. Fuzzy TM, anlamı değiştiren noktalama farkını semantik olarak eşdeğer sayıyor

**Kod:**

- `translation_memory.py:62-80` — `_normalized_semantic_tokens`, `_fuzzy_semantically_compatible`
- `translation_memory.py:365-436` — `fuzzy_lookup`
- `subtitle_translator_gui.py:32782-32809` ve `hybrid_translate.py:13804-13828` — üretimde `%95` fuzzy reuse

**Kök neden:** Fuzzy semantik kapısı kaynak/candidate içinden yalnız word token'larını çıkarıyor; virgül, iki nokta, tire ve diğer noktalama tamamen yok oluyor. Ardından `SequenceMatcher` ham normalize metindeki farkı oranla ölçse de bir-iki virgül farkı uzun cümlede `%95` eşiğinin rahatça üstünde kalıyor. Oysa hitap virgülü veya yan cümle sınırı özne/nesneyi değiştirebilir.

**Saf ve uçtan uca karşı örnek:** Aynı TM context fingerprint'i altında şu kaynak kaydedildi:

```text
Lets eat, Grandma! -> Buyukanneni yiyelim!
```

Ardından şu farklı kaynak `%95` üretim eşiğiyle sorgulandı:

```text
Lets eat Grandma!
```

Güncel sonuç:

```text
semantic tokens equal = True
similarity            = 0.9714285714
fuzzy lookup          = ('Buyukanneni yiyelim!', 0.9714285714)
```

Başka anlam-değiştiren örnekler de aynı kapıdan geçti: `Please help, Jack, off the horse.` / `Please help Jack off the horse.` (`0.96875`) ve `I enjoy cooking, my family, and my dog.` / `I enjoy cooking my family and my dog.` (`0.97368`).

**Etki:** Eski çeviri, yeni cue için ana modeli tamamen bypass eder. Noktalamanın hitabı, listeyi veya nesneyi değiştirdiği yerlerde kaynak tokenları aynı olduğu için mevcut kişi/sayı/negasyon çapaları da farkı göremez. Sonraki pass'ler kaynakla karşılaştırsa bile TM'den gelen akıcı fakat yanlış cümle deterministik olarak şüpheli seçilmeyebilir.

**Önceki fuzzy raporundan farkı:** Önceki dışlama belgelerinde word-token dizisinin birebir eşit olması nedeniyle fuzzy reuse'un **fazla katı** kalması raporlandı. Buradaki hata, token dizisi aynıyken anlam belirleyen noktalamanın kaybolması nedeniyle reuse'un **fazla gevşek** olmasıdır. Önceki düzeltme token eşitliğini gevşetirse bu koruma ayrıca eklenmezse risk büyür.

**Düzeltme ölçütü:** Fuzzy uygunluk, anlam taşıyan noktalama yapısını da karşılaştırmalıdır: en az hitap virgülü, cümle/yan-cümle sınırı, soru/ünlem ve diyalog tireleri. Güvenli tipografik varyantlar (`'`/`’`, üç nokta biçimi) normalize edilebilir; noktalama ekleme/silme yalnız dilsel olarak anlamsız olduğu kanıtlanırsa reuse edilmelidir. Belirsiz durumda fuzzy miss ve normal model çağrısı güvenli varsayımdır.

**Kabul testleri:** Yukarıdaki üç çift `%95+` karakter benzerliğine rağmen fuzzy miss olmalı; yalnız akıllı/düz apostrof veya eşdeğer üç nokta varyantı reuse edebilmeli; mevcut sayı, kişi, zaman ve içerik-kelimesi drift regresyonları korunmalıdır.

---

## 33. Manuel `JSONL → SRT` global çalışma sahipliği ve output baseline korumasını atlıyor

**Kod:**

- `subtitle_translator_gui.py:15975-16005` — process-wide `_claim_translation_run_owner`
- `subtitle_translator_gui.py:22696-22718` — `_set_running` yalnız UI durumunu değiştirir; claim yapmaz
- `subtitle_translator_gui.py:27144-27417` — manuel JSONL akışı

**Kök neden:** Normal başlangıç ve batch resume, ücretli/çıktı-yazan worker başlamadan `_claim_translation_run_owner()` çağırıyor. Manuel JSONL akışı ise dosya seçimlerinden sonra doğrudan `_set_running(True)` yapıp worker başlatıyor. Akış Polish ve eksik-cue API onarımı çalıştırabildiği ve doğrudan `write_srt` ile kullanıcı seçtiği yola yazdığı hâlde process-wide sahiplik kilidine katılmıyor. Save dialogundan sonra alınmış bir output content/hash baseline'ı da son yazımdan önce doğrulanmıyor.

**Etki:** İki uygulama penceresinde normal çeviri/batch ve manuel JSONL eşzamanlı çalışabilir. Aynı SRT yolu seçilmişse uzun Polish/onarım sırasında diğer akışın veya kullanıcının yazdığı yeni final, JSONL worker'ının elindeki eski bloklarla sessizce ezilebilir. Farklı hedeflerde bile ortak token/run UI durumu ve dosya raporları aynı sahiplik sözleşmesinin dışında kalır.

**Neden 28. maddeyle aynı değil:** 28, JSONL içeriğinin **yanlış kaynak filme** ait olmasını doğrulamayan provenance açığıdır. Bu madde JSONL doğru filme ait olsa bile eşzamanlı çalışan başka writer'a karşı output sahipliği ve son-yazım bütünlüğünün bulunmamasıdır.

**Düzeltme ölçütü:** Manuel import, bütün dosyalar seçildikten sonra ve herhangi bir worker/API çağrısından önce global run owner'ı claim etmelidir; başarısız claim görünür biçimde işlemi durdurmalıdır. Save hedefinin başlangıç fingerprint/content baseline'ı alınmalı, nihai yazımdan hemen önce aynı olduğu doğrulanmalıdır. Sahiplik `finally` içinde yalnız bu akışın claim ettiği handle için bırakılmalıdır.

**Kabul testleri:** Owner başka run tarafından tutuluyorsa JSONL worker/API/yazım hiç başlamamalı; JSONL çalışırken normal Start claim edememeli; save seçiminden sonra hedef dışarıdan değişirse eski bloklar yazılmamalı ve iki sürüm de korunmalıdır.

---

## 34. Aynı dosyadaki özdeş kaynak cue'lar exact TM'de tek bağlamsız çeviriye çöküyor

**Kod:**

- `translation_memory.py:248-257` — `_hash`
- `translation_memory.py:300-363` — `lookup_batch`
- `translation_memory.py:474-515` — `store_batch`
- `subtitle_translator_gui.py:32773+` — üretim exact-TM lookup
- `subtitle_translator_gui.py:23378+` — üretim TM store

**Kök neden:** Exact TM anahtarı normalize kaynak metni, hedef dili ve bütün dosyaya ait context fingerprint'i kapsıyor; cue'nun yerel konuşmacısını, önceki/sonraki repliğini veya sahne içindeki anlamını kapsamıyor. Aynı kaynak metin aynı dosyada iki farklı doğru Türkçe karşılığa sahipse iki kayıt da aynı `hash` değerini üretir. `INSERT OR REPLACE` ikinci kaydı birincinin üzerine yazar; `lookup_batch` da bütün özdeş kaynak örneklerini tek sözlük anahtarına indirger.

**Saf ve veritabanlı karşı örnek:** Aynı model, hedef dil, şema ve `same-file-context` altında şunlar toplu kaydedildi:

```text
Right. -> Sağ.     (yön sorusunun cevabı)
Right. -> Doğru.   (bir önermeyi onaylama)
```

Güncel SQLite sonucu yalnız bir satırdır:

```text
source = Right.
target = Doğru.
```

Ardından `lookup_batch(['Right.', 'Right.'], ...)` yalnız `{'Right.': 'Doğru.'}` döndürür. İlk cue'nun yön anlamı ve doğru `Sağ.` çevirisi kaybolur.

**Etki:** `Right.`, `Fine.`, `You.`, `Go on.`, `There.` gibi bağlama duyarlı kısa tekrarlar yeniden çalıştırmada model çağrısını bypass ederek filenin her yerinde son kaydedilen tek karşılığa dönüşebilir. Akıcı ve kısa oldukları için Critic veya final tarama bunları deterministik olarak şüpheli seçmeyebilir.

**Neden 26. maddeden ayrı:** 26. madde dosya düzeyindeki proje/dizi/analiz bağlamı değiştiği hâlde fingerprint'in değişmemesidir. Burada bütün dosya ayarları ve fingerprint aynı kalsa bile **tek dosyanın kendi içinde** aynı metnin iki yerel anlamı vardır; dosya düzeyinde daha geniş fingerprint eklemek çarpışmayı çözmez.

**Düzeltme ölçütü:** Exact final reuse anahtarına kararlı cue-yerel semantik bağlam eklenmelidir: en az konuşmacı, komşu kaynak cue'lar ve sahne kimliği/fragment grubu. Alternatif güvenli kapı, aynı dosyada özdeş kaynak için birden çok kabul edilmiş hedef görülürse o kaynak üzerinde exact final reuse'u devre dışı bırakıp normal modele bırakmaktır. `lookup_batch` sonucu kaynak metin sözlüğü yerine cue kimliğiyle eşleşebilmelidir.

**Kabul testleri:** Aynı dosyadaki iki `Right.` farklı komşu bağlamlarla sırasıyla `Sağ.` ve `Doğru.` olarak saklanıp ayrı geri dönmeli; gerçekten aynı bağlamlı tekrarlar reuse edebilmeli; mevcut model/hedef/schema/context izolasyonu korunmalıdır.

---

## 35. Baş harfi büyük sıradan sözcüklerin kimlik eşlemesi kalıcı “çevirme” kilidine dönüşebiliyor

**Kod:**

- `project_memory.py:64-70` — `is_self_translation`
- `project_memory.py:188-204` — `update_glossary`, `merge_glossary_from_analysis`
- `series_memory.py:364-384` — `merge_terms`
- `hybrid_translate.py:6980-7005,7007+` — kimlik kilidi ve Türkçe sözlük sanitizasyonu
- `subtitle_translator_gui.py:28482+` — proje terimlerinin kilitli terimlere katılması
- `subtitle_translator_gui.py:32245,32305,34500,38668` — analiz terimlerinin dizi/proje hafızasına alınması

**Kök neden:** Proje ve dizi hafızasının kaynak==hedef filtresi yalnız kaynak string tamamen küçük harfliyse kimlik eşlemesini reddediyor. Bu nedenle cümle başında veya analiz modelinin başlık biçiminde döndürdüğü `Camera -> Camera`, `Train -> Train`, `Doctor -> Doctor` gibi sıradan İngilizce sözcükler “büyük harf içeriyor, demek ki özel ad/kısaltma olabilir” varsayımıyla kalıcı hafızaya giriyor. Türkçe sözlük sanitizasyonu yalnız sınırlı bilinen-kötü/exonym listesine bakıyor; bu genel sözcükleri kimlik eşlemesi olarak koruyor.

**Saf karşı örnek:** Güncel sonuçlar:

```text
is_self_translation('camera', 'camera') -> True   (reddedilir)
is_self_translation('Camera', 'Camera') -> False  (saklanır)
is_self_translation('Train', 'Train')   -> False  (saklanır)
is_self_translation('TRAIN', 'TRAIN')   -> False  (saklanır)

sanitize_glossary_for_turkish({'Camera': 'Camera'}) -> {'Camera': 'Camera'}
sanitize_glossary_for_turkish({'Train': 'Train'})   -> {'Train': 'Train'}
```

Proje hafızası bu girişleri `PROJE TERİMLERİ (bu çeviride tutarlı kullan)` altında prompta taşır; `_get_locked_terms_dict` de proje terimlerini sonraki kalite guard'larında kilitli kabul eder.

**Etki:** Analiz modelinin tek bir baş-harf biçimi hatası bölüm/film sonrasına kalıcılaşabilir. Sonraki cue'larda `Camera`, `Train` veya `Doctor` İngilizce bırakılır; kilitli-terim kontrolleri bunun Türkçeleştirilmesini ihlal sayabilir. Dizi hafızasında hata sonraki bölümlere de taşınır.

**Neden önceki auto-proper-noun raporundan ayrı:** Önceki dışlama raporu tekrarlanan büyük harfli Unicode tokenların `auto_locked_proper_nouns` tarafından otomatik özel ad sayılmasıydı. Burada terim analizinden gelen kaynak-hedef sözlük çifti ProjectMemory/SeriesMemory'nin kendi self-translation filtresinden geçip kalıcı kanona dönüşüyor; auto-lock kapalı olsa da oluşur.

**Düzeltme ölçütü:** Kimlik eşlemesinin korunması yalnız pozitif özel-ad/kısaltma kanıtıyla mümkün olmalıdır; “tamamı küçük değil” tek başına kanıt sayılmamalıdır. Genel isim/meslek/nesne filtresi büyük-küçük harften bağımsız çalışmalı. Belirsiz tek sözcüklü kimlik eşlemesi kilitli glossary yerine rapor/inceleme alanına alınmalıdır.

**Kabul testleri:** `Camera/Train/Doctor -> aynı değer` proje ve dizi hafızasına girmemeli; `Ayn Rand`, doğrulanmış `Killface` karakter adı ve `IQ` gibi gerçek özel ad/kısaltmalar korunmalı; case-only varyantlar aynı politika sonucunu üretmelidir.

---

## 36. Unicode bakımından eşdeğer dizi ve terim adları ayrı hafıza/kanon anahtarlarına dönüşüyor

**Kod:**

- `series_memory.py:48-52` — `_slugify`
- `series_memory.py:76-80` — `_term_identity`
- `series_memory.py:145-172` — `parse_series_key`
- `series_memory.py:364-384` — `merge_terms`

**Kök neden:** Dizi slug'ı ve terim kimliği Unicode canonical normalization (`NFC`/`NFKC`) uygulamıyor. `_slugify`, ayrışmış yazımdaki combining accent karakterini `[^\w\s-]` ile silerken birleşik `é` harfini koruyor. `_term_identity` ise iki yazımı ayrı casefold string olarak saklıyor. Windows/indirme araçları görsel olarak aynı adı NFC veya NFD biçiminde ayrı ayrı üretebilir.

**Saf karşı örnek:** Görsel ad iki dosyada da `Café` olmasına rağmen:

```text
parse_series_key('Cafe\u0301.S01E01.srt') -> ('cafe', 1, 1)
parse_series_key('Caf\u00e9.S01E02.srt')  -> ('café', 1, 2)

NFC('Cafe\u0301') == NFC('Caf\u00e9')   -> True
slug equality                            -> False

_term_identity('Cafe\u0301') -> 'folded:café'
_term_identity('Caf\u00e9')  -> 'folded:café'
```

**Etki:** Aynı dizinin bölümleri iki farklı `.series_memory/<slug>.json` kanonuna ayrılabilir. Aynı terimin birleşik/ayrışmış biçimleri farklı hedeflerle iki kez saklanıp promptta çelişkili sabit terimler olarak görünebilir. Sezon sonu kanon taraması da tek diziyi iki grup sanabilir.

**Neden 29. maddeden ayrı:** 29. madde aynı slug'a sahip dosyaların fiziksel sibling bölüm klasörleri nedeniyle farklı **hafıza köklerine** ayrılmasıdır. Burada fiziksel kök aynı olsa bile Unicode-equivalent dizi adı iki farklı **slug/term kimliği** üretir.

**Düzeltme ölçütü:** Slug, term identity ve origin key üretmeden önce tek bir belgelenmiş Unicode normalizasyonu uygulanmalıdır. Aksanları silmek isteniyorsa birleşik ve ayrışmış biçimler aynı transliterasyon yolundan geçmeli; aksan korunacaksa ikisi de aynı NFC string olmalıdır. Mevcut kayıtlar yüklenirken canonical anahtara güvenli merge/migrasyon yapılmalıdır.

**Kabul testleri:** Yukarıdaki iki dosya aynı `slug`, hafıza yolu ve sezon grubunu üretmeli; `Café/Café` terimleri tek canonical giriş olmalı; Türkçe `İ/ı`, gerçek farklı adlar ve büyük-küçük harfe duyarlı kısaltma ayrımı için mevcut regresyonlar korunmalıdır.

---

## 37. Numaralı SRT cue'sundaki görünür zaman kodu satırı yeni cue sanılıyor

**Kod:**

- `subtitle_localizer/srt.py:13-16` — `_TIME_RE`
- `subtitle_localizer/srt.py:31-40` — `_cue_start`
- `subtitle_localizer/srt.py:52-67` — cue gövdesi taraması
- `subtitle_formats.py:1017-1023` — bütün `.srt` kaynakların bu parser'a yönlendirilmesi

**Kök neden:** Parser hem numaralı hem numarasız SRT'yi desteklemek için zaman damgasına benzeyen **her satırı** koşulsuz yeni cue başlangıcı sayıyor. Mevcut cue numaralı ve geçerli bir blok içindeyken bile boş ayraç/sonraki cue kimliği aramıyor. Dolayısıyla teknik belgesel, ekran kaydı veya filmde görünür metin olarak geçen tam bir timecode satırı diyalog metni olamıyor.

**Saf karşı örnek:** Geçerli numaralı SRT bloğu:

```srt
1
00:00:01,000 --> 00:00:06,000
The screen says:
00:10:00,000 --> 00:20:00,000
Do not copy that timecode.

2
00:00:07,000 --> 00:00:09,000
Next line.
```

Güncel parser sonucu:

```text
1 | 00:00:01–00:00:06 | The screen says:
2 | 00:10:00–00:20:00 | Do not copy that timecode.
3 | 00:00:07–00:00:09 | Next line.
```

Görünür `00:10:00...` metni yok olmuş, aynı cue'nun devamı on dakika aralığına taşınmış ve cue sırası kronolojik olarak da bozulmuştur.

**Etki:** Kaynak anlam ve zaman sahipliği API çağrısından önce değişir. Kaynak ve hedef denetimi aynı yanlış parse sonucunu kullandığında yeni sentetik cue “kaynakta da var” görünür; normal source-target timestamp karşılaştırması hatayı mutlaka yakalamaz.

**Düzeltme ölçütü:** Parser dosyanın numaralı/numarasız modunu ve blok sınırını izlemelidir. Numaralı bir cue gövdesindeyken yeni başlangıç, normalde blank separator ardından `ID + timestamp` ile kanıtlanmalı; tek başına timestamp benzeri metin mevcut cue'nun görünür satırı olarak kalmalıdır. Toleranslı numarasız mod yalnız ayrı ve açık fallback olarak uygulanmalıdır.

**Kabul testleri:** Yukarıdaki blok iki cue üretmeli ve timecode satırı cue 1 metninde kalmalı; gerçek numarasız SRT hâlâ parse edilmeli; boş ayraçsız fakat numaralı ardışık cue toleransı korunacaksa yalnız `numeric ID + timestamp` çiftiyle ayrılmalıdır.

---

## 38. Latin dışı alfabelerdeki köşeli-parantezli gerçek ekran yazıları SDH sanılıp siliniyor

**Kod:**

- `sdh_cleaner.py:245-248` — `_ascii_fold`
- `sdh_cleaner.py:419-428` — `is_sdh_descriptor`
- `sdh_cleaner.py:976-1022` — `src_is_sfx_only`
- `sdh_cleaner.py:1314-1365` — kaynak-güdümlü `clean_sdh_blocks`

**Kök neden:** `is_sdh_descriptor`, içerik ASCII'ye indirgenince boş kalıyorsa ve çağrı `bare_text=False` ise bunu koşulsuz SDH descriptor kabul ediyor. Köşeli parantez yalnızca ses betimlemelerinde değil yer, başlık, tabela, mektup veya ekranda görünen metinde de kullanılabilir. Japonca/Kiril/Arapça bir sözcüğün ASCII karşılığı doğal olarak boş olduğu için içerik hakkında hiçbir SDH kanıtı olmadan `True` dönüyor. Kaynak-güdümlü temizlik de bu kararı `src_is_sfx_only` üzerinden bütün cue'yu düşürmek için kullanıyor.

**Saf karşı örnek:** Aşağıdaki kaynak-hedef çiftleri ayrı ayrı kaynak-güdümlü SDH temizliğine verildi:

```text
source [東京]    -> target [Tokyo]
source [Москва] -> target [Moskova]
source [مرحبا]  -> target [Merhaba]
```

Güncel sonuç:

```text
is_sdh_descriptor('東京')    -> True
is_sdh_descriptor('Москва') -> True
is_sdh_descriptor('مرحبا')  -> True

src_is_sfx_only('[東京]')    -> True
src_is_sfx_only('[Москва]') -> True
src_is_sfx_only('[مرحبا]')  -> True

clean_sdh_blocks(..., source_driven=True) -> []
```

Üç doğru çeviri de final blok listesinden tamamen silindi.

**Etki:** Japonca, Rusça, Arapça ve diğer Latin dışı kaynaklardaki anlamlı ekran kartları, yer adları veya yazılı diyaloglar API'de doğru çevrilmiş olsa bile teslim temizliğinde sessizce kaybolur. Kaynak denetimi de aynı cue'yu “beklenen SDH kaldırması” olarak görebildiğinde eksik-timestamp kontrolü bunu meşru kayıp sayabilir.

**Neden 3. maddeden ayrı:** 3. madde doğru **hedef** yazı sisteminin nihai audit tarafından yabancı alfabe sayılıp karantinaya alınmasıdır. Burada hedef Türkçe/Latin olsa bile **kaynağın** Latin dışı parantezli içeriği SDH sınıflandırmasıyla cue listesinde fiziksel olarak silinir.

**Düzeltme ölçütü:** ASCII'ye indirgenememe tek başına descriptor kanıtı olmamalıdır. Parantezli Latin dışı metin ancak dile özgü pozitif ses/konuşmacı işareti, müzik sembolü veya açık yapısal SDH kanıtıyla silinmelidir; belirsiz içerik korunup raporlanmalıdır.

**Kabul testleri:** Yukarıdaki üç kaynak-hedef çifti korunmalı; gerçek `[МУЗЫКА]`, `[拍手]` ve `[موسيقى]` gibi pozitif SDH örnekleri desteklenen sözlük/yapısal kanıtla kaldırılmalı; karışık `東京 — music` ve çok satırlı bracket örnekleri ayrı ayrı doğrulanmalıdır.

---

## 39. WebVTT ruby okunuşu ana metne yapışarak kaynak anlamını çoğaltıyor

**Kod:**

- `subtitle_formats.py:23-26` — `_VTT_SRT_UNSAFE_TAG`
- `subtitle_formats.py:83-95` — `clean_translation_source_text`
- `subtitle_formats.py:736-780` — `_VTT_TAG`, `_clean_vtt_text`
- `subtitle_translator_gui.py:6680-6682` — ana istek öncesi `_clean_src`

**Kök neden:** Güncel regex `<ruby>`, `<rt>` ve kapanış etiketlerini çıkarıyor fakat `<rt>...</rt>` öğesinin **içeriğini** çıkarmıyor. Ruby'de `rt` metni bağımsız diyalog değil, ana yazının okunuş açıklamasıdır. Yalnız tag kabukları silinince ana sözcük ve telaffuz aralarında ayraç olmadan birleşiyor.

**Saf karşı örnek:** 

```html
<ruby>東京<rt>とうきょう</rt></ruby>
I live in <ruby>Tokyo<rt>とうきょう</rt></ruby>.
```

Güncel temizleme sonucu:

```text
東京とうきょう
I live in Tokyoとうきょう.
```

Hem `clean_translation_source_text`, hem `_clean_vtt_text`, hem de gerçek ana-istek yolu `_clean_src` aynı sonucu verdi.

**Etki:** Japonca/Asya WebVTT kaynaklarında model ana metin ile furigana/okunuşu tek sözcük sanabilir; özel ad iki kez çevrilebilir, yabancı kalıntı veya anlamsız birleşik token oluşabilir. Bu bozulma API çağrısından önce gerçekleştiği için sonraki kaynak-hedef denetimleri de yanlış temizlenmiş kaynağı esas alabilir.

**Neden eski ruby/rt bulgusundan ayrı:** Dışlama belgesindeki bug, `ruby/rt` etiketlerinin SRT finale ham olarak geri yazılmasıydı ve regex'e bu etiketlerin eklenmesini öneriyordu. Güncel kod o öneriyi uygulamış durumda; bu yeni karşı örnek, yalnız etiketi silmenin `rt` **içeriğini** ana metne yapıştırdığını gösteren ayrı bir kaynak-anlam kaybıdır.

**Düzeltme ölçütü:** VTT temizliğinde önce bütün `<rt ...>...</rt>` alt ağacı içeriğiyle birlikte kaldırılmalı, ardından `<ruby>` kabuğu çıkarılıp yalnız base text korunmalıdır. Regex yaklaşımı kullanılacaksa iç içe/çoklu ruby örnekleri ve HTML entity çözüm sırası açıkça test edilmelidir.

**Kabul testleri:** Yukarıdaki örnekler sırasıyla `東京` ve `I live in Tokyo.` üretmeli; bir cue'daki iki ruby ayrı ayrı korunmalı; ruby dışındaki `<i>/<b>/<v>` davranışı ve 9/11. maddelerdeki entity/tag güvenliği gerilememelidir.

---

## Yanlış alarm olarak elenenler

- **Dosya başına Gelişmiş/Maksimum analiz cache'i:** Güncel `analysis_fingerprint`, analiz derinliği yanında source/target, model, endpoint, style, schema, glossary ve scene-gap değerlerini kapsıyor. Farklı derinliğin eski cache'i sessizce kullanıldığına dair bug bulunmadı.
- **Aynı-stem klasör taşıma:** Güncel `_output_source_fingerprint_candidates` aynı stem için tek sidecar fallback'i içeriyor. Bu rapordaki 7. madde yalnız stem de değiştiğinde oluşuyor.
- **Completion marker'ın güncel output hash'ini doğrulamaması:** Güncel `_completion_marker_groups` source+output fingerprint kontrolü yapıyor; eski 35. maddeyi yeniden raporlamadım.
- **Hedef dil parametresinin normal `write_srt` çağrılarında unutulması:** Ana yazım yollarının çağrıları `tgt`/`target_language` geçiriyor; bu turda yeni bir call-site eksikliği doğrulanmadı.
- **Kaynak arşivi ile fingerprint'in ana akışta birbirinden bağımsız başarılı sayılması:** Güncel ana yazım yolları ikisini aynı teslim/provenance kapısında kontrol ediyor; arşiv veya sidecar yazımı başarısızsa completion ilerlemiyor.
- **Eski completion marker'ın değiştirilmiş outputu sonsuza dek hazır sayması:** Marker grupları source ve output fingerprint'ini doğruluyor, başarısız grupta stale işareti temizliyor. Bu, 8. maddedeki exact marker-adı/sözleşmesi eksikliğini ortadan kaldırmıyor.
- **Batch listelemede `limit=100` yüzünden 101. batch'in kaybolması:** OpenAI SDK list sonucu iterator ile sayfalıyor; bu çağrıda tek sayfalık liste varsayımı doğrulanmadı.
- **ASS `Text` kolonunun son olmasının parser bugı olduğu şüphesi:** ASS/SSA biçiminde `Text` alanının son kolon olması gerekir; virgüllü diyalog için mevcut son-alan birleştirmesi bu noktada spec uyumlu.
- **Analiz/precontext cache'inin kaynak değişimini görmemesi:** İncelenen cache kimlikleri kaynak SHA ve ilgili analiz ayarlarına bağlı; bu turda stale cache kabulü yeniden üretilemedi.

## Önerilen düzeltme sırası

1. **Madde 1:** Gerçek eksik/hata finalinin hazır ve TM-valid sayılmasını engelle.
2. **Madde 2:** API öncesi geri döndürülemez kaynak anlam kaybını kapat.
3. **Madde 3–5:** Hedef-yazı sistemi farkındalığını final audit ve serializer'a taşı.
4. **Madde 6:** Son yazıcıdaki kısaltma/Roma rakamı mutasyonunu durdur.
5. **Madde 7:** Yeniden adlandırma sonrası provenance'ı koru.
6. **Madde 8:** Kaynak tamamlanma işareti ile gerçek upload-ready işaretini ayır.
7. **Madde 9–11:** WebVTT anlam kaybını, exact-TM semantik çarpışmasını ve desteklenmeyen HTML teslimini kapat.
8. **Madde 12–13:** Kaynak dilini içerikle doğrula; programın kendi VTT/ASS finalini yeniden kaynak almasını engelle.
9. **Madde 14:** Satır-satır rapor ve kalite haritasını bire-çok timestamp'e dayanıklı yap.
10. **Madde 15:** WebVTT yerel zamanını medya timeline'ına doğru uygula.
11. **Madde 16:** Log rotasyonundaki tekil dosya yarışını App başlangıcından izole et.
12. **Madde 17–18:** Manuel post-işlemde rapor yarışını izole et ve arşiv kaynağını hash ile seç.
13. **Madde 19–20:** ASS script saatini uygula; tamamen görünmez event'leri çevrilecek/teslim edilecek diyalogdan çıkar.
14. **Madde 21–22:** ASS wrap/drawing semantiğini override durumuyla birlikte doğru ayrıştır.
15. **Madde 23:** Nihai unvan normalizasyonunu kaynak ve kilitli özel adlarla sınırla.
16. **Madde 24:** CP1254/legacy encoding seçiminde Türkçe kanıtı güçlendir ve seçimi raporla.
17. **Madde 25:** Güvenli milisaniyesiz SRT toleransını parser'ın ortak katmanına ekle.
18. **Madde 26:** TM anahtarını dizi hitap/karakter ve proje bağlam kararlarına bağla.
19. **Madde 28:** Manuel JSONL yazımını kaynak SHA/request sahipliği doğrulamasına bağla.
20. **Madde 29:** Sibling bölüm klasörlerini slug doğrulamalı ortak dizi hafızası/kanon kökünde birleştir.
21. **Madde 27:** Gömülü stream varsayılanını disposition ve tam-track önceliğiyle seç.
22. **Madde 30–31:** Generated-output tespitini provenance'a bağla ve aynı-klasör dosya etiketini gerçek hedef dilden üret.
23. **Madde 32:** Fuzzy TM'de anlam taşıyan noktalama sınırlarını semantik uygunluk kapısına ekle.
24. **Madde 33:** Manuel JSONL'yi global run-owner ve yazım-öncesi output baseline kapısına bağla.
25. **Madde 34:** Exact TM'yi cue-yerel bağlamla ayır veya çok-anlamlı özdeş kaynaklarda final reuse'u kapat.
26. **Madde 35:** Proje/dizi terim hafızasında kimlik eşlemelerini pozitif özel-ad kanıtına bağla.
27. **Madde 36:** Dizi slug'ı ve terim kimliklerini Unicode canonical normalization ile birleştir.
28. **Madde 37:** Numaralı SRT gövdesindeki timecode görünümlü metni sentetik cue başlangıcı sayma.
29. **Madde 38:** Latin dışı parantezli metni yalnız ASCII fold boş diye SDH kabul etme; pozitif descriptor kanıtı iste.
30. **Madde 39:** WebVTT ruby'de yalnız tag kabuğunu değil `<rt>` okunuş alt ağacını da çıkar; base metni tek kez koru.

Her düzeltme ayrı regresyon testiyle yapılmalı; bu raporun kapsamı yalnız bulgu ve düzeltme ölçütüdür.

---

## ✅ UYGULAMA DURUMU (2026-08-21, Claude Opus 5)

**39 maddenin tamamı koda karşı doğrulandı ve düzeltildi. Yanlış pozitif yok.**
Test paketi: **3922 test, hepsi geçiyor** + headless GUI smoke testi.

Regresyon testleri: `tests/test_haric_audit_20260821.py` (madde 1-6),
`_b_` (9-16, 30), `_c_` (17-23), `_d_` (24-29), `_e_` (31-39), `_f_` (7, 8, 12).

Commit'ler: `1871c21`, `2b31d5c`, `271c934`, `55c25a2`, `d1db9c2`, `c050f5d`.

### Düzeltmeler

| # | Nerede | Ne yapıldı |
|---|--------|-----------|
| 1 | `subtitle_formats.py` + 4 kapı | Ortak `visible_semantic_text` / `translation_failure_reason` katmanı; `<i>[HATA]</i>`, `<i></i>`, `—` artık completion, teslim denetimi ve TM kapılarının üçünde de hata |
| 2 | `subtitle_formats.py` | `_SOURCE_HTML_TAG` allowlist'e indirildi; `<Enter>`, `<x>`, `<PRIVATE_PERSON>` korunuyor |
| 3 | `subtitle_translator_gui.py` | `_foreign_script_ids` hedef dili alıyor; Arapça/Rusça/Japonca/Korece/Çince hedefler artık sert hata değil |
| 4 | `subtitle_translator_gui.py` | Şapkalı harf sayımı yalnız Türkçe hedefte |
| 5 | `subtitle_formats.py` | ZWJ/ZWNJ ve bidi isolate anlam taşıdığı bağlamda korunuyor; Latin içi artefakt hâlâ siliniyor |
| 6 | `subtitle_translator_gui.py` | Çeviriden sağ çıkan token + Roma rakamı korunuyor; ASCII `I` ünlü uyumuyla çözülüyor (`GELDI` → `geldi`) |
| 7 | `subtitle_translator_gui.py` | Sidecar son çare olarak çıktı İÇERİK hash'iyle eşleşiyor; yeniden adlandırma provenance'ı koparmıyor |
| 8 | `subtitle_translator_gui.py` | `YÜKLEMEYE HAZIR.txt` sözleşmesi eklendi (run id + dosya + SHA-256); review/partial klasörden kaldırılıyor |
| 9 | `subtitle_formats.py` | `decode_vtt_entities`; sıra kuralı `&lt;i&gt;`'yi gerçek etiket yapmıyor |
| 10 | `translation_memory.py` | Satır yapısı doğrulanıyor; büyük/küçük duyarsızlık KASITLI olarak korundu (testle kilitli) |
| 11 | `subtitle_formats.py` | Yalnız desteklenen sarmalama etiketleri geri yazılıyor |
| 12 | `subtitle_translator_gui.py` | Dosya adı yalnız ipucu; içerik analizi otorite, çatışma loglanıyor; tek-jetonlu ad dil kodu sayılmıyor |
| 13+30 | `subtitle_formats.py` | `is_generated_subtitle_file`: belirsiz adlar KOMŞU KAYNAK kanıtı istiyor |
| 14 | `subtitle_translator_gui.py` | Aynı zaman damgalı cue'lar sırayla eşleniyor |
| 15 | `subtitle_formats.py` | `X-TIMESTAMP-MAP` medya ofseti (33-bit sarma dâhil) |
| 16 | `subtitle_translator_gui.py` | Log rotasyonunda `stat()` yarışı izole |
| 17 | `subtitle_translator_gui.py` | Rapor sıralamasında `stat()` yarışı izole |
| 18 | `subtitle_translator_gui.py` | Arşiv kaynağı `source_sha256` ile seçiliyor; belirsizse fail-closed |
| 19 | `subtitle_formats.py` | `[Script Info] Timer` çarpanı uygulanıyor |
| 20 | `subtitle_formats.py` | Saydam stil ve `\alpha&HFF&` metni teslime çıkmıyor |
| 21 | `subtitle_formats.py` | `\n` yalnız WrapStyle 2'de satır sonu |
| 22 | `subtitle_formats.py` | `\p1…\p0` çizim koordinatları metinden ayıklanıyor |
| 23 | `subtitle_translator_gui.py` | `Mr.`/`Miss` eser/karakter kimliklerinde, kilitli terimlerde ve tırnaklı adlarda korunuyor |
| 24 | `subtitle_formats.py` | CP1254'e özgü `ğĞıİşŞ` ayırt edici kanıt; gerçek dışı karakterler ceza |
| 25 | `subtitle_formats.py` | Milisaniyesiz ve 4+ haneli SRT zamanları tolere ediliyor |
| 26 | `subtitle_translator_gui.py` | TM parmak izi dizi kanonu + analiz derinliğini kapsıyor (varsayılan değerde eski parmak izi korunuyor) |
| 27 | `video_subtitles.py` + GUI | `disposition` bayrakları taşınıyor; tam+default akış seçiliyor, kısıtlı seçimde uyarı |
| 28 | `subtitle_translator_gui.py` | Manuel JSONL kaynak SHA-256 ile doğrulanıyor; uyuşmazlıkta fail-closed |
| 29 | `series_memory.py` | Kardeş `Episode N` klasörleri ortak dizi kökünde |
| 31 | `subtitle_translator_gui.py` | Çıktı yolu hedef dil etiketini taşıyor (Türkçe yolu birebir korunuyor) |
| 32 | `translation_memory.py` | İç noktalama iskeleti ve soru kipi karşılaştırılıyor |
| 33 | `subtitle_translator_gui.py` | Manuel JSONL global run-owner + output baseline kapısına girdi |
| 34 | `translation_memory.py` | Aynı dosyada iki anlamı olan kaynak exact reuse'tan çıkarılıyor, eski kaydı siliniyor |
| 35 | `project_memory.py`, `prompt_constants.py` | Sıradan sözcük kimlik eşlemesi harf durumundan bağımsız reddediliyor |
| 36 | `series_memory.py` | Slug ve terim kimliği NFC'ye indirgeniyor |
| 37 | `subtitle_translator_gui.py` | Numaralı dosyada yeni cue için kimlik şartı |
| 38 | `sdh_cleaner.py` | Latin dışı parantezli metin pozitif SDH kanıtı istiyor |
| 39 | `subtitle_formats.py` | `<rt>`/`<rp>` okunuş alt ağacı çıkarılıyor |

### Kapsam dışı bırakılan tek nokta

Madde 25 ve 37, `subtitle_localizer/srt.py` dosyasına da atıf yapıyor. O modül
**kardeş projededir** (`resolve_subtitle_project_path`) ve bu depoda değildir;
düzeltmeler bu depodaki `subtitle_formats.py` / `subtitle_translator_gui.py`
parser'larına uygulandı.

### Değişen kasıtlı davranışlar (eski davranış sanılıp geri alınmasın)

- Dosya adındaki dil etiketi artık içerik analizini ATLAMIYOR — okunabilir
  diyalog varsa AI çağrısı her dosyada yapılıyor.
  `test_parallel_detection_skips_api_for_explicit_filename_labels` bu yüzden
  yeniden adlandırıldı ve yeni sözleşmeyi doğruluyor.
- Türkçe dışı hedeflerde çıktı adı artık dil etiketi taşıyor (`.de.srt`).
  Türkçe çıktı yolu birebir aynı kaldı.
- `YÜKLEMEYE HAZIR.txt` yeni bir dosyadır; `ÇEVRİLDİ.txt` ile karıştırılmamalı.
