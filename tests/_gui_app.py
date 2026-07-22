"""Test-güvenli App kurucusu.

NEDEN VAR (2026-07-16, gerçek olay): App.__init__ sonunda
`self.after(500, self._check_pending_batches)` var. Bu kontrol proje kökündeki
GERÇEK `batch_id.txt`'yi okur ve yarım kalan batch bulursa modal bir pencere açar
(`grab_set()` + `focus_force()` ile odağı da çalar).

Testler bu dosyayı kullanmazsa: `python -m unittest tests.test_x` (TEK MODÜL, proje
kökünden) çalıştırıldığında `tests/` sys.path'te OLMADIĞI için `tests/customtkinter.py`
stub'ı DEVREYE GİRMEZ — gerçek customtkinter yüklenir, gerçek Tk penceresi açılır ve
App 500 ms'den uzun yaşarsa o modal pencere KULLANICININ EKRANINDA belirir. Kullanıcının
o sırada CANLI bir batch'i varsa pencere onun batch'lerini "yarım kalmış" diye listeler;
"Seçilenleri Sil" düğmesi parası ödenmiş canlı bir batch'in kurtarma verisini siler.
(`discover -s tests` ile tam paket çalışırken stub sayesinde sorun görünmez — yani bu
tuzak yalnızca tek-modül çalıştırmada patlar, tesadüfen güvenliyiz demektir.)

Bu yüzden App oluşturan HER test bunu kullanmalı: gui.App() yerine make_app(gui).
"""
import os
import tempfile
from unittest.mock import patch

from app_state import STATE_DIR_ENV


def make_app(gui):
    """Açılıştaki yarım-batch kontrolü DEVRE DIŞI bir App döner.

    Patch yalnızca __init__ boyunca aktif: `after(500, self._check_pending_batches)`
    zamanlanırken bound-method O AN çözülür, dolayısıyla zamanlanan geri-çağrı
    no-op lambda'ya bağlanır ve patch kalktıktan sonra da no-op kalır — App ne kadar
    uzun yaşarsa yaşasın pencere açılmaz."""
    temp_state = tempfile.TemporaryDirectory()
    previous = os.environ.get(STATE_DIR_ENV)
    os.environ[STATE_DIR_ENV] = temp_state.name
    try:
        with patch.object(gui.App, "_check_pending_batches", lambda self: None):
            app = gui.App()
    except Exception:
        temp_state.cleanup()
        if previous is None:
            os.environ.pop(STATE_DIR_ENV, None)
        else:
            os.environ[STATE_DIR_ENV] = previous
        raise

    original_destroy = app.destroy

    def _destroy():
        try:
            return original_destroy()
        finally:
            try:
                if getattr(app, "_log_file", None):
                    app._log_file.close()
            except Exception:
                pass
            try:
                if getattr(app, "_tm", None):
                    app._tm.close()
            except Exception:
                pass
            temp_state.cleanup()
            if previous is None:
                os.environ.pop(STATE_DIR_ENV, None)
            else:
                os.environ[STATE_DIR_ENV] = previous

    app.destroy = _destroy
    return app
