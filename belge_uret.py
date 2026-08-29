# -*- coding: utf-8 -*-
"""KILAVUZ.md'yi `kilavuz.py`'den üretir.

    python belge_uret.py

Elle düzenlemeyin — bir sonraki üretimde silinir. Metni değiştirmek için
`kilavuz.py` içindeki maddeyi düzenleyin; böylece arayüzdeki ipucu, yardım
penceresi ve bu dosya birlikte güncellenir.

`--kontrol` ile çalıştırılırsa yazmaz, yalnız dosyanın güncel olup
olmadığını söyler (sürüm kontrolünde işe yarar).
"""
from __future__ import annotations

import io
import os
import sys

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)

import kilavuz

HEDEF = os.path.join(KOK, "KILAVUZ.md")


def _bolum_metni() -> list:
    satirlar = []
    gruplar = kilavuz.bolume_gore()
    for bolum in kilavuz.BOLUMLER:
        maddeler = gruplar.get(bolum) or []
        if not maddeler:
            continue
        satirlar.append("## %s" % bolum)
        satirlar.append("")
        for _ad, madde in maddeler:
            varsayilan = {True: "açık", False: "kapalı", None: "—"}[
                madde.varsayilan]
            satirlar.append("### %s" % madde.baslik)
            satirlar.append("")
            satirlar.append("**Varsayılan:** %s" % varsayilan)
            if madde.maliyet:
                satirlar.append("  ·  **Maliyet:** %s" % madde.maliyet)
            satirlar.append("")
            satirlar.append(madde.uzun)
            satirlar.append("")
            if madde.ne_zaman:
                satirlar.append("**Ne zaman:** %s" % madde.ne_zaman)
                satirlar.append("")
            if madde.iliskili:
                adlar = ", ".join(
                    kilavuz.MADDELER[b].baslik for b in madde.iliskili
                    if b in kilavuz.MADDELER)
                if adlar:
                    satirlar.append("**İlgili:** %s" % adlar)
                    satirlar.append("")
    return satirlar


def _bulgu_metni() -> list:
    try:
        import subtitle_translator_gui as g
    except Exception:
        return []
    satirlar = ["## Rapordaki bulgu sınıfları", ""]
    satirlar.append(
        "Teslim taraması bu sınıfları arar. Her bulgu bir cue numarası ve "
        "zaman damgasıyla adreslenir.")
    satirlar.append("")
    satirlar.append("Güven dereceleri:")
    satirlar.append("")
    for derece in ("kesin", "muhtemel", "bilgi"):
        aciklama = kilavuz.GUVEN_ACIKLAMASI.get(derece, "")
        satirlar.append("- **%s** — %s" % (derece, aciklama))
    satirlar.append("")
    satirlar.append("| sınıf | güven | ne demek | ne yapmalı |")
    satirlar.append("|---|---|---|---|")
    for anahtar, guven, etiket, oneri in kilavuz.bulgu_sinifi_maddeleri(
            g._FINDING_CLASSES):
        satirlar.append("| `%s` | %s | %s | %s |" % (
            anahtar, guven, etiket.replace("|", "\\|"),
            oneri.replace("|", "\\|")))
    satirlar.append("")
    return satirlar


def _tur_metni() -> list:
    try:
        import subtitle_translator_gui as g
    except Exception:
        return []
    turler = kilavuz.icerik_turu_maddeleri(g.CONTENT_SCHEMAS)
    satirlar = ["## İçerik türleri", ""]
    satirlar.append(
        "Her tür kendi çeviri kurallarını taşır. \"Otomatik\" seçilirse tür "
        "dosyanın kendisinden tespit edilir. Toplam **%d** tür:"
        % len(turler))
    satirlar.append("")
    adlar = [ad for ad, _kurallar in turler]
    for i in range(0, len(adlar), 4):
        satirlar.append("- " + " · ".join(adlar[i:i + 4]))
    satirlar.append("")
    return satirlar


def uret() -> str:
    parcalar = [
        "# Kullanım Kılavuzu",
        "",
        "> Bu dosya `kilavuz.py`'den ÜRETİLİR (`python belge_uret.py`).",
        "> Elle düzenlemeyin; değişiklik bir sonraki üretimde silinir.",
        "",
        "Programın içindeki **Yardım** penceresi de aynı kaynaktan beslenir, "
        "üstüne arama yapabilirsiniz.",
        "",
    ]
    parcalar += _bolum_metni()
    parcalar += _bulgu_metni()
    parcalar += _tur_metni()
    return "\n".join(parcalar).rstrip() + "\n"


def main(argv) -> int:
    yeni = uret()
    if "--kontrol" in argv:
        eski = ""
        if os.path.exists(HEDEF):
            with io.open(HEDEF, encoding="utf-8") as fh:
                eski = fh.read()
        if eski == yeni:
            print("KILAVUZ.md guncel.")
            return 0
        print("KILAVUZ.md ESKI — `python belge_uret.py` calistirin.")
        return 1
    with io.open(HEDEF, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(yeni)
    print("KILAVUZ.md yazildi (%d satir)." % yeni.count("\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
