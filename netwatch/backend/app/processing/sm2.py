"""SM-2 spaced repetition (quality 0-5). Pure function, unit tested."""
from datetime import date, timedelta


def review(ease: float, interval: int, reps: int, quality: int, today: date | None = None):
    today = today or date.today()
    if quality < 3:
        reps, interval = 0, 1
    else:
        interval = 1 if reps == 0 else 6 if reps == 1 else round(interval * ease)
        reps += 1
    ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return round(ease, 3), interval, reps, (today + timedelta(days=interval)).isoformat()
