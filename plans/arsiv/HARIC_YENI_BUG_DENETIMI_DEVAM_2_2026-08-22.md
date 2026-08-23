# Hariç Yeni Bug Denetimi — Devam 2 (2026-08-22)

## Denetim kimliği ve sınırı

- İncelenen HEAD: `778a5d111b3f73b1a158464c65df3a2a452ca6e0`
- İncelenen gerçek kullanım profili:
  - GPT-5.4 Reseller
  - Yardımcı Analiz
  - Sahne Analizi
  - Critic Pass
  - Dizi Hafızası
  - Zincirleme Bağlam
  - Terim Normalizasyonu
  - Teslim + Otomatik Düzeltme: **Yalnız Raporla**
- Anthropic, Bedrock ve yalnız bu sağlayıcılara ait akışlar kapsam dışı bırakıldı.
- Yalnız Batch API'ye özgü olup etkin Sync/Hybrid yolunu etkilemeyen sorunlar bu rapora alınmadı.
- Bu çalışma yalnız denetim ve raporlama çalışmasıdır. Üretim kodu, ayarlar, çeviri çıktıları ve çalışan süreç değiştirilmedi; commit oluşturulmadı.

## Önceki raporlardan hariç tutulanlar

Aşağıdaki raporlardaki maddeler yeniden sayılmadı:

- `C:\Users\K\Desktop\ALTYAZI_CEVIRI_TUM_BUGLAR_VE_DUZELTME_REHBERI.md`
- `C:\Users\K\Desktop\YENI_DERIN_BUGLAR_VE_DUZELTME_REHBERI.md`
- `DERIN_BUG_DENETIMI_2026-08-20.md`
- `HARIC_YENI_BUG_DENETIMI_2026-08-21.md`
- `HARIC_YENI_BUG_DENETIMI_DEVAM_2026-08-21.md`
- `VERIFIED_BUGS_TO_FIX.md`
- `AUDIT_FINDINGS.md`
- `AUDIT_REPORT.md`
- `BUG_RAPORU_TAM.md`
- `TUM_BUGLAR_VE_DUZELTME_REHBERI.md`
- `YENI_DERIN_BUGLAR_VE_DUZELTME_REHBERI.md`

Önceki raporlarda bulunan `<br>` kaynak metni birleşmesi, görünmez `{username}`, VTT surrogate/noncharacter, Batch sahiplik eşleşmesi, kanıtsız İngilizce kalıntı muafiyetleri ve boş `output_path` ile yüklemeye hazır işareti gibi maddeler de bu raporda tekrarlanmadı.

## Yöntem ve doğrulama

- Etkin akış, kaynak dosyanın okunmasından yardımcı analize; sahne bağlamından ana GPT-5.4 çeviri isteğine; Critic, Dizi Hafızası, Terim Normalizasyonu ve teslim raporuna kadar statik olarak izlendi.
- Bulgular, ağ çağrısı yapmayan küçük yeniden üretimlerle doğrulandı.
- Seçili mevcut regresyon paketi çalıştırıldı:

  ```text
  python -m unittest tests.test_default_helper_analysis tests.test_analysis_retry tests.test_series_memory tests.test_term_normalize tests.test_scene_plan
  Ran 143 tests — OK
  ```

- GUI `App()` oluşturulmadı; gerçek çeviri çalışmasına ve ortak çalışma durumuna dokunulmadı.
- Mevcut testlerin yeşil olması aşağıdaki açıkları geçersiz kılmıyor: bazı testler eksik sözleşmeyi sınarken bazı açıklar için hiç regresyon testi bulunmuyor.

## Özet

| No | Öncelik | Etkilenen etkin özellik | Doğrulanmış sorun |
|---:|:---:|---|---|
| 1 | P1 | Sahne Analizi + ana GPT-5.4 çevirisi | Bir chunk birden çok sahneyi kapsadığında sahnelerin cue aralıkları ana payload'dan siliniyor. |
| 2 | P1 | Yardımcı Analiz | İlk analiz chunk'ı fallback ise sonraki geçerli tonun önüne geçiyor. |
| 3 | P1 | Dizi Hafızası | Sonradan öğrenilen karakter üslubu RAM'de güncelleniyor fakat diske kalıcı yazılmıyor. |
| 4 | P2 | Sahne Analizi + Critic | Anlamsal alanları boş sahne kaydı, Critic'te önceki sahne bağlamını yanlışlıkla taşımaya devam ediyor. |
| 5 | P2 | Terim Normalizasyonu + yalnız raporla teslim | Kilitli kaynak terimin apostrofsuz Türkçe ek almış kalıntısı tespit edilmiyor. |
| 6 | P2 | Yardımcı Analiz / karakter sesi | Model boş karakter örnekleri döndürse bile aşama başarılı ve cache'lenebilir sayılıyor. |
| 7 | P2 | Yardımcı Analiz cache'i | Analiz prompt ve şeması değiştiği halde cache semantik sürümü uzun süredir değişmediği için eski analiz tekrar kullanılabiliyor. |

