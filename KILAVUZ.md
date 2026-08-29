# Kullanım Kılavuzu

> Bu dosya `kilavuz.py`'den ÜRETİLİR (`python belge_uret.py`).
> Elle düzenlemeyin; değişiklik bir sonraki üretimde silinir.

Programın içindeki **Yardım** penceresi de aynı kaynaktan beslenir, üstüne arama yapabilirsiniz.

## Çeviri Akışı

### Ana Model — Özel Sağlayıcı

**Varsayılan:** açık

Çeviriyi kendi anahtarınız ve adresinizle başka bir sağlayıcı üzerinden yaptırabilirsiniz. Bu alanlar gerçek OpenAI anahtarı alanından TAMAMEN AYRIDIR — özel sağlayıcıyı açıp kapatmak OpenAI anahtarınıza dokunmaz, onu bozamaz ya da silemez.

Sağlayıcının modeli aynı isimde olsa bile aynı kalitede olmayabilir; çıktıyı bir dosyada karşılaştırmadan kalıcı olarak geçmeyin.

**Ne zaman:** Maliyet ya da erişim nedeniyle başka bir sağlayıcı kullanıyorsanız. Yalnız OpenAI kullanıyorsanız kapalı.

### İki-Dalgalı Zincirli Batch

**Varsayılan:** kapalı
  ·  **Maliyet:** Süre iki katına çıkar; para maliyeti değişmez.

Toplu (batch) mod ucuzdur ama parçaları aynı anda gönderdiği için zincirleme bağlam kurulamaz. Bu seçenek dosyayı ikiye böler: önce ilk yarı çevrilir, sonuç ikinci yarının istemine eklenir, sonra ikinci yarı gönderilir.

Kazanç sınırlıdır — eşzamanlı moddaki N-1 zincir sınırından yalnız BİRİ kurulur. Bedeli ise beklemenin iki katına çıkması ve toplu akışa sıralı bir durum eklenmesidir.

**Ne zaman:** Yalnız toplu modda ve tutarlılık sorunu yaşadığınız uzun dosyalarda deneyin. Aceleniz varsa kapalı bırakın.

**İlgili:** Zincirleme Bağlam

### Yardımcı Analiz (Hibrit Mod)

**Varsayılan:** açık
  ·  **Maliyet:** Dosya başına bir ek analiz çağrısı.

Kapalıyken program altyazıyı parçalara böler ve her parçayı çevirir. Açıkken önce bir ön geçiş dosyanın TAMAMINI okur ve şunları çıkarır: kim kimdir, kim kime 'sen' kim kime 'siz' der, tekrar eden terimler, sahnelerin duygusu, genel üslup.

Bu analiz sonra her parçanın istemine eklenir. Fark en çok hitapta ve terim tutarlılığında görülür: analiz olmadan model her parçada 'sen/siz' kararını yeniden verir.

**Ne zaman:** Film ve belgesellerde açık tutun. Çok kısa dosyalarda (200 cue altı) analizin maliyeti kazancından fazla olabilir.

**İlgili:** Ön-Bağlam Analizi, Zincirleme Bağlam, Auto-Glossary (Otomatik Sözlük)

### Zincirleme Bağlam

**Varsayılan:** açık

Model bir sonraki parçayı çevirirken yalnız kaynağı değil, önceki satırların Türkçe karşılığını da görür. Böylece bir karakterin adı, bir terimin karşılığı ve hitap biçimi parça sınırında değişmez.

Bu, dosya boyunca tutarlılığın en güçlü tek aracıdır; kapalıyken her parça kendi başına doğru ama birbiriyle uyumsuz olabilir.

**Ne zaman:** Açık tutun. Batch (toplu) modda zincir kurulamaz, çünkü parçalar aynı anda gönderilir — orada İki-Dalgalı Batch kısmi bir karşılık sunar.

**İlgili:** İki-Dalgalı Zincirli Batch, Dizi Hafızası

### Ön-Bağlam Analizi

**Varsayılan:** açık

Yardımcı Analiz'in ürettiği dosya özeti `.context_cache/` altına kaydedilir. Aynı altyazıyı ikinci kez çevirdiğinizde (ayar denemek, model değiştirmek, yarım kalanı tamamlamak) analiz çağrısı tekrarlanmaz.

Önbellek kaynak dosyanın kendisine bağlıdır: kaynağı değiştirirseniz analiz yeniden yapılır.

