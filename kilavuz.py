# -*- coding: utf-8 -*-
"""Kullanım kılavuzunun TEK VERİ KAYNAĞI.

Buradaki her kayıt üç yerde birden kullanılır:
  1. Arayüzde kutunun üstüne gelince çıkan tek satırlık ipucu (`kisa`)
  2. Yardım penceresindeki tam anlatım (`uzun` + `ne_zaman`)
  3. Yayın için üretilen README/kılavuz dosyası

Metni koda yakın tutmanın sebebi: elle yazılan kılavuz birkaç ay sonra
koddan sapar. `tests/test_kilavuz.py` her kutunun burada karşılığı
olduğunu VE `varsayilan` alanının koddaki gerçek varsayılana eşit
olduğunu doğrular; yeni bir kutu kılavuzsuz teslim edilemez.

İçerik türleri (`CONTENT_SCHEMAS`) ve bulgu sınıfları (`_FINDING_CLASSES`)
elle YAZILMAZ — kendi tanımlarından üretilir, bkz. `uretilen_bolumler`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Madde:
    """Kılavuzun tek bir maddesi."""

    baslik: str
    bolum: str
    kisa: str
    uzun: str
    varsayilan: bool | None = None
    ne_zaman: str = ""
    iliskili: tuple = ()
    maliyet: str = ""
    # Kutusu olmayan madde: hep acik bir davranis, kapatilacak bir
    # secenegi yok. Kilavuzun "her madde bir kutudur" degismezi
    # bunlar icin gecmez; ayri kilitlenirler.
    arayuz_kutusu: bool = True

    def ipucu(self) -> str:
        """Kutunun üstüne gelince görünecek metin."""
        parcalar = [self.kisa]
        if self.varsayilan is not None:
            parcalar.append(
                "Varsayılan: %s" % ("açık" if self.varsayilan else "kapalı"))
        if self.maliyet:
            parcalar.append(self.maliyet)
        return "\n".join(parcalar)


# Bölümler kullanıcının okuma sırasına göre; arayüzdeki yerleşimden çok
# "önce neyi anlamam gerek" sırası.
BOLUMLER = (
    "Çeviri Akışı",
    "Kalite Geçişleri",
    "Metin Biçimi",
    "Terim ve Tutarlılık",
    "Teslim ve Güvenlik",
    "Çalışma ve Kurtarma",
)


MADDELER: dict[str, Madde] = {

    # ── Çeviri Akışı ────────────────────────────────────────────────────
    "hybrid_var": Madde(
        baslik="Yardımcı Analiz (Hibrit Mod)",
        bolum="Çeviri Akışı",
        kisa="Çeviriden önce dosyanın tamamını analiz eder; karakterleri, "
             "üslubu ve terimleri çeviri istemine ekler.",
        uzun=(
            "Kapalıyken program altyazıyı parçalara böler ve her parçayı "
            "çevirir. Açıkken önce bir ön geçiş dosyanın TAMAMINI okur ve "
            "şunları çıkarır: kim kimdir, kim kime 'sen' kim kime 'siz' der, "
            "tekrar eden terimler, sahnelerin duygusu, genel üslup.\n\n"
            "Bu analiz sonra her parçanın istemine eklenir. Fark en çok "
            "hitapta ve terim tutarlılığında görülür: analiz olmadan model "
            "her parçada 'sen/siz' kararını yeniden verir."),
        varsayilan=True,
        ne_zaman="Film ve belgesellerde açık tutun. Çok kısa dosyalarda "
                 "(200 cue altı) analizin maliyeti kazancından fazla olabilir.",
        iliskili=("precontext_var", "chain_ctx_var", "auto_glossary_var"),
        maliyet="Dosya başına bir ek analiz çağrısı.",
    ),
    "precontext_var": Madde(
        baslik="Ön-Bağlam Analizi",
        bolum="Çeviri Akışı",
        kisa="Analiz sonucunu diske yazar; aynı dosya yeniden çevrilirse "
             "analiz tekrar yapılmaz.",
        uzun=(
            "Yardımcı Analiz'in ürettiği dosya özeti `.context_cache/` "
            "altına kaydedilir. Aynı altyazıyı ikinci kez çevirdiğinizde "
            "(ayar denemek, model değiştirmek, yarım kalanı tamamlamak) "
            "analiz çağrısı tekrarlanmaz.\n\n"
            "Önbellek kaynak dosyanın kendisine bağlıdır: kaynağı "
            "değiştirirseniz analiz yeniden yapılır."),
        varsayilan=True,
        ne_zaman="Açık bırakın. Kapatmanın tek anlamı analizi her seferinde "
                 "sıfırdan istemektir.",
        iliskili=("hybrid_var",),
    ),
    "chain_ctx_var": Madde(
        baslik="Zincirleme Bağlam",
        bolum="Çeviri Akışı",
        kisa="Her parçaya, önceki parçanın NASIL çevrildiğini de gösterir.",
        uzun=(
            "Model bir sonraki parçayı çevirirken yalnız kaynağı değil, "
            "önceki satırların Türkçe karşılığını da görür. Böylece bir "
            "karakterin adı, bir terimin karşılığı ve hitap biçimi parça "
            "sınırında değişmez.\n\n"
            "Bu, dosya boyunca tutarlılığın en güçlü tek aracıdır; kapalıyken "
            "her parça kendi başına doğru ama birbiriyle uyumsuz olabilir."),
        varsayilan=True,
        ne_zaman="Açık tutun. Batch (toplu) modda zincir kurulamaz, çünkü "
                 "parçalar aynı anda gönderilir — orada İki-Dalgalı Batch "
                 "kısmi bir karşılık sunar.",
        iliskili=("twowave_var", "series_memory_var"),
    ),
    "twowave_var": Madde(
        baslik="İki-Dalgalı Zincirli Batch",
        bolum="Çeviri Akışı",
        kisa="Toplu modda dosyayı iki dalgada gönderir; ikinci dalga "
             "birincinin çevirisini bağlam olarak görür.",
        uzun=(
            "Toplu (batch) mod ucuzdur ama parçaları aynı anda gönderdiği "
            "için zincirleme bağlam kurulamaz. Bu seçenek dosyayı ikiye "
            "böler: önce ilk yarı çevrilir, sonuç ikinci yarının istemine "
            "eklenir, sonra ikinci yarı gönderilir.\n\n"
            "Kazanç sınırlıdır — eşzamanlı moddaki N-1 zincir sınırından "
            "yalnız BİRİ kurulur. Bedeli ise beklemenin iki katına çıkması "
            "ve toplu akışa sıralı bir durum eklenmesidir."),
        varsayilan=False,
        ne_zaman="Yalnız toplu modda ve tutarlılık sorunu yaşadığınız uzun "
                 "dosyalarda deneyin. Aceleniz varsa kapalı bırakın.",
        iliskili=("chain_ctx_var",),
        maliyet="Süre iki katına çıkar; para maliyeti değişmez.",
    ),
    "main_custom_var": Madde(
        baslik="Ana Model — Özel Sağlayıcı",
        bolum="Çeviri Akışı",
        kisa="Ana çeviriyi OpenAI yerine üçüncü taraf, OpenAI uyumlu bir "
             "adrese yönlendirir.",
        uzun=(
            "Çeviriyi kendi anahtarınız ve adresinizle başka bir sağlayıcı "
            "üzerinden yaptırabilirsiniz. Bu alanlar gerçek OpenAI anahtarı "
            "alanından TAMAMEN AYRIDIR — özel sağlayıcıyı açıp kapatmak "
            "OpenAI anahtarınıza dokunmaz, onu bozamaz ya da silemez.\n\n"
            "Sağlayıcının modeli aynı isimde olsa bile aynı kalitede "
            "olmayabilir; çıktıyı bir dosyada karşılaştırmadan kalıcı "
            "olarak geçmeyin."),
        varsayilan=True,
        ne_zaman="Maliyet ya da erişim nedeniyle başka bir sağlayıcı "
                 "kullanıyorsanız. Yalnız OpenAI kullanıyorsanız kapalı.",
        iliskili=(),
    ),

    # ── Kalite Geçişleri ────────────────────────────────────────────────
    "critic_var": Madde(
        baslik="Critic (Eleştirmen) Geçişi",
        bolum="Kalite Geçişleri",
        kisa="Çeviriyi ikinci bir modele okutup sorunları RAPORLAR; metni "
             "kendisi değiştirmez.",
        uzun=(
            "Yardımcı model çeviriyi kaynakla karşılaştırır ve şüpheli "
            "satırları listeler. Bulgular kalite raporuna yazılır.\n\n"
            "Bu geçiş bir dönem düzeltmeleri OTOMATİK uyguluyordu ve dört "
            "sınıfta çeviriyi bozduğu ölçüldü (sözlüğü körlemesine dayatma, "
            "iyelik ekini düşürme, çifte olumsuzlama, yazıyla yazılmış sayıyı "
            "rakama çevirme). Bu yüzden artık yalnız rapor eder."),
        varsayilan=True,
        ne_zaman="Açık tutun; maliyeti düşük, bulduğu şey gerçek.",
        iliskili=("quality_report_only_var", "polish_var"),
        maliyet="Yardımcı modelle bir ek geçiş.",
    ),
    "polish_var": Madde(
        baslik="Polish (Cilalama) Geçişi",
        bolum="Kalite Geçişleri",
        kisa="Çeviriyi akıcılık için yeniden yazar.",
        uzun=(
            "Yardımcı model Türkçeyi daha doğal hâle getirmek için satırları "
            "yeniden yazar. Anlamı değil ifadeyi hedefler.\n\n"
            "Metni DEĞİŞTİREN bir geçiştir: sonucu bir insan ya da başka bir "
            "model okuyacaksa gereksizdir, çünkü okuyan zaten düzeltecektir. "
            "Kelime birleşmesi ve karakter düşmesine karşı koruması vardır, "
            "ama yine de her değişikliği geri alamazsınız."),
        varsayilan=False,
        ne_zaman="Çeviriyi doğrudan yayınlayacaksanız açın. Üzerinden "
                 "geçecekseniz kapalı bırakın.",
        iliskili=("critic_var", "native_var", "quality_report_only_var"),
        maliyet="Yardımcı modelle bir ek geçiş.",
    ),
    "native_var": Madde(
        baslik="Native Okuyucu",
        bolum="Kalite Geçişleri",
        kisa="Metni 'anadili Türkçe bir okuyucu' gözüyle gözden geçirir.",
        uzun=(
            "Polish'ten farkı odağıdır: cümle cümle akıcılık değil, metnin "
            "bütününün Türkçe kulağa doğal gelip gelmediği. Çeviri kokan "
            "kalıpları, İngilizce söz dizimi kalıntısını ve zorlama "
            "deyimleri hedefler.\n\n"
            "Metni DEĞİŞTİREN bir geçiştir."),
        varsayilan=False,
        ne_zaman="Doğrudan yayınlanacak işlerde, Polish ile birlikte.",
        iliskili=("polish_var",),
        maliyet="Yardımcı modelle bir ek geçiş.",
    ),
    "qc_var": Madde(
        baslik="QC Kontrolü",
        bolum="Kalite Geçişleri",
        kisa="Son bir kalite kontrolü geçişi yapar.",
        uzun=(
            "Teslim öncesi son bakış: eksik çeviri işareti, bariz "
            "tutarsızlık, biçim bozukluğu. Bulduğunu düzeltebilir.\n\n"
            "Metni DEĞİŞTİREN bir geçiştir."),
        varsayilan=False,
        ne_zaman="Deterministik teslim taraması bunun çoğunu zaten yapar; "
                 "ek güvence isterseniz açın.",
        iliskili=("quality_report_only_var",),
        maliyet="Yardımcı modelle bir ek geçiş.",
    ),
    "backtrans_var": Madde(
        baslik="Geri Çeviri Anlam Kontrolü",
        bolum="Kalite Geçişleri",
        kisa="Türkçeyi kaynak dile geri çevirip aslıyla karşılaştırır.",
        uzun=(
            "Şüpheli satırlar İngilizceye geri çevrilir ve orijinaliyle "
            "karşılaştırılır. Sapma büyükse satır işaretlenir. Anlamın "
            "tersine dönmesi gibi, akıcı ama yanlış çevirileri yakalamanın "
            "birkaç yolundan biridir.\n\n"
            "Pahalıdır: her kontrol edilen satır için ek bir çağrı."),
        varsayilan=False,
        ne_zaman="Anlam doğruluğunun kritik olduğu belgesellerde ve "
                 "maliyeti göze aldığınızda.",
        iliskili=("semantic_reconcile_var", "deep_delivery_semantic_var"),
        maliyet="Yüksek — kontrol edilen satır başına ek çağrı.",
    ),
    "semantic_reconcile_var": Madde(
        baslik="Nihai Anlam Mutabakatı",
        bolum="Kalite Geçişleri",
        kisa="Kaynakla teslim arasındaki anlam farklarını son bir kez "
             "uzlaştırır.",
        uzun=(
            "Bütün kalite geçişleri bittikten sonra, yazılacak metin kaynakla "
            "bir kez daha karşılaştırılır ve ayrışan yerler düzeltilir. "
            "Amaç, önceki geçişlerin (Polish, Native, kısaltma) anlamdan "
            "uzaklaştırdığı satırları geri çekmektir.\n\n"
            "Metni DEĞİŞTİREN bir geçiştir."),
        varsayilan=False,
        ne_zaman="Metni yeniden yazan geçişleri açtıysanız, güvenlik ağı "
                 "olarak.",
        iliskili=("backtrans_var", "polish_var", "native_var"),
        maliyet="Yardımcı modelle bir ek geçiş.",
    ),
    "review_pass_var": Madde(
        baslik="Bağlam İncelemesi (Batch)",
        bolum="Kalite Geçişleri",
        kisa="Toplu modda, çeviri bittikten sonra bağlam açısından ikinci "
             "bir geçiş yapar.",
        uzun=(
            "Toplu modda parçalar birbirini görmeden çevrildiği için tutarlılık "
            "sorunları oluşabilir. Bu geçiş tamamlanmış dosyayı baştan sona "
            "okuyup parça sınırlarındaki kopuklukları düzeltir.\n\n"
            "Yalnız toplu (batch) akışta çalışır; metni DEĞİŞTİRİR."),
        varsayilan=False,
        ne_zaman="Toplu mod kullanıyorsanız ve zincirleme bağlamın yokluğunu "
                 "hissediyorsanız.",
        iliskili=("chain_ctx_var", "twowave_var"),
        maliyet="Yardımcı modelle bir ek geçiş.",
    ),
    "deep_delivery_semantic_var": Madde(
        baslik="Derin Teslim Anlam Taraması",
        bolum="Kalite Geçişleri",
        kisa="Yazılan dosyayı kaynakla cümle/parça düzeyinde karşılaştırıp "
             "anlam kaybını raporlar.",
        uzun=(
            "Teslim edilecek dosya kaynakla eşleştirilir ve cümle bütünlüğü, "
            "düşen parça, kayan içerik aranır. Kalite raporuna adresli bulgu "
            "olarak yazılır.\n\n"
            "Çeviriyi bir insana ya da bir modele okutacaksanız KAPALI "
            "bırakın — düzeltmeyi zaten o yapacak, bu geçişin bulguları "
            "gürültü olur."),
        varsayilan=True,
        ne_zaman="Doğrudan yayınlanacak işlerde açık; üzerinden geçilecek "
                 "işlerde kapalı.",
        iliskili=("quality_report_only_var", "backtrans_var"),
    ),

    # ── Metin Biçimi ────────────────────────────────────────────────────
    "linebreak_var": Madde(
        baslik="Satır Kırma",
        bolum="Metin Biçimi",
        kisa="Uzun satırları altyazı genişliğine göre yeniden böler.",
        uzun=(
            "Satırları okunabilir uzunlukta tutmak için kırma noktalarını "
            "yeniden hesaplar.\n\n"
            "Kaynağın satır yapısını korumak istiyorsanız KAPALI tutun: "
            "kapalıyken teslim, cue içindeki satır bölünmesini orijinal "
            "altyazıdaki gibi bırakır."),
        varsayilan=True,
        ne_zaman="Kaynak altyazının satır yapısına sadık kalmak istiyorsanız "
                 "kapatın.",
        iliskili=("condense_var", "cue_fill_move_var"),
    ),
    "condense_var": Madde(
        baslik="Okuma Hızı Kısaltma",
        bolum="Metin Biçimi",
        kisa="Ekranda kalma süresine göre çok uzun kalan satırları kısaltır.",
        uzun=(
            "Saniyede düşen karakter sayısı sınırı aşan cue'lar yardımcı "
            "modele kısaltılmak üzere gönderilir. Anlamı koruyarak sözcük "
            "eksiltmesi beklenir.\n\n"
            "Metni DEĞİŞTİREN bir geçiştir ve kısaltma anlam kaybı riski "
            "taşır; çıktı doğrulayıcıları vardır ama uzunluk tek başına bir "
            "cue'ya dokunmak için yeterli gerekçe değildir."),
        varsayilan=False,
        ne_zaman="Okuma hızı sizin için bir teslim ölçütüyse açın; kaynağa "
                 "sadakat önceliğinizse kapalı bırakın.",
        iliskili=("linebreak_var", "cue_fill_move_var"),
        maliyet="Kısaltılan cue başına yardımcı model çağrısı.",
    ),
    "merge_cues_var": Madde(
        baslik="Parçalı Cue Birleştir",
        bolum="Metin Biçimi",
        kisa="Bölünmüş kısa cue'ları birleştirir.",
        uzun=(
            "Bir cümlenin arka arkaya birkaç kısa cue'ya bölündüğü "
            "kaynaklarda, bunları tek cue'da toplar. Zaman damgaları "
            "birleşir.\n\n"
            "Teslimin cue yapısını DEĞİŞTİRİR: cue sayısı ve zamanlar "
            "kaynaktan farklı olur."),
        varsayilan=False,
        ne_zaman="Kaynak aşırı parçalıysa. Kaynak yapısını korumak "
                 "istiyorsanız kapalı.",
        iliskili=("ai_segment_var", "cue_fill_move_var"),
    ),
    "ai_segment_var": Madde(
        baslik="AI Akıllı Segmentasyon",
        bolum="Metin Biçimi",
        kisa="Cue bölme/birleştirme kararını basit kural yerine modele "
             "verdirir.",
        uzun=(
            "Parçalı Cue Birleştir'in model destekli hâli. Nerede "
            "birleştirileceğine cümle yapısına bakarak karar verir.\n\n"
            "Bu ikisinden BİRİ açıksa cue yapısı değişir. İkisi de aynı "
            "kapıyı açar; 'metni yeniden yazma' kipi ikisini birden "
            "kapatır."),
        varsayilan=False,
        ne_zaman="Parçalı Cue Birleştir'i kullanıyorsanız ve sonuçtan memnun "
                 "değilseniz.",
        iliskili=("merge_cues_var",),
        maliyet="Yardımcı model çağrısı.",
    ),
    "cue_fill_move_var": Madde(
        baslik="Cue-fill Taşıma",
        bolum="Metin Biçimi",
        kisa="Aşırı dolu bir cue'nun baştaki birkaç sözcüğünü, boş duran "
             "önceki cue'ya kaydırır.",
        uzun=(
            "Zaman damgalarına DOKUNMAZ; yalnız iki cue arasındaki bölme "
            "noktası kayar ve birleşik metin aynı kalır. Ölçüt dardır: "
            "alıcı cue kendi hız ve genişlik sınırları içinde kalmalı, "
            "kaynak cue anlamlı ölçüde rahatlamalı, cümle kaynağa göre "
            "gerçekten devam ediyor olmalı.\n\n"
            "Yine de gerekçesi uzunluktur; uzunluk tek başına bir cue'ya "
            "dokunmak için yeterli sayılmıyorsa kapalı tutun."),
        varsayilan=True,
        ne_zaman="Okuma hızı sizin için ölçütse açık; satır yapısı kaynağa "
                 "uysun diyorsanız kapalı.",
        iliskili=("linebreak_var", "condense_var"),
    ),
    "clean_sdh_var": Madde(
        baslik="SDH Temizle",
        bolum="Metin Biçimi",
        kisa="İşitme engelli etiketlerini (ses, müzik, konuşmacı adı) siler.",
        uzun=(
            "`[kapı çarpar]`, `(müzik)`, `ADAM:` gibi işitme engelliler için "
            "eklenmiş etiketler teslimden çıkarılır. Yalnız etiketten ibaret "
            "olan cue'lar tamamen düşer.\n\n"
            "Etiket kaynakta İngilizce kalmış da olsa, modelden Türkçe "
            "dönmüş de olsa yakalanır."),
        varsayilan=True,
        ne_zaman="İşitme engelli altyazısı üretmiyorsanız açık tutun.",
        iliskili=(),
    ),

    # ── Terim ve Tutarlılık ─────────────────────────────────────────────
    "term_normalize_var": Madde(
        baslik="Terim Normalizasyonu",
        bolum="Terim ve Tutarlılık",
        kisa="Aynı terimin dosya içinde farklı yazılmış hâllerini bulur.",
        uzun=(
            "Bir özel ad ya da terim aynı dosyada iki biçimde geçiyorsa "
            "(`Göbekli` / `Gobekli`, `Truva` / `Troy`) tespit edilir. "
            "Çoğunluk biçimi değil, hangisinin sızıntı olduğu değerlendirilir "
            "— ham sıklığa güvenilmez."),
        varsayilan=True,
        ne_zaman="Açık tutun; tespit tek başına metne dokunmaz.",
        iliskili=("term_normalize_apply_var", "auto_glossary_var"),
    ),
    "term_normalize_apply_var": Madde(
        baslik="Terim Düzeltmelerini Uygula",
        bolum="Terim ve Tutarlılık",
        kisa="Bulunan terim tutarsızlıklarını yalnız raporlamakla kalmaz, "
             "düzeltir.",
        uzun=(
            "Terim Normalizasyonu'nun bulduğu farklı yazımlar tek biçime "
            "getirilir. Metni DEĞİŞTİREN bir adımdır.\n\n"
            "Terim Normalizasyonu kapalıysa bunun etkisi yoktur."),
        varsayilan=True,
        ne_zaman="Tespitin doğruluğuna güvendiğinizde açık; her değişikliği "
                 "kendiniz görmek istiyorsanız kapalı.",
        iliskili=("term_normalize_var",),
    ),
    "auto_glossary_var": Madde(
        baslik="Auto-Glossary (Otomatik Sözlük)",
        bolum="Terim ve Tutarlılık",
        kisa="Çeviriden sözlüğe eklenebilecek terimleri otomatik önerir.",
        uzun=(
            "Yardımcı model dosyada tekrar eden özel ad ve terimleri "
            "çıkarır ve sözlüğe aday olarak sunar. Sözlüğe giren terim "
            "sonraki parçaların ve sonraki bölümlerin isteminde sabit "
            "karşılığıyla görünür.\n\n"
            "Sözlük üç ayrı şekilde bozulabilir (toplu dil çökmesi, çok kısa "
            "gloss, 'nasıl çevrilmeli' notunun terim sanılması); üçüne karşı "
            "da ayrı koruma vardır."),
        varsayilan=False,
        ne_zaman="Terim yoğun işlerde (belgesel, tarih, bilim) açın.",
        iliskili=("term_normalize_var", "series_memory_var"),
        maliyet="Dosya başına yardımcı model çağrısı.",
    ),
    "series_memory_var": Madde(
        baslik="Dizi Hafızası",
        bolum="Terim ve Tutarlılık",
        kisa="Aynı dizinin önceki bölümlerinden karakter, terim ve hitap "
             "kararlarını taşır.",
        uzun=(
            "Bir bölümde verilmiş kararlar (karakterin adı nasıl yazılıyor, "
            "kim kime 'siz' diyor, terimin karşılığı ne) sonraki bölümlerin "
            "istemine eklenir. Bölümün hangi diziye ait olduğu klasör "
            "adından anlaşılır.\n\n"
            "Aynı sezonun bölümlerini sırayla çevirdiğinizde en çok işe "
            "yarar."),
        varsayilan=True,
        ne_zaman="Dizi çeviriyorsanız açık tutun. Tek dosyalık işlerde "
                 "etkisi yoktur.",
        iliskili=("season_canon_var", "chain_ctx_var"),
    ),
    "season_canon_var": Madde(
        baslik="Sezon Sonu Kanon Denetimi",
        bolum="Terim ve Tutarlılık",
        kisa="Seçilen sezonun bütün bölümleri bitince, sezon genelinde "
             "tutarlılık denetimi yapar.",
        uzun=(
            "Sezonun tamamı başarıyla çevrildiğinde, bölümler arası terim "
            "ve hitap ayrışmaları aranır. Tek bölüme bakarak görülemeyen "
            "sınıf budur: bölüm 3'te 'siz', bölüm 7'de 'sen'.\n\n"
            "Sezonun tamamı seçili değilse ya da bölümlerden biri "
            "başarısızsa denetim atlanır ve raporda sebebi yazılır."),
        varsayilan=False,
        ne_zaman="Bir sezonun tamamını tek seferde çevirirken açın.",
        iliskili=("series_memory_var",),
        maliyet="Sezon başına bir denetim geçişi.",
    ),

    # ── Teslim ve Güvenlik ──────────────────────────────────────────────
    "quality_report_only_var": Madde(
        baslik="Teslim + Otomatik Düzeltme: Yalnız Raporla",
        bolum="Teslim ve Güvenlik",
        kisa="Otomatik düzeltmeler teslim metnini DEĞİŞTİRMEZ, yalnız "
             "raporlanır.",
        uzun=(
            "Açıkken teslim taraması ve otomatik düzelticiler çalışır, "
            "buldukları kalite raporuna ve bulgu kaydına yazılır, ama "
            "dosyaya dokunulmaz. Log'da 'teslim metni değiştirilmedi' "
            "satırını görürsünüz.\n\n"
            "Çeviriyi kendiniz ya da bir model üzerinden geçireceksiniz "
            "açık tutun: hem düzeltmeyi siz yaparsınız hem de programın "
            "neyi şüpheli bulduğunu görürsünüz."),
        varsayilan=True,
        ne_zaman="Üzerinden geçilecek işlerde açık. Programın çıktısını "
                 "olduğu gibi yayınlayacaksanız kapatın.",
        iliskili=("critic_var", "deep_delivery_semantic_var",
                  "term_normalize_apply_var"),
    ),
    "backup_raw_var": Madde(
        baslik="Ham Çeviri Yedeği (.ham.srt)",
        bolum="Teslim ve Güvenlik",
        kisa="Kalite geçişlerinden ÖNCEKİ çeviriyi ayrı bir dosyaya yedekler.",
        uzun=(
            "Critic, Polish, Native, kısaltma gibi geçişler çeviriyi "
            "değiştirebilir. Bu yedek onlardan etkilenmez; bir geçiş bir "
            "satırı bozduysa doğrusu burada durur.\n\n"
            "Ham ile teslim arasındaki içerik farkı ayrıca denetlenir: "
            "yedekte olup teslimde olmayan diyalog, gerçek bir kayıptır."),
        varsayilan=True,
        ne_zaman="Açık bırakın. Tek maliyeti disk alanıdır.",
        iliskili=("quality_report_only_var",),
    ),
    "repair_missing_var": Madde(
        baslik="Eksik Cue API Onarımı",
        bolum="Teslim ve Güvenlik",
        kisa="Çeviri sonunda eksik kalan cue'ları model çağrısıyla yeniden "
             "çevirir.",
        uzun=(
            "Bir parça hata verdiğinde ya da model bazı cue'ları atladığında, "
            "geride `[ÇEVİRİ EKSİK]` işaretli satırlar kalır. Bu seçenek "
            "açıkken o satırlar için hedefli yeni çağrılar yapılır.\n\n"
            "Kapalıyken satır işaretli kalır ve raporda görünür — böylece "
            "eksiği siz görüp karar verirsiniz."),
        varsayilan=False,
        ne_zaman="Elle müdahale etmek istemiyorsanız açın.",
        iliskili=("auto_retry_files_var",),
        maliyet="Eksik cue başına ek çağrı.",
    ),

    # ── Çalışma ve Kurtarma ─────────────────────────────────────────────
    "auto_resume_crash_var": Madde(
        baslik="Çökme Sonrası Otomatik Devam",
        bolum="Çalışma ve Kurtarma",
        kisa="Program beklenmedik şekilde kapanırsa, açılışta kaldığı yerden "
             "devam etmeyi önerir.",
        uzun=(
            "Çeviri sırasında durum diske yazılır. Program kapanır ya da "
            "bilgisayar kapanırsa, bir sonraki açılışta tamamlanmamış "
            "dosyalar sıraya alınır ve baştan çevrilmez.\n\n"
            "Toplu (batch) işler için ayrıca `batch_id` kaydı tutulur; "
            "ödenmiş bir toplu iş kaybolmaz."),
        varsayilan=True,
        ne_zaman="Açık bırakın.",
        iliskili=("auto_retry_files_var",),
    ),
    "auto_retry_files_var": Madde(
        baslik="Başarısız Dosyaları Otomatik Yeniden Dene",
        bolum="Çalışma ve Kurtarma",
        kisa="Hata alan dosyayı, sıranın sonunu beklemeden hemen yeniden "
             "dener.",
        uzun=(
            "Ağ hatası, geçici sağlayıcı arızası ya da tek seferlik bir "
            "model hatası yüzünden düşen dosyalar otomatik tekrarlanır. "
            "Deneme sayısı sınırlıdır; kalıcı bir hata sonsuz döngüye "
            "girmez."),
        varsayilan=True,
        ne_zaman="Açık bırakın.",
        iliskili=("auto_resume_crash_var", "helper_shuai_failover_var"),
    ),
    "helper_shuai_failover_var": Madde(
        baslik="Yardımcı Model Rota Yedeklemesi",
        bolum="Çalışma ve Kurtarma",
        kisa="Üçüncü taraf sağlayıcıda bir rota düşerse diğerine geçer.",
        uzun=(
            "Bazı sağlayıcılar aynı modeli birden çok adresten sunar ve "
            "bunlardan biri geçici olarak düşebilir. Açıkken her deneme "
            "için rota yeniden seçilir; bir adres arızalıysa istek diğerine "
            "gider.\n\n"
            "Sağlayıcıdan gelen 404 iki ayrı şey demek olabilir: model o "
            "grupta yok, ya da kanal geçici düştü. Teşhis için hata "
            "gövdesine bakılır."),
        varsayilan=True,
        ne_zaman="Üçüncü taraf sağlayıcı kullanıyorsanız açık bırakın.",
        iliskili=("main_custom_var",),
    ),
    "chunk_gunlugu": Madde(
        baslik="Chunk Adli Günlüğü",
        bolum="Çalışma ve Kurtarma",
        kisa="Her çeviri isteğini kaydeder: hangi cue hangi parçada gitti, o istekte ne vardı, model ne döndü.",
        uzun=(
            "Teslimde bozuk bir satır bulduğunuzda rapor size cue'yu gösterir, ama o cue'nun hangi istekte gittiğini ve o istekte hangi bağlamın bulunduğunu göstermez. Günlük bu boşluğu kapatır.\n\n"
            "Koşu başına tek dosya yazılır ve şunları taşır: parçadaki cue numaraları ve zaman damgaları, gönderilen yükün tamamı, hangi bağlam anahtarlarının gerçekten konduğu (ctx, prev_tr, sözlük), model, adres, token sayısı, yanıtın kesilip kesilmediği ve ham yanıt.\n\n"
            "Günlükte PARA YOKTUR. Ana rota dinamik faturalandığı için yerelde hesaplanacak bir tutar yanlış olur ve — daha kötüsü — doğru sanılır. Token ölçülen bir büyüklüktür, o kaydedilir.\n\n"
            "Sorgulama ve tek parçayı yeniden gönderme komut satırından yapılır:\n"
            "    python chunk_sorgu.py kosular\n"
            "    python chunk_sorgu.py bul 1874\n"
            "    python chunk_sorgu.py goster dosya.srt__3\n"
            "    python chunk_sorgu.py replay dosya.srt__3\n\n"
            "`replay` hiçbir dosyaya dokunmaz: eski ve yeni çeviriyi yan yana basar, kararı siz verirsiniz. Karşılaştırma cue numarasıyla değil ZAMAN DAMGASIYLA yapılır — bir cue silindiğinde numaralar kayar ve sonraki her satır sahte olarak değişmiş görünür."),
        ne_zaman="Bir teslimde açıklayamadığınız bir bozukluk gördüğünüzde. Günlük kendiliğinden tutulur, açıp kapatmanız gerekmez.",
        iliskili=("kaynak_on_kontrol", "chain_ctx_var"),
        maliyet="Yalnız disk: dosya başına ~300 KB. En yeni 20 koşu ve en çok 100 MB tutulur, eskiler silinir.",
        arayuz_kutusu=False,
    ),
    "kaynak_on_kontrol": Madde(
        baslik="Kaynak Ön Kontrolü",
        bolum="Çalışma ve Kurtarma",
        kisa="Çeviri başlamadan kaynağı ölçer ve dosyanın tamamını götürecek iki kusuru bildirir.",
        uzun=(
            "Kaynak dosya yüklenirken iki ölçüm yapılır ve sonuç kayıt penceresine yazılır. Program DURMAZ; karar sizindir. İşi, para harcanmadan önce söylemektir.\n\n"
            "CÜMLE SONU NOKTALAMASI — kaynakta cue'ların %30'undan azı noktalamayla bitiyorsa uyarır. Böyle bir kaynakta model satır satır çevirme eğilimine girer ve çıktının önemli bir kısmı İngilizce söz diziminde kalır. Bu kusur yamayla düzelmez, yeniden çeviri ister — yani dosyanın parası iki kez ödenir. 386 gerçek kaynakta ortanca %70, eşiğin altında kalan 47 dosya (%12) çıktı; on iki dosya hiç cümle bitirmiyordu (kayan altyazılı belgeseller).\n\n"
            "KODLAMA — kaynak yanlış kodlamayla okunmuşsa çeviri baştan sona yanlış olur. 386 dosyada bir vaka bulundu. Kural iki karakterlik imzalar arar; tek harfe bakan bir kural İsveççe `Åke` gibi meşru sözcükleri yanlış işaretlerdi."),
        ne_zaman="Kendiliğinden çalışır. Uyarı görürseniz çeviriye başlamadan önce kaynağı düzeltmek neredeyse her zaman daha ucuzdur.",
        iliskili=("chunk_gunlugu",),
        arayuz_kutusu=False,
    ),
    "prevent_sleep_var": Madde(
        baslik="Çalışırken Uyku Modunu Engelle",
        bolum="Çalışma ve Kurtarma",
        kisa="Çeviri sürerken bilgisayarın uykuya geçmesini engeller.",
        uzun=(
            "Uzun çeviriler saatler sürebilir. Bilgisayar uykuya geçerse "
            "ağ istekleri kesilir ve dosyalar hata alır. Bu seçenek çeviri "
            "sürdüğü sürece sistemin uyanık kalmasını ister; iş bitince "
            "kısıtlama kalkar."),
        varsayilan=True,
        ne_zaman="Açık bırakın.",
        iliskili=("shutdown_when_done_var",),
    ),
    "shutdown_when_done_var": Madde(
        baslik="Bitince Bilgisayarı Kapat",
        bolum="Çalışma ve Kurtarma",
        kisa="Bütün dosyalar bitince bilgisayarı kapatır.",
        uzun=(
            "Gece boyunca çeviri bırakıp sabah bitmiş bulmak için. Kapatma "
            "öncesi bir uyarı penceresi çıkar ve iptal etme şansı verir.\n\n"
            "Rapor ve yedekler kapatmadan ÖNCE yazılır."),
        varsayilan=False,
        ne_zaman="Uzun bir kuyruğu gözetimsiz bırakırken.",
        iliskili=("prevent_sleep_var", "notify_var"),
    ),
    "notify_var": Madde(
        baslik="Masaüstü Bildirimi",
        bolum="Çalışma ve Kurtarma",
        kisa="İş bitince ya da hata olunca masaüstü bildirimi gösterir.",
        uzun=(
            "Program arka planda çalışırken bitişi ve önemli hataları "
            "haber verir."),
        varsayilan=True,
        ne_zaman="Bilgisayarın başında beklemiyorsanız.",
        iliskili=("shutdown_when_done_var",),
    ),
    "same_folder_var": Madde(
        baslik="Aynı Klasöre Kaydet",
        bolum="Çalışma ve Kurtarma",
        kisa="Çeviriyi ayrı bir çıktı klasörü yerine kaynağın yanına yazar.",
        uzun=(
            "Açıkken her çeviri kendi kaynak dosyasının bulunduğu klasöre "
            "yazılır. Film klasörlerini tek tek düzenliyorsanız pratiktir.\n\n"
            "Kapalıyken hepsi seçtiğiniz tek çıktı klasörüne gider."),
        varsayilan=False,
        ne_zaman="Her filmin kendi klasörü varsa açın.",
        iliskili=(),
    ),
    "light_animations_var": Madde(
        baslik="Canlı İlerleme Animasyonları",
        bolum="Çalışma ve Kurtarma",
        kisa="Arayüzdeki hareketli ilerleme göstergelerini açar/kapatır.",
        uzun=(
            "Yalnız görünümü etkiler; çeviriye ya da çıktıya hiçbir etkisi "
            "yoktur. Zayıf makinelerde kapatmak arayüzü hafifletir."),
        varsayilan=True,
        ne_zaman="Arayüz takılıyorsa kapatın.",
        iliskili=(),
    ),
}


def bolume_gore() -> dict:
    """Bölüm adı -> [(var_adi, Madde)] — kılavuz penceresinin ağacı."""
    gruplar: dict[str, list] = {bolum: [] for bolum in BOLUMLER}
    for ad, madde in MADDELER.items():
        gruplar.setdefault(madde.bolum, []).append((ad, madde))
    for liste in gruplar.values():
        liste.sort(key=lambda ikili: ikili[1].baslik.casefold())
    return gruplar


def ara(sorgu: str) -> list:
    """Basit arama: başlık, kısa ve uzun metinde geçen maddeler."""
    aranan = str(sorgu or "").strip().casefold()
    if not aranan:
        return []
    bulunan = []
    for ad, madde in MADDELER.items():
        havuz = " ".join((
            madde.baslik, madde.kisa, madde.uzun, madde.ne_zaman, ad))
        if aranan in havuz.casefold():
            bulunan.append((ad, madde))
    bulunan.sort(key=lambda ikili: (
        aranan not in ikili[1].baslik.casefold(),
        ikili[1].baslik.casefold()))
    return bulunan


def icerik_turu_maddeleri(schemas: dict) -> list:
    """İçerik türü sayfaları — `CONTENT_SCHEMAS`'tan ÜRETİLİR, elle yazılmaz."""
    uretilen = []
    for ad in sorted(schemas or (), key=str.casefold):
        sema = schemas.get(ad) or {}
        kurallar = []
        for anahtar in ("rules", "kurallar", "notes"):
            deger = sema.get(anahtar)
            if isinstance(deger, (list, tuple)):
                kurallar.extend(str(k) for k in deger)
            elif isinstance(deger, str):
                kurallar.append(deger)
        uretilen.append((ad, tuple(kurallar)))
    return uretilen


