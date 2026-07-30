"""Thread-safe runtime metrics with Prometheus rendering."""
from collections import defaultdict
from threading import Lock


class MetricsCollector:
    _lock = Lock()
    _requests = defaultdict(int)
    _request_duration_ms = defaultdict(float)
    _workflows = defaultdict(int)
    _agents = defaultdict(lambda: {"count": 0, "success": 0, "duration_ms": 0.0})
    _tasks = defaultdict(int)

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._requests.clear()
            cls._request_duration_ms.clear()
            cls._workflows.clear()
            cls._agents.clear()
            cls._tasks.clear()

    @classmethod
    def observe_request(cls, method: str, path: str, status: int, duration_ms: float) -> None:
        key = (method, cls.normalize_path(path), status)
        with cls._lock:
            cls._requests[key] += 1
            cls._request_duration_ms[key] += duration_ms

    @classmethod
    def observe_workflow(cls, state: str) -> None:
        with cls._lock:
            cls._workflows[state] += 1

    @classmethod
    def observe_agent(cls, name: str, success: bool, duration_ms: float) -> None:
        with cls._lock:
            values = cls._agents[name]
            values["count"] += 1
            values["success"] += int(success)
            values["duration_ms"] += duration_ms

    @classmethod
    def observe_task(cls, status: str) -> None:
        with cls._lock:
            cls._tasks[status] += 1

    @staticmethod
    def normalize_path(path: str) -> str:
        parts = path.strip("/").split("/")
        return "/" + "/".join(
            "{id}" if part.isdigit() or part.startswith(("WF-", "TASK-", "APR-", "RUN-")) else part
            for part in parts
        )

    @classmethod
    def snapshot(cls) -> dict:
        with cls._lock:
            return {
                "requests": [
                    {
                        "method": method,
                        "path": path,
                        "status": status,
                        "count": count,
                        "average_duration_ms": round(
                            cls._request_duration_ms[(method, path, status)] / count, 3
                        ),
                    }
                    for (method, path, status), count in sorted(cls._requests.items())
                ],
                "workflows": dict(cls._workflows),
                "agents": {
                    name: {
                        **values,
                        "success_rate": (
                            values["success"] / values["count"] if values["count"] else 0
                        ),
                        "average_duration_ms": (
                            values["duration_ms"] / values["count"] if values["count"] else 0
                        ),
                    }
                    for name, values in cls._agents.items()
                },
                "tasks": dict(cls._tasks),
            }

    @classmethod
    def prometheus(cls) -> str:
        snapshot = cls.snapshot()
        lines = [
            "# HELP darwinboxai_http_requests_total HTTP requests.",
            "# TYPE darwinboxai_http_requests_total counter",
        ]
        for item in snapshot["requests"]:
            labels = (
                f'method="{item["method"]}",path="{item["path"]}",'
                f'status="{item["status"]}"'
            )
            lines.append(f"darwinboxai_http_requests_total{{{labels}}} {item['count']}")
            lines.append(
                f"darwinboxai_http_request_duration_ms_avg{{{labels}}} "
                f"{item['average_duration_ms']}"
            )
        for state, count in sorted(snapshot["workflows"].items()):
            lines.append(f'darwinboxai_workflow_transitions_total{{state="{state}"}} {count}')
        for name, values in sorted(snapshot["agents"].items()):
            lines.append(f'darwinboxai_agent_executions_total{{agent="{name}"}} {values["count"]}')
            lines.append(f'darwinboxai_agent_success_rate{{agent="{name}"}} {values["success_rate"]}')
        for status, count in sorted(snapshot["tasks"].items()):
            lines.append(f'darwinboxai_task_runs_total{{status="{status}"}} {count}')
        return "\n".join(lines) + "\n"
