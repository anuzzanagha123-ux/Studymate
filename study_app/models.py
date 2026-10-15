from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class StudyTask(models.Model):
	class Recurrence(models.TextChoices):
		NONE = 'none', 'Does not repeat'
		DAILY = 'daily', 'Daily'
		WEEKLY = 'weekly', 'Weekly'
		MONTHLY = 'monthly', 'Monthly'

	class Priority(models.TextChoices):
		HIGH = 'high', 'High'
		MEDIUM = 'medium', 'Medium'
		LOW = 'low', 'Low'

	class Difficulty(models.TextChoices):
		EASY = 'easy', 'Easy'
		MEDIUM = 'medium', 'Medium'
		HARD = 'hard', 'Hard'

	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='study_tasks')
	title = models.CharField(max_length=200)
	completed = models.BooleanField(default=False)
	due_date = models.DateField(null=True, blank=True)
	recurrence = models.CharField(
		max_length=7,
		choices=Recurrence.choices,
		default=Recurrence.NONE,
	)
	estimated_minutes = models.PositiveSmallIntegerField(
		default=30,
		validators=[MinValueValidator(1), MaxValueValidator(600)],
	)
	priority = models.CharField(
		max_length=6,
		choices=Priority.choices,
		default=Priority.MEDIUM,
	)
	difficulty = models.CharField(
		max_length=6,
		choices=Difficulty.choices,
		default=Difficulty.MEDIUM,
	)
	subject = models.ForeignKey(
		'Subject',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='tasks',
	)

	class Meta:
		indexes = [
			models.Index(fields=['user', 'completed', 'due_date'], name='task_user_status_due_idx'),
			models.Index(fields=['user', 'subject'], name='task_user_subject_idx'),
		]

	def __str__(self):
		return self.title


class TaskChecklistItem(models.Model):
	task = models.ForeignKey(StudyTask, on_delete=models.CASCADE, related_name='checklist_items')
	title = models.CharField(max_length=200)
	position = models.PositiveSmallIntegerField(default=0)
	is_done = models.BooleanField(default=False)

	class Meta:
		ordering = ('position', 'pk')

	def __str__(self):
		return self.title


class Subject(models.Model):
	class Priority(models.TextChoices):
		HIGH = 'high', 'High'
		MEDIUM = 'medium', 'Medium'
		LOW = 'low', 'Low'

	class Color(models.TextChoices):
		BLUE = '#2563eb', 'Blue'
		VIOLET = '#7c3aed', 'Violet'
		TEAL = '#0f766e', 'Teal'
		AMBER = '#b45309', 'Amber'
		ROSE = '#be123c', 'Rose'

	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='study_subjects')
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	category = models.CharField(max_length=50, blank=True)
	priority = models.CharField(
		max_length=6,
		choices=Priority.choices,
		default=Priority.MEDIUM,
	)
	exam_date = models.DateField(null=True, blank=True)
	study_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
	weekly_goal_hours = models.DecimalField(
		max_digits=4,
		decimal_places=1,
		default=5,
		validators=[MinValueValidator(0), MaxValueValidator(168)],
	)
	color = models.CharField(max_length=7, choices=Color.choices, default=Color.BLUE)

	class Meta:
		indexes = [
			models.Index(fields=['user', 'name'], name='subject_user_name_idx'),
		]

	def __str__(self):
		return self.name

	@property
	def progress_percent(self):
		total_tasks = getattr(self, 'total_tasks', None)
		completed_tasks = getattr(self, 'completed_tasks', None)
		if total_tasks is None or completed_tasks is None:
			total_tasks = self.tasks.count()
			completed_tasks = self.tasks.filter(completed=True).count()
		return round(completed_tasks / total_tasks * 100) if total_tasks else 0