**Ne zaman:** Açık bırakın. Kapatmanın tek anlamı analizi her seferinde sıfırdan istemektir.

**İlgili:** Yardımcı Analiz (Hibrit Mod)

## Kalite Geçişleri

### Bağlam İncelemesi (Batch)

**Varsayılan:** kapalı
  ·  **Maliyet:** Yardımcı modelle bir ek geçiş.

Toplu modda parçalar birbirini görmeden çevrildiği için tutarlılık sorunları oluşabilir. Bu geçiş tamamlanmış dosyayı baştan sona okuyup parça sınırlarındaki kopuklukları düzeltir.

Yalnız toplu (batch) akışta çalışır; metni DEĞİŞTİRİR.

**Ne zaman:** Toplu mod kullanıyorsanız ve zincirleme bağlamın yokluğunu hissediyorsanız.

**İlgili:** Zincirleme Bağlam, İki-Dalgalı Zincirli Batch

### Critic (Eleştirmen) Geçişi

**Varsayılan:** açık
  ·  **Maliyet:** Yardımcı modelle bir ek geçiş.

Yardımcı model çeviriyi kaynakla karşılaştırır ve şüpheli satırları listeler. Bulgular kalite raporuna yazılır.

Bu geçiş bir dönem düzeltmeleri OTOMATİK uyguluyordu ve dört sınıfta çeviriyi bozduğu ölçüldü (sözlüğü körlemesine dayatma, iyelik ekini düşürme, çifte olumsuzlama, yazıyla yazılmış sayıyı rakama çevirme). Bu yüzden artık yalnız rapor eder.

**Ne zaman:** Açık tutun; maliyeti düşük, bulduğu şey gerçek.

**İlgili:** Teslim + Otomatik Düzeltme: Yalnız Raporla, Polish (Cilalama) Geçişi

### Derin Teslim Anlam Taraması

**Varsayılan:** açık

Teslim edilecek dosya kaynakla eşleştirilir ve cümle bütünlüğü, düşen parça, kayan içerik aranır. Kalite raporuna adresli bulgu olarak yazılır.

Çeviriyi bir insana ya da bir modele okutacaksanız KAPALI bırakın — düzeltmeyi zaten o yapacak, bu geçişin bulguları gürültü olur.

**Ne zaman:** Doğrudan yayınlanacak işlerde açık; üzerinden geçilecek işlerde kapalı.

**İlgili:** Teslim + Otomatik Düzeltme: Yalnız Raporla, Geri Çeviri Anlam Kontrolü

### Geri Çeviri Anlam Kontrolü

**Varsayılan:** kapalı
  ·  **Maliyet:** Yüksek — kontrol edilen satır başına ek çağrı.

Şüpheli satırlar İngilizceye geri çevrilir ve orijinaliyle karşılaştırılır. Sapma büyükse satır işaretlenir. Anlamın tersine dönmesi gibi, akıcı ama yanlış çevirileri yakalamanın birkaç yolundan biridir.

Pahalıdır: her kontrol edilen satır için ek bir çağrı.

**Ne zaman:** Anlam doğruluğunun kritik olduğu belgesellerde ve maliyeti göze aldığınızda.

**İlgili:** Nihai Anlam Mutabakatı, Derin Teslim Anlam Taraması

### Native Okuyucu

**Varsayılan:** kapalı
  ·  **Maliyet:** Yardımcı modelle bir ek geçiş.

Polish'ten farkı odağıdır: cümle cümle akıcılık değil, metnin bütününün Türkçe kulağa doğal gelip gelmediği. Çeviri kokan kalıpları, İngilizce söz dizimi kalıntısını ve zorlama deyimleri hedefler.

Metni DEĞİŞTİREN bir geçiştir.

**Ne zaman:** Doğrudan yayınlanacak işlerde, Polish ile birlikte.

**İlgili:** Polish (Cilalama) Geçişi

### Nihai Anlam Mutabakatı

**Varsayılan:** kapalı
  ·  **Maliyet:** Yardımcı modelle bir ek geçiş.

Bütün kalite geçişleri bittikten sonra, yazılacak metin kaynakla bir kez daha karşılaştırılır ve ayrışan yerler düzeltilir. Amaç, önceki geçişlerin (Polish, Native, kısaltma) anlamdan uzaklaştırdığı satırları geri çekmektir.

