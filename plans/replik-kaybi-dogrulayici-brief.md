# Brief — Kaynaktaki repliğin teslimde düşmesi (`MISSING_REPLICA`)

Tarih: 2026-08-29 · Hazırlayan: Opus (denetim) · Uygulayacak: Sonnet 5
Ölçüm tabanı: yüklenmiş 23 film, 29.854 cue, kaynak + teslim yan yana

---

## 1. Karar özeti

| | |
|---|---|
| **Eklenecek** | `MISSING_REPLICA` — kaynakta 2+ tireli replik var, teslimde daha az |
| **EKLENMEYECEK** | `NAME_LOSS` — ölçüldü, **reddedildi** (aşağıda) |
| Ölçülen kesinlik | 4 bulgu / 4'ü de gerçek = **%100**, 23 dosyada |
| Şu anki durum | Bu sınıf programda **hiçbir doğrulayıcı tarafından görülmüyor** |

---

## 2. Önce: kendi önerimi geri çekiyorum (`NAME_LOSS`)

Bir önceki oturumda "kaynaktaki özel ad çeviride yoksa işaretle" diye öneri
yapmıştım. Gerçek 23 teslime karşı üç sürüm yazıp ölçtüm:

| sürüm | kural | bulgu | örneklenen | gerçek | kesinlik |
|---|---|---|---|---|---|
| v1 | cümle-içi büyük harfli sözcük | 3.349 | 24 | 0 | ~%0 |
| v2 | + hiç küçük harfle geçmeyen, unvan/milliyet/akrabalık elenmiş | 722 | 23 | 1 | **%4** |
| v3 | + kısaltma eleme + cümle-içi kanıt şartı | 345 | 40 | 1 | **%2,5** |

**Kök neden — kural daraltmakla düzelmez:** Türkçe altyazıda kaynaktaki özel
adın cins isme ya da egzonime dönüşmesi *doğru davranıştır*. Ölçümde yanlış
alarm üreten gerçek örnekler:

```
Denmark   -> Danimarka       Chevalier -> Şövalye        Jesus  -> İsa
Germany   -> Almanya         Ambassador-> Büyükelçi      Christ -> Kahretsin
Tchaikovsky -> Çaykovski     Santa Claus -> Noel Baba    Yankee -> Amerikalı
Monsieur  -> mösyö           Venice    -> Venedik        Mommy  -> anne
```

"Ad yerinde çevrildi" ile "ad düştü" arasını mekanik olarak ayırmanın ucuz bir
yolu yok. Bu sınıf [[anlamsal-kusur-taranamaz-2026-08-26]] ile aynı kategoride.
**Yazılmasın.**

Ama ölçüm boşa gitmedi: v2/v3'ün bulduğu 2 gerçek bulgunun ikisi de aslında
*ad kaybı değil, replik/cümle kaybıydı*. Ad yalnızca semptomdu. Asıl sınıf bu.

---

## 3. Eklenecek doğrulayıcı

### 3.1 Kural

Bir cue için:

1. Kaynak metni satırlara böl.
2. Bir satır **replik** sayılır: `-`, `–` veya `—` ile başlıyorsa **ve**
   tamamı SDH değilse. SDH satırı = kırpıldığında `-`/`–`/`—` dışında yalnız
   `( ... )` veya `[ ... ]` içeren satır.
   (Bu eleme şart: onsuz 22 aday çıkıyor, 18'i doğru silinmiş SDH.)
3. Teslim metni için aynı sayımı yap.
4. `kaynak_replik >= 2` ve `teslim_replik < kaynak_replik` ise
   → `MISSING_REPLICA`.

### 3.2 Referans uygulama

```python
_SDH_ONLY_LINE = re.compile(r"^\s*[-\u2013\u2014]?\s*[\(\[].*[\)\]]\s*$")

def _replica_count(text: str) -> int:
    """SDH olmayan, tire ile başlayan konuşmacı satırlarının sayısı."""
    n = 0
    for line in str(text or "").split("\n"):
        s = line.strip()
        if not s.startswith(("-", "\u2013", "\u2014")):
            continue
        if _SDH_ONLY_LINE.match(s):
            continue
        n += 1
    return n


def _missing_replica(src_text: str, tr_text: str) -> bool:
    """Kaynakta iki+ replik varken teslimde daha azı kaldıysa True."""
    src_n = _replica_count(src_text)
    if src_n < 2:
        return False
    return _replica_count(tr_text) < src_n
```

### 3.3 Bağlanacağı yer

`hybrid_translate.run_validators` içine, `NUMBER_MISMATCH` üretilen bloğun
yanına:

```python
if _missing_replica(src_text, tr_text):
    reasons.append("MISSING_REPLICA")
```

ve reason kodunu mevcut listeye ekle (`hybrid_translate.py` ~9236 civarındaki
sabit demet — `NUMBER_MISMATCH`, `LENGTH_RATIO_OUTLIER` vb. ile aynı yer).

**Kip:** Critic Pass 2026-08-16'dan beri *yalnız-rapor*. Bu doğrulayıcı da
**otomatik düzeltme yapmasın**, yalnız reason üretsin — bkz.
[[critic-pass-rapor-modu-2026-08]]. Düşen repliği yeniden yazmak model işi;
karar insanda kalmalı.

---

## 4. Kabul ölçütleri

### 4.1 Yakalaması ZORUNLU (gerçek teslimden, elle doğrulanmış)

Hepsi `The Reckoning (Gold, Jack 1970)`:

| cue | kaynak | teslim | düşen |
|---|---|---|---|
| #18 | `- They're after Hazlitt's guts.`<br>`- I didn't know he had any.` | `Onda öyle bir şey olduğunu bilmiyordum.` | 1. replik |
| #122 | `- Mrs Marler phoned.`<br>`- Well, call her back, then.` | `- Bayan Marler aradı.` | 2. replik |
| #149 | `- You've come home.`<br>`- And not before time, neither.` | `- Hem de vakti geçmişken.` | 1. replik |
| #154 | `- He'll not be long with us.`<br>`- Don't be ridiculous, Ma.` | `- Bizimle uzun kalmayacak.` | 2. replik |

### 4.2 Yakalamaması ZORUNLU (doğru silinmiş SDH — yanlış alarm olmamalı)

```
EN: - (Gun pops, cat shrieks)      EN: -[laughs]                EN: - Glass coffins.
    - Death to Debussy!                - When you coming down?      -[laughs]
TR: - Debussy'ye ölüm!             TR: Ne zaman iniyorsun?      TR: - Cam tabutlar.
```

### 4.3 Bütün-korpus ölçütü

23 teslim dosyasında toplam bulgu **tam olarak 4** olmalı (hepsi film 7).
Bu sayı artıyorsa SDH eleme kuralı bozulmuştur.

---

## 5. Neden gerekli — mevcut doğrulayıcılar bunu görmüyor

Beş gerçek kayıp, mevcut `_length_ratio_outlier` ile denendi:

```
f7 #18   LENGTH_RATIO_OUTLIER = False
f7 #93   LENGTH_RATIO_OUTLIER = False
f7 #122  LENGTH_RATIO_OUTLIER = False
f7 #149  LENGTH_RATIO_OUTLIER = False
f7 #154  LENGTH_RATIO_OUTLIER = False
```

`_numeric_token_mismatch` de görmüyor (sayı yok). Yani tam bir replik
düşse bile teslim şu an sessizce geçiyor.

---

## 6. Kapsam dışı (bilerek)

- **Tek konuşmacılı cümle kaybı.** f7 #93'te (`Michael, why aren't we selling
  our larger machines?` → yalnız ikinci cümle çevrilmiş) tire yok, bu kural
  görmüyor. Uzunluk oranı da görmüyor. Bu sınıf için ucuz sinyal bulunamadı;
  ayrı bir çalışma konusu, bu brief'e dahil değil.
- **Düşen repliği otomatik yeniden yazmak.** Yalnız rapor.
- **Geriye dönük onarım.** Doğrulayıcı bundan sonraki koşularda çalışır;
  yüklenmiş 23 dosyadaki 4 cue ayrıca elle onarılacak.
