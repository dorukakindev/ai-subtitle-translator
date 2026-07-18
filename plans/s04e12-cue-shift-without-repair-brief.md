# Brief: S04E12 (Slim Goodbody's Adventure) — JSON onarımı OLMADAN oluşan cue kayması

Hazırlayan: Fable 5 (analiz, 2026-07-08). Bu brief kendi başına yeterlidir; ama önce
`plans/s04e14-json-repair-shift-brief.md`'i oku — aynı hata SINIFININ kök-neden kod
analizi orada (Görev 1/2, `_json_repair_pass` doğrulama eksikliği). **Bu brief o
bulguyu GENİŞLETİYOR: aynı hata, JSON onarımı HİÇ olmadan da oluşuyor.**

**Durum (2026-07-08 güncellemesi):**
- **TESPİT tarafı UYGULANDI (Opus 4.8):** Görev 2'nin güçlü bir versiyonu hayata geçti — `detect_alignment_issues()` + `scan_translation_quality` içine belirgin `🚨 OLASI CUE HİZALAMA/KAYMA SORUNU` uyarısı. Üç deterministik sinyal (number_shift / missing_dialogue / outlier_cluster), yanlış-alarm gardıyla (cümle-içi SOV yeniden dağıtımı ile aşırı-olmayan oranları hariç tutar). 3 bozuk + 3 temiz gerçek dosyada doğrulandı. Testler: `tests/test_alignment_detector.py` (11). Yani artık bu hata sınıfı YENİ koşularda otomatik işaretleniyor. Görev 2'yi TEKRAR yapma — sadece istenirse "tespit edilince otomatik yeniden çeviri" opsiyonunu ekleyebilirsin.
- **ÖNLEME + DOSYA DÜZELTME tarafı da UYGULANDI (Sonnet 5, 2026-07-08):**
  - Görev 1: `plans/s04e14-json-repair-shift-brief.md`'deki id doğrulaması kodlandı.
  - Görev 3: her iki sistem promptuna ("her numaralı id kendi çevirisini almalı") kuralı eklendi, hizalama testi (`tests/test_short_cue_alignment_prompt.py`) ile doğrulandı.
  - Görev 5: `PAREN_NOTE`'daki `"[" not in orig_clean` şartı kaldırıldı; regresyon testi `tests/test_s04e04_mutant_mascot_guards.py::test_flags_paren_note_even_when_source_has_sfx_bracket`.
  - Görev 6: kök neden tam olarak bulundu — `_is_untranslated(src, "")` her zaman `False` dönüyordu (boş çeviriyi hiç sorun saymıyordu) VE `clean_sdh_blocks` girdi ZATEN boşsa bile bloğu sessizce siliyordu. İkisi birlikte düzeltildi: `_is_untranslated` artık SFX-only olmayan kaynaklarda boş çeviriyi True (onarılmalı) sayıyor; `clean_sdh_blocks` girdi-zaten-boş cue'ları artık düşürmüyor, koruyor ki sonraki `_repair_untranslated_sync` geçişi onları görüp doğru kaynakla doldurabilsin. Uçtan uca S04E15 senaryosuyla doğrulandı. Testler: `tests/test_silent_empty_cue_loss.py` (9).
  - Görev 4: dosya düzeltmesi API çağrısı (gerçek para) gerektirdiği için OpenAI'ye tekrar gönderilmedi — cue aralığı ELLE çevrildi (aşağıda not, aralık #487-518 değil **#484-518**, 35 cue — yeniden incelemede kayma 3 cue daha erken başladığı görüldü). `detect_alignment_issues` 0 bulgu, cue sayısı (540) korundu. `.bak` yedeği dosyanın yanında.

## Özet

`C:\Users\K\Downloads\ÇIKTI\Oddities_S04E12_Slim Goodbody's Adventure.English.srt`
dosyasında **cue #487'den #518'e kadar (~32 cue) Türkçe içerik yanlış cue'lara
dağılmış/karışmış** durumda. Bu koşunun logunda **hiçbir "JSON onarıldı" mesajı YOK**
— yani S04E14'teki gibi `_json_repair_pass`'in tetiklenmesine gerek kalmadan, modelin
NORMAL, tam parse olan bir yanıtında bile bu hata sınıfı oluşabiliyor. Kök-neden analizi
bu yüzden genişletilmeli.

