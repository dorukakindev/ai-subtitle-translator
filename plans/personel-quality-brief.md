# Personel (1975) — düzeltme brief'i

**Analiz:** Opus 4.8, 2026-07-17 · **Uygulayacak:** Sonnet 5

**Hedef:** `C:\Users\K\Downloads\Personel (1975)\Çıktı\Personel (1975) [WEB-DL 1080p]\Personel (1975) [WEB-DL 1080p].srt` (819 cue)
**Kaynak (VTT, RUSÇA):** `C:\Users\K\Downloads\Personel (1975)\Personel (1975) [WEB-DL 1080p].vtt`

Kieślowski'nin Personel'i. **Kaynak dil Rusça** (İngilizce değil — Полонya filmi ama eldeki altyazı Rusça çeviri). Bu bir Rusça→Türkçe çevirisi.

**Çeviri kalitesi baştan sona çok yüksek** — akıcı, doğal, register tutturulmuş. Sorunların neredeyse tamamı tek bir kök nedenden: analiz sözlüğü bozuktu (`'Pan': 'пан'` gibi kaynak-dile-çeviri değerleri), model `pan` unvanında karar verememiş ve tutarsız davranmış.

**Kurallar:** Cue ID/zaman kodu değişmez, 819 cue sabit. `\n` = satır bölünmesi. `.bak` al.

---

## A. Polish pass anlamı bozmuş — #141 (ÖNCELİK 1)

Polish pass `ona`yı `one` yapmış (Rusça `ему` = ona). "one frak" Türkçede anlamsız.

| Cue | Kaynak | Şu anki | Olacak |
|---|---|---|---|
| #141 | `мы там фрак ему шили.` (ona frak diktik) | `Müzik tiyatrosunda çalışırken,`<br>`one frak dikmiştik.` | `Müzik tiyatrosunda çalışırken,`<br>`ona frak dikmiştik.` |

---

## B. `pan` unvanı — tutarlılık (ÖNCELİK 1, kök: bozuk sözlük)

Dosya `pan` unvanını **üç ayrı biçimde** işliyor:
- **Doğru:** `X Bey` — #40 Romek Bey, #42 Roman Bey, #102 Marchak Bey, #108 Schmidt Bey, #247 Müdür Bey, #408 Sowa Bey, #796/#797 Januchta Bey
- **Yabancı kalmış:** `Pan X` (özel ad), `Terzi pan` (postpozisyon)
- **Gloss:** `pan (bey)`, `pan (beyefendi)`, `pan (açıklama: bey)`

**Kural: hepsini dosyanın baskın biçimi olan `X Bey`'e çek.** `pan`/`Pan` sözcüğü hiçbir yerde kalmayacak (özel ad `Pan` dahil). Türk izleyici için "pan" anlaşılmaz ve sözlük bozukluğundan geliyor.

### B1 — gloss temizliği + çözüm

| Cue | Şu anki | Olacak |
|---|---|---|
| #15 | `pan (bey) Januchta,`<br>`personel bölümüne gelmeniz rica olunur.` | `Januchta Bey,`<br>`personel bölümüne gelmeniz rica olunur.` |
| #16 | *(aynı)* | `Januchta Bey,`<br>`personel bölümüne gelmeniz rica olunur.` |
| #17 | *(aynı)* | `Januchta Bey,`<br>`personel bölümüne gelmeniz rica olunur.` |
| #394 | `Doldurun, pan (bey) Wilya.` | `Doldurun, Wila Bey.` |
| #398 | `Bizim pan (bey) baş terzimiz,` | `Bizim terzimiz,` |
| #492 | `- O zaman pan (beyefendi) Sowa'yı çağıralım.`<br>`- pan (beyefendi) Sowa nerede?` | `- O zaman Sowa Bey'i çağıralım.`<br>`- Sowa Bey nerede?` |
| #497 | `Haydi pan (beyefendi) Sowa, buraya gelsin!` | `Haydi Sowa Bey buraya gelsin!` |
| #723 | `Orada bir oyun var. Pan(açıklama: bey) Wila bir oyun yazıyor.` | `Orada bir oyun var. Wila Bey bir oyun yazıyor.` |

### B2 — çıplak `pan` (unvan/postpozisyon)

| Cue | Kaynak | Şu anki | Olacak |
|---|---|---|---|
| #160 | `Пан закройщик...` | `Terzi pan...` | `Terzi Bey...` |
| #248 | `...пан закройщик.` | `...pan baş terzi.` | `...terzi bey.` |
| #455 | `Пан профессор, ...` | `Profesör pan, ...` | `Sayın Profesör, ...` |
| #472 | `Пан профессор, ...` | `Profesör pan, ...` | `Sayın Profesör, ...` |
| #479 | `Пан Анджей!` | `Andrzej pan!` | `Andrzej Bey!` |

### B3 — `Pan X` (özel ad, büyük P)

Hepsi `X Bey`'e çekilecek. Ek uyumuna dikkat (`'yle` → `Bey'le`).

