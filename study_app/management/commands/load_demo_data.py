from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from study_app.models import (
	Exam,
	Flashcard,
	Reminder,
	StudyGoal,
	StudyNote,
	StudySession,
	StudyTask,
	Subject,
)


class Command(BaseCommand):
	help = 'Add sample study data to one user account.'

	def add_arguments(self, parser):
		parser.add_argument(
			'--username',
			help='Account that will own the demo data (required if multiple accounts exist).',
		)

	@transaction.atomic
	def handle(self, *args, **options):
		User = get_user_model()
		if options['username']:
			user = User.objects.filter(username=options['username']).first()
			if user is None:
				raise CommandError(f"User '{options['username']}' does not exist.")
		else:
			users = list(User.objects.order_by('pk')[:2])
			if len(users) != 1:
				raise CommandError(
					'Specify --username to choose which account owns the demo data.'
				)
			user = users[0]

		today = timezone.localdate()
		StudyGoal.objects.get_or_create(
			user=user,
			defaults={'weekly_minutes': 300, 'daily_minutes': 30},
		)
		subject_data = (
			{
				'name': 'Mathematics',
				'category': 'STEM',
				'description': 'Algebra, functions, and practice problems.',
				'priority': Subject.Priority.HIGH,
				'study_hours': 8.0,
				'weekly_goal_hours': 4.0,
				'color': Subject.Color.BLUE,
			},
			{
				'name': 'Biology',
				'category': 'STEM',
				'description': 'Cell structure, genetics, and human physiology.',
				'priority': Subject.Priority.MEDIUM,
				'study_hours': 5.5,
				'weekly_goal_hours': 3.5,
				'color': Subject.Color.TEAL,
			},
			{
				'name': 'History',
				'category': 'Humanities',
				'description': 'Review key events, timelines, and source analysis.',
				'priority': Subject.Priority.LOW,
				'study_hours': 3.0,
				'weekly_goal_hours': 2.5,
				'color': Subject.Color.AMBER,
			},
			{
				'name': 'Physics',
				'category': 'STEM',
				'description': 'Mechanics, energy, and exam-style problem solving.',
				'priority': Subject.Priority.HIGH,
				'study_hours': 6.5,
				'weekly_goal_hours': 4.0,
				'color': Subject.Color.VIOLET,
			},
			{
				'name': 'Computer Science',
				'category': 'Technology',
				'description': 'Algorithms, Python fundamentals, and data structures.',
				'priority': Subject.Priority.MEDIUM,
				'study_hours': 4.0,
				'weekly_goal_hours': 3.5,
				'color': Subject.Color.ROSE,
			},
		)
		subjects = {}
		for defaults in subject_data:
			subject, _ = Subject.objects.get_or_create(
				user=user,
				name=defaults['name'],
				defaults={key: value for key, value in defaults.items() if key != 'name'},
			)
			subjects[subject.name] = subject

		task_data = (
			('Complete algebra practice set', 'Mathematics', True, -1, StudyTask.Priority.HIGH),
			('Review quadratic equations', 'Mathematics', False, 1, StudyTask.Priority.HIGH),
			('Make a formula revision sheet', 'Mathematics', False, 4, StudyTask.Priority.MEDIUM),
			('Label the cell diagram', 'Biology', True, -2, StudyTask.Priority.MEDIUM),
			('Review genetics flashcards', 'Biology', False, 3, StudyTask.Priority.HIGH),
			('Summarize the causes of World War I', 'History', True, -3, StudyTask.Priority.LOW),
			('Prepare a timeline of key events', 'History', False, 6, StudyTask.Priority.MEDIUM),
			('Solve forces and motion questions', 'Physics', False, 2, StudyTask.Priority.HIGH),
			('Revise energy transfer diagrams', 'Physics', True, -1, StudyTask.Priority.MEDIUM),
			('Trace a sorting algorithm by hand', 'Computer Science', False, 5, StudyTask.Priority.HIGH),
			('Write tests for a Python function', 'Computer Science', False, 8, StudyTask.Priority.MEDIUM),
		)
		for title, subject_name, completed, days_until_due, priority in task_data:
			StudyTask.objects.get_or_create(
				user=user,
				title=title,
				subject=subjects[subject_name],
				defaults={
					'completed': completed,
					'due_date': today + timedelta(days=days_until_due),
					'priority': priority,
				},
			)

		exam_data = (
			('Mathematics midterm', 'Mathematics', 7),
			('Biology unit test', 'Biology', 14),
			('History essay assessment', 'History', 21),
			('Physics mechanics quiz', 'Physics', 10),
			('Computer Science programming test', 'Computer Science', 18),
		)
		for title, subject_name, days_until_exam in exam_data:
			exam = Exam.objects.filter(
				user=user,
				title=title,
				subject=subjects[subject_name],
			).order_by('date').first()
			if exam is None:
				Exam.objects.create(
					user=user,
					title=title,
					date=today + timedelta(days=days_until_exam),
					subject=subjects[subject_name],
				)

		reminder_data = (
			('Review formulas and practice key problems', 'Mathematics', 2, 'Revise the formula sheet and solve a few mixed problems.'),
			('Revise genetics diagrams and key terms', 'Biology', 26, 'Review inheritance patterns and redraw a cell diagram from memory.'),
			('Outline history essay evidence', 'History', 50, 'Choose strong examples and organize them into a short outline.'),
		)
		for title, subject_name, hours_from_now, note in reminder_data:
			exam = Exam.objects.filter(
				user=user,
				subject=subjects[subject_name],
				date__gte=today,
			).order_by('date').first()
			Reminder.objects.get_or_create(
				user=user,
				title=title,
				defaults={
					'remind_at': timezone.now() + timedelta(hours=hours_from_now),
					'note': note,
					'exam': exam,
				},
			)

		session_data = (
			('Mathematics', 50, 0, 'Practiced quadratic equations, checked solutions by substitution, and noted two recurring mistakes.'),
			('Biology', 40, 1, 'Reviewed cell structures from memory, then corrected a labeled diagram.'),
			('History', 35, 2, 'Built a timeline and compared the perspective of two historical sources.'),
			('Physics', 45, 3, 'Solved mechanics questions and wrote down the units for each equation.'),
			('Computer Science', 50, 4, 'Traced a sorting algorithm and tested a small Python implementation.'),
			('Mathematics', 30, 5, 'Used flashcards to retrieve formulas and worked two timed examples.'),
			('Biology', 25, 6, 'Recalled the stages of mitosis without notes and checked the sequence.'),
			('History', 40, 7, 'Reviewed key causes and separated source evidence from inference.'),
			('Physics', 35, 8, 'Revised energy transfers and explained each diagram aloud.'),
			('Computer Science', 45, 9, 'Practiced tracing loops and wrote tests for edge cases.'),
			('Mathematics', 35, 10, 'Revisited incorrect algebra questions and corrected each working step.'),
			('Biology', 30, 11, 'Reviewed genetics vocabulary with spaced flashcard practice.'),
		)
		for subject_name, minutes, days_ago, notes in session_data:
			if not StudySession.objects.filter(user=user, notes=notes).exists():
				StudySession.objects.create(
					user=user,
					subject=subjects[subject_name],
					date=today - timedelta(days=days_ago),
					duration_minutes=minutes,
					notes=notes,
				)

		flashcard_data = (
			('Mathematics', 'What is the quadratic formula?', 'For ax² + bx + c = 0: x = (-b ± √(b² - 4ac)) / 2a.'),
			('Mathematics', 'What does the gradient of a straight line measure?', 'The change in y divided by the change in x: rise over run.'),
			('Biology', 'What is the function of the cell membrane?', 'It controls which substances enter and leave the cell.'),
			('Biology', 'Where does photosynthesis take place?', 'In the chloroplasts, using chlorophyll to capture light energy.'),
			('History', 'What is a primary historical source?', 'Evidence created during the period being studied, such as a letter or photograph.'),
			('History', 'Why compare multiple historical sources?', 'To identify different perspectives, corroborate evidence, and assess reliability.'),
			('Physics', 'What does the gradient of a distance-time graph represent?', 'The speed of the object during that part of its journey.'),
			('Physics', 'How do you calculate work done?', 'Work done equals force multiplied by distance moved in the direction of the force.'),
			('Computer Science', 'What is an algorithm?', 'A finite, ordered set of steps used to solve a problem or complete a task.'),
			('Computer Science', 'Why use a test case with an empty list?', 'It checks how an algorithm handles a boundary case with no input items.'),
		)
		for subject_name, front, back in flashcard_data:
			Flashcard.objects.get_or_create(
				user=user,
				subject=subjects[subject_name],
				front=front,
				defaults={'back': back},
			)

		note_data = (
			('Mathematics', 'Quadratic equations: quick revision', 'Put the equation in ax² + bx + c = 0 form. Try factorising first; if that does not work, use the quadratic formula. Check solutions by substitution.'),
			('Biology', 'Cell structure essentials', 'The nucleus stores DNA. The cell membrane controls exchange. Mitochondria release energy through respiration. Plant cells also have a cell wall, chloroplasts, and a large permanent vacuole.'),
			('History', 'Evaluating a historical source', 'Identify who created it, when and why. Separate what it directly shows from what you infer, then compare it with another source before drawing a conclusion.'),
			('Physics', 'Mechanics: problem checklist', 'Write down known values with units. Choose the relevant relationship, rearrange before substituting, calculate carefully, and check that the answer has a sensible unit and size.'),
			('Computer Science', 'Python testing reminders', 'Test a typical input, a boundary value, and an invalid or empty input where appropriate. Compare the actual result with the expected result and keep tests small and descriptive.'),
		)
		for subject_name, title, content in note_data:
			StudyNote.objects.get_or_create(
				user=user,
				title=title,
				defaults={'subject': subjects[subject_name], 'content': content},
			)

		self.stdout.write(
			self.style.SUCCESS(
				'Demo data is ready: 5 subjects, 11 tasks, 5 exams, 12 study sessions, '
				'10 flashcards, 5 notes, 3 reminders, and a weekly study goal '
				'(existing matching records were kept).'
			)
		)
