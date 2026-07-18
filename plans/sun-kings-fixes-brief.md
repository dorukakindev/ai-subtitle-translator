# Brief: "Unearthed S10E05 — Rise of Egypt's Sun Kings" izole düzeltmeler (Tur 1, Sonnet 5)

Hazırlayan: **Opus 4.8** (log + kaynak/çıktı timestamp-hizalama, 2026-07-10). Protokol:
Opus teşhis + brief, Sonnet uygular. **Bu dosya oturumun en hasarlı çıktısı.** Kullanıcı
"önce izole fix'ler, 31-cue desync'i sonra" dedi → bu brief YALNIZ izole/cerrahi düzeltmeleri
kapsar; **#480-510 desync'i ve #543 düşük cue'su ERTELENDİ** (aşağıda §Ertelenen).

- **Hedef:** `C:\Users\K\Downloads\ÇIKTI\Unearthed_S10E05_Rise of Egypt's Sun Kings.English(US).srt`
- **Kaynak:** `E:\ALTYAZILAR\Altyazilar\HBO-Max\Unearthed\Season 10\Rise of Egypt's Sun Kings\Unearthed_S10E05_Rise of Egypt's Sun Kings.English(US).srt`
- **Önce `.bak` al.** Çıktı 720 cue (kaynak 721; #543 birleşme-düşüşü — §Ertelenen). Bu turun
  fix'leri **yalnız metin**, timecode DEĞİŞMEZ, cue sayısı 720 kalır.

## A) #28 — 12x outlier: tüm cümle #28'e sıkışmış (duplikasyon)
FIN #28, kaynağın #28+#29+#30'unun TAMAMINI içeriyor; #29 ("Kahire'nin 10 mil güneyinde,") ve
#30 ("Gize ile Sakkara arasında esrarengiz bir nekropol.") zaten DOĞRU ve ayrı. #28'i kaynağa
(#28 = "Abusir,") indir:
- #28: `Abusir,\nKahire’nin 10 mil güneyinde,\nGize ile Sakkara arasında gizemli bir nekropol.` → `Abusir,`
(#29, #30 DOKUNMA.)

## B) #157-159 — desync + duplikasyon + "güne" garble (3 cue 1:1)
Kaynak #157 "on top of the obelisk of the sun temple" / #158 "of Niuserre, and from here," /
#159 "we really touch the sky and the sun." Mevcutta #158 VE #159 ikisi de "göğe...dokun-"
diyor (duplikasyon) ve #159 "güne" (=gün) → olması gereken "güneşe" (=güneş). 1:1 hizala:
- #157: `Aslında Niuserre’nin güneş tapınağındaki\ndikilitaşın tepesindeyiz ve buradan,` → `Aslında Niuserre’nin güneş tapınağındaki\ndikilitaşın tepesindeyiz;`
- #158: `buradan gerçekten de\ngöğe ve güneşe dokunuyoruz.` → `ve buradan, gerçekten de`
- #159: `gerçekten göğe\nve güne dokunuruz.` → `göğe ve güneşe dokunuyoruz.`
(#156, #160 DOĞRU — dokunma.)

## C) Polish Pass'in soktuğu tek-cue garble'lar
Polish Pass bu koşuda YİNE tek-cue garble üretti (bkz. Solve Et Coagula: g geçtiğinde/dalı/Ulü).
İkisi grup-atomikliğine takılmadı çünkü tek-cue, `find_garble_tokens` de yakalamadı (kural yok):
- #303: `ohşap` → `ahşap`  ("ahşap"=wooden; Polish a→o bozdu. Satır: "Yirmi zarif işlenmiş\nohşap sütun, sağlam")
- #465: `ihai statüsünü` → `nihai statüsünü`  ("nihai"=final; Polish baştaki n'yi düşürdü)

## D) Ünlü uyumu garble'ları (R5 — tümü DÜZ apostrof U+0027)
Kaynak "Egypt" → "Mısır"; -da/-daki/-ın geri-ünlü olmalı (Mısır arka-ünlü):
- #248: `Mısır'deki` → `Mısır'daki`  ("Güney Mısır'deki Abydos...")
- #267: `Mısır'in` → `Mısır'ın`  ("ANLATICI: Sahure, Mısır'in 5. Hanedanının...")
- #697: `Mısır'in` → `Mısır'ın`  ("antik Mısır'in en önemlilerinden...")

## E) (OPSİYONEL, DÜŞÜK) Giza/Gize tutarlılığı
Dosya karışık: "Gize" baskın (#30/#646/#647/#653/#668) + Türkçe yerleşik exonim (Kahire gibi);
"Giza" azınlık (#77/#633/#635 + #498 ama #498 desync bloğunda, ERTELENDİ). Baskın+yerleşik
forma "Gize"ye normalize et (yalnız desync-DIŞI 3 cue):
- #77: `ünlü Giza Büyük Piramidi’ne` → `ünlü Gize Büyük Piramidi’ne`
- #633: `bu alanın neden tam burada, Giza ile` → `bu alanın neden tam burada, Gize ile`
- #635: `Abusir, Giza’nın` → `Abusir, Gize’nin`  (Gize ön-ünlü → genitif 'nın değil 'nin; kıvrık apostrof ’ KORU)
(İstemezsen bu bölümü atla — her iki form da anlaşılır; şart değil.)

## Doğrulama (Tur 1)
1. Cue sayısı 720, timecode değişmez (`.bak` ile karşılaştır).
2. Değişen cue kümesi TAM olarak: **28, 157, 158, 159, 248, 267, 303, 465, 697** (+ E yapılırsa
   77, 633, 635). Fazla/eksik OLMAMALI.
3. `ht.find_garble_tokens` tüm dosyada 0 (özellikle #248/#267/#697 temiz; "ohşap"/"ihai" gitmiş).
4. #157-159'da "güne dokunuruz" ve tekrarlanan "dokun-" çifti KALMAMALI.

---

## §ERTELENEN (kullanıcı kararı bekliyor — bu turda YAPMA)
- **#480-510 (31 cue) AĞIR DESYNC**: içerik #480'den itibaren kayıyor (FIN #480=SRC #480+#481),
  **#482 "Khamerernebty" (kralın kızının ADI) DÜŞMÜŞ**, kayma +1→+3 büyüyor, #507-510 önceki
  içeriği TEKRAR ediyor. Üst-sınır #479 temiz, alt-sınır #511 temiz. Ayrıca #480'de "sarasında"
  → "sarayında" garble'ı var (desync ile birlikte çözülür). İki seçenek: (a) Opus 31 cue'yu
  elle 1:1 yeniden hizalar (brief), (b) dosyayı yeniden çevir. Kullanıcı henüz seçmedi.
- **#543 düşük cue**: kaynak "in Egyptian belief." → FIN #542'ye birleşmiş ("Mısır inancında"),
  #543 boşalıp düşmüş (720 vs 721). İçerik kayıp değil ama zaman-slotu boş. Desync kararıyla
  birlikte ele alınabilir.

## DOKUNMA (doğrulanmış FP)
- **#350 (6.33x), #632 (0.12x)**: benign Türkçe SOV yeniden-dağıtımı ("a jar."→fiil öbeği #350'ye;
  "and understanding"→"ve" #632'de). İçerik tam. DOKUNMA.
- **'Egypt' mixed (Mısır×28/NARRATOR×2)**: "NARRATOR" konuşmacı etiketi, "Egypt" çevirisi DEĞİL. FP.

## Kod-gözlemi (uygulama YOK — ayrı tur adayı)
1. **Polish tek-cue garble sınıfı**: #303 "ohşap"(a→o), #465 "ihai"(n düştü), #480 "sarasında"
   (y düştü) — Solve'daki g/dalı/Ulü'yle birlikte ARTIK 3. dosya. Ortak desen: polish'in ürettiği
   token, orijinal bir kelimenin 1-karakter bozulması (silme/değişim) ve geçerli kelime değil.
   `_has_introduced_typo` yalnız İKİZLEME (tek→ttek) yakalıyor; silme/değişim kaçıyor. Aday guard:
   yeni token, orijinalin 1-edit-mesafesindeki bir komşusuysa VE bilinen-kelime değilse reddet
   (sözlük gerektirir — dikkatli tasarım).
2. **31-cue saf-kayma desync dedektöre büyük ölçüde görünmez**: `detect_alignment_issues` yalnız
   duplikasyon ürettiği yeri (#504/#508) yakaladı; #480-506 saf-kayma kısmı akıcı olduğu için
   radar altında. CHUNK=30'a ve Fix C'ye rağmen oldu → chunk küçültme yetmiyor. Timestamp-bazlı
   içerik-kayması dedektörü (kaynak vs final, cümle-eşleştirme) gerçek çözüm olabilir; ayrı tur.
