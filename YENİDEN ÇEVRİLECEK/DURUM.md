# YENİDEN ÇEVRİLECEK — 2026-08-27

Bu klasördeki 7 bölüm **teslim edilmedi, yüklenmedi**. Çeviri dosyaya ve zamana
uyuyor, cue kayması yok, ama metnin büyük kısmı **Türkçe cümle değil** — model
kaynağı satır satır çevirmiş, İngilizce dizilim aynen kalmış.

## Kök neden — ölçüldü

Kaynak altyazıda cümle sonu noktalaması yoksa model cümle sınırını göremiyor ve
cue cue çeviriyor. Korelasyon tam:

| Dosya | Cue | Makine-cümle bloğu | Oran | Kaynakta noktalama |
|---|---:|---:|---:|---:|
| TheRealHustle-S01E05 | 592 | 315 | %53 | %0 |
| TheRealHustle-S01E04 | 624 | 295 | %47 | %0 |
| TheRealHustle-S01E03 | 648 | 269 | %42 | %0 |
| TheRealHustle-S01E01 | 582 | 205 | %35 | %0 |
| penn.and.teller.bullshit.s01e01 | 378 | 129 | %34 | %10 |
| TheRealHustle-S01E02 | 565 | 135 | %24 | %0 |
| penn.and.teller.bullshit.s01e02 | 357 | 59 | %17 | %13 |

Karşılaştırma — aynı koşuda, kaynağı noktalı olan bölümlerde makine cümlesi **sıfır**:

| Dosya | Kaynakta noktalama | Makine-cümle |
|---|---:|---:|
| Penn S01E11 | %75 | 0 |
| Penn S01E05 | %68 | 0 |
| Penn S01E10 | %34 | 17 |

"Makine-cümle bloğu" ölçütü: art arda **6 veya daha fazla** cue'nun hiçbirinin
cümle sonu noktalaması taşımaması. Toplam **1.407 cue**.

## Örnek (TheRealHustle-S01E03 #92-96)

    EN  there I believe yeah Gosselin's had a / look for you there just said the word /
        where we came from okay looking shot all / right they just asked you a few / questions there
    TR  durmuşsunuz diye düşünüyorum, evet, Gosselin bakmış / size orada, sadece söylemiş /
        nereden geldiğimizi, tamam, iyi bir görüntü hepsi / oldu, orada sadece birkaç / soru sordular

Sözcük sırası İngilizce, Türkçe cümle yok.

## Yapılması gereken

Bu bölümler **kaynağa önce cümle bölme / noktalama uygulanarak** yeniden
çevrilmeli. Elle cue düzeltmek semptomu kapatır; noktalamasız bir sonraki
kaynakta aynı sonuç çıkar.

Bug raporuna madde olarak eklendi:
`Raporlar\OPUS\bug-devri-20260827-dizi-logu.md`

## Klasörde ne var

Her bölümün kendi klasörü aynen taşındı: final `.srt`, `Raporlar\Ham`,
`Raporlar\Kaynak`, `Raporlar\Son Denetim` (Opus öncesi yedek) ve varsa
`Raporlar\Kurtarma`. Hiçbir şey silinmedi.