def bulgu_sinifi_maddeleri(siniflar: dict) -> list:
    """Rapor sözlüğü — `_FINDING_CLASSES`'tan ÜRETİLİR.

    Yeni bir bulgu sınıfı eklendiğinde kılavuzda kendiliğinden görünür.
    """
    uretilen = []
    for anahtar in sorted(siniflar or ()):
        meta = siniflar.get(anahtar) or ()
        if len(meta) < 3:
            continue
        guven, etiket, oneri = meta[0], meta[1], meta[2]
        uretilen.append((anahtar, str(guven), str(etiket), str(oneri)))
    return uretilen


def kutulu_maddeler() -> dict:
    """Arayuzde kutusu olan maddeler."""
    return {a: m for a, m in MADDELER.items() if m.arayuz_kutusu}


def kutusuz_maddeler() -> dict:
    """Kutusu olmayan, hep acik davranislar."""
    return {a: m for a, m in MADDELER.items() if not m.arayuz_kutusu}


GUVEN_ACIKLAMASI = {
    "kesin": "Neredeyse her zaman gerçek bir hata; teslimi durdurur.",
    "muhtemel": "Çoğu zaman gerçek, ama bakmadan düzeltmeyin.",
    "bilgi": "Kayıt amaçlı; düzeltme gerekçesi olmayabilir.",
}
