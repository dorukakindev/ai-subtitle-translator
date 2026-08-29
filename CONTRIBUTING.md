# Katkı

Bu program tek bir iş için yazıldı: altyazı çevirip yayınlamak. Kararların
çoğu tahminle değil **ölçümle** verildi ve depo o alışkanlığı korumaya
çalışıyor. Katkı vermeden önce buradaki üç kuralı okuyun; kodun kendisinden
daha önemliler.

## 1. Tespit kuralı ölçülmeden eklenmez

Yeni bir "şunu yakalayan kural" öneriyorsanız, onu **gerçek altyazı
dosyalarına karşı** koşun ve iki sayıyı birden verin:

- kaç gerçek bulgu buldu (isabet)
- kaç yanlış alarm üretti (yanlış pozitif)

Tek yönlü ölçüm yeterli değildir. Bu depoda, yanlış alarmı düşürdüğü için
kabul edilecek gibi görünen bir kural ölçüldüğünde **bilinen gerçek bir
bulguyu kaçırdığı** ortaya çıktı. Aynı koşuda ikisine birden bakın.

Ölçülüp **elenmiş** kurallar da kayıtlıdır (kod yorumlarında ve
`plans/` altında). Bir fikri yeniden önermeden önce daha önce denenip
denenmediğine bakın — birkaçı iki kez denendi.

Güven derecesi (`kesin` / `muhtemel` / `bilgi`) de ölçümle seçilir. Kesinliği
%30 olan bir kuralı `kesin` yapmak teslim kapısını boşuna kapatır.

## 2. Otomatik düzeltici yazıyorsanız

Metni **değiştiren** her kod için:

- Beyaz liste düşünün. Bu depoda yazılmış bir otomatik düzeltici, meşru
  sözcükleri (`dövme`, `gövde`) bozdu ve teslime girdi.
- Bir **değişmez** doğrulayın. Örneğin satır sayısı: bir düzeltici `--\s+`
  deseni kullandı, `\s` satır sonunu da yedi ve dokunduğu 43 cue'nun 4'ünde
  iki repliği tek satıra düşürdü. Testler artık satır sayısının değişmediğini
  ayrıca doğruluyor.
- Değişiklikleri **gözle okuyun**. Sayı yeterli değil.

## 3. Aynı karar iki yerde hesaplanmasın

Bu depodaki tekrar eden bug sınıfı budur: aynı karar iki ayrı yerde
hesaplanır, kopyalar zamanla ayrışır ve biri sessizce zayıf kalır.

Bir geçişi iki ayrı ayar açabiliyorsa ikisi de aynı listede olmalı. Bir kaynak
eşlemesi yapıyorsanız anahtar **her yerde** zaman damgası olmalı, cue numarası
yalnızca yedek — numara teslimde kayar ve boş dönmez, **başka bir cue'yu**
bulur.

Test, adı değil **şekli** kilitlesin: "şu geçişin kapısındaki bütün
değişkenler şu listede mi" diye sorun; böylece sonradan eklenen üçüncü bir
değişken aynı şekilde sızamaz.

---

## Geliştirme

```bash
pip install -r requirements.txt
python subtitle_translator_gui.py
```

Testler (ağ gerektirmez):

```bash
python -m unittest discover -s tests
```

Tek modül:

```bash
python -m unittest tests.test_kilavuz
```

Derleme kontrolü (linter yapılandırılmamıştır):

```bash
python -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py
```

Arayüzde değişiklik yaptıysanız başsız duman testi:

```bash
python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"
```

> **Dikkat:** testler canlı uygulamayla proje kökünü paylaşır (`batch_id.txt`,
> `logs/`). Bir çeviri koşarken `App()` kuran test **çalıştırmayın** — bir kez
> canlı bir toplu işe karşı modal pencere açtı ve koşu logunu rotasyonla sildi.

## Kılavuz

Bir ayar eklerseniz `kilavuz.py`'ye maddesini de ekleyin. `tests/test_kilavuz.py`
her kutunun belgelendiğini ve kılavuzdaki "varsayılan" iddiasının koddaki
gerçek varsayılana eşit olduğunu doğrular — eklemezseniz test kırılır.

`KILAVUZ.md` elle düzenlenmez:

```bash
python belge_uret.py            # yeniden üret
python belge_uret.py --kontrol  # güncel mi (0/1 döner)
```

## Üslup

- Arayüz metinleri, log ve raporlar **Türkçe**; kod tanımlayıcıları İngilizce.
- Mantığı saf fonksiyon olarak yazın, `App` metodu ince kalsın — testler
  arayüz kurmadan koşabilsin.
- Bir davranışı **neden** öyle yaptığınızı yoruma yazın, özellikle ölçtüyseniz.
  Bu depodaki yorumların çoğu "şu ölçüldü, sonuç şuydu" der; bir sonraki kişi
  aynı yolu ikinci kez denemesin.
- Altyazı okumaları **her zaman** `subtitle_formats.read_subtitle_text`
  üzerinden. Windows-1254 Türkçe dosyalar doğrudan `utf-8` ile açılırsa çöker.
