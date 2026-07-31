"""Yarım kalan standalone batch'i güvenli recovery kaydıyla sürdürür."""

from subtitle_batch_translate import (
    _load_api_key,
    clear_standalone_recovery,
    load_standalone_recovery,
    process_results,
    wait_for_batch,
)


def main():
    if not _load_api_key():
        import sys
        print("[!] Hata: API_KEY bulunamadı.")
        sys.exit(1)

    try:
        record = load_standalone_recovery()
    except RuntimeError as exc:
        print(f"[!] Güvenli recovery kaydı bulunamadı: {exc}")
        print("[i] Eski batch_id.txt ile yeniden eşleme yapılmaz; bu, eski sonucu değişmiş kaynağa yazabilir.")
        return

    batch_id = record["batch_id"]
    print(f"[+] Batch ID: {batch_id}")

    output_file_id = wait_for_batch(batch_id)
    if not output_file_id:
        return

    result = process_results(
        output_file_id,
        record["file_map"],
        list(record["source_hashes"]),
        input_folder=record["input_folder"],
        output_folder=record["output_folder"],
        expected_source_hashes=record["source_hashes"],
    )
    if result["failed_ids"] or result["source_mismatches"] or result["skipped_files"]:
        print("[!] Bazı sonuçlar yazılmadı veya hatalı; recovery kaydı korunuyor.")
        return
    clear_standalone_recovery()
    print("\n[✓] Tamamlandı!")


if __name__ == '__main__':
    main()
