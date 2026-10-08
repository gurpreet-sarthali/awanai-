"""AI request rate limiting — global and per-user.

Phase 14: Added per-user rate limiting to prevent single users from
monopolising AI capacity.
"""

from __future__ import annotations

import time
from collections import deque, defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock


class AIRateLimitError(RuntimeError):
    pass


class AIRateLimiter:
    """Global + per-user sliding-window rate limiter."""

    def __init__(self, per_minute: int = 10, per_day: int = 100) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        # Global counters
        self._global_timestamps: deque[datetime] = deque()
        self._global_lock = Lock()
        # Per-user counters
        self._user_timestamps: defaultdict[str, deque[datetime]] = defaultdict(deque)
        self._user_lock = Lock()

    def check(self, user_id: str | None = None) -> None:
        """Check and record a new AI request.

        Raises AIRateLimitError if any limit is breached.
        user_id: optional identifier for per-user limiting.
        """
        now = datetime.now(timezone.utc)

        # ── Global limit ─────────────────────────────────────────────────────
        with self._global_lock:
            self._purge(self._global_timestamps, now, timedelta(days=1))
            minute_count = sum(
                ts >= now - timedelta(minutes=1) for ts in self._global_timestamps
            )
            if minute_count >= self.per_minute:
                raise AIRateLimitError(
                    "Global AI request limit reached. Please try again in a moment."
                )
            if len(self._global_timestamps) >= self.per_day:
                raise AIRateLimitError(
                    "Daily AI request limit reached. Please try again tomorrow."
                )
            self._global_timestamps.append(now)

        # ── Per-user limit (half of global per-user) ─────────────────────────
        if user_id:
            user_per_minute = max(1, self.per_minute // 2)
            user_per_day = max(1, self.per_day // 2)
            with self._user_lock:
                user_ts = self._user_timestamps[user_id]
                self._purge(user_ts, now, timedelta(days=1))
                user_minute = sum(ts >= now - timedelta(minutes=1) for ts in user_ts)
                if user_minute >= user_per_minute:
                    raise AIRateLimitError(
                        "You are sending AI requests too quickly. Please wait a moment."
                    )
                if len(user_ts) >= user_per_day:
                    raise AIRateLimitError(
                        "Your daily AI request limit has been reached."
                    )
                user_ts.append(now)

    @staticmethod
    def _purge(timestamps: deque[datetime], now: datetime, window: timedelta) -> None:
        while timestamps and timestamps[0] < now - window:
            timestamps.popleft()


class LoginAttemptLimiter:
    """Limit repeated failed sign-ins for one email and client pair."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900, max_identities: int = 10_000) -> None:
        self.max_attempts = max(0, max_attempts)
        self.window_seconds = max(1, window_seconds)
        self.max_identities = max(1, max_identities)
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, identity: str) -> None:
        if self.max_attempts == 0:
            return
        now = time.monotonic()
        with self._lock:
            failures = self._failures.get(identity)
            if failures is None:
                return
            self._purge(failures, now)
            if len(failures) >= self.max_attempts:
                raise AIRateLimitError("Too many failed sign-in attempts. Please try again later.")

    def record_failure(self, identity: str) -> None:
        if self.max_attempts == 0:
            return
        now = time.monotonic()
        with self._lock:
            failures = self._failures.get(identity)
            if failures is None:
                if len(self._failures) >= self.max_identities:
                    for known_identity, known_failures in list(self._failures.items()):
                        self._purge(known_failures, now)
                        if not known_failures:
                            self._failures.pop(known_identity, None)
                    if len(self._failures) >= self.max_identities:
                        self._failures.pop(next(iter(self._failures)))
                failures = self._failures.setdefault(identity, deque())
            self._purge(failures, now)
            failures.append(now)

    def reset(self, identity: str) -> None:
        with self._lock:
            self._failures.pop(identity, None)

    def _purge(self, failures: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()