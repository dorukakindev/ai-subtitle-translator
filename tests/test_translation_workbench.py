"""Deneme izolasyonu, geçiş geri alma ve kullanıcı tercihleri."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import subtitle_translator_gui as gui
import translation_review as review
from app_state import atomic_write_json
from pilot_runner import configure_pilot
from translation_workbench import TranslationWorkbenchMixin
from types import MethodType


def blocks(count=9):
    return [(str(i + 1), f'00:00:{i * 2:02},000 --> 00:00:{i * 2 + 1:02},000', f'Metin {i + 1}') for i in range(count)]


class TranslationWorkbenchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'Show.S01E01.srt'
        self.output = self.root / 'translated.srt'
        self.record_path = self.root / 'output.review.json'
        self.before = blocks()
        self.after = list(self.before)
        self.after[0] = (self.before[0][0], self.before[0][1], 'Düzeltilmiş metin')
        gui.write_srt(self.source, self.before, target_language='English')
        gui.write_srt(self.output, self.after, target_language='English')
        history = {}
        gui._record_pass_change({}, 'Polish', self.before, self.after, history)
        self.record = review.build_review_record({'source_path': str(self.source),
            'output_path': str(self.output), 'pass_history': history}, self.after, self.before, 'Turkish', 'English')
        atomic_write_json(self.record_path, self.record)

    def test_short_pilot_has_no_duplicates(self):
        selected = review.select_pilot_scenes(blocks(4))
        self.assertEqual([b for scene in selected for b in scene], blocks(4))

    def test_long_pilot_includes_beginning_middle_end(self):
        selected = review.select_pilot_scenes(blocks(25), 3)
        self.assertEqual([s[0][0] for s in selected], ['1', '12', '23'])
        self.assertEqual(selected[-1][-1][0], '25')

    def test_separate_scenes_respected(self):
        source = [b for b in blocks(25) if int(b[0]) in (1, 2, 12, 13, 24, 25)]
        self.assertEqual([len(s) for s in review.select_pilot_scenes(source)], [2, 2, 2])

    def test_empty_pilot(self):
        self.assertEqual(review.select_pilot_scenes([]), [])

    def test_episode_overrides_series_and_stays_in_episode(self):
        review.save_preference(self.source, 'English', 'Turkish', 'Dizi', 'Terim', 'ward', 'bölge')
        review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Terim', 'ward', 'koğuş')
        current = review.preference_terms(review.load_preferences(self.source, 'en', 'tr'))
        other = review.preference_terms(review.load_preferences(self.root / 'Show.S01E02.srt', 'en', 'tr'))
        self.assertEqual(current['ward'], 'koğuş')
        self.assertEqual(other['ward'], 'bölge')
        self.assertEqual(review.load_preferences(self.source, 'en', 'de'), {})
        self.assertEqual(review.load_preferences(self.root / 'Other.S01E02.srt', 'en', 'tr'), {})

    def test_approved_correction_replaces_previous_approval(self):
        for target in ('bölge', 'koğuş'):
            review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Terim', 'ward', target)
        self.assertEqual(review.preference_terms(review.load_preferences(self.source, 'en', 'tr')), {'ward': 'koğuş'})

    def test_episode_preference_survives_release_name_change(self):
        review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Karakter', 'John', 'Can')
        prefs = review.load_preferences(self.root / 'Show.S01E01.1080p.srt', 'en', 'tr')
        self.assertEqual(review.preference_terms(prefs), {'John': 'Can'})

    def test_address_preference_is_prompt_only(self):
        review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Hitap', 'Ali → Veli', 'siz')
        prefs = review.load_preferences(self.source, 'en', 'tr')
        self.assertEqual(review.preference_terms(prefs), {})
        self.assertIn('siz', review.preference_hint(prefs))
        with self.assertRaises(ValueError):
            review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Hitap', 'Ali', 'böyle')

    def test_approved_terms_override_automatic_terms_in_pipeline(self):
        import hybrid_translate as ht
        review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Terim', 'ward', 'koğuş')
        review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Hitap', 'Ali → Veli', 'siz')
        app = SimpleNamespace(src_var=SimpleNamespace(get=lambda: 'English'),
            tgt_var=SimpleNamespace(get=lambda: 'Turkish'), _snap_get=lambda key, default=None: default,
            _effective_file_source_language=lambda *args: 'English', _get_file_schema=lambda fp: {},
            _get_file_glossary=lambda fp: '', _series_mem_for=lambda fp: (None, None, None),
            _project_memory_for=lambda *args: SimpleNamespace(get_locked_glossary=lambda: {'Ward': 'bölge'}))
        app._approved_preferences_for = MethodType(TranslationWorkbenchMixin._approved_preferences_for, app)
        with patch.object(ht, 'load_glossary', return_value={}):
            terms = gui.App._get_locked_terms_dict(app, str(self.source), 'Turkish')
        self.assertEqual(terms, {'ward': 'koğuş'})
        # Otomatik dizi hafızası kapalıyken de açık kullanıcı onayı prompt'a girer.
        hint = gui.App._series_hint_for(app, str(self.source))
        self.assertIn('siz', hint)
        self.assertIn('koğuş', hint)

    def test_unknown_series_rejected(self):
        with self.assertRaises(ValueError):
            review.save_preference(self.root / 'movie.srt', 'en', 'tr', 'Dizi', 'Terim', 'ward', 'bölge')

    def test_corrupt_preferences_are_not_overwritten(self):
        path = review.preference_locations(self.source, 'en', 'tr')[0]
        path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            review.save_preference(self.source, 'en', 'tr', 'Bölüm', 'Terim', 'ward', 'bölge')
        self.assertEqual(path.read_text(), '{broken')

    def test_timeline_preserves_full_text(self):
        before = [('1', self.before[0][1], '<i>Eski\nmetin</i>')]
        after = [('1', self.before[0][1], '<i>Yeni\nmetin</i>')]
        history = {}
        gui._record_pass_change({}, 'Polish', before, after, history)
        self.assertEqual(history['1'][0]['before_full'], before[0][2])
        self.assertEqual(history['1'][0]['timestamp'], before[0][1])

    def test_renumbered_output_matches_timestamp(self):
        after = [('99', self.after[0][1], self.after[0][2])]
        record = review.build_review_record({'source_path': str(self.source), 'output_path': str(self.output),
            'pass_history': {'1': self.record['cues'][0]['events']}}, after, self.before, 'tr', 'en')
        self.assertEqual(record['cues'][0]['initial'], 'Metin 1')

    def test_ambiguous_timestamps_disable_rollback(self):
        after = [self.after[0], ('99', self.after[0][1], 'Başka metin')]
        record = review.build_review_record({'source_path': str(self.source), 'output_path': str(self.output),
            'pass_history': {'1': self.record['cues'][0]['events']}}, after, self.before, 'tr', 'en')
        self.assertFalse(any(c['has_history'] for c in record['cues']))

    def test_restore_scene_preserves_cues_without_history(self):
        result = review.restore_initial(self.record, {'2': 'Elle düzenlendi'}, '1', True)
        self.assertEqual(result, {'1': 'Metin 1', '2': 'Elle düzenlendi'})

    def test_save_backs_up_exact_bytes_and_keeps_timing(self):
        original = self.output.read_bytes()
        backup = review.apply_review(self.record_path, self.record, {'1': 'Yeni çeviri'})
        self.assertEqual(backup.read_bytes(), original)
        actual = gui.parse_subtitle(str(self.output))
        self.assertEqual([(i, ts) for i, ts, _ in actual], [(i, ts) for i, ts, _ in self.after])
        self.assertEqual(actual[0][2], 'Yeni çeviri')
        self.assertEqual(json.loads(self.record_path.read_text(encoding='utf-8'))['output_hash'], review.file_hash(self.output))
        self.assertEqual(gui.parse_subtitle(str(self.source)), self.before)

    def test_external_changes_block_write(self):
        self.output.write_text('Başka sürüm', encoding='utf-8')
        with self.assertRaises(ValueError):
            review.apply_review(self.record_path, self.record, {'1': 'Yeni'})
        self.assertEqual(self.output.read_text(encoding='utf-8'), 'Başka sürüm')

    def test_record_save_failure_restores_original_output(self):
        original = self.output.read_bytes()
        original_hash = self.record['output_hash']
        def write(path, data):
            if Path(path) == self.record_path:
                raise OSError('disk full')
            atomic_write_json(path, data)
        with patch.object(review, 'atomic_write_json', side_effect=write), self.assertRaises(OSError):
            review.apply_review(self.record_path, self.record, {'1': 'Yeni'})
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(self.record['output_hash'], original_hash)

    def test_invalid_drafts_do_not_modify_output(self):
        original = self.output.read_bytes()
        for value in ('', '[HATA]', 'a\n\nb'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review.apply_review(self.record_path, self.record, {'1': value})
        self.assertEqual(self.output.read_bytes(), original)

    def test_tampered_timestamps_rejected(self):
        self.record['cues'][0]['timestamp'] = self.record['cues'][1]['timestamp']
        with self.assertRaises(ValueError):
            review.apply_review(self.record_path, self.record, {'1': 'Yeni'})

    def test_unchanged_review_does_not_create_backup(self):
        self.assertIsNone(review.apply_review(self.record_path, self.record, {}))
        self.assertFalse((self.root / 'Raporlar').exists())

    def test_pilot_config_uses_frozen_models_and_isolated_paths(self):
        class Var:
            def set(self, value):
                self.value = value
        app = SimpleNamespace(**{name: Var() for name in ('input_var', 'output_var', 'shutdown_when_done_var',
            'same_folder_var', 'auto_resume_crash_var', 'auto_retry_files_var', 'season_canon_var',
            'series_memory_var', 'file_info_var')}, title=Mock(), _log=Mock())
        sample = self.root / 'pilot' / 'Show.S01E01.srt'
        payload = {'source': str(self.source), 'sample': str(sample), 'output': str(self.root / 'out'),
            'snapshot': {'main_model_name': 'test-model', 'helper_keys': {'critic': 'secret'},
                         'helper_urls': {}, 'helper_models': {'critic': 'test-helper'}},
            'main_key': 'main-secret', 'file_language': 'French', 'file_depth': 'Derin',
            'file_schema': {'test': True}, 'locked_terms': {'ward': 'koğuş'}, 'series_hint': 'kanon', 'preferences': {}}
        with patch.object(gui.App, '_update_readiness_card'):
            configure_pilot(app, payload)
        self.assertEqual(app._get_file_source_language(str(sample)), 'French')
        self.assertEqual(app._main_model_name(), 'test-model')
        self.assertEqual(app._helper_api_model('critic'), 'test-helper')
        self.assertEqual(app._selected_files, [str(sample)])
        self.assertFalse(app.shutdown_when_done_var.value)
        self.assertFalse(app.same_folder_var.value)
        self.assertIsNone(app._save_settings())


if __name__ == '__main__':
    unittest.main()
