import ctypes
import os
from ctypes import wintypes


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, value: str):
        import uuid
        raw = uuid.UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


def _method(ptr, index, restype, *argtypes):
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(vtable[index])


def _release(ptr):
    if ptr:
        _method(ptr, 2, wintypes.ULONG)(ptr)


def pick_multiple_folders(owner_hwnd=0, title="Altyazı Klasörlerini Seç"):
    """Windows klasör seçicisini çoklu seçimle açar.

    Liste: seçim tamamlandı. []: kullanıcı iptal etti. None: native picker
    kullanılamadı; çağıran kod fallback uygulayabilir.
    """
    if os.name != "nt":
        return None

    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(_GUID), ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

    coinit_hr = ole32.CoInitializeEx(None, 2)
    should_uninit = coinit_hr in (0, 1)
    dialog = ctypes.c_void_p()
    items = ctypes.c_void_p()
    try:
        clsid = _GUID.from_string("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")
        iid = _GUID.from_string("D57C7288-D4AD-4768-BE02-9D969532D960")
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(dialog))
        if hr < 0 or not dialog:
            return None

        options = wintypes.DWORD()
        if _method(dialog, 10, ctypes.c_long, ctypes.POINTER(wintypes.DWORD))(
                dialog, ctypes.byref(options)) < 0:
            return None
        options.value |= 0x20 | 0x40 | 0x200  # PICKFOLDERS | FORCEFILESYSTEM | ALLOWMULTISELECT
        if _method(dialog, 9, ctypes.c_long, wintypes.DWORD)(dialog, options.value) < 0:
            return None
        _method(dialog, 17, ctypes.c_long, wintypes.LPCWSTR)(dialog, title)

        hr = _method(dialog, 3, ctypes.c_long, wintypes.HWND)(dialog, owner_hwnd or None)
        if hr < 0:
            return [] if ctypes.c_ulong(hr).value == 0x800704C7 else None

        if _method(dialog, 27, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(
                dialog, ctypes.byref(items)) < 0 or not items:
            return None

        count = wintypes.DWORD()
        if _method(items, 7, ctypes.c_long, ctypes.POINTER(wintypes.DWORD))(
                items, ctypes.byref(count)) < 0:
            return None

        selected = []
        for index in range(count.value):
            item = ctypes.c_void_p()
            try:
                if _method(items, 8, ctypes.c_long, wintypes.DWORD,
                           ctypes.POINTER(ctypes.c_void_p))(
                               items, index, ctypes.byref(item)) < 0 or not item:
                    continue
                display_name = ctypes.c_void_p()
                if _method(item, 5, ctypes.c_long, wintypes.DWORD,
                           ctypes.POINTER(ctypes.c_void_p))(
                               item, 0x80058000, ctypes.byref(display_name)) >= 0 and display_name:
                    try:
                        path = ctypes.wstring_at(display_name)
                        if path:
                            selected.append(path)
                    finally:
                        ole32.CoTaskMemFree(display_name)
            finally:
                _release(item)
        return selected
    except Exception:
        return None
    finally:
        _release(items)
        _release(dialog)
        if should_uninit:
            ole32.CoUninitialize()