---

## 1. Çok sahneli ana çeviri payload'ında sahne-cue sahipliği kayboluyor

**Öncelik:** P1 — yüksek kalite riski  
**Etkin yol:** Sahne Analizi → ana GPT-5.4 Reseller çevirisi

### Kod izi

- `hybrid_translate.py:2959-2985` — `_scene_plan_payload_entry`, sahne girdisinden `start` ve `end` alanlarını bilerek çıkartıyor.
- `hybrid_translate.py:2988-3013` — `_scene_context_for_chunk`, chunk ile kesişen bütün sahneleri döndürüyor.
- `hybrid_translate.py:13836-13841` — sonuç `payload["scene"]` olarak ana çeviri isteğine ekleniyor.
- `hybrid_translate.py:3931-3933` — prompt modele `scene.referents` gibi alanları kullanmasını söylüyor, fakat bunların hangi cue'lara ait olduğunu söylemiyor.

### Kanıt

Sahneler:

```python
[
    {"start": 5, "end": 10, "summary": "A", "referents": {"it": "the poison"}},
    {"start": 11, "end": 16, "summary": "B", "referents": {"it": "the machine"}},
]
```

Chunk aralığı `8-14` olduğunda etkin yardımcı:

```python
[
    {"summary": "A", "referents": {"it": "the poison"}},
    {"summary": "B", "referents": {"it": "the machine"}},
]
```

döndürüyor. Model, 8-10 numaralı cue'ların A'ya; 11-14 numaralı cue'ların B'ye ait olduğunu artık göremiyor. Akıllı chunker sahne kesimine yakın sınır arasa da her durumda sahne sınırında bölmeyi garanti etmediğinden çok sahneli chunk meşru olarak oluşabiliyor.

Mevcut testler eksik sözleşmeyi yanlışlıkla sabitliyor:

- `tests/test_scene_plan.py:325-333` — `start/end` alanlarının atılmasını bekliyor.
- `tests/test_scene_plan.py:363-374` — birden çok sahneyi aralıksız döndürmeyi bekliyor.

### Etki

- Zamir ve gönderme çözümü çelişkili hale gelebilir.
- Sahne hedefi, ton, ilişki veya terim bilgisi yanlış cue'ya uygulanabilir.
- Yardımcı analiz raporu sahne kapsamını tam gösterebilir; ancak gönderilen bağlam modele göre eşlenebilir değildir.

### Neden önceki bulgudan farklı

Önceden giderilen/raporlanan “yalnız ilk kesişen sahnenin gönderilmesi” sorunundan farklıdır. Burada bütün sahneler gönderiliyor; yeni açık, sahnelerin cue aralıklarının kaybedilmesidir.

### Düzeltme yönü

Her sahne payload girdisinde chunk'a kırpılmış veya asıl `start/end` cue aralığı korunmalı; sistem promptu bu aralıkların anlamını açıkça belirtmeli.

### Kabul testleri

1. `5-10` ve `11-16` sahnelerini kapsayan `8-14` chunk'ında iki sahne de doğru cue aralığıyla kalmalı.
2. Tek sahneli chunk davranışı değişmemeli.
3. Olmayan sahne sınırı uydurulmamalı.
4. Raporlanan sahne kapsamı, gerçekten cue'ya eşlenebilir kapsamı ölçmeli.

---

## 2. İlk degraded/fallback analiz chunk'ı sonraki geçerli tonu eziyor

**Öncelik:** P1 — doğrudan çeviri üslubu riski  
**Etkin yol:** Yardımcı Analiz → ana GPT-5.4 promptu

### Kod izi

