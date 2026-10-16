from datetime import datetime, timezone

START_TIME_FORMAT = "%Y-%m-%d-%H:%M"


def normalise_start_time(start_time: str) -> str:
    return "-".join(start_time.split()).replace("[", "").replace("]", "")


def parse_start_time(start_time: str) -> datetime:
    return datetime.strptime(start_time, START_TIME_FORMAT).replace(tzinfo=timezone.utc)
