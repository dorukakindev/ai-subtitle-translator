# Brief: Atlantis & the Annunaki — 4 küçük içerik düzeltmesi (Sonnet 5 için)

Hazırlayan: **Fable 5** (log + dosya doğrulaması, 2026-07-09). Protokol: analiz modeli
belirler, Sonnet uygular. Dosya: `translated/Atlantis & the Annunaki.srt` (1225 cue).
Kaynak: `E:\ALTYAZILAR\Altyazilar\Hulu-Altyazilar\Atlantis & the Annunaki.vtt`.
Uygulamadan önce `.bak` al; cue sayısı/timecode DEĞİŞMEZ.

## Düzeltmeler (hepsi kaynak+ham+final karşılaştırmasıyla doğrulandı)

| # | Cue | Mevcut (yanlış) | YENİ | Neden |
|---|---|---|---|---|
| 1 | #245 | `O, Sagittarius dwarf galaxy.` | `O, Sagittarius cüce galaksisi.` | Yarı-çevrilmemiş satır (yeni R2 garble kuralı yakaladı: 'dwarf'+'galaxy') |
| 2 | #301 | `başka bir gezegenin ayıydı.` | `başka bir gezegenin ayıyla çarpışıyordu.` | **Polish anlam bozdu**: kaynak "colliding with another moon..." (ham DOĞRUYDU, polish "çarpışıyordu" fiilini sildi → "onun ayıydı"ya dönüştü) |
| 3 | #118 | `kendiniz okuyup` | `yükleyip, kendiniz okuyup` | **Polish fiil sildi**: kaynak "drop it into an online translator, and read it" — #117 "çevrimiçi bir çeviriciye" şimdi fiilsiz sarkıyor |
| 4a | #139 | `aslında kökeni Akkadca (Akkadian), Akkadca çivi yazısı` | `aslında kökeni Akkadca, Akkadca çivi yazısıyla yazılmış` | Kaynakta olmayan İngilizce parantez notu |
| 4b | #140 | `(Akkadian cuneiform) bir metin.` | `bir metin.` | Aynı — İngilizce parantez notu (6.2x oran uyarısının gerçek nedeni) |