- `hybrid_translate.py:2673-2718` — başarısız analiz için `tone/summary = "fallback"` ve `_analysis_degraded=True` üretiliyor.
- `hybrid_translate.py:3662-3760` — `_merge_memories`, ilk belleği taban alıyor ve ilk dolu `tone`/`setting` değerini seçiyor.
- `hybrid_translate.py:3765-3781` — `_infer_register`, `fallback` tonunu genel register'a indiriyor.
- Birleştirme çağrısından sonra herhangi bir chunk degraded ise bütün analiz degraded işaretleniyor ve cache yazımı engelleniyor; fakat kirlenmiş ton canlı çeviri isteğinde yine kullanılıyor.

### Kanıt

İlk bellek fallback, ikinci bellek geçerli `serious drama` tonu ve `courtroom` mekânı içerdiğinde birleştirilmiş sonuç:

- özet: `fallback | <geçerli özet>`
- setting: `courtroom`
- tone: `fallback`
- register: `general`

oluyor. Yani sonraki gerçek analiz mevcut olduğu halde ilk fallback tonu kazanıyor.

### Etki

- Filmin/dizinin gerçek tonu ana çeviri promptuna taşınmıyor.
- İlk chunk'taki geçici API/JSON sorunu bütün dosyanın register'ını genelleştirebiliyor.
- Yardımcı analiz tokenleri harcanıyor; fakat geçerli sonuçtan yararlanılmıyor.
- Degraded işareti cache'i korusa da aynı çalıştırmadaki çeviri kalitesini korumuyor.

### Düzeltme yönü

En az bir non-degraded bellek varsa scalar `tone`, `setting`, `summary` ve karakter kararlarında degraded bellekler seçim havuzundan çıkartılmalı. Genel degraded bayrağı cache politikası için korunmalı.

### Kabul testleri

1. Fallback ilk + geçerli drama ikinci → drama tonu/register'ı, fakat global degraded `True`.
2. Geçerli ilk + fallback ikinci → geçerli ton korunmalı.
3. Bütün chunk'lar fallback → mevcut genel fallback davranışı sürmeli.

---

## 3. Dizi Hafızası'nda sonradan öğrenilen karakter üslubu diske kaydedilmiyor

**Öncelik:** P1 — bölümler arası süreklilik kaybı  
**Etkin yol:** Dizi Hafızası

### Kod izi

- `series_memory.py:428-455` — `merge_characters`, mevcut karakterin boş `style` alanını yeni dolu değerle RAM'de güncelliyor.
- `series_memory.py:309-367`, özellikle `327-344` — `_merge_saved_data`, disk kopyasını taban alıyor ve kimliği diskte zaten bulunan bellek öğesinin yeni değerini genel olarak yok sayıyor.

### Kanıt

No-network yeniden üretim:

1. Birinci bölümde `John` boş üslupla kaydedildi.
2. Bellek yeniden yüklendi.
3. İkinci bölüm analizi `John.style = "formal"` üretti.
4. RAM'de `formal` görüldü.
5. Kaydedilip yeniden yüklendiğinde diskteki değer yine boş kaldı.

Gözlenen özet:

```text
ilk kayıt: True
RAM:  John -> style=formal
ikinci kayıt: True
disk: John -> style=""
```

### Etki

- Sonraki bölümde öğrenilen hitap/üslup bilgisi aynı oturumda varmış gibi görünür, uygulama yeniden açıldığında kaybolur.
- Karakter sesi ve sen/siz sürekliliği bölümden bölüme kararsızlaşabilir.
- Raporlar belleğin güncellendiğini düşündürebilir; kalıcı dosya gerçekte güncellenmemiştir.

### Neden önceki bulgulardan farklı

Önceki karakter kimliği/casefold çatışmalarından farklıdır. Burada kimlik doğrudur; boş alanın sonradan güvenli biçimde zenginleştirilmesi save/reload sınırında kaybolur.

### Düzeltme yönü

Karakter birleştirmesinde, disk stili boş ve RAM stili doluysa boş alan zenginleştirilmelidir. İki taraf da dolu ve farklıysa mevcut “ilk doğrulanmış kararı koru/çatışmayı raporla” ilkesi sürmelidir.

### Kabul testleri

1. Boş → `formal` güncellemesi save/reload sonrasında kalmalı.
2. `formal` → farklı dolu değer sessizce ezilmemeli.
3. Eşzamanlı farklı karakter kayıtları kaybolmamalı.
4. Kaynak bölüm/origin meta verisi korunmalı.

---

