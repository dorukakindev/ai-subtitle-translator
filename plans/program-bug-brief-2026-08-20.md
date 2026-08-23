# Program tarafı — ikinci parti bulgular (2026-08-20)

Birinci brief (`program-bug-brief-2026-08-19.md`) uygulandı. Bu dosya, o brief yazıldıktan
sonra okunan dosyalardan çıkan **yeni** sınıfları içerir:

- Connections S01E08 / E09 / E10 (2.803 cue, kaynak İngilizce)
- The Witch Doctor Will See You Now S01E01 (759 cue, kaynak **Portekizce**)
- Death Scenes (1989) / 1992 / 3 (1993) — 20260819-233519 koşusunun çıktısı (1.467 cue)

Öncelik sırasına konmuştur. Her madde için somut dosya + cue numarası verilmiştir.

---

## P0-A — Cue çifti içinde metin dengesizliği (okunamaz satır)

**En ciddi yeni bulgu. Sistematik, ölçülebilir ve otomatik yakalanabilir.**

İngilizce kaynak bir cümleyi öyle böler ki devam cue'su tek kelimedir
(`elements.`, `news.`, `form of mayhem.`). Türkçe söz dizimi yüklemi sona attığı için
çeviri, cümlenin tamamını o minik cue'ya yığıyor.

Ölçülen en kötü örnek — `Death Scenes 1992 - YouTube.srt`:

| cue | süre | kaynak | çeviri | okuma hızı |
|---|---|---|---|---|
| #368 | 7,0 sn | 150 kar | 47 kar | 7 kar/sn |
| #369 | **0,4 sn** | 9 kar (`elements.`) | **122 kar** | **305 kar/sn** |
| #483 | 7,0 sn | 155 kar | 93 kar | 13 kar/sn |
| #484 | **0,4 sn** | 5 kar (`news.`) | 61 kar | **161 kar/sn** |

Aynı desenden **23 cue çifti** buldum: Death Scenes 1989'da 15, 1992'de 8.
Hepsinde önceki cue 5–7 saniye ve 7–20 kar/sn ile **boş duruyor**; yani metni
zaman damgasına dokunmadan geri taşımak mümkün (ben elle böyle düzelttim).

