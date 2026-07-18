# Brief: S04E14 (Skull in the City HD) — JSON-onarım kaynaklı cue kayması

Hazırlayan: Fable 5 (analiz, 2026-07-08). Bu brief kendi başına yeterlidir; konuşma bağlamı gerekmez.

**Durum: UYGULANDI (Sonnet 5, 2026-07-08).** Görev 1 (id doğrulaması) kodlandı ve test edildi (`tests/test_json_repair_validation.py`, 11 test). Görev 2 (truncation-vs-format ayrımı) UYGULANMADI — Görev 1 tek başına yeterli koruma sağlıyor, Görev 2 sadece maliyet-optimizasyonu, brief'in kendisi de bunu opsiyonel olarak işaretlemişti. Görev 3 (dosya düzeltmesi): API çağrısı gerektirdiği (gerçek para) için OpenAI'ye tekrar gönderilmedi — bunun yerine cue #79-122 Sonnet 5 tarafından ELLE, kaynak İngilizce'ye sadık ve dosyanın geri kalanındaki üslupla tutarlı şekilde çevrildi; `detect_alignment_issues` üzerinde 0 bulgu ile doğrulandı, cue sayısı (581) korundu. `.bak` yedeği dosyanın yanında duruyor.

## Özet

`C:\Users\K\Downloads\ÇIKTI\Oddities_S04E14_Skull in the City HD.English.srt` dosyasında **cue #79'dan #122'ye kadar (44 cue, ~3:18–4:15 arası) Türkçe metin YANLIŞ cue'ya yapışmış durumda** — her cue'nun zaman damgası doğru ama üzerindeki Türkçe metin o anda söylenen İngilizce'nin değil, komşu bir satırın (çoğunlukla bir sonrakinin) çevirisi. Örnek:

```
#99 [00:03:27,067 --> 00:03:28,633]  EN: "DOES THIS WORK FOR YOUR MUSEUM?"
                                     TR (final): "Evet. İkisini de istiyorum. Bence harika."
                                     (bu aslında #100 "YEAH. I WANT BOTH. I THINK IT'S GREAT."ın çevirisi)
```

Bu bir çeviri KALİTESİ sorunu değil — her satırın Türkçesi tek başına gayet doğru ve akıcı, sadece YANLIŞ zaman damgasının altında duruyor. İzleyici o saniyede söylenen cümleyle hiç alakası olmayan bir alt yazı görür.

## Kanıt ve kapsam

