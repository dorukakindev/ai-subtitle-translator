# Brief: Göbekli Tepe (Genesis + Portal) çeviri kalitesi QA — Sonnet 5 için

Hazırlayan: **Opus 4.8** (analiz + karar, 2026-07-08). Protokol: Opus hangi satırın bozuk
olduğuna ve doğru Türkçe karşılığına karar verir; **Sonnet 5 dosyada uygular** (Opus dosyayı
düzenlemez). Bkz. [[fable5-planning-protocol]]. Kaynak: [[context_aware_translation_2026_06]],
[[mini-main-model-quality-2026-07]].

**Dosyalar (VTT girişi → SRT çıktısı):**
- **F1** = `D:\Openai Altyazı Çevirisi\translated\Göbekli Tepe Genesis of the Gods with Andrew Collins.srt` (639 cue)
- **F2** = `D:\Openai Altyazı Çevirisi\translated\Göbekli Tepe- Portal to the Universe with Andrew Collins.srt` (966 cue)
- Kaynaklar: `E:\ALTYAZILAR\Altyazilar\Hulu-Altyazilar\*.vtt`
- Cue id'leri app'in parse'ıyla (`gui.parse_subtitle`) sıralı numaralandırılır; aşağıdaki
  numaralar o parse'a göredir. **Uygulamadan ÖNCE `.bak` al.**

**Uygulama yöntemi (Sonnet için):** dosyayı `subtitle_formats.read_subtitle_text` ile oku,
ilgili cue'yu **id ile** bul, o cue'nun METİN bloğunda aşağıdaki "Mevcut → Yeni" değişimini
uygula, `utf-8-sig` + `\n` ile yaz. **Cue sayısını, sıra numarasını, timecode'u DEĞİŞTİRME.**
Aşağıdaki her "Mevcut Türkçe" string'i dosyadan birebir doğrulandı (2026-07-08).

---

## 1. HÜKÜM