Log'un kendisi bunu KISMEN yakalamıştı ama ciddiyetini büyük ölçüde hafife
gösteriyordu: `⚠ 3 satırda anormal uzunluk oranı (#491(0.06x), #516(0.08x),
#517(6.6x))`. Gerçekte etkilenen aralık bu 3 satırdan çok daha geniş — bağımsız
anahtar-kelime taramasıyla en az 8 ayrı nokta daha doğrulandı (aşağıda).

## Kanıt

Yan yana karşılaştırma (kaynak EN, final TR — `subtitle_formats.read_subtitle_text` ile
ayrıştırıldı):

```
#487 EN: SLIM GOODBODY STOPPED BY THE SHOP          TR: O, yaklaşan çocuklar için gastrolü için
#488 EN: AND SENT US ON AN ANATOMICAL ADVENTURE.    TR: tam aradığı şeyin peşinde.
#489 EN: HE'S LOOKING FOR THE PERFECT ITEM          TR: Biz de tam aradığı şeyi bulduk sanıyoruz.
#490 EN: FOR HIS UPCOMING EDUCATIONAL TOUR.         TR: Umarım Slim Goodbody kıyafetiyle çıkıp gelir.
#491 EN: WE THINK WE FOUND EXACTLY WHAT HE'S...     TR: Oh.
#492 EN: I JUST HOPE HE SHOWS UP IN THE...OUTFIT.   TR: Umarım Slim Goodbody kıyafetiyle ortaya çıkar.
```

