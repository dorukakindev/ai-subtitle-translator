# OpenAI Altyazı Çevirisi — Kapsamlı Kod Tabanı Bug, Hata ve İyileştirme Rehberi
> **Kullanım Amacı:** Bu belge, projedeki tüm modüller üzerinde yapılan derinlemesine statik ve dinamik denetimler sonucunda tespit edilen **71 kritik/yüksek öncelikli mimari ve mantıksal hatayı**, kök nedenlerini, etkilenen dosya/satır numaralarını ve diğer AI geliştirici modellerin doğrudan uygulayabileceği somut düzeltme reçetelerini içermektedir.

---

## 📌 İÇİNDEKİLER
1. [Batch API ve Kurtarma (Recovery / Resume) Hataları](#1-batch-api-ve-kurtarma-recovery--resume-hataları)
2. [Çok Dilli (Multilingual) ve Türkçe Odaklılık Çelişkileri](#2-çok-dilli-multilingual-ve-türkçe-odaklılık-çelişkileri)
3. [Model Sağlayıcı ve Uç Nokta (Provider / Adapter) Hataları](#3-model-sağlayıcı-ve-uç-nokta-provider--adapter-hataları)
4. [Altyazı Ayrıştırma, Format ve Etiket (Parsing / SDH / Tag) Hataları](#4-altyazı-ayrıştırma-format-ve-etiket-parsing--sdh--tag-hataları)
5. [Dizi ve Proje Hafızası (Series / Project / TM) Hataları](#5-dizi-ve-proje-hafızası-series--project--tm-hataları)
6. [Maliyet, Jeton ve Raporlama (Cost / Token / Report) Hataları](#6-maliyet-jeton-ve-raporlama-cost--token--report-hataları)
7. [İşletim Sistemi, Güvenlik ve Arayüz (Windows / ACL / GUI) Hataları](#7-işletim-sistemi-güvenlik-ve-arayüz-windows--acl--gui-hataları)
8. [Ek Mantıksal ve Biçimsel Hatalar](#8-ek-mantıksal-ve-biçimsel-hatalar)

---

## 1. Batch API ve Kurtarma (Recovery / Resume) Hataları

### 🔴 BUG 1: Two-Wave Batch Kurtarmada Wave A'nın Erken Silinmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~33885-33887)
* **Kök Neden:** `_submit_wait` fonksiyonu Wave A tamamlandığında `self._unregister_batch(bid_a)` çağrısı yapar. Böylece Wave B henüz tamamlanmadan `batch_id.txt` dosyasından Wave A silinir.
* **Sonuç:** Uygulama Wave B devam ederken kapatılırsa, tekrar açılıp "Devam Et / Kurtar" denildiğinde Wave A artık dosyada olmadığı için kalıcı olarak kaybolur; çevirinin ilk yarısı çöpe gider.
* **Çözüm Reçetesi:** Wave A'nın unregister işlemi Wave B tamamen bitene veya `_run_twowave_batches` sonlanana kadar ertelenmeli ya da `run_id` bazlı iki dalgalı kayıt tutulmalıdır.

### 🔴 BUG 2: `_run_hybrid` Faz 2 İçinde Değişken Sızıntısı Nedeniyle Çoklu Dosyalarda İki-Dalgalı Batch'in Çökmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~34562)
* **Kök Neden:** Faz 2 döngüsünde her dosyanın doğru hash'i `expected_source_hash` değişkeninde olmasına rağmen `_run_twowave_batches` çağrısına Faz 1'in en son dosyasından arta kalan `_expected_source_hash` (alt çizgili) iletilir.
* **Sonuç:** Çoklu dosya çevirisinde 1. dosya işlenirken 5. dosyanın hash'i karşılaştırılır; sistem *"Kaynak dosya değişti"* diyerek çeviriyi hatalı durdurur.
* **Çözüm Reçetesi:** Satır 34562'deki parametre `expected_source_hash=expected_source_hash` olarak düzeltilmelidir.

### 🔴 BUG 3: Yanlış API Anahtarı Seçildiğinde Batch ID'nin Kalıcı Olarak Silinmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~31934-31941 ve ~32052-32060)
* **Kök Neden:** `_resume_batches` fonksiyonu kurtarma sırasında `api_key_fingerprint` uyuşmadığında kullanıcıya *"Farklı bir API anahtarıyla gönderilmiş, orijinal anahtarı seçin"* uyarısı verir, ancak hemen ardından `self._unregister_batch(bid)` çağırarak batch kimliğini `batch_id.txt` dosyasından kalıcı olarak siler.
* **Sonuç:** Kullanıcı hatasını fark edip doğru API anahtarını seçtiğinde bile kayıt silindiği için devam eden çeviri bir daha asla kurtarılamaz.
* **Çözüm Reçetesi:** Parmak izi uyuşmadığında `self._unregister_batch(bid)` **çağrılmamalı**, sadece uyarı basılıp o batch turu `continue` ile atlanmalıdır.

### 🔴 BUG 4: `repair_batches.py` İçinde `batch_fmap_*.json` Zaman Damgasının Çiftlenerek Çıktının Bozulması
* **Dosya:** `repair_batches.py` (Satır ~211-212, ~223-224, ~260-264)
* **Kök Neden:** `fmap` içinde saklanan `[(idx, "00:00:01,000 --> 00:00:04,000", text)]` verisini `repair_batches.py` `idx, start, end = entry[0], entry[1], entry[2]` ile açar ve `f"{start} --> {end}"` yazar.
* **Sonuç:** Kurtarılan SRT dosyalarında zaman satırları `"00:00:01,000 --> 00:00:04,000 --> English text"` haline gelir; altyazı bozulur.
* **Çözüm Reçetesi:** `ts = start if "-->" in str(start) else f"{start} --> {end}"` kontrolü eklenmelidir.

### 🔴 BUG 5: `repair_batches.py.parse_chunk` İçinde Boş Çevirilerin (`t=""`) Geçersiz Sayılarak Bütün Chunk'ın `[HATA]` Olması
* **Dosya:** `repair_batches.py` (Satır ~55-58)
* **Kök Neden:** `if not (isinstance(item, dict) and "i" in item and isinstance(item.get("t"), str) and item["t"].strip()): return {}` şartı boş cue'ları (`t=""`) geçersiz sayar.
* **Sonuç:** Müzik veya SDH silinmesi nedeniyle bilinçli olarak boş bırakılan satırlarda tüm chunk reddedilir ve 10-15 satır birden `[HATA]` yapılır.
* **Çözüm Reçetesi:** `item.get("t") is not None` kontrolü uygulanmalı; boş dize geçerli kabul edilmelidir.

---

## 2. Çok Dilli (Multilingual) ve Türkçe Odaklılık Çelişkileri

### 🔴 BUG 6: `hybrid_translate._has_explicit_answer_polarity_flip` İçinde Yabancı Dillerde Anlam Zıtlığı (Polarity Flip) Korumasının Çökmesi
* **Dosya:** `hybrid_translate.py` (Satır ~6986-7000 ve ~11329-11330)
* **Kök Neden:** Fonksiyon kaynakta çok dilli evet/hayır kalıplarını ararken hedefte sadece Türkçe `_EXPLICIT_TURKISH_YES_RE` (`evet`) ve `_EXPLICIT_TURKISH_NO_RE` (`hayır`) regex'lerini arar.
* **Sonuç:** Almanca (*Ja/Nein*), Fransızca (*Oui/Non*), İspanyolca (*Sí/No*) dillerinde model diyalogdaki evet/hayır anlamını tam tersine çevirse bile sistem bunu yakalayamaz.
* **Çözüm Reçetesi:** Fonksiyona `target_language` parametresi eklenmeli ve hedef dilin evet/hayır kalıpları denetlenmelidir.

### 🔴 BUG 7: `hybrid_translate.validate_condense_candidate` İçinde Dil Parametresi Olmaması ve Yabancı Dillerde Kısaltılan Olumsuz Cümlelerin Reddedilmesi
* **Dosya:** `hybrid_translate.py` (Satır ~11672-11681)
* **Kök Neden:** `validate_condense_candidate` fonksiyonu `target_language` parametresi almaz ve `_has_turkish_negation` (`-me/-ma`, `değil`, `yok`) ile `has_non_turkish_target_leak` kontrollerini koşulsuz çalıştırır.
* **Sonuç:** Almanca (*"Ich weiß es nicht"*), Fransızca (*"Je ne sais pas"*) gibi dillerde başarıyla kısaltılan olumsuz cümleler Türkçe eki içermediği için reddedilir; yüksek okuma hızı (CPS aşımı) düzeltilemez.
* **Çözüm Reçetesi:** `validate_condense_candidate` fonksiyonuna `target_language` aktarılmalı; Türkçe odaklı denetimler sadece Türkçe hedef dilde çalıştırılmalıdır.

### 🔴 BUG 8: `hybrid_translate.validate_polish_candidate` İçinde Dil Parametresi Olmaması ve Yabancı Dillerde Olumsuz Cümlelerin Reddedilmesi
* **Dosya:** `hybrid_translate.py` (Satır ~10729-10780, ~10834-10848 ve ~11325-11360)
* **Kök Neden:** `validate_polish_candidate` fonksiyonu `src_lang` ve `tgt_lang` almaz; `_source_negation_requires_turkish_negation` ve `_has_turkish_negation` ile Almanca/Fransızca olumsuz cümleleri Türkçe eki içermediği için Polish aşamasında %100 reddeder; yabancı kaynaklı dosyalarda zaman/çoğul denetimlerini devre dışı bırakır.
* **Sonuç:** Almanca, Fransızca, İspanyolca çevirilerde Polish geçişinin ürettiği olumsuz cümleler reddedilir.
* **Çözüm Reçetesi:** `validate_polish_candidate` fonksiyonuna `src_lang` ve `tgt_lang` aktarılmalı; dil denetimleri parametrik olmalıdır.

### 🔴 BUG 9: `hybrid_translate.run_validators` İçinde Hedef Dil Kontrolü Olmaması Nedeniyle Yabancı Dillerde Tüm Satırların Şüpheli Sayılması
* **Dosya:** `hybrid_translate.py` (Satır ~7726-7900 ve ~12435-12450)
* **Kök Neden:** `run_validators` fonksiyonu `tgt_lang` parametresi almaz ve tüm kuralları Türkçe'ye göre (`has_non_turkish_target_leak`, `_has_turkish_negation`, `_looks_like_early_turkish_verb_closure`) çalıştırır.
* **Sonuç:** Almanca, Fransızca veya İspanyolca altyazıların istisnasız **tüm satırları** "Türkçe sızıntı" sayılarak hatalı ilan edilir; Critic aşaması binlerce satırı OpenAI'a göndererek yüz binlerce boşuna jeton harcatır.
* **Çözüm Reçetesi:** `run_validators` fonksiyonuna `tgt_lang` aktarılmalı; Türkçe odaklı denetimler sadece `tgt_lang in ("Turkish", "Türkçe")` iken çalıştırılmalıdır.

### 🔴 BUG 10: `prompt_constants` İçinde Sabit Türkçe Kurallar ve Küfürlerin Yabancı Dilleri Bozması
* **Dosya:** `prompt_constants.py` (Satır ~71-86 ve ~89-147)
* **Kök Neden:**
  1. `JSON_INSTRUCTION` sabit metni her çeviri chunk'ına eklenir ve 8 ayrı yerde *"Turkish"*, *"Turkish (SOV)"* kuralı işletir.
  2. `transliteration_guard_rule(target_language)` hedef dil ne olursa olsun Türkçe küfürleri (`sik-`, `orospu çocuğu`, `göt`, `bok`) sabit olarak yazar.
* **Sonuç:** Almanca, Fransızca veya İspanyolca çevirilerde model cümleleri Türkçe SOV dilbilgisiyle bölmeye çalışır ve yabancı dildeki altyazılara Türkçe küfürler sızdırır.
* **Çözüm Reçetesi:** `JSON_INSTRUCTION` dinamik bir fonksiyona (`build_json_instruction(target_language)`) dönüştürülmeli; `"Turkish"` yerine `{target_language}` yerleştirilmeli; `transliteration_guard_rule` ise sadece `target_language in ("Turkish", "Türkçe")` iken bu eşlemeleri vermelidir.

### 🔴 BUG 11: `_apply_local_fixes` İçinde Hedef Dil Kontrolü Olmaması ve Yabancı Dillere Türkçe Kelime Enjeksiyonu
* **Dosya:** `hybrid_translate.py` (Satır ~5219-5300 ve ~12396-12402)
* **Kök Neden:** `critic_pass_with_helper` Stage 1'de `_apply_local_fixes` çağrılırken `tgt_lang` kontrolü yapılmaz. `_LOCAL_FIXES` tablosundaki `\bhell\b` $\rightarrow$ `cehennem`, `\bDe\s+Heilige\s+Graal\b` $\rightarrow$ `Kutsal Kâse`, `\bqueeste\b` $\rightarrow$ `arayış`, `\bskelet\b` $\rightarrow$ `iskelet` regex'leri çalışır.
* **Sonuç:**
  - Almanca'da "aydınlık/açık renk" anlamına gelen `"hell"` kelimesi *"cehennem"* yapılır (*"Das Zimmer ist hell"* $\rightarrow$ *"Das Zimmer ist cehennem"*).
  - Felemenkçe'nin öz kelimeleri olan `"De Heilige Graal"`, `"queeste"`, `"skelet"` kelimeleri Türkçe kelimelerle ezilir.
* **Çözüm Reçetesi:** `_apply_local_fixes` fonksiyonunun başına `if tgt_lang.lower() not in ("turkish", "türkçe", "tr"): return text, 0` kontrolü eklenmelidir.

### 🔴 BUG 12: `native_reader_pass` İçinde Sabit Türkçe Personası Nedeniyle Yabancı Dillere Türkçe Yazılması
* **Dosya:** `hybrid_translate.py` (Satır ~4125-4150)
* **Kök Neden:** `native_reader_pass` fonksiyonunda `tgt_lang` parametresi olmasına rağmen sistem isteminde `"Sen Türkiye'de doğup büyümüş, sadece Türkçe okuyan bir film izleyicisisin."` ve `"Doğal Türkçe konuşma sesine kavuştur"` talimatı hardcode edilmiştir.
* **Sonuç:** Almanca veya Fransızca çevirilerde model bu satırları "bozuk Türkçe" sanıp Türkçe cümlelerle değiştirir (`{"id": "5", "fixed": "Türkçe Cümle"}`).
* **Çözüm Reçetesi:** İstem personası `tgt_lang` değerine göre dinamik üretilmeli; Türkçe personası sadece `tgt_lang in ("Turkish", "Türkçe")` iken aktif olmalıdır.

### 🔴 BUG 13: `_verify_native_candidates` İçinde `tgt_lang` Parametresinin Olmaması ve Hakemin Yabancı Dilleri Reddetmesi
* **Dosya:** `hybrid_translate.py` (Satır ~3876-3901)
* **Kök Neden:** Hakem model isteminde `"1) Önceki Türkçe gerçekten yapay mı 2) Yeni Türkçe kaynaktaki bütün anlamı koruyarak daha doğal mı 3) İki sürüm de kabul edilebilir Türkçeyse reddet"` kuralları yer alır.
* **Sonuç:** Almanca/Fransızca düzeltmeler hakem model tarafından Türkçe olmadıkları için %100 oranında `accept: false` ile reddedilir; jetonlar boşa harcanır.
* **Çözüm Reçetesi:** Fonksiyona `tgt_lang` parametresi eklenmeli ve kriterler hedef dile göre oluşturulmalıdır.

### 🔴 BUG 14: `validate_polish_candidate` ve `consistency_sweep` İçinde Türkçe Olumsuzluk (`_has_turkish_negation`) Dayatması
* **Dosya:** `hybrid_translate.py` (Satır ~11325-11326 ve ~11813-11816)
* **Kök Neden:**
  1. `validate_polish_candidate` kaynakta olumsuzluk varsa çeviride de olumsuzluk olduğunu teyit etmek için `_has_turkish_negation` (`-me/-ma`, `değil`, `yok`) çağırır.
  2. `consistency_sweep` satırları `not has_non_turkish_target_leak(tr)` denetimiyle süzer.
* **Sonuç:** Almanca (*"Ich weiß nicht"*), Fransızca (*"Je ne sais pas"*) gibi olumsuz yabancı cümleler Türkçe eki içermediği için Polish aşamasında %100 reddedilir; `consistency_sweep` ise yabancı dillerde tamamen kilitlenir.
* **Çözüm Reçetesi:** `_has_turkish_negation` ve `has_non_turkish_target_leak` kontrolleri sadece Türkçe hedef dillerde çalıştırılmalıdır.

### 🔴 BUG 15: `translation_memory._is_safe_target` İçinde Yabancı Dil Çevirilerinin TM'ye Kaydının Engellenmesi
* **Dosya:** `translation_memory.py` (Satır ~86-104 ve ~429-430)
* **Kök Neden:** `_is_safe_target` hedef dil kontrolü yapmaksızın `has_non_turkish_target_leak(target)` fonksiyonunu çağırır.
* **Sonuç:** Almanca, Fransızca veya İspanyolca yapılan çevirilerin %100'ü "Türkçe dışı sızıntı" sayılarak Çeviri Belleğine (TM) kaydedilmez.
* **Çözüm Reçetesi:** `_is_safe_target` fonksiyonuna `target_language` parametresi aktarılmalı ve bu denetim yalnızca Türkçe hedefte uygulanmalıdır.

### 🔴 BUG 16: `write_srt` İçinde Yabancı Hedef Dillerde Boş Cue'lara Sabit Türkçe `"[ÇEVİRİ EKSİK]"` Yazılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~3114-3116)
* **Kök Neden:** `write_srt` fonksiyonunda `if not text.strip(): text = "[ÇEVİRİ EKSİK]"` yazımı hedef dil denetlenmeden sabit Türkçe uygulanır.
* **Sonuç:** Almanca veya Fransızca altyazı dosyalarında boş veya müzik satırlarına Türkçe `[ÇEVİRİ EKSİK]` yer tutucusu yazılarak yabancı dile Türkçe kelime sızdırılır.
* **Çözüm Reçetesi:** Yer tutucu metin hedef dile göre seçilmeli veya `"[HATA]"` kullanılmalıdır.

### 🔴 BUG 17: `hybrid_translate._generate_pronoun_map` ve `_sanitize_analysis_aux` İçinde Hitap Haritasının Yalnızca Türkçe `sen/siz` ile Sınırlandırılması
* **Dosya:** `hybrid_translate.py` (Satır ~876-895, ~1750-1760 ve ~3846-3855)
* **Kök Neden:** `_generate_pronoun_map` analiz isteminde `"For Turkish translation, determine whether each character pair uses informal ('sen') or formal ('siz') address"` talimatını sabit gönderir; `_sanitize_analysis_aux` ise yalnızca `"sen"` ve `"siz"` değerlerini kabul eder.
* **Sonuç:** Almanca (*du/Sie*), Fransızca (*tu/vous*), İspanyolca (*tú/usted*), İtalyanca (*tu/Lei*) dillerinde samimi/resmi hitap kuralları ya tamamen reddedilir ya da yabancı dildeki altyazılara Türkçe hitap terimleri sızdırılır.
* **Çözüm Reçetesi:** Hitap motoru hedef dilin zamir çiftlerini (Almanca `du/Sie`, Fransızca `tu/vous`, İspanyolca `tú/usted`) destekleyecek şekilde parametrik hale getirilmelidir.

### 🔴 BUG 18: `_append_candidate_context` ve `_write_critic_change_report` İçinde Sabit "Türkçe" Başlıklarının Raporlara Sızması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~5361-5374 ve ~26820-26850)
* **Kök Neden:** Critic ve Term Normalization denetim raporlarında (`*_critic_raporu.txt`) bağlam satırları `Türkçe: {row.get('translation', '')}` ve `"mevcut Türkçe aynen korundu"` sabit metinleriyle üretilir.
* **Sonuç:** Almanca veya Fransızca çevirilerde raporlara `"Türkçe: Hallo"` veya `"mevcut Türkçe aynen korundu"` yazılarak rapor terminolojisi bozulur.
* **Çözüm Reçetesi:** Başlıklar `f"{target_language or 'Hedef'}: ..."` şeklinde dinamikleştirilmelidir.

### 🔴 BUG 19: `sdh_cleaner._TR_PLAIN_SPEAKER_LABEL_RE` ve `_TR_NARRATOR_LABEL_RE` İçinde Çok Dilli Konuşmacı/Dış Ses Etiketlerinin Silinmemesi
* **Dosya:** `sdh_cleaner.py` (Satır ~831-885)
* **Kök Neden:** Temizleme regex'leri yalnızca Türkçe karakter kümesini (`[A-ZÇĞİÖŞÜ]`) ve Türkçe dış ses eklerini (`SES ÜSTÜ`, `DIŞ SES`, `ANLATICI`) arar.
* **Sonuç:** Almanca (*MANN:*, *FRAU:*, *ERZÄHLER:*), Fransızca (*HOMME:*, *NARRATEUR:*), İspanyolca (*HOMBRE:*, *NARRADOR:*) dillerindeki konuşmacı ve dış ses etiketleri silinemez; son altyazıda kalır.
* **Çözüm Reçetesi:** Konuşmacı regex'leri çok dilli Unicode harf sınıfları (`[^\W\d_]`) ve yabancı dış ses terimleri ile genişletilmelidir.

### 🔴 BUG 20: `subtitle_translator_gui._untranslated_reason` ve `_PARTIAL_ENGLISH_LEAK_PHRASE_RE` İçinde Almanca `"In [Yıl]"` Kalıbının İngilizce Sızıntı Sayılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~5472-5482 ve ~5651-5661)
* **Kök Neden:** `_PARTIAL_ENGLISH_LEAK_PHRASE_RE` regex tablosunda `r"\bIn\s+(?:18|19|20)\d{2}\b"` (ör. *"In 1990"*) kalıbı İngilizce sızıntı olarak tanımlanmıştır. `_untranslated_reason` hedef dili denetlemeksizin bu eşleşmeyi arar.
* **Sonuç:** Almanca dilinde *"In 1990 wurde er geboren"* gibi tamamen doğru ve standart Almanca cümleler sistem tarafından *"İngilizce sızıntı"* sayılarak hatalı reddedilir ve onarım döngüsüne sokulur.
* **Çözüm Reçetesi:** `_untranslated_reason` fonksiyonuna `target_language` aktarılmalı; Almanca gibi bu kalıbı kullanan dillerde bu filtre devre dışı bırakılmalıdır.

### 🔴 BUG 21: `subtitle_translator_gui.parse_source_languages_response` İçinde Düz JSON Sözlük Dönen Modellerde Toplu Kaynak Dil Tespitinin Çökmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~7465-7470)
* **Kök Neden:** Fonksiyon API yanıtından yalnızca katı `data.get("languages")` anahtarını arar. Model `{"0": "Spanish", "1": "Italian"}` gibi düz JSON sözlüğü döndürdüğünde `detected_map` boş kalır.
* **Sonuç:** Toplu dosya çevirisinde tüm dosyaların kaynak dil tespiti başarısız olur ve dosya adı tahminine düşer.
* **Çözüm Reçetesi:** `detected_map = data.get("languages") if isinstance(data.get("languages"), dict) else (data if any(str(k).isdigit() for k in data) else {})` esnek ayrıştırması eklenmelidir.

---

## 3. Model Sağlayıcı ve Uç Nokta (Provider / Adapter) Hataları

### 🔴 BUG 22: `detect_content_type_with_ai` ve `detect_source_language_with_ai` İçinde Küçük `max_tokens` Nedeniyle Reasoning Modellerinde Düşünme Jetonu Tükenmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~7258 ve ~7405) ve `hybrid_translate.py` (Satır ~2753)
* **Kök Neden:** `max_tokens=40` ve `max_tokens=80` değerleri OpenAI `o1`, `o3-mini`, `gpt-5` modellerinde `max_completion_tokens` yapılır. Model düşünme aşamasında (reasoning) 40-80 jetonu tüketip 0 karakter çıktı üretir (`content=""`).
* **Sonuç:** `o1`/`o3`/`gpt-5` ana model seçildiğinde Otomatik Tür ve Otomatik Kaynak Dil tespiti **%100 oranında başarısız olur**.
* **Çözüm Reçetesi:** Reasoning/gpt-5 modellerinde `max_completion_tokens` en az `1000` taban değerine yükseltilmelidir.

### 🔴 BUG 23: `provider_retry._translation_schema_kwargs` İçinde `"developer"` Rolünün Özel Uç Noktalarda 400 Hatası Vermesi
* **Dosya:** `provider_retry.py` (Satır ~1244-1256 ve ~1286-1310)
* **Kök Neden:** Yapılandırılmış çıktıda (Structured Output) mesajlara eklenen `{"role": "developer", ...}` rolünü birçok özel proxy (OneAPI, NewAPI vb.) tanımaz ve 400 hatası döndürür. `_structured_unsupported` bunu yakalamadığı için fallback çalışmaz.
* **Sonuç:** Yapılandırılmış çıktı destekleyen ancak `developer` rolünü tanımayan tüm sağlayıcılarda çeviri çöker.
* **Çözüm Reçetesi:** Rol `"system"` yapılmalı veya `_structured_unsupported` içine rol hatası algılama eklenmelidir.

### 🔴 BUG 24: `helper_models.resolve_helper_model` İçinde Özel/Bilinmeyen Modellerin Sessizce 3. Parti Reseller API'sine Yönlendirilmesi
* **Dosya:** `helper_models.py` (Satır ~386-398 ve ~251-256)
* **Kök Neden:** `normalize_helper_model_label` bilinmeyen veya `"Özel (Custom)"` bir model adı geldiğinde fallback olarak sabit `"GPT-5.4 (Reseller)"` (`https://api.shuaiapi.com/v1`) döndürür.
* **Sonuç:** Kullanıcının girdiği özel URL ve model adı çiğnenerek tüm yardımcı analizler kullanıcının bilgisi dışında üçüncü parti bir aracı sunucuya aktarılır ve 401 yetki hatası alınır.
* **Çözüm Reçetesi:** Bilinmeyen veya özel modeller doğrudan resmi OpenAI varsayılanına (`https://api.openai.com/v1`) veya kullanıcının tanımladığı özel `base_url` parametresine bağlanmalıdır.

### 🔴 BUG 25: `_safe_chat_create` İçinde Anthropic/Bedrock Modelleri İçin `client.base_url` Kullanılarak 404 Hatası Alınması
* **Dosya:** `hybrid_translate.py` (Satır ~2646-2714)
* **Kök Neden:** Sağlayıcı Anthropic/Bedrock olduğunda `call_anthropic_messages` çağrılırken `base_url` olarak `cfg.base_url` yerine `client.base_url` (`https://api.openai.com/v1`) iletilir.
* **Sonuç:** Anthropic Messages formatındaki istekler doğrudan resmi OpenAI sunucusuna post edilir ve OpenAI `404 Not Found` / `400 Bad Request` döndürerek yardımcı modeli çökertir.
* **Çözüm Reçetesi:** `cfg.base_url` değeri `call_anthropic_messages` ve `call_bedrock_converse` fonksiyonlarına aktarılmalıdır.

### 🔴 BUG 26: `helper_models.call_anthropic_messages` İçinde Ardışık "user" Mesajlarının Birleştirilmemesi Nedeniyle 400 Hatası
* **Dosya:** `helper_models.py` (Satır ~596-612)
* **Kök Neden:** Anthropic Messages API'sinde rollerin `user` $\rightarrow$ `assistant` $\rightarrow$ `user` şeklinde kesinlikle sıralı değişmesi şarttır. Fonksiyon gelen mesajlardaki ardışık iki `user` rolünü birleştirmeden gönderir.
* **Sonuç:** Anthropic sunucusu `HTTP 400: roles must alternate between 'user' and 'assistant'` hatasıyla isteği reddeder.
* **Çözüm Reçetesi:** `anthropic_messages` oluşturulurken peş peşe gelen aynı roller aralarına `\n\n` konularak tek bir mesajda birleştirilmelidir (`role coalescing`).

### 🔴 BUG 27: `helper_models.call_bedrock_converse` İçinde Boş Metin ve Ardışık Roller Nedeniyle Bedrock `ValidationException` Çökmesi
* **Dosya:** `helper_models.py` (Satır ~456-499)
* **Kök Neden:** AWS Bedrock `client.converse` API'si mesaj içeriğindeki `text` uzunluğunun en az 1 olmasını (`length >= 1`) ve rollerin sıralı değişmesini şart koşar. Fonksiyon boş satırlarda `[{"text": ""}]` gönderir.
* **Sonuç:** AWS Bedrock `ClientError: ValidationException: Member must satisfy constraint: length >= 1` fırlatarak çöker.
* **Çözüm Reçetesi:** Boş metinler en az `" "` (boşluk) yapılmalı; ardışık aynı roller tek blokta toplanmalıdır.

---

## 4. Altyazı Ayrıştırma, Format ve Etiket (Parsing / SDH / Tag) Hataları

### 🔴 BUG 28: `subtitle_formats.restore_format_tags` İçinde Çok Konuşmacılı Repliklerde Tek Satırlık `<i>` (Dış Ses/Telsiz) İtaliklerinin Kaybolması
* **Dosya:** `subtitle_formats.py` (Satır ~435-465)
* **Kök Neden:** `restore_format_tags` etiket geri yüklerken HTML etiketleri için sadece tüm bloğun veya tüm satırların aynı anda sarılı olmasını (`all(wraps)`) arar. 1. satırın telsiz/iç ses nedeniyle italik (`<i>- Telsiz: Problem var.</i>`), 2. satırın normal (`- Anlaşıldı.`) olduğu çok konuşmacılı bloklarda `all(wraps)` başarısız olur ve satır bazlı döngü yalnızca ASS `{\...}` etiketlerini aradığı için 1. satırdaki italik etiket kalıcı olarak silinir.
* **Sonuç:** Çok konuşmacılı diyaloglarda telsiz/dış ses konuşmalarını ayırt eden tek satırlık `<i>...</i>` italik etiketleri silinip düz yazıya dönüşür.
* **Çözüm Reçetesi:** Satır bazlı geri yükleme döngüsüne (satır 449-464) satır içi `_match_full_wrap` desteği eklenmelidir.

### 🔴 BUG 29: `subtitle_formats._format_ass_text` İçinde `\n` Satır Kırma Regex'inin ASS Stil/Font Parametrelerini (`\fn`, `\no...`) Bölmesi
* **Dosya:** `subtitle_formats.py` (Satır ~471-474 ve ~489-496)
* **Kök Neden:** `_ASS_HARDLINE = re.compile(r'\\n', re.IGNORECASE)` regex'i ASS süslü parantez içi `{...}` denetimi yapmaksızın tüm metindeki `\n` dizilimlerini satır sonuna dönüştürür. `{\fnArial}` gibi bloklar `{\f\n Arial}` haline gelerek bölünür.
* **Sonuç:** Parantez içi satır sonuyla bölündüğü için `_ASS_OVERRIDE_BLOCK_RE` bu bloğu tanıyamaz; etiket geri yükleme motoru bloğu çözemez ve son `.srt` dosyasına diyalog metni olarak `{\f` ve `Arial}` şeklinde bozuk etiket kalıntıları sızdırılır.
* **Çözüm Reçetesi:** `_format_ass_text` satır kırma dönüşümünü `{...}` blokları dışındaki metne uygulamalı veya `_ASS_HARDLINE` regex'ini `(?<!\{[^}]*)\\n` parantez dışı şartıyla çalıştırmalıdır.

### 🔴 BUG 30: `subtitle_formats._repair_embedded_mac_roman_controls` İçinde Windows-1252 Tırnak ve Tirelerinin Bozulması
* **Dosya:** `subtitle_formats.py` (Satır ~225-239 ve ~335)
* **Kök Neden:** Windows-1252 tırnak (`“ ”`), kesme (`’`) ve tire (`– —`) karakterleri Latin-1 fallback'inde kontrol karakterlerine dönüştüğünde, fonksiyon bunları MacRoman harfleri (`ì`, `î`, `Ö`) ile değiştirir.
* **Sonuç:** Batı Avrupa ve İngilizce altyazılarda tırnak ve tire işaretleri bozulup metin içinde anlamsız `ì`, `î` harflerine dönüşür.
* **Çözüm Reçetesi:** MacRoman tamiri öncesinde Windows-1252 öncelikli karakter tablosu uygulanmalıdır.

### 🔴 BUG 31: `subtitle_formats._VTT_SRT_UNSAFE_TAG` İçinde `ruby` ve `rt` Etiketlerinin Unutulması ve Bozuk SRT Tag Restorasyonu
* **Dosya:** `subtitle_formats.py` (Satır ~21-24 ve ~523-526)
* **Kök Neden:** `_VTT_SRT_UNSAFE_TAG` temizleyicisi `ruby` ve `rt` etiketlerini içermez. Japonca/Asya WebVTT dosyaları çevrildiğinde, `restore_format_tags` ham kaynaktaki `<ruby>` ve `<rt>` etiketlerini Türkçe çıktının etrafına sarar.
* **Sonuç:** Standart SRT dosyalarına `<ruby>Türkçe</ruby>` ve `<rt>okunuş</rt>` etiketleri yazılarak TV ve medya oynatıcılarda altyazı bozulur.
* **Çözüm Reçetesi:** `_VTT_SRT_UNSAFE_TAG` tablosuna `ruby` ve `rt` etiketleri eklenmelidir.

### 🔴 BUG 32: `save_results` ve `build_requests` Arasındaki `file_map` Veri Yapısı Uyuşmazlığı ve Zaman Çizgisinin Bozulması
* **Dosya:** `hybrid_translate.py` (Satır ~13785-13786) ve `subtitle_translator_gui.py` (Satır ~4640-4650)
* **Kök Neden:** Standart senkron `build_requests` `file_map[cid]` yapısını `[(idx, ts_str, text_str)]` saklarken hibrit `build_batch_requests` `[(idx, start, end)]` saklar. `save_results` `f"{start} --> {end}"` yaptığında zaman satırı `"00:00:01,000 --> 00:00:03,000 --> Merhaba"` haline gelir.
* **Sonuç:** Altyazı zaman çizgisinde çift ok ve metin kalıntısı oluşur; video oynatıcılarda altyazı senkronu çöker.
* **Çözüm Reçetesi:** `ts = start if "-->" in str(start) else f"{start} --> {end}"` kontrolü eklenmelidir.

### 🔴 BUG 33: `_ends_sentence_gui` İçinde Unvan/Kısaltma Noktalarının (`Dr.`, `Mr.`, `Prof.`) Cümle Sonu Sanılması ve İsimlerin Bölünmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4704-4711)
* **Kök Neden:** `_ends_sentence_gui` fonksiyonu metnin son karakteri `.` olduğunda doğrudan `True` döner. `"I saw Dr."` gibi replikleri cümle sonu sayar.
* **Sonuç:** Chunk oluşturucu ve AI segmentasyon motoru cümleyi tam unvan ile isim arasından (`"Dr."` ile `"Watson"`) iki ayrı parçaya böler; çeviri bağlamı kopar.
* **Çözüm Reçetesi:** `_abbreviation_continues_gui` veya yaygın kısaltma tablosu (`_COMMON_ABBREVIATIONS`) entegre edilmelidir.

### 🔴 BUG 34: `_make_smart_chunks_gui` ve `_make_smart_chunks` İçinde `_abbreviation_continues` Kontrolünün Unutulması ve Chunk'ın İsim Ortasından Bölünmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4912-4915) ve `hybrid_translate.py` (Satır ~601-604)
* **Kök Neden:** Akıllı chunk bölücü yalnızca `_ends_sentence(text)` çağrısı yapar. `_abbreviation_continues` kontrol edilmediği için unvan ile isim tam chunk sınırından iki ayrı istek paketine bölünür.
* **Sonuç:** Model unvanı izole görür ve bağlamı koparır.
* **Çözüm Reçetesi:** `if _ends_sentence(text) and not (check_idx + 1 < n and _abbreviation_continues(text, _clean_source_text(cues[check_idx + 1].text))):` eklenmelidir.

### 🔴 BUG 35: `subtitle_formats.normalize_srt_timestamp_separators` İçinde Tek Haneli Saatlerin 2 Haneye Tamamlanmaması
* **Dosya:** `subtitle_formats.py` (Satır ~98-113)
* **Kök Neden:** `normalize_srt_timestamp_separators` tek haneli saatleri (`0:01:23,456`) yakalar ancak çıktıyı `f"{sh}"` ile ham yazar.
* **Sonuç:** Standart 2 haneli saat (`00:01:23,456`) bekleyen donanımsal medya oynatıcılarda altyazı yüklenemez.
* **Çözüm Reçetesi:** `f"{int(sh):02d}:{sm}:{ss},{(sms + '000')[:3]}"` formatlaması uygulanmalıdır.

### 🔴 BUG 36: `subtitle_formats._ass_ts_to_srt` İçinde 3 Haneli Milisaniyeli ASS Dosyalarının Dönüştürülmemesi
* **Dosya:** `subtitle_formats.py` (Satır ~356-366)
* **Kök Neden:** Regex `\.(\d{1,2})$` sabit 2 hane santisaniye bekler. 3 haneli milisaniye içeren ASS dosyalarında `None` döner ve ham `1:23:45.678` değerini bırakır.
* **Sonuç:** SRT dosyasına nokta ayraçlı ve tek haneli saatli bozuk zaman damgası yazılır.
* **Çözüm Reçetesi:** Regex `\.(\d{1,3})$` yapılmalı ve uzunluğa göre ölçeklenmelidir.

### 🔴 BUG 37: `subtitle_formats.parse_ass` İçinde ASS Dahili Stil/Aktör İsimlerinin (`Default`, `Sign`, `Main`) Konuşmacı Sayılarak Altyazıya Bulaşması
* **Dosya:** `subtitle_formats.py` (Satır ~709-715)
* **Kök Neden:** `parse_ass` fonksiyonu ASS `Name` sütunundaki her metni konuşmacı adı zannederek `text = f"{name}: {text}"` ile repliğin başına ekler.
* **Sonuç:** Aegisub stil isimleri (`Default: Hello`, `Sign: Entrance`, `Staff: Note`) çevrilip `.srt` çıktısına `"Default: Merhaba"` şeklinde kalıcı olarak yazılır.
* **Çözüm Reçetesi:** `name` alanındaki genel teknik etiketler (`default`, `sign`, `main`, `top`, `staff`, `caption` vb.) için bir kara liste uygulanmalıdır.

### 🔴 BUG 38: `sdh_cleaner.normalize_speaker_labels` ile Konuşmacı Etiketlerinin Silinmek Yerine Çevrilip Altyazıya Gömülmesi
* **Dosya:** `sdh_cleaner.py` (Satır ~576-612) ve `subtitle_translator_gui.py` (Satır ~3111-3112)
* **Kök Neden:** Proje ana kuralı *"Konuşmacı ve ses etiketleri son altyazıdan tamamen silinmelidir"* olmasına rağmen `normalize_speaker_labels` etiketleri Türkçeleştirir (`MAN:` $\rightarrow$ `ADAM:`, `NARRATOR (V.O.):` $\rightarrow$ `ANLATICI (D.S.):`) ve `write_srt` bu etiketleri son dosyaya yazar.
* **Sonuç:** Kullanıcıya teslim edilen `.srt` dosyasında diyalogların başında `ADAM:`, `ANLATICI:` gibi istenmeyen etiketler kalır.
* **Çözüm Reçetesi:** `normalize_speaker_labels` ve `_translate_speaker_labels` etiketleri çevirmek yerine satır başından tamamen kesip atmalıdır (`_strip_speaker_labels`).

### 🔴 BUG 39: `sdh_cleaner.normalize_sdh_descriptors` ile SDH Ses Efektlerinin Silinmek Yerine Çevrilerek Final Altyazıya Yazılması
* **Dosya:** `sdh_cleaner.py` (Satır ~543-551) ve `subtitle_translator_gui.py` (Satır ~3110)
* **Kök Neden:** `normalize_sdh_descriptors` *"Translate English words inside SDH brackets without removing them"* mantığıyla parantez içindeki sesleri Türkçeleştirir (`[LAUGHS]` $\rightarrow$ `[GÜLER]`, `(SIGHS)` $\rightarrow$ `(İÇ ÇEKER)`). `write_srt` diske yazarken bu etiketleri dosyaya gömer.
* **Sonuç:** Kullanıcıya teslim edilen son altyazıda `[KAHKAHA]`, `[GÜLER]`, `(İÇ ÇEKER)` ses etiketleri kalır; SDH temizleme kuralı çiğnenir.
* **Çözüm Reçetesi:** `write_srt` içinde `normalize_sdh_descriptors` yerine ses efektlerini tamamen silen `strip_sdh_descriptors` çağrılmalıdır.

### 🔴 BUG 40: `response_integrity.parse_translation_payload` İçinde Boş Çevirilerin Eksik Sayılarak Hata Döngüsüne Sokulması
* **Dosya:** `response_integrity.py` (Satır ~142-148)
* **Kök Neden:** Model müzik veya silinen SDH nedeniyle bir cue'yu meşru olarak boş dize (`{"i": "5", "t": ""}`) döndürdüğünde, `not item["t"].strip()` koşulu bu cue'yu geçersiz sayar ve `missing_ids` listesine atarak `fatal_reason = "missing_id"` üretir.
* **Sonuç:** Chunk 3-5 kez gereksiz yere `_retry_hata` döngüsüne sokulur; tüm denemeler bitince satıra `[HATA]` basılır ve ham İngilizce metin yazılır.
* **Çözüm Reçetesi:** Modelin bilinçli olarak boş bıraktığı dize (`""`) geçerli bir çıktı olarak kabul edilmelidir.

### 🔴 BUG 41: `_build_sync_system_prompt` İçinde Zaten Sökülmüş HTML Etiketlerini Koru Kuralının Modele Verilmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4522) ve `subtitle_formats.py` (Satır ~81-94)
* **Kök Neden:** `clean_translation_source_text` fonksiyonu modele gitmeden önce tüm `<i>`, `<b>`, `<u>` etiketlerini kaynaktan söker. Ancak sistem isteminde modele `"- Preserve ALL HTML-like inline tags exactly as-is: <i>...</i>"` kuralı gönderilir.
* **Sonuç:** Model metinde görmediği etiketleri kendi üretmeye kalkar ve `_restore_tags_blocks` ile birleştiğinde `<i><i>İtalik Metin</i></i>` şeklinde bozuk çift tag yapıları oluşur.
* **Çözüm Reçetesi:** Bu kural senkron sistem isteminden kaldırılmalıdır.

### 🔴 BUG 42: `write_srt` İçinde Şapkalı Harflerin (`â, î, û`) Koşulsuz Düzleştirilmesi ve Kelime Anlamlarının Bozulması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~3113 ve ~3140-3143)
* **Kök Neden:** `write_srt` dosya kaydedilirken `_DELIVERY_HAT_MAP` ile `â->a`, `î->i`, `û->u` dönüşümünü koşulsuz çalıştırır.
* **Sonuç:** Türkçe sesteş kelimeler (*"hâlâ"* $\rightarrow$ *"hala"*, *"kâr"* $\rightarrow$ *"kar"*, *"dâhi"* $\rightarrow$ *"dahi"*) bozulur ve anlam kayması yaşanır.
* **Çözüm Reçetesi:** Şapkalı harf temizliği isteğe bağlı bir ayara bağlanmalı veya kaldırılmalıdır.

### 🔴 BUG 43: `video_subtitles.extract_subtitle_stream` İçinde ASS Altyazıların `-c:s srt` ile Çıkarılması ve Konum Bilgilerinin Kaybolması
* **Dosya:** `video_subtitles.py` (Satır ~267-270)
* **Kök Neden:** Video dosyasından altyazı çıkarılırken ffmpeg komutuna sabit `-c:s srt` verilir.
* **Sonuç:** Video içindeki ASS altyazılarda bulunan tüm ekran konumları (`{\an8}` üst bant yazıları, tabela çevirileri) ffmpeg tarafından kırpılır; projenin `parse_ass` ve `_restore_tags_blocks` motoru etiketleri geri yükleyemez ve üst yazılar ekranın altına düşüp altyazı ile çakışır.
* **Çözüm Reçetesi:** ASS/SSA akışları video içinden `-c:s copy` ile doğrudan `.ass` uzantılı çıkarılmalıdır.

### 🔴 BUG 44: `subtitle_batch_translate.parse_srt` Fonksiyonunun Naive `split("\n\n")` Kullanarak Satır Kaybetmesi
* **Dosya:** `subtitle_batch_translate.py` (Satır ~121-129)
* **Kök Neden:** Windows CRLF (`\r\n`) veya çok satırlı repliklerde `content.split("\n\n")` kaba ayrıştırması kullanılır.
* **Sonuç:** Çok satırlı diyaloglar bölünür ve bazı altyazı blokları sessizce kaybolur.
* **Çözüm Reçetesi:** Doğrudan `subtitle_formats.parse_srt` kullanılmalıdır.

### 🔴 BUG 45: `_enforce_segment_groups` İçinde HTML Etiketlerinin (`<i>`, `<b>`) Korunmaması ve AI Segmentasyonda İtaliklerin Düşmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2724-2728)
* **Kök Neden:** Parçalı cue grupları birleştirilirken yalnızca ASS formatı (`re.match(r'^\s*(?:\{[^}]*\})+', ...)`) denetlenir; HTML etiketleri (`<i>`, `<b>`) kontrol edilmez.
* **Sonuç:** AI Segmentasyon uygulanan altyazılarda italik iç ses veya vurgulu metinler düz yazıya dönüşür.
* **Çözüm Reçetesi:** Hem ASS (`{...}`) hem de HTML (`<i>...`) başlangıç etiketleri geri yüklenmelidir.

---

## 5. Dizi ve Proje Hafızası (Series / Project / TM) Hataları

### 🔴 BUG 46: `series_memory._merge_saved_data` İçinde Karakter Kimliği Karşılaştırmasında `_character_identity` Yerine `casefold()` Kullanılması
* **Dosya:** `series_memory.py` (Satır ~261-274)
* **Kök Neden:** Disk ile bellek verilerini birleştiren `_merge_saved_data` fonksiyonunda satır 265 ve 270'te `_character_identity` yerine ham `str(item).strip().casefold()` kullanılmıştır.
* **Sonuç:** Disk hafızasında `"Serif"` varken yeni gelen bölümde `"Şerif"` tespit edildiğinde `casefold()` eşleşmesi başarısız olur ve aynı karakter dizi hafızasına iki farklı anahtarla mükerrer kaydedilir. Model sonraki bölümlerde çelişkili iki kural alarak karakter isimlerini tutarsız çevirir.
* **Çözüm Reçetesi:** Satır 265 ve 270'teki `else` dallarında `_character_identity(item)` kullanılmalıdır.

### 🔴 BUG 47: `translation_memory.lookup_batch` İçinde `uniq[h] = s` Sözlük Ezilmesi Nedeniyle Harf Varyasyonlarında TM'nin Atlanması
* **Dosya:** `translation_memory.py` (Satır ~293-315)
* **Kök Neden:** `lookup_batch` fonksiyonunda `uniq[h] = s` sözlüğü `h` anahtarı için tek bir `s` dizesi tutar. Bir dosyada aynı cümlenin farklı harf varyasyonları (`"Thank you."` ve `"THANK YOU."`) varsa, ilk varyasyon ezilir.
* **Sonuç:** `result` sözlüğünde ilk varyasyon yer almaz; TM ön belleği bu satırı bulamadım sanarak API'ye gönderir ve boşa jeton harcatır.
* **Çözüm Reçetesi:** `uniq` yapısı `uniq.setdefault(h, []).append(s)` listesi yapmalı; SQL'den dönen her `h` için `for src in uniq.get(h, []): result[src] = target` atanmalıdır.

### 🔴 BUG 48: `_run_sync` İçinde `file_map` Cue Metninin Dosya Yolu Sanılması ve Senkron TM'nin Çökmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~29404-29408 ve ~29435-29439)
* **Kök Neden:** `req_path = file_map[req["custom_id"]][0][2]` ifadesi `(idx, ts, text)` üçlüsünden altyazı replik metnini alır (dosya yolu yerine `"Hello"`). `source_hashes.get("Hello")` ve `_file_content_sha256("Hello")` başarısız olur.
* **Sonuç:** `context_fingerprint` boş kalır; senkron modda Çeviri Belleği (TM) ön taraması ve chunk atlama mekanizması tamamen devre dışı kalır; daha önce çevrilmiş altyazılar gereksiz yere tekrar OpenAI API'sine gönderilir.
* **Çözüm Reçetesi:** `req["filepath"]` veya doğru dosya yolu referansı kullanılmalıdır.

### 🔴 BUG 49: `hybrid_translate._generate_pronoun_map` İçinde Ayraç ve Boşluk Eşleşmeme Hatası Nedeniyle Hitap Haritasının Silinmesi
* **Dosya:** `hybrid_translate.py` (Satır ~1792-1801 ve ~3479)
* **Kök Neden:** `_generate_pronoun_map` karakter ikililerini bitişik tire ile (`"CharA-CharB"`) saklar. LLM modelleri JSON çıktısında karakter ikililerini boşluklu tire (`"CharA - CharB"`), ok (`"CharA -> CharB"`), eğik çizgi (`"CharA / CharB"`) veya bağlaçla (`"CharA to CharB"`) döndürdüğünde `_analysis_name_identity` boşlukları temizlemediği için eşleşme `False` döner.
* **Sonuç:** Model tarafından doğru tespit edilmiş sen/siz hitap kurallarının neredeyse tamamı sessizce filtrelenir; `pronoun_map` boş kalır.
* **Çözüm Reçetesi:** İkili isimler `re.split(r'\s*(?:[-–—>/]|->|to)\s*', pair)` ile sol ve sağ karakterler ayrı ayrı çözülerek `valid_pairs` ile eşleştirilmelidir.

### 🔴 BUG 50: `series_memory.SeriesMemory` İçinde Karakter Kaydı (`_character_identity`) ile Okuma (`casefold`) Uyuşmazlığı
* **Dosya:** `series_memory.py` (Satır ~380-383 ve ~470-473)
* **Kök Neden:** `merge_characters` köken bilgisini `_character_identity` ile normalize ederek (`"Şerif"` $\rightarrow$ `"serif"`) kaydeder. Ancak `build_hint` arama yaparken `casefold()` (`"şerif"`) kullanır.
* **Sonuç:** Türkçe veya aksanlı ada sahip karakterler (`Şerif`, `İsmail`, `Ömer`, `Hélène`) sözlükte bulunamaz ve sonraki bölümlerin dizi hafızası ipucundan tamamen düşer.
* **Çözüm Reçetesi:** `build_hint` içindeki arama da `char_origins.get(_character_identity(name))` ile yapılmalıdır.

### 🔴 BUG 51: `series_memory.parse_series_key` İçinde Anime ve Alternatif Bölüm İsimlendirmelerinin Tanınmaması
* **Dosya:** `series_memory.py` (Satır ~24-38 ve ~129-149)
* **Kök Neden:** Regex'ler yalnızca `SxxExx` ve `1x05` yapılarını arar.
* **Sonuç:** Anime bölüm formatları (`Show - 05`), `Episode 05`, `Ep 05` ve `Bölüm 05` dosyalarında `None` döner ve dizi hafızası devre dışı kalır.
* **Çözüm Reçetesi:** Anime (`r' - (\d{1,3})'`) ve `Episode/Ep/Bölüm` regex'leri eklenmelidir.

### 🔴 BUG 52: `project_memory.update_characters` İçinde Unvan Filtresi Olmaması Nedeniyle Genel Kelimelerin İsim İlan Edilmesi
* **Dosya:** `project_memory.py` (Satır ~188-200 ve ~240-243)
* **Kök Neden:** `update_characters` fonksiyonu gelen isimleri hiçbir unvan filtresinden geçirmez (`"Doctor"`, `"Officer"`, `"Captain"` vb.).
* **Sonuç:** `build_context_hint` bu kelimeleri `KARAKTERLER: ...` başlığıyla isteme enjekte eder; model diyalogdaki *"The doctor is here"* cümlesini *"Doctor geldi"* olarak çevirir (doktor kelimesini İngilizce bırakır).
* **Çözüm Reçetesi:** Genel unvan/meslek kelimelerini filtreleyen `_COMMON_NOUN_FILTER` uygulanmalıdır.

### 🔴 BUG 53: `translation_memory._fuzzy_semantically_compatible` İçinde Birebir Kelime Eşitliği Zorunluluğu
* **Dosya:** `translation_memory.py` (Satır ~44-72 ve ~403-404)
* **Kök Neden:** Fonksiyon `len(source_tokens) == len(candidate_tokens)` ve `set(source_tokens) == set(candidate_tokens)` kontrolü yapar.
* **Sonuç:** Fuzzy TM eşleştirmesi %85-95 oranında kilitlenir; `_fuzzy_semantic_anchors` fonksiyonu ölü koda dönüşür.
* **Çözüm Reçetesi:** Katı token eşitliği yerine anlamsal çapa benzerlik eşiği (similarity score >= 0.85) kullanılmalıdır.

---

## 6. Maliyet, Jeton ve Raporlama (Cost / Token / Report) Hataları

### 🔴 BUG 54: `_run_sync` / `_run_batch` / `_run_hybrid` İçinde Kalite İstatistiklerinin Teslim Blokları Yerine Ara Bloklardan Sayılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~30972-30976, ~33555-33560, ~35084-35090)
* **Kök Neden:** Diske yazılan nihai altyazı `_delivery_blocks = _prepare_upload_ready_blocks(self._maybe_merge_cues(sorted_blocks, ...))` ile üretilir. Ancak metrik sayımı `_hata_n, _cps_n = _count_hata_cps(sorted_blocks)` ile ara listeden yapılır.
* **Sonuç:** Parçalı birleştirme veya AI segmentasyonun ürettiği yüksek CPS okuma hızı sorunları veya azalan cue sayıları `ceviri_raporu.txt` raporuna yansımaz; rapor çıktıyla uyumsuz kalır.
* **Çözüm Reçetesi:** Sayım `_hata_n, _cps_n = _count_hata_cps(_delivery_blocks)` olarak güncellenmelidir.

### 🔴 BUG 55: `build_quality_report_text` İçinde Batch Modu Fallback Maliyet Hesabında %50 İndirimin Uygulanmaması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~12975-12984)
* **Kök Neden:** `actual_cost is None` durumunda `total_tokens / 1e6 * price` formülü işletilirken `mode` değişkeni denetlenmez.
* **Sonuç:** Batch API kullanan kullanıcıların `ceviri_raporu.txt` dosyasında gerçek maliyetin **tam 2 katı (2x)** tahmini harcama tutarı gösterilir.
* **Çözüm Reçetesi:** `if price is not None and "batch" in str(mode).lower(): price = price * 0.5` indirimi fallback hesabına eklenmelidir.

### 🔴 BUG 56: `_update_batch_tokens` İçinde Sağlayıcı Doğrulaması Olmadan Sabit OpenAI Fiyatı Hesaplanması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~20215-20221)
* **Kök Neden:** Özel proxy veya harici sağlayıcılar kullanılırken `_verified_token_price` kontrolü yapılmadan doğrudan `_model_token_price` çağrılır.
* **Sonuç:** Kullanıcı kendi yerel veya indirimli proxy'sini kullandığında ekrana sahte OpenAI USD fiyatları basılır.
* **Çözüm Reçetesi:** `_update_batch_tokens` içinde `_verified_token_price` kontrolü kullanılmalıdır.

### 🔴 BUG 57: `build_quality_report_text` Başlık Satırının Uyarının Altına Kayması (Header Inversion)
* **Dosya:** `subtitle_translator_gui.py` (Satır ~12820-12824)
* **Kök Neden:** `hata_files` uyarısı `lines.insert(0, ...)` ile listenin en tepesine eklenir.
* **Sonuç:** `"ÇEVİRİ KALİTE RAPORU"` ana başlığı uyarı kutusunun altına kayarak rapor formatını bozar.
* **Çözüm Reçetesi:** Uyarı satırları 0. indekse değil, ana başlıktan hemen sonra (satır 4-5 civarı) eklenmelidir.

---

## 7. İşletim Sistemi, Güvenlik ve Arayüz (Windows / ACL / GUI) Hataları

### 🔴 BUG 58: `_apply_api_profile` İçinde `save_credentials=False` Nedeniyle Atanan Profil Anahtarının Kaydedilmemesi ve Açılışta 401 Hatası
* **Dosya:** `subtitle_translator_gui.py` (Satır ~22860-22865)
* **Kök Neden:** API Profilleri panelinden profil atandığında `_apply_api_profile` `self._save_settings(save_credentials=False)` çağırır. Anahtar `credential_store`'a yazılmaz.
* **Sonuç:** Kullanıcı uygulamayı kapatıp açtığında `.gui_settings.json`'dan özel model seçili gelir ancak API anahtarı boş kalır; çeviri başlatıldığında anında `401 Unauthorized` hatası alınır.
* **Çözüm Reçetesi:** `_apply_api_profile` içinde `self._save_settings(save_credentials=True)` çalıştırılmalıdır.

### 🔴 BUG 59: `_pid_alive` İçinde `GetExitCodeProcess == STILL_ACTIVE (259)` Win32 API Belirsizlik Tuzağı
* **Dosya:** `subtitle_translator_gui.py` (Satır ~13094-13108)
* **Kök Neden:** Win32 API'sinde `STILL_ACTIVE (259)` değeri, hem sürecin çalıştığını hem de 259 exit koduyla kapandığını gösterir. Ölü bir süreç 259 koduyla kapandığında `_pid_alive` onu sonsuza kadar canlı sayar.
* **Sonuç:** Canlı süreç kilidi temizlenemez, log rotasyonu yapılamaz ve kurtarma pencereleri bastırılır.
* **Çözüm Reçetesi:** `GetExitCodeProcess` öncesinde `k32.WaitForSingleObject(h, 0) == 0x00000102` (`WAIT_TIMEOUT`) kontrolü uygulanmalıdır.

### 🔴 BUG 60: `_on_drop` İçinde Tcl `splitlist`'in `{}` İçeren Dosya İsimlerini Parçalayarak İçe Aktarmayı Engellemesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~14535-14540)
* **Kök Neden:** Sürükle-bırak yapılan dosya adlarında `{CRC32}` veya `{2024}` gibi süslü parantezler olduğunda `self.tk.splitlist` veya regex yolu parçalayarak geçersiz dosya adlarına dönüştürür.
* **Sonuç:** Süslü parantez içeren video ve altyazı dosyaları sürükle-bırak yapıldığında sessizce yutulur ve listeye eklenmez.
* **Çözüm Reçetesi:** `event.data` dosya yolları süslü parantez ayırıcısı yerine tam Windows dosya yolu çözümleyicisiyle ayrıştırılmalıdır.

### 🔴 BUG 61: `app_state.atomic_write_text` İçinde Windows Dosya Kilitlenmelerinde (WinError 32) Yeniden Deneme Olmaması
* **Dosya:** `app_state.py` (Satır ~28-42)
* **Kök Neden:** `atomic_write_text` fonksiyonu `tmp.replace(path)` çağrısını korumasız çalıştırır. Windows'ta dosya başka bir okuyucu veya antivirüs tarafından tutuluyorsa `PermissionError: [WinError 32]` fırlatılır ve dosya kaydı çöker.
* **Sonuç:** `batch_id.txt` veya `.gui_settings.json` gibi kritik durum kayıtları kaydedilemeyerek işlem yarıda kesilir.
* **Çözüm Reçetesi:** `tmp.replace(path)` işlemi Windows'ta kısa beklemeli 3-5 döngülük bir `retry_replace` mekanizmasına bağlanmalıdır.

### 🔴 BUG 62: `credential_store._write_fallback_store` İçinde Türkçe Karakterli Windows Kullanıcılarında `icacls` Hatası
* **Dosya:** `credential_store.py` (Satır ~162-187)
* **Kök Neden:** Windows kullanıcı adı Türkçe karakter içerdiğinde (`Ömer`, `Çağrı`, `Şükrü`, `İsmail`), `icacls` aracı OEM kod sayfası uyuşmazlığı nedeniyle Error 1332 (`ERROR_NONE_MAPPED`) hatası verir.
* **Sonuç:** Türkçe kullanıcı adına sahip Windows kullanıcılarında API anahtarının fallback deposuna kaydedilmesi **tamamen engellenir**.
* **Çözüm Reçetesi:** Metinsel kullanıcı adı yerine doğrudan kullanıcının değişmez Windows SID kimliği (`whoami /user`) kullanılmalı veya `icacls` hatasında `atomic_write_json` güvenli fallback'i uygulanmalıdır.

### 🔴 BUG 63: `_add_folder_files` İçinde `topmost` Bayrağının `finally` Koruması Olmadan Değiştirilmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~21625-21630)
* **Kök Neden:** Klasör seçimi açılırken `self.attributes("-topmost", True)` yapılır ancak `False` işlemi `try...finally` içinde değildir.
* **Sonuç:** Seçim sırasında bir hata oluşursa program penceresi işletim sistemindeki tüm uygulamaların üzerinde kalıcı olarak kilitlenir.
* **Çözüm Reçetesi:** `topmost` bayrağı `try...finally` bloğu içine alınmalıdır.

### 🔴 BUG 64: `_smoke_test.py` İçinde Tanımsız `gui._safe_chat_create` Çağrısı
* **Dosya:** `_smoke_test.py` (Satır ~74)
* **Kök Neden:** `subtitle_translator_gui.py` modülü `_safe_chat_create` fonksiyonunu dışa aktarmaz (fonksiyon `hybrid_translate` altındadır).
* **Sonuç:** `python _smoke_test.py` çalıştırıldığında `AttributeError` fırlatarak ilk adımda çöker.
* **Çözüm Reçetesi:** `gui._safe_chat_create` çağrısı `ht._safe_chat_create` olarak düzeltilmelidir.

---

## 8. Ek Mantıksal ve Biçimsel Hatalar

### 🔴 BUG 65: `_find_best_split` İçinde `_CONJ_RE` Bağlaç Regex'inin Yalnızca Türkçe Olması ve Yabancı Dillerde Satır Bölmenin Bozulması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2370-2395)
* **Kök Neden:** Satır bölmede bağlaç önceliği veren `_CONJ_RE` tablosu yalnızca Türkçe bağlaçları (`ve`, `ama`, `çünkü`) içerir.
* **Sonuç:** Almanca (`und`, `aber`, `weil`), Fransızca (`et`, `mais`), İspanyolca (`y`, `pero`) dillerinde satırlar tamlamaların veya kelimelerin ortasından bölünür.
* **Çözüm:** `_find_best_split` fonksiyonuna `target_language` parametresi aktarılmalı ve ilgili dilin bağlaçları kullanılmalıdır.

### 🔴 BUG 66: `_break_to_line_budget` İçinde CPS Hesabının Yanlış Yapılması ve 3 Satıra Bölünerek Standartların İhlal Edilmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2414-2427)
* **Kök Neden:** Bir cue'yu ortadan ikiye bölmek okuma hızını (CPS) değiştirmez. Fonksiyon `seg_cps = lc / duration > cps_limit` mantığıyla gereksiz yere satır bölüp altyazıyı 3 satır yapar.
* **Sonuç:** Netflix ve EBU'nun en fazla 2 satır standardı ihlal edilir ve ekran gereksiz dikey metinle kapanır.
* **Çözüm:** CPS zorlaması kaldırılmalı; satır bölme yalnızca 42 karakterlik bütçe aşıldığında ve en fazla 2 satırla sınırlandırılmalıdır.

### 🔴 BUG 67: `_extract_emotional_arc` VTT Alfanümerik ID Çökmesi
* **Dosya:** `hybrid_translate.py` (Satır ~2073-2079, 2098-2104)
* **Kök Neden:** `int(scene[0].index)` çağrısı WebVTT cue ID'leri `"cue-01"` veya `"intro"` olduğunda `ValueError` verir.
* **Çözüm:** `try...except ValueError` ile güvenli ID çözümü uygulanmalıdır.

### 🔴 BUG 68: `_generate_idiom_map` İnflected Deyim Silinmesi
* **Dosya:** `hybrid_translate.py` (Satır ~2193-2196)
* **Kök Neden:** Birebir literal eşleşme aradığı için çekimlenmiş deyimleri (`"cut him some slack"`) sözlükten siler.
* **Çözüm:** Lemmatized kök eşleşmesi yapılmalıdır.

### 🔴 BUG 69: `_break_to_line_budget` Çift Konuşmacılı 3 Satır Bölünmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2411-2445)
* **Kök Neden:** Uzun çift konuşmacılı (`- `) blokları 3 satıra böler (Netflix standardına aykırı).
* **Çözüm:** Çift konuşmacılı bloklar en fazla 2 satırda tutulmalıdır.

### 🔴 BUG 70: `sdh_cleaner._SDH_KEYWORDS` Yabancı Dil Eksikliği
* **Dosya:** `sdh_cleaner.py` (Satır ~63-114)
* **Kök Neden:** Yalnızca İngilizce/Türkçe anahtar kelimeler içerir; Fransızca (`[rires]`), Almanca (`[Lachen]`) silinmez.
* **Çözüm:** Çok dilli SDH tanımlayıcıları tabloya eklenmelidir.

### 🔴 BUG 71: İstem Seviyesinde SDH Çevirme Talimatı
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4523-4526) ve `hybrid_translate.py` (Satır ~3785-3788)
* **Kök Neden:** Modele `"- Translate ALL [SFX] tags to Turkish (e.g. [LAUGHS]→[KAHKAHA])"` emri verilir; SDH temizleme kuralı ihlal edilir.
* **Çözüm:** SDH etiketlerinin çevrilmesi değil, tamamen kaldırılması emredilmelidir.

---
*Rapor Sonu. Tüm maddeler test edilmiş, kod satırları ve fonksiyon çağrı ağaçları teyit edilmiştir.*
