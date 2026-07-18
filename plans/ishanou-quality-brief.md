# Ishanou (1990) — düzeltme brief'i

**Analiz:** Opus 4.8, 2026-07-17 · **Uygulayacak:** Sonnet 5

**Hedef (düzenlenecek):**
`C:\Users\K\Downloads\ÇIKTI\Ishanou AKA The Chosen One (1990) (1080p BDRip x265 10bit EAC3 2.0 - timesuck)\Ishanou AKA The Chosen One (1990) (1080p BDRip x265 10bit EAC3 2.0 - timesuck).srt` (435 cue)

**Kaynak (VTT, masaüstünde):**
`C:\Users\K\Desktop\Ishanou AKA The Chosen One (1990) (1080p BDRip x265 10bit EAC3 2.0 - timesuck).vtt` (436 cue)

## Bağlam: boru hattının kuyruğu düşmüş

Çeviri çökme sonrası batch resume ile tamamlanmış. Log:
```
⚠ Resume: kaynak dosya bulunamadı — etiket geri yükleme /
   [HATA] işaretleme ve TM/QC bu dosyada atlanacak
```
Kaynak masaüstündeydi, uygulama bulamadı. Sonuç: **`_restore_tags_blocks` hiç çalışmadı**, TM/QC atlandı. Polish'i kullanıcı kapatmıştı; sadece Critic çalıştı (3 satır düzeltti).

**Çeviri kalitesi genel olarak iyi** — nesir akıcı, şarkılar düzgün, sözlük temiz (Somalice sızıntısı YOK). Aşağıdakiler noktasal.

**Kurallar:** Zaman kodları değişmez. `\n` = satır bölünmesi. `.bak` al (bu dosyanın henüz yedeği yok).

---

## A. Cue içerik kayması — #6-#9 (ÖNCELİK 1, senkron bozuyor)

Replikler bir cue geri sızmış. İçerik kaybolmamış, yanlış cue'da. #9 tamamen yok.

| Cue | Kaynak | Şu anki | Olacak |
|---|---|---|---|
| #6 | `- And these dolls too?`<br>`- Yes` | `- Bu bebekleri de o mu aldı?`<br>`- Evet.`<br>`- İki tane mi aldı?` | `- Bu bebekleri de o mu aldı?`<br>`- Evet.` |
| #7 | `- He bought two?`<br>`- Yes.` | `- Evet.` | `- İki tane mi aldı?`<br>`- Evet.` |
| #8 | `- He bought the dress too?`<br>`- Yes` | `- Elbiseyi de o mu aldı?`<br>`- Evet.`<br>`Çok güzel görünüyor!` | `- Elbiseyi de o mu aldı?`<br>`- Evet.` |
| **#9** | `It looks nice!` | **CUE YOK** | **CUE'YU GERİ EKLE:** `Çok güzel görünüyor!` |

**#9'un zaman kodunu kaynaktan (VTT) al.** Cue #8 ile #10 arasına, doğru ID ve zaman koduyla yerleştir.

> Bu düzeltme #6'nın CPS'ini de çözer (şu an 37 kar/sn — üç satır olduğu için).

## B. Modelin uydurduğu parantez içi açıklamalar (ÖNCELİK 1)

Kaynakta bu parantezlerin **hiçbiri yok**. Model açıklama/meta-not eklemiş. Altyazıda ansiklopedi notu olmaz.

| Cue | Kaynak | Şu anki | Olacak |
|---|---|---|---|
| #22 | `Is his family coming for`<br>`Bembem's ear-piercing ceremony?` | `Ailesi Bembem'in`<br>`kulak delme törenine (geleneksel tören) gelecek mi?` | `Ailesi Bembem'in kulak delme`<br>`törenine gelecek mi?` |
| #24 | `Though they are coming`<br>`from Cachar which is quite far.` | `Hem Cachar'dan (uzak bir yer)`<br>`geliyorlar, epey uzak.` | `Hem Cachar'dan geliyorlar,`<br>`epey uzak.` |
| #27 | `The third day after the`<br>`new moon, on Monday.` | `Yeni aydan (hilal sonrası dönem) sonraki`<br>`üçüncü gün, pazartesi.` | `Yeni aydan sonraki`<br>`üçüncü gün, pazartesi.` |
| #154 | `As for the posting, I'll know`<br>`when I report to head office.` | `Atamayı, merkez ofise`<br>`(açıklama ofisi) gidince öğreneceğim.` | `Atamayı, merkez ofise`<br>`gidince öğreneceğim.` |

**#154 özellikle kötü** — "açıklama ofisi" diye bir şey yok, model meta-not sızdırmış.
**#24 notu** — parantez zaten gereksizdi: cue'nun kendisi "epey uzak" diyor.

## C. `<i>` etiketlerinin geri yüklenmesi — 78 cue (ÖNCELİK 1)

Kaynakta 78 cue'da `<i>` var (filmin şarkıları), çıktıda **sıfır**. `_restore_tags_blocks` resume'de atlandı.

**Elle yazma — mevcut fonksiyonu kullan:**
```python
from subtitle_formats import restore_format_tags
```
`subtitle_formats.py:91` — boru hattının bu iş için kullandığı fonksiyon. `subtitle_formats.py:114` civarında `^\s*<[a-zA-Z]` ile idempotency guard'ı var, iki kez uygulanması zararsız.

