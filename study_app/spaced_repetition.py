from datetime import timedelta
from decimal import Decimal


MIN_EASE = Decimal('1.30')
MAX_EASE = Decimal('3.00')
MAX_INTERVAL_DAYS = 65535


def schedule_next_review(interval_days, ease_factor, remembered, today):
	"""Return the next interval, ease score, and review date for a flashcard."""
	ease = Decimal(ease_factor)
	if remembered:
		if interval_days == 0:
			interval = 1
		elif interval_days == 1:
			interval = 6
		else:
			interval = round(interval_days * ease)
		ease = min(ease + Decimal('0.10'), MAX_EASE)
	else:
		interval = 1
		ease = max(ease - Decimal('0.20'), MIN_EASE)

	interval = min(max(interval, 1), MAX_INTERVAL_DAYS)
	return interval, ease, today + timedelta(days=interval)