`#489`'un TR'si ("Biz de tam aradığı şeyi bulduk sanıyoruz" = "We think we found exactly
what he's looking for") kelimesi kelimesine **`#491`'in İngilizcesine** ait. `#490`
VE `#492` neredeyse AYNI Türkçe cümlenin ("Umarım Slim Goodbody kıyafetiyle...")
iki farklı ifadesini taşıyor — yani bir satır muhtemelen **iki kez** çevrilip iki
farklı cue'ya yapıştırılmış.

Bağımsız nadir-kelime taraması (New York / bargain / costume / Auzoux / nervous /
budget / generosity / missing pieces / money / unfortunate) `#494, #499, #500, #501,
#510, #511, #512, #514, #515, #516, #518` dahil onlarca noktada aynı örüntüyü
doğruladı: İngilizce'de geçen anahtar kelimenin Türkçe karşılığı O CUE'DA YOK, ama
komşu bir cue'da VAR.

**Gerçek bir kopyalama da tespit edildi:** `#517` ve `#520`'nin Türkçe metni
**birebir aynı** ("Beynini kaybetmiş. Korkuluk gibi.") — ama bu cümlenin doğru
kaynağı yalnızca `#520` ("SHE'S MISSING HER BRAIN. LIKE THE SCARECROW."). `#517`nin
kendi kaynağı yalnızca `"OKAY."` — orada bu cümlenin hiçbir izi olmamalıydı.

**Kapsam doğrulaması:** dosyanın geri kalanında (487-518 dışı) aynı taramayla
yapılan geniş kontrolde SIFIR başka şüpheli nokta bulundu — hasar bu tek ~32
cue'luk bloğa izole. `#128`... pardon, bu dosyada `#519`'dan itibaren tekrar temiz
(kontrol edildi).

## Örüntü gözlemi (önleyici tasarım için önemli)

Etkilenen aralık, **çok sayıda kısa/tek-kelimelik ünlem cue'sunun** ("Oh." "ALL
RIGHT." "OKAY." "YEAH, YEAH." "[ KNOCK ON DOOR ]") normal diyalog satırlarının
ARASINA sıkışmış olduğu bir bölüm. S04E14'teki bozulma da benzer şekilde bir SFX-only
cue ("[ LAUGHS ]") + çok-cue'lu bir cümlenin sınırında başlamıştı. **Ortak desen:**
model, kısa/içeriksiz cue'ların sınırını bulanıklaştırıp komşu diyaloğu onların
üzerine "akıtıyor" gibi görünüyor — muhtemelen çünkü tek kelimelik bir cue'ya "gerçek"
bir çeviri ayırmak modele gereksiz geliyor ve id-hizasını kaybediyor.

## Neden mevcut mekanizmalar bunu yakalayamadı

- `has_non_turkish_target_leak` / `_TURKIC_DRIFT_RE`: alakasız — kayan satırların
  hepsi düzgün, akıcı Türkçe.
- `_repair_untranslated_sync`: yalnızca `[HATA*]` veya kaynakla birebir aynı
  (çevrilmemiş) satırları yakalar — kaymış ama dolu/akıcı satırlar bu kritere girmiyor.
- `run_validators`'daki `_length_ratio_outlier`: bu ASLINDA doğru sinyali
  üretiyor (oran çok düşük/yüksek) — ama yalnızca 3 satırda EŞİĞİ AŞTIĞI için
  rapora düştü. Aralıktaki diğer ~29 satırın oranı (0.47x-1.94x gibi) eşiği
  aşacak kadar aşırı değildi, halbuki İÇERİKLERİ de yanlış hizalanmıştı. Yani bu
  validator "biraz doğru" ama **çok dar bir eşikle** çalışıyor ve bulguyu yalnızca
  kalite raporunda görünen tek bir bilgi satırına indirgiyor — critic'e
  otomatik düşmüyor, kullanıcıya "bunu elle kontrol et" gibi belirgin bir uyarı da
  vermiyor.

## Önerilen düzeltmeler (Sonnet 5 için)

### Görev 1 — `plans/s04e14-json-repair-shift-brief.md`'deki Görev 1/2'yi uygula

O brief'teki `_json_repair_pass` doğrulaması hâlâ değerli (S04E14 vakasını önler)
ama **bu vakayı ÖNLEMEZ** (burada repair hiç tetiklenmedi). Yine de temel, düşük
riskli bir düzeltme olduğu için önce o uygulanmalı.

### Görev 2 — `_length_ratio_outlier` bulgularını KÜMELEME sinyaline çevir

`run_validators` zaten her satır için `_length_ratio_outlier` hesaplıyor (gui
~satır 2299 civarı, `LENGTH_RATIO_OUTLIER` reason'ı). Şu an bu yalnızca critic'e
tek tek satır olarak düşüyor. Yeni mantık: **aynı chunk içinde ardışık/yakın 2+
satır `LENGTH_RATIO_OUTLIER` alırsa**, bunu izole satır sorunları olarak değil,
**o CHUNK'IN TAMAMININ hizalama sorunu olabileceğinin sinyali** olarak işle:
- `_write_results` (veya rapor oluşturma noktası — `scan_translation_quality`
  civarı) içinde, aynı dosyada birbirine yakın (örn. ±10 cue içinde) 2+ outlier
  varsa, bunu kalite raporuna VE log'a MEVCUT "3 satırda anormal uzunluk oranı"
  satırından çok daha belirgin bir uyarıyla yaz: örn. `"⚠⚠ #487-518 arası olası
  CUE HİZALAMA SORUNU (N adet uzunluk-oranı aykırı değeri kümelendi) — bu aralığı
  ELLE KONTROL EDİN"`.
- Opsiyonel (daha güçlü, daha maliyetli): kümeleme tespit edilirse, o aralığı
  kapsayan chunk'ı OTOMATİK tam yeniden çeviriye gönder (critic'in tek-satır
  yamalarına güvenme — critic bir satırı DÜZELTEBİLİR ama YANLIŞ HİZALANMIŞ bir
  satırı doğru id'ye TAŞIYAMAZ, çünkü critic her satırı kendi id'sinin doğru
  kaynağı sanıp üzerinde çalışır).

### Görev 3 — Sistem promptuna kısa/ünlem cue'ları için pekiştirme kuralı

Her iki sistem promptuna (gui `_build_sync_system_prompt`, `ht.build_system_prompt`
— hizalı kalmalı) şuna benzer bir kural ekle: *"Every numbered id MUST receive its
OWN translation, even if the source is a single word, an interjection ('Okay.',
'Yeah, yeah.', 'Oh.'), or a bracketed sound effect. NEVER merge a short cue's
meaning into a neighboring id's translation, and never leave a short cue's
translation empty or skip it — doing so shifts every subsequent id's alignment."*

### Görev 4 — Bu dosyayı düzelt

`C:\Users\K\Downloads\ÇIKTI\Oddities_S04E12_Slim Goodbody's Adventure.English.srt`:
cue #487-518 arası (32 cue) yeniden çevrilmeli (regex ile onarılamaz — bu bir
hizalama sorunu). S04E14 brief'indeki Görev-3 ile aynı yöntem: checkpoint
gerekirse temizlenip dosya yeniden çevrilmeli, ya da izole bir alt-istekle bu
aralık yeniden üretilip birleştirilmeli. Düzeltme sonrası bu brief'teki
karşılaştırma yöntemiyle (EN/TR yan yana + nadir-kelime taraması) doğrula.

