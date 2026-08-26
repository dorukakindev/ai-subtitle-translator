# SDH kapsam haritası — 2026-08-26

Beş aşamalı derin ölçüm. Bugüne kadar SDH sözlüğünde üç boşluk **tek tek**
bulunmuştu (Türkçe etiketler, salt-nota gruplar, genel dil ifadeleri); bu
çalışma bütününü ölçtü.

Ölçüm tabanı: **290 gerçek kaynak, 215.918 cue.**

---

## Aşama 1 — Sözlüğün ölü girdileri

`_DELIVERY_BARE_ENGLISH_SDH_RE`, 130 dal (Codex tur-3 ateşleme tablosu):

- 601 cue eşleşti, 629 dal ateşlemesi
- **Hiç ateşlemeyen dal: 6/130** (42, 43, 44, 48, 60, 128)

Sözlük büyük ölçüde canlı. **Ölü kural bir sorun değil** — asıl soru kapsam.

---

## Aşama 2-3 — Kapsam (recall), her sınıf KENDİ ölçütüyle

Aday kümesi koddan bağımsız, yalnız **biçime** göre kuruldu; sonra her
sınıf doğru ölçütle sınandı. İlk denemede konuşmacı etiketi sınıfını yanlış
ölçüt ile (cue silinmeli) ölçüp `%0` bulmuştum — oysa doğru davranış cue'yu
silmek değil **öneki soymak**.

| biçim sınıfı | doğru ölçüt | sonuç |
|---|---|---|
| tamamı parantez | cue düşmeli | **%98,9** (2459/2486) |
| konuşmacı etiketi | önek soyulmalı | **%98,9** (960/971) |
| nota + söz | korunmalı | 205 korundu, 2 düştü |
| çıplak CAPS (karışık dosya, Latin) | cue düşmeli | %76,0 (590/776) |

---

## Aşama 4 — Kaçanların sınıflandırması

Çıplak CAPS sınıfındaki 80 gerçek kaçak elle sınıflandırıldı:

| sınıf | cue | doğru davranış |
|---|---|---|
| yabancı ekran yazısı (`CONSULTA COM O CURANDEIRO`, `DE LAATSTE MACHINE`) | ~18 | çevrilmeli ✓ |
| caps yazılmış gerçek replik | ~15 | korunmalı ✓ |
| gerçek ses etiketi | ~20 | silinmeli |
| kaçan konuşmacı öneki | 3 | soyulmalı |

**Ama "gerçek ses etiketi" boşluğu ölçüldüğünde YANILSAMA çıktı.**
`GARBLED VOICES`, `ELECTRONIC MUSIC`, `GROANS OF PAIN`, `MUSICIANS PLAY`,
`HIGH-PITCHED BUZZING` — hepsi `allow_caps_heuristic=True` ile **zaten**
yakalanıyor, ki çağıran karışık-harfli dosyalarda onu açıyor. Ben ölçümü
yanlış yordamla (`src_is_sfx_only(t)`, bayraksız) yaptığım için kaçıyor
sandım.

Kalan gerçek kazanç: **2 cue** — parantezli küçük harfli etiketler
(`[ transmitter tuning and static ]`, `[ Air Hissing ]`). Ses sözcüğü
dağarcığı o kadarla genişletildi.

### `TRANSLATOR:` öneki — BİLİNÇLİ, dokunulmadı

`_src_has_plain_speaker_label` içinde açık bir dışlama var:

```python
if label.casefold() in {"translation", "translator"}:
    return False
```

Gerekçesi `tests/test_delivery_audit_gaps_20260822.py:284` ile kilitli:
`TRANSLATOR:` iki anlamlı — altyazı künyesi (`Çevirmen: Ahmet Yılmaz`,
silinir) ya da tercümanın seslendirdiği **gerçek replik**
(`TRANSLATOR: 'My role was such...'`, korunur). Dışlama ikincisini
silinmekten koruyor. 7 cue için bu korumayla dövüşülmedi.

---

## Aşama 5 — Sonuç

**SDH sözlüğü sağlam.** İki büyük sınıfta kapsam %98,9; kaçanların çoğu
zaten doğru davranış (yabancı ekran yazısı çevrilmeli, caps replik
korunmalı). Bu alanda tek tek bulunan üç boşluk kapandıktan sonra geriye
anlamlı bir açık kalmamış.

### Bu ölçümün asıl değeri

Sayılar değil, **doğru ölçüt eşlemesi**: her biçim sınıfının farklı bir
başarı tanımı var ve yanlış ölçütle bakınca sağlam bir sınıf `%0` görünüyor.
Sonraki turlar bu tabloyu başlangıç noktası alsın.

### Bu çalışmada yapılan dört ölçüm hatası

Hepsi doğrulama sırasında yakalandı, hiçbiri rapora girmedi:

1. Konuşmacı sınıfı yanlış ölçütle `%0` ölçüldü (doğrusu %98,9)
2. Ses etiketi boşluğu bayraksız yordamla ölçüldü (boşluk yoktu)
3. Hitap dedektöründe "223 düşen" ölçüldü (doğrusu 92)
4. Konum tabanlı hitap kuralı 366 gerçek hitabı eliyordu — ölçüm reddetti
