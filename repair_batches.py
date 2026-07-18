"""
Bozuk batch sonuçlarını düzelten tek seferlik tamir scripti.
Verilen fmap dosyalarındaki batch ID'leri ile OpenAI'dan çıktıyı yeniden
indirir ve düzeltilmiş parse mantığıyla SRT dosyalarını yeniden yazar.
"""
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── Ayarlar ──────────────────────────────────────────────────────────────────
# Önce keyring/credential_store'dan dene (migrate_from_settings sonrası düz JSON'da olmayabilir)
def _load_api_key() -> str:
    try:
        from credential_store import load_key
        key = load_key("openai")
        if key:
            return key
    except Exception:
        pass
    # Fallback: .gui_settings.json
    SETTINGS_FILE = Path(__file__).parent / ".gui_settings.json"
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["api_key"]

API_KEY = _load_api_key()

FMAP_FILES = [
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea30a7134c8190aac14a89f717393f.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea305f1ee88190820652f31c57f030.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea30134138819097685064c4416517.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea2ef96dec8190adca0e4f0dd227ff.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea2ebc2ac88190960bdc16d532d4a4.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea31a2672881909dd84171e9cdd78c.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea316903e48190aa49f7713fed12bb.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea3124ce9c819097ef2ace933c4717.json",
    r"C:\Users\T\Downloads\Batch\batch_fmap_batch_69ea30e87c848190aebd25e86a6d4c7b.json",
]

# ── Sağlam JSON çıkarma (aynı mantık hybrid_translate.py'daki fix ile) ───────
def _try_extract(text: str):
    """JSON array'i prose ön-metinden, markdown fence'ten veya zarftan çıkar."""
    # Markdown fence soy
    clean = text.strip()
    if clean.startswith("```"):
        clean = "\n".join(clean.split("\n")[1:]).rsplit("```", 1)[0].strip()

    # Direkt parse
    try:
        return json.loads(clean)
    except Exception:
        pass

    # İlk [ ... ] bloğunu bul
    s = clean.find('[')
    e = clean.rfind(']')
    if s != -1 and e > s:
        try:
            return json.loads(clean[s:e + 1])
        except Exception:
            pass

    # {"tr": [...]} zarfı
    s2 = clean.find('{')
    e2 = clean.rfind('}')
    if s2 != -1 and e2 > s2:
        try:
            obj = json.loads(clean[s2:e2 + 1])
            if isinstance(obj, dict) and isinstance(obj.get("tr"), list):
                return obj["tr"]
        except Exception:
            pass

    return None


def parse_chunk(raw: str, info: list, cid: str) -> dict:
    """chunk_info: [(idx, start_ts, end_ts), ...]  → {str(idx): translated_text}"""
    items = _try_extract(raw)
    trans_map = {}
    if items and isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and "i" in item and "t" in item:
                trans_map[str(item["i"])] = item["t"]
        if trans_map:
            return trans_map
        # Liste var ama dict değil (nadiren plain string listesi)
    # Tamamen başarısız
    print(f"  [UYARI] {cid}: JSON parse başarısız — ham: {raw[:80]!r}")
    return {}


# ── Ana döngü ─────────────────────────────────────────────────────────────────
from openai import OpenAI
client = OpenAI(api_key=API_KEY)

total_fixed = 0
total_hata  = 0

for fmap_path in FMAP_FILES:
    fname = os.path.basename(fmap_path)
    batch_id = fname.replace("batch_fmap_", "").replace(".json", "")

    with open(fmap_path, encoding="utf-8") as f:
        fmap_data = json.load(f)

    # GUI düz batch'lerde "output_dir", hybrid'de "output_path" yazıyor — ikisini de kabul et
    # (eskiden sabit ["output_path"] erişimi düz batch fmap'lerinde KeyError ile çökerdi)
    output_path = fmap_data.get("output_path") or fmap_data.get("output_dir") or ""
    raw_fmap    = fmap_data.get("fmap", {})   # {cid: [[idx, start, end], ...]}
    if not output_path or not raw_fmap:
        print(f"  ! {fname}: output yolu/fmap eksik — atlanıyor")
        continue

    print(f"\n{'='*60}")
    print(f"Batch  : {batch_id}")
    print(f"Çıktı  : {os.path.basename(output_path)}")
    print(f"Chunks : {len(raw_fmap)}")

    # Batch durumunu sorgula
    try:
        batch = client.batches.retrieve(batch_id)
    except Exception as e:
        print(f"  [HATA] Batch sorgulanamadı: {e}")
        continue

    print(f"Durum  : {batch.status}")
    if batch.status != "completed":
        print(f"  [ATLA] Batch henüz tamamlanmamış veya hatalı.")
        continue

    output_file_id = batch.output_file_id
    if not output_file_id:
        print(f"  [HATA] output_file_id yok.")
        continue

    print(f"Output file: {output_file_id}")

    # Sonuç JSONL'ı indir
    content = client.files.content(output_file_id).text

    srt_blocks = {}
    chunk_ok   = 0
    chunk_fail = 0

    for line in content.strip().splitlines():
        res = json.loads(line)
        cid = res["custom_id"]
        info = raw_fmap.get(cid, [])

        if res.get("error") or not info:
            err_msg = res.get("error", {})
            if err_msg:
                print(f"  [HATA] {cid}: {err_msg.get('message','')}")
            for entry in info:
                idx, start, end = entry[0], entry[1], entry[2]
                srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                total_hata += 1
            chunk_fail += 1
            continue

        body = res["response"]["body"]
        raw  = body["choices"][0]["message"]["content"].strip()

        if not raw:
            print(f"  [UYARI] {cid}: boş yanıt")
            for entry in info:
                idx, start, end = entry[0], entry[1], entry[2]
                srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                total_hata += 1
            chunk_fail += 1
            continue

        trans_map = parse_chunk(raw, info, cid)
        chunk_ok  += 1

        for entry in info:
            idx, start, end = entry[0], entry[1], entry[2]
            text = trans_map.get(str(idx), "[HATA]")
            if text == "[HATA]":
                total_hata += 1
            srt_blocks[idx] = (str(idx), f"{start} --> {end}", text)

    if not srt_blocks:
        print(f"  [ATLA] Hiç blok yok.")
        continue

    # SRT yaz
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for key in sorted(srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k))):
            idx, ts, text = srt_blocks[key]
            f.write(f"{idx}\n{ts}\n{text}\n\n")

    count = len(srt_blocks)
    total_fixed += count
    print(f"  Yazıldı: {count} satır  ({chunk_ok} chunk OK, {chunk_fail} chunk FAIL)")
    print(f"  Dosya: {output_path}")

print(f"\n{'='*60}")
print(f"TAMAMLANDI — Toplam {total_fixed} satır yeniden yazıldı, {total_hata} [HATA] satır")
