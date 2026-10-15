from datetime import date, datetime, time, timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Exam, Flashcard, Reminder, StudyNote, StudySession, StudyTask, Subject


class WorkspaceTestCase(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='workspaceuser',
			password='StrongPassword123!',
		)
		self.client.force_login(self.user)


class HomeViewTests(WorkspaceTestCase):
	def test_workspace_pages_require_login(self):
		self.client.logout()

		for url in (
			'/dashboard/',
			'/subjects/',
			'/tasks/',
			'/exams/',
			'/reminders/add/',
			'/progress/',
			'/planner/',
			'/learning/',
			'/calendar/',
		):
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertRedirects(response, f'/login/?next={url}')

	def test_users_cannot_view_or_change_another_users_records(self):
		other_user = User.objects.create_user(
			username='anotheruser',
			password='StrongPassword123!',
		)
		subject = Subject.objects.create(user=other_user, name='Private biology')
		task = StudyTask.objects.create(
			user=other_user,
			title='Private revision',
			subject=subject,
		)
		exam = Exam.objects.create(
			user=other_user,
			title='Private exam',
			date=timezone.localdate() + timedelta(days=3),
			subject=subject,
		)

		for url in ('/dashboard/', '/subjects/', '/tasks/', '/exams/', '/progress/', '/learning/', '/calendar/'):
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertNotContains(response, 'Private biology')
				self.assertNotContains(response, 'Private revision')
				self.assertNotContains(response, 'Private exam')

		self.assertEqual(self.client.get(f'/subjects/edit/{subject.pk}/').status_code, 404)
		self.assertEqual(self.client.get(f'/exams/edit/{exam.pk}/').status_code, 404)
		self.assertEqual(self.client.post(f'/delete/{task.pk}/').status_code, 404)
		self.assertEqual(self.client.post(f'/exams/delete/{exam.pk}/').status_code, 404)
		task.refresh_from_db()
		self.assertEqual(task.user, other_user)

	def test_dashboard_shows_live_workspace_totals(self):
		subject = Subject.objects.create(user=self.user, name='Chemistry')
		StudyTask.objects.create(user=self.user, title='Review bonding', subject=subject, completed=True)
		StudyTask.objects.create(user=self.user, title='Practice equations', subject=subject)
		Exam.objects.create(
			user=self.user,
			title='Chemistry quiz',
			date=timezone.localdate() + timedelta(days=5),
			subject=subject,
		)

		response = self.client.get('/dashboard/')

		self.assertEqual(response.context['subjects_count'], 1)
		self.assertEqual(response.context['total_tasks'], 2)
		self.assertEqual(response.context['completed_tasks'], 1)
		self.assertEqual(response.context['upcoming_exams_count'], 1)
		self.assertContains(response, 'Study overview')

	def test_dashboard_previews_pending_tasks_and_upcoming_exams(self):
		subject = Subject.objects.create(user=self.user, name='Physics')
		task = StudyTask.objects.create(user=self.user, title='Review motion', subject=subject)
		exam = Exam.objects.create(
			user=self.user,
			title='Physics midterm',
			date=timezone.localdate() + timedelta(days=3),
			subject=subject,
		)

		response = self.client.get('/dashboard/')

		self.assertIn(task, response.context['pending_tasks'])
		self.assertIn(exam, response.context['upcoming_exams'])
		self.assertContains(response, 'Review motion')
		self.assertContains(response, 'Physics midterm')

	def test_dashboard_shows_weekly_study_goal_and_streak_data(self):
		subject = Subject.objects.create(user=self.user, name='Mathematics')
		today = timezone.localdate()
		StudySession.objects.create(
			user=self.user,
			subject=subject,
			date=today - timedelta(days=1),
			duration_minutes=15,
		)
		StudySession.objects.create(
			user=self.user,
			subject=subject,
			date=today,
			duration_minutes=30,
		)

		response = self.client.get('/dashboard/')

		self.assertEqual(response.context['study_minutes_this_week'], 45)
		self.assertEqual(response.context['weekly_goal_percent'], 15)
		self.assertEqual(response.context['study_streak'], 2)
		self.assertEqual(len(response.context['study_week']), 7)
		self.assertContains(response, 'Your last 7 days')

	def test_demo_data_command_is_repeatable(self):
		call_command('load_demo_data', username=self.user.username, stdout=StringIO())
		call_command('load_demo_data', username=self.user.username, stdout=StringIO())

		self.assertEqual(Subject.objects.count(), 5)
		self.assertEqual(StudyTask.objects.count(), 11)
		self.assertEqual(Exam.objects.count(), 5)
		self.assertEqual(StudySession.objects.count(), 12)
		self.assertEqual(Flashcard.objects.count(), 10)
		self.assertEqual(StudyNote.objects.count(), 5)
		self.assertEqual(StudyTask.objects.filter(completed=True).count(), 4)
		self.assertTrue(StudySession.objects.filter(date=timezone.localdate()).exists())
		self.assertTrue(
			StudySession.objects.filter(subject__name='Computer Science').exists()
		)
		self.assertTrue(
			StudyTask.objects.filter(
				user=self.user,
				due_date__isnull=False,
				priority=StudyTask.Priority.HIGH,
			).exists()
		)

	def test_demo_data_command_requires_a_username_when_accounts_are_ambiguous(self):
		User.objects.create_user(username='secondstudent', password='StrongPassword123!')

		with self.assertRaisesMessage(CommandError, 'Specify --username'):
			call_command('load_demo_data', stdout=StringIO())

		self.assertEqual(Subject.objects.count(), 0)
		self.assertEqual(StudyTask.objects.count(), 0)
		self.assertEqual(StudySession.objects.count(), 0)

	def test_homepage_returns_success_and_uses_template(self):
		response = self.client.get('/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/home.html')
		self.assertContains(
			response,
			'<meta name="viewport" content="width=device-width, initial-scale=1">',
		)

	def test_all_pages_include_a_back_button(self):
		subject = Subject.objects.create(user=self.user, name='Mathematics')
		task = StudyTask.objects.create(user=self.user, title='Practice algebra', subject=subject)
		exam = Exam.objects.create(
			user=self.user,
			title='Math assessment',
			date=timezone.localdate() + timedelta(days=5),
		)
		page_urls = (
			'/dashboard/',
			'/subjects/',
			'/tasks/',
			'/exams/',
			f'/exams/edit/{exam.pk}/',
			'/progress/',
			'/learning/',
			'/calendar/',
			'/modules/subject-management/',
			f'/subjects/edit/{subject.pk}/',
			f'/edit/{task.pk}/',
		)

		for url in page_urls:
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertEqual(response.status_code, 200)
				self.assertContains(
					response,
					'<meta name="viewport" content="width=device-width, initial-scale=1">',
				)
				self.assertContains(
					response,
					'aria-label="Go back to the previous page"',
				)
				self.assertContains(
					response,
					'<nav class="app-nav" aria-label="Main navigation">',
				)

	def test_homepage_does_not_show_a_back_button(self):
		response = self.client.get('/')

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(
			response,
			'aria-label="Go back to the previous page"',
		)

	def test_task_tracking_has_its_own_page(self):
		response = self.client.get('/tasks/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/tasks.html')
		self.assertContains(response, 'Task Tracking')

	def test_progress_tracking_reports_overall_and_subject_progress(self):
		subject = Subject.objects.create(user=self.user, name='Mathematics')
		StudyTask.objects.create(user=self.user, title='Practice algebra', subject=subject, completed=True)
		StudyTask.objects.create(user=self.user, title='Review geometry', subject=subject)
		StudyTask.objects.create(user=self.user, title='Read notes', completed=True)

		response = self.client.get('/progress/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/progress.html')
		self.assertEqual(response.context['total_tasks'], 3)
		self.assertEqual(response.context['completed_tasks'], 2)
		self.assertEqual(response.context['pending_tasks'], 1)
		self.assertEqual(response.context['completion_percent'], 67)
		self.assertContains(response, 'Mathematics')
		self.assertContains(response, '50%')

	def test_progress_tracking_includes_daily_and_weekly_study_reports(self):
		subject = Subject.objects.create(user=self.user, name='Physics')
		today = timezone.localdate()
		StudySession.objects.create(
			user=self.user,
			subject=subject,
			date=today,
			duration_minutes=25,
		)
		StudySession.objects.create(
			user=self.user,
			subject=subject,
			date=today - timedelta(days=3),
			duration_minutes=35,
		)

		response = self.client.get('/progress/')

		self.assertEqual(response.context['daily_study_minutes'], 25)
		self.assertEqual(response.context['weekly_study_minutes'], 60)
		self.assertContains(response, 'Study today')
		self.assertContains(response, 'Study this week')

	def test_progress_tracking_handles_an_empty_workspace(self):
		response = self.client.get('/progress/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['completion_percent'], 0)
		self.assertContains(response, 'Add study tasks to start tracking your progress.')
		self.assertContains(response, 'Add a subject')

	def test_daily_planner_prioritizes_overdue_work_and_reschedules_it(self):
		subject = Subject.objects.create(
			user=self.user,
			name='Biology',
			exam_date=timezone.localdate() + timedelta(days=2),
		)
		overdue_task = StudyTask.objects.create(
			user=self.user,
			title='Missed biology revision',
			subject=subject,
			due_date=timezone.localdate() - timedelta(days=1),
			priority=StudyTask.Priority.LOW,
			difficulty=StudyTask.Difficulty.EASY,
			estimated_minutes=30,
		)
		StudyTask.objects.create(
			user=self.user,
			title='Future high priority work',
			due_date=timezone.localdate() + timedelta(days=4),
			priority=StudyTask.Priority.HIGH,
			estimated_minutes=30,
		)

		response = self.client.get('/planner/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['plan'][0]['task'], overdue_task)
		self.assertTrue(response.context['plan'][0]['is_rescheduled'])
		self.assertTrue(response.context['plan'][1]['is_partial'])
		self.assertEqual(response.context['planned_minutes'], 30)
		self.assertContains(response, 'Missed deadline · rescheduled today')

	def test_daily_planner_saves_available_time_and_start_time(self):
		goal = StudyGoal.objects.create(
			user=self.user,
			daily_minutes=60,
			weekly_minutes=480,
		)

		response = self.client.post('/planner/', {
			'daily_minutes': 120,
			'start_time': '10:30',
		})

		self.assertRedirects(response, '/planner/')
		goal.refresh_from_db()
		self.assertEqual(goal.daily_minutes, 120)
		self.assertEqual(goal.weekly_minutes, 480)
		self.assertContains(self.client.get('/planner/'), '10:30 AM')

	def test_daily_planner_requires_login(self):
		self.client.logout()

		self.assertRedirects(self.client.get('/planner/'), '/login/?next=/planner/')

	def test_homepage_does_not_show_study_tasks(self):
		response = self.client.get('/')

		self.assertNotContains(response, 'No study tasks yet')
		self.assertNotContains(response, 'Add task')

	def test_homepage_shows_study_feature_cards(self):
		response = self.client.get('/')

		self.assertContains(response, 'Organize your subjects')
		self.assertContains(response, 'Stay on top of tasks')
		self.assertContains(response, 'Remember exam dates')
		self.assertContains(response, 'Plan with a study calendar')

	def test_dashboard_displays_separate_modules(self):
		response = self.client.get('/dashboard/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/dashboard.html')
		for module in (
			'Subject Management',
			'Study Task Tracking',
			'Exam &amp; Reminder Management',
			'Progress Tracking',
			'Learning Toolkit',
			'Study Calendar',
		):
			self.assertContains(response, module, html=True)
		self.assertNotContains(response, '<h3>Student Dashboard</h3>', html=True)
		self.assertEqual(len(response.context['modules']), 9)
		self.assertNotIn(
			'student-dashboard',
			[module['slug'] for module in response.context['modules']],
		)
		self.assertContains(response, 'Log out')
		self.assertContains(response, 'action="/logout/"')
		self.assertNotContains(response, 'View module')
		self.assertContains(response, 'href="/subjects/"')
		self.assertContains(response, 'href="/tasks/"')
		self.assertContains(response, 'href="/exams/"')
		self.assertContains(response, 'href="/progress/"')
		self.assertContains(response, 'href="/learning/"')
		self.assertContains(response, 'href="/calendar/"')
		self.assertContains(response, 'href="/focus/"')
		self.assertContains(response, 'href="/strategies/"')
		self.assertContains(response, 'href="/planner/"')
		self.assertContains(response, 'study_app/images/study-focus.svg')
		self.assertNotContains(response, 'href="#"')

	def test_focus_timer_module_is_available_and_requires_login(self):
		self.assertEqual(self.client.get('/focus/').status_code, 200)
		self.assertContains(self.client.get('/focus/'), 'Start focus')
		self.assertContains(self.client.get('/focus/'), 'Pause')

		self.client.logout()
		response = self.client.get('/focus/')
		self.assertRedirects(response, '/login/?next=/focus/')

	def test_study_strategies_module_is_available_and_requires_login(self):
		response = self.client.get('/strategies/')
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Active recall')
		self.assertContains(response, 'Space your revision')
		self.assertContains(response, 'study-progress.svg')

		self.client.logout()
		response = self.client.get('/strategies/')
		self.assertRedirects(response, '/login/?next=/strategies/')

	def test_module_page_shows_only_its_name_and_description(self):
		response = self.client.get('/modules/subject-management/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/module_detail.html')
		self.assertContains(response, '<h1>Subject Management</h1>', html=True)
		self.assertContains(
			response,
			'Organize subjects by category and priority',
		)
		self.assertNotContains(response, 'Manage subjects')
		self.assertNotContains(response, 'Study Tasks')

	def test_unknown_module_page_returns_404(self):
		response = self.client.get('/modules/not-a-module/')

		self.assertEqual(response.status_code, 404)

	def test_exam_management_can_add_an_exam_date(self):
		subject = Subject.objects.create(user=self.user, name='Mathematics')
		exam_date = timezone.localdate() + timedelta(days=14)

		response = self.client.post('/exams/add/', {
			'title': 'Algebra exam',
			'date': exam_date.isoformat(),
			'subject': subject.pk,
		})

		self.assertRedirects(response, '/exams/')
		self.assertTrue(Exam.objects.filter(
			title='Algebra exam',
			date=exam_date,
			subject=subject,
		).exists())

	def test_exam_can_save_preparation_details(self):
		exam_date = timezone.localdate() + timedelta(days=14)
		response = self.client.post('/exams/add/', {
			'title': 'Biology practical',
			'date': exam_date.isoformat(),
			'subject': '',
			'exam_type': Exam.ExamType.PRACTICAL,
			'priority': Exam.Priority.HIGH,
			'topics': 'Cell structure, microscopy',
			'preparation_percent': '65',
		})

		self.assertRedirects(response, '/exams/')
		exam = Exam.objects.get(title='Biology practical')
		self.assertEqual(exam.exam_type, Exam.ExamType.PRACTICAL)
		self.assertEqual(exam.priority, Exam.Priority.HIGH)
		self.assertEqual(exam.topics, 'Cell structure, microscopy')
		self.assertEqual(exam.preparation_percent, 65)

	def test_dashboard_shows_exam_form_errors(self):
		response = self.client.post('/exams/add/', {'title': '', 'date': ''})

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/exams.html')
		self.assertTrue(response.context['exam_form'].errors)
		self.assertContains(response, 'This field is required.')
		self.assertEqual(Exam.objects.count(), 0)

	def test_exam_date_form_rejects_past_dates(self):
		response = self.client.post('/exams/add/', {
			'title': 'Past exam',
			'date': (timezone.localdate() - timedelta(days=1)).isoformat(),
			'subject': '',
		})

		self.assertEqual(response.status_code, 200)
		self.assertIn('date', response.context['exam_form'].errors)
		self.assertContains(response, 'Choose today or a future date for the exam.')
		self.assertEqual(Exam.objects.count(), 0)

	def test_exam_management_lists_upcoming_exams(self):
		exam = Exam.objects.create(
			user=self.user,
			title='Physics exam',
			date=timezone.localdate() + timedelta(days=4),
		)

		response = self.client.get('/exams/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/exams.html')
		self.assertContains(response, 'Physics exam')
		self.assertContains(response, f'href="/exams/edit/{exam.pk}/"')
		self.assertContains(response, f'action="/exams/delete/{exam.pk}/"')
		self.assertContains(response, 'Preparation progress')
		self.assertContains(response, 'Exams in the next 7 days')

	def test_exam_can_be_edited(self):
		exam = Exam.objects.create(
			user=self.user,
			title='Old exam',
			date=timezone.localdate() + timedelta(days=4),
		)
		new_date = timezone.localdate() + timedelta(days=8)

		response = self.client.post(f'/exams/edit/{exam.pk}/', {
			'title': 'Updated exam',
			'date': new_date.isoformat(),
			'subject': '',
			'exam_type': Exam.ExamType.ORAL,
			'priority': Exam.Priority.HIGH,
			'topics': 'Definitions and proofs',
			'preparation_percent': '80',
		})

		exam.refresh_from_db()
		self.assertRedirects(response, '/exams/')
		self.assertEqual(exam.title, 'Updated exam')
		self.assertEqual(exam.date, new_date)
		self.assertEqual(exam.exam_type, Exam.ExamType.ORAL)
		self.assertEqual(exam.priority, Exam.Priority.HIGH)
		self.assertEqual(exam.topics, 'Definitions and proofs')
		self.assertEqual(exam.preparation_percent, 80)

	def test_exam_can_be_deleted(self):
		exam = Exam.objects.create(
			user=self.user,
			title='Remove exam',
			date=timezone.localdate() + timedelta(days=4),
		)

		response = self.client.post(f'/exams/delete/{exam.pk}/')

		self.assertRedirects(response, '/exams/')
		self.assertFalse(Exam.objects.filter(pk=exam.pk).exists())

	def test_reminder_can_be_created_completed_and_deleted(self):
		exam = Exam.objects.create(
			user=self.user,
			title='Physics exam',
			date=timezone.localdate() + timedelta(days=4),
		)
		remind_at = timezone.localtime() + timedelta(hours=2)
		response = self.client.post('/reminders/add/', {
			'title': 'Review formulas',
			'remind_at': remind_at.strftime('%Y-%m-%dT%H:%M'),
			'exam': exam.pk,
			'note': 'Focus on mechanics',
		})

		self.assertRedirects(response, '/exams/')
		reminder = Reminder.objects.get(title='Review formulas')
		self.assertEqual(reminder.user, self.user)
		self.assertEqual(reminder.exam, exam)
		self.assertContains(self.client.get('/exams/'), 'Review formulas')

		response = self.client.post(f'/reminders/{reminder.pk}/toggle/')
		self.assertRedirects(response, '/exams/')
		reminder.refresh_from_db()
		self.assertTrue(reminder.is_done)
		self.assertEqual(self.client.get('/exams/').context['open_reminders_count'], 0)

		response = self.client.post(f'/reminders/{reminder.pk}/delete/')
		self.assertRedirects(response, '/exams/')
		self.assertFalse(Reminder.objects.filter(pk=reminder.pk).exists())

	def test_users_cannot_create_or_change_reminders_for_another_users_exam(self):
		other_user = User.objects.create_user(
			username='examowner',
			password='StrongPassword123!',
		)
		private_exam = Exam.objects.create(
			user=other_user,
			title='Private exam',
			date=timezone.localdate() + timedelta(days=2),
		)
		remind_at = timezone.localtime() + timedelta(hours=2)
		response = self.client.post('/reminders/add/', {
			'title': 'Invalid linked reminder',
			'remind_at': remind_at.strftime('%Y-%m-%dT%H:%M'),
			'exam': private_exam.pk,
		})

		self.assertEqual(response.status_code, 200)
		self.assertIn('exam', response.context['reminder_form'].errors)
		self.assertFalse(Reminder.objects.filter(user=self.user).exists())

		private_reminder = Reminder.objects.create(
			user=other_user,
			title='Private reminder',
			remind_at=remind_at,
		)
		self.assertEqual(
			self.client.post(f'/reminders/{private_reminder.pk}/toggle/').status_code,
			404,
		)
		self.assertEqual(
			self.client.post(f'/reminders/{private_reminder.pk}/delete/').status_code,
			404,
		)
		private_reminder.refresh_from_db()
		self.assertFalse(private_reminder.is_done)

	def test_register_and_login_have_separate_pages(self):
		self.client.logout()
		register_response = self.client.get('/register/')
		login_response = self.client.get('/login/')

		self.assertTemplateUsed(register_response, 'study_app/register.html')
		self.assertTemplateUsed(login_response, 'study_app/login.html')
		self.assertContains(register_response, 'Create your account')
		self.assertContains(login_response, 'Welcome back')
		for response in (register_response, login_response):
			self.assertContains(
				response,
				'<meta name="viewport" content="width=device-width, initial-scale=1">',
			)
			self.assertContains(response, 'aria-label="Go back to the previous page"')

		self.assertContains(register_response, 'autocomplete="username"')
		self.assertContains(register_response, 'autocomplete="email"')
		self.assertContains(register_response, 'autocomplete="new-password"')

	def test_registration_errors_and_next_destination_are_preserved(self):
		self.client.logout()

		response = self.client.post('/register/', {
			'username': 'studyuser',
			'email': 'student@example.com',
			'password1': 'StrongPassword123!',
			'password2': 'DifferentPassword123!',
			'next': '/exams/',
		})

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context['form'].errors)
		self.assertContains(response, 'name="next" value="/exams/"')
		self.assertContains(response, 'role="alert"')
		self.assertFalse(User.objects.filter(username='studyuser').exists())

	def test_user_can_register_and_login(self):
		self.client.logout()
		register_response = self.client.post('/register/', {
			'username': 'studyuser',
			'email': 'student@example.com',
			'password1': 'StrongPassword123!',
			'password2': 'StrongPassword123!',
		})

		self.assertEqual(register_response.status_code, 302)
		self.assertEqual(register_response['Location'], '/login/')
		user = User.objects.get(username='studyuser')
		self.assertNotIn('_auth_user_id', self.client.session)
		login_page = self.client.get('/login/')
		self.assertContains(login_page, 'Your account was created. Please log in to continue.')
		self.assertContains(login_page, 'name="username"')

		login_response = self.client.post('/login/', {
			'username': 'studyuser',
			'password': 'StrongPassword123!',
		})
		self.assertRedirects(login_response, '/dashboard/')
		self.assertEqual(str(self.client.session['_auth_user_id']), str(user.pk))
		self.assertEqual(self.client.get('/dashboard/').status_code, 200)

		self.client.post('/subjects/add/', {
			'name': 'Biology',
			'description': '',
			'priority': 'medium',
			'study_hours': '0',
		})
		subject = Subject.objects.get(name='Biology')
		self.client.post('/add/', {'title': 'Review cells', 'subject': subject.pk})
		self.client.post('/exams/add/', {
			'title': 'Biology exam',
			'date': (timezone.localdate() + timedelta(days=7)).isoformat(),
			'subject': subject.pk,
		})
		self.assertTrue(StudyTask.objects.filter(user=user, title='Review cells').exists())
		self.assertTrue(Exam.objects.filter(user=user, title='Biology exam').exists())

		self.client.post('/logout/')
		login_response = self.client.post('/login/', {
			'username': 'studyuser',
			'password': 'StrongPassword123!',
		})

		self.assertRedirects(login_response, '/dashboard/')
		self.assertContains(self.client.get('/subjects/'), 'Biology')
		self.assertContains(self.client.get('/tasks/'), 'Review cells')
		self.assertContains(self.client.get('/exams/'), 'Biology exam')

	def test_authenticated_user_is_sent_to_workspace_from_auth_pages(self):
		user = User.objects.create_user(
			username='existinguser',
			password='StrongPassword123!',
		)
		self.client.force_login(user)

		self.assertRedirects(self.client.get('/register/'), '/dashboard/')
		self.assertRedirects(self.client.get('/login/'), '/dashboard/')

	def test_task_tracking_orders_pending_tasks_before_completed_tasks(self):
		completed_task = StudyTask.objects.create(user=self.user, title='Read notes', completed=True)
		pending_task = StudyTask.objects.create(user=self.user, title='Finish quiz')

		response = self.client.get('/tasks/')

		self.assertEqual(
			list(response.context['tasks']),
			[pending_task, completed_task],
		)

	def test_task_tracking_shows_task_status(self):
		StudyTask.objects.create(user=self.user, title='Finish quiz')
		StudyTask.objects.create(user=self.user, title='Read notes', completed=True)

		response = self.client.get('/tasks/')

		self.assertContains(response, 'Finish quiz - Pending')
		self.assertContains(response, 'Read notes')
		self.assertContains(response, 'Completed')

	def test_task_tracking_searches_and_filters_by_status_and_subject(self):
		math = Subject.objects.create(user=self.user, name='Mathematics')
		science = Subject.objects.create(user=self.user, name='Science')
		pending_task = StudyTask.objects.create(
			user=self.user,
			title='Practice algebra',
			subject=math,
		)
		StudyTask.objects.create(
			user=self.user,
			title='Algebra review complete',
			subject=math,
			completed=True,
		)
		StudyTask.objects.create(
			user=self.user,
			title='Practice algebra in science',
			subject=science,
		)

		response = self.client.get(
			'/tasks/',
			{'q': 'algebra', 'status': 'pending', 'subject': str(math.pk)},
		)

		self.assertEqual(list(response.context['tasks']), [pending_task])
		self.assertEqual(response.context['visible_task_count'], 1)
		self.assertEqual(response.context['total_tasks_count'], 3)

	def test_task_tracking_paginates_large_workspaces(self):
		subject = Subject.objects.create(user=self.user, name='Mathematics')
		StudyTask.objects.bulk_create([
			StudyTask(
				user=self.user,
				subject=subject,
				title=f'Algebra practice {task_number:02d}',
			)
			for task_number in range(30)
		])

		first_page = self.client.get('/tasks/')
		second_page = self.client.get('/tasks/', {'page': '2'})

		self.assertEqual(first_page.context['page_obj'].paginator.count, 30)
		self.assertEqual(len(first_page.context['tasks']), 25)
		self.assertEqual(second_page.context['page_obj'].number, 2)
		self.assertEqual(len(second_page.context['tasks']), 5)
		self.assertContains(first_page, 'Page 1 of 2')

	def test_homepage_can_add_a_task(self):
		response = self.client.post('/add/', {'title': 'Practice algebra'})

		self.assertRedirects(response, '/tasks/')
		self.assertTrue(StudyTask.objects.filter(title='Practice algebra').exists())

	def test_invalid_task_submission_shows_validation_error(self):
		response = self.client.post('/add/', {'title': '', 'subject': ''})

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/tasks.html')
		self.assertContains(response, 'This field is required.')
		self.assertEqual(StudyTask.objects.count(), 0)

	def test_task_form_rejects_invalid_calendar_dates(self):
		response = self.client.post('/add/', {
			'title': 'Prepare for exam',
			'subject': '',
			'due_date': '2026-02-31',
			'priority': StudyTask.Priority.HIGH,
		})

		self.assertEqual(response.status_code, 200)
		self.assertIn('due_date', response.context['form'].errors)
		self.assertEqual(StudyTask.objects.count(), 0)

	def test_task_can_be_marked_complete(self):
		task = StudyTask.objects.create(user=self.user, title='Review flashcards')

		response = self.client.post(f'/toggle/{task.pk}/')

		task.refresh_from_db()
		self.assertRedirects(response, '/tasks/')
		self.assertTrue(task.completed)

	def test_task_can_be_deleted(self):
		task = StudyTask.objects.create(user=self.user, title='Practice spanish')

		response = self.client.post(f'/delete/{task.pk}/')

		self.assertRedirects(response, '/tasks/')
		self.assertFalse(StudyTask.objects.filter(pk=task.pk).exists())

	def test_task_can_be_edited(self):
		task = StudyTask.objects.create(user=self.user, title='Old task title')

		response = self.client.post(f'/edit/{task.pk}/', {'title': 'New task title'})

		task.refresh_from_db()
		self.assertRedirects(response, '/tasks/')
		self.assertEqual(task.title, 'New task title')

	def test_homepage_is_a_landing_page(self):
		self.client.logout()
		response = self.client.get('/')

		self.assertContains(response, 'StudyMate')
		self.assertContains(response, 'Create account')
		self.assertContains(response, 'Login')
		self.assertContains(response, 'About')
		self.assertNotContains(response, 'Your modules')

	def test_authenticated_homepage_links_to_the_users_workspace(self):
		response = self.client.get('/')

		self.assertContains(response, 'Dashboard')
		self.assertContains(response, 'Learning toolkit')
		self.assertContains(response, 'Open my study workspace')
		self.assertContains(response, 'Open calendar')
		self.assertContains(response, 'Log out')
		self.assertNotContains(response, 'Create account')

	def test_successful_login_redirects_to_dashboard(self):
		self.client.logout()
		user = User.objects.create_user(username='dashboarduser', password='StrongPassword123!')

		response = self.client.post('/login/', {
			'username': 'dashboarduser',
			'password': 'StrongPassword123!'
		})

		self.assertRedirects(response, '/dashboard/')
		self.assertContains(self.client.get('/dashboard/'), 'Subject Management')

	def test_login_returns_user_to_requested_exam_page(self):
		self.client.logout()
		User.objects.create_user(username='examuser', password='StrongPassword123!')

		login_page = self.client.get('/login/?next=/exams/')
		self.assertContains(login_page, 'name="next" value="/exams/"')

		response = self.client.post('/login/?next=/exams/', {
			'username': 'examuser',
			'password': 'StrongPassword123!',
			'next': '/exams/',
		})

		self.assertRedirects(response, '/exams/')
		self.assertContains(self.client.get('/exams/'), 'Exam &amp; Reminder Management', html=True)

	def test_login_rejects_external_next_url(self):
		User.objects.create_user(username='safeuser', password='StrongPassword123!')

		response = self.client.post('/login/', {
			'username': 'safeuser',
			'password': 'StrongPassword123!',
			'next': 'https://example.com/exams/',
		})

		self.assertRedirects(response, '/dashboard/')


class SubjectManagementTests(WorkspaceTestCase):
	def test_subject_management_page_loads(self):
		response = self.client.get('/subjects/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/subjects.html')
		self.assertContains(response, 'Subject Management')
		self.assertContains(response, 'Priority')
		self.assertContains(response, 'Study hours')
		self.assertContains(response, 'Search / filter')
		self.assertContains(response, 'Subject analytics')
		self.assertContains(response, 'Weekly study goal')
		self.assertContains(response, 'Category')
		self.assertContains(response, 'Exam date (optional)')

	def test_user_can_add_a_subject(self):
		response = self.client.post('/subjects/add/', {
			'name': 'Mathematics',
			'description': 'Algebra, geometry, and problem solving.',
			'priority': Subject.Priority.HIGH,
			'study_hours': '12.5',
		})

		self.assertRedirects(response, '/subjects/')
		subject = Subject.objects.get(name='Mathematics')
		self.assertEqual(subject.priority, Subject.Priority.HIGH)
		self.assertEqual(subject.study_hours, 12.5)
		self.assertEqual(subject.category, '')
		self.assertEqual(subject.weekly_goal_hours, 5)

	def test_subjects_can_be_searched_and_filtered_by_priority(self):
		Subject.objects.create(user=self.user, name='Biology', priority=Subject.Priority.HIGH)
		Subject.objects.create(user=self.user, name='History', priority=Subject.Priority.LOW)

		response = self.client.get('/subjects/?q=bio&priority=high')

		self.assertContains(response, 'Biology')
		self.assertNotContains(response, 'History')

	def test_subject_progress_comes_from_completed_assigned_tasks(self):
		subject = Subject.objects.create(user=self.user, name='Physics')
		StudyTask.objects.create(user=self.user, title='Review chapter', subject=subject, completed=True)
		StudyTask.objects.create(user=self.user, title='Practice problems', subject=subject)

		response = self.client.get('/subjects/')

		self.assertContains(response, 'Review chapter')
		self.assertContains(response, 'Practice problems')
		self.assertContains(response, 'Task progress')
		self.assertContains(response, '50%')

	def test_subject_analytics_use_weekly_sessions_and_upcoming_exam(self):
		today = timezone.localdate()
		subject = Subject.objects.create(
			user=self.user,
			name='Physics',
			weekly_goal_hours=2,
		)
		StudyTask.objects.create(user=self.user, title='Completed work', subject=subject, completed=True)
		StudyTask.objects.create(user=self.user, title='Pending work', subject=subject)
		StudySession.objects.create(
			user=self.user,
			subject=subject,
			date=today,
			duration_minutes=45,
		)
		StudySession.objects.create(
			user=self.user,
			subject=subject,
			date=today - timedelta(days=8),
			duration_minutes=90,
		)
		Exam.objects.create(
			user=self.user,
			subject=subject,
			title='Physics test',
			date=today + timedelta(days=3),
		)

		response = self.client.get('/subjects/')

		self.assertEqual(response.context['weekly_study_minutes'], 45)
		self.assertEqual(response.context['total_tasks'], 2)
		self.assertEqual(response.context['completed_tasks'], 1)
		subject_in_context = response.context['subjects'][0]
		self.assertEqual(subject_in_context.week_study_minutes, 45)
		self.assertEqual(subject_in_context.week_goal_percent, 38)
		self.assertEqual(subject_in_context.days_until_exam, 3)
		self.assertContains(response, 'Exam in 3 days')

	def test_subjects_can_be_filtered_by_category(self):
		Subject.objects.create(user=self.user, name='Biology', category='Science')
		Subject.objects.create(user=self.user, name='Algebra', category='Mathematics')

		response = self.client.get('/subjects/?category=science')

		self.assertContains(response, 'Biology')
		self.assertNotContains(response, 'Algebra')

	def test_study_task_can_be_assigned_to_a_subject(self):
		subject = Subject.objects.create(user=self.user, name='Chemistry')

		response = self.client.post('/add/', {
			'title': 'Review reactions',
			'subject': subject.pk,
		})

		self.assertRedirects(response, '/tasks/')
		task = StudyTask.objects.get(title='Review reactions')
		self.assertEqual(task.subject, subject)
		self.assertContains(self.client.get('/tasks/'), 'Chemistry')

	def test_subject_can_be_edited_with_all_details(self):
		subject = Subject.objects.create(user=self.user, name='Old name')

		response = self.client.post(f'/subjects/edit/{subject.pk}/', {
			'name': 'New name',
			'category': 'Science',
			'description': 'Updated description',
			'priority': Subject.Priority.LOW,
			'color': Subject.Color.TEAL,
			'study_hours': '8',
			'weekly_goal_hours': '3.5',
			'exam_date': '',
		})

		self.assertRedirects(response, '/subjects/')
		subject.refresh_from_db()
		self.assertEqual(subject.name, 'New name')
		self.assertEqual(subject.category, 'Science')
		self.assertEqual(subject.description, 'Updated description')
		self.assertEqual(subject.priority, Subject.Priority.LOW)
		self.assertEqual(subject.color, Subject.Color.TEAL)
		self.assertEqual(subject.study_hours, 8)
		self.assertEqual(subject.weekly_goal_hours, 3.5)

	def test_subject_can_be_deleted(self):
		subject = Subject.objects.create(user=self.user, name='Biology', description='Cells and ecosystems')

		response = self.client.post(f'/subjects/delete/{subject.pk}/')

		self.assertRedirects(response, '/subjects/')
		self.assertFalse(Subject.objects.filter(pk=subject.pk).exists())


class LearningToolkitTests(WorkspaceTestCase):
	def setUp(self):
		super().setUp()
		self.subject = Subject.objects.create(user=self.user, name='Biology')

	def test_learning_hub_shows_tools_and_requires_login(self):
		response = self.client.get('/learning/')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/learning_hub.html')
		self.assertContains(response, 'Log a study session')
		self.assertContains(response, 'Create a flashcard')
		self.assertContains(response, 'Personal study notes')

		self.client.logout()
		self.assertRedirects(self.client.get('/learning/'), '/login/?next=/learning/')

	def test_study_session_is_saved_and_appears_in_analytics(self):
		response = self.client.post('/learning/sessions/add/', {
			'subject': self.subject.pk,
			'date': timezone.localdate().isoformat(),
			'duration_minutes': 45,
			'notes': 'Reviewed cell structure',
		})

		self.assertRedirects(response, '/learning/')
		session = StudySession.objects.get(user=self.user)
		self.assertEqual(session.duration_minutes, 45)
		self.assertEqual(session.subject, self.subject)
		self.assertEqual(self.client.get('/progress/').context['study_minutes'], 45)
		self.assertEqual(
			self.client.get('/progress/').context['subjects'][0].study_minutes,
			45,
		)
		self.assertEqual(self.client.get('/dashboard/').context['study_minutes_this_week'], 45)

	def test_session_form_rejects_future_dates_invalid_minutes_and_foreign_subjects(self):
		other_user = User.objects.create_user(username='otherstudent', password='StrongPassword123!')
		foreign_subject = Subject.objects.create(user=other_user, name='Private subject')
		payload = {
			'subject': self.subject.pk,
			'date': (timezone.localdate() + timedelta(days=1)).isoformat(),
			'duration_minutes': 45,
		}
		response = self.client.post('/learning/sessions/add/', payload)
		self.assertEqual(response.status_code, 200)
		self.assertIn('date', response.context['session_form'].errors)

		payload['date'] = timezone.localdate().isoformat()
		payload['duration_minutes'] = 0
		response = self.client.post('/learning/sessions/add/', payload)
		self.assertEqual(response.status_code, 200)
		self.assertIn('duration_minutes', response.context['session_form'].errors)

		payload.update(subject=foreign_subject.pk, duration_minutes=45)
		response = self.client.post('/learning/sessions/add/', payload)
		self.assertEqual(response.status_code, 200)
		self.assertIn('subject', response.context['session_form'].errors)
		self.assertEqual(StudySession.objects.count(), 0)

	def test_flashcards_can_be_added_practiced_and_invalid_reviews_are_rejected(self):
		response = self.client.post('/learning/flashcards/add/', {
			'subject': self.subject.pk,
			'front': 'What is a cell?',
			'back': 'The basic unit of life.',
		})
		self.assertRedirects(response, '/learning/')
		card = Flashcard.objects.get(user=self.user)
		self.assertContains(self.client.get('/learning/'), 'What is a cell?')

		response = self.client.post(f'/learning/flashcards/{card.pk}/review/', {'result': 'correct'})
		self.assertRedirects(response, '/learning/')
		response = self.client.post(f'/learning/flashcards/{card.pk}/review/', {'result': 'incorrect'})
		self.assertRedirects(response, '/learning/')
		card.refresh_from_db()
		self.assertEqual(card.review_count, 2)
		self.assertEqual(card.correct_count, 1)
		self.assertEqual(card.accuracy_percent, 50)
		self.assertEqual(self.client.get('/progress/').context['quiz_accuracy'], 50)

		response = self.client.post(f'/learning/flashcards/{card.pk}/review/', {'result': 'maybe'})
		self.assertEqual(response.status_code, 400)
		self.assertEqual(Flashcard.objects.get(pk=card.pk).review_count, 2)

	def test_flashcards_and_notes_require_subjects_owned_by_the_user(self):
		other_user = User.objects.create_user(username='foreignstudent', password='StrongPassword123!')
		foreign_subject = Subject.objects.create(user=other_user, name='Private course')
		response = self.client.post('/learning/flashcards/add/', {
			'subject': foreign_subject.pk,
			'front': 'Secret prompt',
			'back': 'Secret answer',
		})
		self.assertEqual(response.status_code, 200)
		self.assertIn('subject', response.context['flashcard_form'].errors)

		response = self.client.post('/learning/notes/add/', {
			'subject': foreign_subject.pk,
			'title': 'Private note',
			'content': 'Do not save this for another user.',
		})
		self.assertEqual(response.status_code, 200)
		self.assertIn('subject', response.context['note_form'].errors)
		self.assertEqual(Flashcard.objects.count(), 0)
		self.assertEqual(StudyNote.objects.count(), 0)

	def test_blank_flashcards_and_notes_are_rejected(self):
		response = self.client.post('/learning/flashcards/add/', {
			'subject': self.subject.pk,
			'front': '   ',
			'back': '   ',
		})
		self.assertEqual(response.status_code, 200)
		self.assertIn('front', response.context['flashcard_form'].errors)
		self.assertIn('back', response.context['flashcard_form'].errors)

		response = self.client.post('/learning/notes/add/', {
			'subject': self.subject.pk,
			'title': '   ',
			'content': '   ',
		})
		self.assertEqual(response.status_code, 200)
		self.assertIn('title', response.context['note_form'].errors)
		self.assertIn('content', response.context['note_form'].errors)
		self.assertEqual(Flashcard.objects.count(), 0)
		self.assertEqual(StudyNote.objects.count(), 0)

	def test_notes_can_be_created_and_deleted_by_their_owner(self):
		response = self.client.post('/learning/notes/add/', {
			'subject': self.subject.pk,
			'title': 'Cell biology',
			'content': 'Cell membranes regulate what enters and leaves.',
		})
		self.assertRedirects(response, '/learning/')
		note = StudyNote.objects.get(user=self.user)
		self.assertContains(self.client.get('/learning/'), 'Cell biology')

		response = self.client.post(f'/learning/notes/{note.pk}/delete/')
		self.assertRedirects(response, '/learning/')
		self.assertFalse(StudyNote.objects.filter(pk=note.pk).exists())

	def test_users_cannot_review_or_delete_another_users_learning_records(self):
		other_user = User.objects.create_user(username='learningowner', password='StrongPassword123!')
		other_subject = Subject.objects.create(user=other_user, name='Private lesson')
		card = Flashcard.objects.create(
			user=other_user,
			subject=other_subject,
			front='Private flashcard',
			back='Private answer',
		)
		note = StudyNote.objects.create(
			user=other_user,
			subject=other_subject,
			title='Private notes',
			content='Private content',
		)
		self.assertEqual(self.client.get('/learning/').status_code, 200)
		self.assertNotContains(self.client.get('/learning/'), 'Private flashcard')
		self.assertNotContains(self.client.get('/learning/'), 'Private notes')
		self.assertEqual(
			self.client.post(f'/learning/flashcards/{card.pk}/review/', {'result': 'correct'}).status_code,
			404,
		)
		self.assertEqual(self.client.post(f'/learning/notes/{note.pk}/delete/').status_code, 404)
		card.refresh_from_db()
		self.assertEqual(card.review_count, 0)


class StudyCalendarTests(WorkspaceTestCase):
	def test_calendar_includes_owned_open_reminders(self):
		remind_at = timezone.make_aware(
			datetime.combine(
				date(2026, 10, 22),
				time(9, 0),
			)
		)
		reminder = Reminder.objects.create(
			user=self.user,
			title='Review before exam',
			remind_at=remind_at,
		)
		Reminder.objects.create(
			user=self.user,
			title='Completed reminder',
			remind_at=remind_at,
			is_done=True,
		)

		response = self.client.get('/calendar/?month=2026-10')

		self.assertEqual(response.context['event_count'], 1)
		self.assertEqual(response.context['month_events'][0]['title'], reminder.title)
		self.assertEqual(response.context['month_events'][0]['kind'], 'Study reminder')

	def test_calendar_shows_all_owned_event_types_for_selected_month(self):
		subject = Subject.objects.create(user=self.user, name='Physics')
		event_date = date(2026, 10, 22)
		exam = Exam.objects.create(user=self.user, subject=subject, title='Physics final', date=event_date)
		task = StudyTask.objects.create(
			user=self.user,
			subject=subject,
			title='Submit lab report',
			due_date=event_date,
		)
		session = StudySession.objects.create(
			user=self.user,
			subject=subject,
			date=event_date,
			duration_minutes=50,
			notes='Revision',
		)

		response = self.client.get('/calendar/?month=2026-10')

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'study_app/calendar.html')
		self.assertEqual(response.context['month_label'], 'October 2026')
		self.assertEqual(response.context['event_count'], 3)
		self.assertEqual(
			[event['title'] for event in response.context['month_events']],
			[exam.title, f'{subject.name} study session (50 min)', task.title],
		)
		for event_title in (exam.title, task.title, 'Physics study session (50 min)'):
			self.assertContains(response, event_title)

	def test_calendar_filters_other_users_events(self):
		other_user = User.objects.create_user(username='calendarowner', password='StrongPassword123!')
		other_subject = Subject.objects.create(user=other_user, name='Private subject')
		Exam.objects.create(
			user=other_user,
			subject=other_subject,
			title='Private exam',
			date=date(2026, 10, 20),
		)
		StudyTask.objects.create(
			user=other_user,
			subject=other_subject,
			title='Private deadline',
			due_date=date(2026, 10, 21),
		)

		response = self.client.get('/calendar/?month=2026-10')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['event_count'], 0)
		self.assertNotContains(response, 'Private exam')
		self.assertNotContains(response, 'Private deadline')

	def test_calendar_rejects_invalid_or_out_of_range_month_values(self):
		for month_value in (
			'2026-00',
			'2026-13',
			'2026-2',
			'2026-02-01',
			'1899-12',
			'2101-01',
			'not-a-month',
		):
			with self.subTest(month=month_value):
				response = self.client.get(f'/calendar/?month={month_value}')
				self.assertEqual(response.status_code, 400)
				self.assertContains(
					response,
					'Choose a valid calendar month between January 1900 and December 2100.',
					status_code=400,
				)

	def test_calendar_handles_leap_year_and_month_navigation(self):
		response = self.client.get('/calendar/?month=2028-02')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'February 2028')
		self.assertContains(response, 'href="?month=2028-01"')
		self.assertContains(response, 'href="?month=2028-03"')
		days = [
			cell['day']
			for week in response.context['weeks']
			for cell in week
			if cell['day']
		]
		self.assertEqual(days, list(range(1, 30)))

	def test_calendar_requires_login(self):
		self.client.logout()

		self.assertRedirects(self.client.get('/calendar/'), '/login/?next=/calendar/')

	def test_calendar_has_back_button_and_navigation_links(self):
		response = self.client.get('/calendar/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'aria-label="Go back to the previous page"')
		self.assertContains(response, 'href="/dashboard/"')
		self.assertContains(response, 'href="/learning/"')
