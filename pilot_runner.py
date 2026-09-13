"""Ayrı durum dizininde gerçek çeviri motoruyla deneme penceresi.

Anahtarlar yalnız stdin üzerinden belleğe alınır; deneme ayarlarına yazılmaz.
"""
import json
import os
import sys
from pathlib import Path


def configure_pilot(app, payload):
    """Ana uygulamanın seçili model/kalite ayarlarını küçük kaynakla çalıştır."""
    import subtitle_translator_gui as gui
    sample = payload['sample']
    snapshot = payload['snapshot']
    app._pilot_source = payload['source']
    app.title('DENEME ÇEVİRİSİ — ' + Path(sample).name)
    app._save_settings = lambda *args, **kwargs: None
    app.input_var.set(str(Path(sample).parent))
    app.output_var.set(payload['output'])
    Path(payload['output']).mkdir(parents=True, exist_ok=True)
    app._selected_files = [sample]
    app._file_list_files = [sample]
    import tkinter as tk
    if hasattr(app, '_file_schema_vars'):
        app._file_schema_vars[sample] = tk.StringVar(master=app, value=payload.get('file_schema_name', 'Otomatik'))
        app._file_language_vars[sample] = tk.StringVar(master=app, value=payload['file_language'])
        app._file_analysis_depth_vars[sample] = tk.StringVar(master=app, value=payload['file_depth'])
    app._main_api_key = lambda: payload['main_key']
    app._main_api_key_backup = lambda: payload.get('backup_key', '')
    for method, key in (('_main_api_base_url', 'main_api_base_url'),
                        ('_main_model_name', 'main_model_name'),
                        ('_main_api_base_url_backup', 'main_base_url_backup'),
                        ('_main_model_name_backup', 'main_model_backup')):
        setattr(app, method, lambda key=key: snapshot.get(key, ''))
    app._helper_api_key = lambda role: snapshot['helper_keys'].get(role, '')
    app._helper_api_base_url = lambda role: snapshot['helper_urls'].get(role, '')
    app._helper_api_model = lambda role: snapshot['helper_models'].get(role, '')
    if not hasattr(app, '_file_schema_vars'):
        app._get_file_source_language = lambda fp: payload['file_language']
        app._get_file_analysis_depth = lambda fp: payload['file_depth']
        app._get_file_schema = lambda fp: payload['file_schema']
    app._get_file_glossary = lambda fp: payload.get('file_glossary', '')
    app._get_locked_terms_dict = lambda fp, tgt: dict(payload['locked_terms'])
    app._series_hint_for = lambda fp: payload['series_hint']
    app._approved_preferences_for = lambda fp, target=None: dict(payload['preferences'])
    app.shutdown_when_done_var.set(False)
    app.same_folder_var.set(False)
    app.auto_resume_crash_var.set(False)
    app.auto_retry_files_var.set(False)
    app.season_canon_var.set(False)
    app.series_memory_var.set(False)
    app._input_folder_explicitly_selected = False
    app.file_info_var.set('Deneme kaynağı: ' + Path(sample).name)
    app._log('DENEME: Yalnız seçilen sahneler işlenecek. Ayarlar hazır; Başlat ile çeviriyi başlatın.', 'info')
    gui.App._update_readiness_card(app)


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    payload = json.load(sys.stdin)
    import subtitle_translator_gui as gui
    app = gui.App()
    configure_pilot(app, payload)
    app.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # İstek nesneleri/anahtarlar hata metninde bulunabilir; yalnız hata sınıfı.
        from app_state import atomic_write_text
        atomic_write_text(Path(os.environ['SUBTITLE_TRANSLATOR_STATE_DIR']) / 'pilot_error.txt',
                          'Deneme penceresi açılamadı: ' + type(exc).__name__)
        raise SystemExit(1)
