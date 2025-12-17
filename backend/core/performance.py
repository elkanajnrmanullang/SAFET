import time
from collections import deque

class PerformanceMonitor:

    def __init__(self, max_history=200):
        self.history = deque(maxlen=max_history)

    def start(self):
        return time.time()

    def stop(self, start_time, status: str):
        latency = time.time() - start_time

        self.history.append({
            "latency": latency,
            "status": status,
            "timestamp": time.time()
        })
        return latency

    # METRICS SUMMARY
    def summary(self):
        if not self.history:
            return {"status": "no-data"}

        total = len(self.history)
        success = sum(1 for h in self.history if h["status"] == "success")
        fail = total - success
        avg_latency = sum(h["latency"] for h in self.history) / total

        return {
            "total_runs": total,
            "success_rate": round(success / total, 4),
            "fail_rate": round(fail / total, 4),
            "avg_latency": round(avg_latency, 4),
            "last_latency": round(self.history[-1]["latency"], 4),
        }


perf_monitor = PerformanceMonitor()
