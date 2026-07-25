"""
Smoke test: gerçek altyazı çevirisi yap, çıktıyı kontrol et.
Kullanım:  python _smoke_test.py
Çıktı:     smoke_test_tr.srt → smoke_test_tr_tr.srt (veya output klasörü)
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Proje kökünü PATH'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent))

import credential_store
import hybrid_translate as ht
from openai import OpenAI


def _get_schema():
    return None  # otomatik algılamayı kullan


def _get_glossary(_path):
    return {}


def main():
    # 1. API anahtarını al
    api_key = credential_store.load_key("openai")
    if not api_key:
        print("HATA: OpenAI API anahtarı bulunamadı.")
        print("Önce GUI'den kaydedin veya credential_store'a elle ekleyin.")
        return 1

    src_file = Path(__file__).parent / "smoke_test_tr.srt"
    if not src_file.exists():
        print(f"HATA: {src_file} bulunamadı.")
        return 1

    # 2. SRT'yi parse et
    import subtitle_translator_gui as gui
    cues = list(gui.parse_subtitle(str(src_file)))
    print(f"SRT okundu: {len(cues)} cue")

    # 3. build_requests ile çeviri isteklerini oluştur
    # (build_requests gui.py'de tanımlı)

    src = "English"
    tgt = "Turkish"
    model = "gpt-5.4-mini"
    profanity = "Orta"

    reqs, file_map = gui.build_requests(
        [str(src_file)], src, tgt, model,
        chunk_size=50,
        schema=_get_schema(),
        profanity=profanity,
        glossary=_get_glossary(str(src_file)),
        project_memory=None,
    )
    print(f"İstek oluşturuldu: {len(reqs)} chunk")

    # 4. OpenAI istemcisi
    client = OpenAI(api_key=api_key)

    # 5. Her chunk'ı çevir
    srt_blocks = {}
    for req in reqs:
        cid = req["custom_id"]
        print(f"  Çeviriliyor: {cid}...", end=" ", flush=True)
        try:
            resp = gui._safe_chat_create(client, **req["body"])
            raw = (resp.choices[0].message.content or "").strip()
            tmap = gui.parse_response(raw, file_map.get(cid, []))
            for idx, ts, text in file_map.get(cid, []):
                tr_text = tmap.get(str(idx), "[HATA]")
                srt_blocks[int(idx)] = (str(idx), ts, tr_text)
            print(f"OK ({len(file_map.get(cid, []))} satır)")
        except Exception as e:
            print(f"HATA: {e}")
            for idx, ts, text in file_map.get(cid, []):
                srt_blocks[int(idx)] = (str(idx), ts, "[HATA]")

    # 6. SRT olarak yaz
    out_path = src_file.with_name(src_file.stem + "_tr.srt")
    with open(out_path, "w", encoding="utf-8") as f:
        for key in sorted(srt_blocks):
            idx, ts, text = srt_blocks[key]
            text = text.strip()
            f.write(f"{idx}\n{ts}\n{text}\n\n")

    print(f"\nÇıktı: {out_path}  ({len(srt_blocks)} satır)")

    # 7. Kalite geçişleri (consistency sweep + SDH + line-break)
    print("\nKalite geçişleri uygulanıyor...")

    # Consistency sweep
    try:
        sorted_blocks = [srt_blocks[k] for k in sorted(srt_blocks)]
        _src_cues = cues
        sorted_blocks, _ = ht.consistency_sweep(_src_cues, sorted_blocks)
        srt_blocks = {int(b[0]): b for b in sorted_blocks}
        print("  Consistency sweep: OK")
    except Exception as e:
        print(f"  Consistency sweep: {e}")

    # SDH temizliği
    try:
        import sdh_cleaner
        sorted_blocks = [srt_blocks[k] for k in sorted(srt_blocks)]
        src_map = gui._src_map_from_cues(cues)
        sorted_blocks = sdh_cleaner.clean_sdh_blocks(
            sorted_blocks, src_map=src_map, source_driven=True)
        srt_blocks = {int(b[0]): b for b in sorted_blocks}
        print("  SDH temizliği: OK")
    except Exception as e:
        print(f"  SDH temizliği: {e}")

    # Tekrar yaz
    with open(out_path, "w", encoding="utf-8") as f:
        for key in sorted(srt_blocks):
            idx, ts, text = srt_blocks[key]
            text = text.strip()
            f.write(f"{idx}\n{ts}\n{text}\n\n")

    print(f"\nFinal çıktı: {out_path}")

    # 8. Kontrol listesi
    with open(out_path, encoding="utf-8") as f:
        output_text = f.read()

    print("\n=== SMOKE TEST KONTROLLERİ ===\n")

    checks = [
        ("coroner -> adli tabip", "adli tabip"),
        ("holiday party tatil/bayram", "tatil/bayram"),
        ("web korunuyor", "web"),
        ("wifi korunuyor", "wifi"),
        ("fax korunuyor", "fax"),
        ("SDH: ayak sesleri", "ayak sesleri"),
        ("SDH: silah sesi", "silah"),
        ("SDH: kapı çarpma", "kapı"),
        ("Konuşmacı: Doktor", "Doktor"),
        ("Konuşmacı: Hemşire", "Hemşire"),
        ("Konuşmacı: Kral", "Kral"),
        ("Konuşmacı: Kraliçe", "Kraliçe"),
        ("Konuşmacı: Hakim", "Hakim"),
        ("Profanity: bok (hafif)", "bok"),
        ("King/Queen/Judge konuşmacı", "Kral:"),
    ]

    all_ok = True
    for label, keyword in checks:
        found = keyword.lower() in output_text.lower()
        status = "+" if found else "-"
        if not found:
            all_ok = False
        print(f"  [{status}] {label} ({keyword})".encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

    if all_ok:
        print("\nTum kontroller gecti!".encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    else:
        print("\nBAZI KONTROLLER BASARISIZ!".encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

    # Ham ciktiyi da goster (ilk 2500 karakter)
    print("\n=== CEVIRI CIKTISI (ilk 2500 karakter) ===\n".encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    print(output_text[:2500].encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
