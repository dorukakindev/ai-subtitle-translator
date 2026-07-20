# The Shivering Truth S01E01 — düzeltme brief'i

**Analiz:** Opus 4.8, 2026-07-19 · **Uygulayacak:** Sonnet 5

**Hedef:** `C:\Users\K\Downloads\the.shivering.truth.(2018).tv.s01.eng.16cd\ÇIKTI\The Shivering Truth - S01E01 WEB.eng\The Shivering Truth - S01E01 WEB.eng.srt` (207 cue)
**Kaynak:** `C:\Users\K\Downloads\the.shivering.truth.(2018).tv.s01.eng.16cd\episode 1\The Shivering Truth - S01E01 WEB.eng.srt`

Absürt/gonzo animasyon dizisi. Çeviri kalitesi genel olarak çok iyi — sadece bir yerde model kaynakta olmayan bir cümle icat etmiş.

**Kurallar:** Cue ID/zaman kodu değişmez, 207 cue sabit. `\n` = satır bölünmesi. `.bak` al.

---

## A. Uydurma içerik — #121-122 (tek düzeltme)

Kaynakta tek cümle iki cue'ya bölünmüş: `Everyone else in this department types` (cue121) + `at least 10,000 random numbers a day.` (cue122). Model bu cümleyi TAMAMEN cue121'e sıkıştırmış, sonra cue122'yi doldurmak için kaynakta OLMAYAN bir cümle icat etmiş (`bir sen yazamıyorsun` — "only you can't"). Bu bilgi #123'te (`Your average is 19.`) zaten açığa çıkacak, erken ve icat edilmiş biçimde vermek gereksiz.

**Çözüm:** Zaten doğru olan çeviriyi kaynağın 2-cue yapısına göre yeniden böl.

| Cue | Kaynak | Şu anki | Olacak |
|---|---|---|---|
| #121 | `Everyone else\nin this department types` | `Bu bölümdeki herkes\ngünde en az 10,000 rastgele sayı yazıyor` | `Bu bölümdeki herkes` |
| #122 | `at least 10,000\nrandom numbers a day.` | `bir sen yazamıyorsun.` | `günde en az 10,000 rastgele sayı yazıyor.` |

---

## DOKUNMA

- **#14, #19-20** (`adjacent_duplicate` bayrağı) — YANLIŞ ALARM, doğrulandı. Kaynakta gerçekten tekrarlayan replik (`What did you do to me?!` ×2), dizinin kekeleme/absürt üslubu. Doğru çevrilmiş.
- **#17** `W` → `N` — kasıtlı: kaynaktaki kesik kelime kesik çevrilmiş, doğru teknik.
- **`peekaboo` → `ce-e`** — tüm dosyada tutarlı (cee-e oyunu için Türkçe karşılık), dokunma.
- **#12** `Hem,\nbenimki` — zaten Polish pass'te düzeltilmiş, doğru.
- Geri kalan nesir — akıcı, doğal, register korunmuş.

## Doğrulama

1. Cue sayısı 207, ID/zaman kodu değişmemiş.
2. `bir sen yazamıyorsun` → 0 eşleşme.
3. #121 tek satır, #122 tek satır (satır sayıları değişmemeli, yalnız içerik).
4. utf-8, CRLF, cue-içi `\n` korunmuş, `.bak` alınmış.

## Raporla

- #121-122 değişti mi, tam metinle eşleşti mi
- Doğrulama sonuçları
- Belirsiz madde varsa raporla, tahmin yürütme.