- Kaynak/final `subtitle_formats.read_subtitle_text` ile ayrıştırılıp cue-id bazında EN/TR karşılaştırıldı; zaman damgaları teyit edildi (aynı id'nin EN ve TR zaman damgaları birebir eşleşiyor — demek ki kayma cue INDEX'inde değil, TEXT içeriğinde).
- Kayma tam olarak **#79'da başlıyor**: EN#79 `"[ LAUGHS ]"` (ses efekti) — final'de bu satırın Türkçe karşılığı `[KAHKAHA]` YOK, yerine `"Nükleer patlama,"` (=EN#80'in bir parçası) var. #80-81 de EN#81'in ("OF BOTH HEAT AND RADIATION") çevirisini ikiye bölünmüş halde taşıyor.
- Kayma **#122'ye kadar sürüyor** (bağımsız anahtar-kelime taramasıyla doğrulandı: `radiation`, `museum`, `cancer`, `wind`, `nuclear` gibi nadir kelimelerin EN'de geçtiği cue'larda TR karşılığı YOK ama komşu cue'da VAR — 79, 80, 84, 86, 99 dahil çok sayıda bağımsız doğrulama noktası).
- **#123–127 DOĞRU** — log'daki "🔧 8 çevrilmemiş satır sync ile onarılıyor" satırı `subtitle_translator_gui.py::_repair_untranslated_sync` (~satır 2337) fonksiyonuna ait; bu fonksiyon `raw_src_map[str(idx)]`'ten (id'ye göre doğru kaynak metin) çekip küçük gruplar hâlinde YENİDEN çevirir — id-bazlı olduğu için sonucu GARANTİ doğru hizalı. **#128'den itibaren episode tekrar normal** (kontrol edildi, 128-134 ve tüm dosyanın geri kalanı temiz).
- **`_repair_untranslated_sync` neden #79-122'yi YAKALAYAMADI:** bu fonksiyon yalnızca (a) metin `"[HATA"` ile başlıyorsa veya (b) `_is_untranslated()` yardımcı fonksiyonu metnin kendi kaynağıyla (case/noktalama bağımsız) BİREBİR AYNI olduğunu (yani hâlâ İngilizce bırakılmış) tespit ederse devreye giriyor. Kaydırılmış satırların hiçbiri bu iki kritere uymuyor — hepsi GEÇERLİ, AKICI Türkçe, sadece YANLIŞ id'ye bağlı. Yani bu son-çare mekanizması yapısal olarak bu hata sınıfını göremez.
- İkinci JSON-onarımlı chunk (chunk_283, log'da "🔧 chunk_283: JSON onarıldı (40 item)") **kontrol edildi, TEMİZ** — cue #278-329 arası tamamen doğru hizalı. Yani JSON-onarımı HER ZAMAN kayma yaratmıyor; bu spesifik chunk'ta (chunk_81) bir şey ters gitti.
- Dosyanın geri kalanında (bağımsız geniş tarama) başka bir kayma kalıbı YOK — hasar tek bir 44-cue'luk bloğa (79-122) izole.

## Kök neden hipotezi (kod okumasıyla doğrulandı)

`subtitle_translator_gui.py::_json_repair_pass` (~satır 5380):
- Bir chunk'ın JSON'u parse edilemediğinde (kesilmiş/truncated yanıt), fonksiyon **`raw[:2000]`** (bozuk yanıtın yalnızca ilk 2000 karakteri) alıp ayrı, ucuz bir modele ("gpt-5.4-mini", ana modelden BAĞIMSIZ olarak sabit kodlanmış) gönderiyor: *"The previous response was supposed to be a valid JSON array but failed to parse. Return the corrected JSON array with the same translations."*
- Bu onarım isteğinde **kaynak metin (orijinal İngilizce satırlar) YOK** — onarım modeli yalnızca bozuk JSON'un kendisine bakarak "tamamlıyor". Kesilme tam bir item'ın ortasında olduysa (örn. `{"i":79,"t":"[KAHKAHA]"},{"i":80,"t":"Nükleer pat` gibi bir noktada kesildiyse), onarım modelinin id'leri doğru sayıp doğru eşleştirmesi GARANTİ DEĞİL.
- Onarım sonucu **hiçbir doğrulamadan geçmeden** kabul ediliyor: `raw_map[cid] = fixed` — item sayısının chunk'ın beklenen satır sayısıyla eşleşip eşleşmediği, id kümesinin `chunk_info`'daki beklenen id'lerle birebir örtüşüp örtüşmediği KONTROL EDİLMİYOR.
- `parse_response` (gui ~2822) onarılmış JSON'daki `"i"` alanına körü körüne güveniyor (`trans_map[str(item["i"])] = item["t"]`) — bu doğru bir tasarım (id-bazlı eşleştirme, pozisyonel değil) AMA onarım modelinin ÜRETTİĞİ id'ler yanlışsa bunu yakalayacak hiçbir mekanizma yok.
- Sonraki hiçbir aşama (`_retry_hata`, `consistency_sweep`, critic, polish) bunu YAKALAYAMAZ çünkü kaydırılmış satırların HER BİRİ tek başına geçerli, akıcı Türkçe — "[HATA]" değil, yabancı-dil sızıntısı değil, sadece YANLIŞ id'ye bağlı. Mevcut hiçbir validator "bu id'nin çevirisi gerçekten bu id'nin kaynağına mı ait" diye bakmıyor.

**Neden chunk_283 temiz kaldı da chunk_81 bozuldu:** muhtemelen şans meselesi — kesilme noktasının TAM OLARAK nerede olduğu (bir item'ın ortasında mı, item sınırında mı) onarım modelinin id-sayımını şaşırıp şaşırmayacağını belirliyor. Bu, onarımı "güvenilir" kılan bir tasarım değil, doğası gereği kırılgan.

## Önerilen düzeltmeler (Sonnet 5 için)

### Görev 1 — `_json_repair_pass`'e yapısal doğrulama ekle (asıl önleyici düzeltme)

`subtitle_translator_gui.py::_json_repair_pass` içinde, onarım sonucu kabul edilmeden ÖNCE:
1. Fonksiyona expected id kümesini ilet — her `req` için `req["body"]["messages"][1]["content"]` içindeki `payload["tr"]` listesinden `{item["i"] for item in payload["tr"]}` çıkarılabilir (bu deseni `_chunk_src_hash`'in JSON'u nasıl parse ettiğine bakarak uygula, aynı yapı).
2. `items2` (onarılmış liste) kabul edilmeden önce:
   - Tüm id'ler benzersiz mi (`len(ids) == len(set(ids))`)
   - Tüm id'ler beklenen kümenin bir ALT KÜMESİ mi (`set(ids) <= expected_ids`) — yabancı/bilinmeyen id yoksa
   - Kapsama oranı makul mü (örn. `len(items2) >= len(expected_ids) * 0.5` gibi çok düşük değilse) — tamamen boş/anlamsız onarımları ele
3. Doğrulama BAŞARISIZ olursa: onarımı KABUL ETME (`raw_map[cid] = fixed` satırını atla, `repaired` sayacını artırma) — chunk `_retry_hata`'nın normal tam-yeniden-çeviri yoluna düşsün (o yol GERÇEK kaynak metni yeniden gönderir, id-eşleşmesi garanti doğru olur).
4. Log'a doğrulama-reddi durumunda bir satır ekle: `"↺ {cid}: JSON onarımı id doğrulamasından geçemedi, tam yeniden çeviriye bırakıldı"` (uyarı seviyesi) — böylece kullanıcı ileride log'dan bu durumu ayırt edebilir.

### Görev 2 — Kesilmiş yanıtlarda onarım yerine doğrudan tam retry (daha basit, daha güvenli alternatif/ek önlem)

Alternatif olarak ya da Görev 1'e ek olarak: `_json_repair_pass`'in "broken_response" olarak gönderdiği ham metnin GERÇEKTEN kesilmiş mi (yanıt token limitine takılmış, `raw` bir item'ın ortasında bitiyor) yoksa sadece BİÇİM sorunu mu (markdown fence, fazladan virgül gibi tam ama geçersiz JSON) olduğunu ayırt et:
- Gerçek kesilme belirtisi: `raw.rstrip()` bir `"`, `}`, `]` ile bitmiyor VEYA açık parantez/tırnak sayısı dengesiz.
- Gerçek kesilmeyse: onarım DENEME, doğrudan `_retry_hata`'nın tam-yeniden-çeviri yoluna bırak (kaynak metinle güvenli yeniden üretim).
- Sadece biçim sorunuysa (JSON tam ama sarmalı bozuk): mevcut onarım akışını kullanmaya devam et (bu durumda id-kayması riski çok daha düşük, çünkü içerik tam).

### Görev 3 — Bu spesifik dosyayı düzelt

`C:\Users\K\Downloads\ÇIKTI\Oddities_S04E14_Skull in the City HD.English.srt`: cue #79-122 arası içerik hizası bozuk; bu bir metin-düzeltme değil bir HİZALAMA sorunu olduğundan regex ile onarılamaz. Önerilen yol:
1. Görev 1/2 koddaki düzeltme uygulandıktan sonra, dosyayı YENİDEN ÇEVİR (checkpoint parmak izi mekanizması zaten var — `.sync_checkpoint.jsonl` varsa temizlenip temiz bir koşu yapılmalı; model/ayar aynı kalacağı için checkpoint'in kendisi otomatik es geçmeyecektir çünkü kaynak dosya + model + ayarlar aynı olacak — eğer checkpoint bu chunk'ı "tamamlanmış" olarak görüyorsa (dosyada `.sync_checkpoint.jsonl` var mı kontrol et) o dosyayı silip yeniden çeviri tetiklenmeli.
2. Alternatif (daha ucuz, daha kırılgan): yalnızca cue #79-127 aralığını kapsayan küçük, izole bir yeniden-çeviri isteği kurup sonucu mevcut final/ham dosyalarına birleştir — ama bu yeni bir tek-kullanımlık script gerektirir, dosya küçük olduğu için tam yeniden çeviri muhtemelen daha az efor.
3. Hangi yol seçilirse seçilsin: düzeltmeden SONRA cue sayısının (581, mevcut final'daki gibi — 2 SDH cue'su `clean_sdh` ile zaten silinmiş) korunduğunu ve #79-122 aralığının artık EN kaynağıyla anlamca örtüştüğünü doğrula (bu raporda kullanılan karşılaştırma scriptiyle aynı yöntemle: `subtitle_formats.read_subtitle_text` + cue-id eşleştirme + göz kontrolü).

## Test & doğrulama

1. Yeni birim testi `tests/test_json_repair_validation.py`:
   - Sahte bir `req` (expected ids `{1,2,3,4,5}`) + sahte bozuk `raw` + sahte onarım yanıtı olarak id kümesi `{1,2,3,4,5}` dışında bir id içeren (`{"i": 99, ...}`) JSON → onarım REDDEDİLMELİ, `raw_map[cid]` DEĞİŞMEMELİ.
   - Aynı senaryo ama onarım yanıtı doğru id kümesini içeriyor → onarım KABUL EDİLMELİ.
   - Kapsama oranı çok düşük (örn. beklenen 40 id'den yalnızca 3'ü var) → REDDEDİLMELİ.
   - Mevcut `_json_repair_pass` çağıran testler (varsa) kırılmamalı — `tests/` içinde `_json_repair_pass`/`json_repair` geçen mevcut testleri ara ve regresyon kontrolü yap.
2. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py`
3. `python -m unittest discover -s tests` (taban: 1144, hepsi yeşil kalmalı)
4. GUI headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`
5. Dosya düzeltmesi (Görev 3) sonrası: bu brief'teki karşılaştırma scriptiyle (veya benzeriyle) #79-127 aralığının artık doğru hizalandığını elle doğrula — otomatik test bunu kapsamaz, gerçek dosya bazlı bir kontrol gerekir.

## Riskler / dikkat

- `_json_repair_pass` yalnızca `_retry_hata` içinden çağrılıyor ve `_retry_hata`'nın kendisi TEK bir paylaşılan metot — sync (`_run_sync`), sync+hybrid (`_run_sync_hybrid`), batch (`_run_batch`) ve resume (`_resume_batches`) olmak üzere 4 çağrı noktasının hepsi AYNI implementasyonu kullanıyor (grep ile doğrulandı). Yani Görev 1/2'deki düzeltme TEK yerde yapılır, otomatik olarak tüm akışları kapsar — CLAUDE.md'nin "iki prompt/akış ayrı ayrı güncellenmeli" uyarısı burada geçerli DEĞİL (o uyarı `build_requests`/`build_batch_requests` gibi GERÇEKTEN ayrı iki implementasyon için geçerliydi).
- Görev 1'in id-çıkarma mantığı `req["body"]["messages"][1]["content"]`'ın JSON payload olduğu varsayımına dayanıyor — bu, sync/hybrid payload biçimiyle (`{"tr": [{"i":..,"t":..}, ...]}`) uyumlu; `_chunk_src_hash`'in aynı alanı nasıl parse ettiğine bakarak aynı deseni uygula.
- Doğrulama çok KATI olursa (örn. id kümesi TAM eşleşme isterse, alt küme değil), meşru kısmi-kurtarma senaryolarını (bazı id'ler gerçekten API yanıtında hiç yoktu, bu normal) gereksiz yere reddedebilir — bu yüzden "alt küme + benzersiz + makul kapsam oranı" üçlüsü öneriliyor, "tam eşleşme" değil.
- Bu bulgu, projenin şu ana kadarki "yeni bölümde yeni sızıntı kelimesi" örüntüsünden farklı bir SINIF hata — kelime listesi eklemekle çözülmez, yapısal/mimari bir doğrulama eksikliği. Diğer JSON-onarım geçiren geçmiş bölümlerde de (bu oturumdan önce çevrilmiş dosyalarda) aynı sorun sessizce oluşmuş olabilir; kullanıcı isterse geçmiş çıktılarını da (log'larında "JSON onarıldı" geçen dosyaları) aynı yöntemle taratabilir.
