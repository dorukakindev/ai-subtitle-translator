# The Blood of Hussain — düzeltme brief'i

**Analiz:** Opus 4.8, 2026-07-16 · **Uygulayacak:** Sonnet 5
**Hedef dosya:** `C:\Users\K\Downloads\ÇIKTI\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO.srt` (440 cue)
**Kaynak:** `C:\Users\K\Downloads\Yeni klasör (4)\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO.srt` (469 cue)

Çeviri gpt-5.4 (ana) + gpt-5.4-mini (analiz/yardımcı) ile yapıldı. **Yeniden çeviri YOK** — nesir kalitesi iyi, sadece aşağıdaki noktasal düzeltmeler uygulanacak.

## Kök neden (bağlam için — bu brief'te kod değişikliği yok)

Analiz geçişi (gpt-5.4-mini, "13 terim") sözlüğü **Somalice** terimlerle üretmiş. Ana model sözlüğe sadık kaldığı için aynı yanlış dize üç ayrı chunk'ta byte-byte aynı çıktı. Ana modelin hatası değil. Kalıcı kod guard'ı ayrı bir iş olarak ele alınacak.

---

## A. Sözlük zehirlenmesi — Somalice/çevrilmemiş terim sızıntısı (10 cue)

Hepsi ham yedekte de mevcut, yani çeviri anında oluşmuş. Satır sonu (`\n`) yapısını **koru**.

| Cue | Şu anki (YANLIŞ) | Olması gereken |
|---|---|---|
| #36 | `Qawweyaha Xoogga Dalka / ciidamada qalabka sida için` | `Silahlı Kuvvetler'in` |
| #37 | `seyirci kalmak affedilmez bir günahtır.` | `sessiz seyirci kalması affedilmez bir günahtır.` |
| #60 | `Havalimanı,\nQawweyaha Xoogga Dalka / ciidamada qalabka sida kontrolü altında.` | `Havalimanı,\nSilahlı Kuvvetler'in kontrolü altında.` |
| #65 | `Bangiga Adduunka'dan bir kredi\ngörüşmesi yapmanızı istiyorum.` | `Dünya Bankası'ndan bir kredi\ngörüşmesi yapmanızı istiyorum.` |
| #83 | `Sen madaxweynaha'sın.` | `Sen Başkan'sın.` |
| #377 | `Ancak Qawweyaha Xoogga Dalka / ciidamada qalabka sida yönetebilir.` | `Ancak Silahlı Kuvvetler yönetebilir.` |
| #58 | `Pakistan'da martial law ilan edildi.` | `Pakistan'da sıkıyönetim ilan edildi.` |
| #195 | `(mu'addinka çağrısı)` | `(Müezzin sesi)` |
| #242 | `(Uzakta mu'addinka sesi)` | `(Uzaktan müezzin sesi)` |
| #14 | `gaspçı khalifaya karşı geldi` | `gaspçı halifeye karşı geldi` |

**#36/#37 notu:** Kaynak `'it is an inexcusable sin` / `'for the Armed Forces to sit as silent spectators.` şeklinde iki cue'ya bölünmüş. Türkçe söz dizimi gereği özne #36'ya alınmış — bu doğru bir tercih, koru. Sadece Somalice dizeyi değiştir ve #37'de düşen "silent" karşılığını geri koy.

**#83 notu:** #86'da aynı unvan zaten `Sayın Başkan` olarak çevrilmiş. Tutarlılık için `Başkan` seçildi.

## B. Sayı hatası (1 cue)

| Cue | Kaynak | Şu anki | Olması gereken |
|---|---|---|---|
| #384 | `fourteen hundred years ago` | `on dört yüz yıl önce` | `bin dört yüz yıl önce` |

`on dört yüz` Türkçede anlamsız bir birebir kopya. `source_numbers` validator'ı bunu kaçırdı çünkü kaynakta sayı rakamla değil yazıyla ("fourteen hundred").

## C. Cue içerik kayması (2 cue)

#31'in içeriği #30'a sızmış, #31'e #32'nin parafrazı dolmuş:

| Cue | Kaynak | Şu anki | Olması gereken |
|---|---|---|---|
| #30 | `(Horn honks)` | `[KORNA]\nHey!` | `[KORNA]` |
| #31 | `Hey!` | `Çekil!` | `Hey!` |

#32 (`Yoldan çekilin!`) **doğru, dokunma.**