Her iki dosya da genel olarak **iyi kalitede**: akıcı, kaynağa büyük ölçüde sadık, `[HATA]`/eksik
cue **yok**, kaynak-dil kelime salatası **yok**. F2, F1'den daha temiz. Gerçek kusurlar cerrahi
olarak düzeltilebilir ve şunlarla sınırlı:
- **1 yapısal cue-kayması** (F1 #610-617) — senkron bozucu, öncelikli.
- **Terim tutarsızlığı**: "Watchers" 11 yerde **"Gözegçiler"** (bozuk) → "Gözcüler".
- **Bozuk token / İngilizce artık kümesi** (garble'lar, "19th century", "somehow" vb.).
- **Birkaç dağıtım-tekrarı** (aynı cümle iki cue'da) ve **birkaç gerçek anlam kaybı**.

**Önemli dürüstlük notu:** Otomatik tarama (`has_non_turkish_target_leak`, garble regex) bu
hataların **çoğunu kaçırdı** (davânın, toplumlarde, somehow, essaslı, tatmak, Bakırsan…).
Aşağıdaki liste **her iki dosyanın baştan sona yakın okunmasıyla** çıkarıldı; log/tarama değil,
kaynak+final karşılaştırması esas alındı.

---

## 2. F1 — UYGULANACAK DÜZELTMELER

### GÖREV 1 (ÖNCELİK 1) — F1 cue-kayması #610-617 (senkron bozan, yapısal)

`detect_alignment_issues` bu bölgede outlier_cluster verdi. İçerik #612'den itibaren +1 kaymış;
#617'de bozuk kalıntı ("Aman, şöyle biraz") var; #618 zaten doğru. **#610-617'yi cue-cue,
kaynağa sadık, aşağıdaki tam metinlerle DEĞİŞTİR** (bu, mevcut çevirileri sadece kaydırmak
değil — #610/#611'i de düzeltir, yoksa "sürüngen…sürüngen" tekrarı oluşur):

| cue | EN (kaynak) | Mevcut Türkçe | **Yeni Türkçe** |
|---|---|---|---|
| #610 | My insiders have said that these people do appear | İçeridekiler bana, bu insanların gerçekten sürüngen gibi göründüğünü | İçeridekilerin söylediğine göre, bu insanlar gerçekten |
| #611 | to be reptilian, and their children actually | ve çocuklarının aslında bu devlere dönüştüğünü söylediler. | sürüngen gibi görünüyormuş; çocukları da aslında |
| #612 | became these giants. | Onlar melezler ve çok uzun insanlar. | bu devlere dönüşmüş. |
| #613 | They're hybrids, and they're very tall people. | Uzamış kafatasları falan var. | Onlar melez ve çok uzun boylu insanlar. |
| #614 | They have elongated skulls, all that kind of stuff. | Yani buradaki şeyler oldukça çılgın ve vahşi. | Uzamış kafatasları falan var. |
| #615 | So this is pretty wild and crazy stuff here. | Bunu anlıyorum. | Yani buradaki şeyler oldukça çılgınca ve tuhaf. |
| #616 | I understand that. | İnancı biraz askıya alman gerekiyor. | Bunu anlıyorum. |
| #617 | You kind of have to suspend disbelief a little bit. | Aman, şöyle biraz. | İnsanın inancını biraz askıya alması gerekiyor. |

(#618 "Ama unutmayın, bununla ilgili oldukça sağlam veriler var." zaten DOĞRU — **dokunma**.
#619-623 iyi huylu çok-cue'lu dağıtım — anlam doğru, **dokunma**.)

### GÖREV 2 (ÖNCELİK 6) — "Gözegçiler" → "Gözcüler" (terim, 11 yer)

"Watchers" (Henok Kitabı'ndaki gözcü melekler) tutarlı biçimde **"Gözegçiler"** diye bozuk;
standart Türkçe **"Gözcüler"**. Şu cue'ların HEPSİNDE (ekleriyle) değiştir — tarama ile teyitli:
**#39, #41, #46, #378, #383, #390, #401, #415, #437, #595, #605.**
- Ek uyumu: `Gözegçiler`→`Gözcüler`, `Gözegçiler'e`→`Gözcülere`, `Gözegçileri`→`Gözcüleri`.
- **#595 ve #605'te ayrıca kaynakta olmayan "(Watchers)" parantez notu var → SİL.**
  - #595 Mevcut: `bu Gözegçiler (Watchers) görünüşe göre dünya dışı varlıklardı.` → Yeni: `bu Gözcüler görünüşe göre dünya dışı varlıklardı.`
  - #605 Mevcut: `Ve gerçekten de bu Gözegçileri (Watchers) püskürttüler;` → Yeni: `Ve gerçekten de bu Gözcüleri püskürttüler;`
- #415 aynı zamanda GÖREV 3'te (aşağıda) — orada tam satır verildi.

### GÖREV 3 (ÖNCELİK 3) — F1 bozuk token / İngilizce artık

| cue | Mevcut Türkçe (bozuk kısım) | **Yeni** |
|---|---|---|
| #25 | ...Luciferçi **simwolika (şeytani sembolizm)** yaydıkları... | ...Luciferçi **sembolizm** yaydıkları... |
| #127 | **Mısır'teki** Yüksek Antikiteler Konseyi'nin... | **Mısır'daki** Yüksek Antikiteler Konseyi'nin... |
| #132 | ...biz **Giza platosy** hakkında | ...biz **Giza platosu** hakkında |
| #143 | gerçekten **platosyun** altına kadar uzanıyor | gerçekten **platonun** altına kadar uzanıyor |
| #153 | ...girişini **19th century'in** ilk dönemlerinde... | ...girişini **19. yüzyılın** ilk dönemlerinde... |
| #175 | ...bu aslında **19th century'nin** ortasında bildirildi. | ...bu aslında **19. yüzyılın** ortasında bildirildi. |
| #179 | ...**19th century'nin** erken dönemine ait | ...**19. yüzyılın** erken dönemine ait |
| #267 | **Mısır'in**, şu an ona atfettiğimiz önemden | **Mısır'ın**, şu an ona atfettiğimiz önemden |
| #271 | Sfenks anıtının, **Giza platosy'nın** | Sfenks anıtının, **Giza platosunun** |
| #289 | Orion'un kuşak yıldızlarının **Giza platosy** | Orion'un kuşak yıldızlarının **Giza platosu** |
| #311 | **Nile** bölgesine ne kadar yağmurun | **Nil** bölgesine ne kadar yağmurun |
| #415 | **Gözegçiler'e**, yani **melekler'e** dair olanlara... | **Gözcülere**, yani **meleklere** dair olanlara... |
| #473 | **Persiya'dan**, eski İran'dan başka anlatılar da var | **Pers'ten**, eski İran'dan başka anlatılar da var |
| #474 | ...onlar da **Immortals'ın** benzer şeyler yaptığını... | ...onlar da **Ölümsüzler'in** benzer şeyler yaptığını... |
| #574 | ancak **18th century'de**, bir İskoç **kaşif** | ancak **18. yüzyılda**, bir İskoç **kâşif** |

(#473 "Pers" ve #474 "Ölümsüzler" özel-isim yerelleştirme kararıdır; önerilir ama Sonnet emin
değilse #473/#474'ü atlayıp diğerlerini uygulayabilir. Diğer tüm satırlar net garble/artık.)

### GÖREV 4 (ÖNCELİK 4) — F1 anlam bozuklukları

| cue | EN | Mevcut Türkçe (yanlış) | **Yeni Türkçe** |
|---|---|---|---|
| #8 | none other than Andrew Collins, a legend who | Andrew Collins'ten başka kimsenin yapmadığı biri olarak, | ta kendisi Andrew Collins; öyle bir efsane ki |
| #9 | has written many books and is really breaking new ground. | çok kitap yazmış ve gerçekten yeni bir alan açan bir efsane olarak. | çok kitap yazmış ve gerçekten yeni bir çığır açıyor. |
| #113 | You print the truth, and people either like it or they don't. | Hakikati yayımlarsın; insanlar **yanın** sever ya da sevmez. | Hakikati yayımlarsın; insanlar **ya** sever ya da sevmez. |

- **#8+#9 birlikte:** "none other than X" = "**X'in ta kendisi**"; mevcut "başka kimsenin
  yapmadığı" tamamen yanlış. #9 sonunu "…bir efsane olarak" bırakırsan #8'deki "efsane" ile
  tekrar olur → #9'u "…yeni bir çığır açıyor." yap ("breaking new ground").
- **#113:** "yanın" bozuk token; "insanlar ya sever ya da sevmez" doğru kalıp.

### GÖREV 5 (ÖNCELİK 7) — F1 dağıtım-tekrarı (aynı içerik iki cue'da)

| cue | Mevcut Türkçe | **Yeni Türkçe** | Gerekçe |
|---|---|---|---|
| #285 | Baktığınızda, yağmur aşındırmasına ve su aşındırmasına benziyor. | Baktığınızda, yağmur aşındırmasına | #285 ve #286 **birebir aynı** tam cümle → böl |
| #286 | Baktığınızda, yağmur aşındırmasına ve su aşındırmasına benziyor. | ve su aşındırmasına benziyor. | (kaynak #285 "rain weathering" / #286 "water weathering") |
| #569 | uzatılmış hikâyedir, Nephilim'in **iş** hikâyesidir | uzatılmış hikâyedir, Nephilim'in hikâyesidir | "iş" fazlalık/garble ("themselves" zaten #570'te) |
| #633 | uzaylı yaşam tarafından geliştirilmiş bir süper silah gibi görünüyor. | uzaylı yaşam tarafından geliştirilmiş | "uzaylı yaşam tarafından" hem #633 hem #634'te → böl |
| #634 | uzaylı yaşam tarafından. | bir süper silah gibi görünüyor. | (kaynak #633 "super-weapon developed" / #634 "by extraterrestrial life") |

---

## 3. F2 — UYGULANACAK DÜZELTMELER

### GÖREV 6 (ÖNCELİK 3) — F2 bozuk token / İngilizce artık

| cue | Mevcut Türkçe (bozuk) | **Yeni** |
|---|---|---|
| #88 | Aman Tanrım, bu **davânın** tepesinde mi? | Aman Tanrım, bu **dağın** tepesinde mi? |
| #183 | Burası **yatörensel** ya da | Burası **ya törensel** ya da |
| #242 | kulübelerin ilkel **toplumlarde** var olduğu... | kulübelerin ilkel **toplumlarda** var olduğu... |
| #307 | Ve bu, dünyanın **bu çok o bölgesinde** başlıyor, yani, | Ve bu, dünyanın **tam bu bölgesinde** başlıyor, yani, |
| #364 | Size boynuz **atacalar**. | Size boynuz **atacaklar**. |
| #603 | özellikle kış **gündönümünde deki** belirli noktalara. | özellikle kış **gündönümündeki** belirli noktalara. |
| #633 | **>>bir başka seferde** yüzde 22 azalıyordu. | **bir başka seferde** yüzde 22 azalıyordu. |
| #637 | Tabetha Boyajian adlı **a astronom** | Tabetha Boyajian adlı **astronom** |
| #751 | Çünkü dolanıklık, **normale zamanın** dışında işler. | Çünkü dolanıklık, **normal zamanın** dışında işler. |
| #767 | --senin de **orada a olduğunu**-- | --senin de **orada olduğunu**-- |
| #805 | dünyadaki ve dünya dışındaki **essaslı** her büyük teleskop | dünyadaki ve dünya dışındaki **neredeyse** her büyük teleskop |
| #825 | **Bakırsan**, başka bir sonuç alırsın. | **Bakarsan**, başka bir sonuç alırsın. |
| #886 | Avrasya **kıtasını a araştırmaya** başladığımız | Avrasya **kıtasını araştırmaya** başladığımız |

### GÖREV 7 (ÖNCELİK 2/3) — F2 kaynak-dil sızıntısı (çevrilmemiş İngilizce)

| cue | EN | Mevcut Türkçe | **Yeni** |
|---|---|---|---|
| #934 | And somehow we can access that. | Ve **somehow** ona erişebiliyoruz. | Ve **bir şekilde** ona erişebiliyoruz. |

(Not: "somehow" ham İngilizce olarak final çıktıda kalmış; `has_non_turkish_target_leak` bunu
yakalayamadı — bkz. Görev 9 opsiyonel kod önerisi.)

### GÖREV 8 (ÖNCELİK 4) — F2 anlam bozuklukları

| cue | EN | Mevcut Türkçe (yanlış) | **Yeni Türkçe** |
|---|---|---|---|
| #405 | There was what we'd call a power elite behind the motivating, | **Bu** | İktidar seçkinleri diyebileceğimiz bir güç vardı; |
| #406 | of the bringing together of these hunter-gatherers | bu avcı-toplayıcıları bir araya getir**menin** | bu avcı-toplayıcıları bir araya getir**ip** |
| #407 | to create monuments like this. | böyle anıtlar yap**mak için**. | böyle anıtlar yap**tıran**. |
| #695 | to solve all sorts of weird problems, | her türlü tuhaf problemi **tatmak** için, | her türlü tuhaf problemi **çözmek** için, |
| #844 | but the universe as a whole. | bir bütün olarak evrenle **eşitliğimizi** geliştireceğiz. | bir bütün olarak evrenle **etkileşimimizi** geliştireceğiz. |

- **#405-407 birlikte:** #405 "Bu" tek başına bozuk parça; kaynaktaki "power elite" (iktidar
  seçkinleri) düşmüş. Üç cue birlikte düzeltilmeli (yukarıdaki hali kaynağa sadık, akıcı).
- **#695:** "solve"=çözmek; "tatmak" (=to taste) yanlış.
- **#844:** "interaction"=etkileşim; "eşitlik" (=equality) yanlış.

---

## 4. YANLIŞ-POZİTİFLER / DOKUNULMAYACAKLAR

- **Geçerli Türkçe kelimeler** garble regex'inde yanlış işaretlendi — **dokunma**: F1 #379/#532
  "öteki", F2 #485 "öteki dünyaya", F2 #930 "geçmişteki".
- **F1 #476/#477 "From the Ashes of Angels"** — İngilizce **kitap adı**, doğru; İngilizce
  kalmalı. (Bu cue'larda "…adlı kitapta" hafif tekrarlanıyor ama anlam tam; **opsiyonel**,
  düzeltme şart değil.)
- **F1 #619-623** — çok-cue'lu cümle dağıtımı, anlam doğru; **dokunma**.
- **F2 #746 "misease"** gibi yerlerde **kaynak VTT'nin kendisi** bozuk (oto-transkript);
  Türkçe elinden geleni yapmış — **bozuk kaynağa karşı "düzeltme" yapma**.
- **Tüm timecode ve sıra numaraları** — **değiştirme**.
- **Sınırda/düşük öncelik (yalnız istenirse, doğal-Türkçe cilası turunda):** F1 #95 "ait
  oldukları şey olarak tanıdı" (kaba ama anlam var), F1 #286/#287 "küçük bir aile odasının"
  dangling kuyruk, F2 #3 açılış tırnağı eksik (`Beyond Belief."`), F2 #46 kapanış tırnağından
  önce fazla boşluk, F2 #601 "Garden of Eden"→tercihen "Aden Bahçesi". **Bunlar zorunlu
  değil; Sonnet emin değilse dokunmasın.**

---

## 5. DOĞRULAMA ADIMLARI (Sonnet, uyguladıktan sonra)

1. **Cue sayısı sabit:** F1 = 639, F2 = 966 (değişmemeli).
2. **Cue-kayması temiz:** `subtitle_translator_gui.detect_alignment_issues`'i F1 final vs kaynak
   üzerinde çalıştır → #610-617 için bulgu KALMAMALI.
3. **Garble/leak gitti:** dosyalarda şu string'ler KALMAMALI —
   F1: `Gözegç`, `platosy`, `19th century`, `18th century`, `simwolika`, `(Watchers)`, `Mısır'te`, `Mısır'in`, `yanın sever`, `Nile bölge`;
   F2: `yatörensel`, `davânın`, `toplumlarde`, `bu çok o bölge`, `atacalar`, `gündönümünde deki`, `a astronom`, `normale zaman`, `orada a olduğ`, `essaslı`, `Bakırsan`, `kıtasını a`, `Ve somehow`, `tatmak için`, `eşitliğimizi`.
4. **Tekrarlar gitti:** F1 #285≠#286, #633≠#634 artık farklı; F2 #405 "Bu" değil.
5. Bu bir **DOSYA** düzeltmesi — kod/test paketi gerekmez (kod değişmiyor).

---

## 6. KALAN RİSK

- Cue-kayması (GÖREV 1) ve anlam blokları (F2 #405-407, F1 #8-9/#83-84) **yeniden yazıldı**;
  birebir yukarıdaki metinle uygula, serbest yorum katma.
- Ekli Türkçe biçimlerde ünlü uyumuna dikkat (Gözcülere, Gözcüleri).
- Bu brief **net/yüksek-güven** düzeltmeleri kapsar. Her iki dosya baştan sona okundu; listede
  olmayan cue'lara **dokunma** (yanlış "düzeltme" riski). Emin olunmayan satırlar §4'te ayrıca
  "sınırda" olarak işaretlendi.
- **mini ana-model** kaynaklı bu hata sınıfları (garble/kayma/leak) her bölümde YENİ kelimelerle
  tekrar üretilebilir — bkz. [[mini-main-model-quality-2026-07]], [[json-repair-cue-shift-2026-07]].

---

## 7. (OPSİYONEL) Gelecek koşular için kod önerileri — bu brief KAPSAMINDA DEĞİL

Bunlar dosya düzeltmesi değil; ayrı değerlendirilmeli (kullanıcı isterse ayrı görev):
1. `hybrid_translate._LOCAL_FIXES`'e kural: `Gözegçi\w*` → `Gözcü…`, `platosy` → `platosu`,
   `\d+(st|nd|rd|th) century` → Türkçe sıralı yüzyıl. Bu terimler bir daha üretilmez.
2. `has_non_turkish_target_leak` "somehow" gibi tek-kelime İngilizce zarfları kaçırdı (F2 #934).
   Leak sözlüğüne yaygın İngilizce fonksiyon/zarf kelimeleri (somehow, actually, whatever…)
   eklenebilir. Eklenirse `py_compile` + `test_s04e03_holly_odd_guards.py` kalıbında test yaz.
