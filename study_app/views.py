from urllib.parse import urlencode
import calendar
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Min, Prefetch, Q, Sum
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
	ExamForm,
	FlashcardForm,
	RegistrationForm,
	PlannerSettingsForm,
	ReminderForm,
	StudyGoalForm,
	StudyNoteForm,
	StudySessionForm,
	StudyCoachForm,
	StudyTaskForm,
	SubjectForm,
)
from .models import (
	Exam,
	Flashcard,
	Reminder,
	StudyGoal,
	StudyNote,
	StudySession,
	StudyTask,
	Subject,
	TaskChecklistItem,
)
from .planner import build_daily_plan
from .spaced_repetition import schedule_next_review
from .ai_study_coach import StudyCoachUnavailable, generate_study_coach_reply

MODULES = {
	'student-dashboard': {
		'name': 'Student Dashboard',
		'description': 'Get a complete overview of your subjects, study progress, tasks, and upcoming exams.',
	},
	'subject-management': {
		'name': 'Subject Management',
		'description': 'Organize subjects by category and priority, set weekly study goals, and monitor task progress, study time, and exam dates.',
		'image': 'study_app/images/study-books.svg',
		'url_name': 'subject_management',
		'action_label': 'Manage subjects',
	},
	'study-task-tracking': {
		'name': 'Study Task Tracking',
		'description': 'Record study activities, mark work complete, and keep pending tasks visible.',
		'image': 'study_app/images/study-checklist.svg',
		'url_name': 'task_tracking',
		'action_label': 'Manage study tasks',
	},
	'exam-reminder-management': {
		'name': 'Exam & Reminder Management',
		'description': 'Track exam formats, priorities, topics, and preparation progress, and schedule actionable study reminders.',
		'image': 'study_app/images/study-exam.svg',
		'url_name': 'exam_management',
		'action_label': 'Manage exams and reminders',
	},
	'progress-tracking': {
		'name': 'Progress Tracking',
		'description': 'Review your completed study tasks and monitor your learning progress.',
		'image': 'study_app/images/study-progress.svg',
		'url_name': 'progress_tracking',
		'action_label': 'View progress',
	},
	'learning-toolkit': {
		'name': 'Learning Toolkit',
		'description': 'Build flashcards, quiz yourself, write subject notes, and log focused study sessions.',
		'image': 'study_app/images/study-focus.svg',
		'url_name': 'learning_hub',
		'action_label': 'Open learning toolkit',
	},
	'study-calendar': {
		'name': 'Study Calendar',
		'description': 'View exam dates, assignment deadlines, and logged study sessions together in one monthly planner.',
		'image': 'study_app/images/study-exam.svg',
		'url_name': 'study_calendar',
		'action_label': 'Open study calendar',
	},
	'focus-timer': {
		'name': 'Focus Timer',
		'description': 'Use a simple focus-and-break timer to make study sessions easier to start and stick with.',
		'image': 'study_app/images/study-focus.svg',
		'url_name': 'focus_timer',
		'action_label': 'Start a focus session',
	},
	'smart-study-planner': {
		'name': 'Smart Study Planner',
		'description': 'Build a daily timetable that prioritizes subjects with exams in the next seven days, then deadlines, task priority, and topic difficulty.',
		'image': 'study_app/images/study-progress.svg',
		'url_name': 'study_planner',
		'action_label': "Build today's timetable",
	},
	'study-strategies': {
		'name': 'Study Strategies',
		'description': 'Explore practical, research-backed ways to remember more and study with less stress.',
		'image': 'study_app/images/study-books.svg',
		'url_name': 'study_strategies',
		'action_label': 'Explore study strategies',
	},
	'ai-study-coach': {
		'name': 'AI Study Coach',
		'description': 'Get explanations, personalized revision plans, and practice quizzes based on your study material.',
		'image': 'study_app/images/study-focus.svg',
		'url_name': 'study_coach',
		'action_label': 'Open Study Coach',
	},
}

STREAK_MILESTONES = (
	{'days': 3, 'name': 'Getting Started', 'icon': '🌱'},
	{'days': 7, 'name': 'One Week', 'icon': '🔥'},
	{'days': 14, 'name': 'Two Week Focus', 'icon': '🎯'},
	{'days': 30, 'name': 'Monthly Master', 'icon': '🏆'},
	{'days': 60, 'name': 'Study Champion', 'icon': '💎'},
	{'days': 100, 'name': 'Century Scholar', 'icon': '👑'},
)


def home(request):
	return render(request, 'study_app/home.html')


