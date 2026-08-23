# Yeni Derin Kod Tabanı Bug, Hata ve İyileştirme Rehberi (Part 2)
> **Tarih:** 2026-08-20  
> **Kullanım Amacı:** `DERIN_BUG_DENETIMI_2026-08-20.md` dosyasındaki 48 hatanın DIŞINDA, kod tabanının güncel hali üzerinde yapılan derinlemesine denetimlerde tespit edilen 100% YENİ ve ÖZGÜN mimari, mantıksal, veri yapısal, regex ve post-processing hatalarını, kök nedenlerini ve düzeltme reçetelerini içerir.

---

## 📌 YENİ TESPİT EDİLEN DERİN HATALAR LİSTESİ

### 🔴 BUG 1: `auto_locked_proper_nouns` İçinde `position > 1` Mantık Hatası Nedeniyle Cümle Başındaki 2 Kelimeli İsimlerin İkinci Kelimesinin Bağımsız (Standalone) Sanılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4658)
* **Kök Neden:** 
  - `auto_locked_proper_nouns` içinde çok kelimeli isimlerin tekil kelimelerini ayıklamak için `before_caps = position > 1 and forms[position - 1][:1].isupper()` yazılmıştır.
  - Cümle başındaki `"John Smith went to..."` gibi bir yapıda:
    - `position = 0`: `"John"` (forms[0]).
    - `position = 1`: `"Smith"` (forms[1]).
    - `"Smith"` için `position > 1` (`1 > 1`) değerlendirmesi `False` döner! Böylece `forms[0]` (`"John"`) hiç kontrol edilmez ve `before_caps = False` kalır.
    - Bir sonraki kelime (`"went"`) küçük harfli olduğu için `after_caps = False` olur.
    - `not before_caps and not after_caps` ifadesi `True` vererek `"Smith"` kelimesini hatalı şekilde `standalone` (bağımsız tekil isim) sayar.
* **Sonuç:** `"John Smith"`, `"Mary Jane"`, `"Albert Einstein"`, `"James Bond"` gibi iki kelimeli özel adlar cümle başında geçtiğinde, soyadları/ikinci isimleri hatalı şekilde "bağımsız özel ad" ilan edilerek kilitli sözlüğe eklenir ve tekil terim kurallarına sokulur.
* **Düzeltme Reçetesi:** 
  - Satır 4658'deki `position > 1` koşulu `position > 0` yapılmalıdır:
  ```python
  before_caps = position > 0 and forms[position - 1][:1].isupper()
  ```

---

### 🔴 BUG 2: Parçalı Cue Birleştirme (`_maybe_merge_cues`) Sonrasında `rebalance_cue_fill_pairs`'in Birleşmiş Blokları Orijinal Cue Haritasıyla Karşılaştırarak Yanlış Pozitif Üretmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~22184-22240, ~26365, ~33211, ~34953, ~35805, ~37372)
* **Kök Neden:** 
  - Çeviri akışlarında sıra şu şekildedir:
    ```python
    self._maybe_rebalance_cue_fill(self._maybe_merge_cues(blocks, file_path=orig_path), cues)
    ```
  - `_maybe_merge_cues` 2 veya daha fazla cue'yu birleştirdiğinde (örneğin cue 2 ve cue 3 birleştiğinde), dönen listedeki cue 2 artık 2 ve 3'ün birleşik metnini taşır.
  - Ancak fonksiyona ikinci parametre olarak verilen `cues`, orijinal birleştirilmemiş kaynaktır (`src_map['2']` yalnızca cue 2'nin kısa kaynak metnini taşır).
  - `_cue_fill_imbalances` fonksiyonu cue 2'nin birleşmiş uzun çevirisini orijinal cue 2'nin kısa kaynak metniyle karşılaştırır; uzunluk oranını 2.2 katından büyük bularak yanlış alarm verir.
* **Sonuç:** Zaten başarıyla birleştirilmiş ve dengelenmiş olan cue'ların başındaki kelimeler önceki cue'ya hatalı bir şekilde kaydırılmaya çalışılır ve düzgün diyaloglar parçalanır.
* **Düzeltme Reçetesi:** 
  - `_maybe_rebalance_cue_fill` birleştirme işleminden ÖNCE çalıştırılmalı ya da birleştirilmiş bloklar için `src_map` zaman damgası aralığına göre (`_delivery_source_map`) eşleştirilmelidir.

---

### 🔴 BUG 3: Sezon Anlam Mutabakatında (`_maybe_semantic_reconciliation`) Bölüm Kısıtı (`before_episode`) Verilmeden `build_hint()` Çağrılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~21524-21526)
* **Kök Neden:** 
  - Sezon anlam mutabakatı çalıştırılırken `sm_obj, _season, _episode = self._series_mem_for(source_path)` ile dizi hafızası nesnesi ve o dosyanın bölüm numaraları alınır.
  - Ancak satır 21525'te `canon_hint = sm_obj.build_hint() if sm_obj else ""` şeklinde parametresiz çağrı yapılır (`before_episode` iletilmez).
* **Sonuç:** 
  - Örneğin kullanıcı 1. sezon 1. bölümü mutabakata soktuğunda, dizi hafızasında daha önce işlenmiş olan 10. bölümün terimleri, karakter tarzları ve olay örgüsü kuralları 1. bölümün mutabakat istemine sızdırılır (kronolojik sınır ihlal edilir).
* **Düzeltme Reçetesi:** 
  - Satır 21525'teki çağrı `before_episode` parametresi ile güncellenmelidir:
  ```python
  canon_hint = sm_obj.build_hint(before_episode=(_season, _episode)) if sm_obj else ""
  ```

---

### 🔴 BUG 4: `detect_address_register_mix` İçinde Çoğul "Siz" İfadelerinin ve İsim Çekimlerinin Hitap Karışıklığı Olarak Raporlanması (Plural "Siz" False Positive)
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4206-4258)
* **Kök Neden:** 
  - `_ADDRESS_FORMAL_RE` hem kibar tekil "siz" hem de çoğul "siz" (gruba hitap: *"Çocuklar neredesiniz?"*, *"Arkadaşlar buraya gelin"*, *"Hepiniz dinleyin"*) eklerini ayırt etmeksizin resmi hitap sayar.
  - Ayrıca `has_formal = bool(_ADDRESS_FORMAL_RE.search(value))` ifadesi token bazlı kök kontrolü yapmadan tüm metin üzerinde regex arar.
* **Sonuç:** 
  - Karakterlerin birbirine "sen" diye hitap ettiği samimi bir filmde, bir karakter topluluğa veya gruba seslendiğinde sistem bütün dosyayı `SCAN_ADDRESS_REGISTER` gerekçesiyle şüpheli ilan eder; gereksiz yere LLM Critic/onarım geçişlerine sokar.
* **Düzeltme Reçetesi:** 
  - Gruba hitap belirteçleri (`hepiniz`, `çocuklar`, `arkadaşlar`, `beyler`, `millet`) içeren cümleler çoğul kabul edilerek resmiyet sayacından muaf tutulmalı; `_ADDRESS_FORMAL_RE` de `_ADDRESS_INFORMAL_RE` gibi token bazlı kök filtresinden geçirilmelidir.

---

### 🔴 BUG 5: `CANONICAL_TURKISH_NAMES` ve `auto_locked_proper_nouns` Nedeniyle Modern Dizi ve Filmlerdeki Batılı Karakter İsimlerinin (`Adam`, `David`, `Joseph`, `Jacob`, `Mary`) Zorla İslami/Geleneksel İsimlere (`Âdem`, `Davut`, `Yusuf`, `Yakup`, `Meryem`) Dönüştürülmesi
* **Dosya:** `prompt_constants.py` (Satır ~208-221) ve `subtitle_translator_gui.py` (Satır ~4672-4675)
* **Kök Neden:** 
  - `CANONICAL_TURKISH_NAMES` tablosuna mitolojik figürlerin (*Sisyphus*, *Icarus*, *Achilles*) yanı sıra modern Batı isimleri olan `adam` $\rightarrow$ `Âdem`, `david` $\rightarrow$ `Davut`, `joseph` $\rightarrow$ `Yusuf`, `jacob` $\rightarrow$ `Yakup`, `isaac` $\rightarrow$ `İshak`, `mary` $\rightarrow$ `Meryem`, `alexander` $\rightarrow$ `İskender` eklenmiştir.
  - `auto_locked_proper_nouns` kaynakta 3+ kez geçen kelimeleri otomatik kilitler.
* **Sonuç:** 
  - Günümüz Amerikan/İngiliz dizi veya filmlerinde başrol karakterinin adı *David*, *Adam*, *Jacob* veya *Mary* olduğunda, sistem istemine `"David" -> "Davut"`, `"Adam" -> "Âdem"`, `"Mary" -> "Meryem"` kuralları kilitlenir.
  - Modern diyaloglarda *"David, don't do that!"* repliği *"Davut, bunu yapma!"*, *"Where is Mary?"* repliği *"Meryem nerede?"* şeklinde absürt bir çeviriye dönüşür.
* **Düzeltme Reçetesi:** 
  - Modern kişi adları (`adam`, `david`, `joseph`, `jacob`, `isaac`, `mary`, `alexander`) `CANONICAL_TURKISH_NAMES` tablosundan çıkarılmalı; bu tablo yalnızca saf mitolojik/antik figürlerle (*Sisyphus*, *Icarus*, *Achilles*, *Heracles*, *Aristotle*, *Pythagoras*) sınırlandırılmalıdır.

---

### 🔴 BUG 6: `fix_source_lowercase_apostrophes` İçinde Diyalog Çizgisinin (`- `) Satır Başı Sayılmaması Nedeniyle İlk Kelimelerin Küçük Harfe Zorlanması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4403-4427 ve ~5366)
* **Kök Neden:** 
  - Fonksiyon `at_line_start = not value[line_start:match.start()].strip()` ifadesiyle kelimenin satır başında olup olmadığını denetler.
  - Altyazı diyaloglarında satırlar `- ` (tire + boşluk) veya tırnakla başlar. `value[line_start:match.start()].strip()` değeri `"-"` döndüğü için `at_line_start = False` olur.
* **Sonuç:** 
  - Satır başındaki `"- Pain'i dindiremedik."` cümlesi diyalog başında olmasına rağmen `at_line_start = False` kabul edilir ve `stem.lower()` ile `"- paini dindiremedik."` haline getirilerek cümlenin ilk harfi hatalı biçimde küçük harfe dönüştürülür.
* **Düzeltme Reçetesi:** 
  - `at_line_start` hesabı öncesinde satır başındaki diyalog çizgileri (`-–—`), tırnaklar ve parantezler temizlenmelidir:
  ```python
  at_line_start = not value[line_start:match.start()].strip(" \t-–—\"'“‘(«[")
  ```

---

### 🔴 BUG 7: `turkish_suffix_for_stem` İçinde İyelik ve İyelik+Hâl Eklerinin (`-sında`, `-sinde`, `-sından`, `-sine`, `-sini`) Bulunmaması Nedeniyle Ek Uyumunun Bozulması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4288-4330 ve ~4452)
* **Kök Neden:** 
  - `_TR_SUFFIX_KEYS` tablosunda yalnızca yalın hâl ekleri bulunur; 3. tekil iyelik ve iyelik+hâl birleşik ekleri yer almaz.
  - `normalize_foreign_exonyms` fonksiyonu `"West'sinde"` $\rightarrow$ `"Batı"` dönüşümü yaptığında ek tanınmaz ve `"Batı'sinde"` şeklinde hatalı ve uyumsuz bir Türkçe üreterek altyazıyı bozar.
* **Düzeltme Reçetesi:** 
  - `_TR_SUFFIX_KEYS` ve `_tr_suffix_forms` tablolarına `pos3_loc` (`sında/sinde`), `pos3_abl` (`sından/sinden`), `pos3_dat` (`sına/sine`), `pos3_acc` (`sını/sini`) ek grupları eklenmelidir.

---

### 🔴 BUG 8: `normalize_foreign_titles` İçinde `Mr.`, `Mrs.`, `Miss`, `Ms.` Kısaltmalarının Büyük Harfli / Bağırma Repliklerinde (`MR.`, `MISS`) Eşleşmemesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~4342-4354)
* **Kök Neden:** 
  - `_FOREIGN_TITLE_MAP` içinde `Professor`, `Monsieur`, `Madame`, `Señor` için `re.IGNORECASE` verilirken `Mr\.?`, `Mrs\.?`, `Miss`, `Ms\.?` için `re.IGNORECASE` bayrağı konulmamıştır.
* **Sonuç:** 
  - Altyazılardaki büyük harfli bağırma sahnelerinde (`[SHOUTING] MR. WATSON!`, `MISS SMITH, RUN!`), `Professor` Türkçeleştirilirken, `MR.` ve `MISS` etiketleri İngilizce bırakılır.
* **Düzeltme Reçetesi:** 
  - Tüm unvan regex'leri `re.IGNORECASE` veya büyük harfe duyarlı karşılık haritasıyla (`"MR."` $\rightarrow$ `"BAY"`, `"Mr."` $\rightarrow$ `"Bay"`) güncellenmelidir.

---

### 🔴 BUG 9: `quoted_work_titles` İçinde Düz ve Eğik Kesme İşaretlerinin (`'`, `’`) İngilizce Kısaltmalarda (`don't`, `it's`, `we'll`) Eser Adı Sanılması ve İki Kısaltma Arasındaki Cümlelerin Sözlüğü Kirletmesi
* **Dosya:** `hybrid_translate.py` (Satır ~7177-7193)
* **Kök Neden:** 
  - `_QUOTED_TITLE_QUOTES = "\"'\u201c\u201d\u00ab\u00bb\u2018\u2019"` kümesine tek tırnak (`'`) ve kesme (`’`) karakterleri harf-içi kesme denetimi yapılmadan dahil edilmiştir.
  - `_QUOTED_TITLE_RE` regex'i, `"I don't think it's right"` cümlesinde `don't`'un kesme işareti ile `it's`'in kesme işaretini tırnak çifti zanneder ve aradaki `"t think it"` dizesini eser adı olarak yakalar.
