# Varsayılan-AÇIK geçişler ve süreç — iyileştirme brief'i (2026-08-20, Fable 5)

Kapsam: yalnız default-ON olan geçişler ve genel süreç. Kapalı geçişler
(polish, native, qc, backtrans, condense, review, repair_missing,
semantic_reconcile) kapsam DIŞI. Her madde bugünkü gerçek koşu loglarına
(`logs/run_20260820-*.log`) veya çalışan kodda doğrulanmış davranışa dayanıyor.

Default-ON envanteri: hybrid analiz (Gelişmiş), chain_ctx, critic,
deep_delivery_semantic (%35), term_normalize, quality_report_only,
clean_sdh, linebreak, backup_raw, series_memory (Dizi), consistency sweep
(her zaman), teslim taraması (her zaman), auto-lock (analiz içinde).

---

## P1-A — Terim Normalizasyonu AÇIK ama fiilen hiçbir şey düzeltmiyor

`term_normalize: True` + `quality_report_only: True` birleşimi, geçişi
kalıcı "yalnız rapor" moduna kilitliyor. Kod zaten iki katmanlı güvenlik
uyguluyor (`_validate_term_normalize_candidate` aday doğrulaması) ama
doğrulamayı GEÇEN öneriler bile uygulanmıyor.

Kanıt — bu gecenin Crowley koşusu (01:04:16):

```
Terim normalizasyonu yalnız rapor #81  | öneri='O sırada Altın Şafak'taki ustası...'
Terim normalizasyonu yalnız rapor #104 | öneri='Bu da muhtemelen Aleister Crowley...'
Terim normalizasyonu: 2 öneri yalnız raporlandı; altyazı değiştirilmedi
```

İkisi de DOĞRU düzeltmeydi (Golden Dawn→Altın Şafak, Alastair→Aleister)
ve çöpe gitti.

**Öneri:** `quality_report_only` iki ayrı kapıya bölünsün:
- "Teslim koruması yalnız rapor" (mevcut davranış, teslim engelleme kararları)
- "Terim normalizasyonu uygula" (yeni, default ON)

Uygulama yalnız `_validate_term_normalize_candidate`'ı geçen VE düzeltmenin
'correct' biçimi kilitli sözlükte ya da dosya çoğunluğunda çapalı olan alt
kümede. Gerisi rapor olarak kalır. (Politika değişikliği — kullanıcı onayı
alınarak default belirlenmeli.)

## P1-B — Analiz modelinin kendi kimlik eşlemeleri filtresiz geçiyor

Auto-lock tarafı bugün iki turda düzeltildi; ama analiz modeli KENDİSİ
`'French': 'French'` üretirse hiçbir şey yakalamıyor. Bugün çalışan kodda
doğrulandı:

```python
sanitize_glossary_for_turkish({'French':'French','Jesus':'Jesus','King':'King'})
# → hepsi aynen geçiyor
```

Kimlik eşlemesi ana modele "bu kelimeyi ÇEVİRME" demek — auto-lock'taki
bugla birebir aynı hasar sınıfı, sadece kaynağı farklı.

**Öneri:** `sanitize_glossary_for_turkish` içine dördüncü guard: kaynak==hedef
(kimlik) olan girişlerde anahtar `_AUTOLOCK_TRANSLATABLE_STOPS` ∪
`_FOREIGN_EXONYM_MAP` içindeyse girişi DÜŞÜR ve logla. Çok kelimeli
kimlikler ("Holy Ghost": "Holy Ghost" gibi) de parça bazında kontrol edilmeli.
Not: stop seti şu an GUI modülünde — hybrid_translate'ten import döngüsüz
erişim için setin hybrid_translate'e (veya ortak bir modüle) taşınması gerekir.
Testler: mevcut `AutoLockGuardTest` deseninin sanitize karşılığı.

## P1-C — Cue-fill sınıfının KAYNAĞI: prompt'ta dağılım kuralı yok

