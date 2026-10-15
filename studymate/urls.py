"""
URL configuration for studymate project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from study_app.views import (
    add_exam,
    add_flashcard,
    add_reminder,
    add_subject,
    add_study_note,
    add_study_session,
    add_task,
    dashboard,
    delete_study_note,
    delete_exam,
    delete_reminder,
    delete_subject,
    delete_task,
    edit_subject,
    edit_exam,
    edit_task,
    exam_management,
    focus_timer,
    home,
    learning_hub,
    module_detail,
    progress_tracking,
    study_planner,
    register,
    review_flashcard,
    subject_management,
    study_strategies,
    study_calendar,
    study_coach,
    task_tracking,
    toggle_task,
    toggle_reminder,
    user_login,
    user_logout,
)

urlpatterns = [
    # Public pages and account access.
    path('', home, name='home'),
    path('register/', register, name='register'),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),

    # Dashboard and feature overview.
    path('dashboard/', dashboard, name='dashboard'),
    path('modules/<slug:slug>/', module_detail, name='module_detail'),

    # Subjects and tasks.
    path('subjects/', subject_management, name='subject_management'),
    path('subjects/add/', add_subject, name='add_subject'),
    path('subjects/edit/<int:subject_id>/', edit_subject, name='edit_subject'),
    path('subjects/delete/<int:subject_id>/', delete_subject, name='delete_subject'),
    path('tasks/', task_tracking, name='task_tracking'),
    path('add/', add_task, name='add_task'),
    path('edit/<int:task_id>/', edit_task, name='edit_task'),
    path('toggle/<int:task_id>/', toggle_task, name='toggle_task'),
    path('delete/<int:task_id>/', delete_task, name='delete_task'),

    # Exams and reminders.
    path('exams/', exam_management, name='exam_management'),
    path('exams/add/', add_exam, name='add_exam'),
    path('exams/edit/<int:exam_id>/', edit_exam, name='edit_exam'),
    path('exams/delete/<int:exam_id>/', delete_exam, name='delete_exam'),
    path('reminders/add/', add_reminder, name='add_reminder'),
    path('reminders/<int:reminder_id>/toggle/', toggle_reminder, name='toggle_reminder'),
    path('reminders/<int:reminder_id>/delete/', delete_reminder, name='delete_reminder'),

    # Progress, planning, and calendar.
    path('progress/', progress_tracking, name='progress_tracking'),
    path('planner/', study_planner, name='study_planner'),
    path('calendar/', study_calendar, name='study_calendar'),
    path('coach/', study_coach, name='study_coach'),

    # Learning tools.
    path('learning/', learning_hub, name='learning_hub'),
    path('learning/sessions/add/', add_study_session, name='add_study_session'),
    path('learning/flashcards/add/', add_flashcard, name='add_flashcard'),
    path('learning/flashcards/<int:card_id>/review/', review_flashcard, name='review_flashcard'),
    path('learning/notes/add/', add_study_note, name='add_study_note'),
    path('learning/notes/<int:note_id>/delete/', delete_study_note, name='delete_study_note'),

    # Focus and guidance.
    path('focus/', focus_timer, name='focus_timer'),
    path('strategies/', study_strategies, name='study_strategies'),
]
