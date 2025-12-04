from datetime import datetime

class EventBlackout:
    def __init__(self, events, window_minutes=60):
        self.events = events
        self.window = window_minutes * 60

    def is_allowed(self):
        now = datetime.utcnow().timestamp()
        for event_time in self.events:
            if abs(now - event_time) <= self.window:
                return False
        return True
