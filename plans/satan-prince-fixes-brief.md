# Brief: "Satan - Prince Of Darkness" — leak + tutarlılık düzeltmeleri (Sonnet 5)

Hazırlayan: **Opus 4.8** (log incelemesi + kaynak/çıktı/ham karşılaştırması + Python dry-run
doğrulaması, 2026-07-10). Protokol: Opus karar verir + brief yazar, Sonnet uygular.

- **Hedef:** `C:\Users\K\Downloads\ÇIKTI\Satan - Prince Of Darkness.en.srt`
- **Kaynak:** `E:\ALTYAZILAR\Altyazilar\Hulu-Altyazilar\Satan - Prince Of Darkness.en.srt`
- **Önce `.bak` al.** Çıktı hâlihazırda **388 cue** (kaynak 389; #391 `[theme music]` SFX-only,
  kasıtlı SDH düşüşü — benign). Düzeltmeler **yalnız metin**; cue sayısı **388 kalmalı,
  timecode DEĞİŞMEZ**.

## Özet: ne bulundu
gpt-5.4-mini çevirisi 3 sınıf gerçek hata bıraktı; hepsi doğrulandı:
1. **#327 içerik kaybı** — JSON kırılması kalıntısı "Halk a" (0.08x uzunluk uyarısı bunu
   yakaladı ama otomatik onarım fragment'i "dolu" sayıp atladı).
2. **`Satan` → `Şeytan` tutarsızlığı** — belgeselin BAŞ terimi 37 cue'da İngilizce bırakılmış
   (dosyada Şeytan×72 / Satan×39 karışık). "Satanist/Satanizm" meşru, hariç.