* **Sonuç:** 
  - İngilizce kaynak metindeki her iki kısaltma arasında kalan rastgele kelime öbekleri (`"t have done that, it"`, `"s what she"`) `titles` kümesine "eser adı" olarak eklenir; sözlük temizleme guard'ı (`drop_quoted_work_title_terms`) geçerli terimleri yanlışlıkla sözlükten düşürür.
* **Düzeltme Reçetesi:** 
  - Tek tırnak ve kesme işaretlerinin (`'`, `’`) tırnak olarak sayılabilmesi için harf ortasında olmaması (`(?<!\w)['\u2019]...['\u2019](?!\w)`) şartı getirilmelidir.

---

### 🔴 BUG 10: `sdh_cleaner.strip_labels_by_source` İçinde `_TR_PLAIN_SPEAKER_LABEL_RE`'nin Kaynak Doğrulaması Yapmadan Numaralandırma, Liste ve Başlık Öneklerini (`Problem:`, `Solution:`, `Adım 1:`, `Kural:`, `Not:`, `Bölüm:`) Konuşmacı Sanarak Silmesi
* **Dosya:** `sdh_cleaner.py` (Satır ~1032-1038 ve ~1146)
* **Kök Neden:** 
  - `_TR_PLAIN_SPEAKER_LABEL_RE` büyük harfle başlayan ve iki nokta (`: `) ile biten her 1-30 karakterlik sözcüğü konuşmacı etiketi olarak tanımlar.
  - `strip_labels_by_source` kaynakta herhangi bir köşeli parantez gördüğünde bu regex'i çeviri metnine koşulsuz uygular.
* **Sonuç:** 
  - Diyalog içinde geçen ve repliğin anlamlı parçası olan `"Sorun: Yeterli elektrik yok"`, `"Çözüm: Yeni bir jeneratör"`, `"Kural 1: Sessiz olun"`, `"Adım 1: Nişan alın"`, `"Not: Gelmeyeceğim"` gibi tüm liste, kural, adım ve problem/çözüm önekleri konuşmacı etiketi zannedilerek satır başından tamamen silinir; repliklerin listeleme yapısı yok edilir.
* **Düzeltme Reçetesi:** 
  - Liste/önek anahtar kelimeleri (`Problem`, `Solution`, `Sorun`, `Çözüm`, `Kural`, `Adım`, `Not`, `Bölüm`, `Rule`, `Step`, `Note`, `Chapter`, `One`, `Two`, `Bir`, `İki`) konuşmacı filtresinden muaf tutulmalı ve yalnızca kaynak konuşmacı adıyla (`_target_has_source_plain_speaker_label`) eşleşen etiketler silinmelidir.

---

### 🔴 BUG 11: `_normalize_delivery_ids` İçinde `previous = -1` Başlangıcı Nedeniyle Başlık İmzasına Geçersiz `0` Numarası Verilmesi ve Silinen Cue'ların Ardında Numara Boşlukları (Gaps) Bırakılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~5025-5040)
* **Kök Neden:** 
  - `_normalize_delivery_ids` fonksiyonunda `previous = -1` ile başlanır. En başa eklenen imza bloğu için `current = previous + 1` (`-1 + 1 = 0`) hesaplanır ve ilk cue numarası `"0"` yapılır.
  - Diğer cue'lar için `current = max(requested, previous + 1)` kullanılır. Aradaki bir müzik veya SDH cue'su (örneğin 3. cue) silindiğinde, sonraki cue `max(4, 2) = 4` yapılarak dosya içinde `1, 2, 4, 5` şeklinde numara boşlukları bırakılır.
* **Sonuç:** 
  - SubRip (.SRT) standardına göre altyazı numaralandırması kesinlikle `1` ile başlamalı ve `1, 2, 3, 4...` şeklinde aralıksız artmalıdır. `0` numaralı cue veya numara boşlukları içeren dosyalar birçok Smart TV (LG, Samsung), donanımsal medya oynatıcı ve katı SRT ayrıştırıcısı tarafından reddedilir veya zaman senkronu bozulur.
* **Düzeltme Reçetesi:** 
  - `_normalize_delivery_ids` fonksiyonu her bloğu kesinlikle `1`'den başlatıp `1, 2, 3... N` şeklinde ardışık olarak yeniden numaralandırmalıdır:
  ```python
  def _normalize_delivery_ids(blocks: list) -> list:
      return [
          (str(i), ts, text)
          for i, (_idx, ts, text) in enumerate(blocks or [], start=1)
      ]
  ```

---

### 🔴 BUG 12: `_rebalance_line_break` İçinde HTML Etiketlerinin (`<i>`, `<b>`, `</b>`, `</i>`) Temizlenmeden Kelime Kontrolü Yapılması Nedeniyle İtalik Satırlarda Dengelemenin Çalışmaması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2606-2620)
* **Kök Neden:** 
  - `strip("\"'([{")` ve `strip("\"')]} ")` temizleme listelerinde `<` ve `>` (HTML etiket karakterleri) yer almaz.
  - Satır başındaki `"<i>için"` veya satır sonundaki `"ve</i>"` kelimeleri ayrıştırıldığında `head` değeri `"<i>için"`, `tail` değeri `"ve</i>"` olarak kalır.
* **Sonuç:** 
  - `_LINE_PULL_UP_WORDS` ve `_LINE_PUSH_DOWN_WORDS` listeleriyle eşleşme sağlanamaz ve italik formatlı satırlarda sarkan bağlaç/edat dengelemesi tamamen devre dışı kalır.
* **Düzeltme Reçetesi:** 
  - `head` ve `tail` kelime kontrollerinde HTML etiketleri (`<[^>]+>`) `FORMAT_TAG_RE.sub("", word)` ile temizlenmeli ve etiketli satırlarda kelime taşındığında tag bütünlüğü korunmalıdır.

---

### 🔴 BUG 13: `subtitle_formats.parse_ass` İçinde Konuşmacı Adının (`Name: `) Baştaki ASS Konum/Override Etiketlerinin (`{\an8}`, `{\pos}`) Önüne Eklenmesi ve Tüm Konum Etiketlerinin Silinmesi
* **Dosya:** `subtitle_formats.py` (Satır ~830-834)
* **Kök Neden:** 
  - `parse_ass` fonksiyonunda konuşmacı sütunu varsa satır başına doğrudan `text = f"{name}: {text}"` eklenir.
  - Kaynak metin `{\an8}I don't believe you.` (üst yazı/konum etiketi) içeriyorsa, çıktı `"John: {\an8}I don't believe you."` haline gelir.
* **Sonuç:** 
  - `_clean_src` ve `restore_format_tags` fonksiyonlarındaki regex'ler (`_LEAD_OVERRIDE_RE = re.compile(r'^\s*(\{\\[^}]*\})+')`) baştaki konum etiketlerini satırın EN BAŞINDA arar.
  - Satır `"John: "` ile başladığı için konum etiketi (`{\an8}`) baştaki etiket olarak tanınmaz; çeviri sonrası `restore_format_tags` aşamasında tüm ekran üstü/özel konumlu ASS altyazılarının (`{\an8}`, `{\pos}`) konum bilgisi kalıcı olarak kaybolur ve altyazı varsayılan alt konuma düşer.
* **Düzeltme Reçetesi:** 
  - `name: ` öneki eklenirken metin baştaki `{...}` override bloklarını koruyacak şekilde eklenmelidir:
  ```python
  lead_match = _LEAD_OVERRIDE_RE.match(text)
  if lead_match:
      lead = lead_match.group(0)
      text = f"{lead}{name}: {text[len(lead):].lstrip()}"
  else:
      text = f"{name}: {text}"
  ```

---

### 🔴 BUG 14: `_match_category` Fonksiyonunun Model Tarafından Döndürülen Şema Anahtar Kodlarını (`history_documentary`, `sci_fi`, `reality_street`) Eşleştiremeyip Otomatik Tespiti İptal Etmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~8713-8743)
* **Kök Neden:** 
  - `_match_category` yalnızca `categories` listesindeki Türkçe görüntüleme adlarını (`Tarih Belgeseli`, `Siyaset / Toplum Belgeseli`) arar.
  - OpenAI modelleri İngilizce sistem istemi verildiğinde JSON yanıtında sıklıkla şemanın anahtar kodunu (`{"category": "history_documentary"}` veya `{"category": "sci_fi"}`) döndürür.
* **Sonuç:** 
  - `_match_category` `"history_documentary"` dizesini `"Tarih Belgeseli"` ile eşleştiremez; `None` döndürür.
  - `detect_content_type_with_ai` başarılı API çağrısına ve modelin doğru tespitine rağmen kategoriyi bulamamış sayarak `Otomatik` (varsayılan genel şema) seçer; türe özgü terminoloji, ton ve argo kurallarını yüklemez.
* **Düzeltme Reçetesi:** 
  - `_match_category` fonksiyonu hem Türkçe adları hem de `CONTENT_SCHEMAS` sözlüğündeki anahtarları (`key` ve `key.replace("_", " ")`) kontrol edecek şekilde genişletilmelidir:
  ```python
  for key, schema in CONTENT_SCHEMAS.items():
      if _schema_name_key(key) == d or _schema_name_key(key.replace("_", " ")) == d:
          return schema["name"]
  ```

---

### 🔴 BUG 15: `translation_memory._fuzzy_semantically_compatible` İçinde `source_tokens == candidate_tokens` Eşitlik Şartı ve `"â€™"` Mojibake Karakteri Nedeniyle Fuzzy (Bulanık) TM Eşleştirmesinin Tamamen İptal Olması
* **Dosya:** `translation_memory.py` (Satır ~44-72 ve ~417)
* **Kök Neden:** 
  - `_fuzzy_semantic_anchors` fonksiyonu olumsuzluk (`not/never`), zamir (`he/she`), rakam ve kiplik eklerini (`can/must`) denetlemek üzere tasarlanmış ancak hiçbir yerde çağrılmamıştır.
  - `lookup_fuzzy` içinde çağrılan `_fuzzy_semantically_compatible` fonksiyonu, `source_tokens == candidate_tokens` şartıyla iki cümlenin birebir aynı kelimelere sahip olmasını zorunlu kılar.
  - Satır 64 ve 68'de UTF-8 bozulması (mojibake) sonucu `token.replace("â€™", "'")` yazılmıştır.
* **Sonuç:** 
  - Fuzzy Matching (%85+ benzerlikteki cümleleri bulma) özelliği tamamen çöker. Tek bir kelimesi farklı olan hiçbir benzer cümle eşleşemez.
  - Çeviri Hafızası (TM) Fuzzy Modu hiçbir zaman sonuç üretemez hale gelmiştir.
* **Düzeltme Reçetesi:** 
  - `_fuzzy_semantically_compatible` fonksiyonu `_fuzzy_semantic_anchors(source) == _fuzzy_semantic_anchors(candidate)` karşılaştırması yapmalı ve mojibake karakteri (`"â€™"`) düzeltilmelidir (`"’"`):
  ```python
  def _fuzzy_semantically_compatible(source: str, candidate: str) -> bool:
      return _fuzzy_semantic_anchors(source) == _fuzzy_semantic_anchors(candidate)
  ```

---

### 🔴 BUG 16: `_redistribute_two_lines` İçinde `.split(" ")` Kullanılması Nedeniyle Çift Boşluklu Satırlarda 2. Satırın Başına Boşluk Karakteri (`\n `) Sızması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2656-2670)
* **Kök Neden:** 
  - `words = f"{first} {second}".split(" ")` ifadesi metindeki ardışık boşlukları boş dize (`""`) token'ı olarak listeye alır.
  - Bölme noktası (`cut`) bu boş token'a denk geldiğinde `right = " ".join(words[cut:])` ifadesi başında fazladan boşluk bulunan bir dize üretir (`" metin"`).
* **Sonuç:** 
  - SRT çıktısında 2. satırın başında boşluk (`\n metin`) oluşur; televizyon ve medya oynatıcılarında altyazıların sola/sağa yaslanma ve merkezlenme simetrisi bozulur.
* **Düzeltme Reçetesi:** 
  - `words` listesi oluşturulurken parametresiz split kullanılmalı ve `left`, `right` parçaları `strip()` edilmelidir:
  ```python
  words = f"{first} {second}".split()
  ```

---

### 🔴 BUG 17: `_midword_space_ids` Fonksiyonunun İngilizce Kaynak Sözcük ile Türkçeleşmiş Kelimeyi (`pyramids` $\leftrightarrow$ `Piram itler`) Doğrudan Eşleştirmeye Çalışması Nedeniyle Kelime Bölünmelerini Hiçbir Zaman Yakalayamaması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~3974-4002)
* **Kök Neden:** 
  - Fonksiyon, kaynak dildeki İngilizce kelimeleri (`source_keys = {"pyramids", "helicopter", "astronaut"}`) doğrudan çevirideki bitişik kelimelerle (`joined = "piramitler"`, `"helikopter"`, `"astronot"`) karşılaştırır: `_shift_token_key(joined) in source_keys`.
* **Sonuç:** 
  - Fonksiyonun yazılış amacı ve docstring'indeki örnek olan `"Piram itler"` veya `"Helikop ter"`, `"Astro not"` gibi modelin yanlışlıkla araya boşluk koyduğu hiçbir Türkçe kelime tespit edilemez (çünkü `"piramitler" != "pyramids"`).
  - Teslim denetimi `midword_space` sayacını hep `0` gösterir ve bozuk bölünmüş kelimeler son altyazıya sızar.
* **Düzeltme Reçetesi:** 
  - Fonksiyon ya Türkçe kelime dağarcığı (`vocabulary`) üzerinden kelime geçerliliğini denetlemeli ya da fonetik/Levenshtein benzerliği ile İngilizce kaynak kelime ile Türkçeleşmiş gövde arasındaki bağı kurmalıdır.

---

