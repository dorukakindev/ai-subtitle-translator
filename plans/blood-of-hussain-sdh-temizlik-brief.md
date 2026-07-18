# The Blood of Hussain — SDH etiketi temizliği (3. tur)

**Analiz:** Opus 4.8, 2026-07-16 · **Uygulayacak:** Sonnet 5
**Hedef:** `C:\Users\K\Downloads\ÇIKTI\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO.srt`

Kullanıcı SDH etiketlerinin **tamamını** istemiyor (kalıcı tercih). Bu tur hepsini siliyor.

**Beklenen sonuç: 440 cue → ~385 cue.** Cue silinmesi bu turda NORMAL ve İSTENEN — önceki iki turun "cue sayısı sabit kalmalı" kuralı burada GEÇERLİ DEĞİL.

**Yeni `.bak` ALMA** — mevcut `.bak` orijinal baseline'ı tutuyor (assert ile koru).

---

## Kapsam: üç sınıfın tamamı silinecek

1. **Ses/eylem etiketleri** — `[ÇAN SESLERİ]`, `[İNLEME]`, `[AT KİŞNER]`, `[TEYBİ DURDURUR]`, `[♪ PUNJABİ AĞITI]` … (61 adet)
2. **Dil etiketleri** — `(Urduca konuşur)`, `(İngilizce konuşur)`, `(Punjabi konuşur)`, `(Selim, Urduca)`, `(Adam Punjabi diliyle nakleder)` (30 adet)
3. **Konuşmacı etiketleri** — `[RADYO]`, `[ANONS]`, `[KAPTAN]`, `(Selim)`, `(Zahid)`, `(Teyp kaydı)`, `(General radyoda, İngilizce)` (7 adet)

## Algoritma

Her cue'nun metni için:

1. Metindeki **tüm** `[...]` ve `(...)` etiketlerini sil.
2. Etiket silindikten sonra satırda kalan artıkları temizle:
   - Baştaki/sondaki boşluklar
   - Etiketin bıraktığı çift boşluk → tek boşluk
   - Satır tamamen boşaldıysa o satırı düşür
3. Cue'nun **tüm satırları** boşaldıysa → **cue'yu tamamen sil** (blok yok olur).
4. Kalan cue'ları **yeniden numaralandırma** — mevcut ID'ler korunacak, boşluklu gitsin. (Dosyada zaten 29 ID boşluğu var; oynatıcılar ID boşluğuna aldırmaz, zaman kodu esastır.)

## TUZAK: diyalog tiresi korunacak

Bazı etiketler `- ` diyalog tiresinden **sonra** geliyor. Tire repliğin parçası, etiketin değil — **silinmeyecek**.

| Cue | Şu anki | DOĞRU sonuç | YANLIŞ olur |
|---|---|---|---|
| #67 | `- Ne dediniz?\n- [BOĞAZ TEMİZLER]` | `- Ne dediniz?` *(2. satır boşalır, düşer)* | `- Ne dediniz?\n-` |
| #88 | `- [KIKIRDAR]\n- Ve başın gerçekten belada.` | `- Ve başın gerçekten belada.` | `-\n- Ve başın…` |
| #96 | `- (Punjabi konuşur) Ne oldu?\n- Kısrak erken doğuruyor.` | `- Ne oldu?\n- Kısrak erken doğuruyor.` | `-  Ne oldu?` *(çift boşluk)* |
| #104 | `- (İngilizce konuşur) İçeri gel.\n- Yok, yok. Seni dışarıda beklerim.` | `- İçeri gel.\n- Yok, yok. Seni dışarıda beklerim.` | — |
| #404 | `- (İngilizce konuşur) Alo?\n- Bay Murtaza'yla görüşebilir miyim?` | `- Alo?\n- Bay Murtaza'yla görüşebilir miyim?` | — |

**Kural:** Bir satır etiket silindikten sonra yalnızca `-` / `- ` kalıyorsa, o satır boş sayılır ve düşer.

