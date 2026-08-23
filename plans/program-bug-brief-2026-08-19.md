# Program tarafı bulguları — 2026-08-19

Kaynak: 78 nihai altyazı dosyasının kaynakla satır satır karşılaştırılması
(Insomniac 8, Myths & Monsters 6, Mahabharata 3, Tribal Eye 4, Extraordinary Rituals 2,
YÜKLENECEKLER 36, Ancient Egyptian Acoustics 1 + daha önce denetlenen 18).

Her madde gerçek dosya/cue kanıtına dayanıyor. Spekülasyon yok.

---

## P0 — Teslim edilen dosyaya bozuk içerik sızdıran hatalar

### 1. `[ÇEVİRİ EKSİK]` yer tutucusu nihai dosyaya çıkıyor

**Kanıt:** 4 dosyada 5 örnek.
- `Order and Disorder S01E01` #190
- `The Shock of the New.s01e01` #149
- `The Shock of the New.s01e02` #391 ve #405
- `The Shock of the New.s01e08` #91

**Desen her seferinde aynı:** model bir cümleyi önceki cue'ya sıkıştırıyor, son cue boş
kalıyor, uygulama boş bırakmak yerine yer tutucu yazıyor.
Örn. Order E01: #189 = "tüm ısı makinelerinin çalışmasının temel biçimini geliştirdi ve
soyutladı." (iki cue'nun içeriği), #190 = `[ÇEVİRİ EKSİK]`.

**Sorun:** Nihai Teslim Denetimi bunu yakalamıyor. `[HATA]` için guard var,
`[ÇEVİRİ EKSİK]` için yok.

**Öneri:**
1. `[ÇEVİRİ EKSİK]`'i `[HATA]` ile aynı guard'a ekle — teslim denetimi FAIL versin.
2. Daha iyisi: bu durumda ilgili chunk'ı tek cue için yeniden istet; model zaten
   içeriği üretmiş, sadece cue'lara dağıtımı bozuk.

---

### 2. İçerik kayması sınıfı — mevcut detektörler kaçırıyor

En ciddi kalite sorunu. Türkçe metin, ait olmadığı cue'ya yazılıyor; izleyici yanlış
anda yanlış satırı görüyor ve kaynak cümleleri tamamen kayboluyor.

**Kanıt:**

| Dosya | Bölge | Ne oldu |
|---|---|---|
| `The Shock of the New.s01e01` | #123–#149 (27 cue) | Kayma #123'te başlayıp büyüyor; Blériot'nun Manş geçişini anlatan 4 cümle tamamen kayıp, son cue `[ÇEVİRİ EKSİK]` |
| `Mahabharata S01E02` | 16 ayrı cue | Metin bambaşka. #219 `I'm the son of a driver` → "arabacının oğlu Karna'nın bile"; #989 `I still hear the clash of steel` → "Hala annem misin?"; #843 `If you still have breath` → "Hala Duryodhana'yı mı düşünüyorsun?" |
| `Myths . Monsters S01E02` | #552–#574 (23 cue) | Bir cue kaymış; 2 kaynak cümlesi yok olmuş, 2 cue tekrarlanmış |
| `Mahabharata S01E02` | #688–#690 | Üç cue'luk kayma; `Have you forgotten it?` kayıp |
| `Mahabharata S01E03` | #1218–#1219 | #1219 = #1218'in tekrarı; kendi içeriği kayıp |

**`detect_alignment_issues` / `adjacent_duplicate` bunları yakalamadı.**
Uzunluk oranı taraması Mahabharata'daki 16 kaymadan yalnızca 5'ini işaretledi.

**Öneri — ucuz ve etkili bir detektör:**
Kaynak cue *i* ile çeviri cue *i*'nin "ayırt edici jeton" kümelerini karşılaştır:
- rakam grupları (`\d{2,4}`)
- Latin alfabeli özel adlar (`\b[A-Z][a-z]{3,}\b`) — Rusça/Arapça kaynakta bile
  özel adlar Latin harfle geçiyor
- ALL-CAPS adlar

Çeviri *i*'nin jetonları kaynak *i*'de yok ama kaynak *i±1..4*'te varsa işaretle.
Aynı kaydırma değeri 3+ cue ardışık tekrarlıyorsa "kayma bölgesi" olarak raporla.

