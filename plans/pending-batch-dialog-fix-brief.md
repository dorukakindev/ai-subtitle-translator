# Brief: "Yarım Kalan Batch" dialog'u her açılışta çıkıyor + "Sil" kalıcı olmuyor (Sonnet 5)

Hazırlayan: **Opus 4.8** (kök-neden analizi + disk durumu doğrulaması, 2026-07-10).
Protokol: Opus karar verir + brief yazar, Sonnet uygular.

## Semptom (kullanıcı)
"Her başlattığımda yarım kalan batch varmış gibi bildirim geliyor, 'Sil' diyorum ama her
seferinde geliyor. Batch kullanmıyorum, anında (sync) çeviri kullanıyorum, yine de geliyor."

## Kök-neden analizi (doğrulandı)
1. **Dialog yalnız `batch_id.txt` varlığına bakar** (`_check_pending_batches`, sat. 3919-3921).
   Kullanıcının akışı **sync+hybrid** (Yardımcı Analiz açık, batch DEĞİL). batch_id.txt'yi
   yazan TEK yerler `submit_batch` (hybrid_translate.py:6930, mod="a" append) ve `_run_batch`
   (gui 10217/10234) — **ikisi de yalnız BATCH modunda**. Yani dosya, geçmişteki bir batch
   denemesinden kalma **bayat** bir dosya; sync akışı onu asla yaratmaz/güncellemez.