| Cue | Şu anki | Olacak |
|---|---|---|
| #351 | `Pan Radek, buradan başlayalım.` | `Radek Bey, buradan başlayalım.` |
| #362 | `Pan Radek. Ve...!` | `Radek Bey. Ve...!` |
| #489 | `...Pan Sowa...` | `...Sowa Bey...` *(bağlamı koru, yalnız Pan Sowa→Sowa Bey)* |
| #495 | `Pan Sowa nerede?` | `Sowa Bey nerede?` |
| #496 | `Pan Sowa!` | `Sowa Bey!` |
| #505 | `Pan Sowa, bu kostüme ne oldu?` | `Sowa Bey, bu kostüme ne oldu?` |
| #512 | `Pan Sowa, sizin o provalarınız umurumda değil!` | `Sowa Bey, sizin o provalarınız umurumda değil!` |
| #592 | `...hepimizin tanıdığı Pan Andrzej Sedlecki'yle` | `...hepimizin tanıdığı Andrzej Sedlecki Bey'le` |
| #602 | `Pan Sedlecki'yle muhatap olmuş,` | `Sedlecki Bey'le muhatap olmuş,` |
| #627 | `Bence Pan Sedlecki,` | `Bence Sedlecki Bey,` |
| #654 | `Pan Sedlecki konusunda,` | `Sedlecki Bey konusunda,` |
| #758 | `Pan Januchta, iyi ki geldiniz.` | `Januchta Bey, iyi ki geldiniz.` |
| #763 | `Hakkınızda yalnızca iyi şeyler duyuyoruz, Pan Januchta.` | `Hakkınızda yalnızca iyi şeyler duyuyoruz, Januchta Bey.` |
| #785 | `...bizim solistimiz Pan Andrzej'le ilgili` | `...bizim solistimiz Andrzej Bey'le ilgili` |
| #790 | `Siz Pan Sowa'yla iş arkadaşısınız, değil mi?` | `Siz Sowa Bey'le iş arkadaşısınız, değil mi?` |
| #800 | `O provalar sırasında Pan Sowa uygunsuz konuştu,` | `O provalar sırasında Sowa Bey uygunsuz konuştu,` |

---

## C. `закройщик` (terzi) — terim tutarlılığı (ÖNCELİK 2)

Aynı meslek (закройщик) **dört farklı** karşılıkla: `terzi` (#38), `kesimci` (#85), `baş terzi` (#248/#398), `kalıpçı` (#765/#766). **Hepsi `terzi`'ye çekilecek.**

| Cue | Kaynak | Şu anki | Olacak |
|---|---|---|---|
| #85 | `...А это закройщик.` | `...Bu da kesimci.` | `...Bu da terzi.` |
| #765 | `И пан закройщик тоже лестно отзывался.` | `Ve kalıpçı bey de hakkınızda övgüyle konuştu.` | `Ve terzi bey de hakkınızda övgüyle konuştu.` |
| #766 | `Верно, пан закройщик?` | `Doğru değil mi, kalıpçı bey?` | `Doğru değil mi, terzi bey?` |

*(#160, #248, #398 B bölümünde zaten ele alındı — "terzi" biçimi orada da uygulanıyor.)*

---

## D. Ad tutarlılığı — Wila (ÖNCELİK 2)

Kaynakta `Виля` tek kişi ama çeviri iki türlü yazmış: `Wilya` (#394) / `Wila` (#723). **`Wila`'ya birleştir** (Lehçe adın doğru transkripsiyonu).

- #394: B1'de zaten `Wila Bey` yapıldı ✓
- #723: zaten `Wila` ✓

Kalan `Wilya` geçişi olmamalı — tara.

---

## DOKUNMA

- **Çeviri nesri** — baştan sona iyi, yalnız yukarıdaki noktalar. Deyimler, register, akış korunacak.
- **#186/#188/#189** — kaynakta `который считается` iki kez geçiyor (#186, #188), çeviri de tekrarı yansıtıyor; kabul edilebilir, dokunma.
- **Künye adları** (#8, #10, #12, #14, #811-819) — Lehçe özel adların Türkçe transkripsiyonu doğru yapılmış, dokunma.
- **Kiril** — çıktıda ve ham'da SIFIR Kiril kaldı (retry mekanizması temizledi). Kontrol gerektirmiyor.
- **`kesimci` dışındaki meslek adları** — dekor ressamı, sahne tasarımcısı vb. tutarlı, dokunma.

## Doğrulama

1. Cue sayısı **819**, ID ve zaman kodları değişmemiş.
2. `\bpan\b` ve `\bPan\b` → **0 eşleşme** (unvan olarak; hiçbir yerde kalmamalı).
3. `\((bey|beyefendi|açıklama: bey)\)` → **0 eşleşme**.
4. `one frak` → 0. `ona frak` → 1 (#141).
5. `kalıpçı` → 0. `Wilya` → 0.
6. `\bBey\b`/`Bey'` ≥ 40 cue (artmış olmalı).
7. Kaynakta parantez olmayan cue'ların çevirisinde parantez kalmamalı — tara.
8. Çift boşluk (` {2,}`) → 0.
9. Çıktıda Kiril (`[Ѐ-ӿ]`) → 0 (zaten yoktu, bozulmadığını teyit et).
10. utf-8, CRLF, cue-içi `\n` korunmuş, `.bak` alınmış.

## Raporla

- Bölüm bölüm (A/B/C/D) kaç cue değişti
- 10 doğrulama maddesinin sonucu
- Belirsiz/çelişkili madde — **tahmin yürütme, raporla.**