### 🔴 BUG 18: `_SHIFT_TOKEN_STOPS` Kümesinde Cümle Başı Sık Kullanılan Belirteç, Zaman Zarfı ve Zamirlerin (`Every`, `Everyone`, `Today`, `Bütün`, `Herkes`, `Bugün`) Bulunmaması Nedeniyle Yanlış Kayma Alarmları Üretilmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~9852-9892)
* **Kök Neden:** 
  - `_shift_tokens` fonksiyonu, büyük harfle başlayan sözcükleri (`"Everything"`, `"Today"`, `"Bütün"`, `"Herkes"`) özel ad ve kayma çapası (anchor) kabul eder.
  - `_SHIFT_TOKEN_STOPS` istisna listesi çok dar tutulmuş; `"every"`, `"everything"`, `"everyone"`, `"someone"`, `"something"`, `"nothing"`, `"always"`, `"never"`, `"today"`, `"yesterday"`, `"tomorrow"`, `"first"`, `"other"`, `"another"`, `"butun"`, `"herkes"`, `"hepsi"`, `"bugun"`, `"dun"`, `"yarin"` gibi cümle başında zorunlu büyük harfle başlayan genel sözcükler listeye dahil edilmemiştir.
* **Sonuç:** 
  - Cümle başındaki sıradan kelimeler "özel ad çapası" sanılır. Çeviride Türkçe karşılıkları farklı bir kelime olduğunda `tr_tokens & own_tokens` boş kalır; komşu bir cue'da benzer bir genel kelime geçtiğinde sistem 3+ cue'luk bölgeyi yanlışlıkla `OLASI CUE HİZALAMA/KAYMA SORUNU` (alignment shift) olarak loglar ve raporu kirletir.
* **Düzeltme Reçetesi:** 
  - `_SHIFT_TOKEN_STOPS` kümesi İngilizce ve Türkçe cümle başı yaygın belirteç, zaman zarfı, soru sözcüğü ve zamirleri içerecek şekilde genişletilmelidir.

---

### 🔴 BUG 19: `SeriesMemory.build_hint` İçinde `str(origin) < cutoff` Dize Karşılaştırması Nedeniyle Eski Sürüm/Farklı Basamaklı Bölüm Etiketlerinde (`s1e10` < `s1e2`) Kronolojik Sınırın İhlal Edilmesi
* **Dosya:** `series_memory.py` (Satır ~457-475)
* **Kök Neden:** 
  - `build_hint` fonksiyonu bölüm kökenini (`origin`) ve kesme noktasını (`cutoff`) karşılaştırırken `str(origin) < cutoff` şeklinde alfabetik dize karşılaştırması yapar.
  - Eski hafıza dosyalarında veya basamak sayısı farklı etiketlerde:
    - `"s1e10"` dizesi `"s1e2"` dizesinden alfabetik olarak küçüktür (`'1' < '2'`), bu yüzden 10. bölümün terim ve olayları 2. bölüme sızdırılır.
    - Yeni 3 basamaklı `cutoff` (`"s01e005"`) ile eski 1 basamaklı `origin` (`"s1e2"`) karşılaştırıldığında (`'1' > '0'`) 2. bölümün geçerli terimleri 5. bölümde engellenir.
* **Sonuç:** 
  - Dizi hafızasındaki spoiler/karakter kuralları kronolojik olarak ters akar; önceki bölümler sonraki bölümlerin terimlerini alır ya da meşru önceki bölüm kuralları yeni bölümlere aktarılamaz.
* **Düzeltme Reçetesi:** 
  - `origin` ve `cutoff` etiketleri sayı tuple'ına (`(season, ep)`) dönüştürülmeli ve sayısal olarak karşılaştırılmalıdır:
  ```python
  def _ep_key(tag):
      m = re.fullmatch(r"s(\d+)e(\d+)", str(tag or ""), re.I)
      return tuple(map(int, m.groups())) if m else None

  def allowed(origin):
      if not cutoff:
          return True
      if not origin:
          return not legacy_blocked
      o_key, c_key = _ep_key(origin), _ep_key(cutoff)
      if o_key and c_key:
          return o_key < c_key
      return str(origin) < cutoff
  ```

---

### 🔴 BUG 20: `ProjectMemory.detect_series_key` İçinde `[Ee][Pp]?(\d{1,3})` Regex'inin Kelime Sınırı (`(?<![A-Za-z])`) Olmaması Nedeniyle `Step.1`, `Keep.100`, `Deep.2` Gibi Sıradan Dosya Adlarını Dizi Bölümü Sanması
* **Dosya:** `project_memory.py` (Satır ~303-313)
* **Kök Neden:** 
  - `m2 = re.search(r'[Ee][Pp]?(\d{1,3})', name, re.IGNORECASE)` regex'i sol taraftan kelime sınırı (`(?<![A-Za-z])` veya `\b`) içermez.
  - `"Step 1"`, `"Keep 100"`, `"Deep 2"`, `"Rep 1"` gibi `ep` ile biten sıradan İngilizce kelimeleri `Episode` kısaltması sanır.
* **Sonuç:** 
  - Belgesel, eğitim videosu veya tekil film dosyaları hatalı şekilde TV Dizisi bölümü (`EP001`, `"EP100"`) olarak sınıflandırılır; tekil dosyalar dizi hafızası altına kaydedilerek gereksiz dizi hafıza dosyaları üretilir.
* **Düzeltme Reçetesi:** 
  - Regex sol tarafa kelime sınırı (`(?<![A-Za-z])`) eklenerek güncellenmelidir:
  ```python
  m2 = re.search(r'(?<![A-Za-z])[Ee][Pp]?[ ._\-]?(\d{1,3})(?!\d)', name, re.IGNORECASE)
  ```

---

### 🔴 BUG 21: `_repair_untranslated_sync` İçinde `ctx` ve `next_ctx` Alanlarının `{"i": idx, "t": text}` Nesneleri Yerine Düz Dize Listesi (`[text1, text2]`) Olarak Paketlenmesi ve Sistem İstemi Şemasıyla Çelişmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~8054-8065)
* **Kök Neden:** 
  - Ana çeviri akışlarında (`build_requests`, `ht.build_batch_requests`), `ctx` ve `next_ctx` bağlam listeleri modelin cue numarasıyla metni ayırt edebilmesi için `[{"i": idx, "t": clean_text}, ...]` nesne listesi biçimindedir ve sistem istemi bu şemayı tanımlar.
  - Ancak `_repair_untranslated_sync` onarım modülünde `ctx` ve `next_ctx` alanları `[text for _idx, text in source_order[...]]` şeklinde ID'siz düz dize listesi olarak paketlenmiştir.
* **Sonuç:** 
  - Onarım modülü çağrıldığında modele gönderilen JSON payload şeması sistem istemindeki tanımla çelişir. Model bağlamdaki satırları çevrilecek hedef satır sanabilir veya beklenen JSON çıktı formatında numara eşleme karmaşası yaşayabilir.
* **Düzeltme Reçetesi:** 
  - `_repair_untranslated_sync` içindeki `ctx` ve `next_ctx` listeleri standart nesne formatına getirilmelidir:
  ```python
  ctx = [
      {"i": _idx, "t": text} for _idx, text in
      source_order[max(0, first_pos - 8):first_pos]
  ]
  next_ctx = [
      {"i": _idx, "t": text} for _idx, text in
      source_order[last_pos + 1:last_pos + 9]
  ]
  ```

---

### 🔴 BUG 22: `subtitle_formats._strip_srt_unsafe_ass_overrides` İçinde `\an[1-9]` Konum Etiketlerinin Güvenli Listeye Dahil Edilmemesi Nedeniyle `restore_format_tags`'in Kurtardığı Tüm `{\an8}` Üst Ekran Yazısı Konumlarının Satır 538'de Silinmesi
* **Dosya:** `subtitle_formats.py` (Satır ~438-450 ve ~538)
* **Kök Neden:** 
  - `restore_format_tags` fonksiyonu satır 482, 507 ve 532'de kaynak altyazıdaki `{\an8}` (ekran üstü tabela/başlık hizalaması) etiketlerini özenle korur ve çeviri satırının başına ekler.
  - Ancak fonksiyon satır 538'de `return _strip_srt_unsafe_ass_overrides(out)` çağrısı yapar.
  - `_strip_srt_unsafe_ass_overrides` içinde güvenli kabul edilen desen yalnızca `_SRT_SAFE_ASS_OVERRIDE_RE = re.compile(r'^\{(?:\\[ibus][01])+\}$', re.IGNORECASE)` (`\i0`, `\b1` vb.) olarak tanımlanmıştır; `\an[1-9]` hizalama etiketleri bu desene dahil edilmemiştir.
* **Sonuç:** 
  - Tüm VLC, mpv, PotPlayer ve Akıllı TV'lerin standart olarak desteklediği `{\an8}` üst ekran altyazı konum etiketleri, `restore_format_tags` çalışmasına rağmen satır 538'de sessizce ve tamamen silinir.
  - Ekran üstünde durması gereken tüm tabelalar, bölüm başlıkları, gazete manşetleri ve eşzamanlı ikinci konuşmacı altyazıları ekranın altına düşerek alt konuşmacının üzerine biner.
* **Düzeltme Reçetesi:** 
  - `_SRT_SAFE_ASS_OVERRIDE_RE` ve `_strip_srt_unsafe_ass_overrides` içindeki desen `\an[1-9]` etiketlerini destekleyecek şekilde güncellenmelidir:
  ```python
  _SRT_SAFE_ASS_OVERRIDE_RE = re.compile(r'^\{(?:\\[ibus][01]|\\an[1-9])+\}$', re.IGNORECASE)

  def _strip_srt_unsafe_ass_overrides(text: str) -> str:
      def _safe_part(match):
          block = match.group(0)
          if _SRT_SAFE_ASS_OVERRIDE_RE.fullmatch(block):
              return block
          safe = re.findall(r'\\[ibus][01]|\\an[1-9]', block, re.IGNORECASE)
          return "{" + "".join(safe) + "}" if safe else ""

      return _ASS_OVERRIDE_BLOCK_RE.sub(_safe_part, text)
  ```

---

### 🔴 BUG 23: `subtitle_translator_gui._ts_end_sec_gui` İçinde Bitiş Zamanının Boşlukla Ayrılmış İlk Token'ının Alınmaması Nedeniyle Koordinat/Stil Taşıyan Zaman Satırlarında (`00:01:20,000 --> 00:01:23,500 X1:100 Y1:200`) `ValueError: too many values to unpack` Çökmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~6201-6207)
* **Kök Neden:** 
  - `_TS_LINE_RE` regex'i SRT/VTT dosyalarındaki `00:01:20,000 --> 00:01:23,500 X1:100 Y1:200` veya `position:50% line:0` gibi bitiş zamanından sonraki ek koordinat/konum metinlerini kabul eder.
  - Ancak `_ts_end_sec_gui` fonksiyonu `parts[1]` metnini doğrudan iki nokta (`:`) ile bölmeye çalışır. Bu metin 5 parçaya ayrılır ve `h, m, s` değişkenlerine açılırken `ValueError: too many values to unpack (expected 3, got 5)` hatası fırlatır.
* **Sonuç:** 
  - Donanımsal oynatıcılardan, web riplerinden veya video düzenleme yazılımlarından dışa aktarılan koordinatlı altyazı dosyaları açıldığında veya süre/CPS hesaplaması yapıldığında uygulama beklenmedik şekilde çöker.
* **Düzeltme Reçetesi:** 
  - `_ts_end_sec_gui` ve `_ts_to_sec_gui` fonksiyonlarında `split()[0]` kullanılarak yalnızca ilk saat token'ı alınmalıdır:
  ```python
  def _ts_end_sec_gui(ts_str: str) -> float:
      parts = ts_str.split('-->')
      raw = parts[1] if len(parts) > 1 else parts[0]
      tokens = raw.strip().split()
      ts = (tokens[0] if tokens else "00:00:00.000").replace(',', '.')
      h, m, s = ts.split(':')[:3]
      return int(h) * 3600 + int(m) * 60 + float(s)
  ```

---

### 🔴 BUG 24: `subtitle_formats._repair_embedded_mac_roman_controls` İçinde `< 2` Kontrolü Nedeniyle Metinde Tek Bir Adet Windows-1252/MacRoman Kontrol Karakteri (`\x92` $\rightarrow$ `’`, `\x93` $\rightarrow$ `“`) Bulunduğunda Onarımın İptal Edilmesi ve Ham C1 Kontrol Karakterinin Altyazıya Sızması
* **Dosya:** `subtitle_formats.py` (Satır ~249-260)
* **Kök Neden:** 
  - `_repair_embedded_mac_roman_controls` fonksiyonunun başında `if sum("\x80" <= ch <= "\x9f" for ch in text) < 2: return text` şartı bulunmaktadır.
  - Metinde yalnızca bir adet Windows-1252/MacRoman kontrol karakteri (örneğin tek bir kesme işareti `It\x92s` veya tire `\x96`) olduğunda sayaç `1` döner; `1 < 2` ifadesi `True` vererek fonksiyonun onarım yapmadan çıkmasına yol açar.
* **Sonuç:** 
  - Kısa altyazı dosyalarında veya tekil kesme işareti içeren dosyalarda `\x92` gibi C1 kontrol baytları düzeltilemez. Metin ham kontrol baytlarıyla API'ye ve altyazı dosyasına yazılır.
* **Düzeltme Reçetesi:** 
  - Eşik `< 2` yerine `< 1` (veya `not any(...)`) olarak güncellenmelidir:
  ```python
  if not any("\x80" <= ch <= "\x9f" for ch in text):
      return text
  ```

---