`_build_sync_system_prompt` frag etiketlerini anlatıyor ama çeviriyi frag
cue'ları arasında kaynak uzunluklarıyla ORANTILI dağıt kuralı yok (bugün
doğrulandı: prompt'ta 'dengeli/orantı/dağıt' geçmiyor). Sonuç P0-A sınıfı:
0.4 sn'lik `elements.` cue'suna 122 karakter yığılıyor (23 gerçek çift;
bugünkü taramada da dosya başına 1-3 yeni vaka).

**Öneri:** Her iki sistem prompt'una (sync + `ht.build_system_prompt` —
ikisi hizalı tutulmalı, CLAUDE.md kuralı) tek kural: *"frag grubunda çeviri
metnini cue'ların kaynak uzunluklarıyla orantılı dağıt; kısa devam cue'suna
cümlenin tamamını yığma."* Sıfır maliyet, sınıfı kaynağında azaltır.

## P1-D — Deep Delivery Semantic %35 bütçesini körlemesine harcıyor

`_adaptive_semantic_suspects` bugün: frag etiketleri + jenerik risk regex'i
(sayı/olumsuzluk/zamir) + düzgün aralıklı çapalar. Oysa elimizde artık
DETERMİNİSTİK, API'siz bulgu listesi var (`_scan_delivery_blocks`: cue_fill,
partial_echo, register azınlık cue'ları, source_residue, bitişik yineleme)
— ama bu tarama teslim ANINDA, semantic geçişlerden SONRA koşuyor.

**Öneri:** Taramayı (ucuz) `_run_final_semantic_checks`'ten ÖNCE
`sorted_blocks` üzerinde bir kez daha koş; bulgu id'lerini
`extra_suspect_reasons` olarak `build_semantic_reconciliation_clusters`'a
besle. Aynı %35 bütçe, bilinen-şüpheli cue'lara öncelikli harcanır.
Teslim anındaki tarama (rapor) aynen kalır. Dört akışta da (CLAUDE.md:
değişiklik tüm akışlara) uygulanmalı.

## P2-E — Cue-fill için deterministik taşıma geçişi (yeni, aday default ON)

Kullanıcı Death Scenes'te 23 çifti ELLE, zaman damgasına dokunmadan metni
önceki cue'ya taşıyarak düzeltti. Bu mekanik iş otomatikleştirilebilir:
tespit koşulları (CPS>30, oran>2.2, önceki<20 CPS) + aynı frag grubu +
diyalog/etiket yok ise `_find_best_split` ile bölme noktasını kaydır.
Zaman damgaları değişmez. Riskli kısım cümleyi bölmek — bu yüzden ayrı
toggle ve taşıma SONRASI iki cue'nun birleşik metninin değişmediğini
doğrulayan guard şart (condense validatörleri deseninde).

## P2-F — sen/siz karışıklığı: tespit var, düzeltme yolu yok

Bugünkü taramalar: 78/9, 47/13, 45/7, 22/9 (dört dosyada karışık). Analiz
zaten hitap haritası üretiyor; series_memory önceki bölüm kararlarını
taşıyor. Ama nihai dosyada azınlık cue'ları düzeltecek mekanizma yok —
ve bu YAMA işi değil: kullanıcının kalıcı tercihi gereği azınlık cue'ları
İngilizce kaynaktan YENİDEN ÇEVRİLMELİ (hedef hitap prompt'ta sabitlenerek).

**Öneri:** `detect_address_register_mix` mixed dediğinde ve analiz hitap
haritası tek muhatap gösterdiğinde, azınlık cue'larını mevcut onarım
makinesinden (hedef register'ı prompt'a yazarak) geçir. Azınlık tipik
9-47 cue — maliyet küçük. Default'u kullanıcı seçmeli (rapor-önce /
otomatik). Series memory'deki register kararı hangi tarafın "doğru"
olduğunun hakemi olmalı, salt çoğunluk değil.

## P2-G — Ana çeviri max_retry=1, reseller hattı dalgalı

Bu gece: `bağlantı hatası; yedek Shuai rotası denenecek · deneme 1/1`.
Sahne planının kendi merdiveni 8. denemede geçti; ana çeviri chunk'ı tek
denemeyle kalıyor. `max_retry` default 2 yapılmalı (yalnız bağlantı/5xx
sınıfı hatalarda; içerik hatalarında değil). Ucuz, kayıp chunk'ı azaltır.