@login_required
def dashboard(request):
	tasks = StudyTask.objects.filter(user=request.user)
	exams = Exam.objects.filter(user=request.user)
	today = timezone.localdate()
	now = timezone.now()
	active_reminders = list(
		Reminder.objects.filter(user=request.user, is_done=False)
		.select_related('exam')
		.order_by('remind_at', 'title')[:3]
	)
	for reminder in active_reminders:
		reminder.is_overdue = (
			reminder.remind_at <= now
			and timezone.localtime(reminder.remind_at).date() < today
		)
	week_start = today - timedelta(days=6)
	weekly_sessions = StudySession.objects.filter(
		user=request.user,
		date__gte=week_start,
		date__lte=today,
	)
	daily_minutes = {
		row['date']: row['minutes'] or 0
		for row in weekly_sessions.values('date').annotate(minutes=Sum('duration_minutes'))
	}
	study_week = [
		{
			'date': week_start + timedelta(days=day_offset),
			'label': (week_start + timedelta(days=day_offset)).strftime('%a'),
			'minutes': daily_minutes.get(week_start + timedelta(days=day_offset), 0),
		}
		for day_offset in range(7)
	]
	max_daily_minutes = max((day['minutes'] for day in study_week), default=0)
	for day in study_week:
		day['bar_height'] = (
			max(round(day['minutes'] / max_daily_minutes * 100), 8)
			if day['minutes'] and max_daily_minutes
			else 0
		)
	all_study_dates = list(
		StudySession.objects.filter(user=request.user, date__lte=today)
		.order_by('date')
		.values_list('date', flat=True)
		.distinct()
	)
	longest_streak = 0
	consecutive_days = 0
	previous_date = None
	for study_date in all_study_dates:
		consecutive_days = (
			consecutive_days + 1
			if previous_date and study_date == previous_date + timedelta(days=1)
			else 1
		)
		longest_streak = max(longest_streak, consecutive_days)
		previous_date = study_date

	study_streak = 0
	if all_study_dates and all_study_dates[-1] >= today - timedelta(days=1):
		expected_date = all_study_dates[-1]
		for study_date in reversed(all_study_dates):
			if study_date != expected_date:
				break
			study_streak += 1
			expected_date -= timedelta(days=1)
	streak_badges = [
		{**milestone, 'unlocked': longest_streak >= milestone['days']}
		for milestone in STREAK_MILESTONES
	]
	next_streak_badge = next(
		(badge for badge in streak_badges if not badge['unlocked']),
		None,
	)
	if next_streak_badge:
		next_streak_badge = {
			**next_streak_badge,
			'days_remaining': next_streak_badge['days'] - study_streak,
		}
	weekly_goal_minutes = (
		StudyGoal.objects.filter(user=request.user)
		.values_list('weekly_minutes', flat=True)
		.first()
		or 300
	)
	study_minutes_this_week = sum(daily_minutes.values())
	task_totals = tasks.aggregate(
		total=Count('pk'),
		completed=Count('pk', filter=Q(completed=True)),
	)
	total_tasks = task_totals['total']
	completed_tasks = task_totals['completed']
	return render(
		request,
		'study_app/dashboard.html',
		{
			'modules': [
				{'slug': slug, **module}
				for slug, module in MODULES.items()
				if slug != 'student-dashboard'
			],
			'subjects_count': Subject.objects.filter(user=request.user).count(),
			'study_minutes_this_week': study_minutes_this_week,
			'study_week': study_week,
			'today': today,
			'weekly_goal_minutes': weekly_goal_minutes,
			'weekly_goal_percent': min(
				round(study_minutes_this_week / weekly_goal_minutes * 100),
				100,
			),
			'study_streak': study_streak,
			'longest_streak': longest_streak,
			'streak_badges': streak_badges,
			'next_streak_badge': next_streak_badge,
			'has_study_sessions': bool(daily_minutes),
			'total_tasks': total_tasks,
			'completed_tasks': completed_tasks,
			'pending_tasks_count': total_tasks - completed_tasks,
			'completion_percent': round(completed_tasks / total_tasks * 100) if total_tasks else 0,
			'pending_tasks': (
				tasks.filter(completed=False)
				.select_related('subject')
				.order_by(F('due_date').asc(nulls_last=True), 'title')[:3]
			),
			'upcoming_exams': (
				exams.filter(date__gte=timezone.localdate())
				.select_related('subject')
				.order_by('date', 'title')[:3]
			),
			'upcoming_exams_count': exams.filter(date__gte=timezone.localdate()).count(),
			'active_reminders': active_reminders,
			'now': now,
		},
	)


@login_required
def module_detail(request, slug):
	module = MODULES.get(slug)
	if module is None:
		raise Http404('Module not found')
	return render(request, 'study_app/module_detail.html', {'module': module})


@login_required
def focus_timer(request):
	return render(request, 'study_app/focus_timer.html')


@login_required
def study_strategies(request):
	return render(request, 'study_app/study_strategies.html')


