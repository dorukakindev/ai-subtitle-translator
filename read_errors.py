import sys
sys.path.insert(0, '.')
from credential_store import load_key
from openai import OpenAI

key = load_key('openai')
if not key:
    print("API key not found")
    sys.exit(1)

client = OpenAI(api_key=key)
bid = "batch_6a28f4df23b0819092d2c2470d576d31"

try:
    batch = client.batches.retrieve(bid)
    print(f"Batch: {bid}, Status: {batch.status}")
    if batch.error_file_id:
        content = client.files.content(batch.error_file_id).text
        with open("logs/batch_errors.txt", "w", encoding="utf-8") as f:
            f.write(content)
        print("Successfully wrote errors to logs/batch_errors.txt")
    else:
        print("No error file found for this batch")
except Exception as e:
    print(f"Error: {e}")
