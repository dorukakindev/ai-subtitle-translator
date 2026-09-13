"""Deneme, geçiş incelemesi ve açık kullanıcı tercihleri için masaüstü araçları."""
import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from app_state import atomic_write_json
import translation_review as review


def style_window(window):
    """Araç pencerelerini ana uygulamanın renkleriyle eşleştir."""
    import subtitle_translator_gui as gui
    window.configure(fg_color=gui.BG)
    def visit(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkFrame):
                child.configure(fg_color=gui.PANEL)
            elif isinstance(child, ctk.CTkTextbox):
                child.configure(fg_color=gui.PANEL, text_color=gui.FG,
                                border_width=1, border_color=gui.BORDER_SOFT)
            elif isinstance(child, ctk.CTkEntry):
                child.configure(fg_color=gui.CARD, border_color=gui.BORDER, text_color=gui.FG)
            elif isinstance(child, ctk.CTkButton):
                child.configure(fg_color=gui.ACCENT, hover_color=gui.ACCENT_HOVER)
            elif isinstance(child, ctk.CTkOptionMenu):
                child.configure(fg_color=gui.CARD, button_color=gui.ACCENT, button_hover_color=gui.ACCENT_HOVER)
            elif isinstance(child, ctk.CTkLabel):
                child.configure(text_color=gui.FG)
            visit(child)
    visit(window)