Bu tarama Shock E01'deki bölgeyi doğru noktadan (#127) yakaladı. Rapor yeter,
otomatik onarım gerekmez — insan/agent düzeltir.

---

### 3. Tamamlanmış `.partial.srt` nihai konuma terfi ettirilmiyor

**Kanıt:** 4 bölüm aylarca "çevrilmemiş" görünüyordu:
- `Order and Disorder S01E01 - Energy` — 673/675 cue
- `The Shock of the New.s01e01` — 682/682
- `The Shock of the New.s01e02` — 882/882
- `The Shock of the New.s01e08` — 858/859

Dördü de **eksiksiz**: kaynağın tüm süresini kapsıyor, `[HATA]` yok, boş cue yok,
çevrilmemiş satır yok, bozuk blok yok. Sadece `Raporlar/Kurtarma/*.partial.srt`
içinde kalmış ve üç imza eklenmemiş.

**Öneri:** Başlangıçta (veya `_resume_batches` yanında) `.partial.srt` tara:
kaynak kapsaması %100 ve yer tutucu yoksa "bu dosya aslında tamam, terfi ettirilsin mi?"
diye sor veya doğrudan imzaları ekleyip nihai konuma yaz. Aksi halde tamamlanmış iş
sessizce kayboluyor.

---

### 4. §6 sıfır-başlangıç istisnası uygulanmamış — baş imza hiç eklenmiyor

**Kanıt:** Insomniac 8 bölümün 3'ünde baş imza yoktu:
`S01E02 San Francisco`, `S01E05 New Orleans`, `S01E07 Memphis`.
Üçünde de ortak nokta: **ilk gerçek cue `00:00:00,000`'da başlıyor.**
Baş imzaya yer kalmadığı için uygulama imzayı tamamen atlıyor; dosya 3 yerine
2 imzayla teslim ediliyor ve Nihai Teslim Denetimi bunu FAIL saymıyor.

**Öneri:** İlk gerçek cue 2 ms'den erken başlıyorsa baş imzayı
`0` / `00:00:00,000 --> 00:00:00,001` olarak yaz, 1 ms örtüşmeyi
çakışma denetiminde beyaz listeye al, logda "sıfır-başlangıç istisnası uygulandı" de.
İmza sayısı 3 değilse teslim denetimi kesin FAIL vermeli.

---

### 5. Eski hazırlayan imzası Kiril kaynakta yakalanmıyor

**Kanıt:** `The Shock of the New.s01e08` nihai dosyasında iki cue vardı:
```
#858  Субтитры подготовлены Red Bee Media Ltd
      → "Altyazılar Red Bee Media Ltd tarafından hazırlanmıştır"
#859  Эл. почта: subtitling@bbc.co.uk
      → "E-posta: subtitling@bbc.co.uk"
```
Yani hem çevrilmiş hem de teslim edilmiş.

**Arapça çalışıyor** (Myths dosyalarındaki `ترجم من قبل: …` doğru silinmişti),
Kiril çalışmıyor.

**Öneri:** `_DELIVERY_CREDIT_*` desenlerine ekle:
- Kiril: `Субтитры`, `Перевод`, `подготовлен`, `Эл\.\s*почта`
- Dilden bağımsız: çıplak e-posta adresi (`\S+@\S+\.\w+`) ve URL içeren cue —
  gerçek diyalogda neredeyse hiç geçmez, kredi cue'sunda hep geçer.
- Mevcut `altyaz[ıi]\s*:` dalı iki nokta zorunlu kılıyor; `altyazı hazırlayan`,
  `çeviri ve senkron` gibi iki noktasız biçimleri de kapsasın.

---

### 6. SDH temizleyici ekran üstü künye yazılarını siliyor

**Kanıt:** `Myths . Monsters` E01 ve E06'da 4 gerçek cue silinmişti:
- E01 #396 `"حورية البحر الصغيرة"، تأليف "هانز كريستيان أندرسن"` (Küçük Deniz Kızı, H.C. Andersen)
- E06 #392 Frankenstein / Bayan Shelley
- E06 #399 The Vampyre / Lord Byron
- E06 #415 Dracula / Bram Stoker

