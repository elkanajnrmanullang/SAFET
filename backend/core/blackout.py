"""
Event blackout guard.
Mengunci trading +/- window_minutes (default 60) di sekitar event timestamps.

events can be:
- list of epoch timestamps (ints/floats)
- list of dicts with "timestamp" key (epoch)
"""
from datetime import datetime, timezone
from typing import Iterable, Union


class EventBlackout:
    def __init__(self, events: Iterable[Union[int, float, dict]] = None, window_minutes: int = 60):
        """
        events: iterable of epoch timestamps (seconds) OR dicts containing 'timestamp' key (seconds)
        window_minutes: window on each side of event (minutes)
        """
        self.window_seconds = max(1, window_minutes) * 60
        self.events = []
        if events:
            for e in events:
                t = self._extract_timestamp(e)
                if t:
                    self.events.append(t)

    def _extract_timestamp(self, item):
        try:
            if isinstance(item, (int, float)):
                return float(item)
            if isinstance(item, dict):
                if "timestamp" in item:
                    return float(item["timestamp"])
                # support iso string
                if "time" in item:
                    try:
                        return float(item["time"])
                    except Exception:
                        # try parse iso
                        dt = datetime.fromisoformat(item["time"])
                        return dt.replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            return None
        return None

    def is_allowed(self) -> bool:
        """
        Return True if current utc time is NOT within any blackout windows.
        """
        now = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()
        for ev in self.events:
            if abs(now - ev) <= self.window_seconds:
                return False
        return True

    def add_event(self, event: Union[int, float, dict]):
        t = self._extract_timestamp(event)
        if t:
            self.events.append(t)

    def clear_events(self):
        self.events = []


# quick self-test
if __name__ == "__main__":
    import time
    now = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()
    eb = EventBlackout(events=[now + 30], window_minutes=1)
    print("Allowed (should be False):", eb.is_allowed())
    eb.clear_events()
    print("Allowed (should be True):", eb.is_allowed())