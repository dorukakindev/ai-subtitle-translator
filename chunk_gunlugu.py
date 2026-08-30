# -*- coding: utf-8 -*-
"""Chunk adli günlüğü — bir kusurun HANGİ isteğe ait olduğunu söyler.

Teslimde bir bozukluk bulunduğunda (kayma, hatalı terim, düşen replik)
cevaplanamayan soru şuydu: bu cue hangi chunk'ta gitti, o istekte ne
vardı, model ne döndü. Rapor cue'yu gösteriyordu, isteği değil.

Günlük her ana çeviri isteği için bir satır yazar; satırdan chunk yeniden
kurulabilir ve TEK BAŞINA yeniden gönderilebilir. Karşılaştırma eski/yeni
olarak yan yana döner — kendiliğinden hiçbir şey yazılmaz, çünkü ikinci
denemenin daha iyi olduğunun garantisi yoktur.

TASARIM KARARLARI

* MALİYET ALANI YOK. Bu projede ana rota (gpt-5.4 vekil sağlayıcı)
  dinamik faturalandırılıyor; yerelde hesaplanan bir kuruş rakamı yanlış
  olur ve — daha kötüsü — doğru sanılır. Token sayısı ölçülen bir
  büyüklüktür, günlüğe o girer; para girmez.

* KARŞILAŞTIRMA ZAMAN DAMGASIYLA ANAHTARLANIR, cue numarasıyla değil.
  Teslim yeniden numaralandığında tek bir silinmiş cue sonraki her satırı
  "değişmiş" gösterir; bu projede ölçülen vaka 5.901 sahte farka karşı
  1.309 gerçek farktı. Zaman damgası çeviri boyunca değişmeyen tek
  kimliktir.

* SİSTEM İSTEMİ SATIR SATIR TEKRARLANMAZ. Bir dosyanın bütün chunk'ları
  aynı istemi taşır ve istem birkaç kilobayttır; dosya başına bir kez
  başlık satırı olarak yazılır, chunk satırları özetiyle (sha) atıfta
  bulunur. Yeniden gönderim ikisini birleştirir.

* GÜNLÜK BUDANIR. Diskte sınırsız büyüyen bir teşhis aracı, teşhis
  edilecek şeyin kendisi olur.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time

SURUM = 1

# Koşu günlükleri hem SAYIYLA hem BOYUTLA sınırlanır, çünkü koşu boyu
# tek bir dosyayla otuz dosya arasında değişiyor ve tek başına sayı sınırı
# diskte ne olacağını söylemiyor. Gerçek ölçüm (1.033 cue, 41 chunk,
# 19.199 karakterlik sistem istemi): dosya başına 312 KB, chunk başına
# 7,6 KB. Otuz dosyalık bir koşu 9,1 MB; yirmi böyle koşu 183 MB eder.
#
# Yükü ya da yanıtı kırpmak seçenek değil — günlüğün bütün işi "ne
# gönderildi, ne döndü" sorusunu cevaplamak. O yüzden az sayıda koşuyu
# tam sadakatle tutmak, çok sayıda koşuyu cevap veremeyecek hâlde
# tutmaya tercih edildi.
VARSAYILAN_KOSU_SINIRI = 20
VARSAYILAN_BAYT_SINIRI = 100 * 1024 * 1024


def _sha(metin) -> str:
    ham = metin if isinstance(metin, bytes) else str(metin or "").encode("utf-8")
    return hashlib.sha256(ham).hexdigest()[:16]


def _json_satir(kayit) -> str:
    return json.dumps(kayit, ensure_ascii=False, sort_keys=True)


def _yuk_anahtarlari(kullanici_mesaji) -> list:
    """İstekte hangi bağlam anahtarlarının GERÇEKTEN gittiği.

    "Zincirleme bağlam açıktı" ile "bu isteğe prev_tr kondu" ayrı
    şeylerdir; ayarın değerini değil, gövdenin içeriğini kaydeder.
    """
    try:
        yuk = json.loads(str(kullanici_mesaji or ""))
    except Exception:
        return []
    if not isinstance(yuk, dict):
        return []
    return sorted(k for k, v in yuk.items()
                  if v not in (None, "", [], {}, ()))


def _zaman_damgasi(uclu) -> str:
    """İKİ AYRI file_map şekli var, ikisi de kabul edilir.

    Senkron akış `(cue_id, "00:00:01,000 --> 00:00:02,000", dosya_yolu)`
    yazar; hibrit akış `(cue_id, baslangic, bitis)` yazar. Yalnız birini
    varsaymak, ikinci akışta zaman damgasının yerine dosya yolunu ya da
    yarım bir damgayı kaydeder — ve bu günlüğün tek güvenilir anahtarı
    zaman damgasıdır.
    """
    ikinci = str(uclu[1] if len(uclu) > 1 else "").strip()
    if "-->" in ikinci:
        return ikinci
    ucuncu = str(uclu[2] if len(uclu) > 2 else "").strip()
    if ucuncu and ":" in ucuncu and "-->" not in ucuncu:
        return ikinci + " --> " + ucuncu
    return ikinci


def kayit_olustur(custom_id, cue_bilgisi, body, *, akis="", dosya="",
                  model="", taban_url="", kaynak="api", ham_yanit="",
                  giris_token=0, cikis_token=0, bitis_sebebi="",
                  deneme=1, sure_ms=0, hata="", zaman=None) -> dict:
    """Tek chunk kaydı.

    cue_bilgisi: build_requests'in `file_map[custom_id]` girdisi —
    `(cue_id, zaman_damgasi, dosya_yolu)` üçlüleri.
    """
    ucluler = list(cue_bilgisi or ())
    cue_zamanlari = [[str(u[0]), _zaman_damgasi(u)]
                     for u in ucluler if len(u) >= 2]
    mesajlar = (body or {}).get("messages") or []
    sistem = ""
    kullanici = ""
    for m in mesajlar:
        rol = str((m or {}).get("role") or "")
        if rol in ("system", "developer") and not sistem:
            sistem = str(m.get("content") or "")
        elif rol == "user" and not kullanici:
            kullanici = str(m.get("content") or "")
    return {
        "surum": SURUM,
        "tip": "chunk",
        "zaman": float(zaman if zaman is not None else time.time()),
        "akis": str(akis or ""),
        "dosya": os.path.basename(str(dosya or "")),
        "custom_id": str(custom_id or ""),
        "cue_sayisi": len(cue_zamanlari),
        "cue_zamanlari": cue_zamanlari,
        "model": str(model or (body or {}).get("model") or ""),
        "taban_url": str(taban_url or ""),
        "yuk_anahtarlari": _yuk_anahtarlari(kullanici),
        "istem_sha": _sha(sistem),
        "yuk": kullanici,
        "istek_ayarlari": {
            k: v for k, v in (body or {}).items() if k != "messages"
        },
        "yanit_sha": _sha(ham_yanit),
        "yanit_uzunluk": len(str(ham_yanit or "")),
        "ham_yanit": str(ham_yanit or ""),
        "giris_token": int(giris_token or 0),
        "cikis_token": int(cikis_token or 0),
        "bitis_sebebi": str(bitis_sebebi or ""),
        "kaynak": str(kaynak or ""),
        "deneme": int(deneme or 1),
        "sure_ms": int(sure_ms or 0),
        "hata": str(hata or ""),
    }


def istem_basligi(sistem_metni) -> dict:
    return {"surum": SURUM, "tip": "istem",
            "istem_sha": _sha(sistem_metni),
            "istem": str(sistem_metni or "")}


def yaz(yol, kayitlar) -> str:
    """Kayıtları JSONL'e ekler. Günlük yazımı çeviriyi asla düşürmez."""
    tekil = isinstance(kayitlar, dict)
    dizi = [kayitlar] if tekil else list(kayitlar or ())
    if not dizi:
        return str(yol)
    dizin = os.path.dirname(str(yol))
    if dizin and not os.path.isdir(dizin):
        os.makedirs(dizin, exist_ok=True)
    with io.open(yol, "a", encoding="utf-8") as fh:
        for kayit in dizi:
            fh.write(_json_satir(kayit) + chr(10))
    return str(yol)


