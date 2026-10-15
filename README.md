# StudyMate

StudyMate is a Django study planner backed by MySQL. Its dashboard brings the main study tools together, and each account sees only its own study records.

## Features

- **Dashboard:** subject and task totals, weekly study chart and goal, streak, pending tasks, upcoming exams, and reminders.
- **Subjects:** categories, priorities, colors, weekly goals, and exam dates.
- **Tasks:** due dates, priority, difficulty, recurrence, subject links, search, filters, and completion tracking.
- **Exams and reminders:** exam formats, topics, preparation progress, and actionable reminders.
- **Progress:** task completion and logged study time.
- **Learning toolkit:** study sessions, notes, flashcards, review tracking, and spaced repetition that schedules the next card review from your answers.
- **Calendar:** exams, task deadlines, and study sessions.
- **Focus timer:** timed work and break intervals.
- **Smart planner:** a daily task plan based on deadlines, priority, and difficulty.
- **AI Study Coach:** topic explanations, deadline-aware revision plans, and practice quizzes built from your notes and flashcards.
- **Study strategies:** practical learning and revision guidance.

## Project layout

```text
studymate/                    Django settings and project URL routing
study_app/models.py           Study data models
study_app/forms.py            Validated forms and account-scoped choices
study_app/views.py            Feature pages and request handling
study_app/planner.py          Daily study-plan scheduling logic
study_app/templates/          Page templates and shared includes
study_app/static/             Shared styles and feature illustrations
study_app/migrations/         Database schema history
study_app/management/         Django management commands
run_studymate.ps1             Local MySQL startup, migrations, and server
```

## Run locally with MySQL

From the project directory, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_studymate.ps1
```

The script starts the project's local MySQL server on port `3307`, applies pending migrations, and starts Django at `http://127.0.0.1:8000/`. It asks for the MySQL password for `studymate_user` if `DJANGO_DB_PASSWORD` is not set in the Windows user environment.

The MySQL database is the default. To deliberately use the bundled SQLite database for local development, set `$env:DJANGO_DB_ENGINE = 'sqlite'` before running Django. Do not use the SQLite database for MySQL work; each database has its own tables and records.

## Configure the AI Study Coach

The Study Coach works with local study suggestions by default. To enable AI-generated replies, set an OpenAI API key in the PowerShell session before starting StudyMate:

```powershell
$env:OPENAI_API_KEY = 'your-api-key'
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_studymate.ps1
```

The project uses the OpenAI Responses API. Set `$env:OPENAI_MODEL` to override the default model. The key is read from the environment and must not be committed to source control. When AI is enabled, the coach sends the student's prompt and relevant selected study records to OpenAI to prepare a reply; account names and login details are excluded. Students can use the local suggestions without configuring an API key.

## Add sample data

The idempotent sample-data command keeps matching records and fills in missing demo subjects, tasks, exams, reminders, study sessions, a weekly goal, flashcards, and notes for one account:

```powershell
.\.venv\Scripts\python.exe manage.py load_demo_data --username Anagha
```

Run it only after MySQL is available and the schema is migrated. Change the username to the account that should own the sample data.
