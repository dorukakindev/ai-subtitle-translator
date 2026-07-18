# Brief: Sahne planı — max_tokens düzeltmesi + gözlemlenebilirlik (Sonnet 5)

> **DURUM: UYGULANDI (Sonnet 5, 2026-07-17).** Görev A (max_tokens 3000→8000) ve
> Görev B (referent/goal sayılarını loglama) ikisi de uygulandı. Doğrulama: compile
> temiz, `test_scene_plan`+`test_bugfixes_round11`+`test_context_chain` (74 test) yeşil
> — davranış değişmedi, brief'in beklediği gibi.

Hazırlayan: **Opus 4.8** (Fable 5 review bulgusunun kod+token doğrulaması, 2026-07-10).
Protokol: analiz modeli doğrular + brief yazar, Sonnet uygular. Sahne-planı özelliğinin
küçük ama gerçek bir follow-up'ı — iki görev, Görev A zorunlu, Görev B opsiyonel.

## Doğrulanan sorun
Yeni `_extract_emotional_arc` (sahne planı) çağrısı `max_tokens=3000` ile sınırlı
([hybrid_translate.py:1124](hybrid_translate.py:1124)). Ölçtüm:
- **Gerçekçi** (max değil, orta-yoğunluk) 30-sahnelik plan JSON'u ≈ **2550 çıktı token**.
- **Teorik max** (tüm alanlar dolu, 30 sahne) ≈ **8000 token**.
- gpt-5 ailesinde `_safe_chat_create` `max_tokens`→`max_completion_tokens`'a çeviriyor
  ([hybrid_translate.py:1660](hybrid_translate.py:1660)) ve gpt-5'te bu limit **reasoning
  token'larını da** içerir → efektif JSON bütçesi 3000'den DAHA AZ.

Sonuç: uzun belgesellerde (30-sahne limitine çarpan dosyalar — kullanıcının tipik iş yükü)
JSON kesilir → parse fail → fallback da fail → fonksiyon sessizce `[]` döner. Özellik tam da
en çok işe yarayacağı yerde, tek log ipucu bile olmadan devre dışı kalabilir. Çıktı token'ı
yalnız üretildiği kadar faturalanır; yüksek tavanın maliyeti yok.

## GÖREV A (zorunlu) — max_tokens'ı yükselt
[hybrid_translate.py:1124](hybrid_translate.py:1124), `_extract_emotional_arc` içindeki
`_safe_chat_create` çağrısında:
```python
            max_tokens=3000,
```
→
```python
            max_tokens=8000,
```
(8000 = ölçülen teorik max; gerçekçi 2550'ye gpt-5 reasoning overhead'i eklense bile rahat
headroom. Alanlar zaten `_sanitize_scene_plan_entry` ile sınırlı olduğundan çıktı üst-sınırı
kontrollü — sınırsız büyüme riski yok.)

## GÖREV B (opsiyonel) — gözlemlenebilirlik
[hybrid_translate.py:2156](hybrid_translate.py:2156) log satırı şu an yalnız sahne sayısı
veriyor. Özelliğin gerçek koşularda referent/goal ÜRETİP üretmediğini görmek için zenginleştir:
```python
    if log_fn and scene_emotions:
        log_fn(f"Sahne planı: {len(scene_emotions)} sahne çıkarıldı", "ok")
```
→
```python
    if log_fn and scene_emotions:
        _with_ref = sum(1 for s in scene_emotions if isinstance(s, dict) and s.get("referents"))
        _with_goal = sum(1 for s in scene_emotions if isinstance(s, dict) and s.get("speaker_goals"))
        log_fn(f"Sahne planı: {len(scene_emotions)} sahne "
               f"({_with_ref}'inde gönderge çözümü, {_with_goal}'inde konuşmacı hedefi)", "ok")
```
(Yalnız log stringi — davranış değişmez, test gerekmez. Kesilme sorununu da dolaylı görünür
kılar: sahne sayısı beklenenden düşükse veya 0'sa kullanıcı fark eder.)

## Doğrulama
1. `python -m py_compile hybrid_translate.py`
2. `python -m unittest tests.test_scene_plan tests.test_bugfixes_round11 tests.test_context_chain`
   (davranış değişmediği için hepsi yeşil kalmalı — bu görevler token bütçesi/log, mantık değil).
3. Tam paket + headless smoke.

## Kapsam DIŞI (Fable'ın notu, ayrı tur)
- Uzun sahnelerde ilk-8-cue örneklemi yerine baş+orta+son örnekleme (`analysis_depth`
  kalıbı gibi) — `referents` seyrekliğini azaltır ama ayrı, daha büyük iş.
- Sıradaki büyük paket: Risk Yönlendirici + Kalite İnceleme Kuyruğu.
