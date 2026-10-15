from datetime import datetime, timedelta


PRIORITY_RANK = {'high': 0, 'medium': 1, 'low': 2}
DIFFICULTY_RANK = {'hard': 0, 'medium': 1, 'easy': 2}


def build_daily_plan(tasks, today, available_minutes, start_time):
	"""Schedule unfinished tasks, moving subjects with exams in the next week up first."""
	def upcoming_exam_date(task):
		exam_date = getattr(task, 'upcoming_exam_date', None)
		if exam_date is None and task.subject_id and task.subject.exam_date:
			exam_date = task.subject.exam_date
		return exam_date if exam_date and exam_date >= today else None

	def task_sort_key(task):
		exam_date = upcoming_exam_date(task)
		days_until_exam = (exam_date - today).days if exam_date else None
		exam_is_soon = days_until_exam is not None and days_until_exam <= 7
		return (
			0 if exam_is_soon else 1,
			days_until_exam if exam_is_soon else 36500,
			0 if task.due_date and task.due_date < today else 1,
			task.due_date or today + timedelta(days=36500),
			PRIORITY_RANK.get(task.priority, 1),
			DIFFICULTY_RANK.get(task.difficulty, 1),
			task.title.casefold(),
		)

	tasks = sorted(tasks, key=task_sort_key)

	minutes_left = max(available_minutes, 0)
	cursor = datetime.combine(today, start_time)
	blocks = []
	for task in tasks:
		if minutes_left == 0:
			break

		duration = min(task.estimated_minutes, minutes_left)
		block_start = cursor
		cursor += timedelta(minutes=duration)
		minutes_left -= duration
		exam_date = upcoming_exam_date(task)
		blocks.append({
			'task': task,
			'start': block_start.time(),
			'end': cursor.time(),
			'minutes': duration,
			'is_rescheduled': bool(task.due_date and task.due_date < today),
			'is_partial': duration < task.estimated_minutes,
			'upcoming_exam_date': exam_date,
			'days_until_exam': (exam_date - today).days if exam_date else None,
			'is_exam_urgent': bool(exam_date and (exam_date - today).days <= 7),
		})

	return blocks
