# Brief: S04E04 (Mutant Mascot) bulgu düzeltmeleri — Sonnet 5 için

Hazırlayan: Fable 5 (analiz, 2026-07-07). Bu brief kendi başına yeterlidir; konuşma bağlamı gerekmez.

**Durum: uygulandı (Sonnet 5, 2026-07-07).** Aşağıdaki 4 görev tamamlandı, testler yazıldı (17 yeni, toplam 1119 yeşil), yazılmış S04E04 çıktı dosyası onarıldı. Bu dosya geçmiş kayıt olarak saklanıyor (bkz. `round8-robustness-plan.md`/`round9-series-memory-plan.md` — proje geleneği).

## Arka plan (30 saniye)

`C:\Users\K\Downloads\ÇIKTI\Oddities_S04E04_Mutant Mascot.English.srt` (gpt-5.4-mini, sync+hybrid, critic+polish açık) kaynakla karşılaştırıldı; ham yedek `...ham.srt` mevcut. Depo geleneği: her bölümde görülen yeni sızıntı kelimeleri `hybrid_translate.py`'deki üç katmana eklenir (bkz. `tests/test_s04e08_kegels_guards.py` en güncel örnek) ve bölüme özel guard test dosyası açılır.

## Bulgular

1. **Türkmence sızıntı (yeni kelimeler):** cue #162 ve #237, "WELCOME TO THE INNER LAIR" →
   `"İçki gowak / içki otag'a hoş geldin."` — "gowak" (=mağara) ve "otag" (=oda/otağ) Türkmence; "İçki" saçma; üstelik model iki alternatifi `/` ile art arda basmış. Ham ve final aynı → critic yakalamadı (kelimeler tespit listelerinde yok).