## 4. Critic'te boş sahne kaydı önceki sahne bağlamını sızdırıyor

**Öncelik:** P2 — bağlama bağlı yanlış öneri riski  
**Etkin yol:** Sahne Analizi → Critic Pass

### Kod izi

- `hybrid_translate.py:1950-2007` — `_sanitize_scene_plan_entry`, `start/end` bulunan fakat bütün anlamsal alanları boş olan girdiyi geçerli kabul ediyor.
- `hybrid_translate.py:2010-2044` — `_bind_scene_plan_to_requested`, bu girdiyi kapsamın parçası sayıyor.
- `hybrid_translate.py:2959-2985` — `_scene_plan_payload_entry`, anlamsal alanı olmayan girdiyi `None` yapıyor.
- `hybrid_translate.py:13127-13134` — Critic çifti ancak scene değeri truthy ise `scene` alanı yayıyor.
- `hybrid_translate.py:13243-13244` — Critic promptu, yeni bir `scene` alanı gelene kadar önceki sahne bağlamının taşınacağını söylüyor.

### Kanıt

Üç ardışık cue için sahne planı `A → boş → C` olduğunda gönderilen çiftler:

```text
cue 1: scene=A
cue 2: scene alanı yok
cue 3: scene=C
```

Prompt sözleşmesine göre cue 2, yeni sahne bilgisi gelmediği için A altında değerlendiriliyor. Oysa plan açıkça A'dan çıkıp anlamsal verisi boş ayrı aralığa geçmiş durumda.

### Etki

- Critic, geçerli bir çeviriyi önceki sahnenin özne/gönderme/duygu bilgisiyle yanlış değerlendirebilir.
- “Yalnız raporla” modunda dosya otomatik bozulmaz; fakat rapor gereksiz veya yanlış düzeltme önerileriyle kirlenir.
- Kullanıcıya gönderilen inceleme yükü ve Critic maliyeti artar.

### Düzeltme yönü

Sahne geçişi boş/anlamsız bir girdiye geldiğinde açık bir reset işareti gönderilmeli (`scene: []`, `scene_reset: true` gibi) veya her cue'ya güncel sahne açıkça bağlanarak carry sözleşmesi kaldırılmalı.

### Kabul testleri

1. `A → boş → C` geçişinde ikinci cue A'yı miras almamalı.
2. Aynı sahnenin ardışık cue'larında kompakt taşıma davranışı korunabilir.
3. Kapsanmayan cue önceki sahnenin referanslarını kullanmamalı.

---

## 5. Terim Normalizasyonu apostrofsuz Türkçe ek alan kilitli kaynak terimini kaçırıyor

**Öncelik:** P2 — çevrilmeden kalan terimin teslim raporundan kaçması  
**Etkin yol:** Terim Normalizasyonu + Teslim “Yalnız Raporla”

### Kod izi

- `subtitle_translator_gui.py:12055-12120` — kilitli kaynak terimi kalıntısı taranıyor.
- `subtitle_translator_gui.py:12095-12096` — kaynak terim, `(?<!\w)<source>(?!\w)` sınırıyla aranıyor.
- `subtitle_translator_gui.py:5380-5415` — genel son kalıntı taraması yalnız `_APOSTROPHE_SUFFIX_TOKEN_RE` biçimini tarıyor; kilitli terimler ayrıca bu genel yoldan muaf tutuluyor.

### Kanıt

Kilitli terim `Memories → Anılar` iken:

```text
Memories geri geldi.       -> yakalanıyor
Memories'leri geri geldi.  -> yakalanıyor
Memoriesleri geri geldi.   -> yakalanmıyor
```

Üçüncü biçim ne Terim Normalizasyonu kalıntı taramasına ne de genel yabancı-kalıntı taramasına düşüyor.

### Etki

- `Memoriesleri`, `Troylar` gibi çevrilmeden kalmış kaynak kökü + Türkçe ek birleşimleri “temiz” raporlanabilir.
- Teslim modu yalnız raporladığı için kullanıcı, gerçek kalıntıyı logda görmeyebilir.
- Kilitli terim tutarlılığı dosyanın bazı cue'larında sessizce bozulabilir.

### Düzeltme yönü

Kilitli kaynak kökü; çıplak, apostroflu ekli ve doğrulanmış Türkçe ekin doğrudan bitiştiği biçimlerde aranmalı. Rastgele daha uzun İngilizce kelimeleri eşleştirmemek için mevcut Türkçe ek doğrulayıcısı kullanılmalı.

