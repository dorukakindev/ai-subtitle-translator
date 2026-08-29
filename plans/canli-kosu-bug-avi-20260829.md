# Salt-okunur bug avı — 2026-08-29 (koşu canlı: pid 18712, Martı/Romence)

Kod değiştirilmedi, test koşulmadı, App kurulmadı. Bütün sayılar gerçek
arşive karşı ölçüldü: 104 koşu logu, 357 analiz önbelleği, 292 hitap
haritası, doğrulanmış kaynak/teslim çiftleri.

**Ölçüm aracına dair uyarı:** ilk üç denememde tablo yanlış çıktı, üçünde de
suçlu benim harnessimdi — (a) alt-dize eşleşmesi (`Apolo` ⊂ `Apollon`),
(b) dosyayı ADA göre eşleştirince film klasörünün tepesindeki **kaynağı**
teslim sanmam, (c) önbellek adlandırmasının iki biçimli olması. Aşağıdaki
sayılar bu üçü düzeltildikten sonraki hâl.

---

## 1. Tırnak içi "eser adı" guard'ı fazla geniş — ölçülebilir maliyeti var

`quoted_work_titles` kaynakta tırnak içinde geçen HER ifadeyi eser adı
sayıp sözlükten atıyor. Başlık olup olmadığına dair hiçbir sınama yok.

**İki yönlü ölçüm (36 dosya, doğrulanmış Türkçe teslimler):**

| | Türkçesi kullanılmış | Kaynak biçimi kalmış |
|---|---|---|
| Guard'ın attığı (n=77) | 33 (%43) | **14 (%18)** |
| Sözlükte kalan (n=748) | 588 (%79) | **2 (%0,3)** |

Atılan terimin kaynak dilde kalma oranı **60 kat** yüksek.

**Atılanların %29'u eser adı bile değil.** 142 tekil çiftin 41'i küçük
harfle başlıyor:

```
free will -> özgür irade          dualism -> düalizm
time lapse -> hızlandırılmış çekim  cathartic -> katartik
navios de guerra -> savaş gemileri  pulsão de morte -> ölüm dürtüsü
simpósios -> sempozyumlar           cura pela fala -> konuşma yoluyla tedavi
```

`navios de guerra` Portekizce "savaş gemileri" — Türkçe teslimde öyle kalmış.

**Yerleşik Türkçe adlar da düşüyor:** `Iliad->İlyada` (6 kez),
`Odyssey->Odysseia`, `The Jazz Singer->Caz Şarkıcısı`,
`Koroghlu->Köroğlu`. ŞU AN çalışan koşuda da `Pescărușul->Martı` atıldı —
yani Çehov'un oyununun Türkçe adı.

**Önerilen daraltma (ölçüldü):** tırnak içi ifade büyük harfle başlamıyorsa
eser adı sayma. 142 çiftin 41'ini kurtarır, gözle bakılanlarda tek şüpheli
`een kus in de tunnel` (Felemenkçe, gerçekten başlık ama küçük harfli).

---

## 2. Karakter üslubu tek anlaşmazlıkta tamamen düşüyor

`_merge_memories` iki analiz chunk'ı aynı karaktere farklı üslup verirse
üslubu **siliyor** ve adı çatışma listesine yazıyor.

- 192 dosyanın **60'ında (%31)** üslup çatışması var
- toplam **198 karakter** üslubunu kaybetmiş, dosya başına ~3,3
- canlı koşuda Martı: 6 karakterin 4'ü (`Maşa, Nina, Polina, Sorin`)
- The Mark: `Inez, Janey, Mr Clive` — insan denetiminin "dört konuşmacı
  hattının dördü de tutarsız" dediği dosya

