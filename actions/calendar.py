import json
from datetime import datetime
from pathlib import Path
import sys


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


CALENDAR_FILE = _base_dir() / "config" / "calendar.json"


def _ensure_calendar_file() -> None:
    CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CALENDAR_FILE.exists():
        CALENDAR_FILE.write_text("[]", encoding="utf-8")


def _read_calendar() -> list[dict]:
    try:
        _ensure_calendar_file()
        data = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        cleaned = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "Untitled")).strip()
            if not title:
                continue
            date = str(item.get("date", "")).strip()
            time_ = str(item.get("time", "09:00")).strip() or "09:00"
            try:
                datetime.strptime(f"{date} {time_}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            cleaned.append({
                "id": str(item.get("id") or f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(cleaned)}"),
                "title": title,
                "date": date,
                "time": time_,
                "duration_minutes": int(item.get("duration_minutes", 60) or 60),
                "notes": str(item.get("notes", "")).strip(),
                "location": str(item.get("location", "")).strip(),
                "created_at": str(item.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            })
        return cleaned
    except Exception:
        return []


def _write_calendar(events: list[dict]) -> None:
    _ensure_calendar_file()
    CALENDAR_FILE.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


def list_events(limit: int = 20, include_past: bool = False) -> list[dict]:
    events = _read_calendar()
    now = datetime.now()
    out = []
    for event in events:
        dt = datetime.strptime(f"{event['date']} {event['time']}", "%Y-%m-%d %H:%M")
        if include_past or dt >= now:
            out.append(event)
    out.sort(key=lambda e: f"{e['date']} {e['time']}")
    return out[:limit]


def upcoming_events(limit: int = 5) -> list[dict]:
    return list_events(limit=limit, include_past=False)


def get_calendar_status_message(as_speech: bool = False) -> str:
    events = upcoming_events(limit=3)
    if not events:
        return "There are no upcoming calendar appointments." if as_speech else "No upcoming appointments."

    # speech-friendly summary
    if as_speech:
        first = events[0]
        date_text = datetime.strptime(f"{first['date']} {first['time']}", "%Y-%m-%d %H:%M").strftime("%A, %d %B at %H:%M")
        if len(events) == 1:
            return f"You have one upcoming appointment: {first['title']} on {date_text}."
        second = events[1]
        second_text = datetime.strptime(f"{second['date']} {second['time']}", "%Y-%m-%d %H:%M").strftime("%A, %d %B at %H:%M")
        return f"You have {len(events)} upcoming appointments, starting with {first['title']} on {date_text} and then {second['title']} on {second_text}."

    if len(events) == 1:
        return f"1 upcoming appointment: {events[0]['title']} ({events[0]['date']} {events[0]['time']})"
    return f"{len(events)} upcoming appointments: " + ", ".join(f"{e['title']} ({e['date']} {e['time']})" for e in events)


def add_event(title: str, date: str, time_: str, duration_minutes: int = 60, notes: str = "", location: str = "") -> str:
    if not title.strip():
        return "I need a title for the appointment."
    try:
        datetime.strptime(f"{date} {time_}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "Please use date as YYYY-MM-DD and time as HH:MM."

    events = _read_calendar()
    event = {
        "id": f"evt-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "title": title.strip(),
        "date": date.strip(),
        "time": time_.strip(),
        "duration_minutes": max(15, int(duration_minutes or 60)),
        "notes": notes.strip(),
        "location": location.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    events.append(event)
    events.sort(key=lambda e: f"{e['date']} {e['time']}")
    _write_calendar(events)
    return f"Appointment added: {event['title']} on {event['date']} at {event['time']}."


def remove_event(event_id: str) -> str:
    events = _read_calendar()
    filtered = [e for e in events if e.get("id") != str(event_id)]
    if len(filtered) == len(events):
        return "I couldn't find that appointment ID."
    _write_calendar(filtered)
    return "Appointment removed."


def calendar(parameters: dict, response=None, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "list").strip().lower()

    if action in {"add", "create", "new"}:
        return add_event(
            title=parameters.get("title", ""),
            date=parameters.get("date", ""),
            time_=parameters.get("time", "09:00"),
            duration_minutes=parameters.get("duration_minutes", 60),
            notes=parameters.get("notes", ""),
            location=parameters.get("location", ""),
        )

    if action in {"remove", "delete", "cancel"}:
        return remove_event(parameters.get("id", ""))

    if action in {"next", "upcoming", "soon"}:
        events = upcoming_events(limit=int(parameters.get("limit", 5) or 5))
        if not events:
            return "You have no upcoming appointments."
        lines = [
            f"{i + 1}. {event['title']} — {event['date']} {event['time']}"
            + (f" @ {event['location']}" if event['location'] else "")
            for i, event in enumerate(events)
        ]
        return "\n".join(lines)

    if action in {"list", "show", "all"}:
        events = list_events(limit=int(parameters.get("limit", 20) or 20), include_past=bool(parameters.get("include_past", False)))
        if not events:
            return "There are no calendar entries yet."
        lines = [
            f"{i + 1}. {event['title']} — {event['date']} {event['time']}"
            + (f" @ {event['location']}" if event['location'] else "")
            for i, event in enumerate(events)
        ]
        return "\n".join(lines)

    return "Calendar action unknown. Use add, list, upcoming, or remove."


TOOL = {
    "name": "calendar",
    "description": "Manage a personal calendar for appointments and upcoming events. Add, list, show upcoming, or remove entries.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: add, list, upcoming, remove"
            },
            "title": {
                "type": "STRING",
                "description": "Appointment title"
            },
            "date": {
                "type": "STRING",
                "description": "Date in YYYY-MM-DD format"
            },
            "time": {
                "type": "STRING",
                "description": "Time in HH:MM format"
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Appointment duration in minutes, default 60"
            },
            "notes": {
                "type": "STRING",
                "description": "Optional notes"
            },
            "location": {
                "type": "STRING",
                "description": "Optional location"
            },
            "limit": {
                "type": "INTEGER",
                "description": "How many results to return for list/upcoming"
            },
            "id": {
                "type": "STRING",
                "description": "Calendar event ID to remove"
            }
        },
        "required": ["action"]
    },
    "handler": calendar,
}