### 🔴 BUG 25: `_wait_batch_hybrid`'in `ht.save_results`'a `src_cues` Parametresini Geçmemesi ve `[HATA]` İçeren Satırların Metninin Boşaltılarak (`""`) `parse_srt` Tarafından Altyazıdan Tamamen Silinmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~34488-34494) ve `hybrid_translate.py` (Satır ~14280-14286)
* **Kök Neden:** 
  - `_wait_batch_hybrid` içinde batch tamamlandığında `ht.save_results` çağrılırken `src_cues` parametresi verilmemektedir (`src_cues=None`).
  - `hybrid_translate.save_results` içinde `source_by_id` boş sözlük (`{}`) olarak kalır.
  - Satır 14280-14286'da `[HATA]` içeren (başarısız olan veya timeout'a uğrayan) satırlar kontrol edilirken:
    ```python
    if str(text).startswith("[HATA"):
        if src and not sdh_cleaner.src_is_sfx_only(src):
            srt_blocks[key] = (idx, ts, "[ÇEVİRİ EKSİK]")
            n_marked += 1
            continue
        srt_blocks[key] = (idx, ts, "")
        continue
    ```
    `src` boş olduğu için `if src` dalına girilemez ve `srt_blocks[key] = (idx, ts, "")` çalıştırılarak satırın metni boş dizeye dönüştürülür.
  - Ardından `_wait_batch_hybrid` içinde `pp = list(parse_srt(str(_stage_path)))` çalıştırılır. `parse_srt` fonksiyonu `if text:` kontrolü ile boş metinli cue'ları tamamen atar.
* **Sonuç:** 
  - Hata alan veya yanıtı eksik dönen tüm altyazı blokları `pp` listesinden sessizce ve tamamen silinir.
  - Post-processing aşamasının sonunda çalışan `_fill_hata_with_source` fonksiyonu yalnızca `pp` içindeki blokları taradığı için, silinen bu cue'ları göremez ve kaynak metinle dolduramaz.
  - Çıktı altyazı dosyasında satırlar kalıcı olarak yok olur (örneğin 1, 2, 5, 6 şeklinde numara ve diyalog kopuklukları oluşur).
* **Düzeltme Reçetesi:** 
  - `hybrid_translate.save_results` içinde `src` olmasa dahi `[HATA]` blokları boş dize yapılmamalı, `"[HATA]"` veya `"[ÇEVİRİ EKSİK]"` olarak korunmalıdır:
  ```python
  if str(text).startswith("[HATA"):
      if src and sdh_cleaner.src_is_sfx_only(src):
          srt_blocks[key] = (idx, ts, "")
      else:
          srt_blocks[key] = (idx, ts, "[HATA]")
      continue
  ```
  - Ayrıca `_wait_batch_hybrid` çağrısında `src_cues` parametresi iletilmelidir.

---

### 🔴 BUG 26: `_token_callback_for_model` İçinde `_verified_token_price` Çağrılırken `default_is_official=True` Verilmemesi Nedeniyle Resmi OpenAI API Kullanımında Tüm Yardımcı Model Maliyetlerinin Hesaplanamayıp `None` Dönmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~22393 ve ~1560-1568)
* **Kök Neden:** 
  - `_verified_token_price(model, base_url, *, default_is_official=False)` fonksiyonunda `default_is_official` parametresinin varsayılanı `False`'tur.
  - Kullanıcı varsayılan resmi OpenAI API'sini kullandığında `base_url` değeri boş dize (`""`) veya `None`'dır.
  - Satır 22393'te `_token_callback_for_model` fonksiyonu `price = _verified_token_price(model, base_url)` şeklinde parametresiz çağrı yapar.
  - `_verified_token_price` içindeki `if not str(base_url or "").strip() and not default_is_official: return None` koşulu tetiklenerek `None` döndürülür.
* **Sonuç:** 
  - Resmi OpenAI API'si (`api.openai.com`) kullanılmasına rağmen Critic, Polish, Native Reader, QC, Condense, Two-Wave ve Dosya Analizi gibi tüm yardımcı geçişlerin token maliyetleri `$0.00` sayılır.
  - Kullanılan tüm token'lar `_unknown_cost_tokens` sayacına aktarılır ve kullanıcı arayüzünde sürekli *"~0.0000$ + 45,210 token maliyeti sağlayıcı panelinden doğrulanmalı"* uyarısı çıkarak tahmini maliyet göstergesi bozulur.
* **Düzeltme Reçetesi:** 
  - Satır 22393'teki çağrıda `default_is_official=True` iletilmelidir:
  ```python
  price = _verified_token_price(model, base_url, default_is_official=True)
  ```

---

### 🔴 BUG 27: `sdh_cleaner.is_structural_sdh_label`'in Yalnızca Büyük Harf Kontrolü Yapması Nedeniyle Film/Dizi Başlıklarını, Bölüm İsimlerini ve Ekran Tabelalarını (`CHAPTER ONE`, `THE END`, `EMERGENCY EXIT`, `WARNING`, `POLICE DEPARTMENT`) SDH Sanıp Teslim Altyazısından Kalıcı Olarak Silmesi
* **Dosya:** `sdh_cleaner.py` (Satır ~254-283) ve `subtitle_translator_gui.py` (Satır ~3768-3772)
* **Kök Neden:** 
  - `is_structural_sdh_label` fonksiyonu, noktalama ile bitmeyen ve tamamı büyük harfli olan her dizeyi koşulsuz olarak bir "ses/efekt etiketi" (`SDH`) kabul eder.
  - `_delivery_removable_source_ids` fonksiyonunda `allow_caps_heuristic=True` olduğunda, `_source_cue_is_delivery_removable` fonksiyonu bu cue'ları `removable` kümesine ekler.
  - Çevirisi yapılmış `"BÖLÜM BİR"`, `"SON"`, `"ACİL ÇIKIŞ"`, `"UYARI"`, `"POLİS DEPARTMANI"` gibi geçerli tabelalar, bölüm başlıkları ve ekran yazıları `_filter_delivery_blocks` tarafından son altyazı dosyasından tamamen silinir.
* **Sonuç:** 
  - Filmin veya dizinin en kritik ekran yazıları (örneğin film sonundaki `THE END`, bölüm başındaki `CHAPTER 1`, mekân bildiren `LONDON POLICE STATION` veya kapıdaki `EMERGENCY EXIT`) izleyiciye hiçbir zaman gösterilmez; altyazıdan sessizce yok edilir.
* **Düzeltme Reçetesi:** 
  - `is_structural_sdh_label` veya `_source_cue_is_delivery_removable` içinde, bir dize parantez veya köşeli parantez içinde değilse (`[APPLAUSE]`), salt büyük harfli olması silinmesi için yeterli olmamalıdır; ses efekti/SDH anahtar kelimesi (`_SDH_KEYWORDS` veya `_DESCRIPTOR_MULTIWORD_RE`) içermesi zorunlu kılınmalı veya yaygın ekran yazısı kalıpları (`THE END`, `CHAPTER`, `EPISODE`, `WARNING`, `DANGER`, `EXIT`, `SEASON`, `PART`, `ACT`) beyaz listeye alınmalıdır:
  ```python
  _ON_SCREEN_TEXT_WHITELIST_RE = re.compile(
      r"^(?:THE END|CHAPTER(?:\s+\w+)?|EPISODE(?:\s+\w+)?|PART(?:\s+\w+)?|"
      r"ACT(?:\s+\w+)?|WARNING|DANGER|CAUTION|EMERGENCY(?:\s+EXIT)?|"
      r"POLICE(?:\s+DEPARTMENT)?|HOSPITAL|HOTEL|TO BE CONTINUED)$",
      re.IGNORECASE,
  )

  if _ON_SCREEN_TEXT_WHITELIST_RE.match(value):
      return False
  ```

---

### 🔴 BUG 28: `hybrid_translate.native_reader_pass` İçinde Her Chunk İstemi İçin Chunk Başına Limit Yerine Tüm Dosyanın Toplam Bütçesinin (`max_total_fixes`) İletilmesi ve Filmin İkinci Yarısındaki Tüm İyileştirmelerin Bütçe Aşımıyla Reddedilmesi
* **Dosya:** `hybrid_translate.py` (Satır ~4310 ve ~4203)
* **Kök Neden:** 
  - `max_total_fixes` fonksiyonun başında tüm dosya için `math.ceil(eligible_count * 0.20)` (örneğin 1200 satırlık filmde 240 satır) olarak hesaplanır.
  - Ancak satır 4310'da, her 150 satırlık alt chunk (`native_chunks`) için modele gönderilen istemde:
    ```python
    f"En fazla {max_total_fixes} satır düzelt (yaklaşık %20 sınırı). Sadece en emin olduğun satırları seç.\n\n"
    ```
    şeklinde tüm dosyanın 240 satırlık bütçesi yazılır.
  - 150 satırlık bir parça gören model, bütçeyi 240 sanarak ilk 3-4 chunk'ta 50-60 satırlık agresif düzeltmeler yapar.
  - Filmin 5. chunk'ına gelindiğinde toplam 240 kotası tamamen dolar.
  - 6, 7 ve 8. chunk'larda model API'ye çağrılıp para harcanmasına rağmen dönen tüm öneriler `total_fixed + len(unit) > max_total_fixes` denetimine takılarak `%100` oranında çöpe atılır (`total_cap_rejected`).
* **Sonuç:** 
  - Filmin ilk %40'lık bölümü aşırı düzeltilirken, filmin geri kalan %60'lık bölümü Native Reader tarafından hiç düzeltilemez ve API token'ları boşa harcanır.
* **Düzeltme Reçetesi:** 
  - İstemdeki sınır her chunk için `max(1, math.ceil(len(chunk) * MAX_FIX_RATIO))` olarak hesaplanmalı ve kalan bütçe (`max_total_fixes - total_fixed`) ile sınırlandırılmalıdır:
  ```python
  chunk_limit = min(
      max(1, math.ceil(len(chunk) * MAX_FIX_RATIO)),
      max(1, max_total_fixes - total_fixed)
  )
  ```
  - İstemde `f"En fazla {chunk_limit} satır düzelt..."` ifadesi kullanılmalıdır.

---

### 🔴 BUG 29: `subtitle_translator_gui._polish_pass` İçinde `%25` Değişim Eşiği Aşıldığında (`ratio > 0.25`) Parçalı Cümle Gruplarının (`frag_group`) Atomikliği Gözetilmeksizin Tekil Satır Bazında Geri Alma (`is_safe_polish_edit`) Yapılması ve Cümlelerin Yarım Kalarak Bozulması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~28280-28293)
* **Kök Neden:** 
  - Polish geçişi sırasında parçalı cümleler (`start/mid/end` fragmanları), `apply_polish_group_atomic` fonksiyonu ile hep birlikte kabul veya ret edilir (atomiklik korunur).
  - Ancak toplam değişim oranı `%25`'i aştığında (`ratio > 0.25`), sistem ek bir koruma olarak satır satır geri alma döngüsünü (`if new_text != text and not ht.is_safe_polish_edit(text, new_text):`) çalıştırır.
  - Bu döngüde `frag_group_ids` ve bağlı parçalar kontrol edilmez.
  - Örneğin 2 satıra yayılmış bir cümlenin (cue 4 ve cue 5) 4. satırı `is_safe_polish_edit` tarafından riskli bulunup eski haline döndürülürken, 5. satırı güvenli sayılıp cilalanmış yeni halinde bırakılır.
* **Sonuç:** 
  - Birbiriyle bağlantılı iki satırın biri eski çeviride, diğeri yeni cilalanmış çeviride kalır.
  - Türkçe SOV kuralına göre yüklem satırlar arasında kaydırıldıysa, cümlenin yüklemi her iki satırda birden tekrarlanır (*"Tarih boyunca insanlık boğuştu / Armageddon korkularıyla boğuştu"*) ya da cümle tamamen yüklemsiz kalır.
* **Düzeltme Reçetesi:** 
  - `ratio > 0.25` geri alma döngüsünde, bir fragment grubunun herhangi bir üyesi `is_safe_polish_edit` filtresine takılıp geri alındığında, o grubun TÜM üyeleri (`global_group_expected[gid]`) eski haline döndürülerek cümle bütünlüğü atomik olarak korunmalıdır:
  ```python
  if ratio > 0.25:
      revert_count = 0
      reverted_group_ids = set()
      for idx, ts, text in sorted_blocks:
          sid = str(idx)
          new_text = result_map.get(sid, text)
          if new_text != text and not ht.is_safe_polish_edit(text, new_text):
              gid = frag_group_ids.get(idx, frag_group_ids.get(sid))
              if gid is not None:
                  reverted_group_ids.add(gid)

      safe_final = []
      for idx, ts, text in sorted_blocks:
          sid = str(idx)
          new_text = result_map.get(sid, text)
          gid = frag_group_ids.get(idx, frag_group_ids.get(sid))
          if new_text != text and (not ht.is_safe_polish_edit(text, new_text) or gid in reverted_group_ids):
              safe_final.append((idx, ts, text))
              revert_count += 1
          else:
              safe_final.append((idx, ts, new_text))
      final = safe_final
  ```

---

### 🔴 BUG 30: `hybrid_translate._LOCAL_FIX_SAFE_WITHOUT_SOURCE_PATTERNS` İçinde `yasadıkları` ve `yasadığı` Regex Desenlerinin Mojibake Karakterleriyle (`yasadÄ±klarÄ±`, `yasadÄ±ÄŸÄ±`) Saklanması Nedeniyle `_apply_local_fixes`'in İmlâ Hatalarını Düzeltmeyi Reddetmesi
* **Dosya:** `hybrid_translate.py` (Satır ~12042-12045 ve ~12080-12083)
* **Kök Neden:** 
  - `_LOCAL_FIX_SAFE_WITHOUT_SOURCE_PATTERNS` kümesi, kaynak İngilizce cümleye bakılmaksızın doğrudan düzeltilebilecek yazım hatalarını tutar.
  - Ancak satır 12044'te UTF-8 bozulması sonucu `r'\byasadÄ±klarÄ±\b'` ve `r'\byasadÄ±ÄŸÄ±\b'` yazılmıştır.
  - `_apply_local_fixes(..., source_text=...)` çağrıldığında, `pattern.pattern not in _LOCAL_FIX_SAFE_WITHOUT_SOURCE_PATTERNS` şartı mojibake uyuşmazlığı nedeniyle `True` döner.
  - Fonksiyon ardından `_local_fix_source_evidence(pattern, source_text)` çağrısı yaparak İngilizce kaynak metinde `"yasadıkları"` kelimesini arar. İngilizce kaynakta bu kelime bulunamayacağı için `continue` çalıştırılır ve onarım atlanır.
