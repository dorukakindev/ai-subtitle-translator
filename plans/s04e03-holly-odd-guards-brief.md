# Brief: S04E03 (Return to Holly-Odd) bulgu düzeltmeleri — Sonnet 5 için

Hazırlayan: Fable 5 (analiz, 2026-07-07). Bu brief kendi başına yeterlidir; konuşma bağlamı gerekmez.

**Durum: uygulandı (Sonnet 5, 2026-07-07).** 4 görev tamamlandı, 18 yeni test (toplam 1137 yeşil), yazılmış S04E03 çıktı dosyası onarıldı (11 cue, `.bak` yedeği; `.ham.srt`'ye dokunulmadı).

## Arka plan (30 saniye)

`C:\Users\K\Downloads\ÇIKTI\Oddities_S04E03_Return to Holly-Odd.English.srt` (gpt-5.4-mini, sync+hybrid) kaynak ve `.ham.srt` ile karşılaştırıldı. Bu koşu, yeni retry mekanizmasının ilk canlı sınavıydı: 7 chunk "hedef-dil kaçağı" ile 3 tur yeniden denendi, 6'sı 3 turda da geçemedi, "son çare" onarımıyla kapatıldı. Depo geleneği: bölüm başına guard test dosyası (en güncel örnekler: `tests/test_s04e04_mutant_mascot_guards.py`, `tests/test_s04e08_kegels_guards.py`).

## Bulgular

1. **"guş" (Türkmence=kuş) finalde 11 cue'da yayınlandı:** ham'de 14 cue vardı (#10, 48, 67, 70, 78, 79, 181, 203, 220, 244, 351, 353, 357, 376), polish yalnızca 3'ünü düzeltti (#10, #79, #351). "guş" hiçbir tespit listesinde yok → retry hiç tetiklenmedi, satırlar critic'e "leak" olarak düşmedi. Bölüm kuş taksidermisi hakkında olduğu için kelime her yerde.
2. **`başy\w*` deseni yanlış alarm mayını (probe ile kanıtlandı):** `_TURKIC_DRIFT_RE`'deki `başy\w*`, meşru Türkçe "başyapıt", "başyapıtı", "başyazı" kelimelerini yakalıyor (`has_non_turkish_target_leak("Bu bir başyapıt.")` → True). Bu dosyada tetiklenmedi ama "başyapıt" geçen İLK çeviride her chunk 3 tur boşa retry yiyip son çareye düşecek. Antika/sanat içeriğinde "masterpiece→başyapıt" kaçınılmaz.
3. **Gözlemlenebilirlik eksiği:** retry logları ("1 hedef-dil kaçağı son çare için işaretlendi") HANGİ token'ın tetiklediğini söylemiyor. Bu koşuda 6 chunk × 3 tur = 18 chunk-çevirisi neye harcandı, çıktıdan geriye takip edilemiyor (onarım sonrası temiz). Yanlış alarm/gerçek sızıntı ayrımı log'dan yapılabilmeli.
4. Bilgi (düzeltme gerekmez): son çare onarımı çalışmış — final dosyada [HATA]/[ÇEVİRİ EKSİK] yok, bilinen-kelime taraması temiz. #327 "Quang.", #448 "Michael." çevrilmemiş görünüyor ama özel isim — doğru davranış. 5 SDH cue silinmesi `clean_sdh: true` ayarından. CPS aşımı 63 satır (yükseliyor; condense kapalı — kullanıcı tercihi).

## Görev 1 — "guş" guard katmanları (`hybrid_translate.py`)

Güvenlik ön-kontrolü yapıldı: Türkçede "guş" ile başlayan kelime YOK (kuşak/kuşku k ile; doğuşu/oluşu içinde \b yok) — generic önek değişimi güvenli.

`_LOCAL_FIXES` listesine (S04E04 bloğunun yanına; "S04E04 Turkic residue" yorumunu ara), sıra ÖNEMLİ (caps önce, generic re.I EN SONA):
```python
# S04E03 Turkic residue: guş (Türkmence kuş) — bölüm kuş taksidermisi, 14 cue'da sızdı.
# Türkçede 'guş' önekli kelime yok → generic önek değişimi güvenli; ek \1 ile korunur.
(re.compile(r'\bGUŞ(\w*)'), r'KUŞ\1'),
(re.compile(r'\bGuş(\w*)'), r'Kuş\1'),
(re.compile(r'\bguş(\w*)', re.I), r'kuş\1'),
```

`_SOURCE_LANG_LEFTOVER` ve `_TURKIC_DRIFT_RE`'ye (her ikisine): `guş\w*` ekle (gowak/otag girdilerinin yanına).

## Görev 2 — `başy\w*` yanlış alarmını daralt (`hybrid_translate.py` ~3577 bölgesi)

`_TURKIC_DRIFT_RE` içindeki `başy\w*` → `başyn\w*|başy\b` ile değiştir:
- Türkmen biçimler yakalanmaya devam eder: "başy" (çıplak), "başyna", "başynda", "başyny" (`başyn\w*`).
- Türkçe bileşikler kurtulur: "başyapıt" (başy**a**pıt — `başyn` eşleşmez, `başy\b` eşleşmez çünkü kelime devam ediyor), "başyazı", "başyardımcı".
- `_SOURCE_LANG_LEFTOVER`'daki `başy` zaten exact-word — DOKUNMA.
- Mevcut test `tests/test_oddities_round_write_guards.py:156` (`_TURKIC_DRIFT_RE.search("başy")`) geçmeye devam etmeli — doğrula.

## Görev 3 — Retry loguna tetikleyen token'ı ekle (gözlemlenebilirlik)

1. `hybrid_translate.py`'ye yeni yardımcı (mevcut `has_non_turkish_target_leak` ~3817 bölgesinin yanına):
```python
def non_turkish_leak_token(text: str) -> str | None:
    """has_non_turkish_target_leak'in POZİTİF bulduğu ilk somut token'ı döndürür
    (log/teşhis için). Tespit mantığıyla birebir aynı sırada bakar."""
```
   Gövde: `normalize_latin_homoglyphs` → `_FOREIGN_SCRIPT_RE.search` (match'i döndür) → `_TURKIC_DRIFT_RE.search` (match'i döndür) → Latin-extended token döngüsü (mevcut fonksiyondaki aynı döngü; ihlal eden token'ı döndür) → None.
   `has_non_turkish_target_leak` mantığını KOPYALAMA — tersine, `has_...`'ı `return non_turkish_leak_token(text) is not None` olarak sadeleştir (tek doğruluk kaynağı; mevcut testler davranış değişmediğini doğrular).
2. GUI'deki retry loglarına token'ı ekle. Yer: `subtitle_translator_gui.py` içinde grep `hedef-dil kaçağı` — hem "N chunk yeniden deneniyor, M hedef-dil kaçağı" üreten sayım hem "son çare için işaretlendi" mesajı. En az "son çare" mesajına somut token girsin, örn:
   `↺ chunk_80: 1 hedef-dil kaçağı son çare için işaretlendi ('guşlar')`
   Sayım yerlerinde satır başına ilk token'ı toplayıp mesaja `örn: 'X'` eklemek yeterli (tüm listeyi basma, log şişmesin).

## Görev 4 — Yazılmış S04E03 dosyasının onarımı

Dosya: `C:\Users\K\Downloads\ÇIKTI\Oddities_S04E03_Return to Holly-Odd.English.srt` (önce `.bak` yedeği; okuma `subtitle_formats.read_subtitle_text`, yazma `utf-8-sig`, cue sayısı 560 korunmalı; `.ham.srt`'ye DOKUNMA):
- Görev 1'deki yeni `_apply_local_fixes`'i tüm cue gövdelerine uygula — 11 "guş" cue'su (#48, 67, 70, 78, 181, 203, 220, 244, 353, 357, 376) otomatik düzelir (guşları→kuşları, guşlara→kuşlara, guşlarının→kuşlarının vb. — ek \1 ile korunur).
- Doğrulama: dosyada `(?i)\bguş` kalmadı; cue sayısı değişmedi; `has_non_turkish_target_leak` tüm dosyada temiz.

## Test & doğrulama

1. Yeni `tests/test_s04e03_holly_odd_guards.py` (kalıp: `test_s04e04_mutant_mascot_guards.py`):
   - guş local fix: `"Egzotik guşlar arayan"`→`"Egzotik kuşlar arayan"`, `"guşlarının çoğundan"`→`"kuşlarının çoğundan"`, `"en büyük guş bunlar"`→`"en büyük kuş bunlar"`, caps `"GUŞLAR"`→`"KUŞLAR"`
   - detection: `_SOURCE_LANG_LEFTOVER`/`_TURKIC_DRIFT_RE` "guş", "guşlar" eşleşir; `has_non_turkish_target_leak("Ben guşları seviyorum.")` True
   - false-positive regresyonları: `has_non_turkish_target_leak` şunlarda False → `"Bu bir başyapıt."`, `"başyazı yazdı"`, `"kuşak farkı"`, `"gündoğuşu"`; `_apply_local_fixes("kuşku duydum.")` değişmez
   - Türkmen "başy" hâlâ yakalanıyor: `_TURKIC_DRIFT_RE.search("başy")` ve `search("başynda")` not-None
   - `non_turkish_leak_token`: `("Ben guşları seviyorum.")` → "guşları" (veya guş-önekli token), `("Temiz bir cümle.")` → None
2. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py`
3. `python -m unittest discover -s tests` (taban: 1119, hepsi yeşil — `test_oddities_round_write_guards` dahil)
4. GUI'ye dokunulduğu için headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`

## Riskler / dikkat

- `_LOCAL_FIXES` sıra duyarlı: caps kalıplar re.I generic'ten ÖNCE (aksi hâlde caps metin küçük harfe düşer).
- `başy\w*` daraltması mevcut testi (`test_oddities_round_write_guards.py`) kırmamalı — "başy" exact hâlâ eşleşmeli.
- `has_non_turkish_target_leak`'i `non_turkish_leak_token` üzerinden sadeleştirirken davranış birebir korunmalı — mevcut leak testleri (test_source_language_leftover.py, test_faz_audit_guards.py, bölüm guard testleri) regresyon ağı görevi görür.
- Dosya onarımında sadece final .srt'ye dokun; `.bak` yedeği al; ham dosyası tarihî kayıt.

## Uygulama notları (Sonnet 5, 2026-07-07)

- `has_non_turkish_target_leak` → `non_turkish_leak_token` refactörü planlandığı gibi yapıldı (tek doğruluk kaynağı); dosyadaki bazı satırlar mojibake/escape-literal içerdiğinden (önceden bilinen bir durum) Edit eşleşmeleri küçük parçalar hâlinde yapıldı.
- `başy\w*` → `başyn\w*|başy\b` daraltması ve `guş\w*` eklemeleri planlandığı gibi; hem yeni hem eski testler (`test_oddities_round_write_guards.py` dahil) yeşil.
- Retry loglarına örnek token eklendi: tur-sayım mesajına `(örn: 'X')` ve son-çare mesajına da aynı formatta; yeni `_leak_example_token(cid)` closure'ı `_retry_hata` içinde `ht.non_turkish_leak_token` kullanıyor.
- Görev 4: 11/11 beklenen guş cue'su otomatik düzeldi, cue sayısı (560) korundu, tam dosya taraması temiz.
- Test tabanı 1119 → 1137 (+18), hepsi yeşil; compile + GUI headless smoke temiz.