### Kabul testleri

1. Çıplak `Memories`, `Memories'leri` ve geçerli ekli `Memoriesleri` yakalanmalı.
2. `Memoriescape` gibi başka bir kelime yakalanmamalı.
3. Source==target veya bilerek korunan özel adlar yanlış uyarı üretmemeli.
4. Doğru hedef çekimi `Anılarımız` yabancı kalıntı sayılmamalı.

---

## 6. Boş karakter örneği yanıtı başarılı ve cache'lenebilir sayılıyor

**Öncelik:** P2 — Yardımcı Analiz kapsamı ve karakter sesi kalitesi  
**Etkin yol:** Yardımcı Analiz → karakter örnekleri

### Kod izi

- `hybrid_translate.py:1712-1800` — karakter örneği üreticisi JSON'da `examples` ve `styles` anahtarlarını arıyor; adları temizleyip filtreledikten sonra iki sonuç da boş olsa bile durumu koşulsuz `True` kaydediyor.
- `hybrid_translate.py:973-980` — `_retry_failed_analysis_aux`, yalnız durumu `False` olan yardımcı analizi yeniden deniyor.
- `hybrid_translate.py:3512-3619` — cache/degraded kararı da yalnız başarısız durum üzerinden veriliyor.

### Kanıt

İstenen karakter listesi `John` içerirken sahte fakat şema bakımından geçerli GPT yanıtı:

```json
{"examples": {}, "styles": {}}
```

Sonuç:

```python
result = ({}, {})
status = {"character_examples": True}
```

### Etki

- Gerçekte hiçbir karakter sesi üretilmediği halde yardımcı analiz “tamamlandı” görünür.
- Yeniden deneme yapılmaz.
- Boş karakter örnekleri cache'e girip sonraki çalışmalarda yeniden kullanılabilir.
- Analiz/harcama raporu bu pass'in faydasını olduğundan yüksek gösterir.

### Düzeltme yönü

İstenen karakter listesi doluysa ve kanonik istenen karakterlerin hiçbirinde geçerli örnek/üslup yoksa aşama başarısız sayılmalı. Kısmi sonuçlar ayrı `partial`/coverage durumu olarak raporlanmalı.

### Kabul testleri

1. İstenen karakter dolu + boş sonuç → başarısız ve hedefli tek retry.
2. Yalnız bilinmeyen karakter adları → başarısız.
3. Kanonik karakterlerin bir kısmı dönmüşse “tam başarı” değil açık kısmi kapsam.
4. Başlangıçta karakter yoksa boş sonuç başarı sayılabilir.

---

## 7. Yardımcı Analiz cache'i prompt/şema değişikliklerinde geçersizleşmiyor

**Öncelik:** P2 — eski hatalı analizin yeni kodda sessizce tekrar kullanılması  
**Etkin yol:** Yardımcı Analiz + Sahne Analizi + Dizi Hafızası

### Kod izi

- `hybrid_translate.py:862` — `CONTEXT_ANALYSIS_CACHE_VER = 4`.
- `hybrid_translate.py:865-884` — `analysis_fingerprint`; kaynak/ayar/model/URL/şema/glossary/gap ve sabit v4 değerini kapsıyor, fakat analiz promptu, parser'ı, sanitizer'ı veya yardımcı alt-şema semantik revizyonunu kapsamıyor.

### Kanıt

`git blame` ve commit geçmişinde cache v4'ün 2026-08-01'den beri aynı kaldığı; sonrasında sahne planı tamamlama, zamir/deyim kurtarma, analiz karakter kimliği ve üslup çatışmaları gibi çok sayıda yardımcı-analiz davranışının değiştiği doğrulandı. Kaynak dosya ve kullanıcı ayarları aynı kaldığında fingerprint de aynı kaldığı için eski v4 cache yeni kodda hit olabiliyor.

### Etki

- Kullanıcı düzeltmeden sonra aynı altyazıyı tekrar çalıştırsa bile iyileştirilmiş analizi hiç çağırmayabilir.
- Eski sahne/karakter/terim kararları ana GPT-5.4 çevirisine tekrar enjekte edilebilir.
- Log “cache kullanıldı” der; fakat cache'in güncel semantik sözleşmeyle üretildiğine dair güvence yoktur.
- Sorun API sağlayıcısından değil, yerel cache kimliğinin eksikliğinden kaynaklanır.

