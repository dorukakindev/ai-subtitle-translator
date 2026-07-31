"""
Bozuk batch sonuçlarını düzelten tek seferlik tamir scripti.
Verilen fmap dosyalarındaki batch ID'leri ile OpenAI'dan çıktıyı yeniden
indirir ve düzeltilmiş parse mantığıyla SRT dosyalarını yeniden yazar.
"""
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from subtitle_batch_translate import _get_client
from app_state import atomic_write_text

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

def _try_extract(text: str):
    clean = text.strip()
    if clean.startswith("```"):
        clean = "\n".join(clean.split("\n")[1:]).rsplit("```", 1)[0].strip()

    try:
        return json.loads(clean)
    except Exception:
        pass

    s = clean.find('[')
    e = clean.rfind(']')
    if s != -1 and e > s:
        try:
            return json.loads(clean[s:e + 1])
        except Exception:
            pass

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
    items = _try_extract(raw)
    trans_map = {}
    if items and isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and "i" in item and isinstance(item.get("t"), str):
                trans_map[str(item["i"])] = item["t"]
        if trans_map:
            return trans_map
    print(f"  [UYARI] {cid}: JSON parse başarısız — ham: {raw[:80]!r}")
    return {}

def main():
    client = _get_client()
    total_fixed = 0
    total_hata  = 0

    for fmap_path in FMAP_FILES:
        fname = os.path.basename(fmap_path)
        batch_id = fname.replace("batch_fmap_", "").replace(".json", "")

        try:
            with open(fmap_path, encoding="utf-8") as f:
                fmap_data = json.load(f)
        except Exception:
            continue

        output_path = fmap_data.get("output_path") or ""
        raw_fmap    = fmap_data.get("fmap", {})
        if not output_path or not raw_fmap:
            print(f"  ! {fname}: output yolu/fmap eksik — atlanıyor")
            continue

        if Path(output_path).is_dir():
            print(f"  ! {fname}: output_path dosya değil; güvenlik için atlanıyor")
            continue

        print(f"\n{'='*60}")
        print(f"Batch  : {batch_id}")
        print(f"Çıktı  : {os.path.basename(output_path)}")
        print(f"Chunks : {len(raw_fmap)}")

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

        content = client.files.content(output_file_id).text

        srt_blocks = {}
        chunk_ok   = 0
        chunk_fail = 0
        seen_cids = set()

        for line in content.strip().splitlines():
            try:
                if not line or not line.strip():
                    continue
                res = json.loads(line)
            except Exception as e:
                print(f"  [UYARI] Corrupt JSONL line skipped: {e}")
                continue

            cid = res.get("custom_id")
            if not isinstance(cid, str) or not cid:
                print("  [UYARI] Geçersiz custom_id içeren sonuç atlandı")
                continue

            info = raw_fmap.get(cid, [])

            if not info:
                print(f"  [UYARI] {cid}: fmap eşleşmesi yok; sonuç hiçbir cue'ya yazılmadı")
                chunk_fail += 1
                continue

            if cid in seen_cids:
                print(f"  [UYARI] {cid}: yinelenen custom_id; ilgili cue'lar [HATA] olarak korundu")
                for entry in info:
                    idx, start, end = entry[0], entry[1], entry[2]
                    srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                    total_hata += 1
                chunk_fail += 1
                continue
            seen_cids.add(cid)

            if res.get("error"):
                err_msg = res.get("error", {})
                if err_msg:
                    print(f"  [HATA] {cid}: {err_msg.get('message','')}")
                for entry in info:
                    idx, start, end = entry[0], entry[1], entry[2]
                    srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                    total_hata += 1
                chunk_fail += 1
                continue

            raw = ""
            try:
                choices = res.get("response", {}).get("body", {}).get("choices", [])
                if choices and isinstance(choices, list):
                    first = choices[0]
                    if first.get("finish_reason") not in {"length", "content_filter"}:
                        content_value = first.get("message", {}).get("content", "")
                        raw = content_value.strip() if isinstance(content_value, str) else ""
            except Exception:
                raw = ""

            if not raw:
                print(f"  [UYARI] {cid}: yanıt metni alınamadı (eksik veya boş yanıt)")
                for entry in info:
                    idx, start, end = entry[0], entry[1], entry[2]
                    srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                    total_hata += 1
                chunk_fail += 1
                continue

            trans_map = parse_chunk(raw, info, cid)
            if not trans_map:
                for entry in info:
                    idx, start, end = entry[0], entry[1], entry[2]
                    srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                    total_hata += 1
                chunk_fail += 1
                continue
            chunk_ok += 1

            for entry in info:
                idx, start, end = entry[0], entry[1], entry[2]
                text = trans_map.get(str(idx), "[HATA]")
                if text == "[HATA]":
                    total_hata += 1
                srt_blocks[idx] = (str(idx), f"{start} --> {end}", text)

        for cid, info in raw_fmap.items():
            if cid in seen_cids:
                continue
            print(f"  [UYARI] {cid}: batch sonucunda hiç bulunamadı; cue'lar [HATA] olarak korundu")
            for entry in info:
                idx, start, end = entry[0], entry[1], entry[2]
                srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                total_hata += 1
            chunk_fail += 1

        if not srt_blocks:
            print(f"  [ATLA] Hiç blok yok.")
            continue

        lines = []
        for key in sorted(srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k))):
            idx, ts, text = srt_blocks[key]
            lines.append(f"{idx}\n{ts}\n{text}\n\n")
        atomic_write_text(output_path, "".join(lines), encoding="utf-8")

        count = len(srt_blocks)
        total_fixed += count
        print(f"  Yazıldı: {count} satır  ({chunk_ok} chunk OK, {chunk_fail} chunk FAIL)")
        print(f"  Dosya: {output_path}")

    print(f"\n{'='*60}")
    print(f"TAMAMLANDI — Toplam {total_fixed} satır yeniden yazıldı, {total_hata} [HATA] satır")

if __name__ == "__main__":
    main()
