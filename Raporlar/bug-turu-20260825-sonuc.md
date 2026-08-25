# Bug turu 20260825 — sonuç

Kaynak: 2026-08-24/25 koşu loglarından çıkan 18 maddelik liste.
Ölçüm tabanı: 377 teslim `.srt`, 278 kaynak/teslim çifti, 2.083 dosyalık ham
arşiv, 102 gerçek log dosyası.
Suite: **4787 test, hepsi geçiyor.** GUI smoke temiz.

**Madde 8 yapılmadı** — high effort ister, aşağıda gerekçesi var.

---

## A. TESLİMİ BOZAN KOD HATALARI

### 1 — `[ ♪♪♪ ]` "çevrilmemiş" sayılıyor

```
Yer:      sdh_cleaner.py:1264 src_is_sfx_only (bracket grubu döngüsü)
Girdi:    Kaynak cue'su yalnız nota taşıyan parantez grubu: '[ ♪♪♪ ]'
Beklenen: SFX sayılıp düşürülmeli — çıplak '♪♪♪' zaten öyle sayılıyor
Gözlenen: Parantez içi ne betimleyici ne konuşmacı olduğu için reddediliyor;
          cue "çeviri eksik" işaretlenip dosyayı partial bırakıyor
Etki:     300 kaynak / 224.270 cue → 211 cue, 6 dosya (How We Got to Now
          S01E01-E06). Brief'in bildirdiği "6 dosya" ile birebir.
Sonuç:    DÜZELTİLDİ — muafiyet dar: grup nota taşımalı ve harf/rakam
          taşımamalı; önce/sonra ölçümünde 211 kazanç, 0 kayıp.
```

**Mojibake alt notu: YANLIŞ POZİTİF.** 4 dosyadaki 18 cue (`Âª[violin playing]`
biçimi) zaten doğru tanınıyor; mevcut `_strip_mojibake_music_ornament` sağlam.

### 2 — Eser adı / yabancı replik `identical_source` sayılıyor

```
Yer:      subtitle_translator_gui.py:9306 _src_is_proper_name_phrase
          (name_particles) + :9571 identity_tokens
Girdi:    Hedefte korunması doğru olan kaynak metin: kurum adı, kilitli eser
          adı, biçim etiketiyle sarılı ünlem tekrarı
Beklenen: Çevrilmemiş sayılmamalı
Gözlenen: 'of'/'from' bağlayıcısı özel ad listesinde yok → 'Lloyd's of
          London', 'Plan 10 from Outer Space' düşüyor. Ayrı olarak <i>
          etiketinin 'i' harfi token listesine girip tekrarlı ünlem
          muafiyetini bozuyor.
Etki:     278 çift / 206.882 cue → 22 bulgu, 8 dosya. 22'sinin 22'si yanlış
          pozitif.
Sonuç:    KISMEN DÜZELTİLDİ — bulgu 22 → 17. Taklit yankı sınamasında
          192.944 ateşlemenin 56'sı kayboldu (%0,029); 56'sının tamamı özel
          ad öbeği ve gerçek arşivde hiçbiri yankılanmamış.
```

**Kalan 17 için aday kural ÖLÇÜLÜP REDDEDİLDİ.** "Kaynakta İngilizce işlev
sözcüğü yok" kuralı 16 yanlış pozitifi düşürüyordu ama **39.791 gerçek
yankıyı kaçırıyordu (%20,6)** — `Doesn't exist.`, `Three minutes past 5.`
gibi sıradan replikler. Kalan sınıf (Latin ilahi, Eski İngilizce alıntı)
satırın dilini bilmeyi gerektiriyor.

**TM alt notu: ÖLÇÜLEMEDİ.** `identical_source` tüketicilerinin tamamı
teslim denetimi tarafında; TM yazma yolunda bu gerekçeyi kullanan kod
bulunamadı. Kaynak==çeviri çiftinin TM'ye yazılmaması ayrıca **bilinçli bir
kuraldır** (CLAUDE.md), bug değil.

### 3 — JSON kalıntısı `},{` teslime sızıyor

```
Yer:      response_integrity.py:131 parse_translation_payload
          (yeni: strip_json_structure_residue)
Girdi:    Kesik/bozuk yanıt kurtarılırken JSON nesne ayracı cue metnine
          karışıyor
Beklenen: Ayraç metne girmemeli; yalnız ayraçtan ibaret cue eksik sayılmalı
Gözlenen: '},{' doğrudan .srt'ye yazılıyor; bazı cue'lar yalnız ondan ibaret
          — çeviri tamamen kayıp ama cue dolu göründüğü için eksik
          sayılmıyor
Etki:     2.083 .srt / 1.639.230 cue → 18 cue, 16 dosya (8'i final teslim)
Sonuç:    DÜZELTİLDİ — kapı ortak ayrıştırıcıya kondu, sekiz çağrı yeriyle
          dört akış da kapsanıyor.
```

