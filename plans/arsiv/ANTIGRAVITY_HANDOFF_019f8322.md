# Antigravity Devir Notu

Kaynak Codex görevi: `019f8322-e729-7a03-b1b2-9c16baea1171`

Kaynak görev sistem hatası durumuna düştüğü için normal biçimde devam ettirilemiyor. Bu belge, kurtarılabilen konuşma geçmişinden ve mevcut Git durumundan hazırlanmıştır.

## Önce Oku

1. Bu depodaki `AGENTS.md` dosyasını tamamen oku ve oradaki çalışma/test/commit kurallarını uygula.
2. `git status`, `git log --oneline -15` ve gerekli dosyalarda `git diff` çalıştır.
3. Kullanıcıya ait mevcut dosyaları veya untracked inceleme çıktılarını silme, taşıma ya da üzerine yazma.
4. API anahtarlarını hiçbir rapora, loga, mesaja veya commit'e koyma.
5. Gerçek bir çeviri çalışıyor olma ihtimali varsa GUI `App()` smoke testi veya tüm test paketini çalıştırmadan önce kullanıcıya sor. Uygulama ve testler bazı çalışma dosyalarını paylaşıyor.

## Projenin ve Konuşmanın Amacı

Bu Windows masaüstü uygulaması İngilizce altyazıları bağlam-aware biçimde Türkçeye çeviriyor. Kullanıcı uzun konuşma boyunca gerçek çeviri loglarını ve çıktı `.srt` dosyalarını inceletti; yanlış alarmlar ile gerçek kod/çeviri hataları ayrıldı ve doğrulanan kod hataları testlerle commit edildi.

Kullanıcının son yönelimi: QC geçişinin bazı gerçek bozulmalar ürettiğine dair kanıt bulunduğu için çevirilerde ağırlıklı olarak **Critic Pass ile devam etmek**. Native Reader ve QC'nin gözle görülür yararı kanıtlanmadı. Kullanıcının son sözü kabaca "Critic bunları yaptı, başka ne yapsın?" idi.

Şu aşamada yeni Critic özelliği uydurmak yerine gerçek bir sonraki çeviri koşusundan ölçüm toplamak gerekiyor.

## Son Tamamlanan Critic Çalışması

Commit: `b9b47d3`

Yapılanlar:

- `linebreak_count` nedeniyle reddedilen Critic önerileri, doğrudan atılmadan önce orijinal satır sayısına yeniden sarılıp tekrar doğrulanıyor.
- Critic prompt'una aynı satır sayısını koruma kuralı eklendi.
- `critic_pass_with_helper` isteğe bağlı `change_log` topluyor.
- Beş çeviri akışının tamamı `<altyazı>.critic_degisiklikler.txt` raporu yazıyor. Raporda cue kimliği, tetikleme sebebi, kaynak, önceki çeviri ve yeni çeviri bulunuyor.
- Validator nedenleri için öneri/kabul istatistikleri loglanıyor.
- Critic chunk boyutu 300'den 100'e indirildi.
- Boş, kesik veya format dışı helper cevapları artık sessizce kaybolmuyor; loga yazılıyor.
- 9 regresyon testi eklendi.

O noktadaki doğrulama:

- `python -m py_compile subtitle_translator_gui.py`: başarılı.
- Headless GUI smoke testi: başarılı.
- Tam paket: 1518 test, 3 skipped, başarılı.

## Doğru Sıradaki Adım

1. Kullanıcı yeni bir gerçek altyazı çevirisi çalıştırsın. Tercihen Critic açık; QC ve Native Reader kapalı olsun. Ayarları kullanıcı kontrol ediyor, kod varsayılanlarını izinsiz değiştirme.
2. Koşu bittikten sonra şunları iste/incele:
   - tam konsol logu,
   - teslim edilen `.srt`,
   - aynı klasördeki `.ham.srt`,
   - İngilizce kaynak altyazı,
   - yeni oluşan `.critic_degisiklikler.txt`.
3. Critic raporundaki her değişikliği kaynak ve bağlamla doğrula. Yalnız kabul oranına güvenme; içerik kalitesini kontrol et.
4. Logdaki sebep bazlı oranları karşılaştır: ör. `EARLY_VERB_CLOSURE: 12/15`. Çok gürültülü bir sinyal ancak birden fazla gerçek koşuda kanıtlandıktan sonra daraltılmalı.
5. Gerçek bir kod bug'ı bulunursa saf helper + regresyon testi ekle, tam test paketini çalıştır ve yalnız dokunulan dosyaları stage ederek otomatik commit et.
6. Kötü çeviri içeriği bulunursa İngilizce kaynaktan yeniden çevir; yüzeysel kelime değiştirme yapma ve doğru satırlara dokunma.

