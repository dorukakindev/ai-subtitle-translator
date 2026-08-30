# -*- coding: utf-8 -*-
"""Çeviriden ÖNCE kaynağı ölçen iki kontrol.

İkisi de dosya çapında felaketi önler ve ikisi de ölçülerek eklendi
(386 gerçek kaynak dosyası).

1. CÜMLE SONU NOKTALAMASI
   Kaynakta cümleler noktalamayla bitmiyorsa model satır satır çevirir
   ve dosyanın yarısı İngilizce söz diziminde kalmış "makine cümlesi"
   olur. Bu, bu projedeki en pahalı çeviri kusuru sınıfı: yama değil,
   kaynaktan yeniden çeviri gerektiriyor.

   Ölçülen dağılım — ortanca %70,4:
       %20 altı   38 dosya   (%9,8)
       %30 altı   47 dosya   (%12,2)   <- eşik
       %40 altı   68 dosya   (%17,6)
   Eşik %30: uyarı oranı %12'de kalıyor ve uçlar tartışmasız — on iki
   dosya TAM %0,0 (kayan altyazılı belgeseller).

2. KODLAMA (MOJIBAKE)
   Kaynak yanlış kodlamayla okunmuşsa çeviri baştan sona yanlış olur.
   386 dosyada 1 vaka bulundu (69 imza) — nadir ama olduğunda dosyanın
   tamamını götürüyor, ve çeviri bittikten sonra fark edilirse bütün
   maliyet boşa gider.

Program bu kontrolde DURMAZ: karar kullanıcınındır. İşi, parayı
harcamadan önce söylemektir.
"""
from __future__ import annotations

import re

# Cümlenin bittiğini gösteren işaretler. Kapanış tırnağı/parantez de sayılır:
# `"Bekle."` ve `(gülüyor)` cümle sonudur.
_SENTENCE_END_RE = re.compile(r"[.!?…:;\"'”’)\]]\s*$")

# Latin-1 olarak okunmuş UTF-8'in imzası HER ZAMAN İKİ KARAKTERLİKTİR:
# `ó` -> `Ã` + `³`, `ş` -> `Å` + `Ÿ`, `ı` -> `Ä` + `±`.
#
# Tek harfe bakmak YANLIŞ olur: çıplak `Å` İsveççe/Norveççede meşru bir
# harftir (`Åke`) ve İskandinav kaynağında yanlış alarm üretirdi.
# İkinci karakteri şart koşmak bu sınıfı yapısal olarak dışarıda tutar.
_MOJIBAKE_RE = re.compile(
    "[" + chr(0xC3) + chr(0xC5) + chr(0xC4) + chr(0xC2) + "]"
    "[" + chr(0x80) + "-" + chr(0xBF) + chr(0x178) + chr(0x17D)
    + chr(0x2018) + chr(0x2019) + chr(0x201C) + chr(0x201D)
    + chr(0x20AC) + "]"
    "|" + chr(0xE2) + chr(0x20AC) + "[" + chr(0x98) + "-"
    + chr(0x9D) + chr(0x2122) + chr(0x201C) + chr(0x201D) + "]")

PUNCTUATION_WARN_RATIO = 0.30
MOJIBAKE_WARN_HITS = 10
MIN_CUES_FOR_CHECK = 40


def sentence_end_ratio(cue_texts) -> float:
    """Cümle sonu noktalamasıyla biten cue oranı (0..1)."""
    metinler = [str(t or "").strip() for t in (cue_texts or ())]
    metinler = [t for t in metinler if t]
    if not metinler:
        return 1.0
    biten = sum(1 for t in metinler if _SENTENCE_END_RE.search(t))
    return biten / float(len(metinler))


def mojibake_hits(text: str) -> int:
    """Yanlış kodlama imzası sayısı."""
    return len(_MOJIBAKE_RE.findall(str(text or "")))


def on_kontrol(cue_texts, ham_metin: str = "") -> list:
    """Çeviri öncesi uyarılar. Boş liste = kaynak temiz.

    Döner: [{"tur", "seviye", "mesaj", "olcum"}]
    """
    uyarilar = []
    metinler = [str(t or "").strip() for t in (cue_texts or ()) if str(t or "").strip()]

    if len(metinler) >= MIN_CUES_FOR_CHECK:
        oran = sentence_end_ratio(metinler)
        if oran < PUNCTUATION_WARN_RATIO:
            uyarilar.append({
                "tur": "noktalama",
                "seviye": "uyari",
                "olcum": oran,
                "mesaj": (
                    "Kaynakta cue'ların yalnız %%%.0f'i cümle sonu "
                    "noktalamasıyla bitiyor (eşik %%%.0f). Model satır "
                    "satır çevirme eğilimine girer ve çıktının önemli bir "
                    "kısmı İngilizce söz diziminde kalabilir. Bu kusur "
                    "yamayla düzelmez, yeniden çeviri ister."
                    % (oran * 100, PUNCTUATION_WARN_RATIO * 100)),
            })

    izler = mojibake_hits(ham_metin)
    if izler >= MOJIBAKE_WARN_HITS:
        uyarilar.append({
            "tur": "kodlama",
            "seviye": "kritik",
            "olcum": izler,
            "mesaj": (
                "Kaynak metinde %d yanlış kodlama izi var (`Ã³`, `ÅŸ` gibi). "
                "Dosya büyük olasılıkla yanlış kodlamayla okunmuş; bu hâlde "
                "çeviri baştan sona yanlış olur ve harcanan para geri "
                "gelmez. Kaynağı doğru kodlamayla yeniden kaydedip tekrar "
                "deneyin." % izler),
        })
    return uyarilar