2. **"Sil" neden kalıcı olmuyor:** `_show_pending_batches_dialog`'un pencere-X (kapat) davranışı
   yok — X'le kapatınca sadece örtük `destroy()` olur, batch_id.txt DOKUNULMAZ → sonraki
   açılışta AYNEN tekrar çıkar. Ayrıca "Sil" yalnız kutu İŞARETLİYKEN çalışır; kullanıcı
   kutuları kaldırıp (sezgisel "bunları istemiyorum") Sil'e basarsa "Seçim yok" uyarısı çıkar
   ve HİÇBİR ŞEY silinmez.
   **Kanıt:** Diskte 10-29 Haziran tarihli **13 orphan `batch_fmap_*.json`** (479 KB) vardı —
   hiçbiri hiç temizlenmemiş. Bu, checked-Sil yolunun (`_clear_batch_recovery`) bu batch'ler
   için HİÇ başarıyla çalışmadığını kanıtlıyor (kullanıcı hep X'le kapatmış).
3. **Bunlar zaten kurtarılamaz:** OpenAI batch `completion_window="24h"`. 11+ gün önceki
   batch'lerin penceresi çoktan kapalı → "devam ettir" imkânsız. Yani dialog, ASLA
   kurtarılamayacak batch'ler için nafile nag üretiyor.

**Anlık müdahale (Opus zaten yaptı):** 13 bayat fmap `eski_batch_kurtarma_yedek/` klasörüne
TAŞINDI (silinmedi, geri alınabilir), batch_id.txt zaten yoktu. Dialog şu an çıkmayacak. Bu
brief kalıcı **kod** düzeltmesi içindir ki tekrar birikmesin.

## Düzeltme A (ASIL) — süresi geçmiş batch'leri otomatik temizle, dialog'u sadece gerçekten kurtarılabilir olanlar için göster

`_check_pending_batches` içinde, dialog'u göstermeden ÖNCE her aday `bid` için yaşını
`batch_fmap_<bid>.json` **mtime**'ından hesapla (fmap submit anında yazılır → batch yaşının
birebir vekili). mtime **48 saatten** eskiyse (24h pencere + geniş marj) batch artık
kurtarılamaz → sessizce temizle (fmap sil + batch_id.txt'den çıkar). Kurtarılabilir hiçbir
batch kalmazsa dialog'u HİÇ açma.

Proje konvansiyonu (saf, App'siz test edilebilir helper) gereği mantığı **modül düzeyi saf
fonksiyona** çıkar:

```python
# subtitle_translator_gui.py — modül düzeyi (App dışında)
_BATCH_RECOVERY_MAX_AGE_H = 48   # OpenAI completion_window 24h + marj

def partition_recoverable_batches(base_dir, batch_ids, now_ts, max_age_h=_BATCH_RECOVERY_MAX_AGE_H):
    """(recoverable, expired) döndürür. 'expired' = fmap mtime'ı max_age_h'ten eski olanlar.
    fmap'i OLMAYAN id'ler kurtarılamaz sayılır (fmap olmadan hybrid resume mümkün değil ve
    tarihlenemez) — expired'a koy. Böylece bayat cruft sessizce temizlenir."""
    from pathlib import Path as _P
    recoverable, expired = [], []
    for bid in batch_ids:
        fmap = _P(base_dir) / f"batch_fmap_{bid}.json"
        try:
            age_h = (now_ts - fmap.stat().st_mtime) / 3600.0
        except OSError:
            expired.append(bid)   # fmap yok → tarihlenemez/kurtarılamaz
            continue
        (expired if age_h > max_age_h else recoverable).append(bid)
    return recoverable, expired
```

`_check_pending_batches`'i şöyle güncelle (batch_ids dedup edildikten SONRA):
```python
    import time as _time
    recoverable, expired = partition_recoverable_batches(
        Path(__file__).parent, batch_ids, _time.time())
    if expired:
        self._clear_batch_recovery(expired)   # fmap sil + batch_id.txt'den çıkar
    if not recoverable:
        return                                 # gösterilecek gerçek bir şey yok
    self._show_pending_batches_dialog(recoverable)
```
Not: `_clear_batch_recovery` zaten fmap'i siler ve id'leri batch_id.txt'den çıkarır, dosya
boşalırsa unlink eder — mevcut davranış birebir uygun.

## Düzeltme B (İKİNCİL) — dialog'u X ile kapatmak nag'ı bırakmasın
`_show_pending_batches_dialog`'a pencere-kapat protokolü ekle. Kullanıcı X'e basınca "iptal"
standardı yeterli AMA Düzeltme A yürürlükteyken bayatlar zaten gösterilmeyeceği için tek
kalıcı sorun kalmaz. Yine de netlik için:
```python
    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)   # X = iptal (hiçbir şey yapma)
```
(Bu, davranışı DEĞİŞTİRMEZ ama niyeti açık kılar. İstersen X'i "hepsini ihmal et ama bir daha
sorma" yapmak için X-handler'ı `_delete_selected`-benzeri bir "tümünü temizle"ye bağlayabilirsin
— fakat bu, kullanıcı gerçekten <48h kurtarılabilir bir batch'i yanlışlıkla X'lerse veri
kaybı riski taşır; ÖNERİLMEZ. X=iptal bırak, güvenlik Düzeltme A'da.)

## Düzeltme C (opsiyonel, küçük UX) — buton etiketini netleştir
Mevcut açıklama "İşaretli olanlar seçilen işlemi (Sil veya Devam Ettir) alır" kafa karıştırıyor
(silmek için İŞARETLİ bırakmak gerektiği sezgiye aykırı). "🗑 Seçilenleri Sil" → "🗑 İşaretlileri
Sil (kalıcı)" gibi küçük bir netleştirme yeter. Şart değil.

## Testler (tests/test_pending_batch_purge.py — YENİ)
Saf `partition_recoverable_batches` App'siz test edilebilir:
1. `test_expired_fmap_partitioned` — geçici dizinde eski-mtime fmap (os.utime ile 72h öncesi) →
   `expired`'da; yeni fmap → `recoverable`'da.
2. `test_missing_fmap_is_expired` — fmap'i olmayan bid → `expired`.
3. `test_boundary_48h` — tam 47h → recoverable, 49h → expired.
4. `test_empty_input` — boş liste → ([], []).
Mevcut `tests/test_bugfixes_round11.py` (_clear_batch_recovery) bozulmamalı.

## Doğrulama
1. `python -m py_compile subtitle_translator_gui.py`
2. `python -m unittest tests.test_pending_batch_purge tests.test_bugfixes_round11`
3. Tam paket: `python -m unittest discover -s tests`
4. Smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`
5. Elde doğrulama (opsiyonel): sahte `batch_id.txt` + 72h-eski fmap oluştur → app aç → dialog
   ÇIKMAMALI, fmap + batch_id.txt sessizce temizlenmiş olmalı. Taze (<48h) fmap → dialog çıkmalı.

## Not (kullanıcıya, kod dışı)
`eski_batch_kurtarma_yedek/` klasörü (13 bayat fmap) güvenle silinebilir — hepsi 11+ gün önceki
kapanmış batch'ler. İstersen dursun, zararı yok.