* **Sonuç:** 
  - Altyazıdaki `"yasadıkları"` ve `"yasadığı"` gibi noktasız-ı / ş hataları hiçbir zaman düzeltilmez; imlâ bozukluğu çıktıda kalır.
* **Düzeltme Reçetesi:** 
  - Satır 12044'teki mojibake desenleri düzeltilmelidir:
  ```python
  _LOCAL_FIX_SAFE_WITHOUT_SOURCE_PATTERNS = frozenset({
      r'\bevett\b', r'\bttek\b', r'\bmikrofom\b',
      r'\byasadıkları\b', r'\byasadığı\b', r'\bmetafoor\b',
  })
  ```

---

### 🔴 BUG 31: `hybrid_translate.qc_auto_fix` Fonksiyonunun `max_tokens` Yerine Doğrudan `max_completion_tokens=300` Parametresi Göndermesi ve `gpt-4o`/OpenAI Uyumlu Özel Sunucularda (vLLM, Ollama, DeepSeek) HTTP 400 Hatası Alınması
* **Dosya:** `hybrid_translate.py` (Satır ~12400 ve ~2834-2835)
* **Kök Neden:** 
  - `_normalize_chat_create_kwargs` fonksiyonu, `max_tokens` parametresini sadece `gpt-5` veya `o1/o3/o4` modelleri için `max_completion_tokens`'a dönüştürür.
  - Ancak `qc_auto_fix` fonksiyonu satır 12400'de `_safe_chat_create`'e doğrudan `max_completion_tokens=300` parametresi iletir.
  - Kullanıcı `gpt-4o`, `gpt-4o-mini` veya yerel/özel bir OpenAI uyumlu uç nokta (vLLM, LM Studio, Ollama, DeepSeek) kullandığında, `_normalize_chat_create_kwargs` bu modelleri reasoning/gpt-5 saymadığı için `max_completion_tokens` parametresine dokunmaz.
  - Sunucu `Unrecognized request argument: max_completion_tokens` (HTTP 400 Bad Request) hatası fırlatır ve QC otomatik onarımı çöker.
* **Sonuç:** 
  - Yardımcı model olarak `gpt-4o` veya alternatif API sağlayıcıları seçildiğinde QC Auto-Fix çalışmaz ve her cue için hata logu basar.
* **Düzeltme Reçetesi:** 
  - Satır 12400'de `max_tokens=300` kullanılmalıdır (`_normalize_chat_create_kwargs` bunu ihtiyaç duyan modellere kendisi dönüştürür):
  ```python
  max_tokens=300,
  ```

---

### 🔴 BUG 32: `subtitle_translator_gui._chain_waves` İçinde `_extend_chain_pairs` Yerine `prev_pairs = pairs or []` Ataması Yapılması Nedeniyle A Dalgasının Son Parçası Kısa Olduğunda B Dalgasına Yetersiz Bağlam Aktarılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~6797-6810)
* **Kök Neden:** 
  - İki-dalgalı çeviri (Two-Wave Batch / B3), A dalgasının sonundaki çevirileri (`prev_tr`) B dalgasının ilk parçasına aktararak dosya ortasındaki üslup ve ton sürekliliğini sağlamayı hedefler.
  - Ancak `_chain_waves` fonksiyonundaki `for req in wave_a:` döngüsünde her adımda `prev_pairs = pairs or []` şeklinde doğrudan üzerine yazma yapılır.
  - A dalgasının son parçası (örneğin sahne sonu veya cümle bitişi nedeniyle) yalnızca 1 veya 2 satırdan oluştuğunda, önceki parçalardan gelen çeviriler silinir ve `prev_pairs` sadece 1-2 satır kalır.
  - Tasarlanmış olan `_extend_chain_pairs(prev_pairs, pairs, max_pairs=max_pairs)` fonksiyonu kullanılmadığı için B dalgası `max_pairs` (örneğin 6-8 satır) yerine sadece 1 satırlık bağlamla başlar.
* **Sonuç:** 
  - A ve B dalgaları arasındaki bağlantı zayıflar, karakter hitapları (sen/siz) ve terim tutarlılığı dosyanın ikinci yarısına eksik aktarılır.
* **Düzeltme Reçetesi:** 
  - Döngü içinde `prev_pairs = _extend_chain_pairs(prev_pairs, pairs, max_pairs=max_pairs)` kullanılmalıdır:
  ```python
  for req in wave_a:
      cid = req.get("custom_id")
      raw = wave_a_raw_map.get(cid)
      if not raw or _chunk_response_retry_reason(raw, req):
          prev_pairs = []
          continue
      tmap = parse_response(raw, fmap.get(cid, []))
      user_msg = next((m.get("content", "") for m in req.get("body", {}).get("messages", []) if m.get("role") == "user"), "")
      pairs = _chain_pairs_from_result(user_msg, tmap)
      if pairs:
          prev_pairs = _extend_chain_pairs(prev_pairs, pairs, max_pairs=max_pairs)
  ```

---

### 🔴 BUG 33: `subtitle_translator_gui._SEASON_ADDRESS_RE` Regex'inde `"sizde"` Bulunma Hâli Zamirinin Unutulması Nedeniyle Sezonluk Hitap Uyumsuzluğu Denetiminden Kaçması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~10727-10738)
* **Kök Neden:** 
  - Dizi bölümleri arasındaki sen/siz hitap uyumunu denetleyen `_season_address_suspect_ids` fonksiyonu, `_SEASON_ADDRESS_RE` regex'ini kullanır.
  - `_SEASON_ADDRESS_RE` deseni incelendiğinde:
    - Tekil zamirlerin tüm hâlleri eksiksiz yazılmıştır: `sen` (yalın), `sana` (yönelme), `seni` (belirtme), `sende` (bulunma), `senden` (ayrılma), `senin` (ilgi/iyelik).
    - Çoğul/saygı zamirlerinde ise: `siz`, `size`, `sizi`, `sizden`, `sizin` yazılmış; ancak bulunma hâli olan **`sizde`** unutulmuştur.
* **Sonuç:** 
  - Karakterin *"Bu anahtar sizde mi?"*, *"Sizde biraz tuz var mı?"*, *"Gözüm hep sizde olacak"* dediği replikler `_season_address_suspect_ids` tarafından hitap içeren şüpheli satır olarak işaretlenemez (suspect listesine giremez).
  - Birinci bölümde "sen" diye hitap edilen birine sonraki bölümlerde yanlışlıkla "sizde" denildiğinde sistem bu satırı mutabakat geçişine dahil etmez; hitap tutarsızlığı düzeltilmeden kalır.
* **Düzeltme Reçetesi:** 
  - Satır 10728'deki `_SEASON_ADDRESS_RE` desenine `sizde` eklenmelidir:
  ```python
  _SEASON_ADDRESS_RE = re.compile(
      r"(?<!\w)(?:sen|sana|seni|sende|senden|senin|siz|size|sizi|sizde|sizden|sizin)(?!\w)",
      re.IGNORECASE,
  )
  ```

---

### 🔴 BUG 34: `prompt_constants.TRANSLATABLE_CAPITALISED_STOPS` Listesinde 11 Ay Yer Alırken `"may"` (Mayıs) Ayının Unutulması Nedeniyle `"May" -> "May"` Kimlik Kilitlemesinin Guard'ı Aşarak Altyazılarda Mayıs Ayını İngilizce Bırakması
* **Dosya:** `prompt_constants.py` (Satır ~187-190) ve `hybrid_translate.py` (Satır ~6941-6966)
* **Kök Neden:** 
  - `prompt_constants.py` dosyasındaki `TRANSLATABLE_CAPITALISED_STOPS` kümesi, Türkçede karşılığı olan ve kesinlikle İngilizce bırakılmaması gereken (`"French" -> "French"` veya `"Jesus" -> "Jesus"` gibi identity kilitleri engellenen) kelimeleri tanımlar.
  - Satır 187-190'da haftanın tüm günleri ve yılın 11 ayı (`january`, `february`, `march`, `april`, `june`, `july`, `august`, `september`, `october`, `november`, `december`) listelenmiş; ancak **`may`** (Mayıs) ayı atlanmıştır.
  - Bu nedenle `_identity_lock_is_unsafe("May", "May")` çağrıldığında diğer tüm aylar için `"cevrilebilir sinif: ..."` dönüp sözlükten atılırken, `"May"` için `""` (güvenli) döner.
* **Sonuç:** 
  - Tarih veya ay içeren altyazılarda `"May" -> "May"` kuralı kilitli sözlüğe sızar.
  - Model `"5 May 1945"` veya `"in May"` gibi cümleleri `"5 May 1945"` olarak çevirir; `"Mayıs"` çevirisi engellenir.
* **Düzeltme Reçetesi:** 
  - Satır 188'deki ay listesine `"may"` eklenmelidir:
  ```python
  # gün / ay
  "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
  "sunday", "january", "february", "march", "april", "may", "june", "july",
  "august", "september", "october", "november", "december",
  ```

---

### 🔴 BUG 35: `hybrid_translate._locked_target_has_derivational_suffix` Fonksiyonunun Regex Sonuna Kelime Sınırı (`(?!\w)`) Koymaması Nedeniyle `Krallık`, `Prenslik`, `Kontluk`, `Düklük`, `İmparatorluk` Gibi Geçerli Türkçe Kelimeleri `Marslı` Benzeri Türemiş İsim Sanıp Tüm Çeviriyi `locked_term_violation` ile Reddetmesi
* **Dosya:** `hybrid_translate.py` (Satır ~10833-10845 ve ~10953)
* **Kök Neden:** 
  - `_locked_target_has_derivational_suffix` fonksiyonunun amacı, kilitli bir özel adın (örneğin `"Mars"` $\rightarrow$ `"Mars"`) izinsiz olarak `"Marslı"` (farklı bir varlık/Martian) türemiş adına dönüştürülmesini engellemektir.
  - Ancak satır 10843'te kullanılan regex `re.escape(target) + r"(?:['’]?(?:lı|li|lu|lü))"` şeklindedir ve sonuna kelime sınırı (`(?!\w)`) konulmamıştır.
  - Bu yüzden:
    - Kilitli `"Kral"` terimi için `"Krallık"` kelimesi (`Kral` + `lı` + `k`) hatalı biçimde eşleşir.
    - Kilitli `"Prens"` terimi için `"Prenslik"` (`Prens` + `li` + `k`) eşleşir.
    - Kilitli `"Kont"` terimi için `"Kontluk"` (`Kont` + `lu` + `k`) eşleşir.
    - Kilitli `"Dük"` terimi için `"Düklük"` (`Dük` + `lü` + `k`) eşleşir.
    - Kilitli `"İmparator"` terimi için `"İmparatorluk"` (`İmparator` + `lu` + `k`) eşleşir.
  - `locked_term_violation` fonksiyonu bu kelimeleri içeren her çeviriyi doğrudan kural ihlali sayar (`return True`).
* **Sonuç:** 
  - Tarih, krallık, hanedanlık veya imparatorluk temalı film/dizilerde Critic, Polish ve Condense aşamaları `"Krallık"`, `"Prenslik"`, `"Düklük"` veya `"İmparatorluk"` geçen kusursuz çevirileri `locked_term_violation` gerekçesiyle reddeder ve eski hatalı satırlara geri döndürür.
* **Düzeltme Reçetesi:** 
  - Regex'e kelime sınırı ve olası çekim ekleri eklenmelidir:
  ```python
  def _locked_target_has_derivational_suffix(target: str, candidate_text: str) -> bool:
      target = str(target or "").strip()
      if not target or not target[:1].isupper() or " " in target:
          return False
      return bool(re.search(
          re.escape(target)
          + r"(?:['’]?(?:lı|li|lu|lü)(?:lar|ler|[nd]?[ae]|[nd]?[ıiuü]|[nd]?[ae]n|[nd]?[ıiuü]n)?(?!\w))",
          str(candidate_text or ""),
          re.IGNORECASE,
      ))
  ```

---

### 🔴 BUG 36: `hybrid_translate._TR_FINITE_VERB_TAIL_RE` Regex'inde Olumsuz Geniş Zaman (`-maz/-mez/-mam/-mem`) ve Duyulan Geçmiş Zaman (`-mış/-miş/-muş/-müş`) Kiplerinin Bulunmaması Nedeniyle `EARLY_VERB_CLOSURE` Denetiminin Bu Cümlelerde Tamamen Devre Dışı Kalması
* **Dosya:** `hybrid_translate.py` (Satır ~6481-6491 ve ~8220-8222)
* **Kök Neden:** 
  - Çok satırlı bölünmüş cümlelerde (fragment: `start`, `mid`, `end`), ilk veya orta parçanın cümlenin sonunu beklemeden yüklemle erken kapanmasını (`EARLY_VERB_CLOSURE`) tespit etmek için `_looks_like_early_turkish_verb_closure` fonksiyonu kullanılır.
  - Bu fonksiyondaki `_TR_FINITE_VERB_TAIL_RE` regex'i; şimdiki zaman (`-yor`), görülen geçmiş zaman (`-di/-ti`), gelecek zaman (`-ecek/-acak`), gereklilik (`-meli/-malı`) ve olumlu geniş zaman (`-er/-ar`) eklerini içerirken;
    - **Olumsuz Geniş Zaman** eklerini (`-maz`, `-mez`, `-mam`, `-mem`, `-mayız`, `-meyiz`, `-mazsın`, `-mezsiniz`) ve
    - **Duyulan Geçmiş Zaman / Rivayet** eklerini (`-mış`, `-miş`, `-muş`, `-müş`, `-mıştı`, `-mişti`, `-muşlar`) **tamamen atlamıştır.**