def _local_study_coach_reply(mode, context, subject_name=''):
	"""Give useful, clearly local study help when no model key is configured."""
	if mode == 'quiz':
		cards = context.get('flashcards', [])
		if cards:
			parts = [f"Practice quiz for {subject_name}", '\nQuestions - answer these before looking below:']
			for index, card in enumerate(cards, start=1):
				parts.append(f"{index}. {card['front']}")
			parts.append('\nAnswer key:')
			for index, card in enumerate(cards, start=1):
				parts.append(f"{index}. {card['back']}")
			return '\n'.join(parts)
		notes = context.get('notes', [])
		if notes:
			return (
				f"No flashcards found for {subject_name}. Use these note titles to quiz yourself: "
				+ '\n'.join(f"• {note['title']}: explain the idea, give an example, then check your notes." for note in notes)
			)
		return f"Add a few notes or flashcards to {subject_name}, then come back to build a practice quiz."

	if mode == 'plan':
		parts = ['A focused plan based on your upcoming work:']
		entries = []
		for task in context.get('tasks', []):
			entries.append((task.get('due_date') or 'No due date', f"Task: {task['title']}"))
		for exam in context.get('exams', []):
			entries.append((exam['date'], f"Exam: {exam['title']}"))
		for due, title in sorted(entries)[:6]:
			parts.append(f'• {due} — {title}')
		if not entries:
			parts.append('• Add a task or exam date to get a plan around your real deadlines.')
		parts.append('\nStart with 25 minutes on the nearest deadline, take a 5-minute break, then recall the main ideas without looking at your notes.')
		return '\n'.join(parts)

	parts = [
		'AI is not connected yet, so here is a quick study routine you can use now:',
		'• Write down what you already know about the topic.',
		'• Study one small section, then close your notes and explain it from memory.',
		'• Check what you missed and make one practice question for tomorrow.',
	]
	if context.get('exams'):
		next_exam = context['exams'][0]
		parts.append(f"\nYour next exam is {next_exam['title']} on {next_exam['date']}.")
	return '\n'.join(parts)


@login_required
def study_coach(request):
	form = StudyCoachForm(request.POST or None, user=request.user)
	answer = ''
	answer_source = ''
	error = ''
	if request.method == 'POST' and form.is_valid():
		mode = form.cleaned_data['mode']
		selected_subject = form.cleaned_data.get('subject')
		today = timezone.localdate()
		tasks = StudyTask.objects.filter(user=request.user, completed=False)
		exams = Exam.objects.filter(user=request.user, date__gte=today)
		if selected_subject:
			tasks = tasks.filter(subject=selected_subject)
			exams = exams.filter(subject=selected_subject)
		tasks = tasks.select_related('subject').order_by(F('due_date').asc(nulls_last=True), 'title')[:8]
		exams = exams.select_related('subject').order_by('date', 'title')[:5]
		context = {
			'today': today.isoformat(),
			'subject': selected_subject.name if selected_subject else 'All subjects',
			'tasks': [
				{
					'title': task.title,
					'subject': task.subject.name if task.subject_id else '',
					'due_date': task.due_date.isoformat() if task.due_date else None,
					'priority': task.priority,
				}
				for task in tasks
			],
			'exams': [
				{
					'title': exam.title,
					'subject': exam.subject.name if exam.subject_id else '',
					'date': exam.date.isoformat(),
					'topics': exam.topics[:500],
				}
				for exam in exams
			],
		}
		if selected_subject:
			context['notes'] = list(
				StudyNote.objects.filter(user=request.user, subject=selected_subject)
				.order_by('-updated_at')
				.values('title', 'content')[:3]
			)
			for note in context['notes']:
				note['content'] = note['content'][:1200]
		if mode == 'quiz' and selected_subject:
			context['flashcards'] = list(
				Flashcard.objects.filter(user=request.user, subject=selected_subject)
				.order_by('front')
				.values('front', 'back')[:8]
			)

		try:
			answer = generate_study_coach_reply(
				mode=mode,
				prompt=form.cleaned_data['prompt'],
				context=context,
			)
			if answer:
				answer_source = 'AI-generated study guidance'
			else:
				answer = _local_study_coach_reply(
					mode, context, selected_subject.name if selected_subject else ''
				)
				answer_source = 'Local study suggestions'
		except StudyCoachUnavailable as exc:
			error = str(exc)
			answer = _local_study_coach_reply(
				mode, context, selected_subject.name if selected_subject else ''
			)
			answer_source = 'Local study suggestions'

	return render(
		request,
		'study_app/study_coach.html',
		{
			'form': form,
			'answer': answer,
			'answer_source': answer_source,
			'error': error,
			'ai_enabled': bool(getattr(settings, 'OPENAI_API_KEY', '')),
		},
	)


