# Brief: "Solve Et Coagula — The Great Work of Alchemy" düzeltmeleri (Sonnet 5)

Hazırlayan: **Opus 4.8** (log + kaynak/çıktı karşılaştırması + tüm-dosya leak/garble taraması,
2026-07-10). Protokol: Opus karar verir + brief yazar, Sonnet uygular.

- **Hedef:** `C:\Users\K\Desktop\Altyazılar\Solve Et Coagula - The Great Work of Alchemy\ÇIKTI\Solve Et Coagula - The Great Work of Alchemy (HD).en.srt`
- **Kaynak:** `C:\Users\K\Desktop\Altyazılar\Solve Et Coagula - The Great Work of Alchemy\Solve Et Coagula - The Great Work of Alchemy (HD).en.srt`
- **Önce `.bak` al.** Çıktı **683 cue** (kaynak 683, eksik yok, desync yok). Düzeltmeler **yalnız
  metin**; cue sayısı **683 kalmalı, timecode DEĞİŞMEZ**.

## Özet
İki kaynak: (1) Polish Pass'in SOKTUĞU garble'lar (#442 "g geçtiğinde", #192 "dalı", #163
"Ulü işi"), (2) çevrilmeden kalan İngilizce element/terim adları (fire/water/air/earth,
Mercury, ether, quintessence). Ayrıca #201 dangling "Bunun" ve #120-121 bozuk-kaynak kalıntısı
("coutop"). Toplam **16 cue** (A+B+C). "sol" (#301/#327 = Türkçe "sol"), "Luna", "albedo/rubedo"
DOKUNMA (aşağıda).

---

## A) İçerik / garble (YÜKSEK)

**#201-202 — dangling "Bunun" + yanlış "kaynaktan mı"** (0.12x uyarısı). Kaynak #201 "Try to
notice if it is originating from the" / #202 "self or the ego. Is it a need or is it a want?"
Mevcut #201 yalnız "Bunun"; #202 "originating from"u yanlışlıkla "kaynaktan mı" (extra 3. seçenek)
diye çevirmiş. 1:1 yeniden dağıt:
- #201: `Bunun` → `Bunun, benlikten mi`
- #202: `kaynaktan mı, benlikten mi yoksa ego’dan mı geldiğini fark etmeye çalışın. Bir ihtiyaç mı, yoksa bir istek mi?` → `yoksa egodan mı kaynaklandığını fark etmeye çalışın. Bir ihtiyaç mı, yoksa bir istek mi?`

**#442 — Polish'in soktuğu başıboş "g"**:
- #442: `Gerekli etkinlikle işinizi yapıp yeterli enerji merkezlerden\ng geçtiğinde,` → `Gerekli etkinlikle işinizi yapıp yeterli enerji merkezlerden\ngeçtiğinde,`

**#192 — Polish'in soktuğu "dalı" garble**. Kaynak #191-192 "...the length of time you are able
to keep your attention on a thought or feeling." (#191 "...bir düşünce ya da duyguya" DOĞRU):
- #192: `dikkatinizi ne kadar süre\ndalı tutabildiğinizdir.` → `dikkatinizi ne kadar süre\nverebildiğinizdir.`

**#120-121 — bozuk kaynak kalıntısı "coutop"**. Kaynağın kendisi bozuk ("the coutop of Ones or
the peacock's tale" = aslında *Cauda Pavonis* / tavus kuşu kuyruğu). #120 "Ones'in kuyruğu ya da"
gereksiz tekrar, #121 "coutop'un" çevrilmemiş. Temizle:
- #120: `Bir sonraki aşamanın, Ones’in\nkuyruğu ya da tavus kuşunun kuyruğu olarak bilinen` → `Bir sonraki aşamanın, tavus kuşunun\nkuyruğu olarak bilinen`
- #121: `coutop’un, gerçekten\nalbedo’dan mı yoksa nigrado’dan sonra mı yer aldığı konusunda\nbir tartışma vardır.` → `gerçekten albedo’dan mı yoksa\nnigrado’dan sonra mı yer aldığı konusunda\nbir tartışma vardır.`
  (NOT: "nigrado" bilinçli KORUNDU — dosyanın geri kalanıyla tutarlı; opsiyonel D bölümüne bak.)

## B) Element-adı leak'leri — fire/water/air/earth (YÜKSEK)
Dörtlü klasik element pasajı İngilizce kalmış. Dosyada baskın Türkçe: ateş×12, hava×11, su, toprak.
Normalleştir (apostroflara dikkat — #4/#74 DÜZ `'`):
- #4: `Earth'i fire'dan ayır, ki bir araya gelsinler.` → `Toprağı ateşten ayır, ki bir araya gelsinler.`
- #74: `Dört yaygın bilinen yön fire,\nwater, air ve Earth gibi elementlerdir; bunlar` → `Dört yaygın bilinen yön ateş,\nsu, hava ve toprak gibi elementlerdir; bunlar`
- #77: `Fire, irademizdir; yaşam gücü ya da\nDoğu geleneklerinde görüldüğü gibi chi’dir.` → `Ateş, irademizdir; yaşam gücü ya da\nDoğu geleneklerinde görüldüğü gibi chi’dir.`  (chi KALIR — meşru)
- #78: `Water ise duygularımızdır ve\nonların ne kadar kolay` → `Su ise duygularımızdır ve\nonların ne kadar kolay`
- #80: `Air, aklımızdır,\nEarth ise` → `Hava, aklımızdır,\ntoprak ise`

## C) Terim leak / tutarsızlık (ORTA)
- **#45** Mercury → Merkür (Merkür×3 baskın; kıvrık apostrof `’` U+2019 KORU):
  `ruh için Mercury’de, ya da\nkırmızı kral ve beyaz kraliçedir.` → `ruh için Merkür’de, ya da\nkırmızı kral ve beyaz kraliçedir.`
- **#91** ether → eter (eter×11 baskın):
  `beşinci elementi ether olarak\nbilinen şey sayar;` → `beşinci elementi eter olarak\nbilinen şey sayar;`
- **#92-93** quintessence → beşinci öz (Türkçe'de anlamlı; "beşinci element" zaten #89/#91'de geçiyor):
  - #92: `oysa simyacı bu\nunsuru quintessence olarak bilir.` → `oysa simyacı bu\nunsuru beşinci öz olarak bilir.`
  - #93: `Quintessence, yalnızca\nbütün elementleri birbirine bağlayan yapıştırıcı değil,` → `Beşinci öz, yalnızca\nbütün elementleri birbirine bağlayan yapıştırıcı değil,`
- **#163** "Ulü işi" → "Büyük İş'i" (the great work; #10/#66/#107/#654/#658 "Büyük İş"; DÜZ apostrof):
  `Ulü işi\nüstlenmeyi ciddi biçimde düşünüyorsanız,` → `Büyük İş'i\nüstlenmeyi ciddi biçimde düşünüyorsanız,`

## D) OPSİYONEL — nigrado → nigredo (tutarlılık/doğruluk, DÜŞÜK)
Dosya "nigrado" ×8 kullanıyor; doğru simya terimi **nigredo** (albedo/rubedo ile aynı -edo
kalıbı). Kaynağın kendisi de "nigrado" yazmış, o yüzden bu bir DÜZELTME-tercihi. İstenirse:
`Edit` replace_all `nigrado` → `nigredo` (8×). **C/D bağımsız:** A'daki #121 fix "nigrado"yu
KORUYOR; bu replace_all yapılırsa #121 dâhil hepsi düzelir. Yapılmazsa dosya "nigrado"da tutarlı
kalır. Kullanıcı kararı.

---

## DOKUNMA (doğrulanmış yanlış-pozitif / benign)
- **#301 "sol, sağ ve orta sütun", #327 "Ne sol el, ne sağ el"**: "sol" = TÜRKÇE "left",
  Latin "Sol" (güneş) DEĞİL. FP.
- **#44 "Luna", #291 "Luna"/"Caduceus"**: Latin simya adları, bilinçli korunur. DOKUNMA.
- **albedo / rubedo** (#121/#131/#132/#143/#426/#443/#476/#604): doğru simya aşama adları. KALIR.
- **#77 "chi"**: Doğu geleneği terimi, meşru. KALIR.
- **CPS uyarısı (16 satır)**: zamanlama, çeviri hatası değil. Kapsam DIŞI.
- **Kaynağın kendi bozuk İngilizcesi** (#45 "soul for in Mercury", #199 "it is benefits"):
  çeviri anlamı kurtarmış; ek müdahale gerekmiyor.

## Doğrulama (uyguladıktan sonra)
1. Cue sayısı **683**, timecode değişmez (`.bak` ile karşılaştır).
2. Değişen cue kümesi (A+B+C): **4, 45, 74, 77, 78, 80, 91, 92, 93, 120, 121, 163, 192, 201, 202,
   442** (16 cue). D yapılırsa + nigrado geçen 7 cue daha. Fazla/eksik OLMAMALI.
3. `ht.find_garble_tokens` tüm dosyada 0 (özellikle "water", "quintessence" gitmiş).
4. İngilizce element/terim leak taraması (case-insensitive): fire/water/air/earth (İngilizce),
   Mercury, ether, quintessence KALMAMALI. "g geçtiğinde", "dalı", "coutop", "Ulü" KALMAMALI.
5. "sol" (#301/#327), "Luna", "albedo/rubedo", "chi" DOKUNULMAMIŞ olmalı.

## Kod-gözlemi (uygulama YOK — ayrı tur adayı)
Bu koşuda **Polish Pass yeni garble ÜRETTİ** (#442 "g geçtiğinde", #192 "dalı", #163 "Ulü").
`find_garble_tokens` bunları YAKALAYAMADI ("g " tek-harf değil kelime-öncesi; "dalı"/"Ulü" geçerli
harf dizisi). Aday: Polish/Critic çıktısı için post-fix garble-recheck + tek-harf-önek ("^[a-zçğ] ")
ve bilinen-terim-bozulması (Ulü/nigrado gibi) guard'ı. Ayrıca element-adı leak'leri (fire/water/
air/earth) hiçbir katmanı tetiklemedi — yalnız "water" R2'ye takıldı; aday: bilinen-İngilizce-
element sözlüğü (fire/water/air/earth/gold/salt...) ile hedef-dil-kaçağı kontrolü.