Metni DEĞİŞTİREN bir geçiştir.

**Ne zaman:** Metni yeniden yazan geçişleri açtıysanız, güvenlik ağı olarak.

**İlgili:** Geri Çeviri Anlam Kontrolü, Polish (Cilalama) Geçişi, Native Okuyucu

### Polish (Cilalama) Geçişi

**Varsayılan:** kapalı
  ·  **Maliyet:** Yardımcı modelle bir ek geçiş.

Yardımcı model Türkçeyi daha doğal hâle getirmek için satırları yeniden yazar. Anlamı değil ifadeyi hedefler.

Metni DEĞİŞTİREN bir geçiştir: sonucu bir insan ya da başka bir model okuyacaksa gereksizdir, çünkü okuyan zaten düzeltecektir. Kelime birleşmesi ve karakter düşmesine karşı koruması vardır, ama yine de her değişikliği geri alamazsınız.

**Ne zaman:** Çeviriyi doğrudan yayınlayacaksanız açın. Üzerinden geçecekseniz kapalı bırakın.

**İlgili:** Critic (Eleştirmen) Geçişi, Native Okuyucu, Teslim + Otomatik Düzeltme: Yalnız Raporla

### QC Kontrolü

**Varsayılan:** kapalı
  ·  **Maliyet:** Yardımcı modelle bir ek geçiş.

Teslim öncesi son bakış: eksik çeviri işareti, bariz tutarsızlık, biçim bozukluğu. Bulduğunu düzeltebilir.

Metni DEĞİŞTİREN bir geçiştir.

**Ne zaman:** Deterministik teslim taraması bunun çoğunu zaten yapar; ek güvence isterseniz açın.

**İlgili:** Teslim + Otomatik Düzeltme: Yalnız Raporla

## Metin Biçimi

### AI Akıllı Segmentasyon

**Varsayılan:** kapalı
  ·  **Maliyet:** Yardımcı model çağrısı.

Parçalı Cue Birleştir'in model destekli hâli. Nerede birleştirileceğine cümle yapısına bakarak karar verir.

Bu ikisinden BİRİ açıksa cue yapısı değişir. İkisi de aynı kapıyı açar; 'metni yeniden yazma' kipi ikisini birden kapatır.

**Ne zaman:** Parçalı Cue Birleştir'i kullanıyorsanız ve sonuçtan memnun değilseniz.

**İlgili:** Parçalı Cue Birleştir

### Cue-fill Taşıma

**Varsayılan:** açık

Zaman damgalarına DOKUNMAZ; yalnız iki cue arasındaki bölme noktası kayar ve birleşik metin aynı kalır. Ölçüt dardır: alıcı cue kendi hız ve genişlik sınırları içinde kalmalı, kaynak cue anlamlı ölçüde rahatlamalı, cümle kaynağa göre gerçekten devam ediyor olmalı.

Yine de gerekçesi uzunluktur; uzunluk tek başına bir cue'ya dokunmak için yeterli sayılmıyorsa kapalı tutun.

**Ne zaman:** Okuma hızı sizin için ölçütse açık; satır yapısı kaynağa uysun diyorsanız kapalı.

**İlgili:** Satır Kırma, Okuma Hızı Kısaltma

### Okuma Hızı Kısaltma

**Varsayılan:** kapalı
  ·  **Maliyet:** Kısaltılan cue başına yardımcı model çağrısı.

Saniyede düşen karakter sayısı sınırı aşan cue'lar yardımcı modele kısaltılmak üzere gönderilir. Anlamı koruyarak sözcük eksiltmesi beklenir.

Metni DEĞİŞTİREN bir geçiştir ve kısaltma anlam kaybı riski taşır; çıktı doğrulayıcıları vardır ama uzunluk tek başına bir cue'ya dokunmak için yeterli gerekçe değildir.

**Ne zaman:** Okuma hızı sizin için bir teslim ölçütüyse açın; kaynağa sadakat önceliğinizse kapalı bırakın.

**İlgili:** Satır Kırma, Cue-fill Taşıma

### Parçalı Cue Birleştir

**Varsayılan:** kapalı

Bir cümlenin arka arkaya birkaç kısa cue'ya bölündüğü kaynaklarda, bunları tek cue'da toplar. Zaman damgaları birleşir.

Teslimin cue yapısını DEĞİŞTİRİR: cue sayısı ve zamanlar kaynaktan farklı olur.

