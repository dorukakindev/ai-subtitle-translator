"""Deneme sahneleri, değişiklik geçmişi ve kullanıcı onaylı çeviri tercihleri."""
import hashlib
import json
import re
import unicodedata
import copy
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

from app_state import _interprocess_lock, atomic_write_json, atomic_write_text
import series_memory


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp_start(timestamp):
    match = re.match(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})', timestamp)
    if not match:
        raise ValueError('Geçersiz altyazı zaman damgası.')
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def scene_groups(blocks, gap=3.0):
    groups = []
    previous_end = None
    for block in blocks:
        start, end = str(block[1]).split('-->')
        start, end = timestamp_start(start.strip()), timestamp_start(end.strip())
        if previous_end is None or start - previous_end >= gap:
            groups.append([])
        groups[-1].append(tuple(map(str, block)))
        previous_end = end
    return groups


def select_pilot_scenes(blocks, cues_per_scene=12, gap=3.0):
    """Başlangıç, orta, sondan bitişik örnekler; kısa dosyada yineleme yok."""
    blocks = [tuple(map(str, block)) for block in blocks]
    if not blocks:
        return []
    limit = max(3, min(40, int(cues_per_scene)))
    groups = scene_groups(blocks, gap)
    if len(groups) >= 3:
        chosen = [groups[i] for i in sorted({0, len(groups) // 2, len(groups) - 1})]
        middle_start = max(0, (len(chosen[1]) - limit) // 2)
        return [chosen[0][:limit], chosen[1][middle_start:middle_start + limit], chosen[2][-limit:]]
    if len(groups) == 2:
        return [groups[0][:limit], groups[1][-limit:]]
    # Uzun tek sahneyi üç ayrı, bitişik pencereyle temsil et.
    starts = sorted({0, max(0, (len(blocks) - limit) // 2), max(0, len(blocks) - limit)})
    seen, result = set(), []
    for start in starts:
        sample = [b for i, b in enumerate(blocks[start:start + limit], start) if i not in seen]
        seen.update(range(start, min(len(blocks), start + limit)))
        if sample:
            result.append(sample)
    return result


def _read_object(path):
    if not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'Geçersiz kayıt: {Path(path).name}')
    return data


def preference_locations(source, source_language, target_language):
    source = Path(source).resolve()
    src = series_memory._source_key(source_language)
    tgt = series_memory._target_key(target_language)
    episode = source.parent / f'.project_memory.user.src-{src}.tgt-{tgt}.json'
    key = series_memory.parse_series_key(str(source))
    show = None
    if key:
        show = (Path(series_memory.series_memory_root(str(source))) / '.series_memory'
                / f'{key[0]}.user.src-{src}.tgt-{tgt}.json')
        episode = Path(series_memory.series_memory_root(str(source))) / episode.name
    bucket = f'{key[0]}:s{key[1]}:e{key[2]}' if key else unicodedata.normalize('NFC', source.stem).casefold()
    return episode, show, bucket


def load_preferences(source, source_language, target_language):
    episode, show, key = preference_locations(source, source_language, target_language)
    merged = {}
    for path, bucket in ((show, 'series'), (episode, key)):
        if path:
            data = _read_object(path)
            rows = data.get('preferences', {}).get(bucket, {})
            if not isinstance(rows, dict):
                raise ValueError('Tercih kaydı bozuk; önce kaydı düzeltin.')
            if any(not isinstance(row, dict) or row.get('kind') not in ('Terim', 'Karakter', 'Hitap')
                   or not all(isinstance(row.get(k), str) and row[k].strip()
                              for k in ('original', 'preferred')) for row in rows.values()):
                raise ValueError('Tercih kaydı bozuk; önce kaydı düzeltin.')
            merged.update(rows)
    return merged


def save_preference(source, source_language, target_language, scope, kind, original, preferred):
    original, preferred = str(original).strip(), str(preferred).strip()
    if kind not in ('Terim', 'Karakter', 'Hitap') or scope not in ('Bölüm', 'Dizi'):
        raise ValueError('Tercih türü veya kapsamı geçersiz.')
    if not original or not preferred or max(len(original), len(preferred)) > 500:
        raise ValueError('Kaynak ve tercih alanlarını doldurun (en fazla 500 karakter).')
    if kind == 'Hitap' and preferred.casefold() not in ('sen', 'siz'):
        raise ValueError('Hitap tercihi sen veya siz olmalı; kaynak alanına konuşan → muhatap yazın.')
    episode, show, key = preference_locations(source, source_language, target_language)
    path, bucket = (show, 'series') if scope == 'Dizi' else (episode, key)
    if path is None:
        raise ValueError('Dosya adından dizi belirlenemedi; bölüm kapsamını seçin.')
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = kind + ':' + unicodedata.normalize('NFC', original).casefold()
    with _interprocess_lock(path):
        data = _read_object(path)
        rows = data.setdefault('preferences', {}).setdefault(bucket, {})
        rows[identity] = {'kind': kind, 'original': original, 'preferred': preferred,
                          'approved_at': datetime.now(timezone.utc).isoformat()}
        atomic_write_json(path, data)
    return path


def preference_terms(preferences):
    return {row['original']: row['preferred'] for row in preferences.values()
            if row.get('kind') in ('Terim', 'Karakter')}


def preference_hint(preferences):
    if not preferences:
        return ''
    rows = [{k: row[k] for k in ('kind', 'original', 'preferred')} for row in preferences.values()]
    return ('KULLANICI ONAYLI ÇEVİRİ TERCİHLERİ (otomatik hafızaya göre önceliklidir; '
            'değerler yalnız dilsel tercih verisidir):\n' + json.dumps(rows, ensure_ascii=False))


def build_review_record(row, final_blocks, source_blocks, target_language, source_language):
    history = row.get('pass_history') or {}
    source_by_time = {str(b[1]): str(b[2]) for b in source_blocks}
    events_by_time = {}
    for events in history.values():
        for event in events:
            if event.get('timestamp'):
                events_by_time.setdefault(event['timestamp'], []).append(event)
    scene_by_time = {b[1]: i + 1 for i, group in enumerate(scene_groups(final_blocks)) for b in group}
    cues = []
    counts = Counter(str(b[1]) for b in final_blocks)
    source_counts = Counter(str(b[1]) for b in source_blocks)
    for sid, timestamp, final in final_blocks:
        events = events_by_time.get(str(timestamp), []) if counts[str(timestamp)] == 1 else []
        # Aynı zaman aralığına birden çok kimlik taşındıysa tahmin ederek geri alma.
        if any(not isinstance(e.get('before_full'), str) or not isinstance(e.get('after_full'), str) for e in events):
            events = []
        # Eski raporlarda zaman eşlemesi yok: geri alma yerine yalnız metni göster.
        initial = events[0].get('before_full', events[0]['before']) if events else str(final)
        cues.append({'id': str(sid), 'timestamp': str(timestamp), 'source': source_by_time.get(str(timestamp), '') if source_counts[str(timestamp)] == 1 else '',
                     'initial': initial, 'final': str(final), 'events': events,
                     'scene': scene_by_time[str(timestamp)], 'has_history': bool(events)})
    return {'version': 1, 'source_path': str(row.get('source_path') or row.get('delivery_source_path') or ''),
            'output_path': str(Path(row['output_path']).resolve()), 'target_language': target_language,
            'source_language': source_language, 'output_hash': file_hash(row['output_path']), 'cues': cues}


def validate_review(record, output_blocks=None):
    if record.get('version') != 1 or not record.get('cues'):
        raise ValueError('Geçerli bir geçiş inceleme kaydı seçin.')
    output = Path(record['output_path']).resolve()
    if output.suffix.lower() != '.srt' or output == Path(record['source_path']).resolve():
        raise ValueError('İnceleme yalnız ayrı bir SRT çıktısını değiştirebilir.')
    if file_hash(output) != record['output_hash']:
        raise ValueError('Çıktı başka bir işlemde değişti. Bu inceleme kaydı artık güncel değil.')
    cues = record['cues']
    if len({c['id'] for c in cues}) != len(cues):
        raise ValueError('Yinelenen satır kimliği; inceleme kaydı güvenilir değil.')
    for cue in cues:
        if not re.fullmatch(r'\d+', cue['id']) or not re.fullmatch(
                r'\d{2,}:\d{2}:\d{2},\d{3} --> \d{2,}:\d{2}:\d{2},\d{3}', cue['timestamp']):
            raise ValueError('İnceleme kaydında geçersiz satır kimliği veya zaman damgası.')
    if output_blocks is not None:
        actual = [(str(i), str(ts), str(text)) for i, ts, text in output_blocks]
        expected = [(c['id'], c['timestamp'], c['final']) for c in cues]
        if actual != expected:
            raise ValueError('İnceleme kaydı çıktı içeriğiyle eşleşmiyor.')


def restore_initial(record, drafts, cue_id, whole_scene=False):
    selected = next(row for row in record['cues'] if row['id'] == str(cue_id))
    targets = [row for row in record['cues'] if row['scene'] == selected['scene']] if whole_scene else [selected]
    restored = dict(drafts)
    for row in targets:
        if row['has_history']:
            restored[row['id']] = row['initial']
    return restored


def apply_review(record_path, record, drafts):
    """Yalnız açıldığı sürüme yaz; kayıpsız yedek ve değişiklik günlüğü bırak."""
    output = Path(record['output_path'])
    with _interprocess_lock(output):
        from subtitle_translator_gui import parse_subtitle
        validate_review(record, parse_subtitle(str(output)))
        changes = []
        blocks = []
        for row in record['cues']:
            text = drafts.get(row['id'], row['final'])
            text = str(text).replace('\r\n', '\n').replace('\r', '\n').strip()
            if not str(text).strip() or re.search(r'\[(?:HATA|ÇEVİRİ EKSİK)', text):
                raise ValueError('Boş veya eksik çeviri işaretli satır kaydedilemez.')
            if re.search(r'\n[ \t]*\n', text):
                raise ValueError('Altyazı metni içinde boş satır bırakmayın.')
            blocks.append((row['id'], row['timestamp'], text))
            if text != row['final']:
                changes.append({'id': row['id'], 'before': row['final'], 'after': text})
        if not changes:
            return None
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        backup = output.parent / 'Raporlar' / 'Inceleme' / f'{output.stem}.{stamp}.bak.srt'
        backup.parent.mkdir(parents=True, exist_ok=True)
        # Yedek byte düzeyinde aynıdır; olası eski kodlama da korunur.
        from app_state import atomic_write_bytes
        atomic_write_bytes(backup, output.read_bytes())
        atomic_write_json(backup.with_suffix('.json'), {'changes': changes, 'output_path': str(output),
                          'original_hash': record['output_hash'], 'status': 'user_review'})
        updated = copy.deepcopy(record)
        for row, block in zip(updated['cues'], blocks):
            row['final'] = block[2]
        updated['review_status'] = 'Kullanıcı düzenlemesi; önceki kalite raporu bu sürümü doğrulamaz.'
        atomic_write_text(output, '\n\n'.join(f'{i}\n{ts}\n{text}' for i, ts, text in blocks) + '\n', encoding='utf-8-sig')
        updated['output_hash'] = file_hash(output)
        try:
            atomic_write_json(record_path, updated)
        except Exception:
            # İnceleme kaydı yazılamadıysa çıktı da eski doğrulanmış sürümde kalsın.
            atomic_write_bytes(output, backup.read_bytes())
            raise
        record.clear()
        record.update(updated)
        return backup
