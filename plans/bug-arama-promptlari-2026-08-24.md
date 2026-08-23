# Bug arama promptları — 2026-08-24

Altı bağımsız denetim. Paralel çalıştırılabilir; kapsamları kesişmiyor.
Hepsi **salt okunur**.

---

## HER PROMPTUN BAŞINA EKLENECEK ORTAK BLOK

```
KURALLAR — bunlara uymayan çıktı kabul edilmez:

1. SALT OKUNUR. Hiçbir dosyayı değiştirme, oluşturma veya silme. Kod,
   ayar, log, altyazı, test — hiçbirine dokunma. Yalnız oku ve RAPORLA.
   Düzeltme uygulama; düzeltme ÖNER, uygulamayı bana bırak.
2. Test paketini ÇALIŞTIRMA ve `App()` KURMA. Testler canlı uygulamayla
   proje kökünü paylaşıyor (batch_id.txt, logs/) — çalıştırmak kullanıcının
   koşusunu bozabilir.
3. API çağrısı YAPMA. Ücretli ve gereksiz.
4. Ölçüm yapman gerekiyorsa yalnız `%TEMP%` altında geçici betik kullan ve
   işin bitince kendi geçici dosyalarını bırakma.
5. HEAD `484cf5edab2cc572803493fc3355e59117189658`. Raporundaki her
   `dosya.py:satır` göndermesini BU HEAD'e karşı doğrula. Eski bir denetim
   raporundan satır numarası kopyalama — `plans/arsiv/` altındakiler eski
   HEAD'lere bakıyor ve numaraları artık yanlış.
6. Her iddiayı ÖLÇ. "Muhtemelen", "olabilir", "riskli görünüyor" tek başına
   bulgu değildir. Gerçek dosyalar `D:\Openai Altyazı Çevirisi` altında:
   `HAZIR DİZİLER` ve `HAZIR FİLMLER` içinde ~202 kaynak-teslim çifti
   (`Raporlar/Kaynak/<ad>.srt` ile üç üst klasördeki `<ad>.srt`), `logs/`
   içinde ~105 koşu logu. Bulgunu bunlara karşı ölç ve KAÇ DOSYADA /
   KAÇ CUE'DA gerçekleştiğini say.
7. Bir davranışın bug mu yoksa BİLİNÇLİ TASARIM mı olduğunu ayırt et.
   Bir testin o davranışı kilitlemesi, tasarımın kasıtlı olduğunun
   kanıtıdır — "test yanlış" demeden önce testin gerekçe yorumunu oku.
   Bilinçli olduğunu düşündüklerini ayrı bir başlık altında listele.
8. Doğrulayamadıklarını GİZLEME. "Şunu ölçemedim çünkü..." diye ayrı bir
   bölüm aç. Doğrulanmamış iddiayı doğrulanmış gibi sunma.
9. Yanlış pozitif oranını kendin raporla: önerdiğin her yeni kural için
   gerçek dosyalarda kaç kez tetiklendiğini ve bunların kaçının GERÇEK
   sorun olduğunu elle kontrol edip söyle.
```

---

## 1 — Modele ne söylüyoruz?

