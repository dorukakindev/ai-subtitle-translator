# Altyazı Çevirisi

*[English README](README.en.md)*

Altyazı dosyalarını (`.srt`, `.vtt`, `.ass`/`.ssa`) OpenAI API'siyle Türkçeye —
ya da 60 dilden birine — çeviren bir Windows masaüstü uygulaması.

Piyasadaki çoğu araç altyazıyı satır satır çevirir. Bu programın tamamı tek bir
soruna göre kurulmuştur: **bir altyazı satırı tek başına anlamlı değildir.**
"Get him." satırının Türkçesi, onu kimin kime söylediğine, iki satır önce ne
konuşulduğuna ve o kişiye dosyanın başından beri "sen" mi "siz" mi dendiğine
bağlıdır. Program modele bunların hepsini gösterir.

<!-- Buraya bir ekran görüntüsü koyun: docs/ekran-goruntusu.png -->

---

## Ne yapar

**Bağlamla çevirir.** Model her parçayı çevirirken şunları da görür: önceki
satırlar, sonraki satırlar (ileri okuma), sahne kesiminden önceki köprü, ve
**önceki satırların nasıl çevrildiği**. Sonuncusu en önemlisi — parça sınırında
karakterin adı ya da hitap biçimi değişmez.

**Dosyayı önce okur.** İsteğe bağlı bir ön geçiş altyazının tamamını analiz
eder: karakterler kim, kim kime "sen" der, hangi terimler tekrarlıyor,
sahnelerin duygusu ne. Bu analiz sonra her çeviri isteminin içine girer.

**Türü bilir.** 74 içerik türü şeması var (belgesel, anime, FRP, komedi,
tarih…). Her birinin kendi çeviri kuralları vardır: bir belgeselde anlatıcı
üslubu, bir animede hitap ekleri, bir savaş filminde askerî terminoloji.
"Otomatik" seçeneği türü kendisi tespit eder.

**Diziyi hatırlar.** Bir bölümde verilen kararlar — karakterin yazımı, terimin
karşılığı, kimin kime nasıl hitap ettiği — sonraki bölümlere taşınır. Sezon
bitince isteğe bağlı bir kanon denetimi bölümler arası ayrışmaları arar.

**Çevirdiğini denetler.** Teslim edilecek dosya kaynakla karşılaştırılır ve
**39 ayrı bulgu sınıfı** aranır: eksik diyalog, çevrilmemiş parça, bozulmuş
sözcük, metne sızmış cue numarası, kalıntı SDH etiketi, yabancı yazı sistemi,
komşu cue'da yankı, kaynakta olmayan çevirmen açıklaması… Her bulgu bir cue
numarası ve zaman damgasıyla adreslenir; raporda "şu satıra bak" yazar.

**Ne yaptığını söyler.** Her koşu bir kalite raporu ve bulgu kaydı üretir.
Hangi geçişin çalıştığı, neyi değiştirdiği, neyi neden atladığı yazılıdır.

**Bozmamaya çalışır.** Kalite geçişleri metni değiştirebildiği için, geçiş
öncesi hâl ayrı bir dosyaya yedeklenir ve ham ile teslim arasındaki içerik
farkı ayrıca denetlenir. "Yalnız Raporla" kipinde hiçbir otomatik düzeltici
teslim metnine dokunmaz — bulgular yazılır, kararı siz verirsiniz.

---

## Kurulum

Gerekenler: **Windows** ve **Python 3.11+** (3.14 ile geliştirildi).

```bash
pip install -r requirements.txt
```

Çalıştırma:

```bash
python subtitle_translator_gui.py
```

ya da `Başlat.bat` dosyasına çift tıklayın.

### Dosya kuyruğu

Üstteki **Dosya ekle** mevcut kuyruğu koruyarak dosya ekler. Sol paneldeki
**Dosyaları Seç** seçimi değiştirir. Aynı dosya tekrar seçilirse kuyruğa
ikinci kez eklenmez. Dosya satırındaki **X** yalnızca o dosyayı kuyruktan
çıkarır; **Temizle** kuyruğu ve giriş klasörü seçimini boşaltır. Bu işlemler
kaynak dosyaları diskten silmez. Çeviri veya klasör taraması sürerken seçim
temizlenemez ve dosya listesinden öğe kaldırılamaz.

### API anahtarı

Program ilk açılışta anahtar ister. Anahtarlar **ayar dosyasına yazılmaz**;
Windows Kimlik Bilgisi Yöneticisi'nde (`keyring`) saklanır. Kimlik deposuna
erişilemezse şifrelenmiş bir yedek dosya kullanılır.

### Sağlayıcı seçimi

OpenAI zorunlu değil. **API Anahtarları → Yeni Profil** penceresindeki *Hazır
sağlayıcı* listesinden seçtiğinizde adres kendiliğinden dolar:

**Google AI Studio** (Gemini Flash, Gemma) · **OpenRouter** (tek anahtarla
yüzlerce model, `:free` sürümler dahil) · **Groq** · **DeepSeek** · **Mistral**
· **xAI** · **Together** · **Cerebras** · **Fireworks** · **Nebius** ·
**Anthropic** · ya da **Ollama / LM Studio** ile modeli kendi bilgisayarınızda
çalıştırın (ücretsiz, internet gerekmez, veri dışarı çıkmaz).

Model adı koda gömülü değildir: **Modelleri getir** düğmesi sağlayıcının kendi
listesini çeker, süzüp seçersiniz. Sağlayıcılar model çıkarıp kaldırdığı için
gömülü bir liste birkaç ay sonra yanlış olurdu.

Her profil ayrı bir **role** atanabilir — ana çeviri, yedek anahtar, yardımcı
analiz, Critic, Polish, QC. Yani çeviriyi Gemini Flash'a, denetimi GPT'ye
verebilirsiniz.

Yalnız bir uyarı: **Toplu (Batch) mod yalnız resmi OpenAI'de çalışır**; gerçek
Batch API'sini başka sağlayıcı sunmuyor.

Anahtarlar hangi sağlayıcıya ait olursa olsun ayar dosyasına yazılmaz.

---

## Kullanım

1. **Dosya seç** — tek dosya, klasör ya da sürükle-bırak. Video dosyasından
   gömülü altyazı akışı da çıkarılabilir.
2. **Dil ve tür** — kaynak dil otomatik tespit edilir (dosya adındaki dil
   etiketine güvenilmez, metne bakılır). İçerik türünü seçin ya da "Otomatik"
   bırakın.
3. **Maliyet tahmini** — çevirmeden önce yaklaşık tutarı gösterir, model
   karşılaştırmasıyla birlikte.
4. **Çevir** — ilerleme, hangi dosyanın hangi aşamada olduğu ve canlı log
   görünür.
5. **Raporu okuyun** — `Raporlar/` altında kalite raporu, bulgu kaydı ve karar
   izi.

### Üç çeviri kipi

| kip | ne zaman | not |
|---|---|---|
| **Eşzamanlı** | Normal kullanım | En iyi tutarlılık; zincirleme bağlam tam çalışır |
| **Toplu (Batch)** | Çok dosya, acele yok | %50 daha ucuz, saatler sürebilir |
| **Yardımcı Analiz** | Kalite öncelikli | Ön analiz + kalite geçişleri |

Toplu iş yarıda kalırsa kaybolmaz: `batch_id` kaydı tutulur ve program açılışta
devam etmeyi önerir. Program çökerse ya da bilgisayar kapanırsa da tamamlanmamış
dosyalar sıraya alınır, baştan çevrilmez.

---

## Ayarlar

Programın içinde **Yardım** penceresi her ayarı ne yaptığı, varsayılanı ve ne
zaman açılması gerektiğiyle birlikte anlatır; kutuların üstüne gelince de kısa
bir açıklama çıkar.

Tam ayar başvurusu: [KILAVUZ.md](KILAVUZ.md) — bu dosya `kilavuz.py`'den
üretilir, elle düzenlenmez.

Bilmeniz gereken üç tanesi:

- **Yalnız Raporla** (varsayılan açık) — otomatik düzelticiler teslim metnini
  değiştirmez, yalnız raporlar. Çeviriyi üzerinden geçireceksiniz açık tutun.
- **Zincirleme Bağlam** (varsayılan açık) — tutarlılığın en güçlü tek aracı.
- **Ham Çeviri Yedeği** (varsayılan açık) — kalite geçişleri öncesi hâl. Bir
  geçiş bir satırı bozarsa doğrusu burada durur.

---

## Mimari

```
subtitle_translator_gui.py   arayüz, üç çeviri akışı, teslim taraması
hybrid_translate.py          analiz destekli akış, yardımcı model çağrıları
subtitle_formats.py          okuma/yazma (utf-8-sig → cp1254 → latin-1)
sdh_cleaner.py               işitme engelli etiketi temizliği
translation_memory.py        çeviri belleği (SQLite, tam + bulanık eşleşme)
series_memory.py             diziler arası karar taşıma
credential_store.py          anahtar saklama (Windows Kimlik Bilgisi Yöneticisi)
helper_models.py             yardımcı model çözümlemesi
provider_retry.py            yeniden deneme, rota yedekleme
kilavuz.py                   kullanım kılavuzunun tek veri kaynağı
```