* **Sonuç:** 
  - `"Bunu asla yapmaz"`, `"Bize yardım etmez"`, `"Böyle bir şey olmaz"`, `"Kimse oraya gitmemiş"`, `"Kapılar çoktan kapanmış"` gibi olumsuz geniş zaman veya duyulan geçmiş zaman yüklemleriyle biten erken kapanmış hiçbir fragment satırı tespit edilemez.
  - `EARLY_VERB_CLOSURE` doğrulayıcısı `False` döndüğü için bu bozuk cümleler Critic / Polish modüllerine onarım için iletilmez; parçalanmış ve akışı bozulmuş cümleler teslim altyazısında kalır.
* **Düzeltme Reçetesi:** 
  - `_TR_FINITE_VERB_TAIL_RE` regex'ine olumsuz geniş zaman ve duyulan geçmiş zaman kalıpları eklenmelidir:
  ```python
  _TR_FINITE_VERB_TAIL_RE = re.compile(
      r"(?:"
      r"(?:[dt][ıiuü]|di|du|dı|dü|ti|tu|tı|tü)(?:m|n|k|nız|niz|nuz|nüz|lar|ler)?|"
      r"yor(?:um|sun|uz|sunuz|lar|ler)?|"
      r"(?:m[ıiuü]ş|mış|miş|muş|müş)(?:ım|im|um|üm|sın|sin|sun|sün|ız|iz|uz|üz|sınız|siniz|sunuz|sünüz|lar|ler|tı|ti|tu|tü)?|"
      r"(?:maz|mez|mam|mem|mayız|meyiz)(?:sın|sin|sınız|siniz|lar|ler)?|"
      r"(?:acak|ecek)(?:ım|im|sın|sin|ız|iz|sınız|siniz|lar|ler)?|"
      r"(?:malı|meli)(?:yım|yim|sın|sin|yız|yiz|sınız|siniz)?|"
      r"(?:[aeıiuü]r)(?:ım|im|sın|sin|ız|iz|sınız|siniz|lar|ler)?|"
      r"(?:dır|dir|dur|dür|tır|tir|tur|tür)"
      r")$",
      re.IGNORECASE,
  )
  ```

---

### 🔴 BUG 37: `subtitle_translator_gui._strip_delivery_position_tags` ve `_DELIVERY_ASS_POSITION_RE` Regex'inin `\an\d+` Konum Kodlarını Temizlemesi Nedeniyle Teslim Aşamasında (`_filter_delivery_blocks`) Tüm `{\an8}` Ekran Üstü Altyazı Hizalamalarının Kalıcı Olarak Silinmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~3391-3396 ve ~5391)
* **Kök Neden:** 
  - `_DELIVERY_ASS_POSITION_RE` regex'i karmaşık ASS koordinat etiketlerini (`\pos`, `\move`, `\clip`, `\frz`) temizlemek amacıyla yazılmıştır; ancak bu regex'e standart SRT formatında üst/alt ekran hizalaması için tüm medya oynatıcıların (VLC, mpv, PotPlayer, Smart TV) desteklediği `\an\d+` (`\an8`) hizalama kodları da dahil edilmiştir.
  - Çeviri ve post-processing tamamlandıktan sonra en son çalışan teslim filtresi olan `_filter_delivery_blocks` (satır 5391), `value, removed = _strip_delivery_position_tags(value)` çağrısı yapar.
  - Bu çağrı, `restore_format_tags` ve pipeline tarafından titizlikle korunan tüm `{\an8}` (ekran üstü tabela, bölüm başlığı, manşet ve eşzamanlı ikinci konuşmacı) etiketlerini SRT dosyasından tamamen siler.
* **Sonuç:** 
  - Ekranın üstünde durması gereken tüm tabelalar, bölüm başlıkları, gazete manşetleri ve aynı anda konuşan ikinci konuşmacıların altyazıları ekranın altına düşer ve alttaki konuşmacının altyazısıyla üst üste binerek okunmaz hale gelir.
* **Düzeltme Reçetesi:** 
  - `\an\d+` ve `\a\d+` hizalama etiketleri SRT standardında meşru kabul edilerek `_DELIVERY_ASS_POSITION_RE`'den çıkarılmalı ya da `\an8` gibi standart hizalamalar korunacak şekilde istisna tanınmalıdır:
  ```python
  _DELIVERY_ASS_POSITION_RE = re.compile(
      r"\\(?:pos|move|org|clip|iclip)\([^)]*\)"
      r"|\\fr[xyz]?-?\d+(?:\.\d+)?",
      re.IGNORECASE,
  )
  ```

---

### 🔴 BUG 38: `subtitle_translator_gui._match_category` Fonksiyonunda İngilizce Tür Adlarının (`Comedy`, `Documentary`, `Action`, `Sci-Fi`, `Horror`, `Animation`, `Thriller`, `Romance`) Türkçe Şema Adlarına Çevrilmeden Eşleştirilmeye Çalışılması Nedeniyle Modelin Döndürdüğü Tüm Temel Türlerde `%100` Oranında `None` Dönmesi ve Otomatik Şemanın İptal Olması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~8829-8859 ve ~8989)
* **Kök Neden:** 
  - `detect_content_type_with_ai` sistem istemi İngilizce olarak çalışır. OpenAI modelleri alt kategoriler yerine sıkça standart İngilizce tür etiketlerini (`"Comedy"`, `"Documentary"`, `"Action"`, `"Sci-Fi"`, `"Horror"`, `"Animation"`, `"Thriller"`, `"Romance"`) döndürür.
  - `_match_category` fonksiyonu yalnızca Türkçe görüntüleme adlarını (`Komedi (Sitcom)`, `Tarih Belgeseli`, `Aksiyon / Macera`, `Bilim Kurgu / Uzay`, `Korku / Gerilim`, `Anime / Animasyon`) karşılaştırır.
  - Fonksiyonda İngilizce $\rightarrow$ Türkçe tür haritalaması bulunmamaktadır.
* **Sonuç:** 
  - `Comedy`, `Documentary`, `Action`, `Sci-Fi`, `Horror`, `Animation`, `Thriller`, `Romance` yanıtlarının tamamı `None` döndürür.
  - Otomatik Tür Tespiti (`Otomatik`) seçili olduğunda, model türü doğru sınıflandırsa bile sistem eşleştiremez ve filmi genel şemaya (`Otomatik`) düşürür; türe özgü terminoloji, ton, argo ve çeviri kuralları hiçbir zaman yüklenmez.
* **Düzeltme Reçetesi:** 
  - `_match_category` fonksiyonuna İngilizce tür adlarını Türkçe şema eşdeğerlerine bağlayan bir köprü haritası eklenmelidir:
  ```python
  _ENGLISH_GENRE_FALLBACK_MAP = {
      "comedy": "Komedi (Sitcom)",
      "sitcom": "Komedi (Sitcom)",
      "documentary": "Tarih Belgeseli",
      "action": "Aksiyon / Macera",
      "sci-fi": "Bilim Kurgu / Uzay",
      "scifi": "Bilim Kurgu / Uzay",
      "science fiction": "Bilim Kurgu / Uzay",
      "horror": "Korku / Gerilim",
      "thriller": "Korku / Gerilim",
      "animation": "Anime / Animasyon",
      "anime": "Anime / Animasyon",
      "romance": "Romantik Komedi",
      "romantic": "Romantik Komedi",
      "fantasy": "FRP / Fantastik Evren",
      "drama": "Dram / Aile",
      "crime": "Polisiye / Suç Draması",
  }
  ```
  - Eşleşme bulunamadığında `_ENGLISH_GENRE_FALLBACK_MAP` üzerinden arama yapılmalıdır.

---

### 🔴 BUG 39: `subtitle_translator_gui._break_to_line_budget` Fonksiyonunun `_visible_len` Yerine Ham `len(lines[en_i])` Kullanması Nedeniyle Biçimlendirme Etiketli (`<font>`, `<i>`, `<b>`) Kısa Satırları Gereksiz Yere İkiye Bölmesi ve Kapanmamış HTML Tag Kalıntıları Üretmesi
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2554-2560)
* **Kök Neden:** 
  - `_break_to_line_budget` fonksiyonu, satırın genişliğini ve kırılma eşiğini denetlerken `en_i = max(range(len(lines)), key=lambda i: len(lines[i]))` ve `if len(lines[en_i]) <= _LINE_THRESHOLD:` ifadelerinde ham Python `len()` fonksiyonunu kullanır.
  - `<font color="#ffffff">Merhaba dostlarım</font>` gibi etiketli bir satırda görünür metin yalnızca 17 karakter (`"Merhaba dostlarım"`) olmasına rağmen, HTML etiketleriyle birlikte ham uzunluk 44 karakterdir.
  - 44 karakter, `_LINE_THRESHOLD` (42 karakter) sınırını aştığı için fonksiyon satırı çok uzun zanneder ve ortasından ikiye böler: `"<font color=\"#ffffff\">Merhaba\ndostlarım</font>"`.
* **Sonuç:** 
  - 17-20 karakterlik son derece kısa ve tek satıra rahatlıkla sığacak replikler gereksiz yere iki satıra bölünür.
  - 1. satır açık kalan `<font>` etiketiyle biterken, 2. satır açılış etiketi olmayan öksüz `</font>` ile başlar.
  - Medya oynatıcılarında (VLC, Smart TV, tarayıcılar) kapanmamış etiketler nedeniyle 2. satırın rengi bozulur veya sonraki tüm altyazılar beyaz yerine sarı/renkli takılı kalır.
* **Düzeltme Reçetesi:** 
  - Satır uzunluğu hesaplamasında ve en uzun satır seçiminde ham `len()` yerine `_visible_len()` kullanılmalıdır:
  ```python
  def _break_to_line_budget(text: str, max_lines: int = _MAX_LINES, duration: float = None) -> str:
      if not text:
          return text
      lines = text.split('\n')
      while len(lines) < max_lines:
          en_i = max(range(len(lines)), key=lambda i: _visible_len(lines[i]))
          if _visible_len(lines[en_i]) <= _LINE_THRESHOLD:
              break
          pos = _find_best_split(lines[en_i])
          if pos is None:
              break
          first  = lines[en_i][:pos].rstrip()
          second = lines[en_i][pos:].lstrip()
          if not first or not second:
              break
          lines = lines[:en_i] + [first, second] + lines[en_i + 1:]
      return '\n'.join(lines)
  ```

---

### 🔴 BUG 40: `subtitle_translator_gui._find_best_split` Fonksiyonunun Tag Farkındalığı (`inside_html`, `inside_ass`) Olmaması Nedeniyle `<font ...>` ve `{\pos(x, y)...}` İçindeki Boşluklardan Satırı İkiye Bölerek Tag'i Ortasından Parçalaması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2517-2541)
* **Kök Neden:** 
  - `_find_best_split` fonksiyonu metin içindeki boşlukları (`if ch != ' ': continue`) tararken, o anki karakterin bir HTML etiketi (`<...>`) veya ASS stil/koordinat bloğu (`{...}`) içinde olup olmadığını takip etmez (`inside_tag` bayrağı yoktur).
  - Örneğin `{\an8\pos(100, 200)\fnArial\fs12}Kısa metin buraya geldi.` gibi bir satırda `(100,` ile `200)` arasındaki boşluk pozisyon 14'e denk gelir.
  - Fonksiyon bu boşluğu geçerli bir kelime bölme noktası zanneder ve satırı ortadan ikiye böler:
    - **1. Satır:** `{\an8\pos(100,`
    - **2. Satır:** ` 200)\fnArial\fs12}Kısa metin buraya geldi.`
  - Aynı durum `<font color="#ffffff" style="font-size:14px">Metin...</font>` gibi HTML etiketlerindeki boşluklarda da gerçekleşir.
* **Sonuç:** 
  - Ne 1. satır ne de 2. satır geçerli bir ASS/HTML etiketine sahip olur.
  - Medya oynatıcıları (VLC, PotPlayer, MPV, Smart TV) etiketleri tanıyamaz ve videonun üzerinde `200)\fnArial\fs12}Kısa metin buraya geldi.` şeklinde ham bozuk kod metinlerini görüntüler.
* **Düzeltme Reçetesi:** 
  - `_find_best_split` fonksiyonuna etiket içi (`inside_html`, `inside_ass`) takibi eklenmeli ve etiket içindeki boşluklar bölme adayı olarak değerlendirilmemelidir:
  ```python
  def _find_best_split(text: str) -> int | None:
      """text içinde en iyi boşluk pozisyonunu döndürür (merkeze yakın, virgül/bağlaç bonusu).
      Bulunamazsa None."""
      if len(text) <= _LINE_THRESHOLD:
          return None
      mid        = len(text) // 2
      best_pos   = None
      best_score = float('inf')
      inside_html = False
      inside_ass = False
      for i, ch in enumerate(text):
          if ch == '<':
              inside_html = True
              continue
          elif ch == '>':
              inside_html = False
              continue
          elif ch == '{':
              inside_ass = True
              continue
          elif ch == '}':
              inside_ass = False
              continue

          if inside_html or inside_ass:
              continue

          if ch != ' ':
              continue
          # Çok kısa/uzun fragman oluşturma — ilk %15 ve son %15'i atla
          if i < len(text) * 0.15 or i > len(text) * 0.85:
              continue
          dist  = abs(i - mid)
          score = dist
          if i > 0 and text[i - 1] == ',':   score -= 12   # virgülden sonra
          if i > 0 and text[i - 1] == ';':   score -= 11   # noktalı virgül
          if text[max(0, i-2):i+3] in (' — ', ' - '):
              score -= 10                                    # em/en dash
          if _CONJ_RE.match(text[i + 1:]):   score -= 8    # bağlaçla başlıyor
          if score < best_score:
              best_score = score
              best_pos   = i
      return best_pos
  ```

---