2. **Polish yazım hatası ÜRETTİ:** cue #273 ham `"tek sorun"` → final `"ttek sorun"`. Güvenlik filtresi (content_word_drift/linebreak_count/...) üretilmiş yazım hatasını kontrol etmiyor.
3. **Parantezli çevirmen notu (ham'den geliyor):** #41 `East Village'a (Doğu Yakası mahallesi)`, #55 `The Monkey's Paw (Maymun Pençesi)` — ayrıca #55 anlam hatası: kaynak "A MONKEY PAW" (genel bir maymun pençesi), dükkân adı değil.
4. Bilgi (düzeltme gerekmez): 14 SDH cue'sunun silinmesi `clean_sdh: true` ayarından — bilinçli. Critic bu koşuda net faydalıydı (`kollektorlar→koleksiyonerler` vb.). Bilinen sızıntı taraması ham+final 0; uydurma tekrar 0.

## Görev 1 — Guard katmanları (`hybrid_translate.py`)

`_LOCAL_FIXES` listesine (S04E08 bloğunun yanına, ~satır 3120-3160 civarı; "S04E08 Turkic residue" yorumunu ara):

- İki INNER LAIR varyantını tek phrase-fix ile:
  `re.compile(r"İçki\s+gowak\s*/\s*içki\s+otag['’]?a\s+hoş\s+geldin", re.I)` → `'İç mabede hoş geldin'`
  (#162 "geldin.", #237'de "geldiniz." — regex 'geldin' ile bitip kalan "iz" korunursa ikisini de doğru üretir; test et.)
- `(re.compile(r'\bttek\b', re.I), 'tek')`
- NOT: `gowak`/`otag` için kelime-düzeyi otomatik değiştirme EKLEME (bağlamsız karşılık yanlış olur); yalnızca tespit listesine gir.

`_SOURCE_LANG_LEFTOVER` (~3503, "gulak" satırının yanı) ve `_TURKIC_DRIFT_RE` (~3534, aynı şekilde) her ikisine: `gowak\w*` ve `otag\b|otaga\b|otagy\w*` ekle.
Dikkat: Türkçe "otağ" (ğ ile) YANLIŞ ALARM VERMEMELİ — `otag` kalıpları ğ içermediği için çakışmaz; yine de false-positive testi yaz.

## Görev 2 — Güvenlik filtresine "üretilmiş yazım hatası" kontrolü

Filtrenin olduğu yer: `hybrid_translate.py` içinde öneri reddi nedenlerini üreten fonksiyon (grep: `content_word_drift`). Yeni kural (reason: `introduced_typo`):

- Öneri metninin tokenleri içinde, (a) orijinal satırda bulunmayan, (b) `^(\w)\1` ile başlayan (ilk harf çiftlenmiş), ve (c) ilk harfi atılınca orijinal satırdaki bir tokene eşit olan token varsa → öneriyi reddet.
- Bu dar tanım "ttek" vakasını yakalar; "Aaa"/"Ooo" gibi ünlemleri etkilemez (orijinalde 'aa' token eşleşmesi yoksa reddetmez).
- Hem critic hem polish öneri yolundan geçtiğinden filtre tek yerde ise tek ekleme yeter — filtre fonksiyonunun her iki geçiş tarafından paylaşıldığını doğrula.

## Görev 3 — Parantez notu validatörü + prompt kuralı

1. `run_validators`'a (grep: `GLOSS_MISS`) yeni bulgu: çeviri `(` içeriyor ama kaynak satırda `(`/`[` yok → `PAREN_NOTE` (satır critic'e düşsün; critic prompt'una "remove parenthetical translator glosses, keep the sentence natural" yönergesi eklenmeli — critic prompt'un kurulduğu yeri `must_use` geçen bölgede bulabilirsin).
2. Her İKİ sistem prompta (gui `_build_sync_system_prompt` ~1650 bölgesi, `ht.build_system_prompt` ~2130 bölgesi — TURKIC GUARD satırlarının yakını) şu kural YOKSA ekle (önce grep'le var mı bak: "parenthetical"):
   "NEVER add parenthetical translator notes or glosses '(...)' that do not exist in the source line. Translate the term; do not explain it."
   CLAUDE.md kuralı: iki prompt hizalı kalmalı; `tests/test_idiom_traps_prompt.py` kalıbında iki prompt için assert'lü test ekle.
3. Opsiyonel (düşük risk, öneriliyor): kaynakta ` / ` yokken çeviride varsa `ALT_SLASH` bulgusu (model alternatif basmış demektir — #162 deseni).

## Görev 4 — Yazılmış S04E04 dosyasının onarımı

Dosya: `C:\Users\K\Downloads\ÇIKTI\Oddities_S04E04_Mutant Mascot.English.srt` (önce `.bak` yedeği al; okuma `subtitle_formats.read_subtitle_text` ile, yazma `utf-8-sig`):

- #162: `İçki gowak / içki otag'a hoş geldin.` → `İç mabede hoş geldin.` (cue'daki "Ryan: Çok güzel, dostum." kısmı korunacak)
- #237: `İçki gowak / içki otaga hoş geldiniz.` → `İç mabede hoş geldiniz.`
- #273: `ttek` → `tek`
- #41: `öteye, East Village'a (Doğu Yakası mahallesi) taşıdık.` → `öteye, East Village'a taşıdık.`
- #55: `Ryan. Hey, The Monkey's Paw (Maymun Pençesi)!` → `Ryan. Hey, bir maymun pençesi!` (kaynak: "RYAN. HEY, A MONKEY PAW!")

## Test & doğrulama

1. Yeni test dosyası `tests/test_s04e04_mutant_mascot_guards.py` (örnek kalıp: `tests/test_s04e08_kegels_guards.py`):
   - phrase-fix iki varyant (geldin/geldiniz), `ttek→tek`
   - `_SOURCE_LANG_LEFTOVER`/`_TURKIC_DRIFT_RE` `gowak`, `otaga` eşleşmesi; `has_non_turkish_target_leak("İçki gowak / içki otaga hoş geldiniz.")` True
   - false-positive: `has_non_turkish_target_leak("Padişahın otağı ovaya kuruldu.")` False; `_apply_local_fixes("İyi ki geldin.")` değişmez
   - `introduced_typo`: 'ttek sorun' önerisi reddedilir; 'Aaa' ünlem içeren meşru öneri reddedilmez
   - `PAREN_NOTE` validatörü: kaynak parantezsiz + çeviri parantezli → bulgu var; kaynak parantezliyse yok
2. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py`
3. `python -m unittest discover -s tests` (mevcut taban: 1102, hepsi yeşil)
4. GUI'ye dokunulduysa headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`

## Riskler / dikkat

- `_LOCAL_FIXES` sıra duyarlı: spesifik/uzun kalıplar genel olanlardan ÖNCE.
- Dosyadaki regex string'leri `“` gibi kaçışları DÜZ METİN olarak içeriyor — Edit yaparken mevcut satırları birebir kopyala.
- Prompt değişikliği iki dosyada da yapılmalı (CLAUDE.md hizalama zorunluluğu).
- `we` benzeri kısa/riskli kelime ekleme (örn. tek başına `otag` yerine `\botag\b`) — kelime sınırlarını koru.

## Uygulama notları (Sonnet 5, 2026-07-07)

- Görev 1-3 planlandığı gibi uygulandı; `ALT_SLASH` de eklendi (kritik prompta kısa bir "ALTERNATIVE-TRANSLATION FIX" yönergesiyle).
- `introduced_typo` filtresi minimum token uzunluğu 4 ile sınırlandı (nt[0]==nt[1] kontrolünden önce) — "Aaa"/"Aa" gibi 2-3 harfli ünlemler bu eşiğin altında kaldığı için hiç değerlendirmeye girmiyor, tasarımdaki false-positive riski böylece kapatıldı.
- Görev 4'te #41/#55 için basit `str.replace` yetmedi — cue içindeki `\n` konumu beklenenden farklıydı ("East Village'a\n(Doğu Yakası mahallesi) taşıdık." gibi), whitespace-esnek regex ile düzeltildi. Cue sayısı (529) ve genel sızıntı taraması korunarak doğrulandı.
- Test tabanı 1102 → 1119 (+17), hepsi yeşil; compile + GUI headless smoke temiz.
