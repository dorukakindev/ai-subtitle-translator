"""
Yarıda kalan batch'i devam ettirmek için.
batch_id.txt dosyası gerekli.
"""

import glob
from openai import OpenAI
from subtitle_batch_translate import (
    API_KEY, INPUT_FOLDER, create_batch_requests, wait_for_batch, process_results
)

client = OpenAI(api_key=API_KEY)

with open("batch_id.txt", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]
    if not lines:
        import sys
        print("[!] Hata: batch_id.txt boş.")
        sys.exit(1)
    batch_id = lines[-1]

print(f"[+] Batch ID: {batch_id}")

srt_files = glob.glob(f"{INPUT_FOLDER}/**/*.srt", recursive=True) + \
            glob.glob(f"{INPUT_FOLDER}/*.srt")
srt_files = list(set(srt_files))

_, file_map = create_batch_requests(srt_files)

output_file_id = wait_for_batch(batch_id)
if output_file_id:
    process_results(output_file_id, file_map, srt_files)
    print("\n[✓] Tamamlandı!")