### Neden önceki cache bulgusundan farklı

Önceki denetimde kaynak, ayar ve analiz derinliği değişikliklerinin cache'i doğru geçersizleştirdiği doğrulanmıştı. Bu yeni bulgu, kod içindeki prompt/parser/şema davranışı değiştiğinde semantik sürümün değişmemesidir.

### Düzeltme yönü

Mevcut cache sürümü yükseltilmeli ve fingerprint'e ayrı bir `ANALYSIS_SEMANTIC_REVISION` eklenmeli. Analiz promptu, parser/sanitizer veya yardımcı çıktı şeması davranışı değiştiğinde bu revizyon zorunlu olarak artırılmalı.

### Kabul testleri

1. Aynı kaynak ve ayarlarda rev4 → rev5 geçişi cache miss vermeli.
2. Aynı rev5 sözleşmesi ikinci çalıştırmada cache hit vermeli.
3. Eski/eksik cache güvenli biçimde miss olmalı; çalışma çökmemeli.

---

## Elenen yanlış alarmlar ve bilinçli kapsam dışı bırakılanlar

- **Yardımcı analiz örnekleme underfill'i:** Üretim yolunda analiz derinliğinin etkin chunk boyutu örnekleme sınırıyla uyumlu olduğundan yeniden üretilemedi.
- **GPT-5.4 Reseller 429/5xx retry eksikliği:** `_safe_chat_create`, Shuai/provider retry katmanına doğru delege ediyor; bu turda yeni bir retry açığı doğrulanmadı.
- **Critic `apply_changes=False`:** “Yalnız Raporla” ayarında bilinçli davranıştır; bug değildir.
- **Teslim karantinasının çalışmaması:** “Yalnız Raporla” seçiminin beklenen sonucudur; bug değildir.
- **Zincirleme Bağlam:** `prev_tr` sahipliği, sıra ve reset yolları etkin Sync/Hybrid akışında ayrıca izlendi; bu turda önceki raporlardan farklı, tek başına doğrulanmış yeni bir açık bulunmadı.
- **Critic'te yerel + API aynı öneriyi iki kez üretir iddiası:** Yerel ilk aşama `allow_context_sensitive=False` kullandığı için şüphe doğrulanmadı.
- **Anthropic/Bedrock stop reason, checkpoint ve token muhasebesi:** Kullanıcının etkin sağlayıcı yolu olmadığı için incelenmedi/raporlanmadı.
- **Yalnız Batch API sahiplik ve resume ayrıntıları:** Etkin GPT-5.4 Reseller Sync/Hybrid profilini paylaşmayan kısımlar kapsam dışında bırakıldı.
- **Eski/yeni sahne cache karışımı adayı:** Üretim provenance'ı kesin doğrulanamadığı ve mevcut test sözleşmesi bilerek izin verdiği için bulgu yapılmadı.
- **Critic şema doğrulayıcısındaki per-pass kimlik/metin konusu:** Önceki raporda bulunduğu için burada tekrar edilmedi.

## Önerilen düzeltme sırası

1. Çok sahneli payload'a cue aralıklarını geri koymak.
2. Degraded analizin geçerli tonu ezmesini engellemek.
3. Dizi Hafızası karakter üslubu save/reload birleştirmesini düzeltmek.
4. Critic boş sahne geçişine açık reset eklemek.
5. Kilitli terim + apostrofsuz Türkçe ek kalıntısını tespit etmek.
6. Boş karakter örneğini başarı saymamak ve kısmi kapsamı raporlamak.
7. Analiz cache semantik revizyonunu yükseltmek ve kalıcı bir sürümleme kuralı koymak.

Her düzeltme, bu rapordaki kabul testini yeniden üreten ayrı regresyon testiyle yapılmalı. Arka planda başka bir düzeltici çalıştığı için uygulama başlamadan önce HEAD yeniden okunmalı; satır numaralarının veya ilgili kodun değiştiği varsayılmalıdır.

## Sonuç

Bu turda, önceki raporlardan farklı **7 doğrulanmış yeni bug** bulundu. Üçü ana kalite ve süreklilik açısından P1; dördü aktif passlerin kapsam/doğruluk raporlamasını etkileyen P2 seviyesindedir. Kullanılmayan API sağlayıcıları ve yalnız teorik adaylar sayıya dahil edilmemiştir.
