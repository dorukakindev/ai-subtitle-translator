# -*- coding: utf-8 -*-
"""Teslim dedektörleri için gerçek kusur regresyon arşivi.

`tests/regression_corpus/cases.jsonl` yalnız ÜÇ katmanı sınıyordu
(`find_garble_tokens`, `has_non_turkish_target_leak`,
`validate_polish_candidate`). Teslim taramasının dedektörleri — düşen
replik, sızan cue numarası, çevirmen glossu, terim guard'ı, karakter
listesi, biçim onarıcıları — hiç ölçülmüyordu.

Bu dosya onları ölçer. Her vaka GERÇEK arşive karşı ölçülmüştür ve
`koken` alanında nereden geldiği yazar.

`bekleme` üç değerden biri:
    yakala         → dedektör bunu bulmalı
    yakalama       → yanlış alarm olurdu, bulmamalı
    bilinen_kacak  → gerçek kusur ama BUGÜN yakalanmıyor

Bilinen kaçaklar testi KIRMAZ; sayıları kilitlenir. Amaç onları görünür
tutmak: bu depoda bir kuralın kaçırdığı şey, yakaladığı kadar önemli.
"""
import io
import json
import os
import sys
import unittest
from collections import defaultdict

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import hybrid_translate as ht
import subtitle_translator_gui as gui

VAKA_DOSYASI = os.path.join(
    KOK, "tests", "regression_corpus", "delivery_cases.jsonl")

# Bugün kaçırdığımız gerçek kusur sayısı. ARTMAMALI; düşerse sevinilir ve
# bu sayı güncellenir.
BILINEN_KACAK_SINIRI = 2