## P3 — küçükler

- **Auto-lock log satırı elenenleri de yazsın**: "9 kilitlendi (…); elendi:
  French, Jesus, King (çevrilebilir sınıf)" — regresyon tek log satırından
  görülür. Bugünkü iki bug da logdan yakalandı; gözlemlenebilirlik ucuz.
- **Mitolojik/İncil adları için çeviri haritası**: 'Sisyphus' bugün kilitleniyor
  (S01E03) ama Türkçesi Sisifos. Kilidi kaldırmak yerine KÜÇÜK küratörlü harita
  (Sisyphus:Sisifos, Icarus:İkarus, Aesop:Ezop, Jesus:İsa, Moses:Musa...)
  doğru hedefi sözlüğe koysun. Stop-listesi kelimeyi serbest bırakır;
  harita doğrusunu garanti eder.
- **`Sabit terimler` sözlüğü aynı koşuda iki kez loglanıyor** (01:11:12 ve
  01:14:06, birebir aynı içerik) — log gürültüsü, tek kaynağa indirilsin.
- **Critic'e deterministik ipucu**: critic chunk'ı işlerken register-azınlık
  ve cue_fill id'leri "şüpheli cue" olarak inputa eklenebilir (critic input
  yapısı incelenmeli; ekstra API maliyeti yok).

## Bilinçli sınır — dokunma

- 2×42'ye sığmayan cue'lar modelin kendi bölmesiyle kalıyor; bunun tek
  çözümü condense ve condense bilinçli KAPALI (validatörler hazır ama
  kullanıcı "stabilize" dedi). Teslim taraması sayıyor, yeterli.
- CPS uyarısı verip condense uygulamamak DOĞRU davranış (ikinci brief'te
  de teyit edildi).

---

## Uygulama durumu (2026-08-20, Opus 5)

| madde | durum | commit |
|---|---|---|
| P1-A terim normalizasyonu kapısı | UYGULANDI — ayrı toggle, default AÇIK | ec1011b |
| P1-B kimlik eşlemesi filtresi | UYGULANDI — çok kelimeli adlar korunur | ec1011b |
| P1-C orantılı dağıtım kuralı | UYGULANDI — paylaşılan JSON_INSTRUCTION | ec1011b |
| P1-D tarama → şüpheli cue beslemesi | UYGULANDI | ec1011b |
| P2-E cue-fill taşıma | UYGULANDI — toggle, default AÇIK | 2d13f62 |
| P2-F sen/siz azınlık yeniden çevirisi | **YAPILMADI** | — |
| P2-G max_retry 1→2 | UYGULANDI + göç | ec1011b |
| P3 auto-lock elenen logu | UYGULANDI | ec1011b |
| P3 mitolojik ad haritası | UYGULANDI — CANONICAL_TURKISH_NAMES | ec1011b |
| P3 çift Sabit terimler logu | UYGULANDI | ec1011b |
| P3 critic'e şüpheli-cue ipucu | **YAPILMADI** | — |
| UI Shuai rota log tekrarı | UYGULANDI | ec1011b |
| UI dosya adı kısaltma | UYGULANDI | ec1011b |

**P2-F neden yapılmadı:** azınlık cue'larını kaynaktan yeniden çevirmek yeni bir
API yazma yolu açıyor; hedef register'ı prompt'a sabitleyip onarım makinesinden
geçirmek, hangi tarafın doğru olduğuna karar veren bir hakem (series memory +
hitap haritası) gerektiriyor. Tespit ve rapor hazır; uygulama ayrı bir tur.

**P3 critic ipucu neden yapılmadı:** critic girdi yapısı chunk bazlı; şüpheli
cue listesini oraya taşımak P1-D'deki gibi tek noktadan değil, chunk kurulumunun
içinden geçiyor. Değeri P1-D ile büyük ölçüde zaten alındı.

**P2-E ölçümü:** düzeltme öncesi ham yedeklerde 20 dengesiz çiftin 2'si taşındı
(45→11 ve 40→24 kar/sn). Kalan 18'inde birleşik metin iki satıra sığmıyor —
taşımayla çözülemez, condense işidir; teslim taraması raporlamaya devam ediyor.
