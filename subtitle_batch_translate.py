"""
Subtitle Batch Translator - OpenAI Batch API
%50 ucuz, yüksek rate limit, toplu işleme
Kullanım: python subtitle_batch_translate.py
"""

import json
import time
import glob
import hashlib
import re
import unicodedata
import tempfile
from pathlib import Path
from openai import OpenAI
from prompt_constants import meaning_readability_rule
from subtitle_formats import is_generated_subtitle_name

# === AYARLAR ===
SOURCE_LANG = "English"     # Kaynak dil
TARGET_LANG = "Turkish"     # Hedef dil
INPUT_FOLDER = "./subtitles"  # .srt dosyalarının bulunduğu klasör
OUTPUT_FOLDER = "./translated" # Çevrilmiş dosyaların kaydedileceği klasör
MODEL = "gpt-4.1-nano"       # 2.5M/gün bedava token havuzunda, en hızlı
# ===============


def resolve_standalone_provider(
        settings_file: Path | None = None, log_fn=None) -> tuple[str, str, str]:
    """Standalone batch script'leri için API anahtarı, base_url ve servis adını çözer.
    Döner: (api_key, base_url, service_name).
    """
    if settings_file is None:
        settings_file = Path(__file__).parent / ".gui_settings.json"

    main_custom = False
    custom_url = ""
    api_url = ""

    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            main_custom = bool(data.get("main_custom"))
            custom_url = (data.get("main_custom_url", "") or "").strip()
            api_url = (data.get("api_url", "") or "").strip()
        except Exception as e:
            if log_fn:
                log_fn(f"Ayar dosyası okunamadı, varsayılan sağlayıcı kullanılacak: {e}")

    if main_custom and custom_url:
        service_name = "main_custom"
        base_url = custom_url
    else:
        service_name = "openai"
        base_url = api_url

    api_key = None
    try:
        from credential_store import load_key
        api_key = load_key(service_name)
    except Exception as e:
        if log_fn:
            log_fn(f"Credential store okunamadı: {e}")

    if not api_key and service_name == "openai" and settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            api_key = (data.get("api_key", "") or "").strip()
        except Exception as e:
            if log_fn:
                log_fn(f"Eski API anahtarı ayarlardan okunamadı: {e}")

    if not api_key:
        if service_name == "main_custom":
            raise RuntimeError("Custom provider API anahtarı ('main_custom') credential store'da bulunamadı.")
        else:
            raise RuntimeError("OpenAI API anahtarı ('openai') credential store'da veya .gui_settings.json içinde bulunamadı.")

    return api_key, base_url, service_name


def _load_api_key(settings_file: Path | None = None) -> str:
    try:
        api_key, _, _ = resolve_standalone_provider(settings_file)
        return api_key
    except Exception:
        return ""


def _get_client(settings_file: Path | None = None):
    api_key, base_url, _ = resolve_standalone_provider(
        settings_file, log_fn=lambda message: print(f"[!] {message}"))
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)

def safe_parse_jsonl_line(line, log_fn=None):
    try:
        if not line or not line.strip():
            return None
        return json.loads(line)
    except Exception as e:
        if log_fn:
            log_fn(f"Corrupt JSONL line skipped: {e}")
        return None


def parse_srt(filepath):
    """SRT dosyasını parse eder, (index, timestamp, text) listesi döner."""
    blocks = []
    # Toleranslı okuma: cp1254 (Windows-Türkçe) altyazılar katı utf-8 ile çökerdi
    try:
        from subtitle_formats import read_subtitle_text
        content = read_subtitle_text(filepath).strip()
    except Exception:
        with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read().strip()

    # Kaba `split("\n\n")` + `len(lines) < 3` kontrolü CRLF, boşluk içeren ayraç
    # satırları ve metni boş cue'larda blokları sessizce düşürüyordu. Zaman satırını
    # ('-->') çıpa alarak ayrıştır: numarası eksik veya metni boş bloklar da korunur.
    content = re.sub(r"\r\n?", "\n", content)
    for raw_block in re.split(r"\n[ \t]*\n+", content):
        lines = raw_block.strip("\n").splitlines()
        ts_pos = next((pos for pos, line in enumerate(lines) if "-->" in line), None)
        if ts_pos is None:
            continue
        idx = lines[ts_pos - 1].strip() if ts_pos > 0 else str(len(blocks) + 1)
        timestamp = lines[ts_pos].strip()
        text = "\n".join(lines[ts_pos + 1:]).strip()
        blocks.append((idx, timestamp, text))
    return blocks


