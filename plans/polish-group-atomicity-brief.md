# Brief: Polish Pass — cümle-grubu atomikliği (Sonnet 5)

Hazırlayan: **Opus 4.8** (Fable 5 analizi + `_polish_pass` kod-doğrulaması, 2026-07-10).
Protokol: Opus doğrular + brief yazar, Sonnet uygular. Orta-riskli, yüksek-değerli.

## Sorun (bu oturumda CANLI görüldü)
`_polish_pass` ([subtitle_translator_gui.py:8000](subtitle_translator_gui.py:8000)) model çıktısını
**cue-cue** kabul/red ediyor ([8175-8194](subtitle_translator_gui.py:8175)): her item ayrı ayrı
`validate_polish_candidate`'ten geçiyor. Model 3 cue'luk bir cümleyi SOV'a göre yeniden dağıttığında:
- cue 1 & 3 geçer → yeni (yeniden-dağıtılmış) metin yazılır
- cue 2 guard'dan döner → ESKİ metni kalır
→ Sonuçta cue 2'nin eski metni, 1&3'ün yeni dağıtımıyla uyuşmaz; **cümle bütünü bozulur**.

Bu turda gerçek örnekler: Solve Et Coagula Polish "geçtiğinde"→"**g geçtiğinde**", "dayalı"→"**dalı**",
"Uly işi"→"**Ulü işi**" garble'ları üretti; Sumerian'da #151-152'de yüklem yanlış cue'ya kaydı.

## Elde hazır veri (doğrulandı)
`_polish_pass` zaten fragment gruplarını reconstruct ediyor ([8027-8034](subtitle_translator_gui.py:8027)):
```python
frag_tags = _tag_fragments(mock_cues)                          # idx -> start/mid/end/none
frag_group_ids, fragment_groups = _fragment_groups(mock_cues, frag_tags)  # idx -> group_id
```
`frag_group_ids[idx]` = o cue'nun ait olduğu cümle-grubu id'si. Yani grup bilgisi ZATEN var;
yalnız kabul döngüsü bunu kullanmıyor.

## Düzeltme — kabul döngüsünü grup-atomik yap
[subtitle_translator_gui.py:8175-8195](subtitle_translator_gui.py:8175) döngüsünü iki fazlı yap.

**Faz 1 — öner ve doğrula (uygulama YOK):** her `polished` item için mevcut validasyonu çalıştır
ama `result_map`'e HEMEN yazma; öneriyi biriktir:
```python
proposals = {}   # sid -> (new_text, ok, reason)
for item in polished:
    if isinstance(item, dict) and "id" in item and "tr" in item:
        sid = str(item["id"])
        if sid not in original_by_id:
            continue
        new_text = str(item["tr"])
        frag_key = int(sid) if sid.isdigit() else item["id"]
        fragment_tag = frag_tags.get(item["id"], frag_tags.get(frag_key, "none"))
        ok, reason = ht.validate_polish_candidate(
            original_by_id[sid], new_text, src_map.get(sid, ""),
            neighbor_texts=neighbor_texts_by_id.get(sid, []),
            fragment_tag=fragment_tag)
        proposals[sid] = (new_text, ok, reason)
```

