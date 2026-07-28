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