## TUZAK: satıriçi etiketten sonra replik

| Cue | Şu anki | DOĞRU sonuç |
|---|---|---|
| #59 | `[KADININ NEFESİ KESİLİR] Buna inanamıyorum.` | `Buna inanamıyorum.` |
| #205 | `Tam iki gözünün arasından vurdum.\n[KIKIRDAR]` | `Tam iki gözünün arasından vurdum.` |
| #312 | `Ah, selamünaleyküm.` | *(değişmez — etiket yok)* |
| #34 | `(General radyoda, İngilizce)\nArtık size çok açık olmalı ki` | `Artık size çok açık olmalı ki` |
| #53 | `[RADYO] Size kesin güvence veriyorum:` | `Size kesin güvence veriyorum:` |
| #56 | `[ANONS] Bayanlar ve baylar,\nben kaptanınız.` | `Bayanlar ve baylar,\nben kaptanınız.` |
| #60 | `[KAPTAN] Havalimanı,\nSilahlı Kuvvetler'in kontrolü altında.` | `Havalimanı,\nSilahlı Kuvvetler'in kontrolü altında.` |
| #217 | `(Selim) Elimden geleni yapacağım, efendim.` | `Elimden geleni yapacağım, efendim.` |
| #247 | `(Zahid) Kocana\npiç bir çocuk mu sunmak istiyorsun?` | `Kocana\npiç bir çocuk mu sunmak istiyorsun?` |
| #189 | `(Teyp kaydı) 'Aşktaki talihsizlik,\nhayatın tek kederi değil.` | `'Aşktaki talihsizlik,\nhayatın tek kederi değil.` |
| #134 | `(Adam Punjabi diliyle nakleder)\n"Kerbela'da, İmam Hüseyin dedi ki:` | `"Kerbela'da, İmam Hüseyin dedi ki:` |
| #179 | `(Selim, Urduca)\nAşktaki talihsizlik, hayatın tek kederi değil.` | `Aşktaki talihsizlik, hayatın tek kederi değil.` |

## DOKUNMA: gerçek diyalogdaki parantez/tırnak

Etiket olmayan, repliğin kendisine ait işaretler **korunacak**:

- **#266** `<i>Selamünaleyküm.</i>` — `<i>` biçim etiketi, SDH değil. **Kalacak.**
- **Tırnak içindeki repliklerin tırnakları** (#61, #135-159, #416 vb.) — `"` ve `'` işaretleri SDH değil, kalacak.
- Metnin içinde anlam taşıyan hiçbir parantez yok (kontrol edildi) — ama yine de: bir `(...)` içi **replik** ise dokunma. Şu an dosyada böyle bir durum yok, hepsi etiket.

## Doğrulama

1. Dosyada hiç `[...]` etiketi kalmamalı: `\[[^\]]+\]` → **0 eşleşme**.
2. Parantez etiketi kalmamalı: `\([^)]+\)` → **0 eşleşme**.
3. `<i>` / `</i>` biçim etiketleri **korunmuş olmalı** (#266) — silinmemiş.
4. Hiçbir satır sadece `-` veya `- ` olmamalı: `^-\s*$` → 0 eşleşme.
5. Hiçbir satırda çift boşluk olmamalı: ` {2,}` → 0 eşleşme.
6. Hiçbir cue boş olmamalı (boş kalanlar silinmiş olmalı).
7. Kalan cue'ların **zaman kodları değişmemiş** olmalı; ID'ler korunmuş (yeniden numaralanmamış).
8. Silinen cue sayısını raporla (~55 bekleniyor). Silinen her cue'nun 3. tur öncesi metni **yalnızca etiketten** ibaret olmalı — replik içeren bir cue silinmişse DUR ve raporla.
9. Diyalog tireleri korunmuş: #96, #104, #404'te `- ` başlangıçları yerinde.
10. utf-8, CRLF, cue-içi `\n` korunmuş.
