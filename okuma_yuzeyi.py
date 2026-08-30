# -*- coding: utf-8 -*-
"""İkidilli okuma yüzeyi — kaynak ve teslim yan yana, tek HTML dosyası.

NEDEN BU, BULGU PANELİ DEĞİL
Bu projede ölçüldü: teslimdeki anlamsal kusurların tarayıcıyla bulunma
oranı %1. Kalıntının neredeyse tamamı satır satır OKUYARAK bulundu — üç
dosyada 84 kalıntı, hiçbirini dedektör yakalamazdı. Dolayısıyla en yüksek
kaldıraçlı araç, bulguları süzen bir panel değil, kaynakla teslimi yan
yana okunur kılan bir yüzey. Bulgular kenarda küçük bir işaret olarak
durur; metin önde kalır.

HİZALAMA ZAMAN DAMGASIYLA
Cue numarası anahtar olarak kullanılamaz: teslim yeniden numaralandığında
tek bir silinmiş cue sonraki her satırı "değişmiş" gösterir (ölçülen vaka:
5.901 sahte fark, gerçek 1.309). Numara yalnız yedek anahtardır ve iki
taraf ayrıldığında İKİSİ de gösterilir — bu bilgidir, gürültü değil.

Çıktı tek dosyadır: dış kaynak yok, program açık olmadan okunur, başka
makineye taşınır, Ctrl+F ile aranır.
"""
from __future__ import annotations

import html
import io
import os
import re

_TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
                    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})")


def _ts_key(timestamp) -> str:
    """Zaman damgasını karşılaştırılabilir tek anahtara indirger."""
    match = _TS_RE.search(str(timestamp or ""))
    if not match:
        return ""
    return "%s|%s" % (match.group(1).replace(".", ","),
                      match.group(2).replace(".", ","))


def _ts_goster(timestamp) -> str:
    match = _TS_RE.search(str(timestamp or ""))
    return match.group(1) if match else str(timestamp or "")


def satirlari_esle(kaynak_cues, teslim_cues) -> list:
    """[(kaynak_cue, teslim_cue)] — zaman damgasıyla, numara yedekle.

    Eşleşmeyen taraf None kalır: kaynakta olup teslimde olmayan bir cue
    da, teslimde olup kaynakta olmayan bir cue da GÖRÜNÜR olmalı. Sessizce
    atlamak, tam da aranan kaybı gizler.
    """
    kaynak = list(kaynak_cues or ())
    teslim = list(teslim_cues or ())
    kaynak_ts = {}
    for cue in kaynak:
        anahtar = _ts_key(cue[1])
        if anahtar:
            kaynak_ts.setdefault(anahtar, []).append(cue)
    kaynak_no = {str(cue[0]): cue for cue in kaynak}

    kullanilan = set()
    satirlar = []
    for cue in teslim:
        anahtar = _ts_key(cue[1])
        eslesen = None
        havuz = kaynak_ts.get(anahtar) or []
        for aday in havuz:
            if id(aday) not in kullanilan:
                eslesen = aday
                break
        if eslesen is None:
            aday = kaynak_no.get(str(cue[0]))
            if aday is not None and id(aday) not in kullanilan:
                eslesen = aday
        if eslesen is not None:
            kullanilan.add(id(eslesen))
        satirlar.append((eslesen, cue))

    # Teslimde karşılığı bulunmayan kaynak cue'ları da göster.
    artakalan = [cue for cue in kaynak if id(cue) not in kullanilan]
    if artakalan:
        satirlar.extend((cue, None) for cue in artakalan)
    return satirlar


_STIL = """
:root{--bg:#fbfbfa;--fg:#1c1c1e;--fg2:#6b6b73;--cizgi:#e3e3e0;
--kaynak:#f2f2ef;--isaret:#b8863b;--vurgu:#2f6f9f}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#e6e6e9;
--fg2:#96969e;--cizgi:#2b2b31;--kaynak:#1b1b1e;--isaret:#c99a4b;
--vurgu:#6ea8d8}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 "Segoe UI",system-ui,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid
var(--cizgi);padding:14px 22px;z-index:2}
h1{margin:0;font-size:16px;font-weight:600}
.ozet{color:var(--fg2);font-size:12.5px;margin-top:3px}
.ozet b{color:var(--fg);font-weight:600}
table{width:100%;border-collapse:collapse}
tr{border-bottom:1px solid var(--cizgi)}
tr:target{background:color-mix(in srgb,var(--vurgu) 14%,transparent)}
td{padding:9px 14px;vertical-align:top}
.no{width:96px;color:var(--fg2);font:11.5px/1.5 Consolas,monospace;
white-space:nowrap;text-align:right}
.no .ayrik{color:var(--isaret)}
.kaynak{width:44%;background:var(--kaynak);color:var(--fg2)}
.teslim{width:44%}
.isaret{width:26px;text-align:center;color:var(--isaret);
font-size:12px;cursor:help;user-select:none}
.eksik{color:var(--isaret);font-style:italic}
mark{background:color-mix(in srgb,var(--isaret) 26%,transparent);
color:inherit}
footer{padding:22px;color:var(--fg2);font-size:12px}
"""