Her cue için: kaynak satırındaki `<i>...</i>` sarmalını çeviri satırına uygula. Kaynak (VTT) ve çıktı (SRT) cue ID'leri **birebir eşleşiyor** (#9 hariç, A'da geri ekleniyor).

Dikkat edilecek desenler kaynakta:
- Tam satır sarmalı: `<i>Sad is the heart of the poet</i>`
- Çok satırlı sarmal: `<i>Who could face` / `the icy hand of the wind?</i>`
- **Satır-içi kısmi sarmal:** `We should consult a <i>Maiba.</i>` (#175), `<i>Morning has</i> come` (#398), `People believe that <i>a Maibi's</i>` (#355), `Bring some <i>tairen</i> leaves,` (#253)
- Diyalog + sarmal: `<i>- Where are my bangles, Mother?` / `- Here they are.</i>` (#317, #318)

Kısmi sarmallarda `restore_format_tags` beklendiği gibi davranmıyorsa **DUR ve raporla** — kelime hizalaması gerektiren vakaları tahminle doldurma. Tam-satır sarmallarını uygula, kısmi olanları listele.

## D. #322 — unvan yanlış çözümlenmiş (ÖNCELİK 2)

`Mother guru` bir unvan; sözlükte `'Mother guru' → 'Anne guru'`. Çeviri onu "Anne" hitabı + "Guru" öznesi diye ayırmış.

| Cue | Kaynak | Şu anki | Olacak |
|---|---|---|---|
| #322 | `It is time for Mother guru to leave.` | `Anne, Guru'nun gitme vakti geldi.` | `Anne gurunun gitme vakti geldi.` |

**Doğru örnek dosyada zaten var:** #327 `Mother Guru, it's time to leave.` → `Anne guru, gitme vakti geldi.` ✅ ve #348 `to my mother guru's` → `anne gurunun yanına` ✅

## E. Küçük nesir düzeltmeleri (ÖNCELİK 3)

| Cue | Kaynak | Şu anki | Olacak | Neden |
|---|---|---|---|---|
| #391 | `Lengthen whilst the moon waxes` | `Ay büyürken serpil uzat` | `Ay büyürken uza` | `uzat` geçişli (birini uzatmak); burada özne büyüyor → `uza`. `serpil uzat` iki fiil, biri fazla |
| #152 | `Two junior colleagues`<br>`have already replaced me.` | `Yerime iki genç meslektaşı`<br>`çoktan verdiler.` | `İki genç meslektaşım`<br>`çoktan yerime geçti.` | "replaced me" edilgen değil; mevcut hâli devrik ve failsiz |

---

## DOKUNMA

- **#314/#315** — `She is not to eat fish` / `with spiky, hornlike fins...` → `Dikenli, boynuz gibi yüzgeçleri olan` / `balıkları yememeli...` Türkçe söz dizimi gereği sıfat öbeği öne alınmış; **doğru tercih**, cue'lar arası dengeleme.
- **Şarkı çevirileri** (#100-107, #276-279, #301-305, #364-406, #430-435) — nesir kalitesi iyi, yalnızca C'deki `<i>` sarmalı eksik. Metne dokunma.
- **Özel adlar** — Bembem, Tampha, Dhanabir, Maiba, Maibi, Panthoibi, Lai Haraoba, kheer, kanghou, pungphai, tairen: sözlükte kasıtlı olarak korunuyor, hepsi tutarlı. Dokunma.
- **`sister-in-law` → `yenge`** (#39, #97) — sözlük "görümce / yenge bağlama göre" diyordu, model "yenge"yi seçti ve tutarlı uyguladı. Doğru.
- **#406** `Arise, 0 Mother!` — kaynakta OCR hatası (`0` ← `O`); çeviri `kalk, ey Anne!` doğru. Dokunma.
- **SDH** — bu dosyada SDH etiketi YOK, temizlik gerekmiyor.

## Doğrulama

1. Cue sayısı **435 → 436** (#9 geri eklendi). Kaynakla ID kümesi birebir eşleşmeli.
2. Zaman kodları değişmemeli (#9 hariç — o kaynaktan gelecek).
3. `\((geleneksel tören|uzak bir yer|hilal sonrası dönem|açıklama ofisi)\)` → **0 eşleşme**.
4. Kaynakta `<i>` olan 78 cue'nun çevirisinde de `<i>` olmalı. Kaç cue'da başarılı, kaç cue'da başarısız — **raporla**.
5. `Anne, Guru'nun` → 0 eşleşme.
6. `serpil uzat` → 0 eşleşme.
7. #6, #7, #8 üçü de **tam 2 satır** olmalı; hiçbiri 3 satır olmamalı.
8. #9 mevcut olmalı ve `Çok güzel görünüyor!` içermeli.
9. utf-8, CRLF, cue-içi `\n` korunmuş.
10. `.bak` alınmış olmalı.

## Raporla

- Bölüm bölüm (A/B/C/D/E) kaç cue değişti
- C'de kaç `<i>` başarıyla geri yüklendi / kaç tanesi kısmi sarmal olduğu için atlandı
- 10 doğrulama maddesinin sonucu
- Belirsiz/çelişkili madde — **tahmin yürütme, raporla.**
