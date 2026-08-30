# -*- coding: utf-8 -*-
"""Chunk günlüğünü sorgulama ve tek chunk'ı yeniden gönderme aracı.

Teslimde bozuk bir cue bulundu. Sorular sırasıyla şunlar:

    hangi istekte gitti        ->  chunk_sorgu.py bul 1874
    cue'ya kim dokundu         ->  chunk_sorgu.py gecmis 1874
    o istekte ne vardı         ->  chunk_sorgu.py goster ornek.srt__3
    aynısını göndersem ne olur ->  chunk_sorgu.py replay ornek.srt__3

`replay` HİÇBİR ŞEY YAZMAZ. Eski ve yeni çeviriyi yan yana basar, karar
okuyanındır — ikinci denemenin daha iyi olduğunun garantisi yoktur ve bu
projede otomatik uygulanan "düzeltmeler" defalarca çeviriyi bozdu.

Karşılaştırma ZAMAN DAMGASIYLA anahtarlanır. Cue numarası teslim boyunca
değişebilir; ölçülen bir vakada numaraya göre karşılaştırma 5.901 fark
gösterdi, gerçek fark 1.309'du.

Kullanım:
    python chunk_sorgu.py kosular
    python chunk_sorgu.py bul <cue-no|zaman-damgasi> [--gunluk YOL]
    python chunk_sorgu.py goster <custom_id> [--gunluk YOL]
    python chunk_sorgu.py gecmis <cue-no|zaman-damgasi>
    python chunk_sorgu.py passlar
    python chunk_sorgu.py replay <custom_id> [--gunluk YOL] [--model AD]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

import chunk_gunlugu

NL = chr(10)


def _gunluk_dizini() -> str:
    try:
        from app_state import state_path
        return os.path.join(str(state_path(__file__, "logs")), "chunk_gunlugu")
    except Exception:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "logs", "chunk_gunlugu")


def kosular() -> list:
    dizin = _gunluk_dizini()
    try:
        adlar = [a for a in os.listdir(dizin) if a.endswith(".jsonl")]
    except Exception:
        return []
    yollar = [(os.path.getmtime(os.path.join(dizin, a)),
               os.path.join(dizin, a)) for a in adlar]
    yollar.sort(reverse=True)
    return [y for _m, y in yollar]


def _gunluk_sec(istenen=None) -> str:
    if istenen:
        return istenen
    hepsi = kosular()
    if not hepsi:
        raise SystemExit("Günlük yok: %s" % _gunluk_dizini())
    return hepsi[0]


def _yukle(yol):
    kayitlar = chunk_gunlugu.oku(yol)
    if not kayitlar:
        raise SystemExit("Günlük okunamadı ya da boş: %s" % yol)
    return kayitlar, chunk_gunlugu.istemleri_topla(kayitlar)


def _kisa(metin, n=200):
    m = str(metin or "").replace(NL, " ")
    return m if len(m) <= n else m[:n] + "…"


def komut_kosular(_args) -> int:
    hepsi = kosular()
    if not hepsi:
        print("Günlük yok: %s" % _gunluk_dizini())
        return 1
    for yol in hepsi:
        kayitlar = chunk_gunlugu.oku(yol)
        o = chunk_gunlugu.ozet(kayitlar)
        print("%s  %s" % (
            time.strftime("%Y-%m-%d %H:%M",
                          time.localtime(os.path.getmtime(yol))),
            os.path.basename(yol)))
        print("    %d chunk · %d cue · %d hatalı · %d kesilen · %s"
              % (o["chunk"], o["cue"], o["hatali"], o["kesilen"],
                 ", ".join(o["modeller"]) or "model yok"))
    return 0


def komut_bul(args) -> int:
    yol = _gunluk_sec(args.gunluk)
    kayitlar, _istemler = _yukle(yol)
    hedef = str(args.hedef).strip()
    zamanla = ":" in hedef
    bulunan = chunk_gunlugu.cue_ara(
        kayitlar,
        cue_id=None if zamanla else hedef,
        zaman_damgasi=hedef if zamanla else None)
    if args.dosya:
        bulunan = [k for k in bulunan if args.dosya.lower() in k["dosya"].lower()]
    if not bulunan:
        print("%s için chunk bulunamadı (%s)" % (hedef, os.path.basename(yol)))
        if not zamanla:
            print("  Not: cue numarası birden çok dosyada geçebilir; zaman "
                  "damgasıyla aramak daha kesin.")
        return 1
    for kayit in bulunan:
        zamanlar = kayit.get("cue_zamanlari") or []
        print("%s   %s" % (kayit["custom_id"], kayit["dosya"]))
        print("    cue %s–%s (%d) · %s · %s"
              % (zamanlar[0][0] if zamanlar else "?",
                 zamanlar[-1][0] if zamanlar else "?",
                 kayit.get("cue_sayisi", 0),
                 kayit.get("model") or "model?",
                 kayit.get("akis") or ""))
        print("    yük: %s" % (", ".join(kayit.get("yuk_anahtarlari") or [])
                               or "—"))
        if kayit.get("bitis_sebebi") or kayit.get("hata"):
            print("    DİKKAT: bitiş=%s hata=%s"
                  % (kayit.get("bitis_sebebi") or "-",
                     kayit.get("hata") or "-"))
    return 0


def komut_goster(args) -> int:
    yol = _gunluk_sec(args.gunluk)
    kayitlar, istemler = _yukle(yol)
    for kayit in chunk_gunlugu.chunklar(kayitlar):
        if kayit["custom_id"] != args.custom_id:
            continue
        print("custom_id : %s" % kayit["custom_id"])
        print("dosya     : %s" % kayit["dosya"])
        print("akış      : %s (%s)" % (kayit.get("akis"), kayit.get("kaynak")))
        print("model     : %s" % kayit.get("model"))
        print("adres     : %s" % (kayit.get("taban_url") or "—"))
        print("token     : giriş %d / çıkış %d"
              % (kayit.get("giris_token", 0), kayit.get("cikis_token", 0)))
        print("bitiş     : %s" % (kayit.get("bitis_sebebi") or "—"))
        print("hata      : %s" % (kayit.get("hata") or "—"))
        print("yük anaht.: %s" % ", ".join(kayit.get("yuk_anahtarlari") or []))
        print("istem     : %s (%d karakter)"
              % (kayit.get("istem_sha"),
                 len(istemler.get(kayit.get("istem_sha"), ""))))
        print()
        print("── GÖNDERİLEN YÜK ──")
        print(kayit.get("yuk") or "—")
        print()
        print("── HAM YANIT ──")
        print(kayit.get("ham_yanit") or "—")
        return 0
    print("custom_id bulunamadı: %s" % args.custom_id)
    return 1


def _cevirileri_cikar(ham) -> dict:
    """Ham yanıttan {cue_id: metin}. Bozuk yanıt boş sözlük döner."""
    try:
        from response_integrity import parse_translation_payload
        sonuc = parse_translation_payload(str(ham or ""), None)
        return dict(sonuc.translations or {})
    except Exception:
        pass
    try:
        veri = json.loads(str(ham or ""))
    except Exception:
        return {}
    ogeler = veri if isinstance(veri, list) else (
        veri.get("translations") if isinstance(veri, dict) else None)
    if not isinstance(ogeler, list):
        return {}
    return {str(o.get("i", o.get("id"))): str(o.get("t", o.get("text")) or "")
            for o in ogeler if isinstance(o, dict)}


def _api_anahtari() -> str:
    """Anahtar günlükte DEĞİL kimlik deposunda; günlüğe sır yazılmaz."""
    import credential_store
    kok = os.path.dirname(os.path.abspath(__file__))
    atama = None
    try:
        with io.open(os.path.join(kok, ".gui_settings.json"),
                     encoding="utf-8") as fh:
            ayarlar = json.load(fh)
        atama = (ayarlar.get("api_key_assignments") or {}).get("main")
    except Exception:
        pass
    for servis in ([("api_profile_%s" % atama)] if atama else []) + \
            ["main_custom", "openai"]:
        anahtar = (credential_store.load_key(servis) or "").strip()
        if anahtar:
            return anahtar
    raise SystemExit(
        "API anahtarı bulunamadı. Uygulamada anahtar kayıtlı değilse "
        "yeniden gönderim yapılamaz.")


def komut_replay(args) -> int:
    yol = _gunluk_sec(args.gunluk)
    kayitlar, istemler = _yukle(yol)
    kayit = next((k for k in chunk_gunlugu.chunklar(kayitlar)
                  if k["custom_id"] == args.custom_id), None)
    if kayit is None:
        print("custom_id bulunamadı: %s" % args.custom_id)
        return 1
    if not (kayit.get("yuk") or "").strip():
        print("Bu kayıtta istek yükü yok (batch çıktısı gövdesiz gelmişti); "
              "yeniden gönderilemez.")
        return 1

    govde = chunk_gunlugu.replay_govdesi(
        kayit, istemler.get(kayit.get("istem_sha"), ""))
    if args.model:
        govde["model"] = args.model

    from openai import OpenAI
    istemci = OpenAI(api_key=_api_anahtari(),
                     base_url=kayit.get("taban_url") or None)
    print("Gönderiliyor: %s · %s · %d cue"
          % (kayit["custom_id"], govde.get("model"),
             kayit.get("cue_sayisi", 0)))
    yanit = istemci.chat.completions.create(**govde)
    yeni_ham = (yanit.choices[0].message.content or "").strip()

    satirlar = chunk_gunlugu.karsilastir(
        kayit,
        _cevirileri_cikar(kayit.get("ham_yanit")),
        _cevirileri_cikar(yeni_ham))
    degisen = [s for s in satirlar if s["degisti"]]
    print()
    print("%d cue · %d farklı" % (len(satirlar), len(degisen)))
    print()
    for satir in (degisen if not args.hepsi else satirlar):
        print("%s   (#%s)" % (satir["zaman"], satir["cue_id"]))
        print("  eski: %s" % _kisa(satir["eski"], 400))
        print("  yeni: %s" % _kisa(satir["yeni"], 400))
        print()
    print("Hiçbir dosya değiştirilmedi. Yeni çeviriyi kullanmak isterseniz "
          "kararı siz verirsiniz.")
    return 0


def komut_gecmis(args) -> int:
    """Bir cue'nun tam geçmişi: hangi istekte gitti, sonra kim dokundu."""
    yol = _gunluk_sec(args.gunluk)
    kayitlar, _istemler = _yukle(yol)
    hedef = str(args.hedef).strip()
    zamanla = ":" in hedef
    gecmis = chunk_gunlugu.cue_gecmisi(
        kayitlar,
        cue_id=None if zamanla else hedef,
        zaman_damgasi=hedef if zamanla else None,
        dosya=args.dosya or "")
    if not gecmis:
        print("%s için kayıt yok (%s)" % (hedef, os.path.basename(yol)))
        return 1
    for kayit in gecmis:
        if kayit.get("tip") == "chunk":
            print("ÇEVİRİ   %s   %s" % (kayit["custom_id"], kayit["dosya"]))
            print("         model %s · yük: %s"
                  % (kayit.get("model") or "?",
                     ", ".join(kayit.get("yuk_anahtarlari") or []) or "—"))
            if kayit.get("bitis_sebebi") or kayit.get("hata"):
                print("         DİKKAT bitiş=%s hata=%s"
                      % (kayit.get("bitis_sebebi") or "-",
                         kayit.get("hata") or "-"))
        else:
            print("%-8s %-11s %s"
                  % (kayit.get("pass_adi", "?").upper()[:8],
                     kayit.get("sonuc") or "?",
                     kayit.get("gerekce") or ""))
            print("         eski: %s" % _kisa(kayit.get("eski"), 300))
            print("         yeni: %s" % _kisa(kayit.get("yeni"), 300))
    return 0