_JS = """
(function(){
 var m=[].slice.call(document.querySelectorAll('tr[data-bulgu]')),i=-1;
 function git(a){if(!m.length)return;i=(i+a+m.length)%m.length;
  m[i].scrollIntoView({block:'center'});location.hash=m[i].id;}
 document.addEventListener('keydown',function(e){
  if(e.target.tagName==='INPUT')return;
  if(e.key==='n'){git(1);e.preventDefault();}
  if(e.key==='p'){git(-1);e.preventDefault();}});
})();
"""


def html_uret(baslik: str, kaynak_cues, teslim_cues,
              bulgular: dict | None = None) -> str:
    """İkidilli okuma sayfası. `bulgular`: {teslim_cue_id: "sebep"}."""
    bulgular = {str(k): str(v) for k, v in (bulgular or {}).items()}
    satirlar = satirlari_esle(kaynak_cues, teslim_cues)

    govde = []
    isaretli = 0
    eksik = 0
    for kaynak, teslim in satirlar:
        teslim_no = str(teslim[0]) if teslim else ""
        sebep = bulgular.get(teslim_no, "")
        if sebep:
            isaretli += 1
        if kaynak is None or teslim is None:
            eksik += 1

        kaynak_no = str(kaynak[0]) if kaynak else ""
        numara = html.escape(teslim_no or kaynak_no)
        if kaynak_no and teslim_no and kaynak_no != teslim_no:
            # İki taraf ayrıldı: ikisini de göster, gizleme.
            numara = '%s<span class="ayrik"> ⇠%s</span>' % (
                html.escape(teslim_no), html.escape(kaynak_no))
        zaman = html.escape(_ts_goster((teslim or kaynak)[1]))

        def _metin(cue, sinif):
            if cue is None:
                return '<td class="%s eksik">— yok —</td>' % sinif
            return '<td class="%s">%s</td>' % (
                sinif, html.escape(str(cue[2] or "")).replace("\n", "<br>"))

        govde.append(
            '<tr id="c%s"%s>'
            '<td class="no">%s<br>%s</td>%s'
            '<td class="isaret" title="%s">%s</td>%s</tr>'
            % (html.escape(teslim_no or kaynak_no),
               ' data-bulgu="1"' if sebep else "",
               numara, zaman,
               _metin(kaynak, "kaynak"),
               html.escape(sebep), "◆" if sebep else "",
               _metin(teslim, "teslim")))

    ozet = ("<b>%d</b> cue · <b>%d</b> işaretli · <b>%d</b> tek taraflı"
            % (len(satirlar), isaretli, eksik))
    return (
        "<!doctype html><html lang=\"tr\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,"
        "initial-scale=1\"><title>%s</title><style>%s</style>"
        "<header><h1>%s</h1><div class=\"ozet\">%s &nbsp;·&nbsp; "
        "sonraki işaret <kbd>n</kbd>, önceki <kbd>p</kbd></div></header>"
        "<table>%s</table>"
        "<footer>Kaynak ve teslim ZAMAN DAMGASIYLA hizalandı; numaralar "
        "ayrıldığında ikisi de yazılır (⇠ kaynak).</footer>"
        "<script>%s</script></html>"
        % (html.escape(baslik), _STIL, html.escape(baslik), ozet,
           "".join(govde), _JS))


def yaz(hedef_yol, baslik: str, kaynak_cues, teslim_cues,
        bulgular: dict | None = None) -> str:
    """Sayfayı diske yazar ve yolunu döner."""
    icerik = html_uret(baslik, kaynak_cues, teslim_cues, bulgular)
    os.makedirs(os.path.dirname(str(hedef_yol)) or ".", exist_ok=True)
    with io.open(hedef_yol, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(icerik)
    return str(hedef_yol)