def _vakalar():
    with io.open(VAKA_DOSYASI, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ── Dedektör çalıştırıcıları ────────────────────────────────────────────
# Her biri True dönerse "dedektör bunu yakaladı" demektir.

def _calistir_missing_replica(vaka):
    return ht._missing_replica(vaka["kaynak"], vaka["teslim"])


def _onarim_sonucu(vaka, uretilen):
    """Onarıcılar için ortak yorum.

    "Yakaladı" = METNİ DEĞİŞTİRDİ. `beklenen_cikti` verilmişse ayrıca
    doğru değere dönüştürdüğü sınanır — ilk sürümde bu ikisi karıştırıldı
    ve "değişmemeli" vakası "doğru çıktı verdi" diye yakalanmış sayıldı.
    """
    beklenen = vaka.get("beklenen_cikti")
    if beklenen is not None and uretilen != beklenen:
        raise AssertionError(
            "%s: beklenen %r, üretilen %r" % (vaka["id"], beklenen, uretilen))
    return uretilen != vaka["teslim"]


def _calistir_sanitize_glossary(vaka):
    sonuc = ht.sanitize_glossary_for_turkish(
        {vaka["kaynak"]: vaka["teslim"]}, target_language="Turkish")
    return _onarim_sonucu(vaka, sonuc.get(vaka["kaynak"], ""))


def _calistir_tirnak_guard(vaka):
    kaynak_terim, hedef = vaka["teslim"].split("|", 1)
    kalan = ht.drop_quoted_work_title_terms(
        {kaynak_terim: hedef}, vaka["kaynak"])
    return kaynak_terim not in kalan          # düştüyse yakalandı


def _calistir_kisi_degil(vaka):
    return ht._is_not_a_person(vaka["teslim"])


def _calistir_kesinti(vaka):
    sonuc = gui._normalize_delivery_interruption_dashes(vaka["teslim"])
    if vaka.get("satir_korunur"):
        # Bu vaka için "yakalamak" = satır yapısını BOZMAK.
        return sonuc.count(chr(10)) != vaka["teslim"].count(chr(10))
    return _onarim_sonucu(vaka, sonuc)


def _calistir_literal_kacis(vaka):
    return _onarim_sonucu(
        vaka, gui._restore_source_linebreaks(vaka["teslim"], vaka["kaynak"]))


def _calistir_hizalama(vaka):
    """Tek cue'luk bir kayma bölgesini hizalama taramasına sorar."""
    bloklar = [("1", "00:00:01,000 --> 00:00:03,000", vaka["teslim"])]
    src_map = {"1": vaka["kaynak"]}
    seq = [(kimlik, gui._align_visible(metin))
           for kimlik, _ts, metin in bloklar]
    return bool(gui._content_shift_regions(seq, src_map))


CALISTIRICILAR = {
    "_missing_replica": _calistir_missing_replica,
    "sanitize_glossary_for_turkish": _calistir_sanitize_glossary,
    "drop_quoted_work_title_terms": _calistir_tirnak_guard,
    "_is_not_a_person": _calistir_kisi_degil,
    "_normalize_delivery_interruption_dashes": _calistir_kesinti,
    "_restore_source_linebreaks": _calistir_literal_kacis,
    "detect_alignment_issues": _calistir_hizalama,
}


class DeliveryRegressionCorpusTest(unittest.TestCase):

    def test_arsiv_bicimsel_olarak_saglam(self):
        vakalar = _vakalar()
        self.assertTrue(vakalar, "arşiv boş")
        kimlikler = [v["id"] for v in vakalar]
        self.assertEqual(len(kimlikler), len(set(kimlikler)),
                         "yinelenen vaka kimliği var")
        for vaka in vakalar:
            for alan in ("id", "dedektor", "bekleme", "teslim", "not",
                         "koken"):
                self.assertIn(alan, vaka, vaka.get("id"))
            self.assertIn(vaka["bekleme"],
                          ("yakala", "yakalama", "bilenen_kacak",
                           "bilinen_kacak"), vaka["id"])
            self.assertIn(vaka["dedektor"], CALISTIRICILAR, vaka["id"])
            self.assertTrue(str(vaka["not"]).strip(),
                            "%s: not boş — vaka nereden geldiğini "
                            "söylemeli" % vaka["id"])

    def test_her_dedektorun_iki_yonlu_orani(self):
        """Rapor üretir ve BEKLENTİYE uymayan vakayı hata sayar."""
        vakalar = _vakalar()
        isabet = defaultdict(lambda: [0, 0])       # [dogru, toplam]
        yanlis_alarm = defaultdict(lambda: [0, 0])
        basarisiz = []
        kacaklar = []
        for vaka in vakalar:
            calistir = CALISTIRICILAR[vaka["dedektor"]]
            try:
                sonuc = bool(calistir(vaka))
            except Exception as hata:               # pragma: no cover
                basarisiz.append("%s: çalıştırıcı patladı: %s"
                                 % (vaka["id"], hata))
                continue
            if vaka["bekleme"] == "yakala":
                isabet[vaka["dedektor"]][1] += 1
                if sonuc:
                    isabet[vaka["dedektor"]][0] += 1
                else:
                    basarisiz.append("%s: YAKALAMADI" % vaka["id"])
            elif vaka["bekleme"] == "yakalama":
                yanlis_alarm[vaka["dedektor"]][1] += 1
                if not sonuc:
                    yanlis_alarm[vaka["dedektor"]][0] += 1
                else:
                    basarisiz.append("%s: YANLIŞ ALARM" % vaka["id"])
            else:
                kacaklar.append(vaka["id"])
                if sonuc:
                    # Sevindirici: bilinen kaçak artık yakalanıyor.
                    basarisiz.append(
                        "%s: bilinen kaçak ARTIK YAKALANIYOR — vakayı "
                        "'yakala'ya çevirin ve sınırı düşürün" % vaka["id"])

        print()
        print("%-42s %9s %9s" % ("dedektör", "isabet", "yanlış alarm"))
        print("-" * 64)
        for ad in sorted(set(isabet) | set(yanlis_alarm)):
            d, t = isabet[ad]
            yd, yt = yanlis_alarm[ad]
            print("%-42s %4s/%-4s %5s/%-4s" % (
                ad, d, t or "-", yd, yt or "-"))
        print()
        print("bilinen kaçak: %d  (sınır %d)"
              % (len(kacaklar), BILINEN_KACAK_SINIRI))
        self.assertEqual(basarisiz, [], "; ".join(basarisiz))

    def test_bilinen_kacak_sayisi_artmadi(self):
        """Kaçırdığımız gerçek kusur sayısı BÜYÜMEMELİ."""
        kacak = [v for v in _vakalar() if v["bekleme"] == "bilinen_kacak"]
        self.assertLessEqual(
            len(kacak), BILINEN_KACAK_SINIRI,
            "bilinen kaçak arttı: %s" % [v["id"] for v in kacak])

    def test_her_dedektorun_IKI_YONU_de_var(self):
        """Tek yönlü ölçülen dedektör kabul edilmez.

        Bu deponun kuralı: bir tespit kuralı hem isabet hem yanlış alarm
        yönünden ölçülmeden eklenmez. Arşiv de o kuralı yansıtmalı.
        """
        yon = defaultdict(set)
        for vaka in _vakalar():
            if vaka["bekleme"] in ("yakala", "yakalama"):
                yon[vaka["dedektor"]].add(vaka["bekleme"])
        tek_yonlu = sorted(
            ad for ad, yonler in yon.items() if len(yonler) < 2)
        self.assertEqual(
            tek_yonlu, [],
            "yalnız tek yönden ölçülen dedektör(ler): %s" % tek_yonlu)


if __name__ == "__main__":
    unittest.main()