def _exam_context(request, exam_form=None):
	today = timezone.localdate()
	now = timezone.localtime()
	upcoming_exams = list(
		Exam.objects.filter(user=request.user, date__gte=today)
		.select_related('subject')
		.order_by('date', 'title')
	)
	for exam in upcoming_exams:
		exam.days_until_exam = (exam.date - today).days

	reminders = list(
		Reminder.objects.filter(user=request.user)
		.select_related('exam', 'exam__subject')
		.order_by('is_done', 'remind_at', 'title')
	)
	for reminder in reminders:
		reminder.is_due = not reminder.is_done and reminder.remind_at <= now

	return {
		'upcoming_exams': upcoming_exams,
		'reminders': reminders,
		'reminder_form': ReminderForm(user=request.user),
		'open_reminders_count': sum(not reminder.is_done for reminder in reminders),
		'due_reminders_count': sum(reminder.is_due for reminder in reminders),
		'urgent_exams_count': sum(exam.days_until_exam <= 7 for exam in upcoming_exams),
		'subjects': Subject.objects.filter(user=request.user).order_by('name'),
		'exam_form': exam_form or ExamForm(user=request.user),
	}


@login_required
def exam_management(request):
	return render(request, 'study_app/exams.html', _exam_context(request))


@login_required
def add_exam(request):
	if request.method != 'POST':
		return redirect('dashboard')

	form = ExamForm(request.POST, user=request.user)
	if form.is_valid():
		exam = form.save(commit=False)
		exam.user = request.user
		exam.save()
		return redirect('exam_management')
	return render(
		request,
		'study_app/exams.html',
		_exam_context(request, exam_form=form),
	)


@login_required
def edit_exam(request, exam_id):
	exam = get_object_or_404(Exam, pk=exam_id, user=request.user)
	if request.method == 'POST':
		form = ExamForm(request.POST, instance=exam, user=request.user)
		if form.is_valid():
			form.save()
			return redirect('exam_management')
	else:
		form = ExamForm(instance=exam, user=request.user)

	return render(request, 'study_app/edit_exam.html', {'exam': exam, 'form': form})


@login_required
def delete_exam(request, exam_id):
	if request.method != 'POST':
		return redirect('exam_management')

	exam = get_object_or_404(Exam, pk=exam_id, user=request.user)
	exam.delete()
	return redirect('exam_management')


@login_required
def add_reminder(request):
	if request.method != 'POST':
		return redirect('exam_management')

	form = ReminderForm(request.POST, user=request.user)
	if form.is_valid():
		reminder = form.save(commit=False)
		reminder.user = request.user
		reminder.save()
		return redirect('exam_management')

	return render(
		request,
		'study_app/exams.html',
		{**_exam_context(request), 'reminder_form': form},
	)


@login_required
def toggle_reminder(request, reminder_id):
	if request.method != 'POST':
		return redirect('exam_management')

	reminder = get_object_or_404(Reminder, pk=reminder_id, user=request.user)
	reminder.is_done = not reminder.is_done
	reminder.save(update_fields=['is_done'])
	return redirect('exam_management')


@login_required
def delete_reminder(request, reminder_id):
	if request.method != 'POST':
		return redirect('exam_management')

	reminder = get_object_or_404(Reminder, pk=reminder_id, user=request.user)
	reminder.delete()
	return redirect('exam_management')


def _subject_context(request, subject_form=None):
	query = request.GET.get('q', '').strip()
	priority = request.GET.get('priority', '')
	category = request.GET.get('category', '').strip()
	today = timezone.localdate()
	week_start = today - timedelta(days=today.weekday())
	subjects = Subject.objects.filter(user=request.user).annotate(
		total_tasks=Count(
			'tasks',
			filter=Q(tasks__user=request.user),
			distinct=True,
		),
		completed_tasks=Count(
			'tasks',
			filter=Q(tasks__user=request.user, tasks__completed=True),
			distinct=True,
		),
	).prefetch_related(
		Prefetch(
			'tasks',
			queryset=StudyTask.objects.filter(user=request.user).order_by('completed', 'title'),
		)
	).order_by('name')
	if query:
		subjects = subjects.filter(Q(name__icontains=query) | Q(description__icontains=query))
	if priority in Subject.Priority.values:
		subjects = subjects.filter(priority=priority)
	if category:
		subjects = subjects.filter(category__iexact=category)

	subjects = list(subjects)
	subject_ids = [subject.pk for subject in subjects]
	weekly_minutes_by_subject = dict(
		StudySession.objects.filter(
			user=request.user,
			subject_id__in=subject_ids,
			date__gte=week_start,
			date__lte=today,
		).values_list('subject_id').annotate(minutes=Sum('duration_minutes'))
	)
	next_exam_by_subject = dict(
		Exam.objects.filter(
			user=request.user,
			subject_id__in=subject_ids,
			date__gte=today,
		).values_list('subject_id').annotate(next_exam=Min('date'))
	)
	for subject in subjects:
		weekly_minutes = weekly_minutes_by_subject.get(subject.pk, 0) or 0
		subject.week_study_minutes = weekly_minutes
		subject.week_study_hours = weekly_minutes / 60
		goal_minutes = int(subject.weekly_goal_hours * 60)
		subject.week_goal_percent = (
			min(round(weekly_minutes / goal_minutes * 100), 100)
			if goal_minutes
			else 0
		)
		exam_dates = [
			exam_date
			for exam_date in (subject.exam_date, next_exam_by_subject.get(subject.pk))
			if exam_date and exam_date >= today
		]
		subject.next_exam_date = min(exam_dates) if exam_dates else None
		subject.days_until_exam = (
			(subject.next_exam_date - today).days if subject.next_exam_date else None
		)

	task_totals = StudyTask.objects.filter(
		user=request.user,
		subject__user=request.user,
	).aggregate(
		total=Count('pk'),
		completed=Count('pk', filter=Q(completed=True)),
	)
	total_tasks = task_totals['total'] or 0
	completed_tasks = task_totals['completed'] or 0
	weekly_study_minutes = StudySession.objects.filter(
		user=request.user,
		subject__user=request.user,
		date__gte=week_start,
		date__lte=today,
	).aggregate(total=Sum('duration_minutes'))['total'] or 0
	return render(
		request,
		'study_app/subjects.html',
		{
			'subjects': subjects,
			'form': subject_form or SubjectForm(),
			'query': query,
			'selected_priority': priority,
			'selected_category': category,
			'priorities': Subject.Priority.choices,
			'categories': Subject.objects.filter(
				user=request.user,
			).exclude(category='').order_by('category').values_list(
				'category', flat=True,
			).distinct(),
			'subject_count': Subject.objects.filter(user=request.user).count(),
			'total_tasks': total_tasks,
			'completed_tasks': completed_tasks,
			'pending_tasks_count': total_tasks - completed_tasks,
			'completion_percent': (
				round(completed_tasks / total_tasks * 100) if total_tasks else 0
			),
			'weekly_study_minutes': weekly_study_minutes,
			'week_start': week_start,
		}
	)


