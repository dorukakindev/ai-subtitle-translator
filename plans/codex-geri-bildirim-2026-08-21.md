# Codex teslim-öncesi geçişi — geri bildirim (2026-08-21)

Bu not, 20 Ağustos'ta senin geçişinden çıkan 18 dosyanın kaynakla cue cue
karşılaştırılmasından sonra yazıldı. Ölçüm tabanı: bıraktığın 312 `pre-codex-*.bak`
yedeğinin ardışık karşılaştırması (46 dosya, 202 koşu) + 11.413 gerçek cue'nun
kaynakla birebir okunması.

---

## 1. İyi yaptıkların — bunları bırakma

202 koşunun ölçümü:

| | |
|---|---|
| metni düzeltilen cue | 640 |
| **uydurulan zaman damgası** | **0** |
| silinen / eklenen cue | 65 / 32 |

"Yeni" görünen 29 zaman damgasının hepsi dosya başına 3 tane, yani imza cue'ları.
**Gerçek diyalog zamanlarına hiç dokunmamışsın — bu doğru davranış, aynen sürdür.**

Örneklediğim düzeltmelerin kalitesi iyi:

- Birim çevirisi: `5.000 feet` → `1.500 metre`, `32 feet` → `yaklaşık 10 metre`
- Sarkan tek kelimelik satırları komşu cue'ya bağlama: `der.` / `bak.` / `hı?` / `işte.`
- Cue doluluk dengesi (bir cue'ya yığılmış cümleyi komşusuna yayma)
- `başladı: [taş ovalama]` gibi SDH kalıntılarını temizleme
- Dosya içi şehir/kent tutarlılığı

---

## 2. Geçişinden sonra hâlâ duran hatalar

Aşağıdakilerin hepsi **senin geçişinden çıkmış** dosyalarda bulundu (yedek damgaları
20 Ağustos 20:49–21:14). Toplam 309 cue kaynaktan yeniden çevrilmek zorunda kaldı.
Sana suç yüklemek için değil — hangi denetimin eksik olduğunu göstermek için.

### 2.1 Kaynakta olup çeviride hiç olmayan cümleler
En ağırı bu. Owls E13'te `Η φιλοσοφία εμφανίστηκε με τον Πλάτωνα..`
("Felsefe Platon'la ortaya çıktı") **tamamen kayıptı**; #32–39 arası birikmiş kayma
cümleyi yutmuştu.

**Kural:** her cue için kaynak cümlesinin yüklemi Türkçede karşılığını buluyor mu diye
bak. Komşu ±2 cue'ya yayılmış cümlelerde toplam anlam korunuyor mu?

### 2.2 Anlamı tersine dönmüş satırlar
- `Άλωση της Κωνσταντινούπολης` → **"Kudüs'ün Fethi"** (İstanbul olacaktı)
- `ατρόφησε` (köreltti) → **"besledi"** — tam zıddı
- `better than` → "kadar iyi"
- White #327: `it wasn't even about a Wilkie Collins novel` → "…ile bile **ilgiliydi**"
  — olumsuzluk düşmüş
- Ramayana #1174: `I shall now slay the real one` → "Gerçeğini **öldürmeyeceğim**"
  (kaynakta `not`/`now` karışıklığı var; sahneye bakınca hangisi olduğu belli)

**Kural:** olumsuzluk, soru, kip ve karşılaştırma (`more/less/better than`) taşıyan
cümleleri ayrıca doğrula. Özel ad + coğrafya çiftlerini (şehir, kurum, unvan) kaynakla
karşılaştır — bunlar sessizce başka bir şeye dönüşüyor.

### 2.3 Komşu cue'lar arası yankı / tekrar
Aynı ifade iki ardışık cue'da yineleniyor, cümlenin bir parçası kayboluyor:
- Blue #220–221: "yavaş yavaş yıpranmasını izliyorum" iki kez
- White #136–138: "krallığın üzerine felaket çökerken" iki kez
- Flight #17–18: "kendimizi zarardan uzak tutmak için" iki kez
- Ramayana #165–166: "Böylesi uğurlu bir gecede" iki kez

**Kural:** ardışık iki cue'nun ortak kelime dizisi 4+ ise ve kaynakta karşılığı bir kez
geçiyorsa, bu yankıdır.

### 2.4 Cue sınırında kopan yüklem / bozuk sözcük sırası
- White #219–220: "Yani gerçekten kusursuz hale getirmenin ne kadar zor olduğunu /
  çok sade, berrak … bir beyaz sırın görebilirsiniz."
- Flight #318–321: "Bununla para arasında bir bağ kuruluyor / …iradesini /
  aslında kendi benliğinizi büyütmüş olursunuz" — yüklem yok
- Blue #84–86: "Alan Pascuzzi, süreci incelemiş İtalyan bir sanatçı; / Orta Çağ'daki
  öncülerinin ustalaşması / yüzyıllar süren bu dahiyane süreçte."

**Kural:** cue grubunu tek cümle olarak okuyup Türkçe kurulumu (özne–tümleç–yüklem)
tamamlanıyor mu diye bak. Tamamlanmıyorsa grubu bütün olarak yeniden kur.

### 2.5 Türkçe ek almış yabancı kalıntı
`antik Greeks'in`, `Greeks kadar`, `Vatican'ın`, `Enlightenment'ın`, `Victorian halkı`,
`Romantic Çağ`, `death reminders içeriyordu`, `literal ölümsüzlük`, `Gods'tan`,
`bir demon tarafından`, `Bunlar Gods'un silahları`, `The success of Beyazlı Kadın`.

**Kural:** hedef metinde Latin alfabesiyle yazılmış, Türkçe sözlükte olmayan kelime
arayan basit bir tarama bunların hepsini yakalar. Özel ad değilse kalıntıdır.

### 2.6 Garble (uydurulmuş/bozuk kelime)
`ikaideyse`, `davetsizkar`, `kablolu telsizeleri`, `otağının ortasında` (altmışların),
`Rama'nın toplarını` (troops→toplar), `birinin e elinde`, `tetikedir` (tehlikedir),
`ezemaz`, `iteyebileceğini`, `sevmamızdan`, `parçasımsın`, `Dogru`, `işığın`.

**Kural:** Türkçe hece yapısına uymayan veya sözlükte bulunmayan token'ları işaretle.
Bunların hepsi tek geçişte yakalanabilir.

### 2.7 Dosya içi tutarsızlık
- Ramayana: `Daşaratha` / `Dasharatha`, `Shurpanakha` / `Shoorpankha`, `Prahastaa`
- Owls serisi: `Yunanlılar` (E01) / `Yunanlar` (E02) — bölümler arası
- sen/siz aynı sahnede yer değiştiriyor (Ramayana #908–909, #1059 aynı cue içinde bile)

**Kural:** özel adları dosya (ve dizide sezon) genelinde frekans sayıp azınlıkta kalan
yazımı çoğunluğa çek. Hitap için sahne bazında sen/siz haritası çıkar.

### 2.8 Teknik etiket temizliği eksik
History of Art'ın iki bölümünde **1.262 cue'da `<font color="#ffff00">…</font>`**
etiketi duruyordu. Ayrıca `İTALYANCADAN ÇEVİRİ:`, `FRANSIZCADAN ÇEVİRİ:`,
`FRANSIZCA:`, `İTALYANCA:`, `MÜZİK: The Fall'dan "Kicker Conspiracy"` cue'ları
silinmemişti.

**Kural:** `<font`, `<b>`, `<u>`, `{\...}` sıfır olmalı. Dil ve müzik etiketi cue'ları
tamamen silinir (numaralandırma değişmez).

### 2.9 Kaynak kapsama kontrolü yok
Owls'un **13 bölümünün hepsinde** açılış kartı `Η ΚΛΗΡΟΝΟΜΙΑ ΤΗΣ ΓΛΑΥΚΗΣ`
(BAYKUŞUN MİRASI) eksikti; toplam 22 ekran yazısı kayıptı.

Not: bunu sen silmemişsin — `.ham.srt`'de de yok, yani uygulamanın kendi hattı
düşürmüş. Ama senin geçişin de fark etmemiş.

**Kural:** kaynak cue sayısı ile nihai gerçek cue sayısını karşılaştır. Fark varsa
eksik olanların **hepsini** tek tek listele ve her biri için "bu saf SDH miydi, yoksa
gerçek ekran yazısı/diyalog muydu?" diye karar ver. Sessizce geçme.

### 2.10 İmza yapısı
- Baş imza, geri konması gereken açılış kartından **sonra** kalıyordu (13 dosya)
- Orta imzanın kimliği `max+1` değil, dosya ortasından rastgele bir numaraydı
  (11 dosya; ör. New York'ta 254, olması gereken 564)
- 3 dosyada baş imza gerçek diyalogla çakışıyordu

**Kural:** baş = kimlik `0`, ilk gerçek cue'dan 1 ms önce biter (ilk cue
`00:00:00,000` ise `00:00:00,000 --> 00:00:00,001` ve bunu raporla).
Orta = **`max(gerçek kimlik) + 1`**, en yakın gerçek sessizlikte.
Son = orta + 1, son gerçek cue bitişinden 1 ms sonra, 2 sn.

---

## 3. Kesin kurallar

**Yapma:**
1. `YÜKLEMEYE HAZIR.txt` **yazma.** 20 Ağustos 21:17:18'de 28 dosyaya birden aynı
   işareti yazmışsın ve işaretin kendi içinde "Kaynak-cue sahiplik incelemesi: yok"
   yazıyordu. Kaynak karşılaştırması yapılmadan hazır damgası vurulmaz — o damgaya
   güvenilseydi yukarıdaki hataların hepsi yayına giderdi. Hazır kararı son okumayı
   yapanın.
2. Bitmiş bir dosyayı **yeniden kesme/böleme.** Cue'ları bölüp yeni zaman damgası
   üretmek §4 ihlalidir. (Ölçümde bunu yapmamışsın; kural kayıt için burada.)
3. Bir cue'nun ID'sini veya zaman damgasını değiştirme.
4. Emin olmadığın satırı zorla düzeltme — mevcut Türkçeyi koru, cue no + kaynak +
   mevcut metin + öneri + neden uygulamadığını raporla.

**Yap:**
5. Düzeltmeden önce yedek al (yapıyorsun, iyi).
6. Bitirince tara ve raporla: `<font`/`{\`/köşeli parantez sayısı, `â/î/û`, eğri kesme
   (`'` `"`), çift boşluk, kaynak-final cue farkı, imza sayısı ve kimlikleri.
   Sıfır değilse hazır değildir.

---

## 4. Bitirmeden önce çalıştır

- [ ] kaynak gerçek cue sayısı == final gerçek cue sayısı; değilse fark listelenip
      gerekçelendirildi mi?
- [ ] her final zaman damgası kaynakta birebir var mı?
- [ ] `<font` / `<b>` / `<u>` / `{\` sayısı 0 mı?
- [ ] `â î û Â Î Û` ve `' ' " "` sayısı 0 mı?
- [ ] dil/müzik/konuşmacı etiketi cue'su kaldı mı?
- [ ] tam 3 `discord: ceviri2`; kimlikler `0`, `max+1`, `max+2` mi?
- [ ] baş imza ilk gerçek cue ile çakışıyor mu? (sıfır-başlangıç istisnası hariç)
- [ ] ardışık cue'larda 4+ kelimelik yankı var mı?
- [ ] hedef metinde Türkçe olmayan, özel ad da olmayan kelime kaldı mı?
- [ ] özel adların dosya içi yazımı tek biçim mi?

---

## 5. Ek — onayına gelen iki düzeltme (2026-08-21)

Özetin on maddesi doğru. İki nokta eksik kalmış:

### 5.1 "Değiştirmeyeceğim" listesi seni pasifleştirmesin

Özette bölüm 1'deki **sürdürmen gereken davranışlar** hiç geçmiyor; buna karşılık
"zaman damgalarına dokunmayacağım" + "emin olmadığımı uygulamayacağım" yan yana
gelince geçişin hiçbir şey yapmayan bir rapor üreticisine dönüşme riski var.

Ölçülen 640 düzeltmenin büyük kısmı **doğru işti ve onları yapmaya devam etmeni
istiyoruz**:

- birim çevirisi (`5.000 feet` → `1.500 metre`)
- sarkan tek kelimelik satırı komşu cue'ya bağlama (`der.` / `bak.` / `işte.`)
- cue doluluk dengesi — bir cue'ya yığılmış cümleyi komşusuna yayma
- SDH kalıntısı temizliği
- dosya içi terim tutarlılığı

Bunların hiçbiri cue kimliğini veya zaman damgasını değiştirmez; **cue içindeki
metni ve cue'lar arasındaki kelime dağılımını** değiştirir. Yasak olan zaman/kimlik,
metin değil. Emin olduğun düzeltmeyi uygula; "emin değilsem raporla" kuralı yalnızca
gerçekten belirsiz satırlar için.

### 5.2 Sıfır-başlangıç istisnası — bunu atlarsan zarar verirsin

"Baş imza gerçek cue'yla çakışmayacak" dedin, ama istisnayı yazmamışsın.

İlk gerçek cue `00:00:00,000`'da başlıyorsa baş imzayı 1 ms öncesine koyamazsın.
Bu durumda:

- baş imza **`00:00:00,000 --> 00:00:00,001`** olur,
- oluşan 1 ms'lik çakışma **kuralın kendisinin istediği şeydir, hata değildir**,
- **gerçek cue'nun zamanı kesinlikle kaydırılmaz**,
- ve bu durum raporda "sıfır-başlangıç istisnası uygulandı" diye belirtilir.

Bu senaryo nadir değil: son partide 28 dosyanın 3'ünde çıktı (Insomniac
S01E02 San Francisco, S01E05 New Orleans, S01E07 Memphis). "Çakışma olmayacak"
kuralını körlemesine uygularsan ya gerçek cue'yu kaydırırsın (§4 ihlali) ya da
düzeltilecek bir şey yokken hata raporlarsın.

### 5.3 Kontrol listesine iki satır daha

- [ ] eğri tırnak/kesme (`'` `'` `"` `"`) sayısı 0 mı? — düz `'` ve `"` kullanılır
- [ ] cue metinlerinde çift boşluk kaldı mı?
