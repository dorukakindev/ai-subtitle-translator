import threading


DEFAULT_CANCEL_CLEANUP_SECONDS = 0.25


class RequestCancelled(RuntimeError):
    pass


class RunRequestCanceller:
    def __init__(self):
        self._cancelled = threading.Event()
        self._lock = threading.RLock()
        self._clients = {}

    def is_cancelled(self):
        return self._cancelled.is_set()

    def raise_if_cancelled(self):
        if self.is_cancelled():
            raise RequestCancelled("request cancelled")

    def register(self, client):
        with self._lock:
            self.raise_if_cancelled()
            key = id(client)
            current = self._clients.get(key)
            if current is None:
                self._clients[key] = [client, 1]
            else:
                current[1] += 1

    def unregister(self, client):
        with self._lock:
            key = id(client)
            current = self._clients.get(key)
            if current is None:
                return
            current[1] -= 1
            if current[1] <= 0:
                self._clients.pop(key, None)

    def cancel(self):
        with self._lock:
            self._cancelled.set()
            clients = [entry[0] for entry in self._clients.values()]
        for client in clients:
            try:
                client.close()
            except Exception:
                pass
        return len(clients)


class CancellableCallHandle:
    """İptal sırasında taşıma bağlantısını kapatmak için paylaşılan handle."""
    def __init__(self, wake, close_hook=None):
        self._wake = wake
        self._lock = threading.RLock()
        self._closed = False
        self._close_hooks = []
        if close_hook is not None:
            self.add_close_hook(close_hook)

    def add_close_hook(self, close_hook):
        """Bir socket/HTTP client close çağrısını güvenle iptale bağlar."""
        if not callable(close_hook):
            return False
        call_now = False
        with self._lock:
            if self._closed:
                call_now = True
            else:
                self._close_hooks.append(close_hook)
        if call_now:
            try:
                close_hook()
            except Exception:
                pass
        return True

    def close(self):
        with self._lock:
            if self._closed:
                self._wake.set()
                return
            self._closed = True
            hooks = list(self._close_hooks)
            self._close_hooks.clear()
        for hook in hooks:
            try:
                hook()
            except Exception:
                pass
        self._wake.set()


def run_cancellable_call(call, cancel_context, poll_interval=0.05,
                         transport_close=None,
                         cancel_cleanup_seconds=DEFAULT_CANCEL_CLEANUP_SECONDS):
    """Çağrıyı iptal edilebilir yürütür.

    Python iş parçacığı güvenle zorla öldürülemez. Sağlayıcı adaptörü
    ``transport_close`` ile açık socket/client ``close`` çağrısını verdiğinde
    iptal hem hemen döner hem de isteğin arka planda sürmesini engeller. Hook
    yoksa bekleme yine sınırlıdır; sonuç kesinlikle akışa geri yazılmaz.
    """
    if cancel_context is None:
        return call()

    done = threading.Event()
    wake = threading.Event()
    outcome = {}

    handle = CancellableCallHandle(wake, transport_close)

    def _worker():
        try:
            outcome["result"] = call()
        except BaseException as exc:
            outcome["error"] = exc
        finally:
            done.set()
            wake.set()

    cancel_context.register(handle)
    try:
        thread = threading.Thread(
            target=_worker, name="cancellable-provider-call", daemon=True)
        thread.start()
        while not done.is_set():
            wake.wait(poll_interval)
            cancel_context.raise_if_cancelled()
        cancel_context.raise_if_cancelled()
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("result")
    except RequestCancelled:
        # cancel() handle.close() çağırmış olabilir; doğrudan çağrı da güvenli
        # biçimde aynı kapanış yolunu kullanır. İş parçacığı yalnız kısa süre
        # beklenir, böylece bozuk sağlayıcı soketi uygulamayı kilitlemez.
        handle.close()
        try:
            cleanup = max(0.0, float(cancel_cleanup_seconds))
        except (TypeError, ValueError):
            cleanup = DEFAULT_CANCEL_CLEANUP_SECONDS
        if cleanup and not done.is_set():
            done.wait(cleanup)
        raise
    finally:
        cancel_context.unregister(handle)