**Ne zaman:** Kaynak aşırı parçalıysa. Kaynak yapısını korumak istiyorsanız kapalı.

**İlgili:** AI Akıllı Segmentasyon, Cue-fill Taşıma

### Satır Kırma

**Varsayılan:** açık

Satırları okunabilir uzunlukta tutmak için kırma noktalarını yeniden hesaplar.

Kaynağın satır yapısını korumak istiyorsanız KAPALI tutun: kapalıyken teslim, cue içindeki satır bölünmesini orijinal altyazıdaki gibi bırakır.

**Ne zaman:** Kaynak altyazının satır yapısına sadık kalmak istiyorsanız kapatın.

**İlgili:** Okuma Hızı Kısaltma, Cue-fill Taşıma

### SDH Temizle

**Varsayılan:** açık

`[kapı çarpar]`, `(müzik)`, `ADAM:` gibi işitme engelliler için eklenmiş etiketler teslimden çıkarılır. Yalnız etiketten ibaret olan cue'lar tamamen düşer.

Etiket kaynakta İngilizce kalmış da olsa, modelden Türkçe dönmüş de olsa yakalanır.

**Ne zaman:** İşitme engelli altyazısı üretmiyorsanız açık tutun.

## Terim ve Tutarlılık

### Auto-Glossary (Otomatik Sözlük)

**Varsayılan:** kapalı
  ·  **Maliyet:** Dosya başına yardımcı model çağrısı.

Yardımcı model dosyada tekrar eden özel ad ve terimleri çıkarır ve sözlüğe aday olarak sunar. Sözlüğe giren terim sonraki parçaların ve sonraki bölümlerin isteminde sabit karşılığıyla görünür.

Sözlük üç ayrı şekilde bozulabilir (toplu dil çökmesi, çok kısa gloss, 'nasıl çevrilmeli' notunun terim sanılması); üçüne karşı da ayrı koruma vardır.

**Ne zaman:** Terim yoğun işlerde (belgesel, tarih, bilim) açın.

**İlgili:** Terim Normalizasyonu, Dizi Hafızası

### Dizi Hafızası

**Varsayılan:** açık

Bir bölümde verilmiş kararlar (karakterin adı nasıl yazılıyor, kim kime 'siz' diyor, terimin karşılığı ne) sonraki bölümlerin istemine eklenir. Bölümün hangi diziye ait olduğu klasör adından anlaşılır.

Aynı sezonun bölümlerini sırayla çevirdiğinizde en çok işe yarar.

**Ne zaman:** Dizi çeviriyorsanız açık tutun. Tek dosyalık işlerde etkisi yoktur.

**İlgili:** Sezon Sonu Kanon Denetimi, Zincirleme Bağlam

### Sezon Sonu Kanon Denetimi

**Varsayılan:** kapalı
  ·  **Maliyet:** Sezon başına bir denetim geçişi.

Sezonun tamamı başarıyla çevrildiğinde, bölümler arası terim ve hitap ayrışmaları aranır. Tek bölüme bakarak görülemeyen sınıf budur: bölüm 3'te 'siz', bölüm 7'de 'sen'.

Sezonun tamamı seçili değilse ya da bölümlerden biri başarısızsa denetim atlanır ve raporda sebebi yazılır.

**Ne zaman:** Bir sezonun tamamını tek seferde çevirirken açın.

**İlgili:** Dizi Hafızası

### Terim Düzeltmelerini Uygula

**Varsayılan:** açık

Terim Normalizasyonu'nun bulduğu farklı yazımlar tek biçime getirilir. Metni DEĞİŞTİREN bir adımdır.

Terim Normalizasyonu kapalıysa bunun etkisi yoktur.

**Ne zaman:** Tespitin doğruluğuna güvendiğinizde açık; her değişikliği kendiniz görmek istiyorsanız kapalı.

**İlgili:** Terim Normalizasyonu

### Terim Normalizasyonu

**Varsayılan:** açık

Bir özel ad ya da terim aynı dosyada iki biçimde geçiyorsa (`Göbekli` / `Gobekli`, `Truva` / `Troy`) tespit edilir. Çoğunluk biçimi değil, hangisinin sızıntı olduğu değerlendirilir — ham sıklığa güvenilmez.

**Ne zaman:** Açık tutun; tespit tek başına metne dokunmaz.