3. **`Jesus` → `İsa` leak** — 16 cue "Jesus" bırakmış (Türkçe'de her zaman "İsa").
   Ek küçük leak'ler: **#307 `Science`→`Bilim`**, **#32/#33 `Michael`→`Mikail`** (doküman
   Havva/Yahuda/Eyüp/Roma'yı çevirmiş; tutarlılık için Mikail).

**Python dry-run** tüm dönüşümü simüle etti: 56 cue değişiyor, sonrası temiz — kalan "Satan"
substring=2 (yalnız Satanist+Satanizm), Jesus=0, Science=0, Michael=0, hiçbir bozuk artifact
yok (`İsa'ın`/`İsa'ı`/`İsa'a` = 0). Küçük harf "satanik" (#291, sıfat) DOKUNULMUYOR.

---

## A) #327 — kesik cue, yeniden çevir (KRİTİK)
Kaynak #327: *"The folklore also tells us that there is one sure way to get rid of Satan,"*
(devamı #328'de: *"and that is to laugh at him..."* — #328 zaten doğru, DOKUNMA).

Mevcut (tek satır): `Halk a`
YENİ (2 satır):
```
Folklor ayrıca Şeytan'dan kurtulmanın
kesin bir yolu olduğunu söyler,
```
(Sonundaki virgül bilinçli — #328'in "ve ona gülmek... demektir" cümlesine akıyor, kaynağın
"...get rid of Satan, and that is..." yapısına birebir paralel.)

## B) `Satan` → `Şeytan` (blanket, en güvenli yol)
`Satan` → `Şeytan` **case-sensitive** olduğu için yalnız büyük-S geçişlerini vurur; "Satan"
gövdenin İLK 5 harfi, tüm ekler (`'ın`/`'ı`/`'a`, düz veya kıvrık apostrof) sonrasında gelir ve
DEĞİŞMEDEN korunur (Şeytan da -an ile bittiği için ünlü uyumu birebir aynı). Uygula:

1. `Edit` **replace_all**: `Satan` → `Şeytan`  (41 substring vurur)
2. `Edit` **replace_all**: `Şeytanist` → `Satanist`  (#356 geri al — meşru Türkçe)
3. `Edit` **replace_all**: `Şeytanizm` → `Satanizm`  (#357 geri al — meşru Türkçe)

Sonuç: 39 şeytan-adı geçişi düzelir, 2 türev kelime korunur. (#358 ritüel çağrısı da
"Şeytan, Lucifer" olur — istenen; **Lucifer İngilizce kalır**, o doğru.)

Etkilenen şeytan cue'ları (doğrulama için): 24, 30, 32, 35, 36, 37, 38, 40, 48, 56, 65, 67,
71, 75, 78, 79, 82, 88, 91, 190, 198, 208, 213, 215, 217, 234, 236, 242, 245, 246, 248, 273,
277, 278, 307, 314, 317, 323, 358.

## C) `Jesus` → `İsa` (SIRA ÖNEMLİ — ekli olanlar önce)
"İsa" ünlüyle bittiği için ekler tampon harf alır; bare "Jesus"u en sona bırak yoksa
`Jesus'ın` içindeki "Jesus"u bozarsın. Şu SIRAYLA `Edit` **replace_all**:

1. `Jesus'ın` → `İsa'nın`   (2×: #126, #152 — düz apostrof U+0027)
2. `Jesus'ı`  → `İsa'yı`    (4×: #127, #131, #134, #147 — düz apostrof)
3. `Jesus'a`  → `İsa'ya`    (1×: #146 — düz apostrof U+0027)
4. `Jesus’a`  → `İsa’ya`    (1×: #167 — **kıvrık apostrof U+2019**, ayrı string)
5. `Jesus`    → `İsa`       (kalan 8×: #130,133,137,139,148,149,154,168 — nominatif)

Toplam 16 geçiş. (3 ve 4 aynı görünür ama apostrof kod-noktası farklı — ikisini de yaz.)

## D) Tekil leak'ler
- **#307**: `Science çağı` → `Bilim çağı`  (Satan→Şeytan zaten B'de hallolur → "Bilim çağı
  geliştikçe, Şeytan'ın itibarı...").
- **#32**: `Michael'a` → `Mikail'e`  (dativ ünlü uyumu: Mikail ön-ünlü → -e).
- **#33**: `Michael` → `Mikail`.
  (Michael'ı ikincil-öncelik say; standart Türkçe "başmelek Mikail" ve doküman diğer İncil
  adlarını çeviriyor — uygulanması önerilir.)

---

## DOKUNMA (doğrulanmış yanlış-pozitif / benign)
- **#227 "Dr. Faustus, 1604."** — özel isim + yıl, çevrilmemiş görünür ama DOĞRU. FP.
- **Book kümesi** (Kutsal×2/Eyüp×2 uyarısı): "Vahiy Kitabı", "Eyüp Kitabı", "Kutsal Kitap"ın
  hepsi doğru — küme ayırıcı "Kitap" eklerini bölmüş. FP.
- **Christ** uyarısı: FIN'de bare "Christ" yok, hepsi "Mesih". FP.
- **#245/#246 "conventicles"/"sabbaths"** — tırnak içinde bırakılmış tarihsel teknik terimler;
  meşru bir tercih, gerekmiyor. (Opsiyonel: "gizli ibadet meclisleri"/"şabatlar" yapılabilir.)
- **CPS uyarıları** (8 satır >24 kar/sn) — okuma-hızı/zamanlama uyarısı, çeviri hatası DEĞİL;
  condense kapalı. Bu turda kapsam DIŞI.
- **#391 [theme music]** — SFX-only, kasıtlı düşüş. FP.

## Doğrulama (uyguladıktan sonra)
1. Cue sayısı **388**, timecode değişmez (`.bak` ile karşılaştır).
2. Değişen cue kümesi TAM olarak şu 57 olmalı: A'daki #327 + B/C/D'nin 56'sı
   (24,30,32,33,35,36,37,38,40,48,56,65,67,71,75,78,79,82,88,91,126,127,130,131,133,134,137,
   139,146,147,148,149,152,154,167,168,190,198,208,213,215,217,234,236,242,245,246,248,273,
   277,278,307,314,317,323,358). Fazla/eksik değişiklik OLMAMALI.
3. Tüm dosyada: `Satan` substring = **2** (yalnız Satanist+Satanizm), `Jesus` = **0**,
   `Science` = **0**, `Michael` = **0**. Bozuk artifact (`İsa'ın`,`İsa'ı`,`İsa'a`) = **0**.
4. `ht.find_garble_tokens` tüm dosyada 0.
5. `#327` artık "Halk a" değil; anormal-uzunluk (0.08x) uyarısı kalmamalı.

## Kod-gözlemi (uygulama YOK — ayrı tur adayı)
#327, JSON-truncation'ın boş DEĞİL ama çok kısa+kelime-ortası-kesik ("Halk a") bir fragment
üretmesiyle oluştu. `_repair_untranslated_sync` fragment dolu olduğu için atladı; yalnız
post-write scan "0.08x anormal uzunluk" ile UYARDI ama otomatik onarmadı. Aday: çeviri/kaynak
uzunluk oranı < ~0.25 VE kelime-ortası biten cue'lar `_retry_hata`'da otomatik yeniden-deneme
tetiklesin (yalnız boş/[HATA] değil). Yüksek-değerli, düşük-FP bir guard — ama ayrı brief.