class TranslationWorkbenchMixin:
    def _approved_preferences_for(self, fp, target=None):
        if not fp:
            return {}
        from subtitle_translator_gui import _lang_iso639_1
        on_ui = threading.current_thread() is threading.main_thread()
        source_var = self.__dict__.get('src_var')
        target_var = self.__dict__.get('tgt_var')
        source_fallback = source_var.get() if on_ui and source_var is not None else self._snap_get('src_lang', 'English')
        target = target or (target_var.get() if on_ui and target_var is not None else self._snap_get('tgt_lang', 'Turkish'))
        # GUI kurulmadan çağrılan rapor/yardımcı işlemler snapshot varsayımlarını kullanır.
        source = (self._effective_file_source_language(fp, source_fallback)
                  if '_file_language_vars' in self.__dict__ or '_effective_file_source_language' in self.__dict__
                  else source_fallback)
        return review.load_preferences(fp, _lang_iso639_1(source),
                                       _lang_iso639_1(target))

    def _save_translation_reviews(self, rows, directory):
        from subtitle_translator_gui import parse_subtitle
        for row in rows:
            try:
                output = Path(row.get('output_path') or '')
                source = row.get('delivery_source_path') or row.get('source_path')
                if not output.is_file() or output.suffix.lower() != '.srt' or not source:
                    continue
                source_language = self._effective_file_source_language(source, self._snap_get('src_lang', 'English'))
                record = review.build_review_record(row, parse_subtitle(str(output)),
                    parse_subtitle(source, source_language=source_language) if Path(source).is_file() else [],
                    self._snap_get('tgt_lang', 'Turkish'), source_language)
                if self.__dict__.get('_pilot_source'):
                    record['source_path'] = self._pilot_source
                name = output.stem + '.' + review.hashlib.sha256(str(output.resolve()).encode()).hexdigest()[:10]
                path = Path(directory) / 'Inceleme' / (name + '.review.json')
                atomic_write_json(path, record)
                row['review_path'] = str(path)
                self._last_translation_review = str(path)
            except Exception as exc:
                self._log(f'Geçiş inceleme kaydı oluşturulamadı: {exc}', 'warn')

    def _choose_workbench_source(self):
        files = self._get_srt_files()
        if len(files) == 1:
            return files[0]
        return filedialog.askopenfilename(parent=self, title='İşlenecek kaynak altyazıyı seçin',
            initialdir=str(Path(files[0]).parent) if files else None,
            filetypes=[('Altyazı', '*.srt *.vtt *.ass *.ssa')])

    def _open_preferences_dialog(self, source=None, source_language=None, target_language=None):
        source = source or self._choose_workbench_source()
        if not source:
            return
        from subtitle_translator_gui import _lang_iso639_1
        source_language = _lang_iso639_1(source_language or self._effective_file_source_language(source, self.src_var.get()))
        target_language = _lang_iso639_1(target_language or self.tgt_var.get())
        dlg = ctk.CTkToplevel(self)
        dlg.title('Onaylı çeviri tercihleri')
        dlg.geometry('700x600')
        dlg.minsize(540, 480)
        ctk.CTkLabel(dlg, text=Path(source).name, font=ctk.CTkFont(size=17, weight='bold')).pack(pady=(18, 8))
        ctk.CTkLabel(dlg, text='Bölüm tercihi dizi tercihinden önceliklidir. Kaydetmek mevcut çıktıyı değiştirmez.\n'
                    'Hitap için kaynak: konuşan → muhatap; tercih: sen veya siz.', wraplength=620).pack(padx=18)
        form = ctk.CTkFrame(dlg)
        form.pack(fill='x', padx=18, pady=12)
        form.grid_columnconfigure((0, 1), weight=1)
        kind = ctk.CTkOptionMenu(form, values=['Terim', 'Karakter', 'Hitap'])
        scope = ctk.CTkOptionMenu(form, values=['Bölüm', 'Dizi'])
        kind.grid(row=0, column=0, padx=8, pady=8, sticky='ew')
        scope.grid(row=0, column=1, padx=8, pady=8, sticky='ew')
        original = ctk.CTkEntry(form, placeholder_text='Kaynak terim / isim / konuşan → muhatap')
        preferred = ctk.CTkEntry(form, placeholder_text='Onayladığınız karşılık')
        original.grid(row=1, column=0, padx=8, pady=8, sticky='ew')
        preferred.grid(row=1, column=1, padx=8, pady=8, sticky='ew')
        listing = ctk.CTkTextbox(dlg, wrap='word')
        listing.pack(fill='both', expand=True, padx=18, pady=8)
        status = ctk.CTkLabel(dlg, text='', wraplength=620)
        status.pack(fill='x', padx=18, pady=(0, 12))

        def refresh():
            data = review.load_preferences(source, source_language, target_language)
            listing.configure(state='normal')
            listing.delete('1.0', 'end')
            listing.insert('1.0', '\n\n'.join(f"{v['kind']}: {v['original']} → {v['preferred']}" for v in data.values())
                           or 'Henüz onaylı tercih yok.')
            listing.configure(state='disabled')

        def save():
            try:
                if getattr(self, '_is_running', False):
                    raise ValueError('Tercihleri değiştirmek için çevirinin bitmesini bekleyin.')
                review.save_preference(source, source_language, target_language, scope.get(),
                                       kind.get(), original.get(), preferred.get())
                refresh()
                status.configure(text='Tercih onaylandı. Sonraki çeviride kullanılacak.')
            except Exception as exc:
                status.configure(text=str(exc))
        ctk.CTkButton(form, text='Tercihi onayla ve kaydet', command=save).grid(
            row=2, column=0, columnspan=2, padx=8, pady=8, sticky='ew')
        try:
            refresh()
        except Exception as exc:
            status.configure(text=str(exc))
        style_window(dlg)
        return dlg

    def _open_translation_review(self, path=None):
        from subtitle_translator_gui import parse_subtitle
        if not path:
            latest = self.__dict__.get('_last_translation_review')
            path = filedialog.askopenfilename(parent=self, title='Geçiş inceleme kaydı seçin',
                initialdir=str(Path(latest).parent) if latest else self.output_var.get() or None,
                initialfile=Path(latest).name if latest else None,
                filetypes=[('Geçiş incelemesi', '*.review.json')])
        if not path:
            return
        try:
            record = review._read_object(path)
            review.validate_review(record, parse_subtitle(record['output_path']))
        except Exception as exc:
            messagebox.showerror('İnceleme açılamadı', str(exc), parent=self)
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title('Çeviri geçişleri — ' + Path(record['output_path']).name)
        dlg.geometry('1060x650')
        dlg.minsize(700, 600)
        dlg.grid_columnconfigure((0, 1), weight=1)
        dlg.grid_rowconfigure(3, weight=1)
        state = {'index': 0, 'drafts': {}}
        title = ctk.CTkLabel(dlg, text='', font=ctk.CTkFont(size=17, weight='bold'))
        title.grid(row=0, column=0, columnspan=2, padx=16, pady=12)
        nav = ctk.CTkFrame(dlg)
        nav.grid(row=1, column=0, columnspan=2, sticky='ew', padx=16)
        source_box = ctk.CTkTextbox(dlg, height=95, wrap='word')
        source_box.grid(row=2, column=0, columnspan=2, sticky='ew', padx=16, pady=8)
        timeline = ctk.CTkTextbox(dlg, wrap='word')
        timeline.grid(row=3, column=0, sticky='nsew', padx=(16, 4), pady=8)
        final_box = ctk.CTkTextbox(dlg, wrap='word')
        final_box.grid(row=3, column=1, sticky='nsew', padx=(4, 16), pady=8)
        stage = ctk.CTkOptionMenu(dlg, values=['İlk kayıtlı sürüm'])
        stage.grid(row=4, column=0, sticky='ew', padx=16, pady=4)
        buttons = ctk.CTkFrame(dlg)
        buttons.grid(row=5, column=0, columnspan=2, sticky='ew', padx=16, pady=8)
        buttons.grid_columnconfigure((0, 1, 2), weight=1)
        status = ctk.CTkLabel(dlg, text='Sağdaki metin düzenlenebilir. Kaydetmeden önce değişiklikleri kontrol edin.', wraplength=900)
        status.grid(row=6, column=0, columnspan=2, padx=16, pady=8)

        def current():
            return record['cues'][state['index']]

        def remember():
            state['drafts'][current()['id']] = final_box.get('1.0', 'end-1c')

        def fill(box, text, readonly=False):
            box.configure(state='normal')
            box.delete('1.0', 'end')
            box.insert('1.0', text)
            if readonly:
                box.configure(state='disabled')

        def show():
            cue = current()
            title.configure(text=f"Satır {cue['id']} / {len(record['cues'])} · Sahne {cue['scene']} · {cue['timestamp']}")
            fill(source_box, 'KAYNAK\n' + (cue['source'] or 'Yapısal değişiklik nedeniyle kaynak eşleştirilemedi.'), True)
            parts = ['İLK KAYITLI ÇEVİRİ\n' + cue['initial']]
            for event in cue['events']:
                parts.append(f"{event['pass']}\nÖNCE: {event.get('before_full', event['before'])}\n"
                             f"SONRA: {event.get('after_full', event['after'])}")
            parts.append('SON ÇIKTI\n' + cue['final'])
            if not cue['has_history']:
                parts.insert(0, 'Bu satırda güvenilir geçiş eşlemesi yok; otomatik geri alma kapalı.')
            fill(timeline, '\n\n'.join(parts), True)
            fill(final_box, state['drafts'].get(cue['id'], cue['final']))
            values = ['İlk kayıtlı sürüm'] + [f"{i + 1}. {e['pass']} sonrası" for i, e in enumerate(cue['events'])]
            stage.configure(values=values)
            stage.set(values[0])

        def navigate(delta):
            remember()
            state['index'] = max(0, min(len(record['cues']) - 1, state['index'] + delta))
            show()

        def restore(scene=False):
            remember()
            state['drafts'] = review.restore_initial(record, state['drafts'], current()['id'], scene)
            show()
            status.configure(text='Geçmişi bulunan satırlar ilk kayıtlı sürüme alındı. Henüz dosyaya yazılmadı.')

        def use_stage():
            cue = current()
            if not cue['has_history']:
                status.configure(text='Bu satırda güvenilir geçiş eşlemesi yok.')
                return
            choice = stage.get()
            text = cue['initial'] if choice == 'İlk kayıtlı sürüm' else cue['events'][int(choice.split('.')[0]) - 1]['after_full']
            fill(final_box, text)
            remember()

        def save():
            try:
                if getattr(self, '_is_running', False):
                    raise ValueError('Çıktıyı değiştirmek için çevirinin bitmesini bekleyin.')
                remember()
                backup = review.apply_review(path, record, state['drafts'])
                state['drafts'] = {}
                status.configure(text=('Kaydedildi ve yedeklendi. Önceki kalite raporu bu düzenlemeyi kapsamaz.'
                                       if backup else 'Kaydedilecek değişiklik yok.'))
                show()
            except Exception as exc:
                status.configure(text=str(exc))

        def close():
            remember()
            dirty = any(state['drafts'].get(c['id'], c['final']) != c['final'] for c in record['cues'])
            if not dirty or messagebox.askyesno('Kaydedilmemiş değişiklik', 'Değişiklikleri kaydetmeden kapatılsın mı?', parent=dlg):
                dlg.destroy()

        ctk.CTkButton(nav, text='← Önceki', command=lambda: navigate(-1), width=110).pack(side='left', padx=8, pady=8)
        ctk.CTkButton(nav, text='Sonraki →', command=lambda: navigate(1), width=110).pack(side='left', padx=8, pady=8)
        ctk.CTkButton(nav, text='Onaylı tercih ekle', command=lambda: self._open_preferences_dialog(
            record['source_path'], record['source_language'], record['target_language'])).pack(side='right', padx=8, pady=8)
        ctk.CTkButton(dlg, text='Seçili sürümü kullan', command=use_stage).grid(row=4, column=1, sticky='ew', padx=16)
        for col, (caption, callback) in enumerate((('Satırı geri al', restore),
                ('Sahneyi geri al', lambda: restore(True)), ('Değişiklikleri kaydet', save))):
            ctk.CTkButton(buttons, text=caption, command=callback).grid(row=0, column=col, sticky='ew', padx=6, pady=8)
        dlg.protocol('WM_DELETE_WINDOW', close)
        show()
        style_window(dlg)
        return dlg

    def _open_pilot_dialog(self):
        process = self.__dict__.get('_pilot_process')
        if getattr(self, '_is_running', False) or getattr(self, '_folder_scan_busy', False) or (process and process.poll() is None):
            messagebox.showinfo('Deneme çevirisi', 'Önce mevcut işlemi tamamlayın.', parent=self)
            return
        if self.__dict__.get('_pilot_source'):
            messagebox.showinfo('Deneme çevirisi', 'Bu pencere zaten bir deneme çalışmasıdır.', parent=self)
            return
        source = self._choose_workbench_source()
        if not source:
            return
        from subtitle_translator_gui import parse_subtitle
        try:
            blocks = parse_subtitle(source, source_language=self._get_file_source_language(source))
            if not blocks:
                raise ValueError('Altyazıda işlenecek satır yok.')
        except Exception as exc:
            messagebox.showerror('Deneme çevirisi', str(exc), parent=self)
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title('Başlangıç · Orta · Son — Deneme çevirisi')
        dlg.geometry('660x480')
        dlg.minsize(540, 430)
        ctk.CTkLabel(dlg, text=Path(source).name, font=ctk.CTkFont(size=17, weight='bold')).pack(padx=16, pady=16)
        ctk.CTkLabel(dlg, text='Seçili model ve kalite ayarlarıyla ayrı bir deneme penceresi açılır.\n'
            'Yalnız örnek sahneler analiz edilir; tüm dosya bağlamının yerini tutmaz.\n'
            'API kullanımı ücretlidir. Batch seçiliyse sonuç bekleme süresi uzayabilir.', wraplength=610).pack(padx=16)
        size = ctk.CTkOptionMenu(dlg, values=['6', '12', '20', '40'])
        size.set('12')
        ctk.CTkLabel(dlg, text='Her örnekte en fazla kaç satır olsun?').pack(pady=(8, 0))
        size.pack(pady=12)
        preview = ctk.CTkTextbox(dlg, wrap='word')
        preview.pack(fill='both', expand=True, padx=16, pady=8)

        def samples(_=None):
            scenes = review.select_pilot_scenes(blocks, int(size.get()))
            preview.configure(state='normal')
            preview.delete('1.0', 'end')
            preview.insert('1.0', f'Toplam {sum(map(len, scenes))} / {len(blocks)} satır\n\n' + '\n\n'.join(
                f"Örnek {i + 1}: {scene[0][1].split('-->')[0]} — {scene[-1][1].split('-->')[-1]}\n{scene[0][2]}"
                for i, scene in enumerate(scenes)))
            preview.configure(state='disabled')
            return scenes

        def launch():
            try:
                if getattr(self, '_is_running', False):
                    raise ValueError('Ana çeviri sürerken deneme başlatılamaz.')
                self._launch_pilot(source, samples())
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror('Deneme başlatılamadı', str(exc), parent=dlg)
        size.configure(command=samples)
        ctk.CTkButton(dlg, text='Deneme penceresini hazırla', command=launch).pack(fill='x', padx=16, pady=16)
        samples()
        style_window(dlg)
        return dlg

    def _launch_pilot(self, source, scenes):
        existing = self.__dict__.get('_pilot_process')
        if (getattr(self, '_is_running', False) or getattr(self, '_folder_scan_busy', False)
                or (existing is not None and existing.poll() is None)):
            raise ValueError('Mevcut işlem tamamlanmadan ikinci bir deneme açılamaz.')
        from app_state import atomic_write_text
        # Ayarları ayrı dizine yakala: ana ayar dosyasına veya kimlik kasasına yazma.
        captured = {}
        old_path = self.__dict__.get('_settings_path')
        base = Path(self.output_var.get() or Path(source).parent) / 'Raporlar' / 'Deneme' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        state = base / 'durum'
        state.mkdir(parents=True)
        self._settings_path = lambda: state / '.gui_settings.json'
        try:
            self._save_settings(save_credentials=False)
            captured = json.loads((state / '.gui_settings.json').read_text(encoding='utf-8'))
        finally:
            if old_path is None:
                self.__dict__.pop('_settings_path', None)
            else:
                self._settings_path = old_path
        snapshot = self._take_run_snapshot()
        sample = base / 'kaynak' / (Path(source).stem + '.srt')
        sample.parent.mkdir()
        atomic_write_text(sample, '\n\n'.join(f'{i}\n{ts}\n{text}'
            for i, ts, text in [b for scene in scenes for b in scene]) + '\n', encoding='utf-8-sig')
        captured.update({'same_folder': False, 'auto_resume_crash': False, 'auto_retry_files': False,
                         'season_canon': False, 'series_memory': False, 'window_geometry': '1100x720'})
        # Otomatik sözlük önerileri onaylansa da denemenin sözlük kopyasına yazılsın.
        import shutil
        def copy_glossary(value, label):
            if not value or not Path(value).is_file():
                return value
            destination = base / (label + Path(value).suffix)
            shutil.copy2(value, destination)
            return str(destination.resolve())
        captured['glossary'] = copy_glossary(captured.get('glossary', ''), 'genel-sozluk')
        pilot_glossary = copy_glossary(self._get_file_glossary(source), 'dosya-sozlugu')
        atomic_write_json(state / '.gui_settings.json', captured)
        payload = {'source': str(Path(source).resolve()), 'sample': str(sample.resolve()),
                   'output': str((base / 'cikti').resolve()), 'snapshot': snapshot,
                   'main_key': self._main_api_key(), 'backup_key': self._main_api_key_backup(),
                   'preferences': self._approved_preferences_for(source),
                   'locked_terms': self._get_locked_terms_dict(source, self.tgt_var.get()),
                   'series_hint': self._series_hint_for(source),
                   'file_language': self._get_file_source_language(source),
                   'file_schema': self._get_file_schema(source),
                   'file_schema_name': (self._file_schema_vars[source].get()
                       if source in self._file_schema_vars else self.content_type_var.get()),
                   'file_glossary': pilot_glossary,
                   'file_depth': self._get_file_analysis_depth(source)}
        env = dict(os.environ, SUBTITLE_TRANSLATOR_STATE_DIR=str(state.resolve()))
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('pilot_runner.py'))],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._pilot_process = process

        def deliver():
            try:
                process.communicate(json.dumps(payload, ensure_ascii=False))
            except Exception:
                process.terminate()
        threading.Thread(target=deliver, daemon=True).start()
        self._log(f'Deneme penceresi hazırlanıyor: {base}', 'info')

        def check():
            code = process.poll()
            if code is None:
                self.after(1000, check)
            elif code:
                self._log(f'Deneme penceresi hata ile kapandı. Tanı kaydı: {state / "pilot_error.txt"}', 'err')
            else:
                self._log(f'Deneme penceresi kapandı. Çıktılar: {base}', 'info')
        self.after(1000, check)