**İlgili:** Terim Düzeltmelerini Uygula, Auto-Glossary (Otomatik Sözlük)

## Teslim ve Güvenlik

### Eksik Cue API Onarımı

**Varsayılan:** kapalı
  ·  **Maliyet:** Eksik cue başına ek çağrı.

Bir parça hata verdiğinde ya da model bazı cue'ları atladığında, geride `[ÇEVİRİ EKSİK]` işaretli satırlar kalır. Bu seçenek açıkken o satırlar için hedefli yeni çağrılar yapılır.

Kapalıyken satır işaretli kalır ve raporda görünür — böylece eksiği siz görüp karar verirsiniz.

**Ne zaman:** Elle müdahale etmek istemiyorsanız açın.

**İlgili:** Başarısız Dosyaları Otomatik Yeniden Dene

### Ham Çeviri Yedeği (.ham.srt)

**Varsayılan:** açık

Critic, Polish, Native, kısaltma gibi geçişler çeviriyi değiştirebilir. Bu yedek onlardan etkilenmez; bir geçiş bir satırı bozduysa doğrusu burada durur.

Ham ile teslim arasındaki içerik farkı ayrıca denetlenir: yedekte olup teslimde olmayan diyalog, gerçek bir kayıptır.

**Ne zaman:** Açık bırakın. Tek maliyeti disk alanıdır.

**İlgili:** Teslim + Otomatik Düzeltme: Yalnız Raporla

### Teslim + Otomatik Düzeltme: Yalnız Raporla

**Varsayılan:** açık

Açıkken teslim taraması ve otomatik düzelticiler çalışır, buldukları kalite raporuna ve bulgu kaydına yazılır, ama dosyaya dokunulmaz. Log'da 'teslim metni değiştirilmedi' satırını görürsünüz.

Çeviriyi kendiniz ya da bir model üzerinden geçireceksiniz açık tutun: hem düzeltmeyi siz yaparsınız hem de programın neyi şüpheli bulduğunu görürsünüz.

**Ne zaman:** Üzerinden geçilecek işlerde açık. Programın çıktısını olduğu gibi yayınlayacaksanız kapatın.

**İlgili:** Critic (Eleştirmen) Geçişi, Derin Teslim Anlam Taraması, Terim Düzeltmelerini Uygula

## Çalışma ve Kurtarma

### Aynı Klasöre Kaydet

**Varsayılan:** kapalı

Açıkken her çeviri kendi kaynak dosyasının bulunduğu klasöre yazılır. Film klasörlerini tek tek düzenliyorsanız pratiktir.

Kapalıyken hepsi seçtiğiniz tek çıktı klasörüne gider.

**Ne zaman:** Her filmin kendi klasörü varsa açın.

### Başarısız Dosyaları Otomatik Yeniden Dene

**Varsayılan:** açık

Ağ hatası, geçici sağlayıcı arızası ya da tek seferlik bir model hatası yüzünden düşen dosyalar otomatik tekrarlanır. Deneme sayısı sınırlıdır; kalıcı bir hata sonsuz döngüye girmez.

**Ne zaman:** Açık bırakın.

**İlgili:** Çökme Sonrası Otomatik Devam, Yardımcı Model Rota Yedeklemesi

### Bitince Bilgisayarı Kapat

**Varsayılan:** kapalı

Gece boyunca çeviri bırakıp sabah bitmiş bulmak için. Kapatma öncesi bir uyarı penceresi çıkar ve iptal etme şansı verir.

Rapor ve yedekler kapatmadan ÖNCE yazılır.

**Ne zaman:** Uzun bir kuyruğu gözetimsiz bırakırken.

**İlgili:** Çalışırken Uyku Modunu Engelle, Masaüstü Bildirimi

### Canlı İlerleme Animasyonları

**Varsayılan:** açık

Yalnız görünümü etkiler; çeviriye ya da çıktıya hiçbir etkisi yoktur. Zayıf makinelerde kapatmak arayüzü hafifletir.

**Ne zaman:** Arayüz takılıyorsa kapatın.

### Masaüstü Bildirimi

**Varsayılan:** açık

Program arka planda çalışırken bitişi ve önemli hataları haber verir.

**Ne zaman:** Bilgisayarın başında beklemiyorsanız.

**İlgili:** Bitince Bilgisayarı Kapat

### Yardımcı Model Rota Yedeklemesi

**Varsayılan:** açık