def _normalize_output_text(text: str, target_language: str = TARGET_LANG) -> str:
    text = unicodedata.normalize("NFC", str(text).strip()).replace("\t", " ")
    text = re.sub(r"\n{2,}", "\n", text)
    try:
        import sdh_cleaner
    except Exception:
        return text
    text = sdh_cleaner.normalize_sdh_descriptors(text)
    text = sdh_cleaner.normalize_speaker_labels(text)
    if str(target_language or "").strip().lower() in {"turkish", "türkçe", "turkce", "tr"}:
        text = sdh_cleaner.normalize_turkish_artifacts(text)
    return text


def build_standalone_system_prompt(
        source_language: str = SOURCE_LANG,
        target_language: str = TARGET_LANG) -> str:
    return (
        "You are an expert professional subtitle translator.\n"
        f"Translate the source subtitle from {source_language} to {target_language}.\n"
        f"{meaning_readability_rule(target_language)}\n"
        "- Return ONLY the translated subtitle text; no notes, labels, explanations, or quotes.\n"
        "- Preserve every name, number, fact, negation, question, and speaker ownership.\n"
        "- Preserve the input line count, dialogue dashes, and meaningful line breaks.\n"
        "- Keep formatting tags unchanged and never invent parenthetical explanations.\n"
        "- Use natural spoken language appropriate to the scene; avoid word-for-word translation."
    )


from app_state import (
    atomic_write_json, atomic_write_text, best_effort_cancel_remote_batch,
    is_safe_batch_id, state_dir, state_path,
)


_STANDALONE_RECOVERY_VERSION = 1
_STANDALONE_RECOVERY_FILE = "standalone_batch_recovery.json"


def standalone_recovery_path() -> Path:
    """Standalone batch'in çalışma dizininden bağımsız, tek güvenli durum yolu."""
    return state_path(__file__, _STANDALONE_RECOVERY_FILE)