**İlk denemem ölçümde reddedildi:** satır sonundaki tek süslü parantezi de
kırpıyordu ve **61 dosyada 736 cue'nun ASS biçim etiketini** bozuyordu
(`{\i0}` → `{\i0`). Kural yalnız `},{` dizisine daraltıldı.

### 4 — SDH tanıyıcı + sayaç

```
Yer:      sdh_cleaner.py (_tr_sdh_label, is_sdh_descriptor)
          subtitle_translator_gui.py:3255 clean_sdh (sayaç)
Girdi:    Türkçe ses etiketi: 'KEDİ MİYAVLAR', 'KEÇİ MELEMESİ', 'VIZILTI'
Beklenen: Silinmeli (kullanıcının kalıcı tercihi: ses+dil+konuşmacı
          etiketlerinin hepsi silinir)
Gözlenen: 377 anahtar sözcüğün tamamına yakını İngilizce; Türkçe etiketler
          teslimde ayakta kalıyor. Ayrıca geçiş kaç cue düşürdüğünü hiç
          loglamıyor — çalışmadığını fark etmenin yolu yok.
Etki:     377 teslim / 284.076 cue → 10 dosyada 17 kalıntı, 15'i Türkçe ses
          tarifi. Düzeltmeden sonra 20 cue yeni siliniyor, hepsi gerçek
          etiket; silinen replik 0, korunmaya dönen 0.
Sonuç:    DÜZELTİLDİ — kök listesi + biçim koşulu; sayaç dört akışa bağlandı.
```

**İlk denemem ölçümde reddedildi:** yalnız ses köküne bakan sürüm **gerçek
anlatımı siliyordu** — `kibirli bir homurtuyla çekip gittiler;`, `Kahkaha,
demokrasiden yana bir güçtür`, `Bir mandolinin hoş iniltisini`. Etiket
sayılmak için artık parantez içinde ya da baştan sona büyük harf olma ve en
çok dört sözcük tutma şartı var.

**"Boşluk/çok-kelime körlüğü" alt notu: YANLIŞ POZİTİF.** `[ SES ]`,
`[ MUSIC ]`, `[MUSIC PLAYING]` zaten tanınıyordu. Gerçek kusur sözcük
dağarcığıydı.

---

## 17 — Klasör ekleme, seçilmeyen dosyaları listeye alıyor

```
Yer:      subtitle_translator_gui.py:28273 _append_folder_files
          ve :28229 _queue_append_folder_files (yeni: _folders_all_inside)
Girdi:    Giriş klasörü dolu · dosya seçimi boş
          (_input_folder_explicitly_selected=True) · giriş klasörünün
          ALTINDAKİ 15 alt klasör "klasör ekle" ile seçiliyor
Beklenen: Yalnız o 15 klasörün altyazıları listeye girer
Gözlenen: Önce _get_srt_files() ile giriş klasörünün tamamı listeye konuyor;
          15 klasör zaten içinde kaldığı için added=0
Etki:     Gerçek logda (run_20260824-121939) üç ardışık deneme:
          '15 klasör eklendi: +0 yeni, toplam 488' → '484' → '484'.
          Yanlışlıkla başlatılırsa istenmeyen dosyalar çevrilir, kota yanar.
Sonuç:    DÜZELTİLDİ — tohumlama yalnız eklenen klasörler giriş ağacının
          DIŞINDAYSA yapılır; iki yol da kapsandı, üç mevcut test modülü
          hâlâ geçiyor.
```

---

## B. YANILTICI SONUÇ / VERİM

### 5 — Onarım retry yok

```
Yer:      subtitle_translator_gui.py:10421 total_attempts = 1
Girdi:    Onarım adayı doğrulayıcıdan dönüyor
Beklenen: (iddia) yeniden denenmeli
Gözlenen: Tek deneme — ama bu commit cb7741e ile BİLEREK konmuş
          ("cap subtitle repair to one attempt per cue") ve
          tests/test_repair_retry_hardening.py:397 onu kilitliyor
Etki:     Logdaki 246 reddin gözlenen örneklerinin tamamı doğrulayıcı yanlış
          pozitifiydi (partial_english_token, source_english_overlap) ve bu
          oturumda düzeltildi; tekrar denemek aynı reddi üretip API yakardı
Sonuç:    YANLIŞ POZİTİF — testin kilitlediği bilinçli tasarım.
```