Bazı sağlayıcılar aynı modeli birden çok adresten sunar ve bunlardan biri geçici olarak düşebilir. Açıkken her deneme için rota yeniden seçilir; bir adres arızalıysa istek diğerine gider.

Sağlayıcıdan gelen 404 iki ayrı şey demek olabilir: model o grupta yok, ya da kanal geçici düştü. Teşhis için hata gövdesine bakılır.

**Ne zaman:** Üçüncü taraf sağlayıcı kullanıyorsanız açık bırakın.

**İlgili:** Ana Model — Özel Sağlayıcı

### Çalışırken Uyku Modunu Engelle

**Varsayılan:** açık

Uzun çeviriler saatler sürebilir. Bilgisayar uykuya geçerse ağ istekleri kesilir ve dosyalar hata alır. Bu seçenek çeviri sürdüğü sürece sistemin uyanık kalmasını ister; iş bitince kısıtlama kalkar.

**Ne zaman:** Açık bırakın.

**İlgili:** Bitince Bilgisayarı Kapat

### Çökme Sonrası Otomatik Devam

**Varsayılan:** açık

Çeviri sırasında durum diske yazılır. Program kapanır ya da bilgisayar kapanırsa, bir sonraki açılışta tamamlanmamış dosyalar sıraya alınır ve baştan çevrilmez.

Toplu (batch) işler için ayrıca `batch_id` kaydı tutulur; ödenmiş bir toplu iş kaybolmaz.

**Ne zaman:** Açık bırakın.

**İlgili:** Başarısız Dosyaları Otomatik Yeniden Dene

## Rapordaki bulgu sınıfları

Teslim taraması bu sınıfları arar. Her bulgu bir cue numarası ve zaman damgasıyla adreslenir.

Güven dereceleri:

- **kesin** — Neredeyse her zaman gerçek bir hata; teslimi durdurur.
- **muhtemel** — Çoğu zaman gerçek, ama bakmadan düzeltmeyin.
- **bilgi** — Kayıt amaçlı; düzeltme gerekçesi olmayabilir.