## Konuşmada Tamamlanan Başlıca Commitler

- `b9b47d3`: Critic satır-sayısı kurtarma, değişiklik raporu ve sebep bazlı istatistik.
- `a215942`: Massacre in Rome örneğindeki üç mixed-term yanlış-pozitif sınıfı.
- `8aff6db`: `1, 2, 3...` gibi yalnız sayılardan oluşan cue'ların yanlışlıkla çevrilmemiş sayılması.
- `f1f5185`: `Newsweeks` → `Newsweek'ler` çoğul/gövde glossary-guard istisnası.
- `2732322`: ALL-CAPS kaynaklarda mixed-term yanlış alarmları; gerçek dosyada 27 → 0.
- `9b82e50`: QC'nin gerçekten uyguladığı değişiklikler için `.qc_degisiklikler.txt` raporu.
- `999a93d`: Ayar yedeği seçiminin mtime yerine dosya adı epoch suffix'iyle yapılması; flaky test giderildi.
- `3860d87`: Özel sağlayıcı açıkken Batch engeli; özel sağlayıcı/gpt-5.4 varsayımları.
- `7e9529e`: Apostroflu ve çok kelimeli korunan özel isimler için glossary guard düzeltmesi.
- `739c2dc`: `AGENTS.md` içine kalıcı çeviri-log inceleme iş akışı.
- `51234aa`: Çok kelimeli özel isim glossary guard'ı ve SDH kaynaklarda yanlış çevrilmemiş alarmı.
- `8dd57bd`: Glossary meta-commentary guard testleri, dil kodu testi ve iki plan belgesi.

## Konuşmadan Kalan Tarihsel Bulgular

Bunlar eski konuşma sırasında açık görünüyordu. Güncel dosyayı yeniden bulup kaynakla karşılaştırmadan değişiklik yapma:

- Heroin Town çıktısında QC'nin bozduğu düşünülen cue `#812` ve `#604-605`.
- Massacre in Rome `#623`: `Mareşal'in` biçiminde olası ünlü uyumu/yazım hatası.
- Metamorfose dos Passaros çıktısında kalmış olabilecek `mère` ve `kóri` yabancı dil sızıntıları.
- rough.treatment.1978 `#433-435` hizalama uyarısı.
- `blood.tea.and.red.string.2006` tamamen ses/müzik açıklamalarından oluştuğu için SDH temizliği sonunda boş çıktı oluşmuştu. Kullanıcının kalıcı kuralı SDH/ses etiketlerini nihai dosyadan tamamen kaldırmaktır; bu kuralı izinsiz gevşetme.

## Mevcut Depo Durumu

Bu devir belgesi hazırlanırken dal `master`, HEAD `108052c` idi. Kaynak konuşma bittikten sonra aynı depoya başka çalışmalar da eklenmiş:

- `ef0f476`: checkpoint hash ve şema/test değişiklikleri.
- `158be36`: sync/hybrid chunk omission ve `has_hata` değerlendirmesi.
- `108052c`: UI glossary guard hedef dil eşlemesi.

Bu yeni commitleri geri alma veya `b9b47d3` durumuna resetleme. Critic çalışmasına güncel HEAD üzerinden devam et.

Mevcut untracked dosyalar kullanıcıya/başka görevlere ait olabilir; koru:

- `.sync_checkpoint.jsonl`
- `check_cues.py`, `check_cues2.py`, `check_flags.py`
- `check_report.txt`, `cues_align.txt`, `cues_check.txt`, `cues_output.txt`
- `fix.py`, `fix_srt.py`, `salome_check.txt`
- bu devir dosyası

## Antigravity'ye Verilecek Başlangıç Mesajı

Şunu yeni Antigravity konuşmasına yapıştır:

> `D:\Openai Altyazı Çevirisi` klasörünü çalışma alanı olarak aç. `AGENTS.md` ve `ANTIGRAVITY_HANDOFF_019f8322.md` dosyalarını tamamen oku. `git status` ve `git log --oneline -15` ile güncel durumu doğrula; mevcut untracked dosyalara dokunma. Kaynak Codex konuşması sistem hatasıyla kapandı. Critic Pass iyileştirmeleri `b9b47d3` ile tamamlandı; yeni kod yazmadan önce bir sonraki gerçek çeviri koşusunun logunu ve `.critic_degisiklikler.txt` raporunu incelememiz gerekiyor. Kullanıcının yeni mesajını bu bağlamla yanıtla ve yalnızca kanıtlanan sorunlarda değişiklik yap.