### 6 — `birbirinden` → `birinden`

```
Yer:      subtitle_translator_gui.py:6208 _HEAD_TYPO_LEGITIMATE_PREFIXES
          ve :6226 hece tekrarı döngüsü
Girdi:    7+ harfli sözcükte ilk 2-3 harf tekrar ediyor, kırpılmış biçim
          aynı dosyada geçiyor
Beklenen: Yalnız gerçek yazım hatası bildirilmeli
Gözlenen: 'birbirinden' karşılıklılık zamiri, 'durdur-' ettirgen çatı;
          ikisi de yazım hatası sanılıyor
Etki:     377 teslim → 9 bulgu, 8 dosya. 9'unun 9'u yanlış.
Sonuç:    DÜZELTİLDİ — beyaz liste büyütülmedi, kural daraltıldı: ettirgen
          eki biçimindeki tekrar atlanıyor. Aynı arşivde bulgu 9 → 0,
          sentetik gerçek hata ('neneredeyse') hâlâ yakalanıyor.
```

### 7 — `max_tokens` sınırda

```
Yer:      subtitle_translator_gui.py:8901 build_requests
          (max_completion_tokens = max(chunk_size, len(chunk)) * 120 + 500)
Girdi:    Ana çeviri isteği
Beklenen: (iddia) bütçe yetmiyor, yanıt kesiliyor
Gözlenen: 284.076 cue'da cue başına en yüksek çıktı 103 token (bütçe 120);
          6.917 chunk'ın hiçbiri 5.300'lük bütçeyi aşmıyor, en dolu chunk
          bütçenin %47'si, p99 %36'sı
Etki:     Bütçe kaynaklı kesilme yok
Sonuç:    YANLIŞ POZİTİF — ama etiket yanıltıcıydı ve DÜZELTİLDİ:
          recovery_kind her kısmi eksikte "kesilme" diyordu. Gerçek
          kesilmede eksikler chunk'ın sonunda toplanır; dağınıksa model cue
          atlamıştır. Artık ayrı adlandırılıyor.
```

### 8 — `consistency_sweep` yalnız tam-cümle tekrarına bakıyor

```
Yer:      hybrid_translate.py:13078 consistency_sweep
Girdi:    Aynı terimin dosya içinde farklı çevrilmesi
Beklenen: Terim düzeyinde tutarsızlık yakalanmalı
Gözlenen: 55/55 dosya "tutarlı" raporlandı
Etki:     ÖLÇÜLMEDİ (bu oturumda yapılmadı)
Sonuç:    YAPILMADI — HIGH EFFORT gerekiyor.
```

**Neden high:** karşılaştırma birimini cümleden terime çevirmek dedektör
semantiği değişikliğidir ve iki yönlü ölçüm ister. Bu oturumda tam bu
sınıfta **üç ayrı ucuz kural ölçülüp reddedildi** (madde 2, 3, 4). Medium
efforta sıkıştırmak ya eksik ölçüm ya da tutarlılık taramasını körleştirme
riski taşır.

### 9 — Terim normalizasyonu `response_not_array` ile çöktü

```
Yer:      subtitle_translator_gui.py:13805 _normalize_mixed_terms chunk
          döngüsü (yeni: TERM_NORMALIZATION_MAX_ATTEMPTS)
Girdi:    Yardımcı model dizi olmayan yanıt döndürüyor
Beklenen: Yeniden denenmeli, olmuyorsa açıkça bildirilmeli
Gözlenen: Paket sessizce düşüyor (tek warn satırı), bütün terimleri
          normalize edilmemiş kalıyor
Etki:     Gerçek koşuda 1 dosya
Sonuç:    DÜZELTİLDİ — bir kez tekrar + "N terim normalize edilmedi" satırı.
```

### 10 — Kaynak dil koşu boyunca hiç loglanmıyor

```
Yer:      subtitle_translator_gui.py:22850 _source_language_log_text (yeni);
          iki akışta İçerik türü satırının yanına eklendi
Girdi:    Her dosya
Beklenen: Hangi dilden çevrildiği log'da yazmalı
Gözlenen: Hiç yazmıyor; teşhiste dosya adına bakılıyor, ad otorite değil
Etki:     Bütün koşular
Sonuç:    DÜZELTİLDİ — çözülmüş dil + kaynağı ("seçildi" / "otomatik tespit").
```