def _source_file_sha256(filepath: str) -> str | None:
    """Eski batch sonucunun değiştirilmiş kaynakla birleştirilmesini engeller."""
    digest = hashlib.sha256()
    try:
        with open(filepath, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def save_standalone_recovery(batch_id: str, file_map: dict, *,
                             input_folder: str = INPUT_FOLDER,
                             output_folder: str = OUTPUT_FOLDER) -> Path:
    """Resume için batch ile gönderilen cue eşlemesini ve kaynak imzalarını saklar."""
    if not is_safe_batch_id(batch_id):
        raise ValueError("Güvenli olmayan batch kimliği kaydedilemez.")

    packed_map = {}
    source_hashes = {}
    for cid, entry in file_map.items():
        if not isinstance(cid, str) or not cid or not isinstance(entry, (list, tuple)) or len(entry) != 4:
            raise ValueError("Geçersiz standalone batch eşleme kaydı.")
        filepath, block_i, idx, timestamp = entry
        if not isinstance(filepath, str) or not isinstance(block_i, int):
            raise ValueError("Geçersiz standalone batch kaynak kaydı.")
        source_hash = _source_file_sha256(filepath)
        if not source_hash:
            raise ValueError(f"Kaynak dosya okunamadı: {filepath}")
        source_hashes[filepath] = source_hash
        packed_map[cid] = [filepath, block_i, str(idx), str(timestamp)]

    record = {
        "version": _STANDALONE_RECOVERY_VERSION,
        "batch_id": batch_id,
        "input_folder": str(input_folder),
        "output_folder": str(output_folder),
        "file_map": packed_map,
        "source_hashes": source_hashes,
    }
    path = standalone_recovery_path()
    atomic_write_json(path, record)
    return path


def load_standalone_recovery(path: Path | None = None) -> dict:
    """Sadece eksiksiz ve güvenli recovery kaydını kabul eder."""
    path = Path(path or standalone_recovery_path())
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Recovery kaydı okunamadı: {exc}") from exc

    if not isinstance(record, dict) or record.get("version") != _STANDALONE_RECOVERY_VERSION:
        raise RuntimeError("Recovery kaydı sürümü geçersiz.")
    batch_id = record.get("batch_id")
    raw_map = record.get("file_map")
    source_hashes = record.get("source_hashes")
    if not is_safe_batch_id(batch_id) or not isinstance(raw_map, dict) or not raw_map or not isinstance(source_hashes, dict):
        raise RuntimeError("Recovery kaydı eksik veya güvenli değil.")

    file_map = {}
    for cid, entry in raw_map.items():
        if (not isinstance(cid, str) or not cid or not isinstance(entry, list) or len(entry) != 4
                or not isinstance(entry[0], str) or not isinstance(entry[1], int)):
            raise RuntimeError("Recovery eşleme kaydı geçersiz.")
        file_map[cid] = (entry[0], entry[1], str(entry[2]), str(entry[3]))
    if set(source_hashes) != {entry[0] for entry in file_map.values()}:
        raise RuntimeError("Recovery kaynak imzaları eşleme kaydıyla uyuşmuyor.")
    if not all(isinstance(value, str) and len(value) == 64 for value in source_hashes.values()):
        raise RuntimeError("Recovery kaynak imzası geçersiz.")

    record["file_map"] = file_map
    return record


def clear_standalone_recovery(path: Path | None = None) -> None:
    Path(path or standalone_recovery_path()).unlink(missing_ok=True)


def write_srt(filepath, blocks, target_language: str = TARGET_LANG):
    """(index, timestamp, text) listesinden SRT dosyası yazar (atomik)."""
    lines = []
    for idx, timestamp, text in blocks:
        text = (_normalize_output_text(text) if target_language == TARGET_LANG
                else _normalize_output_text(text, target_language))
        lines.append(f"{idx}\n{timestamp}\n{text}\n\n")
    atomic_write_text(filepath, "".join(lines), encoding="utf-8")


def discover_source_srt_files(input_folder: str = INPUT_FOLDER,
                              output_folder: str = OUTPUT_FOLDER) -> list[str]:
    input_root = Path(input_folder).resolve()
    output_root = Path(output_folder).resolve()
    excluded_root = None
    try:
        output_root.relative_to(input_root)
        excluded_root = output_root
    except ValueError:
        pass
    found = set(glob.glob(str(input_root / "**" / "*.srt"), recursive=True))
    files = []
    for filepath in found:
        path = Path(filepath)
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if excluded_root is not None:
            try:
                resolved.relative_to(excluded_root)
                continue
            except ValueError:
                pass
        # GUI taramasıyla parite: programın ürettiği artifact'lar kaynak değildir
        # ('.tr.srt', '.ham.srt', '.partial.srt', gizli '.stage.srt') — aksi hâlde
        # sonraki koşu kendi çıktısını çevirir (denetim 2026-08-20, madde 16).
        if is_generated_subtitle_name(path.name):
            continue
        if any(part.casefold() in {"raporlar", "çıktı"}
               for part in resolved.parts[:-1]):
            continue
        files.append(str(path))
    return sorted(files)


def create_batch_requests(srt_files):
    """Tüm SRT dosyalarından JSONL batch request dosyası oluşturur."""
    requests = []
    file_map = {}  # custom_id -> (filepath, block_index)

    for filepath in srt_files:
        blocks = parse_srt(filepath)
        # 24 bitlik önek binlerce aynı adlı yolda çakışıyordu; çakışan iki
        # istekte file_map yalnız ikinci sahibi tutup çeviriyi YANLIŞ
        # dosyaya yazabiliyordu (denetim 2026-08-20, madde 24).
        _phash = hashlib.sha256(
            str(Path(filepath).resolve()).encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        for i, (idx, timestamp, text) in enumerate(blocks):
            custom_id = f"{Path(filepath).stem}_{_phash}__block{i}"
            if custom_id in file_map:
                raise ValueError(
                    f"custom_id çakışması: {custom_id} "
                    f"({file_map[custom_id][0]} ↔ {filepath})")
            file_map[custom_id] = (filepath, i, idx, timestamp)

            requests.append({
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": build_standalone_system_prompt()
                        },
                        {"role": "user", "content": text}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3
                }
            })

    return requests, file_map


def submit_batch(requests):
    """JSONL dosyasını OpenAI'a yükler ve batch başlatır."""
    state_dir(__file__).mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".jsonl", prefix="standalone_batch_",
            dir=state_dir(__file__), delete=False) as handle:
        jsonl_path = Path(handle.name)
        for req in requests:
            handle.write(json.dumps(req, ensure_ascii=False) + "\n")

    print(f"[+] {len(requests)} istek JSONL dosyasına yazıldı.")

    try:
        client = _get_client()
        with open(jsonl_path, "rb") as handle:
            uploaded = client.files.create(file=handle, purpose="batch")
    finally:
        jsonl_path.unlink(missing_ok=True)

    print(f"[+] Dosya yüklendi: {uploaded.id}")

    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )

    print(f"[+] Batch oluşturuldu: {batch.id}")
    print(f"    Durum: {batch.status}")
    return batch.id


