import threading


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


def run_cancellable_call(call, cancel_context, poll_interval=0.05):
    if cancel_context is None:
        return call()

    done = threading.Event()
    wake = threading.Event()
    outcome = {}

    class _CallHandle:
        def close(self):
            wake.set()

    handle = _CallHandle()

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
    finally:
        cancel_context.unregister(handle)
