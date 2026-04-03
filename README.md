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

## Demo Data

ShiftSync includes a management command to generate realistic demo data for testing and demonstration purposes.

### Creating Demo Data

```bash
# Create demo data (1 manager + 5 employees + shifts + day-off requests)
python manage.py seed_demo

# Clear existing data and recreate fresh demo data
python manage.py seed_demo --clear
```

### Demo Accounts

After running the seed command, you can log in with these accounts:

| Role | Username | Password |
|------|----------|----------|
| Manager | manager | demo1234 |
| Employee | employee1 | demo1234 |
| Employee | employee2 | demo1234 |
| Employee | employee3 | demo1234 |
| Employee | employee4 | demo1234 |
| Employee | employee5 | demo1234 |

### What Gets Created

- **1 Manager account** with full access to scheduling features
- **5 Employee accounts** with employee-level access
- **1 Department** ("Main Department") with all users assigned
- **Sample shifts** for the current and upcoming weeks
- **Sample day-off requests** in various statuses (pending, approved, denied)

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

## Email Configuration

ShiftSync sends email notifications for shift assignments, updates, cancellations, and day-off request status changes.

### Development (Console Backend)

By default, emails are printed to the console for easy development debugging:

```bash
# .env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

All emails will appear in your terminal where `runserver` is running.

### Production (SMTP Backend)

For production, configure an SMTP provider to send real emails:

```bash
# .env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-username
EMAIL_HOST_PASSWORD=your-password
DEFAULT_FROM_EMAIL=ShiftSync <noreply@shiftsync.example.com>
```

### Common Email Providers

#### SendGrid
```bash
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
```

#### Mailgun
```bash
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=postmaster@your-domain.mailgun.org
EMAIL_HOST_PASSWORD=your-mailgun-smtp-password
```

#### Amazon SES
```bash
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-ses-smtp-username
EMAIL_HOST_PASSWORD=your-ses-smtp-password
```

#### Gmail (for testing only)
```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
```

> **Note:** For Gmail, you must use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

## Cron Jobs

ShiftSync includes automated tasks that should be scheduled via cron (or a task scheduler).

### Shift Reminders

Send reminder emails to employees about their shifts tomorrow:

```bash
# Run daily at 6 PM to send tomorrow's shift reminders
0 18 * * * cd /path/to/shift-sync && /path/to/venv/bin/python manage.py send_shift_reminders
```

This command:
- Finds all published shifts scheduled for tomorrow
- Sends a reminder email to each employee with shift details
- Logs the number of reminders sent

### Example Crontab

```bash
# Edit crontab
crontab -e

# Add these lines (adjust paths to match your deployment):

# Shift reminders - daily at 6 PM
0 18 * * * cd /var/www/shiftsync && /var/www/shiftsync/venv/bin/python manage.py send_shift_reminders >> /var/log/shiftsync/reminders.log 2>&1
```

### Using systemd Timers (Alternative)

For systemd-based systems, you can use timer units instead of cron:

```ini
# /etc/systemd/system/shiftsync-reminders.service
[Unit]
Description=ShiftSync Shift Reminders
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/var/www/shiftsync
ExecStart=/var/www/shiftsync/venv/bin/python manage.py send_shift_reminders
User=www-data

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/shiftsync-reminders.timer
[Unit]
Description=Run ShiftSync reminders daily at 6 PM

[Timer]
OnCalendar=*-*-* 18:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable with:
```bash
sudo systemctl enable --now shiftsync-reminders.timer
```

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
│   ├── services.py      # Business logic (calendar, email, notifications)
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

## Deployment Checklist

Before deploying ShiftSync to production, ensure the following:

### Security

- [ ] **SECRET_KEY**: Generate a new, unique secret key (never use the development key)
- [ ] **DEBUG**: Set to `False`
- [ ] **ALLOWED_HOSTS**: Configure with your actual domain(s)
- [ ] **HTTPS**: Enable HTTPS and set `SECURE_SSL_REDIRECT=True`
- [ ] **CSRF**: Ensure `CSRF_COOKIE_SECURE=True` and `SESSION_COOKIE_SECURE=True`
- [ ] **Database**: Use a strong, unique database password

### Database

- [ ] **PostgreSQL**: Install and configure PostgreSQL
- [ ] **DATABASE_URL**: Set the production database connection string
- [ ] **Migrations**: Run `python manage.py migrate`
- [ ] **Backups**: Configure automated database backups

### Email

- [ ] **EMAIL_BACKEND**: Switch to `django.core.mail.backends.smtp.EmailBackend`
- [ ] **SMTP Settings**: Configure your email provider credentials
- [ ] **Test Email**: Verify emails are being sent correctly

### Static Files

- [ ] **Collect Static**: Run `python manage.py collectstatic`
- [ ] **CDN/Storage**: Configure static file serving (nginx, S3, CDN)

### Web Server

- [ ] **WSGI Server**: Install and configure Gunicorn or uWSGI
- [ ] **Reverse Proxy**: Configure nginx or Apache as reverse proxy
- [ ] **Process Manager**: Set up systemd or supervisor to manage the application

### Cron Jobs

- [ ] **Shift Reminders**: Schedule `send_shift_reminders` command (see Cron Jobs section)

### Monitoring

- [ ] **Logging**: Configure application logging to files
- [ ] **Error Tracking**: Set up Sentry or similar error tracking
- [ ] **Health Checks**: Implement health check endpoints

### Initial Data

- [ ] **Superuser**: Create an admin account with `python manage.py createsuperuser`
- [ ] **Departments**: Create initial department(s) via admin
- [ ] **Manager Account**: Create at least one manager user

### Sample Production Configuration

```bash
# Production .env example
SECRET_KEY=your-production-secret-key-here
DEBUG=False
ALLOWED_HOSTS=shiftsync.example.com,www.shiftsync.example.com

DATABASE_URL=postgres://shiftsync:secure_password@localhost:5432/shiftsync_prod

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=ShiftSync <noreply@shiftsync.example.com>

TIME_ZONE=America/New_York
```

## License

MIT