## Test & doğrulama

0. Görev 6 için: kaynak `"Evan: OH. [ CHUCKLES ]"` + çeviri (fragment/consistency
   veya SDH-temizleme sonrası) boş/`[ÇEVİRİ EKSİK]` kalan bir sonraki cue senaryosu
   kurup, final yazımda bu cue'nun ya onarıldığını ya da GÖRÜNÜR `[ÇEVİRİ EKSİK]`
   olarak kaldığını (sessizce silinmediğini) doğrulayan bir regresyon testi ekle.
1. `plans/s04e14-json-repair-shift-brief.md`'deki test planı (Görev 1 için).
2. Görev 2 için yeni test: aynı chunk'ta 2+ `LENGTH_RATIO_OUTLIER` reason'lı satır
   olan sahte bir `tr_blocks`/`cues` seti kurup, kümeleme uyarısının/log satırının
   tetiklendiğini doğrula.
3. Görev 3 için `tests/test_idiom_traps_prompt.py` kalıbında: yeni kural metninin
   HER İKİ promptta da bulunduğunu assert eden test.
4. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py`
5. `python -m unittest discover -s tests` (taban: bu oturumun sonunda kaç teste
   çıkıldıysa onu koru, hepsi yeşil).
6. GUI headless smoke test.

### Görev 5 — (Küçük, düşük öncelik) `PAREN_NOTE` validatöründe kendi hatamı düzelt

S04E04 brief'inde eklenen `PAREN_NOTE` kontrolü (gui `run_validators`, grep
`PAREN_NOTE`) şu satırı içeriyor:
```python
if "(" in text and "(" not in orig_clean and "[" not in orig_clean:
    reasons.append("PAREN_NOTE")
```
Bu S04E12 çıktısında test edilip GERÇEK BİR ATLAMA olduğu doğrulandı: cue #17
kaynağı `"[ Chuckling ] ONLY IN NEW YORK."` (SFX etiketi `[...]` içeriyor) →
çeviri `"[KIKIRDAMA] Sadece New York (New York açıklaması)."` — burada gerçek bir
çevirmen notu (`(New York açıklaması)`) eklenmiş ama `"[" not in orig_clean`
şartı, kaynakta SFX etiketi olduğu için YANLIŞLIKLA tüm satırı muaf tutuyor;
`run_validators` yalnızca `SFX_LEFTOVER` buluyor, `PAREN_NOTE` hiç tetiklenmiyor
(doğrudan test edildi: `ht.run_validators(...)` çıktısı yalnızca
`'SFX_LEFTOVER'`). Sonunda Polish bunu kendi LLM yargısıyla düzeltti ama bu
şansa bağlı — critic hiç görmedi.

**Düzeltme:** `"[" not in orig_clean` şartını kaldır (yalnızca `"(" not in
orig_clean` yeterli — SFX etiketleri `[...]` farklı bir söz dizimi, çıktıda
`(...)`'a asla meşru şekilde dönüşmez, bu yüzden '[' varlığı '(' eklenmesini
mazur göstermemeli). Test: yukarıdaki tam senaryo (`Cue(17, "[ Chuckling ]
ONLY IN NEW YORK.")` + çeviri `"[KIKIRDAMA] Sadece New York (New York
açıklaması)."`) → `run_validators` artık `'PAREN_NOTE'` da döndürmeli (mevcut
`SFX_LEFTOVER` ile birlikte, biri diğerini dışlamamalı). Var olan
`tests/test_s04e04_mutant_mascot_guards.py::ParenNoteValidatorTest`'e bu SFX+parantez
kombinasyonunu kapsayan bir regresyon testi ekle.