(#139+#140 birlikte okunuş: "aslında kökeni Akkadca, Akkadca çivi yazısıyla yazılmış / bir metin." ✓)

## DOKUNMA (doğrulanmış yanlış-pozitif / kabul edilebilir)
- **Earth→"Güneş×2" karışık-terim uyarısı**: YANLIŞ-POZİTİF — Earth dosya boyunca tutarlı "Dünya"; iki cue'da (kaynakta hem Earth hem sun geçen satırlar, #816/#830) eşleştirici en yakın büyük-harfli kelimeyi (Güneş) seçmiş. Bilinen sınır durumu, dosyada gerçek sorun yok.
- **#78 (5.2x oran)**: meşru SOV dağıtımı ("said." → uzun Türkçe kuyruk). Dokunma.
- **#996 (🚨 missing_dialogue)**: kaynak "can be--" (yarıda kesilen söz); ham "-–" üretmiş, temizlik düşürmüş. Anlam #997'de zaten var ("hesaplayabilirsiniz"). İSTEĞE BAĞLI: orijinal timestamp'iyle `hesaplanabilir--` içerikli cue geri eklenebilir; eklemezsen de kabul edilebilir (dedektör görevini yaptı, kayıp minimal). Kullanıcı isterse ekle, istemezse atla.
- **chunk_824 (JSON onarımı)**: bölge cue-cue kontrol edildi, hizalama TEMİZ (id-doğrulama çalıştı).

## Doğrulama (uyguladıktan sonra)
1. Cue sayısı 1225 kalmalı (#996 eklenirse 1226 — kullanıcı kararına göre).
2. `ht.find_garble_tokens` #245'in yeni metninde boş dönmeli; dosya genelinde garble taraması 0 olmalı.
3. `(Akkadian` string'i dosyada KALMAMALI.

## Not (kod değil, gelecek adayı — uygulama YOK)
Polish'in #118 ve #301 hasarları aynı deseni paylaşıyor: **tek bir içerik-FİİLİ silinince**
`content_word_loss` guard'ı geçiyor (kaynak verildiğinde eşik ≥2 eksik kelime). Aday
iyileştirme: silinen tek kelime fiil-görünümlüyse (-yor/-di/-mış/-ir/-ecek eki) 1 eksikte de
reddet. Ayrı tur işi; bu brief'te uygulanmayacak.

---

# TUR 2 — Örneklemeli anlam okuması bulguları (Fable 5, 2026-07-09)

İlk 5 düzeltme UYGULANDI (Sonnet, doğrulandı). Ardından 4 pencere yakın okundu
(#1-70, #280-360, #600-660, #1165-1225 ≈ %22): genel kalite İYİ — bağlam anlaşılmış,
akış doğal, konuşmacı üslubu korunmuş. Ama yakın okuma, guard'ların GÖREMEYECEĞİ
şu gerçek sorunları buldu. Sonnet için (yine `.bak` üzerine devam; cue sayısı 1225 sabit):

| # | Cue | Mevcut (yanlış) | YENİ | Neden |
|---|---|---|---|---|
| 6a | #609 | `nereye giderseniz gidin, bulamayacaksınız` | `nereye giderseniz gidin,` | **NEGASYON TERS DÖNMÜŞ** — kaynak "you're going to FIND" (olumlu!) |
| 6b | #610 | `benzer yapılar.` | `benzer yapılar bulacaksınız.` | 6a'nın devamı (fiil buraya taşınır, akış düzelir) |
| 7a | #61 | `ve bence Zecharia Sitchin'i (araştırmacı yazar) de duymuştur;` | `ve bence Zecharia Sitchin'i de duymuştur;` | Kaynakta olmayan parantez çevirmen notu |
| 7b | #62 | `bence Zecharia Sitchin (araştırmacı yazar), gelmiş geçmiş` | `bence Zecharia Sitchin, gelmiş geçmiş` | Aynı notun tekrarı |
| 8 | #292, #293, #298, #336 | `anomallikleri` / `anomalliğin` / `anomallikler` | `anomalileri` / `anomalinin` / `anomaliler` | "anomallik" standart değil; dosyanın geri kalanı "anomali" kullanıyor (#339, #1168) — tutarlılık |
| 9 | #1183 | `Mars'ta Kafkasyalı yüzler görüyorsunuz.` | `Mars'ta beyaz tenli yüzler görüyorsunuz.` | "Caucasian" = beyaz ırk; "Kafkasyalı" coğrafi anlam, yanlış |
| 10 | #1218 | `hangi bölüm olduğunu emin değilim` | `hangi bölüm olduğundan emin değilim` | Hâl eki hatası |

Uygulama notu 8 için: #292 `anomallikleri`→`anomalileri`, #293 `anomalliğin`→`anomalinin`,
#298 `anomallikler`→`anomaliler`, #336 `anomallikler`→`anomaliler` (tam satırları Grep ile
id'den bul; başka `anomallik` geçişi olursa onları da aynı şekilde düzelt).

Doğrulama: cue sayısı 1225; `bulamayacaksınız` ve `(araştırmacı yazar` ve `anomallik`
ve `Kafkasyalı` string'leri dosyada KALMAMALI.

## Yeni gözlemlenen guard açığı (gelecek adayı, uygulama YOK)
#609 sınıfı: kaynak OLUMLU iken çeviriye olumsuzluk EKLENMESİ hiçbir guard'da yok —
`_source_negation_requires_turkish_negation` yalnız ters yönü kontrol ediyor. Aday:
simetrik kontrol (kaynakta not/never/no yokken çeviride -ma/-me/değil/asla belirirse
critic'e işaretle). Yanlış-pozitif riski yüksek (Türkçe'de retorik olumsuzluk meşru
olabilir) — dikkatli tasarım ister, ayrı tur.
