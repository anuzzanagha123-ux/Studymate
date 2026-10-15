from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

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

CALENDAR_MIN_DATE = date(1900, 1, 1)
CALENDAR_MAX_DATE = date(2100, 12, 31)


class StudyTaskForm(forms.ModelForm):
    checklist_items = forms.CharField(
        required=False,
        label='Checklist (one item per line)',
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Read chapter 4\nComplete practice questions',
        }),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['priority'].required = False
        self.fields['recurrence'].required = False
        self.fields['estimated_minutes'].required = False
        self.fields['due_date'].widget.attrs.update({
            'min': CALENDAR_MIN_DATE.isoformat(),
            'max': CALENDAR_MAX_DATE.isoformat(),
        })
        if self.instance and self.instance.pk:
            self.fields['checklist_items'].initial = '\n'.join(
                self.instance.checklist_items.values_list('title', flat=True)
            )
        if user is not None:
            self.fields['subject'].queryset = Subject.objects.filter(user=user)

    class Meta:
        model = StudyTask
        fields = [
            'title',
            'subject',
            'due_date',
            'priority',
            'difficulty',
            'recurrence',
            'estimated_minutes',
        ]
        labels = {
            'title': 'New study task',
            'subject': 'Subject (optional)',
            'due_date': 'Due date (optional)',
            'priority': 'Priority',
            'difficulty': 'Topic difficulty',
            'recurrence': 'Repeat',
            'estimated_minutes': 'Estimated minutes',
        }
        widgets = {
            'title': forms.TextInput(
                attrs={'placeholder': 'What do you need to study?'}
            ),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'estimated_minutes': forms.NumberInput(attrs={'min': 1, 'max': 600}),
        }

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise forms.ValidationError('Enter a task title.')
        return title

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and not CALENDAR_MIN_DATE <= due_date <= CALENDAR_MAX_DATE:
            raise forms.ValidationError('Choose a date between January 1900 and December 2100.')
        return due_date

    def clean_priority(self):
        return self.cleaned_data.get('priority') or StudyTask.Priority.MEDIUM

    def clean_recurrence(self):
        return self.cleaned_data.get('recurrence') or StudyTask.Recurrence.NONE

    def clean_estimated_minutes(self):
        value = self.cleaned_data.get('estimated_minutes')
        return 30 if value is None else value

    def clean_checklist_items(self):
        lines = self.cleaned_data['checklist_items'].splitlines()
        items = list(dict.fromkeys(line.strip() for line in lines if line.strip()))
        if len(items) > 20:
            raise forms.ValidationError('A task can have at most 20 checklist items.')
        if any(len(item) > 200 for item in items):
            raise forms.ValidationError('Checklist items must be 200 characters or fewer.')
        return items

    def sync_checklist(self, task):
        old_items = {item.title: item for item in task.checklist_items.all()}
        keep_ids = []
        for position, title in enumerate(self.cleaned_data.get('checklist_items', [])):
            item = old_items.get(title)
            if item is None:
                item = TaskChecklistItem.objects.create(
                    task=task,
                    title=title,
                    position=position,
                )
            elif item.position != position:
                item.position = position
                item.save(update_fields=['position'])
            keep_ids.append(item.pk)
        task.checklist_items.exclude(pk__in=keep_ids).delete()


class SubjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['weekly_goal_hours'].required = False
        self.fields['color'].required = False
        self.fields['exam_date'].widget.attrs.update({
            'min': timezone.localdate().isoformat(),
            'max': CALENDAR_MAX_DATE.isoformat(),
        })

    class Meta:
        model = Subject
        fields = [
            'name',
            'category',
            'description',
            'priority',
            'color',
            'study_hours',
            'weekly_goal_hours',
            'exam_date',
        ]
        labels = {
            'name': 'Subject name',
            'category': 'Category',
            'description': 'Description',
            'priority': 'Priority',
            'color': 'Card color',
            'study_hours': 'Study hours',
            'weekly_goal_hours': 'Weekly study goal (hours)',
            'exam_date': 'Exam date (optional)',
        }
        help_texts = {
            'weekly_goal_hours': 'Set to 0 if you do not want a weekly target.',
        }
        widgets = {
            'name': forms.TextInput(
                attrs={'placeholder': 'e.g. Mathematics'}
            ),
            'category': forms.TextInput(
                attrs={'placeholder': 'e.g. Science, Core, or Elective'}
            ),
            'description': forms.Textarea(
                attrs={'placeholder': 'Add a short description', 'rows': 3}
            ),
            'study_hours': forms.NumberInput(attrs={'min': '0', 'step': '0.5'}),
            'weekly_goal_hours': forms.NumberInput(
                attrs={'min': '0', 'max': '168', 'step': '0.5'}
            ),
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_category(self):
        return self.cleaned_data['category'].strip()

    def clean_weekly_goal_hours(self):
        value = self.cleaned_data.get('weekly_goal_hours')
        return 5 if value is None else value

    def clean_color(self):
        return self.cleaned_data.get('color') or Subject.Color.BLUE

    def clean_exam_date(self):
        exam_date = self.cleaned_data.get('exam_date')
        if exam_date is not None:
            if exam_date < timezone.localdate():
                raise forms.ValidationError('Choose today or a future date for the exam.')
            if exam_date > CALENDAR_MAX_DATE:
                raise forms.ValidationError('Choose an exam date on or before December 31, 2100.')
        return exam_date


class ExamForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['exam_type'].required = False
        self.fields['priority'].required = False
        self.fields['preparation_percent'].required = False
        self.fields['date'].widget.attrs.update({
            'min': timezone.localdate().isoformat(),
            'max': CALENDAR_MAX_DATE.isoformat(),
        })
        if user is not None:
            self.fields['subject'].queryset = Subject.objects.filter(user=user)

    class Meta:
        model = Exam
        fields = [
            'title',
            'date',
            'subject',
            'exam_type',
            'priority',
            'topics',
            'preparation_percent',
        ]
        labels = {
            'title': 'Exam name',
            'date': 'Exam date',
            'subject': 'Subject (optional)',
            'exam_type': 'Exam format',
            'priority': 'Priority',
            'topics': 'Topics to prepare',
            'preparation_percent': 'Preparation complete (%)',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Biology final'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
            'topics': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'List chapters, units, or skills to review'}
            ),
            'preparation_percent': forms.NumberInput(
                attrs={'min': 0, 'max': 100, 'step': 5}
            ),
        }

    def clean_date(self):
        exam_date = self.cleaned_data['date']
        if exam_date < timezone.localdate():
            raise forms.ValidationError('Choose today or a future date for the exam.')
        if exam_date > CALENDAR_MAX_DATE:
            raise forms.ValidationError('Choose an exam date on or before December 31, 2100.')
        return exam_date

    def clean_exam_type(self):
        return self.cleaned_data.get('exam_type') or Exam.ExamType.WRITTEN

    def clean_priority(self):
        return self.cleaned_data.get('priority') or Exam.Priority.MEDIUM

    def clean_preparation_percent(self):
        value = self.cleaned_data.get('preparation_percent')
        return 0 if value is None else value


class ReminderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['exam'].required = False
        local_now = timezone.localtime(timezone.now())
        self.fields['remind_at'].widget.attrs.update({
            'min': local_now.strftime('%Y-%m-%dT%H:%M'),
            'max': '2100-12-31T23:59',
        })
        self.fields['exam'].queryset = (
            Exam.objects.filter(user=user, date__gte=timezone.localdate()).order_by('date', 'title')
            if user else Exam.objects.none()
        )

    class Meta:
        model = Reminder
        fields = ['title', 'remind_at', 'exam', 'note']
        labels = {
            'title': 'Reminder',
            'remind_at': 'Reminder date and time',
            'exam': 'Related exam (optional)',
            'note': 'Note (optional)',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Review biology flashcards'}),
            'remind_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'note': forms.TextInput(attrs={'maxlength': 500, 'placeholder': 'Add a short note'}),
        }

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise forms.ValidationError('Enter a reminder title.')
        return title

    def clean_remind_at(self):
        remind_at = self.cleaned_data['remind_at']
        local_remind_at = timezone.localtime(remind_at) if timezone.is_aware(remind_at) else remind_at
        if local_remind_at.date() < timezone.localdate():
            raise forms.ValidationError('Choose a reminder time in the future.')
        if local_remind_at.date() < CALENDAR_MIN_DATE or local_remind_at.date() > CALENDAR_MAX_DATE:
            raise forms.ValidationError('Choose a reminder date between January 1900 and December 2100.')
        if remind_at <= timezone.now():
            raise forms.ValidationError('Choose a reminder time in the future.')
        return remind_at

    def clean(self):
        cleaned_data = super().clean()
        remind_at = cleaned_data.get('remind_at')
        exam = cleaned_data.get('exam')
        if remind_at and exam:
            reminder_date = timezone.localtime(remind_at).date() if timezone.is_aware(remind_at) else remind_at.date()
            if reminder_date > exam.date:
                self.add_error('remind_at', 'Set the reminder on or before the related exam date.')
        return cleaned_data


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'


class StudySessionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['date'].widget.attrs.update({
            'min': CALENDAR_MIN_DATE.isoformat(),
            'max': timezone.localdate().isoformat(),
        })
        self.fields['subject'].queryset = Subject.objects.filter(user=user) if user else Subject.objects.none()
        self.fields['task'].required = False
        self.fields['task'].queryset = StudyTask.objects.filter(
            user=user,
            completed=False,
        ) if user else StudyTask.objects.none()

    class Meta:
        model = StudySession
        fields = ['subject', 'task', 'date', 'duration_minutes', 'notes']
        labels = {
            'subject': 'Subject',
            'task': 'Task (optional)',
            'date': 'Study date',
            'duration_minutes': 'Minutes studied',
            'notes': 'Session notes (optional)',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'duration_minutes': forms.NumberInput(attrs={'min': 1, 'max': 600}),
            'notes': forms.TextInput(attrs={'maxlength': 500, 'placeholder': 'What did you cover?'}),
        }

    def clean_date(self):
        study_date = self.cleaned_data['date']
        if study_date < CALENDAR_MIN_DATE:
            raise forms.ValidationError('Choose a study date on or after January 1, 1900.')
        if study_date > timezone.localdate():
            raise forms.ValidationError('A study session cannot be dated in the future.')
        return study_date

    def clean(self):
        cleaned_data = super().clean()
        task = cleaned_data.get('task')
        subject = cleaned_data.get('subject')
        if task and subject and task.subject_id != subject.pk:
            self.add_error('task', 'Choose a task that belongs to the selected subject.')
        return cleaned_data


class StudyGoalForm(forms.ModelForm):
    class Meta:
        model = StudyGoal
        fields = ['weekly_minutes', 'daily_minutes']
        labels = {
            'weekly_minutes': 'Weekly study target (minutes)',
            'daily_minutes': 'Daily study target (minutes)',
        }
        widgets = {
            'weekly_minutes': forms.NumberInput(attrs={'min': 1, 'max': 10080}),
            'daily_minutes': forms.NumberInput(attrs={'min': 1, 'max': 1440}),
        }


class PlannerSettingsForm(forms.Form):
	daily_minutes = forms.IntegerField(
		min_value=1,
		max_value=1440,
		label='Available study minutes today',
		widget=forms.NumberInput(attrs={'min': 1, 'max': 1440, 'step': 15}),
	)
	start_time = forms.TimeField(
		label='Start time',
		widget=forms.TimeInput(attrs={'type': 'time'}),
	)


class StudyCoachForm(forms.Form):
    MODES = (
        ('ask', 'Explain a topic'),
        ('plan', 'Build my revision plan'),
        ('quiz', 'Make a practice quiz'),
    )

    mode = forms.ChoiceField(
        choices=MODES,
        label='What do you need?',
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        required=False,
        empty_label='All my subjects',
        label='Study context',
    )
    prompt = forms.CharField(
        required=False,
        max_length=800,
        label='Your question or topic',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'maxlength': 800,
            'placeholder': 'For example: Explain quadratic equations with a simple example.',
        }),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = (
            Subject.objects.filter(user=user).order_by('name') if user else Subject.objects.none()
        )

    def clean_prompt(self):
        return self.cleaned_data.get('prompt', '').strip()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('mode') == 'ask' and not cleaned_data.get('prompt'):
            self.add_error('prompt', 'Add a topic or question for your study coach.')
        if cleaned_data.get('mode') == 'quiz' and not cleaned_data.get('subject'):
            self.add_error('subject', 'Choose a subject so the quiz can use your study material.')
        return cleaned_data


class FlashcardForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.filter(user=user) if user else Subject.objects.none()

    class Meta:
        model = Flashcard
        fields = ['subject', 'front', 'back']
        labels = {'subject': 'Subject', 'front': 'Question / front', 'back': 'Answer / back'}
        widgets = {
            'front': forms.TextInput(attrs={'maxlength': 300, 'placeholder': 'Enter a question'}),
            'back': forms.Textarea(attrs={'maxlength': 2000, 'rows': 3, 'placeholder': 'Enter the answer'}),
        }

    def clean_front(self):
        front = self.cleaned_data['front'].strip()
        if not front:
            raise forms.ValidationError('Enter a question for the flashcard.')
        return front

    def clean_back(self):
        back = self.cleaned_data['back'].strip()
        if not back:
            raise forms.ValidationError('Enter an answer for the flashcard.')
        return back


class StudyNoteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.filter(user=user) if user else Subject.objects.none()

    class Meta:
        model = StudyNote
        fields = ['subject', 'title', 'content']
        labels = {'subject': 'Subject (optional)', 'title': 'Note title', 'content': 'Note'}
        widgets = {
            'title': forms.TextInput(attrs={'maxlength': 200, 'placeholder': 'Give this note a title'}),
            'content': forms.Textarea(attrs={'maxlength': 10000, 'rows': 5, 'placeholder': 'Write your study notes'}),
        }

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise forms.ValidationError('Enter a title for the note.')
        return title

    def clean_content(self):
        content = self.cleaned_data['content'].strip()
        if not content:
            raise forms.ValidationError('Enter some note content.')
        return content