## S04E15 (Vampires of PhilaHELLphia) doğrulaması — 3. örnek, ÇOK DAHA NET bir mikro-desen

`Oddities_S04E15_Vampires of PhilaHELLphia.English.srt` koşusunda (log: `⚠ 1
satırda anormal uzunluk oranı (#385(6.17x))`) bu episode GENELİ çok temizdi (0
sızıntı, JSON onarımı yok, düşük critic/polish aktivitesi) ama TAM OLARAK aynı
hata ailesinden **4 ayrı, birebir özdeş** mikro-örnek bulundu:

```
#361 EN: "Evan: OH. [ CHUCKLES ]"              ham: "Evan: Oo. [KIKIRDAR] Ne harika bir oda bu, vay be!"
#362 EN: "WHAT A GREAT ROOM THIS IS. WOW!"     ham: "[ÇEVİRİ EKSİK]"  → FİNALDE CUE TAMAMEN SİLİNMİŞ

#367 EN: "[ BOTH LAUGH ]"                      ham/fin: "[İKİSİ DE GÜLER] Size biraz şey getirdik."
#368 EN: "WE GOT YOU SOME STUFF."              ham: "[ÇEVİRİ EKSİK]"  → FİNALDE CUE TAMAMEN SİLİNMİŞ

#385 EN: "[ CHUCKLES ]"                        ham/fin: "[KIKIRDAR] Şimdi dükkânda birkaç tane vardı, sizde de zaten birkaçı var."
#386 EN: "NOW, WE'VE HAD SOME AROUND..."       ham: "[ÇEVİRİ EKSİK]"  → FİNALDE CUE TAMAMEN SİLİNMİŞ

#391 EN: "[ CHUCKLES ]"                        ham/fin: "[KIKIRDAR] İnanılmaz."
#392 EN: "IT'S INCREDIBLE."                    ham: "[ÇEVİRİ EKSİK]"  → FİNALDE CUE TAMAMEN SİLİNMİŞ
```

Desen HER 4 örnekte de birebir aynı: **kısa bir tepki/ünlem ("OH.") veya SFX
etiketi ("[ CHUCKLES ]", "[ BOTH LAUGH ]") ile başlayan/oluşan bir cue, hemen
SONRAKİ cue'nun TÜM diyalog içeriğini kendi üzerine çekiyor**; sonraki cue
modelin JSON yanıtında hiç üretilmemiş gibi davranıp `[ÇEVİRİ EKSİK]` oluyor.
Bu, S04E12/S04E14'teki büyük-ölçekli kaymanın aynı kök nedeninin (kısa/ünlem
cue'ların model tarafından "atlanması") çok daha KÜÇÜK VE TEMİZ bir tezahürü —
burada yalnızca 2'şerli çiftler halinde, kademeli bir kaymaya dönüşmeden.

