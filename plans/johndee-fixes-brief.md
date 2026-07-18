# Brief: John Dee (Renaissance Alchemist) — desync + leak düzeltmeleri (Sonnet 5)

Hazırlayan: **Opus 4.8** (log + dosya/timestamp doğrulaması, 2026-07-09). Protokol:
Opus karar verir, Sonnet uygular. Dosya: `C:\Users\K\Downloads\ÇIKTI\john-dee-renaissance-alchemist-jason-louv.srt`
(1482 cue). Kaynak: `E:\ALTYAZILAR\Altyazilar\Hulu-Altyazilar\john-dee-renaissance-alchemist-jason-louv.vtt`.
Önce `.bak` al; **cue sayısı 1482, timecode DEĞİŞMEZ**.

## Bağlam: bu koşu, Fix C'nin (öz-onarım) İLK canlı testi
Log: `↺ 5 chunk yeniden deneniyor, 5 chunk-içi tekrar` → 5 chunk otomatik yakalanıp
düzeltildi (chunk_30/342/403/1298/1328). Aşağıdaki 3 desync bölgesi Fix C'yi ATLATTI —
büyük olasılıkla **chunk-sınırını aşan** tekrarlar (Fix C yalnız chunk-içine bakar) ya da
sonraki pass'lerin bıraktığı kalıntı. (Kod-gözlemi §son'da.)

## A) Ayrık leak/garble düzeltmeleri (net)

| Cue | Mevcut | YENİ | Neden |
|---|---|---|---|
| #71 | ...tepeden inme bir **church** ya da... | ...tepeden inme bir **kilise** ya da... | çevrilmemiş İngilizce |
| #73 | O yüzden bence **he's a fascinating person** | O yüzden bence o büyüleyici biri, | çevrilmemiş İngilizce (kaynak: "I think he's a fascinating person") |
| #1132 | Geri çekilip **a baktığınızda** | Geri çekilip baktığınızda | başıboş "a" (R1 kuralı yakaladı) |

## B) Desync-1 — #981-991 (11 cue, 1:1 yeniden hizala)

Kaynak #982'den itibaren içerik -1 kaymış; #990/#991 "Dee için tezahür etti" TEKRARI var;
#985'te "**different**" çevrilmemiş. İçerik kaybı YOK (hepsi mevcut, kaymış) ama tekrar+leak
gerçek. Aşağıdaki tam metinlerle DEĞİŞTİR (kaynağa sadık, akıcı):

| cue | Kaynak (EN) | YENİ TR |
|---|---|---|
| #981 | than perhaps even the King James Bible, parts of them. | hatta onlardan daha üstündür. |
| #982 | And incredible, even just as a literary record. | Salt yazınsal bir kayıt olarak bile inanılmaz. |
| #983 | But there were certainly parts where Kelley became unhinged. | Ama kesinlikle Kelley'nin çıldırdığı anlar da oldu. |
| #984 | And it was a tumultuous working relationship, | Çalkantılı bir çalışma ilişkisiydi, |
| #985 | but a fascinating one at a human level | ama insani düzeyde büyüleyici bir ilişki; |
| #986 | between two very different individuals, who | birbirinden çok farklı iki insan arasında, |
| #987 | formed a greater whole. | ki bir araya gelip daha büyük bir bütün oluşturdular. |
| #988 | >>REGINA: Well, that's why I brought up | >>REGINA: İşte tam da bu yüzden gündeme getirdim: |
| #989 | the difficulty of being open to other forces. | başka güçlere açık olmanın zorluğunu. |
| #990 | Because at the same time, kind of monstrous types of entities | Çünkü aynı zamanda, bir tür canavarımsı varlıklar da |
| #991 | started manifesting for Dee and such as well. | Dee ve benzerleri için belirmeye başlamıştı. |