@login_required
def subject_management(request):
	return _subject_context(request)


@login_required
def add_subject(request):
	if request.method != 'POST':
		return redirect('subject_management')

	form = SubjectForm(request.POST)
	if form.is_valid():
		subject = form.save(commit=False)
		subject.user = request.user
		subject.save()
		return redirect('subject_management')
	return _subject_context(request, subject_form=form)


@login_required
def edit_subject(request, subject_id):
	subject = get_object_or_404(Subject, pk=subject_id, user=request.user)

	if request.method == 'POST':
		form = SubjectForm(request.POST, instance=subject)
		if form.is_valid():
			form.save()
			return redirect('subject_management')
	else:
		form = SubjectForm(instance=subject)

	return render(
		request,
		'study_app/edit_subject.html',
		{'subject': subject, 'form': form}
	)


@login_required
def delete_subject(request, subject_id):
	if request.method != 'POST':
		return redirect('subject_management')

	subject = get_object_or_404(Subject, pk=subject_id, user=request.user)
	subject.delete()
	return redirect('subject_management')


@login_required
def task_tracking(request, task_form=None):
	all_tasks = StudyTask.objects.filter(user=request.user)
	tasks = all_tasks.select_related('subject').order_by(
		'completed',
		F('due_date').asc(nulls_last=True),
		'title',
	)
	query = request.GET.get('q', '').strip()[:100]
	status = request.GET.get('status', 'all')
	if status not in {'all', 'pending', 'completed'}:
		status = 'all'
	if query:
		tasks = tasks.filter(
			Q(title__icontains=query) | Q(subject__name__icontains=query)
		)
	if status == 'pending':
		tasks = tasks.filter(completed=False)
	elif status == 'completed':
		tasks = tasks.filter(completed=True)

	selected_subject = ''
	subject_id = request.GET.get('subject', '')
	if subject_id.isdecimal() and len(subject_id) <= 10:
		subject = Subject.objects.filter(user=request.user, pk=int(subject_id)).first()
		if subject:
			selected_subject = subject.pk
			tasks = tasks.filter(subject=subject)

	task_page = Paginator(tasks, 25).get_page(request.GET.get('page'))
	task_counts = all_tasks.aggregate(
		total=Count('pk'),
		pending=Count('pk', filter=Q(completed=False)),
		completed=Count('pk', filter=Q(completed=True)),
	)
	return render(
		request,
		'study_app/tasks.html',
		{
			'tasks': task_page.object_list,
			'page_obj': task_page,
			'form': task_form or StudyTaskForm(user=request.user),
			'completed_tasks_count': task_counts['completed'],
			'pending_tasks_count': task_counts['pending'],
			'total_tasks_count': task_counts['total'],
			'visible_task_count': task_page.paginator.count,
			'query': query,
			'selected_status': status,
			'selected_subject': selected_subject,
			'subjects': Subject.objects.filter(user=request.user).order_by('name'),
		}
	)