**Mevcut uyarılar bunu yakalamıyor:**
- `CPS uyarısı` satır sayıyor ama düzeltilebilir alt kümeyi göstermiyor
  (1989'da 51, 1992'de 42 satır uyarısı verdi; hangi 23'ünün komşusunda yer olduğunu söylemedi).
- `anormal uzunluk oranı` TR/EN karakter oranına bakıyor; 23 vakanın yalnızca 4'ünü işaretledi
  (#17, #439, #480, #483).

**Önerilen detektör** — üç koşul birden:
1. cue'nun okuma hızı > 30 kar/sn,
2. çeviri uzunluğu, kaynak cue uzunluğunun 2,2 katından fazla,
3. **bir önceki cue'nun okuma hızı < 20 kar/sn** (yani yer var).

Bu üçlü, 23 vakanın hepsini yakalıyor, temiz cue'larda yanlış alarm vermiyor
(Death Scenes 3'te sıfır bulgu; oradaki hızlı satırlar kaynağın kendisi yüzünden hızlı).

Otomatik onarım riskli (cümleyi bölmek gerekiyor), **raporlamak yeterli**:
"#369 (0,4 sn / 122 kar) — metni #368'e kaydırın" gibi.

## P0-B — Yeni içerik-kayması detektörü bu desende yanlış pozitif veriyor

Brief'te istediğim `content_offset` detektörü şimdi çalışıyor ve bu koşuda
`Death Scenes 1992 - YouTube.srt` **#370**'i 🚨 ile işaretledi. Kaynakla karşılaştırdım:
**gerçek kayma yok.** Detektörü tetikleyen şey tam olarak P0-A'daki yeniden dağıtım —
#368'in içeriği #369'a taşındığı için jetonlar bir cue kaymış görünüyor.

**Öneri:** kayma bölgesi 1–2 cue uzunluğundaysa ve komşu çift bir cümle devamıysa
(önceki cue noktalama ile bitmiyor), `content_offset` yerine **cue-fill** sınıfına düşür.
Yoksa her uzun cümle bölünmesinde 🚨 çıkacak ve uyarı güvenilirliğini yitirecek.

## P0-C — Dosya içinde sen/siz kayması (denetlenmiyor)

`BBC.Connections.S01E10` dosyanın ilk yarısında "siz", ortasından itibaren "sen"
kullanıyordu — **120 cue**. Anlatıcı aynı kişi, muhatap aynı (izleyici).
E01–E09'un tamamı "siz". Yani tek dosya kendi içinde ve seriyle tutarsız.

Hitap haritası aşaması var (log'da `Hitap haritası: {...}` görünüyor) ama
**yazılan dosya üzerinde tutarlılık kontrolü yok.**

**Önerilen kontrol:** nihai dosyada 2. tekil işaretçilerini (`-sın/-sin/-sun/-sün`,
`-san/-sen`, `sana/seni/senin`, `-dın/-din`) ve 2. çoğul işaretçilerini say.
İkisi de eşiği (ör. %10) aşıyorsa uyar. Ucuz, ve gözle çok belli olan bir kusuru yakalıyor.
Not: `-ın/-in` ve `-atın/-yapın` gibi emir kipleri yanlış pozitif üretir, onları dışla.

## P0-D — Kaynak dili kalıntısı, Türkçe ekli

Portekizce kaynaklı `The.Witch.Doctor...S01E01` şunlarla teslim edilmişti:

| cue | çeviri | olması gereken |
|---|---|---|
| #603 | **Ocidente'de** acıya verdiğimiz tepki | Batı'da |
| #607 | **China'daki** şifalı ilaçlar | Çin'deki |
| #644 | anakaradaki **China'da** da | anakara Çin'de de |
| #620, 621, 642, 645 | **Mr.** Yi | Bay Yi |
| #50, 65, 94 | **Miss** Xiao | Bayan Xiao |
| #672, 680, 694 | **Professor** Sun | Profesör Sun |

`Death Scenes 3 (1993)` #46: `Sawdust Caesar` (Mussolini'nin lakabı, "Talaştan Sezar").

`find_garble_tokens` bunları kaçırıyor çünkü hepsi **düzgün yazılmış yabancı kelimeler**.

**Yüksek güvenli sinyal:** kaynak cue'da birebir geçen bir kelimenin, çeviride
**Türkçe çekim eki** taşıması (`Ocidente'de`, `China'daki`). Bu neredeyse hiç yanlış
pozitif vermez — özel adlar zaten ek alır ama onlar kaynakta da özel addır ve
kilitli sözlükte bulunur. Ek olarak sabit bir unvan listesi
(`Mr./Mrs./Miss/Ms./Dr./Prof./Professor/Monsieur/Madame/Señor`) doğrudan normalize edilebilir.

---

## P1-E — Numaralandırma ve etiket önekleri düşüyor

- `Connections E10` #869 `One: do nothing.` → "hiçbir şey yapmamak." (**"Bir:" yok**)
- `Connections E10` #872 `Two: do what people have done...` → "makineler istemedikleri..." (**"İki:" yok**)
- `Connections E09` #473 `Problem: not enough electricity.` → "yeterli elektrik yok." (**"Sorun:" yok**)
- `Connections E09` #474 `Solution: professor...` → "Belçikalı Profesör..." (**"Çözüm:" yok**)

E09'daki bu bölüm bir "sorun/çözüm" listesi olarak kurgulanmış; öneklerin düşmesi
listenin yapısını görünmez kılıyor. Sistem istemine tek satır kural yeter:
*"Satır başındaki numaralandırma/etiket öneklerini (One:, Two:, Problem:, Solution:, a), b)) koru."*

## P1-F — Komşu cue'da yankı (kısmi tekrar)

`adjacent_duplicate` birebir aynı cue'yu yakalıyor ama **kısmi yankıyı** yakalamıyor:

- `Witch Doctor E01` #524 "Yetişkinlik hayatım boyunca hiç böyle olduğunu hatırlamıyorum" / #525 "böyle olduğunu hatırlamıyorum." — **son beş kelime birebir tekrar**
- `Connections E10` #643 "Yirmi yıl dayanacak bir araba yapıp..." / #644 "...neden yirmi yıl dayanacak bir araba yapamıyoruz?" — aynı öbek iki kez
- `Connections E09` #257 "haritalar son derece yetersizdi" / #258 "hatta haritalarla alay ediliyordu" — ikincisi kaynakta yok, uydurma
- `Connections E10` #413/#414 "fırsat verince" / "fırsat verince"

**Detektör:** komşu iki cue arasında jeton örtüşme oranı > 0,6 **ve** kaynak cue'larında
aynı örtüşme yoksa işaretle. (Kaynak zaten tekrar ediyorsa — röportajda tekrarlanan
soru gibi — susmalı; `Death Scenes 1992` #347/#348 tam böyle bir meşru tekrar.)

## P1-G — Tek harflik/tek heceli kelime karışmaları

Sözlükte olmayan, gözle çok belli, `find_garble_tokens`'ın kaçırdığı sınıf:

| dosya | cue | yazılan | olması gereken |
|---|---|---|---|
| Connections E10 | #317, #319 | **organ** borusu / **organ** yapımcısı | org (çalgı) |
| Death Scenes 3 | #191 | pankreas ve **dalgayı** | dalağı |
| Witch Doctor E01 | #296 | tadını alabildiğim **tak** şeyler | tek |
| Connections E09 | #54 | 15. yüzyıl Avrupası, **neneredeyse** | neredeyse |
| Connections E09 | #372 | yeni bir aydınlatma **türününün** | türünün |
| Witch Doctor E01 | #664 | **badanın** herhangi bir yerini | bedenin |
| Witch Doctor E01 | #465 | bir **tıbbiyi** anlamakta | tıbbı |

Bunların çoğu bir Türkçe yazım denetimi geçişiyle yakalanır (`neneredeyse`, `türününün`,
`badanın`, `tıbbiyi` sözlükte yok). `organ`/`dalga`/`tak` geçerli kelimeler olduğu için
ancak bağlamla yakalanır — düşük öncelik.

## P1-H — Yüklemi tamamen kaybolan cue

- `Death Scenes 3` #80: `Efforts to control the huge crowd and permit the death car to proceed to a hospital are unsuccessful.`
  → "Kalabalığı denetleyip ölüm arabasının hastaneye gitmesine" — **yüklem yok, cümle bitiyor.**
- `Connections E09` #439–441: perilerin `came to grief` yüklemi hiç çevrilmemiş,
  Türkçe cümlede özne var yüklem yok.

**Detektör:** cue, ismin -e/-i/-de hâliyle ya da mastarla bitiyor **ve** sonraki cue
büyük harfle yeni cümle başlatıyorsa (küçük harfli devam değil) işaretle.

## P1-I — Tipografik kesme/tırnak hâlâ çıktıya yazılıyor

Brief'teki P1-7 uygulanmış olmasına rağmen bu koşunun (20260819-233519) üç çıktısında
toplam **59 tipografik karakter** vardı: Death Scenes 1989'da 27, 1992'de 19, 1993'te 13
(`Mussolini’yi`, `1934’te`, `Aleksandar’ı`). Aynı dosyada hem `'` hem `’` kullanılmış.
Ya bu koşu düzeltmeden önce başladı ya da normalize bu akışa bağlanmadı — kontrol edilmeli.

## P1-J — Ortak isimlerde kesme işareti

`Death Scenes 3`: `lamina'yı` (#259), `Dura'sı` (#264), `symphysis pubis'e` (#112).
Kesme işareti yalnız özel adlarda kullanılır. Latince terimler de çekim ekini
kesmesiz alır (`laminayı`, `durası`, `pubis simfizine`).

---

## P1-10 hakkında (önceki brief'teki terim kayması maddesi)

Diğer chatin tespiti doğru: `_normalize_mixed_terms` kapalı değil ve zaten sözlüğe çapalı.
Bu oturumdaki bulgular da bunu doğruluyor — kaçan terimlerin **hiçbiri sözlükte değildi**:

- `Witch Doctor E01`: `Dr. Lee` / `Doktor Lee`, `sırt ağrısı` / `bel ağrısı`, `Dr. Phung` / `Doktor Phung`
- `Death Scenes 1989`: `Dalya` / `Dahlia` (sözlükte yalnız `Black Dahlia` var, çıplak `Dahlia` yok)
- `Death Scenes 3`: `Barthou` / `Bartu`, `Aleksandar` / `Alexander`, `omurilik` / `kord`

Yani iş kodda değil **sözlüğün kapsamında**. Öneri: analiz aşaması sözlüğü kurarken,
model ne söylerse söylesin, dosyada **3+ kez geçen büyük harfli özel adları** ve
kaynak metinde 3+ kez geçen alan terimlerini otomatik olarak kilitli sözlüğe eklesin.
`Barthou`, `Dahlia`, `Lee` bu kuralla girer ve normalize onları da toparlar.

---

## Doğru çalışıyor — bozulmasın

- Portekizce çevirmen kredisi (`Tradução e Legendagem / Joana Barata / MOVIOLA`)
  dört Witch Doctor bölümünün dördünde de doğru silinmiş.
- Kaynak yazım hatalarının doğru okunması: `petikii` → `peteşi`, `renal pulvis` → `renal pelvis`,
  `formal infixation` → `formalinle tespit`, `it is averted` → `ters çevrilir`,
  `cella tersica` → `sella turcica`, `chicken pops` → `tavuk parçaları`.
  Bu, mini'de görmediğim bir kalite; gpt-5.4 kaynağın bozuk olduğunu anlayıp doğrusunu yazıyor.
- SDH kapsamı: Connections E08'de 16, E09'da 5, E10'da 9 eksik cue'nun **tamamı** saf SDH'ti.
  Tek bir içerik cue'su yanlışlıkla silinmemişti.
- Küfür/argo sansürsüz geçiyor (`Pat, pat, pat, kara götüne, kaltak.`) — istenen davranış.
- Zaman damgaları kaynakla birebir; üç filmde ve on Connections bölümünde tek sapma yok.

## Kasıtlı davranış — hata sanılmasın

- CPS uyarısı verilip condense uygulanmaması **doğru**. P0-A'nın çözümü condense değil,
  metni komşu cue'ya taşımak; bunlar farklı işler.
- Sahne Planı aşamasındaki %47,8 hata oranı SHUAI sağlayıcı kaynaklı (bağlantı hatası),
  kod hatası değil. Yeniden deneme düzeni çalıştı ve 8. denemede geçti.
