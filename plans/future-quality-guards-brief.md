# Brief: Geleceğe dönük kalite guard'ları (5 görev) — Sonnet 5 için (KOD)

Hazırlayan: **Fable 5** (analiz + tasarım, 2026-07-08). Protokol: analiz modeli karar verir
ve brief yazar; **Sonnet 5 uygular**. Bkz. [[fable5-planning-protocol]],
[[mini-main-model-quality-2026-07]], [[json-repair-cue-shift-2026-07]].

## Kanıt tabanı (neden bu 5 görev)

Bu oturum + önceki bölümlerin QA'sında bulunan, **hâlâ korumasız** hata sınıfları:
- **Garble token'lar** finale sızıyor, otomatik tarama ~1/3'ünü yakalıyor. Gerçek örnekler
  (hepsi teslim edilmiş dosyalardan): `simwolika` (w harfi), `Mısır'teki`/`Mısır'in` (ek
  uyumu), `toplumlarde` (-larde imkânsız dizi), `gündönümünde deki` (kopuk ek),
  `a astronom` / `orada a olduğunu` / `kıtasını a` (başıboş tek harf ×3!), `19th/18th century`.
- **Karışık terim çevirisi** aynı dosyada: `Incas'ı` ↔ `İnkaların` (Explorer 1, ikisi de
  var), `Ouija tahtası` ↔ `Ouija board`, `Boy King` ↔ `Çocuk Kral` — helper-model
  consistency sweep her seferinde "tutarsızlık bulunamadı" dedi (aynı-model kör noktası).
