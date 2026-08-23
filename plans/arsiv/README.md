# Denetim raporları arşivi

Bu klasördeki dosyalar **tamamlanmış denetimlerin künyesi**, güncel bir
başvuru kaynağı değil. Hepsi işlendi: kabul edilen bulgular düzeltildi,
reddedilenler gerekçesiyle kayda geçti.

## Bunları referans olarak KULLANMA

İki somut nedenle:

**Satır numaraları ölü.** Raporlar yazıldıkları günün HEAD'ine bakıyor.
Örnek: `DERIN_BUG_DENETIMI_2026-08-20.md` yazıldığından beri yalnız
`subtitle_translator_gui.py` dosyasında 106 commit'te +6.224 / −628 satır
değişti. İçindeki her `dosya.py:12297` göndermesi bugün başka bir yeri
gösteriyor.

**Veri iddiaları doğrulamayı her zaman geçmiyor.** Bu arşivdeki ve
sonraki denetimlerde defalarca yaşandı:

- Bir denetim `GİRDİ/.project_memory.json` içinde 49 terimlik bir karışma
  gösterdi; o dosya bu makinede hiç yok.
- Önerilen bir SOV kuralı ölçülünce yanlış alarmı düşürüyor ama *gerçek*
  bir desync'i kaçırıyordu — geri alındı.
- Para birimi bulgularının kanıt cue'larının 6'sı, arşivlenmiş "kaynağı"
  Arapça olan dosyalardan geliyordu; 2'si ise çeviri hatası değil, kaynak
  altyazıdan `$` işaretinin sıyrılmasıydı.

Yani bir raporun "doğrulanmış bulgu" demesi, bulgunun doğrulandığı
anlamına gelmiyor. Ölçmeden hareket etme.

## Kalıcı bilgi nerede duruyor

Bu raporlardan damıtılan ve hâlâ geçerli olan tek şey, **hangi bulgunun
reddedildiği ve neden** — çünkü onu bilmeyen biri bilinçli bir guard'ı
"bug" sanıp düzeltir ve programı bozar.

O kayıt burada değil, eskiyemeyecek yerlerde tutuluyor:

- **Testler** — bilinçli tasarımı kilitleyen bir test, kod değişince
  kırılır ve kendini duyurur. Bir markdown iddiası sessizce eskiyebilir.
- **Kod yorumları** — geri alınan kurallar reddedilme gerekçesiyle
  birlikte ilgili fonksiyonun içinde yazıyor (örn. `_find_adjacent_
  duplicate_ids` içindeki SOV notu).
- **Proje hafızası** — hangi turda ne kabul/red edildiğinin dizini.

Yeni bir denetim bir bulguyu "yeniden keşfederse", cevabı önce testlerde
ve kod yorumlarında ara; burada değil.