### 🔴 BUG 41: `subtitle_translator_gui._ends_sentence_gui` ve `_ellipsis_continues_gui` Fonksiyonlarının Köşeli Parantez ve Tırnak Kombinasyonlarında (`The end.]"`) Cümlenin Bittiğini Algılayamaması (`False` Dönmesi) Nedeniyle Chunk Sınırlarının ve Fragment Zincirlerinin Bozulması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~6350-6370) ve `hybrid_translate.py` (Satır ~424-440)
* **Kök Neden:** 
  - `_ends_sentence_gui` ve `hybrid_translate._ends_sentence` fonksiyonlarında `bracket_trimmed = str(text or "").rstrip().rstrip(")]}")` yazılmıştır.
  - Bir diyalog veya altyazı `The end.]"` (nokta, köşeli parantez `]`, tırnak `"`) şeklinde bittiğinde, en dışta tırnak (`"`) bulunduğu için `rstrip(")]}")` hiçbir karakteri silemez (`bracket_trimmed == text` olur).
  - Ardından çalışan `t = text.strip().rstrip('"\'»"\u201d')` yalnızca en dıştaki tırnağı siler ve `t` değeri `"The end.]"` olarak kalır.
  - `t[-1]` karakteri `]` olduğu için `t[-1] in '.!?…'` koşulu `False` döner.
* **Sonuç:** 
  - Cümle tam olarak bitmiş ve noktalanmış olmasına rağmen sistem cümlenin açık kaldığını (`incomplete fragment`) zanneder.
  - `_detect_fragment_tags` (satır 6399) bu cue'yu hatalı biçimde `start`/`mid` fragment olarak etiketler; `_make_smart_chunks` (satır 6563) ise chunk sınırını buradan kesemeyip sonraki replikleri zorla bu chunk'a dahil ederek şişirir.
* **Düzeltme Reçetesi:** 
  - Cümle sonundaki tırnak, parantez ve boşluk karakterleri sıralı veya düzensiz iç içe geçebileceği için tüm kapanış karakterlerini tek seferde temizleyen regex kullanılmalıdır:
  ```python
  _TRAIL_CLOSING_PUNCT_RE = re.compile(r'["\'»”’›)\]}\s]+$')

  def _ends_sentence_gui(text: str) -> bool:
      """True if text ends with sentence-closing punctuation."""
      t = _TRAIL_CLOSING_PUNCT_RE.sub("", str(text or ""))
      return bool(t) and t[-1] in '.!?…'

  def _ellipsis_continues_gui(cur: str, nxt: str) -> bool:
      """Return whether an ellipsis continues into the following subtitle cue."""
      c = _TRAIL_CLOSING_PUNCT_RE.sub("", str(cur or ""))
      if not (c.endswith('...') or c.endswith('…')):
          return False
      n = re.sub(r'^[«“‘‹(\[{\s"\']+', '', str(nxt or ""))
      return bool(n) and (n.startswith('...') or n.startswith('…') or n[0].islower())
  ```

---

### 🔴 BUG 42: `subtitle_translator_gui._rebalance_line_break` Fonksiyonunun 1. Satırın Noktalama İle Bitişini Denetlerken (`re.search(r"[.!?…:;,]$", first)`) Kapanış Tırnak ve Parantezlerini (`."`, `!"`, `.]`) Hesaba Katmaması Nedeniyle Tamamlanmış Tırnaklı Cümlelerin Peşine 2. Satırın İlk Kelimesini Çekmesi (`"Bunu yapacağını biliyordum." Gibi\ndavranma bana.`)
* **Dosya:** `subtitle_translator_gui.py` (Satır ~2603-2612)
* **Kök Neden:** 
  - `_rebalance_line_break` fonksiyonu, 1. satırın doğal bir cümle sınırı veya noktalama ile bitip bitmediğini denetlemek için `if re.search(r"[.!?…:;,]$", first): return value` koşulunu kullanır.
  - Bu regex yalnızca dizenin en son karakterini (`$`) denetler.
  - 1. satır tırnak içinde veya parantez içinde bittiğinde (örneğin `"Bunu yapacağını biliyordum."`), son karakter tırnak işareti (`"`) olduğu için regex `None` döner ve fonksiyon 1. satırın bittiğini anlayamaz.
  - 2. satır `_LINE_PULL_UP_WORDS` listesindeki bir kelimeyle (örneğin `"Gibi"`, `"İçin"`, `"ile"`, `"göre"`, `"kadar"`) başladığında (`"Gibi davranma bana."`), `_rebalance_line_break` 2. satırın ilk kelimesini 1. satırdaki tırnak işaretinin sonrasına taşır.
* **Sonuç:** 
  - Çıktı `"Bunu yapacağını biliyordum." Gibi\ndavranma bana.` haline gelir.
  - Tamamlanmış tırnaklı bir cümlenin kapanış tırnağından sonrasına alakasız yeni bir cümlenin ilk kelimesi yapıştırılır; diyalog ve anlam tamamen bozulur.
* **Düzeltme Reçetesi:** 
  - Noktalama denetimi kapanış tırnak, ayraç ve parantezlerini de kapsayacak şekilde güncellenmelidir:
  ```python
  _TRAIL_PUNCT_CHECK_RE = re.compile(r'[.!?…:;,]["\'»”’›)\]}\s]*$')

  def _rebalance_line_break(text: str) -> str:
      value = str(text or "")
      lines = value.split("\n")
      if len(lines) != 2:
          return value
      first, second = lines[0].rstrip(), lines[1].lstrip()
      if not first or not second:
          return value
      if second.startswith(("-", "–", "—")):
          return value
      if _TRAIL_PUNCT_CHECK_RE.search(first):
          return value
  ```

---

### 🔴 BUG 43: Tüm Çeviri Akışlarında (`_run_sync_hybrid`, `_write_results`, `_wait_batch_hybrid`, `_run_sync`, `_run_post_process`) `apply_line_breaks` (Satır Kırma) Geçişinin QC Pass'inden ÖNCE Çalıştırılması ve QC'nin Düzelttiği Uzun Satırların Kırılmadan Doğrudan Final Çıktıya Yazılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~33192-33270, ~35866-35890, ~34975-35020, ~37365-37410 ve ~28859-28900)
* **Kök Neden:** 
  - Tüm çeviri ve post-processing akışlarında işlem sırası `apply_line_breaks` $\rightarrow$ `QC Kontrolü` (`qc_auto_fix` / `_run_quality_check_inline`) şeklindedir.
  - `qc_auto_fix` modeli hatalı bir çeviriyi düzelttiğinde, ürettiği yeni Türkçe çeviri metni genellikle tek parça halinde 50-70 karakterlik uzun bir dizedir.
  - QC aşamasından sonra `apply_line_breaks` tekrar çalıştırılmadığı için, QC tarafından üretilen bu yeni metinler hiçbir zaman 42 karakterlik satır bütçesine göre bölünmez ve dengelenmez.
* **Sonuç:** 
  - QC'nin onardığı tüm satırlar EBU altyazı standardını (tek satırda en fazla 42 karakter) ihlal eder.
  - Televizyonlarda ve video oynatıcılarda altyazılar ekranın sağından ve solundan taşar, kenarları kesilir veya oynatıcının rastgele kelime bölmesiyle estetik açıdan son derece çirkin ve dengesiz bir görüntü oluşturur.
* **Düzeltme Reçetesi:** 
  - QC pass'i `apply_line_breaks`'ten ÖNCE çalıştırılmalı veya QC düzeltmeleri (`_qc_fixes > 0`) uygulandıktan sonra `apply_line_breaks` tekrar çağrılmalıdır:
  ```python
  if self.linebreak_var.get() and sorted_blocks and _qc_fixes > 0:
      sorted_blocks = apply_line_breaks(sorted_blocks)
  ```

---

### 🔴 BUG 44: Tüm Çeviri ve Post-Processing Akışlarında (`_run_sync_hybrid`, `_write_results`, `_wait_batch_hybrid`, `_run_sync`, `_run_post_process`) Native Okuyucu Geçişinin (`native_reader_pass`) UI'da Tanımlı `"native"` Rolü Yerine Hardcoded `"critic"` Model/URL/Key Parametrelerini Kullanması ve Kullanıcının Native Okuyucu Konfigürasyonunun Tamamen Yok Sayılması
* **Dosya:** `subtitle_translator_gui.py` (Satır ~33104, ~34920, ~35784, ~37304 ve ~28815)
* **Kök Neden:** 
  - Uygulama ayarlarında ve arayüzünde `"native"` rolü (`Native Okuyucu`) için ayrı bir model seçimi, özel API URL'si ve API anahtarı profili tanımlanmıştır (`_take_run_snapshot` içinde `["analysis", "critic", "polish", "qc", "native", "condense", "review"]`).
  - Ancak 5 farklı akışta `ht.native_reader_pass` çağrılırken parametreler hatalı şekilde `self._helper_api_key("critic")`, `self._helper_api_base_url("critic")` ve `self._helper_api_model("critic")` olarak geçilmiştir.
* **Sonuç:** 
  - Kullanıcı arayüzde Native Okuyucu için farklı ve daha güçlü bir model (örneğin `gpt-5.4` veya özel yerel LLM sunucusu) seçtiğinde veya ayrı bir API anahtarı atadığında bu ayarlar hiçbir zaman devreye girmez.
  - Sistem Native Okuyucu geçişini Critic'in ayarlarına (ve modeline) zorlar; kullanıcının Native Okuyucu ayarları runtime'da tamamen etkisiz kalır.
* **Düzeltme Reçetesi:** 
  - Tüm çağrı noktalarında `"critic"` yerine `"native"` rolü iletilmelidir:
  ```python
  helper_api_key=self._helper_api_key("native"),
  helper_url=self._helper_api_base_url("native"),
  helper_model=self._helper_api_model("native"),
  ```

---

### 🔴 BUG 45: `subtitle_formats._adjacent_vtt_cue_id` Fonksiyonunun Yalnızca `"cue"` ve `"note"` Öneklerini Tanıması Nedeniyle Boş Satırsız WebVTT Dosyalarında Cue ID'lerinin (`sub-2`, `item-2`, `caption_2`, `seq-2`, `part-2`) Önceki Cue'nun Diyalog Metnine Yapıştırılması (`'First text.\nsub-2'`)
* **Dosya:** `subtitle_formats.py` (Satır ~686-706 ve ~774-780)
* **Kök Neden:** 
  - WebVTT (.vtt) formatında cue blokları arasında boş satır bulunmadığında veya satır sonları birleştirilmiş dosyalarda `parse_vtt` sonraki satırın bir cue ID'si mi yoksa mevcut repliğin devamı mı olduğunu anlamak için `_adjacent_vtt_cue_id` çağrısı yapar.
  - `_adjacent_vtt_cue_id` içinde kullanılan regex `return bool(re.match(r"(?i)(?:cue|note)[-_.:]?\d", value))` şeklinde yalnızca `cue` veya `note` öneklerini kabul eder.
  - YouTube, Netflix, BBC veya web oynatıcılarından indirilen VTT dosyalarında yaygın olarak kullanılan `sub-1`, `sub-2`, `item-1`, `item-2`, `caption_1`, `caption_2`, `seq-1`, `seq-2`, `c-1`, `c-2` veya `part-1`, `part-2` gibi standart önekler `False` döner.
* **Sonuç:** 
  - Bir sonraki cue'nun başlığı olan `sub-2` veya `item-2` satırı, önceki cue'nun diyalog metnine eklenir (`"First cue text.\nsub-2"`).
  - Çeviri modeli `sub-2` ifadesini alakasız bir kelime zannederek Türkçe diyalog içine çevirir (`"İlk metin.\nmadde-2"`).
  - Altyazıların içine rastgele sistem/öğe etiketleri sızar ve çevirinin doğallığı bozulur.
* **Düzeltme Reçetesi:** 
  - `_adjacent_vtt_cue_id` fonksiyonu `previous_id` ile `value` arasındaki ortak önek ve sıralı numara yapısını tanıyacak şekilde ve yaygın önekleri kapsayacak şekilde güncellenmelidir:
  ```python
  def _adjacent_vtt_cue_id(value: str, expected_index: int,
                           previous_id: str = "") -> bool:
      value = value.strip()
      if value.isdigit():
          return value == str(expected_index) or str(previous_id).strip().isdigit()
      previous = str(previous_id or "").strip()
      if previous:
          m_val = re.match(r'^([A-Za-z0-9_-]*?)(\d+)$', value)
          m_prev = re.match(r'^([A-Za-z0-9_-]*?)(\d+)$', previous)
          if m_val and m_prev and m_val.group(1).casefold() == m_prev.group(1).casefold():
              return True
          value_tokens = {token.casefold() for token in re.findall(r"[A-Za-z]{2,}", value)}
          previous_tokens = {
              token.casefold() for token in re.findall(r"[A-Za-z]{2,}", previous)
          }
          if (value_tokens & previous_tokens
                  and re.search(r"[-_.:]", value)
                  and re.search(r"[-_.:]", previous)):
              return True
      if re.fullmatch(r'[A-Za-z0-9_-]*\d+[A-Za-z0-9_.:-]*', value) and not re.search(r'\s', value):
          return bool(re.match(r"(?i)(?:cue|note|sub|seq|item|cap|caption|part|line)[-_.:]?\d", value))
      return False
  ```

---

### 🔴 BUG 46: `subtitle_formats._ass_ts_to_srt` Fonksiyonunun Regex'inde `\d{1,3}$` Kısıtlaması Nedeniyle 4+ Haneli Milisaniye/Mikrosaniye Taşıyan ASS Dosyalarında (`0:01:23.5000`) Dönüştürmenin İptal Olup Ham Geçersiz Metnin SRT'ye Yazılması
* **Dosya:** `subtitle_formats.py` (Satır ~459-472)
* **Kök Neden:** 
  - `_ass_ts_to_srt` fonksiyonu ASS formatındaki zaman damgalarını SRT biçimine dönüştürürken `m = re.match(r'(\d{1,2}):(\d{2}):(\d{2})\.(\d{1,3})$', ts)` regex'ini kullanır.
  - FFmpeg, HandBrake, Aegisub veya video düzenleme araçlarından dışa aktarılan bazı ASS/SSA dosyalarında zaman damgaları 4 veya daha fazla basamaklı mikrosaniye/alt kesir içerir (örneğin `0:01:23.5000` veya `1:12:05.12345`).
  - Regex'teki `\d{1,3}$` deseni 3 basamaktan uzun kesirleri reddeder ve `m` değeri `None` döner.
  - Fonksiyon ham `ts` dizesini (`'0:01:23.5000'`) hiçbir dönüşüm yapmadan aynen döndürür.