def oku(yol) -> list:
    """Bozuk satırlar atlanır: yarım yazılmış son satır yüzünden bütün
    günlüğü kaybetmek, günlüğün amacına aykırı."""
    kayitlar = []
    try:
        with io.open(yol, encoding="utf-8") as fh:
            for satir in fh:
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    kayitlar.append(json.loads(satir))
                except Exception:
                    continue
    except Exception:
        return []
    return kayitlar


def istemleri_topla(kayitlar) -> dict:
    return {k.get("istem_sha"): k.get("istem", "")
            for k in (kayitlar or ()) if k.get("tip") == "istem"}


def chunklar(kayitlar) -> list:
    return [k for k in (kayitlar or ()) if k.get("tip") == "chunk"]


def cue_ara(kayitlar, cue_id=None, zaman_damgasi=None) -> list:
    """Bir cue'yu HANGİ chunk'ın ürettiği.

    Zaman damgası verildiyse onunla eşleşir; teslim yeniden
    numaralanmışsa cue numarası yanıltır, zaman damgası yanıltmaz.
    """
    hedef_id = None if cue_id is None else str(cue_id)
    hedef_ts = None if zaman_damgasi is None else str(zaman_damgasi).strip()
    bulunan = []
    for kayit in chunklar(kayitlar):
        for cid, ts in kayit.get("cue_zamanlari") or ():
            if hedef_ts is not None and str(ts).strip() == hedef_ts:
                bulunan.append(kayit)
                break
            if hedef_ts is None and hedef_id is not None and str(cid) == hedef_id:
                bulunan.append(kayit)
                break
    return bulunan