def wait_for_batch(batch_id, poll_interval=60):
    """Batch tamamlanana kadar bekler."""
    client = _get_client()
    print(f"\n[~] Batch bekleniyor (her {poll_interval} saniyede kontrol)...")
    while True:
        batch = client.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(f"    Durum: {batch.status} | Tamamlanan: {counts.completed}/{counts.total} | Hatalı: {counts.failed}")

        if batch.status == "completed":
            print("[+] Batch tamamlandı!")
            return batch.output_file_id
        elif batch.status in ("failed", "expired", "cancelled"):
            print(f"[!] Batch başarısız: {batch.status}")
            return None

        time.sleep(poll_interval)


def process_results(output_file_id, file_map, srt_files, *,
                    input_folder: str | None = None, output_folder: str | None = None,
                    expected_source_hashes: dict | None = None):
    """Sonuçları indir ve SRT dosyalarını oluştur."""
    input_folder = input_folder or INPUT_FOLDER
    output_folder = output_folder or OUTPUT_FOLDER
    client = _get_client()
    content = client.files.content(output_file_id).text

    # Sonuçları custom_id'ye göre topla
    translations = {}
    seen_ids = set()
    duplicate_ids = set()
    for line in content.strip().splitlines():
        result = safe_parse_jsonl_line(line, log_fn=print)
        if not result:
            continue
        cid = result.get("custom_id")
        if not isinstance(cid, str) or not cid:
            print("[!] Geçersiz custom_id içeren batch sonucu atlandı.")
            continue
        if cid not in file_map:
            print(f"[!] Bilinmeyen custom_id sonucu atlandı: {cid}")
            continue
        if cid in seen_ids:
            print(f"[!] Yinelenen custom_id sonucu reddedildi: {cid}")
            duplicate_ids.add(cid)
            translations[cid] = None
            continue
        seen_ids.add(cid)
        if result.get("error"):
            print(f"[!] Hata ({cid}): {result['error']}")
            translations[cid] = None
        else:
            try:
                choice = result["response"]["body"]["choices"][0]
                if choice.get("finish_reason") in {"length", "content_filter"}:
                    translations[cid] = None
                    continue
                response_text = choice["message"]["content"]
                cleaned = (response_text.strip()
                           if isinstance(response_text, str) else None)
                # Boş ama HTTP-başarılı cevap ÇEVİRİ DEĞİLDİR: eskiden kaynak metin
                # finale yazılıp failed_ids boş kaldığı için recovery de siliniyordu
                # (denetim 2026-08-20, madde 25).
                translations[cid] = cleaned or None
            except (KeyError, TypeError, IndexError):
                translations[cid] = None

    # Her SRT dosyası için çevrilmiş blokları topla (dict — None slot crash'i önler)
    file_blocks = {}  # filepath -> {block_i: (idx, timestamp, text)}
    source_cache = {}
    source_mismatches = set()
    if expected_source_hashes is not None:
        expected_paths = set(expected_source_hashes)
        mapped_paths = {entry[0] for entry in file_map.values()}
        for filepath in mapped_paths - expected_paths:
            source_mismatches.add(filepath)
            print(f"[!] Kaynak imzası yok; eski batch sonucu yazılmadı: {filepath}")
        for filepath, expected_hash in expected_source_hashes.items():
            if _source_file_sha256(filepath) != expected_hash:
                source_mismatches.add(filepath)
                print(f"[!] Kaynak değişti; eski batch sonucu yazılmadı: {filepath}")
    for cid, (filepath, block_i, idx, timestamp) in file_map.items():
        if filepath in source_mismatches:
            continue
        if filepath not in source_cache:
            try:
                source_cache[filepath] = parse_srt(filepath)
            except Exception:
                source_cache[filepath] = []
        source_blocks = source_cache[filepath]
        source_text = source_blocks[block_i][2] if block_i < len(source_blocks) else ""
        if cid not in translations or translations[cid] is None or cid in duplicate_ids:
            # Eksik/boş/tekrarlı yanıt. Kaynağı SAF SDH ise cue zaten düşer;
            # gerçek diyalogsa kaynak metin YER TUTUCU olarak konur ama dosya
            # `file_failed` sayıldığı için final değil `.partial` olarak yazılır
            # ve recovery kaydı korunur (denetim 2026-08-20, madde 9 ve 25).
            try:
                import sdh_cleaner
                if source_text and sdh_cleaner.is_sdh_only(source_text):
                    continue
            except Exception:
                pass
            translated_text = source_text or "[ÇEVIRI HATASI]"
        else:
            translated_text = translations[cid]
        file_blocks.setdefault(filepath, {})[block_i] = (idx, timestamp, translated_text)

    # Dosyaları sıralı blok indeksine göre yaz
    written_files = 0
    skipped_files = len(source_mismatches)
    for filepath, blocks_dict in file_blocks.items():
        try:
            rel = Path(filepath).resolve().relative_to(Path(input_folder).resolve())
        except ValueError:
            print(f"[!] Kaynak dosya girdi klasörü dışında; çıktı yazılmadı: {filepath}")
            skipped_files += 1
            continue
        out_path = Path(output_folder) / rel
        try:
            if out_path.resolve() == Path(filepath).resolve():
                out_path = out_path.with_name(f"{out_path.stem}.tr{out_path.suffix}")
                print(f"[i] Kaynak dosya korunuyor; çıktı farklı ada yazılacak: {out_path}")
        except OSError:
            skipped_files += 1
            print(f"[!] Güvenli çıktı yolu çözümlenemedi; çıktı yazılmadı: {filepath}")
            continue
        file_failed = any(
            cid in duplicate_ids or cid not in translations or translations.get(cid) is None
            for cid, entry in file_map.items() if entry[0] == filepath
        )
        if file_failed:
            # Eksik cue'lar kaynak metniyle dolduruluyor; bu ÇEVİRİ DEĞİLDİR.
            # Böyle bir dosya final `.srt` olarak yazılırsa hem çevrilmemiş
            # satır teslim edilmiş olur hem de resume "final var" diye dosyayı
            # atlar ve kurtarma döngüsü hiç bitmez (denetim 2026-08-20, madde 9).
            if out_path.exists():
                skipped_files += 1
                print(f"[!] Kısmi batch sonucu mevcut finali ezmedi: {out_path}")
                continue
            out_path = out_path.with_name(
                f"{out_path.stem}.partial{out_path.suffix}")
            print(f"[!] Eksik cue var; kısmi sonuç ayrıldı: {out_path}")
        ordered = [blocks_dict[k] for k in sorted(blocks_dict)]
        write_srt(out_path, ordered, TARGET_LANG)
        print(f"[+] Kaydedildi: {out_path}")
        written_files += 1

    failed_ids = {cid for cid in file_map if cid not in translations or translations.get(cid) is None}
    failed_ids.update(duplicate_ids)
    return {
        "written_files": written_files,
        "skipped_files": skipped_files,
        "failed_ids": failed_ids,
        "source_mismatches": source_mismatches,
    }