* **Sonuç:** 
  - SRT dosyasına geçersiz formatta (`0:01:23.5000 --> 0:01:28.0000`) zaman damgası satırları yazılır.
  - Virgül yerine nokta ve 4 hane içeren bu satırlar standart SRT ayrıştırıcıları ve Akıllı TV / medya oynatıcıları tarafından reddedilir; altyazı senkronu tamamen kayar veya oynatıcı altyazıyı hiç yükleyemez.
* **Düzeltme Reçetesi:** 
  - Regex kesir kısmı için `\d+` kullanacak şekilde esnetilmeli ve 3 haneye kırpılmalıdır:
  ```python
  def _ass_ts_to_srt(ts: str) -> str:
      """ASS zaman damgasını (H:MM:SS.cc veya H:MM:SS.mmmm) SRT formatına çevirir."""
      ts = ts.strip()
      m = re.match(r'(\d{1,2}):(\d{2}):(\d{2})[.,](\d+)$', ts)
      if m:
          h, mm, s, frac = m.groups()
          if len(frac) == 2:
              ms = int(frac) * 10
          elif len(frac) == 1:
              ms = int(frac) * 100
          else:
              ms = int((frac + '000')[:3])
          return f'{int(h):02d}:{mm}:{s},{ms:03d}'
      return ts
  ```

---

### 🔴 BUG 47: `hybrid_translate.cps` ve `_identify_fast_lines` Fonksiyonlarının HTML/ASS Etiketlerini (`<font>`, `<i>`, `{\an8}`) Temizlemeden Ham Karakter Sayımı Yapması Nedeniyle Normal Hızdaki Biçimli Altyazıların Yanlışlıkla `> 21 CPS` (Aşırı Hızlı) Sayılıp Kısaltma Modeline Gönderilerek Bozulması
* **Dosya:** `hybrid_translate.py` (Satır ~319-323, ~4596-4603 ve ~4770-4772)
* **Kök Neden:** 
  - `hybrid_translate.cps(text, duration_sec)` fonksiyonu:
    ```python
    def cps(text: str, duration_sec: float) -> float:
        chars = len(text.replace('\n', ' ').strip())
        return chars / duration_sec if duration_sec > 0 else 0.0
    ```
    şeklinde yazılmıştır ve `_identify_fast_lines` fonksiyonunda `visible = len(text.replace('\n', ' ').strip())` kullanılmaktadır.
  - Metin içindeki HTML (`<font color="#ffff00">...</font>`, `<i>`, `<b>`) veya ASS override (`{\an8}`, `{\pos(100, 200)}`) etiketleri görünür metinden arındırılmaz.
  - Örneğin 1 saniyelik `<font color="#ffff00">Evet, geldim.</font>` altyazısında gerçek konuşulan metin yalnızca 13 karakter (13.0 CPS) iken, ham etiketlerle birlikte uzunluk 42 karakter (42.0 CPS) olarak hesaplanır.
  - 42.0 CPS değeri 21.0 CPS sınırının tam 2 katı olduğu için satır `fast` (aşırı hızlı) listesine eklenir ve `budget = 21` karakter hedefiyle `condense_fast_lines` (LLM) modeline gönderilir.
* **Sonuç:** 
  - Kusursuz, kısa ve rahatça okunabilir olan biçimli diyaloglar gereksiz yere LLM'e kısaltma için gönderilir.
  - Model etiketlerin içinde kelimeleri silmeye çalışarak anlamı bozar, cümleleri tek kelimeye indirir veya etiketleri kopararak altyazıyı bozar.
  - Ayrıca API'ye gereksiz çağrılar yapılarak token ve para israf edilir.
* **Düzeltme Reçetesi:** 
  - `cps` ve `_identify_fast_lines` fonksiyonlarında görünür karakter uzunluğu (`_visible_len`) kullanılmalıdır:
  ```python
  def _visible_text_len(text: str) -> int:
      t = re.sub(r'</?[a-zA-Z][^>]*>', '', str(text or ''))
      t = re.sub(r'\{[^}]+\}', '', t)
      return len(t.replace('\n', ' ').strip())

  def cps(text: str, duration_sec: float) -> float:
      """Characters per second (display speed) for a subtitle block."""
      chars = _visible_text_len(text)
      return chars / duration_sec if duration_sec > 0 else 0.0
  ```

---

### 🔴 BUG 48: `subtitle_formats._ASS_COMMENT` Regex'inin Yalnızca `{=...}` Formatını Tanıması Nedeniyle Standart ASS/Aegisub İçi Yorum ve Çevirmen Notlarının (`{TL Note: Japanese pun}`, `{Scene 2}`, `{SFX}`, `{music}`) Diyalog Metni Gibi Çeviri Modeline Gönderilerek Altyazıya Yazılması
* **Dosya:** `subtitle_formats.py` (Satır ~591, ~598 ve ~612)
* **Kök Neden:** 
  - ASS/SSA spesifikasyonunda ve Aegisub'da, süslü parantez içinde ters bölü (`\`) ile başlamayan her metin (`{...}`) dahili çevirmen/sahne yorumudur ve video oynatıcılarda ekranda hiçbir zaman gösterilmez.
  - `subtitle_formats.py` içinde `_ASS_COMMENT = re.compile(r'\{=[^}]*\}')` şeklinde regex yalnızca `=` ile başlayan yorumları arayacak şekilde kısıtlanmıştır.
  - `_clean_ass_text` ve `_format_ass_text` fonksiyonlarında `{TL Note: ...}`, `{Scene transition}`, `{Japanese pun}`, `{bgm fades}` gibi standart ASS yorumları ne `_ASS_COMMENT` ne de `_ASS_OVERRIDE` (`\{\\[^}]*\}`) tarafından yakalanamaz.
* **Sonuç:** 
  - Kaynak dosyadaki tüm dahili çevirmen notları, sahne açıklamaları ve teknik yönergeler ham diyalog metni gibi OpenAI modeline iletilir.
  - Model bu notları diyalog zannederek Türkçe replik gibi çevirir (*"Çevirmen Notu: Japonca kelime oyunu"*, *"Sahne 2"*) ve son SRT altyazı dosyasına kalıcı olarak yazar.
* **Düzeltme Reçetesi:** 
  - `_ASS_COMMENT` regex'i ters bölü (`\`) ile başlamayan tüm süslü parantez bloklarını kapsayacak şekilde güncellenmelidir:
  ```python
  _ASS_COMMENT = re.compile(r'\{(?!\\[a-zA-Z0-9])[^}]*\}')
  ```

---
*Yeni Rapor Dosyası Güncellendi. Tüm maddeler `DERIN_BUG_DENETIMI_2026-08-20.md` dosyasından tamamen bağımsız, özgün ve kod satırlarıyla teyit edilmiştir.*

---

## ✅ UYGULAMA DURUMU (2026-08-21, Claude Opus 5)

48 maddenin tamamı koda karşı doğrulandı. **43 madde düzeltildi, 5 madde yeniden üretilemedi.**
Test paketi: **3763 test, hepsi geçiyor** + headless GUI smoke testi.
Commit: `fix: work through the second deep-audit report (Part 2)`.

Regresyon testleri: `tests/test_deep_audit_part2_20260820.py` (30 test) ve
`tests/test_deep_audit_part2b_20260820.py` (24 test).

### Düzeltilenler

| # | Dosya | Not |
|---|-------|-----|
| 1 | `subtitle_translator_gui.py` | `position > 0`; ayrıca soyadın tek başına da geçmesi şartı eklendi |
| 3 | `subtitle_translator_gui.py` | `build_hint(before_episode=(season, episode))` — sezon kanonu artık spoiler taşımıyor |
| 4 | `subtitle_translator_gui.py` | `_ADDRESS_PLURAL_CONTEXT_RE` — açık çoğul muhatap ("hepiniz", "beyler") sayımdan çıkarılıyor |
| 5 | `prompt_constants.py` | `CANONICAL_TURKISH_NAMES` yalnız mitoloji/antikite; David/Mary/Adam vb. çıkarıldı |
| 6 | `subtitle_translator_gui.py` | Diyalog çizgisi ve açılış tırnağı satır başı sayılıyor |
| 7 | `subtitle_translator_gui.py` | İyelik ve iyelik+hâl ekleri `_TR_SUFFIX_KEYS`/`_tr_suffix_forms`'a eklendi |
| 8 | `subtitle_translator_gui.py` | `MR.`/`MRS.`/`MS.`/`MISS` — nokta + tamamı büyük harfli ad şartıyla (MS/MR kısaltmaları korunuyor) |
| 9 | `hybrid_translate.py` | `_APOSTROPHE_IN_WORD_RE` ile kısaltma kesmeleri maskeleniyor |
| 10 | `sdh_cleaner.py` | Sunum başlıkları (`Problem`, `Result`, `Step`, `Rule`, `Sonuç`, `Adım`…) `_HEADING_LABEL_PATTERNS`'a eklendi |
| 12 | `subtitle_translator_gui.py` | `_boundary_word_key` etiket/noktalama soyuyor |
| 13 | `subtitle_formats.py` | Konuşmacı öneki baştaki `{\an8}`/`<i>` etiketlerinin ARKASINA yazılıyor |
| 14 + 38 | `subtitle_translator_gui.py` | `_match_category`'ye şema-anahtarı ve `_ENGLISH_GENRE_ALIASES` yedekleri; `Animation`/`Drama` kasten dışarıda |
| 17 | `subtitle_translator_gui.py` | Dosya içi kanıt kuralı + meşru ayrı yazım listesi (`her şey` korunuyor) |
| 18 | `subtitle_translator_gui.py` | `_SHIFT_TOKEN_STOPS` genişletildi |
| 19 | `series_memory.py` | `_episode_order` — bölüm etiketleri sayısal karşılaştırılıyor |
| 21 | `subtitle_translator_gui.py` | Onarım isteminde `ctx`/`next_ctx` artık `{"i","t"}` şemasında |
| 23 | `subtitle_translator_gui.py` | `_ts_field_seconds` koordinat taşıyan zaman satırını tolere ediyor |
| 24 | `subtitle_formats.py` | Tek C1 baytı da onarılıyor; `_cp1252_punctuation_in_context` MacRoman aksanını bozmuyor |
| 26 | `subtitle_translator_gui.py` | Rota çözüldüyse boş `base_url` resmî OpenAI sayılıyor (`default_is_official`) |
| 27 | `sdh_cleaner.py` | Ekran tabelaları (`EMERGENCY EXIT`, `WARNING`, `DANGER`…) korunuyor |
| 28 | `hybrid_translate.py` | `chunk_fix_budget` — istemde chunk başına bütçe duyuruluyor |
| 29 | `subtitle_translator_gui.py` | %25 eşiği aşıldığında geri alma frag grubunun TAMAMINI kapsıyor |
| 30 | `hybrid_translate.py` | Mojibake regex desenleri düzeltildi |
| 31 | `hybrid_translate.py` | `_normalize_chat_create_kwargs` ters eşleme: gpt-5 dışında `max_tokens` |
| 32 | `subtitle_translator_gui.py` | `_chain_waves` artık `_extend_chain_pairs` ile biriktiriyor |
| 33 | `subtitle_translator_gui.py` | `sizde` eklendi |
| 34 | `prompt_constants.py` | `may` eklendi |
| 35 | `hybrid_translate.py` | `(?![kğ])` — `Krallık`/`Prenslik`/`Kontluk` artık reddedilmiyor |
| 36 | `hybrid_translate.py` | `-maz/-mez/-mam/-mem` ve `-mış/-miş/-muş/-müş` eklendi |
| 39, 40 | `subtitle_translator_gui.py` | `_find_best_split` ve `_break_to_line_budget` etiket farkında |
| 41 | `subtitle_translator_gui.py` | `_SENTENCE_CLOSERS` ile iç içe kapanışlar (`The end.]"`) |
| 42 | `subtitle_translator_gui.py` | `_LINE_END_PUNCT_RE` kapanış tırnak/parantezini görüyor |
| 43 | `subtitle_translator_gui.py` | `_finalize_translation_blocks(..., line_breaks=True)` — 5 akışta QC'den SONRA satır kırma |
| 45 | `subtitle_formats.py` | `_shares_vtt_id_pattern`; `Caption1` ve `line-0-797` replik olarak korunuyor |
| 46 | `subtitle_formats.py` | 4+ haneli kesir |
| 47 | `hybrid_translate.py` | `cps()` görünür karakter sayıyor |
| 48 | `subtitle_formats.py` | `_ASS_COMMENT` not anahtar kelimeleriyle daraltıldı (`{username}` korunuyor) |
| — | 6 modül | Kaynaktaki çift kodlanmış Türkçe dizeler temizlendi (test ile kilitlendi) |

### Yeniden üretilemeyenler (kasıtlı davranış)

| # | Neden |
|---|-------|
| 2 | `_delivery_source_map` kimliğe değil ZAMAN DAMGASINA göre eşliyor; birleşmiş cue birleşmiş kaynağı alıyor |
| 11 | Teslim kimliklerinin 0'dan başlaması kasıtlı — baş imza cue'su ve bütünlük işareti buna dayanıyor (`test_upload_ready_finalization`) |
| 15 | Tam jeton eşitliği kasıtlı bir içerik-kayması guard'ı ('gear' → 'bear' çapa karşılaştırmasından geçerdi); `test_fuzzy_rejects_content_tense_and_person_drift` bunu kilitliyor. Yalnız kesme işareti normalizasyonu eklendi |
| 22 + 37 | `{\an8}` temizliği bilinçli bir teslim kuralı — `residual_position_tags` zaten sert hata sayılıyor |
| 25 | Çağrı yerleri `src_cues=None` geçiyor; `[HATA]` işaretleri boşaltılmıyor, `_fill_hata_with_source` sonradan dolduruyor |
| 44 | `FEATURE_HELPER_ROLES` içinde `"native"` özelliği zaten `"critic"` rolüne bağlı; ayrı bir Native Okuyucu rolü yok |