def replay_govdesi(kayit, istem_metni="") -> dict:
    """Kayıttan yeniden gönderilebilir istek gövdesi kurar.

    Gövde ORİJİNALİN AYNISIDIR — model, ayarlar ve yük olduğu gibi. Neyin
    değiştiğini görebilmek için önce aynısını göndermek gerekir; farklı
    bir model denemek isteyen `model` alanını kendisi değiştirir.
    """
    ayarlar = dict(kayit.get("istek_ayarlari") or {})
    rol = "developer" if str(ayarlar.get("model") or "").lower().startswith(
        ("gpt-5", "codex-", "o1", "o3", "o4")) else "system"
    govde = dict(ayarlar)
    govde["messages"] = [
        {"role": rol, "content": str(istem_metni or "")},
        {"role": "user", "content": str(kayit.get("yuk") or "")},
    ]
    return govde


def karsilastir(kayit, eski_ceviriler, yeni_ceviriler) -> list:
    """Eski ve yeni çeviriyi ZAMAN DAMGASIYLA yan yana koyar.

    eski/yeni: {cue_id: metin}. Anahtar cue numarası DEĞİL zaman damgası;
    numara teslim boyunca değişebilir, zaman değişmez.

    Döner: [{"zaman", "cue_id", "eski", "yeni", "degisti"}]
    """
    eski = {str(k): str(v or "") for k, v in (eski_ceviriler or {}).items()}
    yeni = {str(k): str(v or "") for k, v in (yeni_ceviriler or {}).items()}
    satirlar = []
    for cid, ts in kayit.get("cue_zamanlari") or ():
        e = eski.get(str(cid), "")
        y = yeni.get(str(cid), "")
        satirlar.append({
            "zaman": str(ts),
            "cue_id": str(cid),
            "eski": e,
            "yeni": y,
            "degisti": e.strip() != y.strip(),
        })
    return satirlar


def ozet(kayitlar) -> dict:
    """Bir koşunun tek bakışta hâli."""
    c = chunklar(kayitlar)
    return {
        "chunk": len(c),
        "cue": sum(k.get("cue_sayisi", 0) for k in c),
        "hatali": sum(1 for k in c if k.get("hata")),
        "kesilen": sum(1 for k in c if k.get("bitis_sebebi") == "length"),
        "giris_token": sum(k.get("giris_token", 0) for k in c),
        "cikis_token": sum(k.get("cikis_token", 0) for k in c),
        "kaynaklar": sorted({str(k.get("kaynak") or "") for k in c}),
        "modeller": sorted({str(k.get("model") or "") for k in c}),
    }


def budan(dizin, sinir=VARSAYILAN_KOSU_SINIRI,
          bayt_siniri=VARSAYILAN_BAYT_SINIRI) -> list:
    """En yeni koşuları tutar; sayı VE boyut sınırının ikisine de uyar.

    En yeni günlük hiçbir koşulda silinmez: tek başına bayt sınırını aşan
    bir koşu, o koşuyu diskte sıfır iz bırakacak şekilde silmeye gerekçe
    olamaz — silinirse elde teşhis edilecek şey kalmaz.
    """
    try:
        adlar = [a for a in os.listdir(dizin) if a.endswith(".jsonl")]
    except Exception:
        return []
    yollar = []
    for ad in adlar:
        tam = os.path.join(dizin, ad)
        try:
            yollar.append((os.path.getmtime(tam), os.path.getsize(tam), tam))
        except Exception:
            continue
    yollar.sort(reverse=True)
    silinecek = list(yollar[max(int(sinir or 0), 0):])
    kalanlar = yollar[:max(int(sinir or 0), 0)]
    if bayt_siniri:
        toplam = 0
        for sira, (_mt, boyut, tam) in enumerate(kalanlar):
            toplam += boyut
            if sira > 0 and toplam > bayt_siniri:
                silinecek.extend(kalanlar[sira:])
                break
    silinen = []
    for _mt, _boyut, tam in silinecek:
        try:
            os.remove(tam)
            silinen.append(tam)
        except Exception:
            continue
    return silinen
