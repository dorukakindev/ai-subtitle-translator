"""
Bozuk batch sonuçlarını düzelten tek seferlik tamir scripti.
Verilen fmap dosyalarındaki batch ID'leri ile OpenAI'dan çıktıyı yeniden
indirir ve düzeltilmiş parse mantığıyla SRT dosyalarını yeniden yazar.
"""
import json, os, sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from subtitle_batch_translate import _get_client, _source_file_sha256
from app_state import atomic_write_text

# Bilerek boş: kullanıcı açıp çalıştırdığında başka bir makinenin eski batch
# yollarına yazmaya çalışmamalı. Dosyalar komut satırından verilir.
FMAP_FILES = []

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
        expected_ids = {str(entry[0]) for entry in info if isinstance(entry, (list, tuple)) and entry}
        for item in items:
            if not (isinstance(item, dict) and "i" in item
                    and isinstance(item.get("t"), str) and item["t"].strip()):
                print(f"  [UYARI] {cid}: geÃ§ersiz veya boÅŸ cue yanÄ±tÄ± reddedildi")
                return {}
            item_id = str(item["i"])
            if item_id not in expected_ids or item_id in trans_map:
                print(f"  [UYARI] {cid}: geÃ§ersiz/yinelenen cue kimliÄŸi ({item_id}) reddedildi")
                return {}
            trans_map[item_id] = item["t"]
        if trans_map and set(trans_map) == expected_ids:
            return trans_map
        if trans_map:
            print(f"  [UYARI] {cid}: eksik cue kimliği bulunan yanıt reddedildi")
    print(f"  [UYARI] {cid}: JSON parse başarısız — ham: {raw[:80]!r}")
    return {}


def _valid_repair_entries(info) -> bool:
    return (
        isinstance(info, list) and bool(info) and
        all(isinstance(entry, (list, tuple)) and len(entry) >= 3 and
            str(entry[0]).strip() and str(entry[1]).strip() and str(entry[2]).strip()
            for entry in info)
    )


def _repair_map_has_unique_cue_ids(raw_fmap: dict) -> bool:
    cue_ids = set()
    for info in raw_fmap.values():
        for entry in info:
            cue_id = str(entry[0])
            if cue_id in cue_ids:
                return False
            cue_ids.add(cue_id)
    return True


def _backup_before_repair(output_path: Path) -> Path | None:
    """Eski teslimi, tamir yazÄ±mÄ± baÅŸarÄ±sÄ±z olursa geri dÃ¶nÃ¼lebilir tutar."""
    if not output_path.exists():
        return None
    backup = output_path.with_name(output_path.name + ".repair.bak")
    counter = 2
    while backup.exists():
        backup = output_path.with_name(output_path.name + f".repair.{counter}.bak")
        counter += 1
    shutil.copy2(output_path, backup)
    return backup

def main(fmap_files=None):
    client = _get_client()
    total_fixed = 0
    total_hata  = 0

    fmap_files = list(FMAP_FILES if fmap_files is None else fmap_files)
    if not fmap_files:
        print("Kullanım: python repair_batches.py <batch_fmap_*.json> [...]")
        return

    for fmap_path in fmap_files:
        fname = os.path.basename(fmap_path)
        batch_id = fname.replace("batch_fmap_", "").replace(".json", "")

        try:
            with open(fmap_path, encoding="utf-8") as f:
                fmap_data = json.load(f)
        except Exception as exc:
            print(f"  [HATA] {fname}: fmap okunamadÄ±; dokunulmadÄ±: {exc}")
            continue

        output_path = fmap_data.get("output_path") or ""
        raw_fmap    = fmap_data.get("fmap", {})
        source_path = fmap_data.get("source_path") or ""
        source_hash = fmap_data.get("source_hash") or ""
        if not output_path or not isinstance(raw_fmap, dict) or not raw_fmap:
            print(f"  ! {fname}: output yolu/fmap eksik — atlanıyor")
            continue

        source = Path(str(source_path))
        if (not isinstance(source_hash, str) or len(source_hash) != 64
                or not source.is_absolute() or _source_file_sha256(str(source)) != source_hash):
            print(f"  ! {fname}: kaynak imzası doğrulanamadı; dosyaya dokunulmadı")
            continue

        invalid_cids = [cid for cid, info in raw_fmap.items()
                        if not isinstance(cid, str) or not cid or not _valid_repair_entries(info)]
        if invalid_cids:
            print(f"  [HATA] {fname}: {len(invalid_cids)} geçersiz fmap kaydı var; dosyaya dokunulmadı")
            continue

        if not _repair_map_has_unique_cue_ids(raw_fmap):
            print(f"  [HATA] {fname}: fmap cue kimlikleri yineleniyor; dosyaya dokunulmadÄ±")
            continue

        output = Path(output_path)
        if output.is_dir() or output.resolve() == source.resolve():
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

        try:
            content = client.files.content(output_file_id).text
        except Exception as exc:
            print(f"  [HATA] Batch Ã§Ä±ktÄ±sÄ± indirilemedi; dokunulmadÄ±: {exc}")
            continue

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

        if chunk_fail or chunk_ok != len(raw_fmap):
            print(f"  [ATLA] {chunk_fail} chunk eksik veya bozuk; mevcut teslim korunuyor")
            continue

        if not srt_blocks:
            print(f"  [ATLA] Hiç blok yok.")
            continue

        lines = []
        for key in sorted(srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k))):
            idx, ts, text = srt_blocks[key]
            lines.append(f"{idx}\n{ts}\n{text}\n\n")
        try:
            backup = _backup_before_repair(output)
            atomic_write_text(output, "".join(lines), encoding="utf-8")
        except Exception as exc:
            print(f"  [HATA] Ã‡Ä±ktÄ± yazÄ±lamadÄ±; eski teslim korunuyor: {exc}")
            continue
        if backup:
            print(f"  Yedek : {backup}")

        count = len(srt_blocks)
        total_fixed += count
        print(f"  Yazıldı: {count} satır  ({chunk_ok} chunk OK, {chunk_fail} chunk FAIL)")
        print(f"  Dosya: {output_path}")

    print(f"\n{'='*60}")
    print(f"TAMAMLANDI — Toplam {total_fixed} satır yeniden yazıldı, {total_hata} [HATA] satır")

if __name__ == "__main__":
    main(sys.argv[1:])
