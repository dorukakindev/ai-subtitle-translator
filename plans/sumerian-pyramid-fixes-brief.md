# Brief: "Unearthed S08E09 — Sumerian Pyramid of Death" düzeltmeleri (Sonnet 5)

Hazırlayan: **Opus 4.8** (log + kaynak/çıktı timestamp-hizalama + tüm-dosya leak/garble taraması,
2026-07-10). Protokol: Opus karar verir + brief yazar, Sonnet uygular.

- **Hedef:** `C:\Users\K\Downloads\ÇIKTI\Unearthed_S08E09_Sumerian Pyramid of Death.English(US).srt`
- **Kaynak:** `E:\ALTYAZILAR\Altyazilar\HBO-Max\Unearthed\Season 8\Sumerian Pyramid of Death\Unearthed_S08E09_Sumerian Pyramid of Death.English(US).srt`
- **Önce `.bak` al.** Çıktı **634 cue** (kaynak 637; sondaki #635-637 `♪♪` SFX-only, benign
  düşüş). Timestamp'ler 1:1 hizalı → kaba desync yok. Düzeltmeler **yalnız metin**; cue sayısı
  **634 kalmalı, timecode DEĞİŞMEZ**.

## Özet
Timestamp hizalaması sağlam; sorunlar cue-İÇİ içerik. Bir gerçek desync+duplikasyon, iki
İngilizce leak, bir terim tutarsızlığı, bir tekrar-stutter, bir yazım hatası. Log'daki 🚨
uyarısının bir kısmı (özellikle #389-395) Türkçe SOV yeniden-dağıtımından kaynaklı
YANLIŞ-POZİTİF — aşağıda "DOKUNMA" bölümünde açıkça ayrıldı.

---

## A) #603-606 — GERÇEK desync + duplikasyon (YÜKSEK öncelik)
İçerik -1 kaymış: FIN #604 = kaynak #605, FIN #605 = kaynak #606, FIN #606 = #606'nın
TEKRARI (üstelik "koyun" **emir kipi** — yanlış). #602 DOĞRU (kaynak #602 + "ancient artifacts"
birleşmiş, tam) — **DOKUNMA**. #603-606'yı 1:1 yeniden hizala:

| cue | Kaynak (EN) | Mevcut FIN (yanlış) | YENİ FIN |
|---|---|---|---|
| #603 | ancient artifacts -- they're ancient for us, | onlar bizim için eskiydi,\nama onlar için de eskiydi, | onlar bizim için eski, |
| #604 | but they were ancient for them, as well, | bu yüzden bunları bu tapınağın\nkalıntılarından yukarı çıkardılar | ama onlar için de eskiydi, |
| #605 | so they brought them up out of the ruins of this temple | ve bir koleksiyona\nkoydular. | bu yüzden bunları bu tapınağın\nkalıntılarından çıkardılar |
| #606 | and put them in a collection. | ve onları\nbir koleksiyona koyun. | ve bir koleksiyona koydular. |

Edit için tam eşleşmeler (`\n` = satır sonu):
- #603: `onlar bizim için eskiydi,\nama onlar için de eskiydi,` → `onlar bizim için eski,`
- #604: `bu yüzden bunları bu tapınağın\nkalıntılarından yukarı çıkardılar` → `ama onlar için de eskiydi,`
- #605: `ve bir koleksiyona\nkoydular.` → `bu yüzden bunları bu tapınağın\nkalıntılarından çıkardılar`
- #606: `ve onları\nbir koleksiyona koyun.` → `ve bir koleksiyona koydular.`

## B) #439-440 — "Garden of Eden" İngilizce leak + temizlik (ORTA)
Kaynak #439 "a green oasis inspiring stories" / #440 "about a prosperous Garden of Eden."
Mevcutta "Garden of Eden" ÇEVRİLMEMİŞ (dosyanın her yerinde "Cennet Bahçesi") ve #439 "refah
dolu bir" sarkıyor. 1:1 düzelt:
- #439: `refah dolu bir` → `hikâyelere ilham veren yeşil bir vaha;`
- #440: `Garden of Eden hakkında hikâyelere ilham veren yeşil bir vaha.` → `refah dolu bir Cennet Bahçesi hakkında.`

