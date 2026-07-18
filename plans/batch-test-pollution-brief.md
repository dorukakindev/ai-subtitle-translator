# Brief: "Yarım kalan batch" hayalet dialog'u — test kirliliği kök nedeni (Sonnet 5)

Hazırlayan: **Opus 4.8** (kullanıcı ekran görüntüsü + kök-neden doğrulaması, 2026-07-10).
Protokol: Opus teşhis + brief, Sonnet uygular. Kullanıcı hiç batch kullanmadığı hâlde her
açılışta "Yarım Kalan Batch'ler Bulundu → `batch_test_atomic`" dialog'u görüyordu.

## Kök neden (kesin, tekrarlanabilir)
`ht.submit_batch` proje köküne HEM `batch_fmap_<id>.json` HEM `batch_id.txt` yazıyor
([hybrid_translate.py:7144](hybrid_translate.py:7144)). Test
[tests/test_deep_bugfix_round2.py:167](tests/test_deep_bugfix_round2.py:167)
`test_submit_batch_fmap_atomic`, `ht.submit_batch(...)`'i gerçek proje dizinine karşı çağırıyor;
**fmap dosyasını temizliyor (satır 179-180) ama `batch_id.txt`'yi temizlemiyor**. Sonuç: proje
kökünde `batch_test_atomic` içeren bir `batch_id.txt` kalıyor, uygulama açılışında `_resume_batches`
onu bulup dialog'u gösteriyor. Doğrulama: bu testi tek başına çalıştırınca `batch_id.txt`
YENİDEN oluşuyor — yani her test paketi koşusu kirliliği geri getiriyor.

**Anlık temizlik ZATEN YAPILDI** (Opus, operasyonel): takılı `batch_id.txt` kaldırıldı
(scratchpad'e yedeklendi), başka batch artefaktı yoktu. Dialog şu an çıkmıyor. Bu brief
TEKRARI önlemek içindir.

## GÖREV A (zorunlu) — testi kendinden sonra temizlet + gerçek dosyayı koru
[tests/test_deep_bugfix_round2.py:167-180](tests/test_deep_bugfix_round2.py:167) mevcut:
```python
    def test_submit_batch_fmap_atomic(self):
        fake_client = MagicMock()
        fake_client.files.create.return_value.id = "file_abc"
        fake_client.batches.create.return_value.id = "batch_test_atomic"
        requests = [{"custom_id": "1", "body": {"messages": [{"role": "user", "content": "test"}]}}]
        file_map = {"1": [("0", "00:00:01", "00:00:04")]}
        with patch("openai.OpenAI", return_value=fake_client):
            bid = ht.submit_batch("dummy_key", requests, file_map=file_map)
        self.assertEqual(bid, "batch_test_atomic")
        fmap_path = Path(__file__).parent.parent / f"batch_fmap_{bid}.json"
        self.assertTrue(fmap_path.exists())
        self.assertFalse(fmap_path.with_suffix(".json.tmp").exists())
        if fmap_path.exists():
            fmap_path.unlink()
```
Şununla değiştir — çalıştırmadan önce mevcut gerçek `batch_id.txt`'yi yedekle, testten sonra
HEM fmap HEM batch_id.txt'yi temizle, sonra gerçek dosyayı geri yükle (bir kullanıcının gerçek
bekleyen batch'i test paketi koştuğunda YOK OLMASIN):
```python
    def test_submit_batch_fmap_atomic(self):
        fake_client = MagicMock()
        fake_client.files.create.return_value.id = "file_abc"
        fake_client.batches.create.return_value.id = "batch_test_atomic"
        requests = [{"custom_id": "1", "body": {"messages": [{"role": "user", "content": "test"}]}}]
        file_map = {"1": [("0", "00:00:01", "00:00:04")]}
        root = Path(ht.__file__).parent
        bid_path = root / "batch_id.txt"
        # submit_batch gerçek proje köküne yazıyor — varsa kullanıcının gerçek
        # batch_id.txt'sini yedekle, testten sonra geri yükle.
        _saved = bid_path.read_text(encoding="utf-8") if bid_path.exists() else None
        fmap_path = None
        try:
            with patch("openai.OpenAI", return_value=fake_client):
                bid = ht.submit_batch("dummy_key", requests, file_map=file_map)
            self.assertEqual(bid, "batch_test_atomic")
            fmap_path = root / f"batch_fmap_{bid}.json"
            self.assertTrue(fmap_path.exists())
            self.assertFalse(fmap_path.with_suffix(".json.tmp").exists())
        finally:
            if fmap_path is not None:
                fmap_path.unlink(missing_ok=True)
            if _saved is not None:
                bid_path.write_text(_saved, encoding="utf-8")
            else:
                bid_path.unlink(missing_ok=True)
```
(NOT: `fmap_path` eski kodda `__file__.parent.parent` idi = proje kökü; `ht.__file__`.parent de
proje kökü — aynı yer, ama `submit_batch`'in gerçekte yazdığı yerle [`Path(__file__).parent`
= ht modül dizini] birebir aynı olması için `ht.__file__` bazlı kök kullanıldı.)

## GÖREV B (ikincil sağlamlaştırma) — round11 testleri de gerçek dosyayı ezmesin
[tests/test_bugfixes_round11.py:23-55](tests/test_bugfixes_round11.py:23) `_clear_batch_recovery`
testleri `finally`'de temizliyor (iyi) AMA teste girerken gerçek `batch_id.txt`'yi
`write_text` ile EZİYOR ve sonda koşulsuz `unlink` ediyor → kullanıcının gerçek bekleyen
batch'i, test paketi koşarsa yok olur. Aynı yedekle-geri-yükle kalıbını uygula: her iki testte
(`test_removes_fmap_and_prunes_batch_id_txt`, `test_deletes_batch_id_txt_when_all_cleared`)
başta `_saved = bidp.read_text() if bidp.exists() else None`, `finally`'de koşulsuz
`bidp.unlink(missing_ok=True)` yerine `_saved` varsa geri yaz / yoksa sil.

## Doğrulama
1. `python -m unittest tests.test_deep_bugfix_round2 tests.test_bugfixes_round11 -v` → yeşil.
2. **Kirlilik testi:** yukarıdaki komuttan SONRA proje kökünde `batch_id.txt` OLMAMALI:
   `ls batch_id.txt` → "No such file or directory". (Şu an temiz; fix sonrası tam paket
   koşusu da temiz bırakmalı.)
3. Tam paket + smoke.
4. Elle: `python -m unittest discover -s tests` bitince `ls batch_id.txt batch_fmap_*.json`
   → hiçbiri kalmamalı.

## Kod-gözlemi (uygulama YOK — ayrı tur adayı)
Asıl kırılganlık: `submit_batch` / `_clear_batch_recovery` batch artefaktlarını sabit
`Path(__file__).parent`'a yazıyor, yönlendirilemiyor — bu yüzden onları test eden her test
gerçek kurulumu kirletmek zorunda. Uzun vade: artefakt dizinini enjekte edilebilir yap
(parametre/env), böylece testler izole tmp dizine yazar. Bu turda kapsam dışı.