### 11 — Log satırı birleşmesi

```
Yer:      subtitle_translator_gui.py:23786 App._log disk yazımı
          (yeni: _fold_log_record)
Girdi:    Mesajın İÇİNDE gerçek satır sonu — tutarlılık ve onarım satırları
          cue metni alıntılıyor, cue metni satır sarıyor
Beklenen: Bir kayıt bir fiziksel satır
Gözlenen: Tek kayıt birden çok satıra yayılıyor, devam satırlarında zaman
          damgası yok, satır bazlı ayrıştırma iki kaydı birleşmiş görüyor
Etki:     102 gerçek log / 19.434 dolu satır → 776 satır (%4,0) zaman
          damgasız
Sonuç:    DÜZELTİLDİ — dosyada katlanıyor, arayüzde çok satırlı kalıyor.
```

### 12 — Klasör sayacı + log spam

```
Yer:      (a) _append_folder_files tohumlaması — madde 17 ile aynı kök
          (b) iddia edilen dosya listeleme spam'i
Girdi:    (a) 15 alt klasör ekleme  (b) uzun koşu
Beklenen: (a) sayı tekrarlanabilir olmalı  (b) listeleme özetlenmeli
Gözlenen: (a) 488 → 484 → 484, üçü de '+0 yeni'; sayı bir kez önbellekten
          bir kez taze taramadan geliyor
          (b) adı geçen log 2.900 değil 1.556 satır; tekrarlar dosya
          listelemeden değil chunk kurtarma raporlamasından (86+79+41)
Etki:     (a) her klasör ekleme  (b) yok
Sonuç:    (a) DÜZELTİLDİ (madde 17 ile birlikte, testle kilitlendi)
          (b) YANLIŞ POZİTİF — tekrar eden satırlar anlamlı, spam değil.
```

---

## C. RAPOR EKSİKSİZLİĞİ

### R1 — Kırpma yasağı

```
Yer:      subtitle_translator_gui.py:5359 _cue_fill_report_lines
          ve :18558 delivery_scan_report_lines
Girdi:    8'den fazla cue-fill bulgusu, 8'den fazla hece tekrarı/çift
Beklenen: Rapor dosyası kırpmamalı
Gözlenen: "… +N cue daha" satırı bulguları kalıcı olarak gizliyor
Etki:     68 dosya / 19.736 cue
Sonuç:    DÜZELTİLDİ — log yolu kırpmaya devam ediyor (akış okunur kalsın),
          rapor yolu limit=None ile tam yazıyor.
```

### R2-R5 — Üretilen dosyalar

```
Yer:      subtitle_translator_gui.py — build_delivery_scan_report_text,
          build_report_index_text, build_decisions_report_text,
          verify_report_coverage; App._save_quality_report'a bağlandı
Girdi:    Her koşu sonu
Beklenen: Bulgular kalıcı dosyaya yazılmalı, tek giriş noktası olmalı,
          karar izi kaybolmamalı, yazılan == bulunan olmalı
Gözlenen: Teslim taraması yalnız log'a gidiyordu; log rotasyona giriyor
Etki:     Bütün koşular
Sonuç:    DÜZELTİLDİ — Raporlar/teslim_taramasi.txt (R2),
          Raporlar/00-OZET.md (R3, sıra KRİTİK→TERİM→BİÇİM),
          Raporlar/KARARLAR.md (R4, karar alanı + uygulayan araç),
          koşu sonunda kapsam değişmezi doğrulaması (R5).
```

---

## Özet

| durum | maddeler |
|---|---|
| DÜZELTİLDİ | 1, 3, 4, 6, 9, 10, 11, 12a, 17, R1, R2, R3, R4, R5 |
| KISMEN | 2 (22→17; kalan sınıf için aday kural ölçülüp reddedildi) |
| YANLIŞ POZİTİF | 5, 7, 12b + madde 1 mojibake notu + madde 4 "boşluk körlüğü" |
| ÖLÇÜLEMEDİ | madde 2'nin TM alt notu |
| YAPILMADI | 8 (high effort) |

**Ölçüm üç kez kendi düzeltmemi reddetti** (madde 2 aday kuralı, madde 3 ilk
sanitizer, madde 4 ilk kök listesi). Üçü de sentetik testte "çalışıyor"
görünüyordu ve yalnız gerçek arşive karşı ölçünce yanlış çıktı.