(#979-980 DOĞRU — "Kral James çevirisi İncil'in kimi bölümleriyle yan yana" — dokunma.
#992 "Sanki bunlar biraz melekvari şeylermiş gibi" DOĞRU — dokunma.)

## C) Desync-2 — #1064-1070 (7 cue, 1:1)

İçerik doğru dağılmış ama #1069/#1070 ">>LOUV: Doğru" TEKRARI var. 1:1 yeniden hizala:

| cue | Kaynak | YENİ TR |
|---|---|---|
| #1064 | >>REGINA: And what was the direction and nature | >>REGINA: Peki, bu çalışmanın gövdesinin yönü ve |
| #1065 | of the body of work, in summary? | niteliği, özetle neydi? |
| #1066 | And then I do want to get into the end times | Sonra da kıyamet zamanı senaryosuna, |
| #1067 | scenario, the mission to save the 144,000 souls, | 144.000 ruhu kurtarma görevine |
| #1068 | and who those actually were. | ve onların gerçekte kim olduğuna girmek istiyorum. |
| #1069 | So we'll lead from one question to the next. | Böylece sorudan soruya ilerleyelim. |
| #1070 | >>LOUV: Right. | >>LOUV: Doğru. |

## D) Desync-3 — #1077-1083 (7 cue, 1:1)

Kaynak #1077'den -1 kaymış; #1082/#1083 "melek âlemleri" TEKRARI var. 1:1 yeniden hizala:

| cue | Kaynak | YENİ TR |
|---|---|---|
| #1077 | a term they used at the time. | o dönemde kullandıkları bir terim. |
| #1078 | It's a term later writers used. | Sonraki yazarların kullandığı bir terim bu. |
| #1079 | And the Enochian system, and language, | Enokyan sistemi ve diline gelince, |
| #1080 | which was supposed to be the language that the angels spoke | ki bu, meleklerin Eden'den düşüşten önce |
| #1081 | before the fall of-- from Eden, was | konuştuğu dil olduğu sanılıyordu; amacı |
| #1082 | to tune them up and allow them deeper access | onları uyumlayıp daha derin erişim sağlamaktı— |
| #1083 | to the angelic realms. | melek âlemlerine. |

(#1084 "Bunu aştıklarında melekler" DOĞRU — dokunma.)

## E) DOKUNMA (doğrulanmış yanlış-pozitif / benign)
- **#1452 (🚨 missing_dialogue)**: kaynak "of ecological collapse." → #1451'e MERGE olmuş
  ("ekolojik çöküşün eşiğindeyken"); içerik kayıp değil, cue benign biçimde düşmüş. Fix YOK.
- **Mixed-term uyarıları çoğunlukla FP**: 'Kelley'→Evet (Evet ayrı cümle, FP); 'Bible'→
  İncil/Kral (Kral "King James"ten geliyor, çeviri DEĞİL — FP); 'Christianity'→Hristiyanlığın/
  Hristiyanlık (AYNI kelimenin ekli/eksiz hâli — gövde-eşleştirici ayırmış, FP). Gerçek terim
  hatası yok. (Küçük opsiyonel: "Bible" bazen "İncil" bazen "Kutsal Kitap" — ikisi de meşru,
  tutarlılık istenirse "Kutsal Kitap"a çekilebilir ama şart değil.)
- #178-182, #978-982: benign SOV yeniden dağıtımı — içerik doğru, dokunma.

## Doğrulama (uyguladıktan sonra)
1. Cue sayısı 1482, timecode değişmez.
2. `ht.find_garble_tokens` tüm dosyada 0 (özellikle #73/#1132/#985 temiz).
3. `church`, `he's a fascinating`, `different` (İngilizce), tekrarlanan ">>LOUV: Doğru"
   ardışık çifti, tekrarlanan "melek âlemleri" çifti KALMAMALI.
4. `detect_alignment_issues`'ı yeni çıktı vs kaynak üzerinde çalıştır → #982-991/#1064-1070/
   #1077-1083 için adjacent_duplicate bulgusu KALMAMALI.

## Kod-gözlemi (uygulama YOK — ayrı tur adayı)
Fix C 5 chunk yakaladı ama 3 desync atlattı çünkü `_find_adjacent_duplicate_ids` yalnız
tek chunk'ın item'larına bakıyor; tekrar chunk SINIRINI aşınca (cue N son chunk'ta, N+1
sonraki chunk'ta) görülmüyor. Aday: `_retry_hata` bittikten sonra TÜM raw_map birleştirilip
komşu-sınır cue çiftleri de kontrol edilsin (ya da post-write dedektör zaten yakaladığı için
bu kabul edilebilir — kullanıcı kararı). Ayrıca CHUNK=30'a rağmen desync oldu → chunk
küçültme tek başına yetmiyor, tespit+onarım asıl güvence.
