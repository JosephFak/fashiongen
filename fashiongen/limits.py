"""Small, single-process usage guard for the public portfolio demo."""

from collections import deque
import math
import time


class UsageLimitError(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after


class UsageLimiter:
    """Rolling hourly/daily limits across all visitors; failed attempts count too.

    Counters reset on process restart. Use provider spending controls as well,
    and replace this with shared durable storage before using multiple replicas.
    """

    def __init__(self, hourly, daily, clock=time.monotonic):
        self.hourly = hourly
        self.daily = daily
        self.clock = clock
        self.hour = deque()
        self.day = deque()

    def consume(self):
        now = self.clock()
        for events, duration in ((self.hour, 3600), (self.day, 86400)):
            while events and events[0] <= now - duration:
                events.popleft()
        waits = []
        for events, limit, duration in ((self.hour, self.hourly, 3600), (self.day, self.daily, 86400)):
            if len(events) >= limit:
                waits.append(events[0] + duration - now)
        if waits:
            raise UsageLimitError(max(1, math.ceil(max(waits))))
        self.hour.append(now)
        self.day.append(now)