**Yeni ve önemli ek bulgu — veri kaybı SESSİZCE oluyor:** Bu 4 "yutulan" cue
(`#362, #368, #386, #392`) `[ÇEVİRİ EKSİK]` olarak ham'de görünüyor ama
**final dosyada görünür bir placeholder olarak KALMIYOR — cue'nun kendisi
TAMAMEN SİLİNMİŞ** (S04E12/14'te gördüğümüz "[ÇEVİRİ EKSİK] görünür kalır" veya
"_repair_untranslated_sync ile onarılır" davranışlarından FARKLI). Kanıt: final
dosyada ham'e göre eksik olan 9 cue'nun 5'i gerçekten SFX-only cue'ların
`clean_sdh` ile bilinçli temizlenmesi (`#28, #251, #311, #313, #399` — hepsi
doğru çevrilmiş `[KAHKAHA]` vb. idi, temizlenmeleri BEKLENEN/doğru davranış),
ama **4'ü (`#362, #368, #386, #392`) GERÇEK DİYALOG satırı** ("WHAT A GREAT
ROOM THIS IS, WOW!", "WE GOT YOU SOME STUFF." gibi) — bunlar SDH değil, temizlik
mantığı bunları YANLIŞLIKLA SFX-only cue'larla AYNI şekilde işleyip silmiş
görünüyor. Bu koşuda `_repair_untranslated_sync` hiç tetiklenmedi (log'da
"çevrilmemiş satır ... onarılıyor" satırı YOK) — yani bu 4 cue, o onarım
mekanizmasının GÖREBİLECEĞİ noktaya (blocks listesi) hiç ulaşmadan, muhtemelen
daha ERKEN bir aşamada (fragment/consistency-sweep veya SDH-temizleme mantığı)
sessizce düşürülmüş olmalı — kesin sorumlu fonksiyon Sonnet 5 tarafından kod
okumasıyla doğrulanmalı (aday alanlar: `clean_sdh`'nin çalıştığı yer, veya
`_maybe_merge_cues`/boş-metin cue temizleme mantığı — "metin boş/[ÇEVİRİ
EKSİK] İSE VE kaynak SFX-only DEĞİLSE silme, görünür bırak" ayrımı eksik).

### Görev 6 — Boş/[ÇEVİRİ EKSİK] cue'ların SDH-temizliğiyle karışmasını önle

Kaynak metni SFX-only OLMAYAN (yani `_is_sdh`/parantez-köşeli-parantez-dışı
gerçek kelime içeren) bir cue, çeviri aşamasında boş/`[ÇEVİRİ EKSİK]` kalırsa,
bu cue **SDH temizliği ile aynı yoldan sessizce silinmemeli** — ya (a)
`_repair_untranslated_sync`'in bu cue'yu MUTLAKA görmesini garanti et (hangi
aşamada kayboluyorsa, o aşamadan ÖNCE repair-pass çalıştır ya da bu tip
cue'ları o aşamadan hariç tut), ya da (b) en azından final yazımdan önce
`[ÇEVİRİ EKSİK]` olarak GÖRÜNÜR bırak (S04E12/14'teki gibi) — SDH-boş cue'larla
karıştırıp tamamen silme. Kaynağın SFX-only olup olmadığını ayırt etmek için
zaten `run_validators`/`_is_untranslated` içinde kullanılan `_SDH_ONLY_RE` /
parantez-köşeli-parantez tespiti yeniden kullanılabilir.

## Riskler / dikkat

- Görev 2'nin "otomatik tam yeniden çeviri" opsiyonu maliyetli olabilir (ekstra
  API çağrısı) — önce sadece BELİRGİN UYARI/log kısmını uygulamak, otomatik
  yeniden çeviriyi kullanıcıyla konuşulacak ikinci bir adım olarak bırakmak daha
  güvenli bir sıralama olabilir. Sonnet 5 bu tercihi kullanıcıya sorabilir.
- Görev 3'ün prompt kuralı modelin davranışını GARANTİ DEĞİŞTİRMEZ (gpt-5.4-mini
  bir kural yazıldı diye kusursuz uymaz) — bu bir AZALTMA, kesin çözüm değil. Asıl
  güvenlik ağı Görev 2'nin tespiti olmalı.
- Bu ikinci vaka (S04E12), S04E14 ile birlikte, projenin şu ana kadarki
  "kelime-listesi ekle" düzeltme kalıbının bu hata SINIFINI çözemeyeceğini
  gösteriyor — kelime sızıntısı ile cue-hizalama bozulması FARKLI kök nedenler,
  farklı düzeltme yaklaşımları gerektiriyor.
