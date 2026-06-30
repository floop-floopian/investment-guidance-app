import json
from pathlib import Path
from src.models.state_log import StateLogEntry
from src.config.settings import get_settings


def _get_log_path() -> Path:
    path = get_settings().state_log_path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_entry(entry: StateLogEntry) -> None:
    """Atomically append one StateLogEntry as a JSON line to the NDJSON log file."""
    line = entry.model_dump_json() + "\n"
    log_path = _get_log_path()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def read_entries(
    last_n: int | None = None,
    run_id: str | None = None,
    action_type: str | None = None,
) -> list[StateLogEntry]:
    """Read and filter entries from the NDJSON log file."""
    log_path = _get_log_path()
    if not log_path.exists():
        return []

    entries: list[StateLogEntry] = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entry = StateLogEntry.model_validate(data)
                if run_id and entry.run_id != run_id:
                    continue
                if action_type and entry.action.value != action_type:
                    continue
                entries.append(entry)
            except Exception:
                continue

    if last_n is not None:
        entries = entries[-last_n:]
    return entries