@login_required
def progress_tracking(request):
	tasks = StudyTask.objects.filter(user=request.user)
	task_totals = tasks.aggregate(
		total=Count('pk'),
		completed=Count('pk', filter=Q(completed=True)),
	)
	total_tasks = task_totals['total']
	completed_tasks = task_totals['completed']
	today = timezone.localdate()
	week_start = today - timedelta(days=6)
	study_minutes = (
		StudySession.objects.filter(user=request.user)
		.aggregate(total=Sum('duration_minutes'))['total']
		or 0
	)
	daily_study_minutes = (
		StudySession.objects.filter(user=request.user, date=today)
		.aggregate(total=Sum('duration_minutes'))['total']
		or 0
	)
	weekly_study_minutes = (
		StudySession.objects.filter(
			user=request.user,
			date__gte=week_start,
			date__lte=today,
		).aggregate(total=Sum('duration_minutes'))['total']
		or 0
	)
	review_stats = Flashcard.objects.filter(user=request.user).aggregate(
		reviews=Sum('review_count'),
		correct=Sum('correct_count'),
	)
	review_count = review_stats['reviews'] or 0
	correct_count = review_stats['correct'] or 0
	subject_minutes = {
		row['subject_id']: row['minutes'] or 0
		for row in StudySession.objects.filter(user=request.user)
		.values('subject_id')
		.annotate(minutes=Sum('duration_minutes'))
	}
	subjects = Subject.objects.filter(user=request.user).annotate(
		total_tasks=Count('tasks', distinct=True),
		completed_tasks=Count(
			'tasks',
			filter=Q(tasks__completed=True),
			distinct=True,
		),
	).order_by('name')
	for subject in subjects:
		subject.study_minutes = subject_minutes.get(subject.pk, 0)

	return render(
		request,
		'study_app/progress.html',
		{
			'total_tasks': total_tasks,
			'completed_tasks': completed_tasks,
			'pending_tasks': total_tasks - completed_tasks,
			'completion_percent': round(completed_tasks / total_tasks * 100) if total_tasks else 0,
			'study_minutes': study_minutes,
			'daily_study_minutes': daily_study_minutes,
			'weekly_study_minutes': weekly_study_minutes,
			'report_week_start': week_start,
			'quiz_reviews': review_count,
			'quiz_accuracy': round(correct_count / review_count * 100) if review_count else 0,
			'subjects': subjects,
		},
	)


@login_required
def study_planner(request):
	today = timezone.localdate()
	goal, _ = StudyGoal.objects.get_or_create(user=request.user)
	start_time_key = f'study_planner_start_{request.user.pk}'
	try:
		start_time = time.fromisoformat(request.session.get(start_time_key, '09:00'))
	except ValueError:
		start_time = time(9, 0)

	form = PlannerSettingsForm(initial={
		'daily_minutes': goal.daily_minutes,
		'start_time': start_time,
	})
	if request.method == 'POST':
		form = PlannerSettingsForm(request.POST)
		if form.is_valid():
			goal.daily_minutes = form.cleaned_data['daily_minutes']
			goal.save(update_fields=['daily_minutes'])
			start_time = form.cleaned_data['start_time']
			request.session[start_time_key] = start_time.strftime('%H:%M')
			return redirect('study_planner')

	logged_today = (
		StudySession.objects.filter(user=request.user, date=today)
		.aggregate(total=Sum('duration_minutes'))['total']
		or 0
	)
	available_minutes = max(goal.daily_minutes - logged_today, 0)
	pending_tasks = list(
		StudyTask.objects.filter(user=request.user, completed=False)
		.select_related('subject')
	)
	exam_dates_by_subject = {}
	for subject_id, exam_date in Subject.objects.filter(
		user=request.user,
		exam_date__gte=today,
	).values_list('pk', 'exam_date'):
		exam_dates_by_subject[subject_id] = exam_date
	for subject_id, exam_date in Exam.objects.filter(
		user=request.user,
		subject__user=request.user,
		subject__isnull=False,
		date__gte=today,
	).values_list('subject_id', 'date'):
		current_exam_date = exam_dates_by_subject.get(subject_id)
		if current_exam_date is None or exam_date < current_exam_date:
			exam_dates_by_subject[subject_id] = exam_date
	for task in pending_tasks:
		task.upcoming_exam_date = exam_dates_by_subject.get(task.subject_id)
	plan = build_daily_plan(
		pending_tasks,
		today,
		available_minutes,
		start_time,
	)
	scheduled_task_ids = {block['task'].pk for block in plan}
	unscheduled_count = sum(
		task.pk not in scheduled_task_ids or any(
			block['task'].pk == task.pk and block['is_partial']
			for block in plan
		)
		for task in pending_tasks
	)
	return render(
		request,
		'study_app/planner.html',
		{
			'form': form,
			'plan': plan,
			'today': today,
			'daily_minutes': goal.daily_minutes,
			'logged_today': logged_today,
			'planned_minutes': sum(block['minutes'] for block in plan),
			'pending_count': len(pending_tasks),
			'unscheduled_count': unscheduled_count,
			'start_time': start_time,
		},
	)