**Faz 2 — grup-atomik uygula:** her öneriyi grubuna göre topla. Bir cue DEĞİŞMİŞ (new_text !=
original) sayılır. Kural: **bir fragment grubunda değişen cue'lardan HERHANGİ biri red aldıysa,
o grubun TÜM önerilerini reddet** (hiçbirini uygulama → hepsi orijinal kalır, tutarlı). Singleton
(`none`) cue'lar bugünkü gibi bağımsız.
```python
    def _group_of(sid):
        fk = int(sid) if sid.isdigit() else sid
        gid = frag_group_ids.get(fk, frag_group_ids.get(sid))
        return gid   # None => singleton

    # grup -> o gruptaki değişen sid'ler
    from collections import defaultdict
    group_members = defaultdict(list)
    singletons = []
    for sid, (new_text, ok, reason) in proposals.items():
        changed = (new_text != original_by_id[sid])
        gid = _group_of(sid)
        if gid is None:
            singletons.append(sid)
        else:
            group_members[gid].append(sid)

    # singleton: bugünkü davranış
    for sid in singletons:
        new_text, ok, reason = proposals[sid]
        if ok:
            result_map[sid] = new_text
        else:
            rejected += 1
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    # grup: değişen üyelerden biri bile red ise TÜM grubu geri al
    for gid, sids in group_members.items():
        changed_sids = [s for s in sids if proposals[s][0] != original_by_id[s]]
        if not changed_sids:
            continue   # grupta değişiklik yok
        all_ok = all(proposals[s][1] for s in changed_sids)
        if all_ok:
            for s in changed_sids:
                result_map[s] = proposals[s][0]
        else:
            # atomik red: grubun hiçbir değişikliğini uygulama
            rejected += len(changed_sids)
            reason = next((proposals[s][2] for s in changed_sids if not proposals[s][1]),
                          "group_atomic_reject")
            rejected_reasons["group_atomic:" + str(reason)] = \
                rejected_reasons.get("group_atomic:" + str(reason), 0) + len(changed_sids)
            if self._log:
                pass  # istenirse: log_fn ile "grup {gid} atomik reddedildi" 
```
(Kod bütünü mevcut try/except ve `break` yapısının içinde kalmalı; yalnız kabul mantığı değişiyor.)

**Net etki:** Polish daha KONSERVATİF olur — bir cümle grubunu ya bütün olarak iyileştirir ya
hiç dokunmaz. Kısmi (bozuk) uygulama biter. Bu, Fable 5'in "grup atomikliği" ve "muhafazakâr
Polish" önerilerinin ikisini birden karşılar.

## İsteğe bağlı ek — Polish sıcaklığı
[8154](subtitle_translator_gui.py:8154) `temperature=0.4`. NOT: helper gpt-5.4-mini olduğunda
`_safe_chat_create` temperature'ı zaten SİLİYOR → kullanıcı için no-op. Yalnız eski/non-gpt5
helper modelleri için 0.4→0.2 düşürülebilir. Düşük öncelik, isteğe bağlı.

## Testler (`tests/test_polish_group_atomicity.py` — YENİ)
Saf test için `validate_polish_candidate`'i ve grup mantığını izole etmek zor (App metodu içinde).
Öneri: grup-atomik karar mantığını saf modül-düzeyi helper'a çıkar —
`apply_polish_group_atomic(proposals, original_by_id, frag_group_ids) -> (result_map, rejected, reasons)`
— ve onu test et:
1. `test_all_group_pass_applies_all`: 3-cue grup, hepsi geçer → 3'ü de uygulanır.
2. `test_one_group_fail_reverts_all`: 3-cue grup, cue 2 red → 3'ü de orijinal kalır (result_map'te yok).
3. `test_singleton_independent`: none-cue red → yalnız o cue etkilenir, komşu uygulanır.
4. `test_unchanged_group_member_ignored`: grupta yalnız 1 cue değişmiş ve geçmiş → uygulanır.
5. `test_partial_response_group`: model grubun yalnız 2/3 cue'sunu döndürmüş, biri red → değişenler geri alınır.
`_polish_pass` bu helper'ı çağırsın; böylece App'siz test edilebilir (proje konvansiyonu).

## Doğrulama
1. `python -m py_compile subtitle_translator_gui.py`
2. `python -m unittest tests.test_polish_group_atomicity`
3. Tam paket + smoke.
4. Elde: bu turda düzeltilen Solve Et Coagula `.bak`'ını (Polish garble'lı ham) yeniden Polish'ten
   geçir → "g geçtiğinde"/"dalı" gibi tek-cue bozulmalar artık grup-atomik redle ENGELLENMELİ
   (ya da hiç uygulanmamalı). (Manuel/opsiyonel doğrulama.)

## Kapsam DIŞI (ayrı brief)
- Cümle-birimi çeviri + deterministik cue dağıtımı (ana çeviri akışının yeniden tasarımı) —
  en büyük ve en riskli değişiklik; önce yalnız repair yolunda denenmeli. Bu brief SADECE
  Polish kabul mantığını atomik yapıyor, çeviri akışına dokunmuyor.
- Regresyon corpus'u — ayrı plan.
