"""
Network - A High-Availability, Thread-Safe Network Connectivity Monitor for Python.

Key Features:
- Background Daemon Monitoring: Continuously probes TCP endpoints in a dedicated daemon
  thread without blocking main thread execution.
- Latency & Quality Guard: Filters connectivity based on configurable latency thresholds
  rather than simple ping responses.
- Blocking Decorator (@online): Automatically suspends network-dependent function calls
  until active connectivity is verified.
- Reconnection Jitter: Applies customizable random delay jitter upon internet recovery
  to prevent thundering herd calls.
- Multi-Provider Failover: Probes redundant DNS endpoints (Google, Cloudflare, Quad9)
  with sequential retry logic.
"""
# ========== ========== ==========


from typing import Dict, Tuple
from threading import Thread, Event
from functools import wraps
import socket
import time
import random

NUM_TRIES = 3
PORT_HTTPS = 443

PROVIDERS: Dict[str, Tuple[str, int]] = {
    "google": ("8.8.8.8", PORT_HTTPS),
    "cloudflare": ("1.1.1.1", PORT_HTTPS),
    "quad9": ("9.9.9.9", PORT_HTTPS)
}
# ========== ========== ==========


class Network:
    def __init__(
        self,
        max_latency_ms: float = 800.0,
        interval: float = 2.0,
        max_jitter_s: float = 1
    ) -> None:
        self.max_latency_ms = max_latency_ms
        self.interval = interval
        self.max_jitter_s = max_jitter_s

        self.providers = PROVIDERS
        self.online_event = Event()

        Thread(target=self._monitor_loop, daemon=True).start()
        # ========== ========== ==========


    # blocking function, used as decorator upon a function
    def online(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.online_event.wait()
            if self.max_jitter_s > 0:
                time.sleep(random.uniform(0, self.max_jitter_s))
            return func(*args, **kwargs)
        return wrapper

    # non-blocking function, ask if is online or not
    def is_online(self) -> bool:
        return self.online_event.is_set()
    # ========== ========== ==========


    def _monitor_loop(self) -> None:
        while True:
            is_ok, latency = self._ping()
            if not is_ok or latency >= self.max_latency_ms:
                self.online_event.clear()
            else:
                self.online_event.set()
            time.sleep(self.interval)

    def _ping(self) -> Tuple[bool, float]:
        for _ in range(NUM_TRIES):
            for ip, port in self.providers.values():
                try:
                    start_time = time.perf_counter()
                    with socket.create_connection((ip, port), timeout=1.5):
                        latency = (time.perf_counter() - start_time) * 1000
                        return (True, latency)
                except OSError:
                    continue
            time.sleep(1.0)
        return (False, 0.0)
    # ========== ========== ==========
