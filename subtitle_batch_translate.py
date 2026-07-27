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
from pathlib import Path
from openai import OpenAI
from prompt_constants import meaning_readability_rule

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

    for block in content.split("\n\n"):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        idx = lines[0].strip()
        timestamp = lines[1].strip()
        text = "\n".join(lines[2:]).strip()
        blocks.append((idx, timestamp, text))
    return blocks


def _normalize_output_text(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text).strip()).replace("\t", " ")
    text = re.sub(r"\n{2,}", "\n", text)
    try:
        import sdh_cleaner
    except Exception:
        return text
    text = sdh_cleaner.normalize_sdh_descriptors(text)
    text = sdh_cleaner.normalize_speaker_labels(text)
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


from app_state import atomic_write_text, state_path


def write_srt(filepath, blocks):
    """(index, timestamp, text) listesinden SRT dosyası yazar (atomik)."""
    lines = []
    for idx, timestamp, text in blocks:
        text = _normalize_output_text(text)
        lines.append(f"{idx}\n{timestamp}\n{text}\n\n")
    atomic_write_text(filepath, "".join(lines), encoding="utf-8")


def create_batch_requests(srt_files):
    """Tüm SRT dosyalarından JSONL batch request dosyası oluşturur."""
    requests = []
    file_map = {}  # custom_id -> (filepath, block_index)

    for filepath in srt_files:
        blocks = parse_srt(filepath)
        _phash = hashlib.md5(filepath.encode("utf-8", errors="replace")).hexdigest()[:6]
        for i, (idx, timestamp, text) in enumerate(blocks):
            custom_id = f"{Path(filepath).stem}_{_phash}__block{i}"
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
    jsonl_path = "batch_input.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    print(f"[+] {len(requests)} istek JSONL dosyasına yazıldı.")

    client = _get_client()
    with open(jsonl_path, "rb") as f:
        uploaded = client.files.create(file=f, purpose="batch")

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


def process_results(output_file_id, file_map, srt_files):
    """Sonuçları indir ve SRT dosyalarını oluştur."""
    client = _get_client()
    content = client.files.content(output_file_id).text

    # Sonuçları custom_id'ye göre topla
    translations = {}
    for line in content.strip().splitlines():
        result = safe_parse_jsonl_line(line, log_fn=print)
        if not result:
            continue
        cid = result.get("custom_id")
        if not cid:
            continue
        if result.get("error"):
            print(f"[!] Hata ({cid}): {result['error']}")
            translations[cid] = None
        else:
            try:
                translations[cid] = result["response"]["body"]["choices"][0]["message"]["content"].strip()
            except (KeyError, TypeError, IndexError):
                translations[cid] = None

    # Her SRT dosyası için çevrilmiş blokları topla (dict — None slot crash'i önler)
    file_blocks = {}  # filepath -> {block_i: (idx, timestamp, text)}
    source_cache = {}
    for cid, (filepath, block_i, idx, timestamp) in file_map.items():
        if filepath not in source_cache:
            try:
                source_cache[filepath] = parse_srt(filepath)
            except Exception:
                source_cache[filepath] = []
        source_blocks = source_cache[filepath]
        source_text = source_blocks[block_i][2] if block_i < len(source_blocks) else ""
        if cid not in translations or translations[cid] is None:
            translated_text = "[ÇEVIRI HATASI]"
        elif translations[cid]:
            translated_text = translations[cid]
        else:
            try:
                import sdh_cleaner
                if source_text and sdh_cleaner.is_sdh_only(source_text):
                    continue
            except Exception:
                pass
            translated_text = "[ÇEVIRI HATASI]"
        file_blocks.setdefault(filepath, {})[block_i] = (idx, timestamp, translated_text)

    # Dosyaları sıralı blok indeksine göre yaz
    for filepath, blocks_dict in file_blocks.items():
        rel = Path(filepath).relative_to(INPUT_FOLDER)
        out_path = Path(OUTPUT_FOLDER) / rel
        ordered = [blocks_dict[k] for k in sorted(blocks_dict)]
        write_srt(out_path, ordered)
        print(f"[+] Kaydedildi: {out_path}")


def main():
    srt_files = glob.glob(f"{INPUT_FOLDER}/**/*.srt", recursive=True) + \
                glob.glob(f"{INPUT_FOLDER}/*.srt")
    srt_files = list(set(srt_files))

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
    with open("batch_id.txt", "w", encoding="utf-8") as f:
        f.write(batch_id)
    print("\n[i] Batch ID kaydedildi: batch_id.txt")
    print("[i] Script kapanırsa 'python resume_batch.py' ile devam edebilirsin.\n")

    # Tamamlanmasını bekle
    output_file_id = wait_for_batch(batch_id)

    if output_file_id:
        process_results(output_file_id, file_map, srt_files)
        print("\n[✓] Tüm çeviriler tamamlandı!")
    else:
        print("[!] Batch başarısız oldu. OpenAI dashboard'unu kontrol et.")


if __name__ == "__main__":
    main()