| sınıf | güven | ne demek | ne yapmalı |
|---|---|---|---|
| `broken_italic_ids` | kesin | Dengesiz/iç içe italik etiketi | Tek dış <i>…</i> çiftine indir. |
| `cue_id_leak_ids` | kesin | Metne sızmış cue numarası | Sızan numarayı sil. |
| `delivery_owner_mismatch_ids` | bilgi | Sahiplik eşleşmedi | Eşleme incelemesi. |
| `duplicate_cue_ids` | kesin | Yinelenen cue kimliği | Kimliği tekilleştir. |
| `duplicate_translation_ids` | muhtemel | Yakın cue'larda çeviri tekrarı | İki cue'nun KAYNAĞINI karşılaştır; farklıysa birini yeniden çevir. |
| `english_filler_ids` | muhtemel | Çevrilmemiş İngilizce dolgu | Türkçe karşılığına çevir (ee/şey). |
| `expected_removed_ids` | bilgi | Bilinçli silinen cue | Beklenen davranış; kayıt için. |
| `extra_dialogue_ids` | bilgi | Kaynakta olmayan cue | Fazladan içerik mi bak. |
| `foreign_script_ids` | muhtemel | Yabancı yazı sistemi | Hedef dile çevir. |
| `format_coverage_lost_ids` | muhtemel | Kaynaktaki biçim etiketi kaybolmuş | Etiketi geri koy. |
| `garble_ids` | muhtemel | Bozulmuş sözcük | Kaynağa göre yeniden yaz. |
| `inconsistent_repeat_ids` | muhtemel | Aynı dize farklı çevrilmiş | Tekrarlanan dizeyi tek Türkçeye getir. |
| `inherited_out_of_order_ids` | bilgi | Sıra bozulması (kaynaktan) | Kaynakta da var. |
| `introduced_out_of_order_ids` | muhtemel | Sıra bozulması (bu koşuda) | Sırayı düzelt. |
| `invalid_timestamp_ids` | kesin | Geçersiz zaman damgası | Zaman damgasını düzelt. |
| `line_parity_mismatch_ids` | bilgi | Satır sayısı kaynaktan farklı | Kayıt için; geriye dönük onarım istenmiyor. |
| `merged_into_neighbour_ids` | bilgi | İçerik komşu cue'ya birleşmiş olabilir | Önceki cue'yu oku; anlam oradaysa bölüştür, değilse çevir. |
| `midword_space_ids` | bilgi | Kelime ortası boşluk | Bitişik yazılmalı mı bak (`Hiç bir`->`Hiçbir`). |
| `missing_dialogue_ids` | muhtemel | Teslimde eksik diyalog | Kaynaktaki repliği çevirip ekle. |
| `missing_predicate_ids` | muhtemel | Yüklemsiz biten cue | Cümle sonraki cue'da tamamlanıyor mu bak. |
| `non_monotonic_cue_ids` | kesin | Cue numarası geri gidiyor | Numaraları yeniden sırala. |
| `ocr_artifact_ids` | muhtemel | OCR kalıntısı | Kaynağa göre düzelt. |
| `partial_echo_ids` | bilgi | Komşu cue'da kısmi yankı | İki cue'yu birlikte oku; tekrar meşru olabilir. |
| `quote_chain_ids` | bilgi | Alinti zincirinin her cue'sunda tirnak | Turkcede alinti bir kez acilir; zinciri gozle oku. |
| `repetition_collapse_ids` | kesin | Cue içi tekrar çöküşü | Kaynaktan yeniden çevir. |
| `residual_credit_ids` | muhtemel | Kalıntı künye | Cue'yu sil. |
| `residual_sdh_ids` | muhtemel | Kalıntı SDH etiketi | Etiketi sil. |
| `residual_speaker_label_ids` | muhtemel | Kalıntı konuşmacı etiketi | Öneki soy. |
| `reversed_timestamp_ids` | kesin | Ters zaman damgası | Başlangıç bitişten sonra; düzelt. |
| `semantic_loss_ids` | muhtemel | Anlam kaybı | Kaynakla karşılaştır. |
| `serialized_json_residue_ids` | kesin | Metne sızmış JSON kalıntısı | Kalıntıyı sil. |
| `signature_cue_id_ids` | kesin | İmza cue numarası sapmış | Baş imza 0, diğerleri öncekinin bir fazlası olmalı. |
| `signature_overlap_ids` | kesin | İmza cue'su çakışıyor | İmza zamanını kaydır. |
| `source_residue_ids` | muhtemel | Türkçe ekli kaynak kalıntısı | Sözcüğü Türkçeye çevir. |
| `stray_line_initial_e_ids` | kesin | Satır başında tek başına 'e' | Bağlama göre 've' yap, sil ya da sonraki sözcüğe ekle. |
| `timestamp_mismatch_ids` | bilgi | Zaman damgası kaymış | Eşleme incelemesi. |
| `translator_gloss_ids` | muhtemel | Kaynakta olmayan cevirmen aciklamasi | Kaynakta yoksa parantezi kaldirmayi degerlendir; anlami degistirme. |
| `unbalanced_note_ids` | kesin | Nota işareti tek kalmış | Kapanış ♪ işaretini geri koy. |
| `untranslated_fragment_ids` | muhtemel | Çevrilmemiş parça | Kaynaktan çevir. |

## İçerik türleri

Her tür kendi çeviri kurallarını taşır. "Otomatik" seçilirse tür dosyanın kendisinden tespit edilir. Toplam **74** tür:

- academic_lecture · action_crime · adult_animation · animation_kids
- anime · archaeology_ancient_history · art_culture · artist_biography_period
- auto · auto_motorsport · biopic · bollywood_indian
- business_economy · cinema_film · collector_reality · comedy
- comedy_biography_documentary · cyberpunk_sci_fi · documentary · drama_general
- esoteric_occult · experimental_essay_film · film · food_travel
- frp · game_show · gaming · gonzo_science
- gonzo_subculture · historical · history_documentary · horror_thriller
- howto_craft · kdrama · kids_animation · legal_courtroom
- martial_arts_wuxia · medical · music_documentary · musical
- mythology_ancient_world · nature_wildlife · news · noir
- nordic_noir · philosophical_theological_dialogue · podcast_interview · police_procedural
- political_art_cinema · psychological_institutional_drama · psychology_selfhelp · reality
- reality_street · religious_faith · romance_drama · science_space
- scifi_fantasy · series · shockumentary · sketch_comedy
- society_politics_documentary · sports · spy_political_thriller · standup
- superhero_comic · talk_show · tech_review · telenovela
- true_crime · war_military · warhammer40k · western
- youtube · youtube_edu