Bunlar ekranda görünen kitap künyeleri — SDH değil, içerik.
E01'de silinmesi **cümleyi kırdı**: sonraki cue "…en zarif öykülerdendir." öznesiz kaldı.

**Öneri:** Bir cue'yu SDH diye silmeden önce iki kontrol:
1. Sonraki cue küçük harfle başlıyor veya yüklemsizse (yani cümlenin devamıysa),
   silme — büyük ihtimalle içerik.
2. "Başlık, yazar/eser sahibi" kalıbı (`«…», تأليف …` / `X, by Y`) beyaz listeye alınsın.

Not: aynı dosyalarda uzman ad-künyeleri (`د. (ليز غلوين) / جامعة (لندن)`) doğru
silinmişti — o davranış korunmalı.

---

## P1 — Kalite kaybı, teslimi bloke etmiyor

### 7. Tipografik noktalama normalize edilmiyor

**Kanıt:** 36 dosyada 404 eğik kesme/tırnak (`’ “ ”`) + 142 Fransız tırnağı (`« »`);
bitmiş 11 dosyada 12 daha. Aynı dosyanın içinde `Camelot’taki` ile `Camelot'un`
yan yana duruyordu.

Log satırı `0 bozuk OCR tırnak işareti düzeltildi` diyor — yani bir adım var ama
bu karakterleri kapsamıyor.

**Öneri:** Nihai temizlikte `’ ‘ “ ” « »` → `' "` dönüşümü. Riski yok;
Türkçe altyazıda bu karakterlerin yeri yok.

### 8. Görünmez karakterler

**Kanıt:** `Connections S01E08` #167 `ay­nı`, `S01E09` #799 `selen­yum` —
kelimenin ortasında U+00AD (soft hyphen). Bazı oynatıcılarda tire olarak görünür.

**Öneri:** U+00AD, U+200B–200F, U+2060, U+FEFF'i nihai temizlikte sil.

### 9. Cue numarası metne sızıyor

**Kanıt:** 2 örnek —
`Mahabharata S01E01` #107 = `"Sadakati bu kadar yücelten sen,\n108"`,
`Order and Disorder S01E01` #81 = `"Yazışmaları sırasında\nLeibniz ve Papin, 84"`.

JSON-onarım/chunk-ayrıştırma yolunda id'nin metne karışabildiğini gösteriyor.

**Öneri:** Yazımdan sonra ucuz bir guard: metninde tek başına tam sayı satırı olan
ya da kendi id'sinin ±3 komşusuyla biten cue'yu raporla.

### 10. Dosya içi terim kayması hala teslim ediliyor

`_normalize_mixed_terms` varsayılan KAPALI. Bu oturumda elle düzelttiğim, hepsi
**aynı dosya içinde** iki biçimde geçen terimler:

`Krişna/Krishna` · `Şiva/Shiva` · `Vişnu/Vishnu` · `Jaquard/Jacquard` ·
`Maxwell'ın/Maxwell'in` · `Fomoryonlar/Fomoriler/Fomorlar` · `Avlis/Aulis` ·
`Aşil/Akhilleus` · `Virgil/Vergilius` · `yaşayan kuvvet/canlı kuvvet` ·
`Victorian/Viktorya dönemi` · `bindirme/konsol` · `düşme kapısı/portkulis` ·
`bel/sırt` · `kobay/Gine domuzu` · `turkuaz/firuze` · `Geoffrey of Monmouth/Monmouthlu Geoffrey`

**Öneri:** Özelliği açmaya değer, ama **yalnızca sabit sözlükteki bir kaynak terimin
Türkçe karşılığı dosya içinde birden fazla biçimde geçtiğinde** tetiklensin
(ham frekansa değil, sözlüğe çapalansın). Böylece hafızadaki "sızıntı vs çoğunluk"
riski ortadan kalkar.

### 11. Sabit sözlük özel adları/eser adlarını Türkçeleştiriyor