Terim çatışmasında düşürmenin zararsız olduğunu daha önce ölçmüştüm
(42 terimin 0'ı teslimde karışık çıkmıştı). Üslup için aynı şey
söylenemez, çünkü üslubun karşılığı metinde tek bir sözcük değil.

---

## 3. Hitap haritası üretiliyor, prompt'a giriyor — ama hiç DOĞRULANMIYOR

`detect_address_register_mix` yalnız teslim bloklarına bakıp sen/siz
sayıyor ve "karışık" diyor. Analizin ürettiği **çift bazlı haritaya hiç
bakmıyor**. Kodda `pronoun` + doğrulama/ihlal araması sıfır sonuç veriyor.

**Muhafazakâr ölçüm** — yalnız haritası TEK DÜZE olan dosyalar (her çift
aynı hitap düzeyi), en az 10 işaretli cue:

- 114 dosya
- aykırı cue oranı **ortalama %19**
- **40/114 dosyada (%35) aykırılık %20'nin üstünde**

| dosya | harita | aykırı |
|---|---|---|
| The Mark 1961 | `siz` (9 çift) | **325/516 cue (%63)** |
| That Cold Day in the Park | `siz` (10 çift) | 169/225 (%75) |
| Le.Dossier.51 | `siz` (3 çift) | 89/173 (%51) |

The Mark'ı insan denetimi bağımsız olarak işaretlemişti — ölçüm onu
listenin tepesinde buluyor.

**Dürüst kayıt:** tek düze harita "her cue o hitabı kullanmalı" demek
değil; anlatım, iç ses, alıntı ve haritada olmayan karakterler meşru
şekilde ayrışır. Yani %19 bir üst sınır, ihlal sayısı değil. Ama %63'lük
bir iki kişilik dramda bunu anlatıcıyla açıklamak mümkün değil.

**Önerilen:** teslim taramasına harita-uyum kontrolü (`bilgi` ya da
`muhtemel`, otomatik düzeltme YOK).

---

## 4. Aynı "ana karakterler kimdir" kararı dört ayrı yerde farklı kırpılıyor

```
hybrid_translate.py:1815  characters[:6]   üslup/örnek üretimi
hybrid_translate.py:1939  characters[:6]   hitap haritası üretimi
hybrid_translate.py:5429  characters[:5]   başka bir prompt yolu
hybrid_translate.py:3623  characters[:4]   log/özet
```

Karakter sayısı ortalama **11,9**, en yüksek **35**. Yani:

- üslup/hitap kapsamı ortalama **%60**, ortanca %55
- **114/357 dosyada kapsam %50'nin altında**
- en düşük: `The.Overnighters` %17 (6/35), `Colossus` %19 (6/32)

Kapsam dışı kalan karakterler için ne register ne hitap kararı var —
madde 3'teki savrulmanın yapısal kaynağı burası olabilir.

---

## Ölçülüp REDDEDİLENLER

| hipotez | sonuç |
|---|---|
| Hitap haritası prompt'a girerken kırpılıyor (`[:40]`) | En büyük harita **27 çift**; sınır hiç ateşlenmiyor. |
| Üslup prompt'a girerken kırpılıyor (`[:12]`) | En büyük **6**; sınır hiç ateşlenmiyor. |
| Guard'ın attığı terimler ile kalanlar aynı davranıyor | İlk iki ölçümde öyle görünmüştü — ikisi de benim harness hatamdı, bkz. başlık. |

## Küçük not (hata değil)

`_write_results` içinde tekrar hizalaması için `_src_map_from_cues(_src_cues)`
çağırıyorum; aynı sözlük iki satır yukarıda `src_blocks` adıyla zaten
hesaplanmış durumda. Davranış aynı, yalnız gereksiz.

---

## Öneri sırası (çeviri bitince)

1. **Madde 1** — tek satırlık daraltma, ölçülmüş kazanç, düşük risk.
2. **Madde 3** — yeni bir tarama sınıfı; otomatik düzeltme yok.
3. **Madde 4** — dört sınırı tek sabite bağla; kaç olacağı ayrı karar.
4. **Madde 2** — düşürme yerine "ilk karar kanon" denenebilir, ama önce
   üslubun teslime etkisi ölçülmeli; ölçmeden değiştirme.

---

# İkinci tur — üç bulgu daha

## 5. `characters[:6]` en ÖNEMLİ altı değil, en ERKEN görünen altı

Her analiz chunk'ı karakterleri `[:12]` ile kırpıyor (`hybrid_translate.py:3370`),
`_merge_memories` chunk'ları SIRAYLA birleştirip ilk görüleni önce koyuyor.
Yani nihai liste **ilk görünme sırası**. Üslup, örnek ve hitap haritası
bütçesinin gittiği ilk 6, filmin açılışında konuşanlar.

**Ölçüm** (209 dosya, en az 8 karakterli): kapsanan ilk-6 ile kaynakta en
sık geçen 6 arasındaki örtüşme **ortalama 3,9/6**, ortanca 4/6. Yani
kapsanan altının ~2'si en görünür altıda değil.

```
Ancient.Greece    örtüşme 1/6  kapsanan: Narrator, Rosie, Interviewee,
                               HE SPEAKS IN GREEK
                               kapsanmayan: Alexander(9), Neoptolemus(8)
BBC.Connections08 örtüşme 1/6  kapsanmayan: John Gorrie(19)
```

**Ölçütün sınırı açık:** "adın kaynakta geçme sayısı" bir vekil; çok konuşan
ama adı az anılan karakteri hafife alır. Sıralama sorusu için yeterli,
kesin önem sıralaması değil.

## 6. Karakter listesine kişi olmayan girişler sızıyor — KÜÇÜK

İlk sayımım %12,4 demişti; **o sayı benim fazla hevesli sınıflandırıcımdı**
(`Doctor`, `Princess`, `King`, `Man`, `Woman` adsız ama GERÇEK konuşmacılar).
Katı ölçütle:

- **44 kesin yanlış giriş, 39 dosya**, bunların **10'u ilk 6 slotunda**
- `Song lyrics`, `Şarkı sözleri`, `Congregation`, `Crowd`, `Kalabalık`,
  `Koro`, `CHORUS`, `NEWSREEL`, `Audience`, `HE SPEAKS IN GREEK`

Madde 5'in yanında küçük bir kalem; tek başına düzeltmeye değmeyebilir.

## 7. Çeviri Belleği yapı gereği YAZ-ONLY — 546.373 satır, neredeyse sıfır isabet

`_tm_context_fingerprint`'in gövdesi:

```python
body = {"source_sha256": source_hash, "locked_terms": normalized_terms}
```

Parmak izi **kaynak dosyanın SHA-256'sını** içeriyor ve arama hash'i de
parmak izini içeriyor (`translation_memory.py:349`). Sonuç: bir TM kaydı
ancak **birebir aynı dosya** yeniden çevrilirken bulunabilir. Dosyalar
arası yeniden kullanım yapı gereği imkânsız.

**Ölçüm:**

| | |
|---|---|
| TM boyutu | 184 MB, **546.373 satır** |
| farklı `context_key` | 163 (satırların %78'i boş anahtarlı) |
| farklı `source` | 525.981 → tekrar eden kaynak yalnız 20.392 |
| raporlarda "TM önbellek kullanımı" | **643 satırın 641'i 0**, ikisi 29 |
| loglarda "TM önbellekten N chunk atlandı" | 104 logda **hiç yok** |

Yazan akış 4 (`_run_hybrid`, `_run_sync_hybrid`, `_wait_batch_hybrid`,
`_write_results`), okuyan 2 (`_run_sync`, `_run_sync_hybrid`).

**Bu KASITLI olabilir:** parmak izi 2026-08-21 denetiminde bilinçli
genişletildi (kullanıcı sen/siz ya da analiz derinliğini değiştirince eski
çeviri dönmesin diye) ve senin kaydında "parmak izi tasarımı bozulmasın"
yazıyor. O hâlde soru şu: **dosyalar arası yeniden kullanım hiç
beklenmiyorsa** 184 MB ve her koşudaki yazma maliyeti karşılığında alınan
şey yalnız "aynı dosyayı yeniden çevirirsen atlar" oluyor. Bekleniyorsa,
kaynak SHA'sı parmak izinden çıkmadan mümkün değil.

Karar senin; ölçüm burada.

## 8. Cue sahipliği şüphesi: en zararlı sınıf, en düşük şiddet, tekrar yok

Canlı koşu şu an bir örnek üretti:

```
[11:48:08] ⚠  chunk_715: cue_content_owner_mismatch; şüpheli cue yalnız inceleme raporuna
[11:48:08] ⚠  Cue sahipliği inceleme özeti: 1 cue API tekrarı yapılmadan rapora bırakıldı
```

- 104 logda **37 olay / 15 koşu** — nadir (koşu başına ~2,5)
- sınıf `delivery_owner_mismatch_ids` = **`bilgi`**, teslim kapısını tetiklemiyor
- cue **yeniden denenmiyor**, yalnız rapora bırakılıyor

"İçerik yanlış cue'da" senin arşivinde SYNC-BREAKING diye kayıtlı en zararlı
sınıf. Buna karşılık en düşük şiddetle işaretleniyor ve onarıma gönderilmiyor.

**Karşı argüman, dürüstlük için:** tek-cue içerik kayması için ucuz sinyaller
daha önce ölçülüp reddedilmişti (çapa yaklaşımı özel adlar çevrildiği için
çalışmıyor). Yani dedektörün güveni tasarım gereği düşük olabilir ve
`bilgi` bilinçli olabilir. Ama o zaman soru şu: 37 olayın kaçı gerçekti?
Bu, ancak o cue'lar elle okunarak yanıtlanır — mekanik ölçüm yok.

---

# Üçüncü tur — kapı bileşimi ve imza kökeni

## 9. Teslim kapısını fiilen ne tetikliyor — ve bugünkü değişikliğim onu ele geçiriyor

349 gerçek teslimde blok tabanlı `kesin` sınıfları koşturdum:

| sınıf | işaretlediği dosya | tek sebep olduğu |
|---|---|---|
| **`stray_line_initial_e_ids`** (bugün ekledim) | **9** | **9** |
| `unbalanced_note_ids` | 2 | 2 |
| `cue_id_leak_ids` | 1 | 1 |
| `broken_italic_ids` | 0 | — |
| `repetition_collapse_ids` | 0 | — |

Toplam 12/349 dosya (%3). **Yani bugün eklediğim sınıf, kapının baskın
tetikleyicisi oluyor** ve dokuzunda da tek sebep — başka hiçbir sert
hatası olmayan 9 teslim bloke olacak, her biri genelde tek cue için.

Bulgular gerçek (satır başında yalnız `e`), soru şiddet: `kesin` mi
kalsın, `muhtemel` mi olsun? Senin kararın. `broken_italic` ve
`repetition_collapse` ise arşivde hiç ateşlenmiyor — kapı çok az sayıda
sınıfın omzunda duruyor.

## 10. İmza numarası sapması: program suçsuz, ELLE DÜZELTME bozuyor

13 teslimde imza cue'sunun numarası son diyalog cue'sunun bir fazlası
değil (`872 → 889`, `799 → 831`, `747 → 750`). Sınıf `kesin`, yani bu
dosyalar sert hatalı sayılıyor.

**Kod okuması:** `_prepare_upload_ready_blocks` imzayı BOŞ kimlikle ekleyip
hemen `_normalize_delivery_ids` çağırıyor; orada imza koşulsuz
`previous + 1` alıyor. Dört akışta da sıra doğru: `_finalize_translation_blocks`
(SDH-only cue'ları düşüren) → `_prepare_upload_ready_blocks`. İmza
numaralandıktan sonra cue düşüren hiçbir şey yok.

**Programın kendi köken kaydıyla karar** (teslim onaylanırken sidecar'a
çıktının SHA-256'sı yazılıyor):

```
program üretti: 0    teslim sonrası değişti: 7    kayıt yok: 6
```

**Hiçbiri programın yazdığı hâlde değil.** 13'ünün 13'ü 2026-08-27
onarımından sonra yazılmış olsa da kaynağı program değil: elle düzeltme
sırasında cue silinince imzanın numarası boşlukta kalıyor.

**Sonuç, senin iş akışın için:** elle düzeltme turundan sonra imza
numarasının yeniden normalize edilmesi gerekiyor; yoksa düzeltilen dosya
programın kendi kapısına takılıyor.

*(İki ölçüm tuzağı daha: sidecar'lar film klasöründe değil koleksiyon
kökündeki ortak `Raporlar/` altında — ilk denememde "köken kaydı yok"
sanmıştım. Ve `pre-opus` anlık görüntüleri yalnız 23 filmlik parti için
var, bu 13 dosyanın hiçbirinde yok.)*

---

# Dördüncü tur — analiz kapsamı, akış paritesi ve KAPSAM NOTU

## 11. Standart analiz derinliği chunk'ın yalnız İLK 250 cue'sunu okuyor — LATENT

```python
_ANALYSIS_DEPTH_CONFIG = {
    "standard": {"chunk_size": 2000, "sample_limit":  250, ...},
    "advanced": {"chunk_size":  900, "sample_limit":  900, ...},
    "maximum":  {"chunk_size":  550, "sample_limit":  550, ...},
}
```

`_analysis_sample_for_depth`:

```python
if depth_key == "standard":
    selected = list(range(min(limit, len(cues))))   # ilk 250, yayılmış DEĞİL
```

Standart'ta her 2000'lik chunk'ın **%87,5'i analize hiç girmiyor** ve
seçim baştan alınıyor, yayılmış örneklem değil. Derin modlarda
`sample_limit == chunk_size`, yani kapsam tam.

**Ateşlenmiyor:** raporlarda derinlik dağılımı **310 Gelişmiş / 121
Maksimum / 0 Standart**, ayardaki varsayılan da `Gelismis`. Yani bu tuzak
senin koşularında hiç çalışmıyor — ama Standart'a düşen biri için ağır.

## 12. Deyim ve kültürel referans tavanı

`idiom_map` ve `cultural_refs` 30'da tavan yapıyor (üretimde, prompt'ta değil).

- `idiom_map`: ortalama 20,5 — **21/357 dosya tavanda**
- `cultural_refs`: ortalama 15,5 — **28/357 dosya tavanda**

Ayrıca ikisi de kaynağın tamamından değil örneklemden üretiliyor
(`_evenly_sample_cues(cues, 300)` ve `200`).

## 13. Akış paritesi matrisi — bir gerçek boşluk

27 geçişi dört akışa karşı AST ile eşledim. `_run_sync` sütunu boş çıkıyor
ama bu boşluk değil: o akış işi `_write_results`'a devrediyor.

Kısmi kalan üç satır:

| geçiş | eksik olduğu akış | değerlendirme |
|---|---|---|
| Review | sync, sync+hybrid | **tasarım** — CLAUDE.md "batch only" diyor |
| TM-read | hybrid, resume, write_results | bulgu 7 |
| **Auto-Glossary** | **resume (`_wait_batch_hybrid`)** | **gerçek boşluk** |

Auto-Glossary üç akışta çağrılıyor (`_run_sync_hybrid`, `_write_results`,
`_run_hybrid`), batch kurtarma yolunda çağrılmıyor. Yani çökme sonrası
tamamlanan dosya sözlüğünü almıyor, normal tamamlanan alıyor.

---

# KAPSAM NOTU — bulguların kaçı senin koşunu etkiliyor

`.gui_settings.json` (canlı):

```
AÇIK  : hybrid, chain_ctx, clean_sdh, repair_missing, term_normalize,
        quality_report_only, backup_raw, auto_retry_files, auto_resume_crash
KAPALI: critic, polish, native, qc, review_pass, backtrans, semantic_reconcile,
        deep_delivery_semantic, condense, linebreak, cue_fill_move,
        series_memory, auto_glossary, term_normalize_apply, precontext,
        merge_cues, twowave, season_canon
mode=sync + hybrid=True  ->  akış: _run_sync_hybrid
analysis_depth = Gelismis
```

| bulgu | senin koşunda |
|---|---|
| 1 eser adı guard'ı | **CANLI** — şu an Martı'da ateşlendi |
| 2 üslup düşmesi | **CANLI** — şu an 6 karakterin 4'ü |
| 3 hitap doğrulanmıyor | **CANLI** |
| 4/5 karakter sınırları | **CANLI** |
| 7 TM yaz-only | **CANLI** (yazıyor, `_run_sync_hybrid` okuyor ama isabet yok) |
| 9 kapı bileşimi | **CANLI** — `stray_e` sınıfı devreye girince |
| 10 imza sapması | elle düzeltme kaynaklı, program değil |
| 6 sahte karakter | küçük |
| 11 standart derinlik | **latent** — hep Gelişmiş kullanıyorsun |
| 13 Auto-Glossary boşluğu | **latent** — toggle kapalı, 104 logda hiç Resume yok |
| Dizi Hafızası düzeltmelerim | `series_memory=False` — şimdilik moot, açarsan hazır |

Ayrıca: `quality_report_only=True` olduğu için bugün eklediğim tekrar
hizalaması senin koşunda **yalnız aday raporlayacak**, metne dokunmayacak.

**Kontrol ettim, sorun yok:** tekrar hizalaması çağrım `final_consistency_sweep`'in
`critic or polish or native` kapısının DIŞINDA (12 boşluk girinti) — o
kapı senin ayarınla hiç açılmıyor, hizalama yine de çalışıyor. Düz
`consistency_sweep` da koşulsuz.

---

# Beşinci tur — maliyet muhasebesi ve checkpoint depoları

## 14. Sync checkpoint: her chunk TÜM depoyu yeniden yazıyor

`_save_sync_ckpt_entry` chunk başına çağrılıyor (`_run_sync` 3 yer,
`_run_sync_hybrid` 3 yer — ikincisi senin canlı akışın). Her çağrı:
süreçler arası kilit → dosyanın tamamını oku → JSON parse → 3000 kaydı
sırala → tamamını serialize et → atomik yaz.

**Gerçek depoda ölçtüm** (`.sync_checkpoint.json`, kopya üzerinden,
gerçek dosyaya dokunmadan):

```
depo: 4.91 MB, 3000 kayıt (TAVANDA)
  oku 13.7 ms | parse 21.6 ms | sırala 0.3 ms | dump 19.8 ms | yaz 6.3 ms
  TOPLAM ~63 ms / chunk
     40 chunk ->  2.5 sn,  0.19 GB yazım
    800 chunk -> 50.2 sn,  3.84 GB yazım
```

Depo kalıcı olarak 3000 tavanında (canlı log: "1 eski kayıt düşürüldü,
3000 kayıt kaldı"), yani her yazım bir kayıt tahliye ediyor.

**Dürüst değerlendirme:** saatler süren bir koşuda 50 sn ihmal edilebilir
(~%0,5). Asıl maliyet **disk yazımı**: büyük bir koşuda ~3,8 GB, tek bir
kaydı güncellemek için. Bug değil, verimlilik kalemi.

## 15. Stage checkpoint deposunda BUDAMA YOK — kardeş depoda var

| depo | kayıt sınırı | yaş sınırı |
|---|---|---|
| `.sync_checkpoint.json` | ✅ 3000 | ✅ 30 gün |
| `.sync_stage_checkpoint.json` | ❌ yok | ❌ yok |
| `.quality_response_checkpoint/` | — | ✅ 30 gün (açılışta çalışıyor) |

`save_sync_stage_entry_to_store`'da hiçbir sınır yok; kayıt yalnız dosya
BAŞARIYLA bitince siliniyor (`clear_sync_stage_entry_from_store`). Yarım
kalan, karantinaya giden ya da vazgeçilen her dosya kaydını kalıcı
bırakıyor.

Şu an: **4,54 MB / 78 kayıt**, kayıt başına ~61 KB, en eskisi 2026-08-03
(26 gün). 26 günde 78 kayıt ≈ günde 3 → yılda ~65 MB. Acil değil ama
sınırsız, ve kardeş deposunda iki sınır varken burada hiç yok.

## 16. Maliyet muhasebesi DOĞRU çalışıyor ama bu kurulumda tamamen boş

`_verified_token_price(model, base_url, default_is_official=True)` resmi
OpenAI rotası değilse `None` döner:

```python
if not _is_official_openai_api_route(base_url):
    return None
```

Senin bütün trafiğin `https://api.shuaiapi.com/v1` üzerinden gidiyor
(`main_custom=True`), yardımcı model de `claude-haiku-4-5` (fiyat
tablosunda zaten yok). Sonuç, HER raporda:

```
Oturum token toplamı: 5,951,306  (~$0.0000 + 5,951,306 token maliyeti
                                  sağlayıcı panelinden doğrulanmalı)
```

**Bu doğru davranış** — üçüncü taraf proxy'nin fiyatını uydurmuyor, ve
koşu öncesi tahmin ekranı da aynı ayrımı yapıyor ("Doğrulanmış USD ara
toplam"). Tutarsızlık yok, bug yok.

**Ama pratik sonuç:** `MODEL_PRICE` tablosu (gpt-5.4 = 25 USD/1M) senin
koşularında hiç kullanılmıyor; maliyet özelliği kalıcı olarak sıfır
bilgi üretiyor. **Elle fiyat girişi de yok** — ayarlarda ve UI'da
`price/fiyat` anahtarı sıfır sonuç veriyor.

**Geliştirme önerisi:** API profiline "proxy fiyatı (USD/1M token)" alanı.
Profil başına tek sayı; girilirse `_verified_token_price` onu kullanır,
girilmezse bugünkü davranış aynen kalır. Böylece hem tahmin hem rapor
gerçek rotayı fiyatlandırır.

---

# Altıncı tur — içerik türü, bağlam penceresi, kaynak haritası asimetrisi

## Temiz çıkanlar

**İçerik türü tespiti (`Otomatik`) — sorun yok.** 213 rapor bloğundaki
tespitlerin **tamamı** gerçek bir `CONTENT_SCHEMAS` adına eşleşiyor
(74 şemanın 29'u kullanılmış); serbest metin kalıntısı sıfır, yani
`_match_category` çalışıyor. Kuralsız tek şema `Otomatik` (yer tutucu,
doğru); jenerik `Film` bile 10 kural taşıyor.

"316 blokta tür satırı yok" diye bir sinyal gördüm, tarihe kırınca
çözüldü: satır 2026-08-23'te eklenmiş, öncesinde sıfır, sonrasında %100.
Tarihsel, bug değil.

**Bağlam penceresi — bilinçli.** `chunk_size=25`, `context_lines=30`
(tavan 30), `lookahead_lines=15` (tavan 20). Bağlamın chunk'tan büyük
olması tasarım: istek başına 30 önceki + 25 çevrilecek + 15 sonraki.
Program buna "Güçlü bağlam" diyor. Kalite/maliyet takası, hata değil.

## 17. Kaynak haritası asimetrisi — teslimde %30 ayrışma

İki farklı eşleme var:

```
geçişler        : {str(c.index): _clean_src(c.text)}      -> NUMARA
teslim denetimi : _delivery_source_map                     -> ZAMAN
kalite taraması : _source_map_for_quality_blocks           -> ZAMAN, numaraya geri düşer
```

**Ölçüm (355 çift, 287.348 teslim cue'su):**

| | ıska |
|---|---|
| numara ile bulunamayan | 2.239 (%0,78) |
| zaman ile bulunamayan | 915 (%0,32) |

Asıl mesele ıska değil, **yanlış eşleşme**. İkisinin de çözüldüğü
284.741 cue'da:

- aynı kaynağı veriyor: 198.279 (**%69,6**)
- **FARKLI kaynak veriyor: 86.462 (%30,4), 255 dosya**

Örnekler temiz bir kaymayı gösteriyor:

```
[Ancient.Greece] teslim#518: numara->'near the'  zaman->(#517) 'The Athe'
                 teslim#519: numara->'which is'  zaman->(#518) 'near the'
```

**Dürüst sınır — bu ÖLÇÜM teslim dosyası üzerinde.** Çalışma zamanında
tüketiciler korunuyor:

- kalite taraması ve teslim denetimi zaten ZAMAN öncelikli,
- geçişler `_normalize_delivery_ids`'ten ÖNCE koşuyor, yani o noktada
  blok numaraları hâlâ kaynak numaraları,
- `_restore_tags_blocks`'a bugün eklediğim zaman damgası yedeği de bu
  sınıfın canlı olduğunu gösteriyordu (32 cue'da italik kaybı).

Yani kanıtlanan şey şu: **teslim dosyasını kaynağa NUMARAYLA bağlayan her
araç 255 dosyada %30 yanlış eşleşir.** Bu, sonradan çalışan her denetim
aracı için geçerli — benim bu oturumdaki betiklerim de dahil, o yüzden
hepsinde zaman damgasına geçtim. Kod tarafında yapılacak şey, numara
anahtarlı `{str(c.index): ...}` kalıplarını `_source_map_for_quality_blocks`
gibi zaman-öncelikli tek bir yardımcıya bağlamak; bugün işleyen bir
hata değil, ama numaralar bir kez kayarsa sessizce yanlış kaynağa bakılır.

---

# Yedinci tur — paralellik, biçim, dil tespiti

## 18. `max_workers` senin ayarında hiçbir şey yapmıyor — panel yine "4 paralel işçi" diyor

Zincirleme bağlam açıkken chunk'lar düz bir `for` döngüsünde SIRAYLA
işleniyor. `ThreadPoolExecutor(max_workers=self._max_workers)` yalnız
`else` dalında, yani **chain_ctx KAPALIYKEN**. Senin ayarın `chain_ctx=True`,
dolayısıyla `max_workers=4` ana çeviride etkisiz.

Buna karşılık `_advanced_settings_summary` koşulsuz şunu yazıyor:

```python
f"{chunk} cue / istek  ·  {context} önceki + {lookahead} sonraki  ·  "
f"{workers} paralel işçi"
```

**Bedelin ölçüsü** (219 dosya, raporlardaki "Ana Çeviri" süreleri):

```
toplam 35,6 saat / 195.833 cue     chunk (25 cue) başına ~17,3 sn
4 işçi paralel olsaydı ideal üst sınır: ~8,9 saat
```

Yani zincirleme bağlam bu arşivde kabaca **26 saat** ek süreye mal olmuş.
Bu bir hata DEĞİL — bilinçli kalite takası, ve zincirleme bağlam senin en
çok yatırım yaptığın özellik. Hata olan, panelin "4 paralel işçi" deyip
zincirleme bağlamın bunu sıfırladığını söylememesi.

## 19. ASS/VTT → SRT: belgelenmiş tasarım, bug değil

3 ASS + 5 VTT kaynak, 4 VTT Türkçe teslim, **0 ASS Türkçe teslim**.
Sebep kodda açıkça yazılı:

```
'.vtt.srt'/'.ass.srt' ise aynı-klasör modunda programın VTT/ASS çıktısının adıdır
```

Program her zaman SRT üretiyor; ASS stil override'ları (`{\an8}`, font,
konum) teslime taşınmıyor. Belgelenmiş sınır.

*Küçük not:* çıktı klasörü kaynağın adını UZANTISIYLA alıyor
(`.../episode 1/Dougram 01v2.ass/` bir DİZİN, içinde
`Fang of the Sun Dougram S01E01.srt`). Uzantıya bakan her araç bunu
altyazı dosyası sanıyor — benim taramamı da yanılttı.

## 20. Kaynak dil tespiti başarısız olunca SESSİZCE dosya adı etiketine düşülüyor

İki katmanda da aynı davranış:

```python
except Exception as e:
    log_fn(f"[{...}] Kaynak dil tespiti başarısız: {e}", "warn")
return infer_source_language_from_filename(filename)          # 12763
...
except Exception as e:
    self._log(f"Kaynak dil ön analizi başarısız: {e}", "warn")
    detected = {fp: infer_source_language_from_filename(fp)    # 38936
                for fp in auto_files}
```

Uyarı log'a düşüyor ama **çeviri devam ediyor** ve dilin artık bir tahmin
olduğunu söyleyen bir kapı yok.

**Etiketin güvenilirliği ölçüldü** (AI tespiti bilinen 108 dosya):

| | |
|---|---|
| ad etiketi YOK (ipucu veremez) | **84 (%78)** |
| ad etiketi AI ile aynı | 21 (%19) |
| **ad etiketi AI'dan FARKLI** | **3 (%3)** |

Yani geri düşüş vakaların %78'inde hiçbir şey söylemiyor; etiket
bulunduğunda ise **8'de 1'i çelişiyor**. Üstelik çelişenlerin üçü de aynı
sınıf:

```
Les.dragueurs.1959.FRENCH...   ad->French  AI->Spanish
Gang.of.Four.1989.FRENCH...    ad->French  AI->English
Le.Dossier.51.(1978).FRENCH... ad->French  AI->English
```

Sürüm adındaki `FRENCH` altyazının değil **SESİN** dilidir — etiketin
otorite olmaktan çıkarılmasının sebebi de buydu. Şimdi tam da o etiket,
tespit çöktüğünde sessiz yedek.

**Yan bulgu:** 401 KALICI bir hata ve `_is_permanent_provider_error` bunu
biliyor, ama dil tespiti kısa devre yapmıyor: 2026-08-22 logunda 11 dosya
için 11 ayrı 401 çağrısı, 37 sn sonra 11 tane daha. O koşu "çeviri
başlatılmadı" ile bittiği için zarar oluşmadı (kullanıcı yalnız ön analiz
çalıştırmış), ama gerçek bir koşuda aynı 401 sessizce ad etiketine düşerdi.

---

# Sekizinci tur — Fork 2 devrinin triyajı (koda dokunulmadı)

Brief: `plans/fork2-denetim-kod-bulgulari.md` (commit `720776b`). Bu belge
BUGÜNKÜ kod durumuna göre yazılmamış — birkaç maddesi bu oturumda zaten
kapandı. Her maddeyi kendi kodumda doğruladım.

| madde | durum |
|---|---|
| **A1** 3 imza yazılıyor | **KAPANDI** — `_delivery_middle_signature_slot` artık yok, yalnız son imza |
| **A2** ilk kimlik 0 | **ateşlenemez** — 0 yalnız ilk blok imzaysa/boş kimlikliyse çıkıyor; baş imza artık yazılmıyor. `previous = -1` tohumu duruyor |
| **A3** numara boşluğu korunuyor | **CANLI** — `[1,2,4,5] -> [1,2,4,5]` |
| **A4** normalize `unresolved` kapısında | yapısal olarak doğru, **ölçülen zarar SIFIR** |
| **B1** aynı dize farklı çeviri | **KAPANDI** — `_inconsistent_repeat_ids` var, bugün `_repeat_alignment_plan` eklendi |
| **B2** sen/siz sürüklenmesi | = bu raporun 3. bulgusu, ölçüldü (The Mark %63) |
| **B3** satır içi italik | açık (hafızada da kayıtlı) |
| **B4** sayı/tırnak çapası | **ÖLÇÜLDÜ ve REDDEDİLDİ** ↓ |
| **B5** Latin harfli İngilizce | **DOĞRULANDI** ↓ |
| **B6** biçim sızması | açık |
| **B7** çift kodlama | **DOĞRULANDI ve ölçüldü** ↓ |

## A4 ölçümü — brief'in beklentisini çürütüyor

Yalnız GERÇEK teslimlerle (kaynak dosyalar hariç; ilk denememde onlar
ölçümü kirletmişti):

```
unresolved (normalize EDİLMEZ): 100 dosya -> kimlik sorunu 0  (%0,0)
temiz      (normalize EDİLİR) : 398 dosya -> kimlik sorunu 13 (%3,3)
```

Ve o 13'ün hepsi bu raporun 10. bulgusu (elle düzeltme kaynaklı imza
boşluğu). Yani normalizasyonun kapı içinde olması gerçek bir zarar
üretmiyor; blok numaraları kapıya gelmeden zaten doğru.

## B4 — sayı çapası ölçüldü, REDDEDİLDİ

356 çift, 4.350 ayırt edici sayı çapası:

```
aynı cue'da  3.696 (%85,0)
bulunamadı     527 (%12,1)   <- Türkçede yazıyla yazılmış ya da düşmüş
KAYMIŞ         127 (%2,9)    <- 120'si ±1, yani cümle kuyruğu (meşru)
```

|kayma| ≥ 2 olan **7 adayın 7'si de yanlış pozitif**:

```
20 feet      -> "6 metre"        (birim çevrimi)
14           -> "on dört"        (yazıyla)
10 grand     -> "on bin"         (yazıyla)
90% of the…  -> cümle iki cue'ya dağılmış
```

Türkçe çeviri sayıyı yazıyla yazıyor, birime çeviriyor ve cümleyi yeniden
dağıtıyor. Tırnak çapası da çalışmaz — tırnak içi metin ÇEVRİLİYOR.
Bu, içerik-kayması için ölçülüp elenen **üçüncü** ucuz sinyal.

## B5 — doğrulandı: Latin harfli İngilizce kapıdan geçiyor

```
'kingdom of heaven'  -> english_filler: yok, foreign_script: yok
'and the of to is'   -> english_filler: yok, foreign_script: yok
```

`_ENGLISH_FILLER_RE` yalnız `um/uh/yeah/okay` sınıfını tanıyor;
`foreign_script_ids` alfabe temelli. Aradaki boşluk gerçek.

## B7 — doğrulandı: çift kodlama tarayıcının kapsamı dışında

`scan_source_encoding` VAR ama yalnız **Kiril/Yunan yanlış kod sayfası**
sınıfını hedefliyor (büyük harf oranı + sesli oranı). Brief'in vakası
`JÃ¡nos BirÃ³` — Latin harfli çift UTF-8, o testleri geçer.

Arşiv ölçümü (376 kaynak): çift-kodlama imzası taşıyan **2 dosya**, tepesi
brief'in adını verdiği Macarca dosya (69 eşleşme).

## Fork 3 sınıfları — mevcut kapsam

- **S12 Türki dil sızması:** GUI modülünde Türki dil guard'ı **hiç yok**
  (`turkic` adlı fonksiyon sıfır). `senzuralaýyş`, `jemgyýeti`, `kino`,
  `öncekindən` — hiçbiri `foreign_script_ids`'e takılmıyor (Latin harfli).
- **S13 komşu cue içerik tekrarı:** `_partial_echo_ids` VAR ve raporda
  "Komşu cue'da kısmi yankı" diye görünüyor — ama ↓
- **S14 anlam tersine çevirme:** mekanik sinyali yok; bu sınıfta okumanın
  ikamesi olmadığı hafızada da kayıtlı.
- **S15/S16:** dedektör yok.

## 21. İki dedektör cue kimliklerini ATIYOR — bulgu adreslenemiyor

```python
stats["midword_space"] = len(_midword_space_ids(blocks, src_map))   # :6960
stats["partial_echo"]  = len(_partial_echo_ids(blocks, src_map))    # :6964
```

İkisi de `_ids` kardeşi saklamıyor ve `_FINDING_CLASSES`'ta kayıtlı değil.
Sonuç: rapora SAYI giriyor, ama cue kimliği `bulgular.jsonl`'e giremiyor ve
sınıf teslim kapısına hiç ulaşmıyor. Kodun kendi yorumu (`:6749`) bu
kusurun KRİTİK sınıflar için düzeltildiğini söylüyor — bu ikisi atlanmış.

Ayrıca `owner_mismatch_ids` (`:35113`) üretiliyor ama `_FINDING_CLASSES`'ta
yok; denetim tarafındaki `delivery_owner_mismatch_ids` (`bilgi`) ile ayrı
anahtarlar.

---

# Dokuzuncu tur — Fork 3 sınıflarının ölçümü

## 22. S12 — Türki dil guard'ı iki parçalı ve ikisi de yeni sözcüğü tanımıyor

Guard nerede:

1. **Prompt talimatı** (`hybrid_translate.py:3966-3971`) — "TURKIC GUARD:
   … never drift into Uzbek, Azerbaijani, Turkmen…"
2. **Elle küratörlü sabit liste** (`:5710-5902`) — geçmiş bölümlerden
   toplanmış tekil kalıntılar: `dyz`, `guş`, `haryt bazary`, `İçki gowak`…

Yani yakalama **sözcük listesine** bağlı; listede olmayan yeni sızıntı
görünmez. Bildirdiğin dördü de listede yok.

**Ama üçünde alfabe sinyali var.** `find_garble_tokens` q/w/x'i (R_wqx
kuralı) yakalıyor — Türk alfabesinde olmadıkları için. Aynı gerekçe
`ý` (Türkmence), `ə` (Azerice), `ň` için de geçerli ama kural onları
kapsamıyor:

```
'qonuşmak lazım'        -> garble: EVET
'wagon geldi'           -> garble: EVET
'senzuralaýyş yapıldı'  -> garble: hayır   <-- ý
'öncekindən daha iyi'   -> garble: hayır   <-- ə
'Bu bir kino.'          -> garble: hayır   <-- alfabe sinyali YOK
```

**Arşiv ölçümü** (357 Türkçe teslim, 289.729 cue): `ý/ə/ň` taşıyan
**4 cue**.

| cue | değerlendirme |
|---|---|
| `cubbəsini giymek zorundadır` | **GERÇEK** — Azerice schwa, Türkçe ekli sözcükte |
| `Slovenský filmový ústav / sunar` | yanlış pozitif (Slovak künye) |
| `Durný, Čubrina tepelerinde` | yanlış pozitif |
| `Kôprový'de, adları her neyse` | yanlış pozitif |

Üç yanlış pozitifin üçü de **tek bir Slovak filminin** özel adları.
Kuralı "alfabe dışı harf + aynı sözcükte TÜRKÇE EK" diye daraltmak
kesinliği 1/1'e çıkarır (`cubbə+sini` ekli, `filmový` değil).

`kino` sınıfı alfabeyle yakalanamaz — sözcük listesi ya da model gerekir.

## 23. S16 — çevirmen parantezi: dedektör yok, temizleyici de silmiyor

SDH temizleyicisi satır İÇİ parantezi silmiyor, yalnız tam-cue etiketini:

```
'Pentekost (Hamsin Yortusu) kutlanıyor.'  -> aynen kalıyor
'(KAPI ÇARPILIR)'                          -> cue silindi
```

Yani çevirmenin eklediği açıklama teslime kadar geliyor ve onu ölçen
hiçbir kalem yok.

**Taban ölçümü değerli:** 357 teslim / 289.729 cue'da, kaynağında parantez
OLMAYAN bir cue'da teslimde parantez **sıfır kez** görüldü (80 dosyalık
alt kümede parantezli tek cue vardı, onun kaynağında da parantez vardı).

Yani bu sınıfın arşivdeki tabanı SIFIR — eklenecek bir dedektörün yanlış
pozitif zemini yok, her isabet gerçek sinyal olur. Fork 3'ün bulduğu
vakalar bu arşivde bulunmayan dosyalardan.

## S13 / S14 / S15 durumu

- **S13** (komşu cue içerik tekrarı): `_partial_echo_ids` VAR ve raporda
  "Komşu cue'da kısmi yankı" diye görünüyor — ama 21. bulgu: cue
  kimlikleri saklanmıyor, yani bulgu adreslenemiyor. Senin vurguladığın
  asıl zarar (ikinci kopyanın kaynağın içeriğini YUTMASI) ayrı bir
  ölçüm gerektiriyor; mevcut kalem yalnız yankıyı sayıyor.
- **S14** (anlamı tersine çevirme): mekanik sinyali yok. Bu oturumda
  içerik kayması için ölçülüp elenen üçüncü sinyalden sonra (sayı çapası),
  bu sınıfta da okumanın ikamesi görünmüyor.
- **S15** (bozuk kaynağı dosyanın kendisi çözüyor): ilginç ve
  mekanikleştirilebilir — aynı pasajın tekrarında kaynak doğru sözcüğü
  veriyor. Ölçmedim; ayrı bir tur gerektirir.

---

# Onuncu tur — S15 ölçümü ve raporun sinyal/gürültü oranı

## S15 — ölçüldü, dedektör olarak ELENDİ

Fikir mekanikleştirilebilir görünüyordu: aynı pasaj kaynakta iki kez geçip
yalnız bir sözcükte ayrışıyorsa, o sözcüğün biri dizgi hatasıdır ve doğru
okuma dosyanın kendisinde var.

Ölçüt dar tutuldu (aynı sözcük sayısı, tam bir konumda ayrışma, ayrışan
sözcükler Levenshtein ≤2 ve ≥4 harf, cue ≥5 sözcük). **375 kaynakta 4 aday**
ve hiçbiri dizgi hatası değil:

```
religion / religions     (çoğul)
взрывы / взрыв           (çoğul)
suit / shirt             (farklı giysi)
walking / talking        (ikisi de anlamlı)
```

Sınıf gerçek (Fork 3'ün bulduğu vaka doğru) ama **mekanikleştirilemeyecek
kadar seyrek**; ölçütü gevşetmek yanlış pozitifi patlatır.

## 24. Teslim taramasının %96'sı kullanıcının reddettiği sınıf — asıl sinyal boğuluyor

267 teslim bloğunda sayılan bütün kalemler:

| kalem | dosya | toplam | ortanca |
|---|---|---|---|
| Aşırı uzun satır | **267 (%100)** | 24.739 | 78 |
| Fazla satırlı cue | 133 | 1.980 | 3 |
| **Komşu cue'da kısmi yankı** | **206 (%77)** | **631** | 2 |
| Komşusuna taşınabilir aşırı dolu cue | 95 | 187 | 1 |
| Türkçe ekli kaynak kalıntısı | 93 | 172 | 1 |
| **Kelime ortası boşluk** | 44 | **115** | 1 |
| Yüklemsiz biten cue | 43 | 54 | 1 |
| Metne sızmış cue numarası | 35 | 38 | 1 |
| Kaynaktaki biçim etiketi kaybolmuş | 4 | 6 | 1 |
| Hece tekrarı yazım hatası | 4 | 5 | 1 |

**Oran:**

```
toplam sayılan bulgu                : 27.927
satır yapısı sınıfı (KALICI TERCİH  : 26.906  (%96,3)
  gereği düzeltme gerekçesi DEĞİL)
geriye kalan gerçek sinyal          :  1.021  (%3,7)
   bunun cue KİMLİĞİ OLMAYAN kısmı  :    746  (%73)
   ADRESLENEBİLİR gerçek sinyal     :    275  (%1,0)
```

Yani teslim taraması 27.927 sayı üretiyor, bunların **275'i (%1,0)** hem
senin kabul ettiğin bir kusur sınıfında hem de cue düzeyinde adreslenebilir.

`Aşırı uzun satır` **her dosyada** ateşleniyor, dosya başına ortanca 78 —
ve senin kalıcı tercihin "satır yapısı kaynaktaki gibi kalır". `Fazla
satırlı cue` ve `Komşusuna taşınabilir aşırı dolu cue` (CPS taşıması,
toggle'ı zaten kapalı) aynı aileden.

## 21'in gerçek boyutu

Bu ölçüm 21. bulguyu büyütüyor. Cue kimliği saklanmayan iki sınıf:

- `Komşu cue'da kısmi yankı`: **206 dosya / 631 bulgu** — üçüncü en sık kalem
- `Kelime ortası boşluk`: 44 dosya / 115 bulgu

Yani kalan gerçek sinyalin **%73'ü** rapora sayı olarak giriyor ama
`bulgular.jsonl`'e giremiyor ve hangi cue olduğu bilinmiyor. Bu iki satırlık
düzeltme (`stats["..._ids"] = ...` + `_FINDING_CLASSES` kaydı)
adreslenebilir sinyali **275'ten 1.021'e** çıkarır — dört katı.

Ayrıca bu, Fork 3'ün S13 sınıfının (komşu cue içerik tekrarı) neden
raporlardan takip edilemediğini de açıklıyor: kalem 206 dosyada ateşleniyor
ama hangi cue olduğu hiçbir yere yazılmıyor.

---

# On birinci tur — programın geneli, performansı, sağlığı

Bu tura kadar hep teslim/analiz/kalite bölgesine bakmıştım. Bu tur
programın kendisine.

## Ölçek

| modül | satır | fonksiyon | sınıf |
|---|---|---|---|
| subtitle_translator_gui.py | **46.484** | **1.160** | 5 |
| hybrid_translate.py | 15.570 | 377 | 3 |
| subtitle_formats.py | 2.011 | 70 | 0 |
| sdh_cleaner.py | 1.953 | 60 | 0 |
| translation_memory.py | 719 | 28 | 1 |
| response_integrity.py | 202 | 6 | 1 |
| **TOPLAM** | **66.939** | | |

En büyük fonksiyonlar: `_run_hybrid` **1.581 satır**, `_run_sync_hybrid`
1.457, `_build_sidebar` 1.325, `critic_pass_with_helper` 914.

## 25. 513 sessiz istisna yutma — 62'si KRİTİK yolda

`except ...: pass / continue / return` (log yok):

```
subtitle_translator_gui.py   326 çıplak except Exception  + 54 dar tip
hybrid_translate.py           59 + 15
diğerleri                     ~59
TOPLAM                       513
```

Adı yazma/teslim/kalıcılık olan fonksiyonlarda **62** tane. En kritik
olanlar: `_save_raw_backup` (2), `_persist_active_run_record` (2),
`_save_detection_cache_locked` (2), `load_sync_ckpt_store` (3),
`_write_sanitized_settings_backup` (1).

## 26. Ham yedek SESSİZCE bozuk yazılabiliyor — ve 9 dosyada yazılmış

`_save_raw_backup` içinde:

```python
try:
    blk, _ = _fill_hata_with_source(blk, raw_map)
    blk = _restore_tags_blocks(blk, raw_map)
except Exception:
    pass                      # <-- yedek yine yazılır, ama ETİKETSİZ
```

Dış yazma hatası loglanıyor (`"Ham yedek yazılamadı"`), ama bu iç hata
loglanmıyor: yedek yazılır, yalnız biçim etiketleri geri konmamış olur.
Ayrıca toggle okunamazsa (`except Exception: return`) yedek hiç yazılmaz
ve yine ses çıkmaz.

**Ölçüm (396 ham/teslim çifti):**

```
ikisinde de italik yok            248
ham yedek etiketleri taşıyor      139
HAM YEDEKTE ETİKET EKSİK            9
```

```
The.Tales.of.Hoffmann   ham  101 <i>  |  teslim 1.508 <i>
The Cruise-eng          ham   14      |  teslim    25
Tavernier.La.Vie        ham   11      |  teslim    19
```

**Neden önemli:** "ham yedekte var, teslimde yok" karşılaştırması senin
diyalog kaybını kanıtlama yöntemin. Bu 9 dosyada ham yedek sadık bir
"kalite geçişlerinden önceki hâl" değil — o karşılaştırma orada yanıltır.

## 27. Teslim taraması bir performans sorunu DEĞİL — ölçüldü

12 dedektörü gerçek dosyalarda profilledim:

```
5 dosya / 10.178 cue -> 1.053 ms toplam  =  cue başına 0,104 ms
  _midword_space_ids            324 ms  (%31)
  detect_mixed_term_renderings  213 ms  (%20)
  detect_address_register_mix   148 ms  (%14)
  _partial_echo_ids             104 ms  (%10)
  ... kalan 8 dedektör          264 ms
```

Bütün arşiv (200 bin cue) için ~21 saniye. Burada optimize edilecek bir
şey yok — kayda geçiyorum ki kimse boşuna uğraşmasın. Gerçek maliyet
kalemleri zaten bulundu: **API gecikmesi** (18. bulgu, sıralı çalışma) ve
**checkpoint yazımı** (14. bulgu, chunk başına 63 ms / 4,91 MB).

## 28. Ölü kod ve küçük düzen kalemleri

- **Hiç çağrılmayan fonksiyon: 12** (~180 satır) / ~1.700 fonksiyon —
  bu ölçekte **çok temiz** (%0,7). Üçü UI kalıntısı (`_animate_stat`,
  `_calculate_eta`, `_update_progress_speed`); `_calculate_eta` satır içi
  ETA hesabının ölü ikizi.
- **BOM (U+FEFF):** `credential_store.py` ve `tests/test_symbols_residue.py`.
  Python tolere ediyor ama düz utf-8 ile okuyan araç kırılıyor (benim
  taramam kırıldı).
- **Import maliyeti:** `subtitle_translator_gui` **920 ms**, hybrid 94 ms —
  UI kurulmadan önce ~1 saniye.
- **Sınırsız iki önbellek** (`_TERM_RE_CACHE`, `_FOREIGN_SCRIPT_RE_CACHE`);
  ikisi de pratikte küçük kalıyor (terim/dil sayısıyla sınırlı), sorun değil.

## Ölçülüp temiz çıkan

**Ayar kaydet/yükle simetrisi.** Varsayılanı AÇIK olan bir toggle'ın
`d.get()` ile yüklenip kullanıcının `false`'unu yutması klasik bir hata;
25 boolean ayarı taradım, **gerçek ihlal yok**. İki şüpheli çıktı, ikisi
de benim desenimin yanılgısıydı (`report_only` bir ayar değil pass-status
alanı; `helper_shuai_failover` yükleniyor ama grep'im ilk 6 eşleşmede
kesmişti).

---

# On ikinci tur — eşzamanlılık, kaynak, ve akış tekrarının ÖLÇÜSÜ

## 29. Dört akışın %54'ü tekrar — bir düzeltme ortalama 4,2 yerde yapılmalı

CLAUDE.md "a change usually has to be applied to all relevant flows" diyor.
Bunun büyüklüğünü ölçtüm (yorumsuz, normalize satır):

| akış | satır |
|---|---|
| `_run_hybrid` | 1.463 |
| `_run_sync_hybrid` | 1.356 |
| `_write_results` | 754 |
| `_wait_batch_hybrid` | 753 |

**İkili örtüşme (ortak normalize satır sayısı / o akışın yüzdesi):**

```
                    _run_sync_hyb   _run_hybrid   _wait_batch   _write_res
_run_sync_hybrid          -           589/43%       265/20%      379/28%
_run_hybrid            589/40%           -          284/19%      300/21%
_wait_batch_hybrid     265/35%       284/38%           -         223/30%
_write_results         379/50%       300/40%       223/30%          -
```

**Toplam:**

```
dört akışın toplam satırı        : 4.326
  yalnız bir akışta              : 1.678 farklı satır
  2+ akışta                      :   566
  3+ akışta                      :   219
  4 akışta birden                :   112

TEKRARIN KAPLADIĞI HACİM         : 2.351 / 4.326  (%54)
bir düzeltme ortalama             : 4,2 yerde tekrarlanmalı
```

Bu sayı, bu oturumda gördüğüm her şeyi açıklıyor: Dizi Hafızası'nı **5**
yerde düzeltmem gerekti, tekrar hizalamasını **4** yere bağladım, Fork 2
briefindeki A1 **3 kod yeri + 3 test** istiyordu, ve "bir akışta düzeltildi
ötekinde unutuldu" sınıfı tekrar tekrar çıkıyor. Yapısal kök burada.

**Sürüklenme taraması:** 3 akışta aynı olup 4.'de az farklı olan **126**
satır buldum; örnekleyerek baktım, hepsi iyi huylu (satır sarması,
`tgt` ↔ `_tgt_lang`, `out_path` ↔ `output_path` gibi yerel ad farkları).
Yani tekrar şu an sessiz bir bug üretmiyor — ama her yeni düzeltmede
üretme riski taşıyor.

## Ölçülüp TEMİZ çıkanlar (bu tur)

| kontrol | sonuç |
|---|---|
| Worker iş parçacığından doğrudan Tk çağrısı | **0** — 46 bin satırlık Tk uygulaması için ciddi disiplin; `_post_ui` kuralı tutuyor |
| `with` olmadan `open()` | **2**, ikisi de uygulama ömrü boyunca açık tutulan log dosyası — kasıtlı, sızıntı değil |
| Yardımcı çağrılarında ROL karışması (`key("critic")` + `base_url("qc")`) | **0** — yönlendirme tutarlı; daha önce gördüğüm 401'ler gerçek anahtar hatasıydı, karışma değil |

Bu üç negatif sonuç önemli: eşzamanlılık ve kaynak yönetimi tarafında
aranacak bir şey yok, aramaya değmez.

---

# ALTI EKSENLİ DERİN ARAMA (aşama aşama)

Koşu canlı; kod değiştirilmedi, App kurulmadı. Yeniden üretimler saf
fonksiyonlara kontrollü girdi vererek yapıldı (API çağrısı yok).

## AŞAMA 1 — Pass atlama / iptal / durum sızıntısı → **TEMİZ**

- **104 logda gerçek olay:** 1 dosya atlama, 15 durdurma, 876 `request
  cancelled` (13 koşuda yoğunlaşmış), 174 "Chunk hatası" (2 koşuda).
- **Tarihsel bug bulundu ve kapalı:** `run_20260822-211926` logunda
  kullanıcı `Domestic.Violence...srt`'yi atlıyor ve ardından 174 sahte
  "Chunk hatası" üretiliyor. Düzeltme `c2b61a1` (**2026-08-23**) —
  log ondan bir gün önce. Bugün iki dalda da `RequestCancelled` ayrı
  yakalanıp `break` ediliyor (sıralı dal ve `ThreadPoolExecutor` dalı;
  ikincisi ayrıca `cancel_futures=True` ile kapatıyor).
- **Atlanan pass raporda başarılı GÖRÜNMÜYOR:** `status="user_skipped"`
  + kısmi kapsam kaydediliyor, rapor şunu yazıyor:
  `"kullanıcı atladı; API paket kapsamı N/M (%X); ana çeviri korundu"`.
- **Durum sızıntısı YOK:** `_pass_status`, `_pass_trace`, `_pass_history`,
  `completed`, `failed` üç akışta da dosya döngüsünün İÇİNDE sıfırlanıyor.
  (`_run_hybrid` ilk taramamda "dışında" göründü — sezgim gönderim
  döngüsünü seçmişti; gerçek sıfırlama sonuç döngüsünde, 45512-46410.)
- **Kanıtlanamayan tek kalıntı:** `_complete_file_skip` yeni bir
  `RunRequestCanceller` yalnız `_is_running and not _stop_flag` iken
  kuruyor; aksi durumda iptal edilmiş canceller kalır. Ulaşılabilirliği
  gösterilemedi.

## AŞAMA 2 — API rotaları → **1 GERÇEK BULGU (düşük etki)**

**Rota sağlığı kova dışı.** `provider_retry.py`:

```python
_SHUAI_FAILOVER_PREFERRED_ROUTES = {"main": ..., "helper": ...}   # kova var
_SHUAI_LAST_WORKING_ROUTES       = {"main": "",  "helper": ""}    # kova var
_SHUAI_ROUTE_STATES = { url: {"health":..., "cooldown_until":...} }  # KOVA YOK
```

Uygunluk filtresi ve `_shuai_claim_route` bu kovasız duruma bakıyor:

```python
available = [url for _l, url in SHUAI_API_ROUTE_OPTIONS
             if float(_SHUAI_ROUTE_STATES[url]["cooldown_until"]) <= now]
```

- **Beklenen:** yardımcı pass'in 429'u yalnız yardımcı rotasını etkiler.
- **Gözlenen:** yardımcı 429 → o rota **300 sn** boyunca ANA çeviriye de
  kapalı (farklı anahtar, farklı model, farklı kota).
- **Sınırlayıcı:** hepsi cooldown'daysa `routes = (original,)` geri düşüşü
  var — tam kilit yok.
- **Gerçek etki:** 104 logdaki 242 "429" geçişinin **231'i rota özeti
  sayacı**; gerçek 429 olayı ~5 (4 Ana Çeviri, 1 Kaynak Dil Analizi).
  Yani yapısal açık gerçek, **pratikte neredeyse hiç ateşlenmemiş**.
- Kalıcı/geçici ayrımı **doğru**: 401 → `"kalıcı hata"`, 502/503 →
  `"geçici olarak kullanılamıyor"`.

## AŞAMA 3 — Prompt boyutu → **1 GERÇEK BULGU (maliyet)**

Gerçek 6 büyük dosyada `build_requests` çalıştırıldı (449 chunk):

```
chunk başına  user payload  ~889 token
              SİSTEM prompt ~4.799 token      <-- isteğin %84'ü
```

Bileşen payları (user payload içinde):

```
tr (çevrilecek cue)   %58,5      ctx (önceki)      %19,9
next_ctx (sonraki)    %12,7      sentence_groups    %4,3
prev_scene             %3,3
```

- **Sistem promptu her chunk'ta yeniden gönderiliyor.** Arşiv ölçeğinde
  ~7.833 chunk × 4.799 ≈ **37,6 milyon token** yalnız sistem promptu.
- **Sessiz kırpma bulunamadı** — ölçülen bileşenlerin hiçbiri kesilmiyor.
- **Kullanıcı göremiyor:** kod `cached_tokens`'ı okuyor (`:642`) ama
  raporlarda ve loglarda **hiç cache satırı yok** — prompt önbelleğinin
  çalışıp çalışmadığı görünmüyor. (16. bulguyla aynı kör nokta.)
- **Asimetri ölçüldü, TEMİZ:** prompt'a girmeyen bir terimin sonradan
  dayatılması sınıfı için 12 vaka koştum
  (`lady/ladies`, `mummy/mummies`, `child/children`, `crisis/crises`…):
  **0/12 asimetri.** Dayatma kapısı (`_locked_term_residue_plan`)
  enjeksiyon kapısından (`term_in_text`) DAR — güvenli yön.

## AŞAMA 4 — Bozuk yanıt ve cue sahipliği → **14/15 SAĞLAM, 1 yapısal kör nokta**

`parse_translation_payload`'a 15 kontrollü bozuk yanıt verildi
(beklenen kimlikler `{10,11,12}`):

| senaryo | sonuç |
|---|---|
| kesilmiş JSON / kapanmamış liste | 2/3 kurtarıldı, yarım obje atıldı ✓ |
| **yinelenen kimlik** | duplike kimliğin **her iki kopyası da** düşürüldü ✓ |
| **başka chunk'ın cue'su** (`99`) | **reddedildi** ✓ |
| sırası değişmiş | 3/3 — sıra değil kimlik esas ✓ |
| açıklama metni / markdown fence | 3/3 soyuldu ✓ |
| boş liste / JSON yok | 0/3, sessizce uydurmuyor ✓ |
| `{"tr":[...]}` sarmalı | 3/3 ✓ |
| boş metinli cue | düşürüldü ✓ |
| metin komşuya taşınmış | boşalan cue düşürüldü ✓ |
| **KİMLİK DOĞRU, İÇERİK YANLIŞ CUE'DA** | **3/3 KABUL — yakalanmıyor** |

Son satır yapı gereği: o katman kaynağı görmez, elinde yalnız kimlik ve
metin vardır. Aşağı akışta tek net `cue_content_owner_mismatch` (37 olay /
15 koşu, `bilgi` şiddetinde, yeniden deneme yok — 8. bulgu). Bu oturumda
bu sınıf için **üçüncü** ucuz sinyal de (sayı çapası) ölçülüp elendi.

## AŞAMA 5 — Format bütünlüğü → **2 KAYIP (biri latent)**

Sentetik örnekler `parse_subtitle`'dan geçirildi:

**Korunanlar ✓:** SRT çok satırlı yapı, `<i>`, `<b>`, `{\an8}`,
`<font color>`; aynı zaman damgalı iki cue **birleşmiyor**; ASS `{\i1}`,
`{\pos(100,200)}` override'ları; ASS `\N` → gerçek satır sonu;
ASS `0:00:01.00` → `00:00:01,000` doğru dönüşüm.

**Kayıplar:**
1. **VTT cue settings düşüyor** — `line:90% align:middle` ayrıştırmadan
   sonra yok. (Çıktı zaten SRT olduğu için tutarlı, ama VTT→VTT bir
   yuvarlak seyahat değil.)
2. **ASS `Name` alanı METNE karışıyor** — `Dialogue: ...,Default,Ali,...`
   → cue metni `'{\i1}Ali: İtalik...'`. İzole `clean_sdh_blocks` bu
   `Ali:` önekini **silmiyor**.
   **Gerçek etki: SIFIR.** Arşivdeki ASS kaynaklarında Name alanı
   tamamen boş (`hofmann's potion.ass`: 520 Dialogue, **0 dolu Name**),
   ASS türevi teslimlerdeki `Ad:` eşleşmelerinin hepsi sıradan Türkçe
   cümle (`Tekrar ediyorum:`, `Asıl mesele şu:`). Latent.

## AŞAMA 6 — Kaynak dili ve analiz önbelleği → **TEMİZ**

`load_context_cache` önbelleği şunların HEPSİ uyuşmazsa reddediyor:
dosya SHA-256 (`_sig`), `_source_hint` (kaynak dil), `target_language`,
analiz derinliği, yardımcı model, stil, şema, sözlük, sahne eşiği.

```python
if expected_source and str(d.get("_source_hint") or "").strip().casefold() \
        != str(expected_source).strip().casefold():
    return None          # farklı kaynak dil -> önbellek KULLANILMAZ
```

- Arşiv: 571 önbellek, **571'inde `_sig`**, 370'inde `_source_hint`.
  Eksik olan 201'i eski biçim — guard onları da **reddediyor** (kapalı
  yönde hata veriyor), yani yanlış dille yeniden kullanım olmuyor.
- Önbellekteki kaynak diller: en 304, es 15, ru 13, pt 12, nl 7, ar 6…
- Dil tespitinin **başarısızlık** yolu ayrı bir bulgu olarak zaten
  raporda (20. bulgu: sessizce dosya adı etiketine düşme).

---

# ON AŞAMALI TUR — ölçülen bulgular ve gerçek kapsamlı "temiz"ler

Not: on aşamadan on bulgu çıkarmadım. Dördünü gerçek yeniden üretimlerle
sonuna kadar koştum; ikisini önceki turda zaten kapsamıştım; kalanları
kapsam sayısı çıkaramadığım için AÇIK bıraktım (aşağıda listeli).

## BULGU — Türkçe `İ` sözlük aksan onarımında bozuluyor

- **Önem:** düşük (latent — arşivde hiç ateşlenmemiş)
- **Tetikleyici:** aksansız yazılmış, BÜYÜK harfle başlayan bir sözlük
  hedefi: `Isci`, `Isciler`, `Icin`
- **Beklenen:** `İşçi`, `İşçiler`, `İçin`
- **Gözlenen:** `Işçi`, `Işçiler`, `Için` (ASCII `I`)
- **Yeniden üretim:**

```python
import hybrid_translate as ht
ht.sanitize_glossary_for_turkish({"worker": "Isci"}, target_language="Turkish")
# -> {'worker': 'Işçi'}      beklenen: 'İşçi'
```

- **Kök neden:** `hybrid_translate.py:7460`

```python
lambda match, repl=correct: repl[:1].upper() + repl[1:]
```

  `"işçi"[:1].upper()` ASCII `I` verir; Türkçe `İ` için `_tr_upper`
  gerekir. Modülde 18 çıplak `.upper()` var, 4 Türkçe-duyarlı çağrı;
  **on yedisi zararsız** (UI etiketi, prompt başlığı, karşılaştırma,
  ya da zaten harf harf Türkçe işleyen gövde) — çıktıya yazan yalnız bu.
- **Gerçek etki:** arşivde büyük harfli `Isci/Isciler/Icin` sözlük hedefi
  **0**; teslimlerde yanlış biçim (`Işçi/Için`) **0**, doğru biçim 42.
  Yani hata gerçek, etkisi bugüne kadar sıfır.
- **Kullanıcıya yansıması:** böyle bir terim gelirse Türkçe metne
  `Işçi` yazılır ve terim normalizasyonu bunu "doğru" sayar.
- **Çözüm yönü:** o lambda `sdh_cleaner._tr_upper` kullansın.
- **Regresyon testi:** `sanitize_glossary_for_turkish({"w":"Isci"})`
  çıktısının `İşçi` olduğunu kilitleyen tek satırlık test. **Şu an böyle
  bir test yok** (mevcut testler aksan onarımını yalnız küçük harfle
  koşuyor).

---

## AŞAMA 1 — Geçiş sırası ve idempotanlık → **TEMİZ (120 teslim)**

120 gerçek teslimin tüm cue'ları üzerinde:

```
İDEMPOTANLIK (X vs X∘X)   fark
  SDH temizleme              0
  satır kırma                0
  etiket geri yükleme        0
  id normalizasyonu          0
SIRA (SDH∘satır vs satır∘SDH) 0
```

**"Temiz" boş değil:** üç geçişin de gerçekten dönüştürdüğünü ayrıca
gösterdim (SDH `[KAPI ÇARPILIR]` cue'sunu siliyor, satır kırma uzun
satırı bölüyor, etiket geri yükleme `<i>` ekliyor). Hafızandaki
`tur5-satir-kirma-salinimi` (86 cue'da sonsuz salınım) düzeltmesi
**tutuyor**.

## AŞAMA 3 — Unicode / homoglif → **hipotez REDDEDİLDİ (14.789 terim)**

Asıl testi tersinden kurdum: analizin KENDİ kaynağından çıkardığı terim,
`term_in_text` ile o kaynakta geri bulunuyor mu? Bulunamıyorsa terim
hiçbir prompt'a girmez.

```
367 dosya / 14.789 terim
  kendi kaynağında bulundu : 14.651 (%99,1)
  bulunamadı               :    138 (%0,9)
      129  kaynakta gerçekten YOK (analiz uydurmuş/çevirmiş)
        8  sözcük sınırı/çoğul kuralı kaçırdı
        1  boşluk biçimi
        0  NFC/NFD          <-- unicode kaçağı YOK
        0  eğri/düz kesme   <-- YOK
        0  üç nokta biçimi  <-- YOK
```

Yan bulgu: **129 sözlük girdisi hiç enjekte edilemez**, çünkü "kaynak
terim" kaynakta yok (`neuronal correlates of consciousness`,
`warrior princess`, `συλλογικά ασυνείδητα αρχέτυπα`). Ölü ağırlık.

## AŞAMA 6 — Altyazı metninin prompt yapısını bozması → **TEMİZ (310.079 cue)**

377 kaynak dosyada:

```
JSON benzeri replik                    0
üçlü ters tırnak                       0
biçim dışı XML/HTML etiketi            0
"önceki talimatları yok say" kalıbı    0
ters eğik çizgi kaçışı                 0
cue kimliği/zaman damgası benzeri      5   (çıplak sayılar: '430')
system/assistant/user ile başlayan    23   (hepsi sıradan cümle:
                                            'Technology is a life-support
                                             system.')
```

Yapısal olarak da güvenli: cue verisi `json.dumps` ile kaçırılarak
payload'a giriyor, yani metin talimat alanına taşamaz. Ayrıştırıcı
tarafını önceki turda ayrıca test etmiştim (markdown fence ve açıklama
metni soyuluyor, başka chunk'ın cue'su reddediliyor).

## AŞAMA 7 — Aynı dosyanın iki kez kuyruğa girmesi → **TEMİZ (2.977 dosya)**

```
normcase çakışması (aynı dosya farklı yazım)   0
NFC/NFD klasör adı çakışması                   0
aynı koleksiyonda aynı adlı KAYNAK             0
AYNI BASENAME farklı klasörde              411 ad / 1.331 dosya
```

411 yinelenen basename var ama **artefakt çakışması yok**: her dosyanın
kendi klasörü ve `Raporlar/`'ı var, paylaşılan koleksiyon `Raporlar/`'ında
sidecar adı içerik jetonu taşıyor (`<stem>.<hash>.source.sha256`).

Tek belirsizlik: **6 stem'de iki sidecar** (aynı dosyanın iki koşusu).
`_output_source_fingerprint_candidates` bu durumda bilerek `[]` dönüyor
("aynı stem için birden çok aday — belirsiz") ve içerik-hash geri
düşüşüne bırakıyor. Yani kapalı yönde hata veriyor.

## KOŞULMAYAN / ÖNCEKİ TURDA KAPSANANLAR

| aşama | durum |
|---|---|
| 2 — ham→final semantik kayıp | **açık.** Bilgi sınıfı bazlı (olumsuzluk, kip, sayı, hitap…) defter çıkarmadım; ham↔teslim etiket karşılaştırmasını yaptım (26. bulgu: 9 dosyada ham yedek bozuk) ama anlam sınıfları ölçülmedi. |
| 4 — karakter/hitap kanonu | önceki turda: `[:6]` ilk-görünen tuzağı (5. bulgu), üslup düşmesi (2), hitap doğrulanmıyor (3). Kılık değiştiren/aynı adlı iki karakter senaryoları **koşulmadı**. |
| 5 — sahne planı hizası | önceki turda kapsam %100 ölçüldü; "kapsam yüksek ama sahne notu YANLIŞ" alt sorusu **koşulmadı**. |
| 8 — model/parametre uyumu | **açık.** `_safe_chat_create` ortak katmanı var (CLAUDE.md), sahte istemciyle 11 sağlayıcı davranışı denenmedi. |
| 9 — yutulan istisna → yanlış başarı | kısmen: 513 sessiz yutma / 62'si kritik yolda, ham yedek bozulması ölçüldü (25-26. bulgu). Kontrollü hata enjeksiyonu **yapılmadı**. |
| 10 — soy zinciri | kısmen: sidecar belirsizliği (yukarıda), imza sapması kökeni (10. bulgu). Çoklu ham/partial seçimi **koşulmadı**. |
