"""Tests for is_source_likely_turkish preflight."""
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import subtitle_translator_gui as gui

_TR_TEXT = (
    "Burası New York'un en büyük mahallelerinden biri. Great Neck'te"
    " bir sürü güzel ev var. Bu akşam oraya gideceğiz ve harika"
    " bir akşam yemeği yiyeceğiz. Sonra da şehir merkezinde"
    " dolaşacağız. Bu arada, dedektif yeni bir ipucu buldu."
    " Ona göre katil çok yakında olabilir. Şimdi harekete geçmeliyiz."
    " Polis her yeri aradı ama hiçbir şey bulamadı."
)

_EN_TEXT = (
    "This is one of the largest neighborhoods in New York. There are"
    " many beautiful houses in Great Neck. Tonight we will go there"
    " and have a wonderful dinner. Then we will walk around downtown."
    " Meanwhile, the detective found a new clue. According to him,"
    " the killer might be very close. We must act now."
    " The police searched everywhere but found nothing."
)


class PreflightTurkishTest(unittest.TestCase):

    def test_filename_tr_srt_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Capturing..._tr.srt")
        )

    def test_filename_dot_tr_srt_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show.S01E01.Tr.srt")
        )

    def test_filename_turkish_word_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show Turkish.srt")
        )

    def test_filename_turkce_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show Türkçe.srt")
        )

    def test_english_content_not_detected(self):
        self.assertFalse(
            ht.is_source_likely_turkish(text=_EN_TEXT, filename="Show.S01E01.en.srt")
        )

    def test_english_content_no_filename_not_detected(self):
        self.assertFalse(
            ht.is_source_likely_turkish(text=_EN_TEXT)
        )

    def test_turkish_content_with_place_names_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(text=_TR_TEXT, filename="Show.S01E01.en.srt")
        )

    def test_turkish_content_no_filename_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(text=_TR_TEXT)
        )

    def test_empty_text_not_detected(self):
        self.assertFalse(
            ht.is_source_likely_turkish(filename="Show.S01E01.srt")
        )

    def test_short_text_not_enough_content(self):
        self.assertFalse(
            ht.is_source_likely_turkish(text="Merhaba nasılsın")
        )

    def test_filename_signal_with_empty_text_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show_turkish.srt")
        )

    def test_mixed_text_more_english_than_turkish_not_detected(self):
        mixed = (
            "This is mostly English text with just a few Turkish words like"
            " merhaba and teşekkürler. The rest of this paragraph is entirely"
            " in English so that the overall ratio of Turkish content stays"
            " very low. We want to make sure that lightweight Turkish token"
            " presence does not accidentally trigger the preflight detector."
            " There is absolutely nothing in this text that suggests a full"
            " Turkish subtitle file. It is just an English sentence with a"
            " couple of Turkish loanwords thrown in for testing purposes."
            " The great majority of the words here are plain English words."
        )
        self.assertFalse(
            ht.is_source_likely_turkish(text=mixed)
        )

    def _preflight_stub(self, signature_fn):
        resumed = []
        states = []
        return SimpleNamespace(
            _turkish_source_preflight_signature=None,
            _stop_flag=False,
            _is_shutting_down=False,
            _worker_lock=threading.Lock(),
            _worker_threads=set(),
            _ui_queue=queue.Queue(),
            _file_preflight_signature=signature_fn,
            _get_srt_files=lambda: ["episode.srt"],
            _set_phase=lambda *_args: None,
            _set_status=lambda *_args: None,
            _set_running=lambda running: states.append(running),
            _log=lambda *_args, **_kwargs: None,
            _start=lambda: None,
            after_idle=lambda fn: resumed.append(fn),
            _preflight_resumed=resumed,
            _running_states=states,
        )

    @staticmethod
    def _drain_worker_ui(stub):
        fn, args, kwargs = stub._ui_queue.get_nowait()
        fn(*args, **kwargs)

    def test_gui_turkish_preflight_reads_disk_on_worker_and_caches_clean_result(self):
        signature = ("clean",)
        stub = self._preflight_stub(lambda _files: signature)
        started = threading.Event()
        release = threading.Event()
        read_threads = []

        def slow_read(_path):
            read_threads.append(threading.current_thread())
            started.set()
            release.wait(1)
            return _EN_TEXT

        with mock.patch("subtitle_translator_gui.read_subtitle_text", slow_read):
            self.assertTrue(gui.App._start_turkish_source_preflight(
                stub, ["episode.srt"]))
            self.assertTrue(started.wait(1))
            self.assertIsNot(read_threads[0], threading.main_thread())
            release.set()
            for worker in list(stub._worker_threads):
                worker.join(1)

        self._drain_worker_ui(stub)
        self.assertEqual(stub._turkish_source_preflight_signature, signature)
        self.assertEqual(stub._running_states, [False])
        self.assertEqual(len(stub._preflight_resumed), 1)
        self.assertFalse(gui.App._start_turkish_source_preflight(
            stub, ["episode.srt"]))

    def test_gui_turkish_preflight_drops_stale_worker_result(self):
        current_signature = [("original",)]
        stub = self._preflight_stub(lambda _files: current_signature[0])

        with mock.patch("subtitle_translator_gui.read_subtitle_text", return_value=_TR_TEXT):
            self.assertTrue(gui.App._start_turkish_source_preflight(
                stub, ["episode.srt"]))
            for worker in list(stub._worker_threads):
                worker.join(1)

        current_signature[0] = ("new-selection",)
        with mock.patch("subtitle_translator_gui.messagebox.showerror") as show_error:
            self._drain_worker_ui(stub)

        show_error.assert_not_called()
        self.assertIsNone(stub._turkish_source_preflight_signature)
        self.assertEqual(stub._running_states, [False])
        self.assertEqual(len(stub._preflight_resumed), 1)


if __name__ == "__main__":
    unittest.main()