**Kanıt:** Ancient Egyptian koşusunda `Egyptian Sonics` → `Mısır Sonikleri`.
Bu, konuşmacının **kitabının adı** (#27 ve #540'ta geçiyor, #541'de fiyatı veriliyor).

**Öneri:** Sözlük üreticisine "çevrilmez" sınıfı: kitap/film/marka/şirket/proje adları.
Kişi ve yer adları zaten korunuyor, eser adları korunmuyor.

### 12. Satır bölme yerleşimi denetlenmiyor

**Kanıt:** 36 dosyada 1.046 ihlal. Türü:
- Sarkan edat: `…tiyatroları ⏎ gibi yerlerde`, `…gözünüzün görebildiği yere ⏎ kadar`
- Satır sonunda bağlaç: `10. yüzyılın kaos ve ⏎ karmaşasından`
- Soru eki kopmuş: `…yolcu uçakları ⏎ mı yapmalıyız?`
- Tamlama bölünmüş: `oldukça özel bir ⏎ zincirleme tepki`

Mekanik olarak 521'ini düzelttim (kelimeyi doğru tarafa taşımak yetiyor).

**Öneri:** Yazımdan önce bir satır-bölme geçişi. Kurallar:
- Satır 2 şu kelimelerle başlıyorsa yukarı al:
  `için, gibi, ile, göre, kadar, rağmen, üzere, dolayı, beraber, birlikte, ise, bile, dahi, de, da, mi/mı/mu/mü`
- Satır 1 şunlarla bitiyorsa aşağı indir:
  `ve, veya, ya, ile, ki, hem, her, bir, bu, şu, çok, daha, en, tam, hiç, ne, o`
- Satır 1 rakamla bitiyorsa rakamı aşağı indir (birimden ayırma)
- Satır noktalama ile bitiyorsa (doğal cümle sınırı) **hiç dokunma**
- Taşıma sonrası satır ~58 karakteri aşacaksa taşımayı atla, raporla

### 13. Büyük harf kaynakta nokta/virgül ayrımı korunuyor

**Kanıt:** ALL-CAPS closed caption kaynaklarda (The Brain) nokta virgül yerine
kullanılıyor; çeviri bunu birebir kopyalıyor.
`CAROL. BILL. THEIR SONS TOM AND JOHN. AND DAUGHTER VICTORIA.`
→ "Carol. Bill. Oğulları Tom ve John. Ve kızları Victoria."
Doğrusu: "Carol, Bill, oğulları Tom ve John, bir de kızları Victoria."

36 dosyada 88 aday; hepsi hatalı değil, insan kararı gerekiyor.

**Öneri:** Kaynak büyük-harf-ağırlıklıysa (harflerin >%80'i büyük) sistem promptuna
tek satır ekle: "Kaynak noktalaması closed-caption biçimidir; noktaları Türkçe
söz dizimine göre virgüle çevir."

### 14. Kelime ortası boşluk

**Kanıt:** Ancient Egyptian #154 `Piram itler Çağı`.
Nadir ama ucuz bir guard'la yakalanır.

---

## Doğru çalışan, bozulmaması gerekenler

- Arapça çevirmen imzası temizliği (`ترجم من قبل: …`) — Myths 6 dosyada doğru çalıştı
- Uzman ad-künyesi cue'larının silinmesi (`د. (ليز غلوين) / جامعة (لندن)`)
- Tribal Eye'daki 33 SDH cue'sunun (`(Shrill flute playing)`) silinmesi — hepsi doğru
- Deyim haritası: `straight as a die` → "cetvelle çizilmiş gibi dümdüz",
  `leave that plug in` → "o tanıtım da kalsın", `jet pillar` → "djed sütunu"
- Sahne planı / gönderge çözümü: Mahabharata'da 1.138 cue'da tek bir zamir hatası çıkmadı
- Zaman damgası sadakati: 78 dosyanın hiçbirinde kaynakla uyumsuzluk yok

## Kasıtlı davranış, hata sanılmasın

- CPS uyarısı verip condense uygulamaması doğru; condense'in çıktı doğrulaması
  tamamlanana kadar KAPALI kalmalı
- `[HATA]` satırlarının kaynak metinle doldurulması
- Şapkalı harf temizliği (Ancient Egyptian koşusunda 28 harf temizlendi)