```
Bu programda çeviri kalitesinin çoğu, modele gönderilen SİSTEM PROMPT'unda
ve payload'da ne yazdığına bağlı. Bugüne kadar yapılan denetimler hep
kodun akışını inceledi; PROMPT'un kendisini kimse denetlemedi.

İncele:
- `_build_sync_system_prompt` (subtitle_translator_gui.py) ve
  `build_system_prompt` (hybrid_translate.py). Bu ikisinin semantik olarak
  hizalı kalması gerekiyor (CLAUDE.md bunu açıkça söylüyor).
- `prompt_constants.py` içindeki paylaşılan parçalar.
- `build_requests` / `ht.build_batch_requests` ile üretilen payload
  anahtarları: ctx, next_ctx, prev_scene, prev_tr, glossary, frag.

Cevaplaman gerekenler:
1. İki sistem promptunu YAN YANA çıkar ve farkları listele. Hangi kural
   birinde var diğerinde yok? Her fark için: bu kasıtlı mı, yoksa biri
   güncellenirken diğeri unutulmuş mu? Farkın çeviriye etkisini söyle.
2. Prompt içinde BİRBİRİYLE ÇELİŞEN talimat var mı? (Örnek arıyorsan:
   "kısalt" diyen bir kural ile "hiçbir şeyi atma" diyen bir kural aynı
   anda gönderiliyor olabilir.) Çelişkiyi metinden alıntıla.
3. Artık geçersiz/bayat talimat var mı? Kaldırılmış bir özelliğe,
   olmayan bir payload anahtarına veya eski bir model davranışına atıf.
4. Prompt'a giren DEĞİŞKEN içerik ne kadar büyüyebiliyor? Sözlük, karakter
   listesi, sahne notları, prev_tr — hepsinin bir üst sınırı var mı?
   Sınırsız olan varsa, gerçek `.context_cache/*.json` dosyalarında en
   büyük değerin ne olduğunu ÖLÇ ve bunun kaç token ettiğini tahmin et.
5. Payload'da modele gönderilen ama sistem promptunda HİÇ AÇIKLANMAYAN
   bir anahtar var mı? (Model onu ne yapacağını bilmiyor olabilir.)
   Tersi de: promptta bahsedilen ama payload'da hiç gönderilmeyen.
6. Gerçek koşu loglarında veya `.context_cache` içinde, promptun modele
   YANLIŞ bir şey söylediğine dair kanıt bul. Örnek: son turda sabit
   terim tablosunun "pupil → göz bebeği" dayattığı ama metnin öğrenciden
   bahsettiği bulundu. Benzer sınıf başka ne var?
```

---

## 2 — SDH / ses etiketi temizliği

```
Kullanıcının KALICI tercihi: ses, dil ve konuşmacı etiketlerinin HEPSİ
silinsin, hiç sorma. `sdh_cleaner.py` (~1650 satır) bunu yapıyor ama
daha önce şu tespit edilmişti: beyaz listesi Türkçe etiketleri tanımıyor
ve 20 etiketten yalnız 1'ini yakalıyor. Bu tespit ölçülmedi ve
düzeltilmedi. Şimdi ölç.

Cevaplaman gerekenler:
1. `sdh_cleaner.py`'ın tanıdığı etiket biçimlerini çıkar: parantez türleri,
   büyük harf kuralı, konuşmacı öneki, müzik işareti, italik içindekiler.
2. 202 gerçek TESLİM dosyasında (çeviri sonrası, yani temizlik ÇALIŞMIŞ
   olması gereken dosyalar) kalan etiket ara. Kaç dosyada kaç etiket
   kalmış? Örnekleri ver. Türkçe etiketler ([SES], (MÜZİK), ANLATICI:)
   ile İngilizce olanları AYRI say.
3. Aynı taramayı KAYNAK dosyalarda yap: kaynakta kaç etiket vardı, kaçı
   temizlendi? Temizlik oranını yüzde olarak ver.
4. TERS yöndeki hatayı da ara — temizleyicinin GERÇEK DİYALOĞU sildiği
   vakalar. Kaynakta parantez içinde gerçek replik varsa veya bir cue
   tamamen büyük harfse yanlışlıkla etiket sayılmış olabilir. Kaynak ve
   teslimi karşılaştırıp kaç cue'nun içeriği kaybolmuş say.
5. Bir cue'nun TAMAMI etiketse ne oluyor? Cue siliniyor mu, boş mu
   kalıyor, yoksa zaman kodu boşta mı duruyor? Gerçek teslimlerde boş
   veya tek noktalama içeren cue sayısını ver.
6. `_bare_gerund_sdh_label` ve çevresindeki kurallar hangi biçimleri
   yakalıyor, hangilerini kaçırıyor? Gerçek dosyalardan kaçırdığı
   örnekleri listele.
```

---

## 3 — Ayardaki düğme gerçekten ne yapıyor?

```
Kenar çubuğunda çok sayıda açma/kapama düğmesi var ve koşu bir "anlık
görüntü" (`_active_snapshot`) üzerinden çalışıyor. Sorun şu: bir düğmenin
ETİKETİ, KAYDEDİLMESİ, ANLIK GÖRÜNTÜYE GİRMESİ ve GERÇEKTEN UYGULANMASI
dört ayrı şey ve bunlar birbirinden kopabiliyor.

Cevaplaman gerekenler:
1. Bütün UI değişkenlerini (`*_var`) çıkar. Her biri için dört soruyu
   cevapla ve bir TABLO olarak ver:
   a) `.gui_settings.json`'a kaydediliyor mu?
   b) `_load_settings` onu geri yüklüyor mu? (Varsayılan-AÇIK olanlar
      `if "key" in d:` kalıbını, varsayılan-KAPALI olanlar `if d.get(...)`
      kalıbını kullanmalı — yanlış kalıp kullananı bul.)
   c) Anlık görüntüye giriyor mu?
   d) Kodda GERÇEKTEN okunup bir davranışı değiştiriyor mu, yoksa ölü mü?
2. Ölü düğme var mı? Yani kullanıcı açıp kapatıyor ama hiçbir şey
   değişmiyor. Varsa kesin kanıtla göster.
3. Bir düğmenin dört akıştan (sync, sync-hybrid, batch, batch-hybrid)
   yalnız bazılarında etkili olduğu durumları bul. Etiketi bunu söylüyor
   mu?
4. Kullanıcının şu anki `.gui_settings.json` dosyasını oku ve
   AÇIK olan her geçişin gerçekten çalışacağını doğrula. Çalışmayacak
   olan varsa öne çıkar.
5. Koşu sırasında değiştirilen bir ayar ne oluyor? Anlık görüntü onu
   dondurmalı. Dondurmayan (canlı `.get()` çağrısı yapan) yer var mı?
   `_freeze_run_variable_reads` neyi kapsıyor, neyi kapsamıyor?
6. Varsayılanı son bir ayda değişmiş geçişler var (terim normalizasyonu,
   cue-fill taşıma, max_retry, kimlik eşlemeleri). Bunların ETİKETLERİ
   yeni davranışı doğru anlatıyor mu?
```

---

## 4 — Aynı dosyayı iki kez çevirsem aynı sonucu alır mıyım?

```
Program çok sayıda kalıcı durum tutuyor: `.context_cache/`,
`translation_memory.db`, `.series_memory/`, `<klasör>/.project_memory.json`,
`.quality_response_checkpoint/`. Bunların hepsi sonraki çeviriyi
etkiliyor. Yani aynı dosya, aynı ayarlarla iki kez çevrildiğinde farklı
çıkabilir — ve bu bazen istenen, bazen bug.

Cevaplaman gerekenler:
1. Bir dosyanın çevirisini etkileyen BÜTÜN kalıcı durum kaynaklarını
   listele. Her biri için: ne zaman yazılır, ne zaman okunur, ne zaman
   geçersizleşir?
2. Bunlardan hangisi ÇEVİRİYİ DEĞİŞTİRİR, hangisi yalnız hızlandırır?
   (Cache yalnız hızlandırmalı; bellek çeviriyi değiştirebilir.)
3. Sıra bağımlılığı ara: A dosyası B'den önce çevrilirse B'nin sonucu
   değişir mi? Hangi durum kaynağı üzerinden? Gerçek koşu loglarında
   aynı dizinin bölümlerinin farklı sırayla çevrildiği bir vaka bul ve
   sonuçlarını karşılaştır.
4. `.context_cache` parmak izi neyi kapsıyor? Kapsamadığı ama analizi
   etkileyen bir girdi var mı? (Örnek arıyorsan: analiz PROMPT'u
   değişirse sürüm elle artırılmalı — son sürüm artışından bu yana
   analiz semantiğini değiştiren bir commit var mı, `git log` ile bak.)
5. Bir dosya YARIM kalıp yeniden çevrilirse ne oluyor? Checkpoint'ler
   hangi kısmı atlıyor, hangi kısmı tekrar ücretlendiriyor?
6. Gerçek arşivde, aynı dosyanın iki kez çevrilmiş olduğuna dair kanıt
   ara (`.ham.srt`, `.bak.srt`, `Raporlar/Kurtarma/` altındaki sürümler).
   İki sürümü karşılaştır: fark ne kadar, farkın kaynağı hangi durum?
```

---

## 5 — Komut satırı araçları teslim dosyasına yazıyor

```
`repair_batches.py`, `resume_batch.py` ve `subtitle_batch_translate.py`
GUI'den bağımsız çalışan araçlar ve TESLİM EDİLMİŞ altyazı dosyalarını
değiştirebiliyorlar. GUI akışları defalarca denetlendi; bu üçü neredeyse
hiç denetlenmedi.

Cevaplaman gerekenler:
1. Üçünün de yazma yollarını çıkar. Hangi dosyayı, hangi koşulla, hangi
   yedekle değiştiriyorlar? Yazma atomik mi?
2. GUI'nin teslim kapısı (sert hata taraması, karantina, parmak izi) bu
   araçlarda da çalışıyor mu, yoksa atlanıyor mu? Atlanıyorsa bu araçla
   onarılan bir dosya denetimsiz teslim edilmiş olur — gerçek arşivde
   böyle dosya var mı?
3. GUI ile aynı anda çalışırlarsa ne olur? Aynı çıktı dosyasına iki
   yazıcı. Süreçler arası kilit alıyorlar mı?
4. `repair_batches.py` yedeği `.repair.bak` olarak alıyor. Yedek yarım
   kalırsa ne olur? Yedek ne zaman silinir? Gerçek arşivde kaç tane var?
5. Bu araçlar GUI'nin kalite geçişlerini ve teslim cilasını (etiket geri
   yükleme, satır kırma, binlik ayracı) uyguluyor mu? Uygulamıyorsa
   onarılan cue'lar diğerlerinden farklı biçimde kalır — gerçek
   dosyalarda bunun izini ara.
6. Bu araçların yazdığı bir dosya, GUI'nin kalite raporuna yansıyor mu?
   Yoksa rapor artık dosyanın gerçek hâlini anlatmıyor demektir.
```

---

## 6 — Biçimlendirme çeviriden sonra geri konurken

```
Çeviriden ÖNCE `_clean_src` kaynaktaki `<i>`, `{\an8}` gibi biçim
etiketlerini sıyırıyor; en SONDA `_restore_tags_blocks` onları geri
koyuyor. Arada metin baştan yazılmış olabiliyor (Critic, Polish, Native,
condense, satır kırma, terim normalizasyonu). Yani etiketler, artık
sözcük sayısı ve sırası farklı olan bir metne geri konuyor.

Cevaplaman gerekenler:
1. `_restore_tags_blocks` etiketi nereye koyuyor? Konumu neye göre
   belirliyor — karakter ofseti mi, sözcük indeksi mi, tüm cue'yu mu
   sarıyor? Metin uzunluğu değiştiyse ne oluyor?
2. Gerçek 202 teslim dosyasında etiketleri say ve kaynakla karşılaştır:
   - Kaynakta olup teslimde OLMAYAN etiket kaç tane?
   - Teslimde olup kaynakta olmayan kaç tane?
   - Açılmış ama kapanmamış (`<i>` var `</i>` yok) kaç cue var?
   - Yanlış yere kaymış görünen (cümlenin ortasında başlayan italik)
     kaç cue var?
3. Diyalog tireleri: kaynakta iki konuşmacılı cue (`- ...` / `- ...`)
   teslimde de iki satır ve iki tire olarak duruyor mu? Kaç cue'da
   bozulmuş? Satır kırma geçişi tire yapısını bozuyor mu?
4. `{\an8}` gibi ASS konum etiketleri `.srt` çıktıya doğru taşınıyor mu?
   `.ass` kaynaklı teslimlerde stil bilgisi ne oluyor?
5. Satır kırma ve binlik ayracı gibi SON adımlar, etiket geri
   yüklendikten SONRA mı ÖNCE mi çalışıyor? Sıra yanlışsa etiket
   içindeki boşluğa satır sonu girebilir — gerçek dosyalarda ara.
6. `_visible_len` etiketleri sayıyor mu? Sayıyorsa etiketli satırlar
   gereğinden erken kırılıyor demektir; gerçek dosyalarda etiketli ve
   etiketsiz satırların uzunluk dağılımını karşılaştır.
```
