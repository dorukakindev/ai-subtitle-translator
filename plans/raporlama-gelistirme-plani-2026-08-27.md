# Raporlama geliştirme planı — 2026-08-27

**Çerçeve:** program bir onarım aracı değil, kullanıcı + Codex/Claude onarım
döngüsünü besleyen bir **ölçüm aleti**. Düzeltmeyi dışarıda LLM yapıyor.
Dolayısıyla değer, otomatik düzeltmede değil **tespit kesinliğinde ve
bulgunun kullanılabilirliğinde**.

Her madde bu oturumda ölçülmüş bir kanıta dayanıyor. Sıra = uygulama sırası.
Her madde ayrı commit, ayrı ölçüm.

---

## A — Bulguları kullanılabilir yapmak

### A1. Bulgu düzeyinde düz liste (`bulgular.jsonl`)
Mevcut `ceviri_raporu.json` **dosya düzeyinde** (`delivery_audit`,
`hata_indices`…). Codex hâlâ altyazıyı açıp numara eşleştirmek zorunda.
Yeni: satır başına tek eylem —
`{id, dosya, zaman_damgasi, cue_no, sinif, guven, kaynak, teslim, ham, oneri}`.

### A2. Zaman damgası birincil anahtar
Cue numaraları teslimde yeniden numaralanıyor (SDH silmesi boşluk bırakıyor,
imza cue'ları kaydırıyor). Bu tuzağa bu oturumda ben iki kez, Codex bir kez
düştü — Codex'in ilk cue-ID eşlemesi **23.398 sahte ihlal** üretti.
Numara kalsın, **adres zaman damgası olsun**.

### A3. Güven derecesi (`kesin / muhtemel / bilgi`)
Eksik-diyalog alarmı 92 → 47'ye indirildi, içindeki gerçek kayıp hâlâ **3**.
Düz liste olarak sunulunca 47 satır okutmak için token ödeniyor.

### A4. Bulgu geri beslemesi (`bulgu_kararlari.json`)
Codex "düzeltildi / yanlış alarm" diye işaretler, sonraki koşu aynı yanlış
alarmı **tekrar yazmaz**. Şu an her turda aynı gürültü yeniden okunuyor.

---

## B — Yeni dedektörler (hepsi yalnız-rapor, kutuya gerek yok)

### B5. Ham ↔ teslim içerik koruma  ← en yüksek değer
Üç teslim dosyasında gerçek diyalog kaybı bulundu; üçü de **doğru
çevrilmişti** (ham yedekte duruyor, teslimde yok). Program 362 ham yedeği
üretiyor ve hiçbirine bakmıyor.
Ölçüt: ham'da metin taşıyan bir cue teslimde yoksa ve silinmesi beklenen
sınıfta değilse, bir geçiş içerik yok etmiş.
Bulgu **ham'daki doğru çeviriyi taşır** → onarım "şunu geri koy" olur.
İki yönlü ölçüm: bilinen 3 vakayı yakalamalı, 362 dosyada gürültü yapmamalı.

### B6. Kaynak kodlama / mojibake ön kontrolü
`Qu'est ce que l'acte de creation.srt` baştan sona yanlış kod sayfasıyla
okunup çevrildi (`ЩРН АСДСР БНОПНЯШ`). Hafızada aynı sınıftan ikinci vaka
var (%78'i yanlış). Çeviri başlamadan uyarır.
Risk ters yönde: Yunanca/Arapça/Kiril **meşru** kaynakları engellememeli —
300 gerçek kaynakta ölçülecek.

### B7. Ardışık cue'da öbek tekrarı
Devir maddesi 6: ardışık iki cue'nun ortak bitişik ≥5 sözcüklük öbeği,
kaynakta da tekrar varsa eleyerek. 181 dosyada **%58 isabet** ölçülmüş.
Uygulamadaki `adjacent_duplicate` birebir aynı cue arıyor — farklı şey.

### B8. İdempotans kontrolü
Deterministik geçişleri çıktıya bir kez daha uygula, değişiyorsa raporla.
Satır kırma **86 cue'da sonsuza dek salınıyordu**, hiçbir şey uyarmıyordu.

---

## C — Arayüz

### C9. Tek kip seçici: *Sonrası → LLM incelemesi / Doğrudan teslim*
Kullanıcı bugün 34 kutuyu elle doğru kurmuş (`quality_report_only` açık,
metni değiştiren geçişlerin tamamı kapalı). Bu düzen tek tıkla ve **nedeni
yazılı** olsun. Alttaki kutular ince ayar için yerinde kalır.

### C10. Her kutuya açıklama satırı
`ai_segment`, `semantic_reconcile`, `cue_fill_move` gibi adlar ne yaptığını
söylemiyor. Biçim: *"Ne yapar: … | LLM'e vereceksen kapalı bırak, çünkü …"*.

---

## D — Küçük ama gerçek

### D11. Doğrulanabilir `YÜKLEMEYE HAZIR` işareti
Arşivde 115 işaret var, **hiçbiri** güncel hash zinciriyle doğrulanamıyor ve
28'i bugünkü kapıya göre sert hatalı. Doğrulanamayan işaret, işaretsizlikten
kötü. İşaret dosyanın SHA-256'sını taşısın.

---

## E — Deney (çıkarsa alınır, çıkmazsa kapatılır)

### E12. spaCy ölçüm turu
Kaynak: `nCeviri-API.py` (başka bir uygulama, PySide6 + Gemini).
Alınmaya değer **iki fikri** var, gerisi bizde zaten var.

1. **Cümle devamı kararı POS ile.** Onlar
   `pos_ in [ADP, CCONJ, SCONJ, DET, PART, AUX]` diyor; biz elle yazılmış
   sözcük listesi kullanıyoruz. Codex bizim etiketleyiciyi bağımsız ölçütle
   karşılaştırdı: **%92,25 uyum**, ölçütün kendi doğruluğu %96,7. Orada
   gerçek bir açık var.
   *Ölçüm:* spaCy POS kararını aynı 209.964 cue'da koştur, %92,25'i yeniyor mu.

2. **Caps kaynakta özel ad ayrımı (`PROPN`).** Hafızada açık sınıf:
   "otomatik küçültme özel adları bozar — elle ayıkla". `PROPN` tam da eksik
   parça. The Cruise'da etiketli veri var: 71 aday, 42 gerçek hata, 45 özel ad.
   *Ölçüm:* iki yönlü — kaç özel adı korur, kaçını bozar.

**Kural:** ölçmeden bağımlılık eklenmez. spaCy model indirmesi + yükleme
süresi + bellek maliyeti var; ancak ölçüm kazandırırsa girer.

---

## Kullanıcı kararı bekleyen

### TM: dosyalar arası bellek mi, yazmayı durdurmak mı
516.903 satır var, **isabet sıfır** (nedeni bulundu: zincirleme bağlam
açıkken önbellek bayat olacağı için okuma bilinçli kapalı).
- **Seçenek A:** parmak izinden kaynak dosya hash'ini çıkar → çeviriler
  dosyalar arası yeniden kullanılır (aynı dizinin 20 bölümünde ciddi
  tasarruf). **Risk:** yanlış bir yeniden kullanım yanlış çeviriyi sessizce
  teslime sokar ve bu ölçülemez (A/B çeviri koşusu gerekir).
- **Seçenek B (güvenli):** zincirleme açıkken yazmayı da kapat, ölü satır
  birikmesin.

## Ayrı iş

Üç dosyadaki kayıp satırları ham yedekten geri koymak. Çeviriler doğru,
mekanik onarım:
- BBC Amazon With Bruce Parry 4of6 — 00:27:34 — `Portekizce konuşuyorsun.`
- The Shock of the New S01E08 — 00:43:22 — `ÇEVİRMEN: Tüm sanatçılar gibi…`
- gates of heaven eng dvd — 00:56:36 — `Genellikle ölümden ve öteki dünyadan
  söz ediyoruz.`

---

## Uygulama sırası

`A1 → A2 → A3 → A4 → B5 → B6 → C9 → C10 → B7 → B8 → D11 → E12`

B5 ve A3 önce **yalnız-rapor** olarak girer; bir koşu boyunca ne dediği
görülür, sonra sert hataya bağlanır. Bugün tam tersini yapan bir kural
yüzünden 33 dosya haksız yere engelleniyordu.

**Uyarı:** çeviri koşusu açıkken App kuran test çalıştırılmaz — bugün canlı
koşu yüzünden 4 test ortam kaynaklı düştü, koşu bitince kendiliğinden geçti.