- **TM kirliliği**: `translation_memory.py::store/store_batch` (satır 233/261) hedef metni
  HİÇ doğrulamadan kaydediyor → geçmişte sızıntı/garble içeren satırlar DB'ye girdiyse,
  fuzzy/exact eşleşmeyle GELECEK bölümlere geri taşınır. (Kayıtlı hataların geri dönüşü,
  guard'ları by-pass eden tek yol.)
- **Polish kelime birleştirme hasarı**: `ya törensel` → `yatörensel` (F2 #183, polish
  yaptı); `introduced_typo` guard'ı bunu yakalamıyor (çift-harf değil, bitişme).

Hepsi deterministik, API'siz, offline test edilebilir. Doğrulama korpusu diskte hazır:
`translated/Göbekli*.srt.bak` (düzeltme ÖNCESİ, garble'lı) + `translated/Göbekli*.srt`
(düzeltilmiş, temiz = yanlış-pozitif kontrolü) + `C:\Users\K\Downloads\ÇIKTI\Explorer *.srt`
(düzeltilmemiş, garble'lı).

**Uygulama sırası (değer/risk):** Görev 1 → 4 → 2 → 3 → 5.

---

## GÖREV 1 — Deterministik garble-token kuralları (tespit + koşu-içi düzeltme)

**Yeni fonksiyon** `find_garble_tokens(text) -> list[tuple[str, str]]` (token, kural_adı)
— `hybrid_translate.py`'ye modül-düzeyi (hem `run_validators` hem gui kullanacak; gui
zaten fonksiyon içinde `import hybrid_translate as ht` yapıyor, scan_translation_quality
~3247'deki kalıp).

Kurallar (hepsi kanıt-tabanlı, ~sıfır yanlış-pozitif hedefli):

| # | Kural | Regex/mantık | Yakalar | FP guard'ı |
|---|---|---|---|---|
| R1 | Başıboş tek harf | token == tek küçük harf ∈ {a, ı, u, ü, ö} (satır içinde tek başına) | `a astronom`, `orada a`, `kıtasını a` | `o` (zamir) ve `e` (ünlem) HARİÇ — asla flagleme |
| R2 | Küçük-harf w/q/x token | token [wqx] içeriyor VE tamamen küçük harf | `simwolika` | allowlist: {web, wifi, www, fax, show, taxi}; büyük harfle başlayan (özel isim) atla |
| R3 | Başıboş ek | token ∈ {deki, daki, teki, taki} tek başına | `gündönümünde deki` | yok (bunlar asla bağımsız kelime değil) |
| R4 | İmkânsız ek dizisi | `\w+(larde|lerda|larte|lerta)\b` | `toplumlarde` | yok (Türkçe'de bu diziler imkânsız) |
| R5 | Apostrof ek uyumu (DAR) | `stem'suffix`: stem Türkçe-özel harf (çğıöşü/ı) İÇERİYORSA son ünlüsüyle ekin ilk ünlüsü kalınlık uyumu kontrol (-da/-de/-ta/-te, -ın/-in/-un/-ün, -a/-e aileleri) | `Mısır'teki`, `Mısır'in` | stem yalnız ASCII ise ATLA (İng. isimlerde telaffuz≠yazım: "Google'da" meşru) |
| R6 | İngilizce sıra sayısı | `\b\d+(st\|nd\|rd\|th)\b` | `19th century`, `18th century` | yok |

**Bağlantı A (koşu-içi düzeltme):** `run_validators` (~4296-4328, PAREN_NOTE/ALT_SLASH
kalıbı) → bulgu adı `GARBLE_TOKEN` (reason'a token'ları ekle, ör. `GARBLE_TOKEN(simwolika)`),
critic fix-talimatlarına (~6426 civarı, PAREN_NOTE/ALT_SLASH açıklamalarının yanına):
"GARBLE FIX: if reason includes GARBLE_TOKEN, the listed token(s) are broken/foreign —
rewrite ONLY those tokens as natural Turkish (fix vowel harmony, remove stray letters,
join broken suffixes); do not change anything else in the line."

**Bağlantı B (yazım-sonrası tarama):** `scan_translation_quality` — alignment bloğundan
sonra, `[HATA]` olmayan her blok için `ht.find_garble_tokens`; bulgu varsa:
`⚠ {fname}: N satırda bozuk/yabancı token — örn: #25 'simwolika', #88 'a' …` (warn) +
warnings sayısına ekle.

**Test** (`tests/test_garble_rules.py`, yeni): her kural için pozitif ör. yukarıdaki
gerçek token'lar + FP-negatifler: "o gitti" (R1 flaglemez), "web sitesi"/"show" (R2),
"Mısır'daki" (R5 uyum DOĞRU → flaglemez), "New York'ta" (R5 ASCII stem → atla),
"1969'da" (R6 değil), normal Türkçe cümleler → boş liste.

**Gerçek-dosya doğrulaması (ZORUNLU, scratchpad script):** `find_garble_tokens`'ı 4 dosyada
çalıştır: (1) `Göbekli...Genesis....srt.bak` → beklenen: simwolika, Mısır'teki, Mısır'in,
19th century×3, 18th century; (2) `Göbekli...Portal....srt.bak` → gündönümünde deki
(NOT: davânın/toplumlarde/atacalar Portal'ın .bak'ında; toplumlarde→R4, a astronom /
orada a / kıtasını a→R1); (3+4) DÜZELTİLMİŞ Göbekli çıktıları → **0 bulgu** (FP kontrolü).
Sapma varsa kuralı daralt, brief'teki tabloyu güncelleme — sonuçları raporla.

---

## GÖREV 4 (küçük, Görev 1'den hemen sonra) — Polish kelime-birleştirme guard'ı

`validate_polish_candidate`'e (hybrid_translate.py ~5652) yeni kontrol `_has_word_merge(old, new)`:
new'deki, old'da olmayan herhangi bir token (≥7 harf), old'daki iki ARDIŞIK token'ın
birleşimine eşitse (küçük harf, noktalama-arındırılmış) → `(False, "word_merge")`.
- Kanıt: F2 #183 `ya törensel` → `yatörensel` (polish bozdu, hiçbir guard yakalamadı).
- FP notu: "fark etmek"→"farketmek" gibi meşru-görünümlü birleşmeler de reddedilir — bu
  İSTENEN davranış (resmî yazım ayrık; polish'in yazım birleştirmesi zaten istenmiyor).
- Test: mevcut polish-guard test dosyalarından birine (`tests/test_s04e04_mutant_mascot_guards.py`
  kalıbı) `ya törensel ya da` → `yatörensel ya da` reddi + temiz öneri kabulü.

---

## GÖREV 2 — TM hijyeni (hataların geri dönüşünü kes)

**(a) Kayıt-anı gate'i:** `TranslationMemory.store` ve `store_batch` (translation_memory.py
233/261) içine, kaydetmeden önce doğrulama: hedef metin şunlardan birine takılırsa KAYDETME
(sessizce atla + reddedilen sayacı döndür/logla):
- `startswith("[HATA")` veya `== "[ÇEVİRİ EKSİK]"` veya boş,
- `ht.has_non_turkish_target_leak(target)`,
- `ht.find_garble_tokens(target)` boş değil.
Döngüsel import'a dikkat: `hybrid_translate`'i **fonksiyon içinde** lazy-import et (gui'deki
~3247 kalıbı). ht import edilemezse (ör. test ortamı) gate'i sessizce atla (fail-open —
TM kaydı kritik yol değil).
- Test (`tests/test_tm_store_gate.py`, yeni; geçici DB dosyasıyla): bäýram'lı hedef
  reddedilir; "[HATA]" reddedilir; temiz çift kaydedilir; store_batch karışık listede
  yalnız temizleri kaydeder.

**(b) Bir-defalık temizlik (script, app kodu DEĞİL):** scratchpad'e script yaz+çalıştır:
`translation_memory.db`'yi **önce kopyala** (`translation_memory.db.bak`), sonra tüm
satırları tara; hedefi (a)'daki kontrollere takılan satırları SİL; silinen sayı + ilk 10
örneği yazdır. Kullanıcıya sonucu raporla (kaç kayıt gitti). DB şeması için
translation_memory.py'yi oku — tablo/kolon adlarını koddan al, varsayma.

---

## GÖREV 3 — Deterministik karışık-terim raporu (aynı-model kör noktasına protez)

**Yeni fonksiyon** `detect_mixed_term_renderings(blocks, src_map) -> list` (gui,
detect_alignment_issues yanına): 
1. Kaynakta ≥3 kez geçen, en az bir kez cümle-ortasında Büyük-harfle yazılmış token'ları
   topla (özel isim adayları; ≥4 harf).
2. Her geçtiği cue'nun ÇEVİRİSİNDE bu terime karşılık gelen token'ı bul: önce aynen-geçme
   (Incas→Incas), yoksa gövde-eşleşme (`_has_stem_match` kalıbı: İnka→İnkaların) — ±1 cue
   toleransı (SOV dağıtımı).
3. Karşılıklar ≥2 FARKLI gövde kümesine ayrışıyorsa ve her kümede ≥2 örnek varsa bulgu:
   `{"term": "Incas", "renderings": {"İnka*": 5, "Incas*": 3}}`.
`scan_translation_quality`'ye bağla: `⚠ {fname}: 'Incas' dosya içinde karışık çevrilmiş
(İnka*×5 / Incas*×3) — tutarlılık kontrolü önerilir` (warn; otomatik düzeltme YOK —
hangisinin doğru olduğuna insan karar verir).
- **Gerçek-dosya doğrulaması:** Explorer 1 çıktısında Incas/İnkalar bulgusu ÇIKMALI;
  düzeltilmiş Göbekli'lerde çıkmamalı (ya da yalnız gerçek karışıklık). FP fazlaysa
  eşikleri sıkılaştır (küme≥3) — sonucu raporla.
- Test: sentetik karışık/tutarlı/tek-küme durumları.

---

## GÖREV 5 (opsiyonel, düşük risk tercihli) — Bulguları kalite raporuna kalıcılaştır

Bugün 🚨/⚠ bulguları yalnız log'da; kullanıcı `ceviri_raporu.txt`'den göremiyor.
`scan_translation_quality`'ye opsiyonel `notes_out: list = None` parametresi ekle; alignment
+ garble + karışık-terim bulgu özetlerini (tek satırlık string'ler) append et. Çağıran
yerlerde (grep `scan_translation_quality(`) listeyi geçir ve rapor satırlarına
(`build_quality_report_text` ~3541 çıktısının dosya bölümüne "Sorunlar:" alt-listesi olarak)
ekle. Çağrı-yeri değişikliği 4 akışta karmaşıklaşırsa bu görevi ATLA ve brief'e not düş —
log-only kabul edilebilir.

---

## Doğrulama (Sonnet, her görevden sonra)
1. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py translation_memory.py`
2. İlgili yeni test modülü + `python -m unittest discover -s tests` (tam paket, regresyon yok)
3. Headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`
4. Görev 1 ve 3'ün **gerçek-dosya doğrulama** sonuçlarını (beklenen-yakalanan tablosu +
   temiz dosyalarda 0 FP) kullanıcıya raporla.

## KAPSAM DIŞI (dokunma)
- Explorer/Göbekli çıktılarının içerik düzeltmesi (ayrı karar, hâlâ bekliyor).
- `condense` (ayrı brief: `plans/condense-safety-validators-brief.md`, o da Sonnet'te bekliyor).
- Timecode/sıra no/credential. Büyük refactor yok. `_LOCAL_FIXES`'e kelime ekleme YOK
  (bu brief'in amacı kelime-listesi değil, SINIF yakalayan desen-kuralları).