Kodlama notu: bütün altyazı okumaları `subtitle_formats.read_subtitle_text`
üzerinden gider (utf-8-sig → cp1254 → latin-1). Windows-1254 Türkçe dosyalar
doğrudan `utf-8` ile açılırsa çöker.

---

## Testler

376 test modülü, ~4800 test. Ağ erişimi gerektirmez.

```bash
python -m unittest discover -s tests
```

Testlerin çoğu saf fonksiyonları sınar; arayüz kurmadan çalışırlar. Bu bilinçli
bir tercih: mantık, arayüzden ayrı ve test edilebilir tutulur.

Bazı testler tespit kurallarının **yanlış pozitif oranını** kilitler. Bu
projede bir tespit kuralı, gerçek teslim dosyalarına karşı hem isabet hem
yanlış alarm yönünden ölçülmeden eklenmez.

---

## Katkı

Bu program tek bir kullanım için — altyazı çevirip yayınlamak — yazıldı ve
kararların çoğu ölçüme dayanıyor. Katkı vermeden önce
[CONTRIBUTING.md](CONTRIBUTING.md) dosyasını okuyun; özellikle yeni bir tespit
kuralı ekliyorsanız ölçüm beklentisi orada anlatılıyor.

---

## Lisans

GNU General Public License v3.0 — bkz. [LICENSE](LICENSE).

Programı kullanabilir, değiştirebilir ve ticari olarak da dağıtabilirsiniz;
tek şart, bu programdan türetip DAĞITTIĞINIZ her şeyin de aynı lisansla
özgür yazılım olması ve kaynağının erişilebilir kalmasıdır.

---

## Bilinmesi gerekenler

### Deneme, geçiş incelemesi ve onaylı tercihler

Kenar çubuğundaki **Araçlar** bölümünde üç yeni araç bulunur:

- **Deneme çevirisi:** Kaynağın başından, ortasından ve sonundan örnekler seçer.
  Örnek başına 6, 12, 20 veya 40 satır seçilebilir; kısa dosyalarda satırlar
  tekrarlanmaz. **Deneme penceresini hazırla** ayrı bir uygulama penceresi açar;
  bu penceredeki **Başlat** çeviriyi başlatır. Model ve kalite ayarları ana
  pencereden alınır. Çıktılar, kuyruk ve çalışma hafızası
  `Raporlar/Deneme/<tarih-saat>/` altında ayrıdır. API anahtarları deneme ayar
  dosyasına yazılmaz. Yalnız örnekler analiz edilir; bu işlem bütün dosyanın
  bağlam analizinin yerini tutmaz. Batch modu seçiliyse normal Batch bekleme
  süresi geçerlidir.
- **Geçişleri incele:** Yeni çevirilerde rapor klasörünün `Inceleme/` altına
  yazılan `*.review.json` kaydını açar. Kaynak, ilk kayıtlı çeviri, metni
  değiştiren kalite geçişleri ve son çıktı görülebilir. Satır veya sahne ilk
  kayıtlı sürüme alınabilir; bir geçişin sonucu seçilebilir veya metin elle
  düzenlenebilir. Kaydetmek zaman damgalarını değiştirmez ve önceki dosyanın
  birebir yedeğini oluşturur. Başka bir işlemde değişmiş çıktıya yazılmaz.
  Zaman eşlemesi belirsiz satırlarda otomatik geri alma kapalıdır. Eski
  raporlarda bulunmayan geçiş geçmişi sonradan üretilmez. Elle düzenlenen
  çıktı önceki kalite raporuyla doğrulanmış sayılmaz.
- **Onaylı tercihler:** Terim, karakter adı veya hitap tercihini açıkça
  onaylayarak **Bölüm** ya da **Dizi** kapsamında kaydeder. Hitap için kaynak
  alanına `konuşan → muhatap`, karşılık alanına `sen` veya `siz` yazılır.
  Bölüm tercihi dizi tercihinden, onaylı tercihler otomatik hafızadan
  önceliklidir. Tercihler kaynak/hedef dil çiftine göre ayrılır ve sonraki
  çevirilerde kullanılır; mevcut çıktıyı kendiliğinden değiştirmez. Dizi
  kapsamı için dosya adından dizi ve bölümün tanınabilmesi gerekir. Aynı
  tercihi yeniden kaydetmek önceki onayı günceller.

- Arayüz, log ve raporlar **Türkçedir**. Kod tanımlayıcıları İngilizce.
- Çeviri kalitesi seçtiğiniz modele bağlıdır. Ucuz modeller uzun dosyalarda
  terim kayması ve senkron bozulması üretebilir; program bunların çoğunu
  yakalar ama hepsini düzeltemez.
- Program bir **çeviri asistanıdır**, çevirmen değil. Yayınlanacak işlerde
  çıktının üzerinden geçilmesi beklenir; raporlar tam olarak bunun için var.
