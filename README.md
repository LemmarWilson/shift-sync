# ShiftSync

Employee scheduling web application designed to replace informal word-of-mouth shift communication with a structured, digital solution.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5.x (Python 3.12) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | Django Templates + HTMX + Alpine.js |
| Styling | Tailwind CSS (CDN) |
| Fonts | Geist (Google Fonts) |

## Features

### For Managers
- Calendar dashboard with week/month views
- Full shift CRUD with publish workflow
- Day-off request approval system
- Automated email notifications
- Department management

### For Employees
- View personal and published shifts
- Submit day-off requests
- Receive schedule notifications
- Shift reminders

## Local Development

### Prerequisites
- Python 3.12+
- pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd shift-sync
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create superuser:
```bash
python manage.py createsuperuser
```

7. Run development server:
```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000/admin to access the admin interface.

## Environment Variables

See `.env.example` for all configuration options:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | Debug mode (True/False) |
| `ALLOWED_HOSTS` | Comma-separated list of hosts |
| `DATABASE_URL` | PostgreSQL connection string (production) |
| `EMAIL_*` | Email backend configuration |
| `TIME_ZONE` | Application timezone |

## Project Structure

```
shift-sync/
├── config/
│   ├── settings/
│   │   ├── base.py      # Shared settings
│   │   ├── dev.py       # Development settings
│   │   └── prod.py      # Production settings
│   ├── urls.py
│   └── wsgi.py
├── scheduling/
│   ├── models.py        # User, Department, Shift, DayOffRequest, Notification
│   ├── views.py
│   ├── forms.py
│   ├── admin.py
│   └── urls.py
├── templates/
├── static/
├── manage.py
└── requirements.txt
```

## Data Models

- **User** - Extended Django user with role, phone, color, department
- **Department** - Organization unit with manager
- **Shift** - Employee work assignment with date/time
- **DayOffRequest** - Time-off request with approval workflow
- **Notification** - In-app notification system

## License

MIT