## D. Ses etiketi anlam hataları (3 cue)

| Cue | Kaynak | Şu anki | Olması gereken | Neden |
|---|---|---|---|---|
| #121 | `(Snorts)` | `[HORLAMA]` | `[HOMURDANMA]` | Sahne at sahnesi; "horlama" uyku sesi, tamamen yanlış |
| #333 | `(Horse snorts)` | `[ATIN KİŞNEMESİ]` | `[ATIN HOMURDANMASI]` | kişneme = neigh; snort ≠ neigh. #97/#112'de `(Horse neighs)` zaten "kişner" |
| #119 | `(Laughs)` | `(Kıkırdar)` | `(Güler)` | #88 `(Chuckles)` zaten "kıkırdar"; ikisi ayrışmalı |

## E. Konuşma dili etiketleri — stil birleştirme (34 cue)

Şu an **7 farklı stil + tamamen düşürülmüş** hâller bir arada. Bu filmde dil geçişi anlamlı (Batılılaşmış elit İngilizce, köylüler Punjabi konuşuyor — sınıf göstergesi), o yüzden **etiketler korunacak**, sadece tek stile çekilecek.

**Benimsenecek tek stil:** `(Urduca konuşur)` — parantez + cümle düzeni (ilk harf büyük, gerisi küçük). Gerekçe: dosyadaki en yaygın hâli bu (#4, #90, #252, #257 …) ve `[...]` + BÜYÜK HARF kalıbı bu dosyada ses efektlerine ayrılmış durumda; ikisinin ayrışması okunurluk için iyi.

### E1. Parantezi hiç olmayanlar — düz replik gibi okunuyor (EN KRİTİK, 7 cue)

| Cue | Şu anki | Olması gereken |
|---|---|---|
| #91 | `İngilizce konuşuyor` | `(İngilizce konuşur)` |
| #96 | `- Punjabi konuşuyor Ne oldu?` | `- (Punjabi konuşur) Ne oldu?` |
| #104 | `- İngilizce konuşuyor İçeri gel.` | `- (İngilizce konuşur) İçeri gel.` |
| #105 | `Punjabi konuşuyor` | `(Punjabi konuşur)` |
| #113 | `İngilizce konuşuyor` | `(İngilizce konuşur)` |
| #305 | `İngilizce konuşuyor.` | `(İngilizce konuşur)` |
| #309 | `Punjabi konuşuyor.` | `(Punjabi konuşur)` |

### E2. Köşeli/büyük harf → parantez (8 cue)

| Cue | Şu anki | Olması gereken |
|---|---|---|
| #169 | `[URDUCA KONUŞUR]` | `(Urduca konuşur)` |
| #174 | `[İNGİLİZCE KONUŞUR]` | `(İngilizce konuşur)` |
| #176 | `[URDUCA KONUŞUR]` | `(Urduca konuşur)` |
| #334 | `[URDUCA KONUŞUR]` | `(Urduca konuşur)` |
| #399 | `[Punjabi konuşur]` | `(Punjabi konuşur)` |
| #424 | `[Punjabi konuşur]` | `(Punjabi konuşur)` |
| #428 | `[Punjabi konuşur]` | `(Punjabi konuşur)` |
| #34 | `[GENERAL RADYODA, İNGİLİZCE]` | `(General radyoda, İngilizce)` |

### E3. Fiil çekimi / biçim düzeltmesi (2 cue)

| Cue | Şu anki | Olması gereken |
|---|---|---|
| #98 | `(Punjabi konuşuyor)` | `(Punjabi konuşur)` |
| #179 | `(Selim Urduca)` | `(Selim, Urduca)` |

### E4. Düşürülmüş etiketler — geri ekle (7 cue)

Satır uzunluğuna dikkat; etiket eklenince CPS artacak, gerekirse etiket kendi satırında dursun.

| Cue | Kaynak | Şu anki | Olması gereken |
|---|---|---|---|
| #32 | `(Speaks Urdu) Get out of the way!` | `Yoldan çekilin!` | `(Urduca konuşur) Yoldan çekilin!` |
| #134 | `(Man declaims in Punjabi)` | (etiket yok) | `(Adam Punjabi diliyle anlatır)` satırını başa ekle |
| #268 | `(Speaks English) Brother,` | `Ağabey,` | `(İngilizce konuşur) Ağabey,` |
| #286 | `(Speaks Punjabi) Hussain Sahab…` | `Hussain Sahab, her şey…` | `(Punjabi konuşur) Hussain Sahab, her şey…` |
| #360 | `(Speaks English) Get off this land.` | `Bu topraklardan git.` | `(İngilizce konuşur) Bu topraklardan git.` |
| #363 | `(Speaks English) Be sensible.` | `Mantıklı ol.` | `(İngilizce konuşur) Mantıklı ol.` |
| #404 | `- (Speaks English) Hello?` | `- Alo?` | `- (İngilizce konuşur) Alo?` |

## F. Özel adlar — tarihi/dini figürler Türkçeleşiyor (kullanıcı kararı)

**Kural:** Tarihi İmam Hüseyin anlatısındaki adlar Türkçe yerleşik forma geçer. **Filmin yaşayan karakteri `Hussain` olarak KALIR.** Filmin göndermesi tam da bu adaşlık ikiliğine dayanıyor; ayrışması metni güçlendirir.

> **UYARI: Mekanik bul-değiştir YAPMA.** "Hussain" hem tarihi imam hem yaşayan karakter için geçiyor. Aşağıdaki cue listesine birebir uy.

### F1. Karbala → Kerbela (4 cue)
#15, #134, #152, #163

### F2. Yazid → Yezid (7 cue)
#6, #139, #144, **#154**, #159, #161, #165

### F3. Imam Hussain → İmam Hüseyin (3 cue)
#14, **#134**, #166

### F4. Tarihi anlatı bloğunda "Hussain" → "Hüseyin" (6 cue)
**Yalnızca #134–#167 arası kesintisiz tarihi anlatı bloğu içinde:** #140, #151, #152, #156, #160, #163

Bu blok #134'te (`'At Karbala, Imam Hussain declared:`) başlar, #167'de (`'By his death Islam is reborn...'`) biter. #168 (`Selim.`) ile şimdiki zamana dönülür.

### F5. DEĞİŞMEYECEK "Hussain" geçişleri (yaşayan karakter)
#5, #100, #107, #123, #176, #184, #186, #241, #286, #294, #317, #399, #411, #413, #445, **#468**

**#468 özellikle önemli:** `Hussain lives forever!` → `Hussain sonsuza dek yaşar!` — filmin kapanış çığlığı kasıtlı olarak iki Hüseyin'i birden çağırıyor. `Hussain` kalmalı ki belirsizlik korunsun.

---

## DOKUNMA — doğrulanmış yanlış alarmlar

- **`adjacent_duplicate` bayrağı (#357, #361, #435-443):** YANLIŞ ALARM. Kaynakta gerçekten "Yes, sir." iki kez (#435/#438) ve "(Mutters)" iki kez (#441/#443) geçiyor. Hizalama doğru.
- **#352/#353:** `I am nearing that ocean... / ...that awaits us all.` → Türkçe fiil sona gittiği için cue'lar arası yeniden dengelenmiş. Doğru tercih.
- **Silinen 29 cue** (#21, #22, #23, #173, #228, #251 …): SDH temizliği yalnızca ses etiketinden ibaret cue'ları düşürdü. Beklenen davranış.
- **`Urdu` "karışık çevrilmiş" bayrağı:** terim tutarsızlığı DEĞİL, E bölümündeki stil kaosu. E uygulanınca kendiliğinden kapanır.

## Doğrulama

1. Cue sayısı 440 kalmalı; hiçbir cue **ID'si veya zaman kodu** değişmemeli.
2. Çıktıda hiçbir Somalice token kalmamalı:
   `qalabka|Qawweyaha|madaxweynaha|Bangiga|Adduunka|ciidamada|mu'addinka|Xoogga`
3. `martial law` ve `khalifa` kalmamalı.
4. Konuşma dili etiketi taraması: parantezsiz `İngilizce konuşuyor|Punjabi konuşuyor` kalmamalı; `[URDUCA|[İNGİLİZCE|[Punjabi` kalmamalı.
5. `Karbala|Yazid` kalmamalı. `Hüseyin` yalnızca F3/F4'teki 8 cue'da geçmeli — F5 listesindeki cue'larda `Hussain` aynen durmalı.
6. Dosya `utf-8` kaydedilmeli, `\r\n` satır sonu korunmalı, cue-içi `\n` yapısı bozulmamalı.
7. Değişiklik öncesi `.bak` al.