class Exam(models.Model):
	class ExamType(models.TextChoices):
		WRITTEN = 'written', 'Written'
		ORAL = 'oral', 'Oral'
		PRACTICAL = 'practical', 'Practical'
		ONLINE = 'online', 'Online'

	class Priority(models.TextChoices):
		HIGH = 'high', 'High'
		MEDIUM = 'medium', 'Medium'
		LOW = 'low', 'Low'

	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='study_exams')
	title = models.CharField(max_length=200)
	date = models.DateField()
	exam_type = models.CharField(
		max_length=10,
		choices=ExamType.choices,
		default=ExamType.WRITTEN,
	)
	priority = models.CharField(
		max_length=6,
		choices=Priority.choices,
		default=Priority.MEDIUM,
	)
	topics = models.TextField(blank=True)
	preparation_percent = models.PositiveSmallIntegerField(
		default=0,
		validators=[MinValueValidator(0), MaxValueValidator(100)],
	)
	subject = models.ForeignKey(
		Subject,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='exams',
	)

	class Meta:
		indexes = [
			models.Index(fields=['user', 'date'], name='exam_user_date_idx'),
		]

	def __str__(self):
		return self.title


class Reminder(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_reminders')
	title = models.CharField(max_length=200)
	remind_at = models.DateTimeField()
	note = models.CharField(max_length=500, blank=True)
	is_done = models.BooleanField(default=False)
	exam = models.ForeignKey(
		Exam,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='reminders',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ('is_done', 'remind_at', 'title')
		indexes = [
			models.Index(fields=['user', 'is_done', 'remind_at'], name='reminder_user_status_at_idx'),
		]

	def __str__(self):
		return self.title


class StudySession(models.Model):
	class SessionType(models.TextChoices):
		STUDY = 'study', 'Study session'
		FOCUS = 'focus', 'Focus timer'

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_sessions')
	subject = models.ForeignKey(
		Subject,
		on_delete=models.CASCADE,
		related_name='study_sessions',
	)
	task = models.ForeignKey(
		StudyTask,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='study_sessions',
	)
	date = models.DateField(default=timezone.localdate)
	duration_minutes = models.PositiveSmallIntegerField(
		validators=[MinValueValidator(1), MaxValueValidator(600)]
	)
	session_type = models.CharField(
		max_length=5,
		choices=SessionType.choices,
		default=SessionType.STUDY,
	)
	notes = models.CharField(max_length=500, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ('-date', '-created_at')
		indexes = [
			models.Index(fields=['user', 'date'], name='session_user_date_idx'),
			models.Index(fields=['user', 'subject', 'date'], name='session_user_subject_date_idx'),
		]

	def __str__(self):
		return f'{self.subject.name}: {self.duration_minutes} minutes'


class StudyGoal(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='study_goal')
	weekly_minutes = models.PositiveSmallIntegerField(
		default=300,
		validators=[MinValueValidator(1), MaxValueValidator(10080)],
	)
	daily_minutes = models.PositiveSmallIntegerField(
		default=30,
		validators=[MinValueValidator(1), MaxValueValidator(1440)],
	)

	def __str__(self):
		return f'{self.user.username}: {self.weekly_minutes} minutes per week'


class Flashcard(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flashcards')
	subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='flashcards')
	front = models.CharField(max_length=300)
	back = models.TextField(max_length=2000)
	review_count = models.PositiveIntegerField(default=0)
	correct_count = models.PositiveIntegerField(default=0)
	interval_days = models.PositiveSmallIntegerField(default=0)
	ease_factor = models.DecimalField(max_digits=3, decimal_places=2, default=2.50)
	next_review_date = models.DateField(default=timezone.localdate)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ('subject__name', 'front')

	def __str__(self):
		return self.front

	@property
	def accuracy_percent(self):
		return round(self.correct_count / self.review_count * 100) if self.review_count else 0


class StudyNote(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_notes')
	subject = models.ForeignKey(
		Subject,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='notes',
	)
	title = models.CharField(max_length=200)
	content = models.TextField(max_length=10000)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ('-updated_at',)

	def __str__(self):
		return self.title
