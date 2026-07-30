"""APScheduler imports with a deterministic minimal-environment fallback."""
from datetime import datetime, timedelta

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False

    class CronTrigger:
        """Small five-field cron fallback used only when dependency is unavailable."""

        def __init__(self, expression: str):
            self.expression = expression
            self.fields = expression.split()
            if len(self.fields) != 5:
                raise ValueError("Cron expression must contain five fields")
            ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
            for value, bounds in zip(self.fields, ranges):
                self._validate_field(value, *bounds)

        @classmethod
        def from_crontab(cls, expression: str):
            return cls(expression)

        @staticmethod
        def _validate_field(value: str, minimum: int, maximum: int) -> None:
            for part in value.split(","):
                base, _, step = part.partition("/")
                if step and (not step.isdigit() or int(step) < 1):
                    raise ValueError("Invalid cron step")
                if base == "*":
                    continue
                numbers = base.split("-")
                if not all(number.isdigit() for number in numbers):
                    raise ValueError("Invalid cron field")
                if any(not minimum <= int(number) <= maximum for number in numbers):
                    raise ValueError("Cron field outside valid range")

        @staticmethod
        def _matches(value: int, field: str, minimum: int) -> bool:
            for part in field.split(","):
                base, _, step_text = part.partition("/")
                step = int(step_text or 1)
                if base == "*" and (value - minimum) % step == 0:
                    return True
                if "-" in base:
                    start, end = map(int, base.split("-"))
                    if start <= value <= end and (value - start) % step == 0:
                        return True
                elif base.isdigit() and value == int(base):
                    return True
            return False

        def get_next_fire_time(self, previous_fire_time, now: datetime):
            candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
            for _ in range(60 * 24 * 366):
                values = (
                    candidate.minute,
                    candidate.hour,
                    candidate.day,
                    candidate.month,
                    (candidate.weekday() + 1) % 7,
                )
                if all(
                    self._matches(value, field, minimum)
                    for value, field, minimum in zip(
                        values, self.fields, (0, 0, 1, 1, 0)
                    )
                ):
                    return candidate
                candidate += timedelta(minutes=1)
            return None

    class BackgroundScheduler:
        """No-thread fallback; manual dispatch remains available."""

        def __init__(self, timezone=None):
            self.running = False
            self.jobs = {}

        def add_job(self, function, trigger, **kwargs):
            self.jobs[kwargs.get("id", str(len(self.jobs)))] = function

        def start(self):
            self.running = True

        def shutdown(self, wait=False):
            self.running = False