def main():
    srt_files = discover_source_srt_files(INPUT_FOLDER, OUTPUT_FOLDER)

    if not srt_files:
        print(f"[!] '{INPUT_FOLDER}' klasöründe .srt dosyası bulunamadı!")
        return

    print(f"[+] {len(srt_files)} SRT dosyası bulundu:")
    for f in srt_files:
        print(f"    - {f}")

    print("\n[~] Batch istekleri hazırlanıyor...")
    requests, file_map = create_batch_requests(srt_files)
    print(f"    Toplam {len(requests)} altyazı bloğu")

    # Batch başlat
    batch_id = submit_batch(requests)

    # batch_id kaydet (crash olursa tekrar kullanmak için)
    try:
        recovery_path = save_standalone_recovery(batch_id, file_map)
    except Exception as exc:
        print(f"[!] Batch recovery kaydı yazılamadı: {exc}")
        try:
            best_effort_cancel_remote_batch(
                _get_client(), batch_id, log_fn=lambda message, *_: print(f"[!] {message}"))
        except Exception as cancel_exc:
            print(f"[!] Batch iptal denemesi başlatılamadı: {cancel_exc}")
        return
    print(f"\n[i] Batch recovery kaydı kaydedildi: {recovery_path}")
    print("[i] Script kapanırsa 'python resume_batch.py' ile devam edebilirsin.\n")

    # Tamamlanmasını bekle
    output_file_id = wait_for_batch(batch_id)

    if output_file_id:
        source_hashes = load_standalone_recovery(recovery_path)["source_hashes"]
        result = process_results(
            output_file_id, file_map, srt_files, expected_source_hashes=source_hashes)
        if result["failed_ids"] or result["source_mismatches"] or result["skipped_files"]:
            print("\n[!] Bazı sonuçlar yazılmadı veya hatalı; recovery kaydı korunuyor.")
            return
        clear_standalone_recovery(recovery_path)
        print("\n[✓] Tüm çeviriler tamamlandı!")
    else:
        print("[!] Batch başarısız oldu. OpenAI dashboard'unu kontrol et.")


if __name__ == "__main__":
    main()