def komut_passlar(args) -> int:
    """Pass başına: kaç öneri, kaçı uygulandı, kaçı reddedildi."""
    yol = _gunluk_sec(args.gunluk)
    kayitlar, _istemler = _yukle(yol)
    ozet = chunk_gunlugu.pass_ozeti(kayitlar)
    if not ozet:
        print("Bu koşuda pass kaydı yok (%s)" % os.path.basename(yol))
        return 1
    print("%-16s %8s %11s %11s %8s" % (
        "pass", "toplam", "uygulandı", "reddedildi", "rapor"))
    print("-" * 58)
    for ad in sorted(ozet):
        h = ozet[ad]
        print("%-16s %8d %11d %11d %8d" % (
            ad, h["toplam"], h["uygulandi"], h["reddedildi"], h["rapor"]))
    return 0


def main(argv=None) -> int:
    ayrac = argparse.ArgumentParser(
        description="Chunk adli günlüğü — sorgula ve yeniden gönder")
    altlar = ayrac.add_subparsers(dest="komut")

    altlar.add_parser("kosular", help="Günlükleri listele")

    p_bul = altlar.add_parser("bul", help="Bir cue hangi chunk'ta gitti")
    p_bul.add_argument("hedef", help="cue numarası VEYA zaman damgası")
    p_bul.add_argument("--gunluk")
    p_bul.add_argument("--dosya", help="dosya adına göre daralt")

    p_gos = altlar.add_parser("goster", help="Chunk'ın tam kaydı")
    p_gos.add_argument("custom_id")
    p_gos.add_argument("--gunluk")

    p_gec = altlar.add_parser(
        "gecmis", help="Bir cue'ya çeviri dışında kim dokundu")
    p_gec.add_argument("hedef", help="cue numarası VEYA zaman damgası")
    p_gec.add_argument("--gunluk")
    p_gec.add_argument("--dosya", help="dosya adına göre daralt")

    p_pas = altlar.add_parser("passlar", help="Pass başına öneri/red özeti")
    p_pas.add_argument("--gunluk")

    p_rep = altlar.add_parser("replay", help="Chunk'ı yeniden gönder ve karşılaştır")
    p_rep.add_argument("custom_id")
    p_rep.add_argument("--gunluk")
    p_rep.add_argument("--model", help="başka bir modelle dene")
    p_rep.add_argument("--hepsi", action="store_true",
                       help="değişmeyen cue'ları da bas")

    args = ayrac.parse_args(argv)
    if not args.komut:
        ayrac.print_help()
        return 2
    return {
        "kosular": komut_kosular,
        "bul": komut_bul,
        "goster": komut_goster,
        "gecmis": komut_gecmis,
        "passlar": komut_passlar,
        "replay": komut_replay,
    }[args.komut](args)


if __name__ == "__main__":
    sys.exit(main())