def register(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	next_url = request.POST.get('next') or request.GET.get('next', '')
	if request.method == 'POST':
		form = RegistrationForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Your account was created. Please log in to continue.')
			login_url = reverse('login')
			if next_url and url_has_allowed_host_and_scheme(
				next_url,
				allowed_hosts={request.get_host()},
				require_https=request.is_secure(),
			):
				login_url = f'{login_url}?{urlencode({"next": next_url})}'
			return redirect(login_url)
	else:
		form = RegistrationForm()

	return render(
		request,
		'study_app/register.html',
		{'form': form, 'next_url': next_url},
	)


def user_login(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	if request.method == 'POST':
		form = AuthenticationForm(request, data=request.POST)
		if form.is_valid():
			login(request, form.get_user())
			next_url = request.POST.get('next')
			if next_url and url_has_allowed_host_and_scheme(
				next_url,
				allowed_hosts={request.get_host()},
				require_https=request.is_secure(),
			):
				return redirect(next_url)
			return redirect('dashboard')
	else:
		form = AuthenticationForm()

	return render(request, 'study_app/login.html', {'form': form})


def user_logout(request):
	if request.method == 'POST':
		logout(request)
	return redirect('home')


@login_required
def add_task(request):
	if request.method != 'POST':
		return redirect('task_tracking')

	form = StudyTaskForm(request.POST, user=request.user)
	if form.is_valid():
		task = form.save(commit=False)
		task.user = request.user
		task.save()
		return redirect('task_tracking')

	return task_tracking(request, task_form=form)


@login_required
def edit_task(request, task_id):
	task = get_object_or_404(StudyTask, pk=task_id, user=request.user)

	if request.method == 'POST':
		form = StudyTaskForm(request.POST, instance=task, user=request.user)
		if form.is_valid():
			form.save()
			return redirect('task_tracking')
	else:
		form = StudyTaskForm(instance=task, user=request.user)

	return render(request, 'study_app/edit_task.html', {'task': task, 'form': form})


@login_required
def toggle_task(request, task_id):
	if request.method != 'POST':
		return redirect('task_tracking')

	task = get_object_or_404(StudyTask, pk=task_id, user=request.user)
	task.completed = not task.completed
	task.save()
	return redirect('task_tracking')


@login_required
def delete_task(request, task_id):
	if request.method != 'POST':
		return redirect('task_tracking')

	task = get_object_or_404(StudyTask, pk=task_id, user=request.user)
	task.delete()
	return redirect('task_tracking')


@login_required
def learning_hub(request, session_form=None, flashcard_form=None, note_form=None):
	today = timezone.localdate()
	cards = (
		Flashcard.objects.filter(user=request.user)
		.select_related('subject')
		.order_by('next_review_date', 'subject__name', 'front')
	)
	review_stats = cards.aggregate(reviews=Sum('review_count'), correct=Sum('correct_count'))
	return render(
		request,
		'study_app/learning_hub.html',
		{
			'session_form': session_form or StudySessionForm(user=request.user),
			'flashcard_form': flashcard_form or FlashcardForm(user=request.user),
			'note_form': note_form or StudyNoteForm(user=request.user),
			'flashcards': cards,
			'today': today,
			'due_flashcards_count': cards.filter(next_review_date__lte=today).count(),
			'notes': StudyNote.objects.filter(user=request.user).select_related('subject'),
			'sessions': StudySession.objects.filter(user=request.user).select_related('subject')[:10],
			'study_minutes': (
				StudySession.objects.filter(user=request.user)
				.aggregate(total=Sum('duration_minutes'))['total']
				or 0
			),
			'quiz_reviews': review_stats['reviews'] or 0,
			'quiz_accuracy': (
				round((review_stats['correct'] or 0) / review_stats['reviews'] * 100)
				if review_stats['reviews']
				else 0
			),
		},
	)


@login_required
def study_calendar(request):
	today = timezone.localdate()
	month_value = request.GET.get('month', '')
	if month_value:
		try:
			year_text, month_text = month_value.split('-', 1)
			if (
				len(year_text) != 4
				or len(month_text) != 2
				or not year_text.isdecimal()
				or not month_text.isdecimal()
			):
				raise ValueError
			year, month = int(year_text), int(month_text)
			if not 1900 <= year <= 2100 or not 1 <= month <= 12:
				raise ValueError
			first_day = date(year, month, 1)
		except (ValueError, TypeError):
			return HttpResponseBadRequest(
				'Choose a valid calendar month between January 1900 and December 2100.'
			)
	else:
		first_day = today.replace(day=1)

	last_day_number = calendar.monthrange(first_day.year, first_day.month)[1]
	last_day = first_day.replace(day=last_day_number)
	next_month = (
		date(first_day.year + 1, 1, 1)
		if first_day.month == 12
		else date(first_day.year, first_day.month + 1, 1)
	)
	reminder_month_start = timezone.make_aware(datetime.combine(first_day, time.min))
	reminder_month_end = timezone.make_aware(datetime.combine(next_month, time.min))
	events_by_date = {}

	def add_event(event_date, title, kind, subject_name=''):
		events_by_date.setdefault(event_date, []).append(
			{'title': title, 'kind': kind, 'subject': subject_name}
		)

	for exam in Exam.objects.filter(
		user=request.user, date__gte=first_day, date__lte=last_day
	).select_related('subject'):
		add_event(exam.date, exam.title, 'Exam', exam.subject.name if exam.subject else '')

	for subject in Subject.objects.filter(
		user=request.user,
		exam_date__gte=first_day,
		exam_date__lte=last_day,
	):
		add_event(subject.exam_date, f'{subject.name} exam', 'Exam', subject.name)

	for reminder in Reminder.objects.filter(
		user=request.user,
		is_done=False,
		remind_at__gte=reminder_month_start,
		remind_at__lt=reminder_month_end,
	).select_related('exam'):
		add_event(
			timezone.localtime(reminder.remind_at).date(),
			reminder.title,
			'Study reminder',
			reminder.exam.title if reminder.exam_id else '',
		)

	for task in StudyTask.objects.filter(
		user=request.user,
		completed=False,
		due_date__gte=first_day,
		due_date__lte=last_day,
	).select_related('subject'):
		add_event(
			task.due_date,
			task.title,
			'Task deadline',
			task.subject.name if task.subject else '',
		)

	for session in StudySession.objects.filter(
		user=request.user, date__gte=first_day, date__lte=last_day
	).select_related('subject'):
		add_event(
			session.date,
			f'{session.subject.name} study session ({session.duration_minutes} min)',
			'Study session',
			session.subject.name,
		)

	weeks = []
	for week in calendar.Calendar(firstweekday=0).monthdayscalendar(first_day.year, first_day.month):
		weeks.append(
			[
				{
					'day': day,
					'date': date(first_day.year, first_day.month, day) if day else None,
					'events': events_by_date.get(
						date(first_day.year, first_day.month, day), []
					) if day else [],
				}
				for day in week
			]
		)

	previous_month = (
		date(first_day.year - 1, 12, 1)
		if first_day.month == 1
		else date(first_day.year, first_day.month - 1, 1)
	)
	return render(
		request,
		'study_app/calendar.html',
		{
			'month_start': first_day,
			'month_label': first_day.strftime('%B %Y'),
			'month_value': first_day.strftime('%Y-%m'),
			'previous_month': previous_month.strftime('%Y-%m'),
			'next_month': next_month.strftime('%Y-%m'),
			'can_previous': first_day.year > 1900 or first_day.month > 1,
			'can_next': first_day.year < 2100 or first_day.month < 12,
			'today': today,
			'weeks': weeks,
			'event_count': sum(len(events) for events in events_by_date.values()),
			'month_events': sorted(
				(
					{'date': event_date, **event}
					for event_date, events in events_by_date.items()
					for event in events
				),
				key=lambda event: (event['date'], event['kind'], event['title']),
			),
		},
	)


@login_required
def add_study_session(request):
	if request.method != 'POST':
		return redirect('learning_hub')
	form = StudySessionForm(request.POST, user=request.user)
	if form.is_valid():
		session = form.save(commit=False)
		session.user = request.user
		session.save()
		return redirect('learning_hub')
	return learning_hub(request, session_form=form)


@login_required
def add_flashcard(request):
	if request.method != 'POST':
		return redirect('learning_hub')
	form = FlashcardForm(request.POST, user=request.user)
	if form.is_valid():
		card = form.save(commit=False)
		card.user = request.user
		card.save()
		return redirect('learning_hub')
	return learning_hub(request, flashcard_form=form)


@login_required
def review_flashcard(request, card_id):
	if request.method != 'POST':
		return redirect('learning_hub')
	card = get_object_or_404(Flashcard, pk=card_id, user=request.user)
	result = request.POST.get('result')
	if result not in {'correct', 'incorrect'}:
		return HttpResponseBadRequest('Choose whether you knew the answer.')
	card.review_count += 1
	remembered = result == 'correct'
	if remembered:
		card.correct_count += 1
	card.interval_days, card.ease_factor, card.next_review_date = schedule_next_review(
		card.interval_days,
		card.ease_factor,
		remembered,
		timezone.localdate(),
	)
	card.save(update_fields=[
		'review_count',
		'correct_count',
		'interval_days',
		'ease_factor',
		'next_review_date',
	])
	return redirect('learning_hub')


@login_required
def add_study_note(request):
	if request.method != 'POST':
		return redirect('learning_hub')
	form = StudyNoteForm(request.POST, user=request.user)
	if form.is_valid():
		note = form.save(commit=False)
		note.user = request.user
		note.save()
		return redirect('learning_hub')
	return learning_hub(request, note_form=form)


@login_required
def delete_study_note(request, note_id):
	if request.method != 'POST':
		return redirect('learning_hub')
	note = get_object_or_404(StudyNote, pk=note_id, user=request.user)
	note.delete()
	return redirect('learning_hub')