(#438 "...verimli bitki örtüsünü besler," DOĞRU — dokunma. Sonuç akış: "...besler, / hikâyelere
ilham veren yeşil bir vaha; / refah dolu bir Cennet Bahçesi hakkında.")

## C) #480 — "King" İngilizce leak (ORTA)
Kaynak "...distribute King Shulgi's". Dosyada başka her yerde "Kral" ("Kral Shulgi" #455/#595/
#596). "Shulgi" ismi tutarlı biçimde "Shulgi" bırakılmış — DOĞRU, dokunma; yalnız "King"→"Kral":
- #480: `King Shulgi'nin` → `Kral Shulgi'nin`

## D) #562 — terim tutarsızlığı "Eden Bahçesi" → "Cennet Bahçesi" (DÜŞÜK)
Dosya baskın olarak "Cennet Bahçesi" (#7,#345,#360,#382,#632); yalnız #562 "Eden Bahçesi".
Tutarlılık için:
- #562: `ve ayrıca Eden Bahçesi’nin\nbulunabileceği yer olarak` → `ve ayrıca Cennet Bahçesi’nin\nbulunabileceği yer olarak`
  (NOT: kıvrık apostrof `’` U+2019 — aynen koru.)

## E) #392-393 — "benzediğine dair" tekrarı (DÜŞÜK)
Kaynak #392 "It's an incredible vision of what" / #393 "the landscape around Ur was like."
Mevcutta "benzediğine dair" iki cue'da tekrarlanıyor (stutter). 1:1 düzelt:
- #392: `Bu, neye benzediğine dair` → `Bu, Ur çevresindeki manzaranın`
- #393: `benzediğine dair inanılmaz bir bakış sunuyor.` → `nasıl olduğuna dair inanılmaz bir bakış sunuyor.`

## F) #481 — yazım hatası (DÜŞÜK)
- #481: `parçalayip` → `parçalayıp`  (Latin 'i' → Türkçe 'ı'; tek karakter. Replace_all=false,
  cue #481 içindeki tek geçiş.)

---

## DOKUNMA (doğrulanmış yanlış-pozitif / benign)
- **#389-391, #394-396**: log'da 🚨 flag'lendi ama Türkçe **SOV yeniden-dağıtımı** — anlam TAM,
  kayıp/tekrar YOK. (#389-391 "Şehrin / kaybolmuş su yolları... / ...ışık tutabilir diye
  düşünüyor" tek cümle; #394-396 "Bu çizgiler / ...kanallardan oluşan bir ağı / işaret ediyor"
  tek cümle.) DOKUNMA.
- **#560-561, #563**: 🚨 değil ama #563 "yaşamayı sürdürüyor" izole bakınca alakasız görünür —
  BAĞLAMDA DOĞRU: "lives on" fiili Türkçe SOV'da cümlenin sonuna gelmiş. #560-563 tek cümle,
  tam ve doğru. DOKUNMA. (Yalnız #562 terim tutarsızlığı D'de düzeliyor.)
- **#391 (5.58x anormal uzunluk)**: SOV outlier — kaynak "city states." kısa, çeviri fiil öbeği
  bu cue'ya düşmüş. Benign. DOKUNMA.
- **'Sumerians' mixed-term (Mezopotamya×3)**: FP. #6/#34/#447 kaynakta HEM "Sumerians" HEM
  "Mesopotamia" var; çeviri ikisini de doğru veriyor ("Mezopotamya'nın Sümerleri"). "Sumerians"
  tutarlı biçimde "Sümerler". DOKUNMA.
- **CPS uyarıları (42 satır >24 kar/sn)**: zamanlama/okuma-hızı, çeviri hatası DEĞİL; condense
  kapalı. Kapsam DIŞI.
- **#635-637 `♪♪`**: SFX-only, kasıtlı düşüş. FP.

## Doğrulama (uyguladıktan sonra)
1. Cue sayısı **634**, timecode değişmez (`.bak` ile karşılaştır).
2. Değişen cue kümesi TAM olarak: **392, 393, 439, 440, 480, 481, 562, 603, 604, 605, 606**
   (11 cue). Fazla/eksik OLMAMALI.
3. Tüm dosyada İngilizce leak taraması: "Garden", "Eden" (İngilizce, ayrı), "King" KALMAMALI.
   ("Shulgi", "Ur-Nammu", "Ziggurat" gibi özel isimler meşru — kalır.)
4. `ht.find_garble_tokens` tüm dosyada 0; "parçalayip" kalmamalı.
5. `detect_alignment_issues` yeni çıktı vs kaynak: #603-606 için `adjacent_duplicate` bulgusu
   KALMAMALI. (#389-395 outlier'ı SOV'dan ötürü kalabilir — o benign; asıl #605-606 gitmeli.)
6. "Cennet Bahçesi" tutarlı (Eden Bahçesi kalmamalı); ">>koyun" emir-kipi tekrarı gitmiş.

## Kod-gözlemi (uygulama YOK — ayrı tur adayı)
Dedektör #605-606 duplikasyonunu YAKALADI (Fix A/C çalışıyor) ✓. Ama #440/#480 İngilizce
leak'lerini ve #562 terim sapmasını post-write **mixed-term + leak scan** yakaladı, alignment
dedektörü değil — yani iki katman da gerekli. #392-393 "benzediğine dair" stutter'ı hiçbir
otomatik katman yakalamadı (yalnız bilingual okuma). Bu, "otomatik tarama gerekli ama yeterli
değil" dersini bir kez daha doğruluyor.
