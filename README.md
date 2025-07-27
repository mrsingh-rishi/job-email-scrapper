# Job Email Outreach API

A full-fledged FastAPI application that scrapes recruiter emails and sends personalized job application emails with PostgreSQL logging and Docker support.

## 🚀 Features

- **Email Scraping**: Simulate scraping recruiter emails for specific job titles
- **Personalized Emails**: Send customized job application emails with your profile information
- **PostgreSQL Integration**: Log all sent emails with timestamps and status
- **RESTful API**: Clean endpoints for sending emails and retrieving logs
- **Docker Support**: Fully containerized with Docker Compose
- **Production Ready**: Async operations, proper error handling, and logging
- **Health Checks**: Built-in health monitoring for services

## 📋 Prerequisites

- Docker and Docker Compose
- Gmail account with App Password (for email sending)
- Python 3.11+ (for local development)

## 🛠️ Setup Instructions

### 1. Clone and Setup

```bash
# The files are already created in your current directory
cd /Users/rishisingh12/desktop

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Edit the `.env` file with your credentials:

```env
# Email Configuration
SENDER_EMAIL=rs3949427@gmail.com
SENDER_PASSWORD=your_gmail_app_password_here

# Database Configuration (defaults work with docker-compose)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=job_outreach
```

### 3. Gmail App Password Setup

1. Go to Google Account settings: https://myaccount.google.com/
2. Security → 2-Step Verification (must be enabled)
3. App passwords → Generate password for "Mail"
4. Use this password in your `.env` file

### 4. Run with Docker Compose

```bash
# Start all services (PostgreSQL + FastAPI)
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 5. Optional: Run PgAdmin (Database Management)

```bash
# Start with PgAdmin included
docker-compose --profile tools up -d

# Access PgAdmin at http://localhost:5050
# Email: admin@admin.com
# Password: admin
```

## 📊 API Endpoints

### Base URL
```
http://localhost:8000
```

### 1. Send Job Application Emails (Enhanced)
```http
POST /send-emails
Content-Type: application/json

{
    "job_title": "Senior Backend Engineer",
    "experience_level": "Senior",
    "experience_years": "5-7 years",
    "required_skills": ["Python", "Django", "PostgreSQL", "AWS"],
    "preferred_skills": ["Docker", "Kubernetes", "Redis"],
    "locations": ["San Francisco", "New York", "Remote"],
    "remote_ok": true,
    "company_types": ["Startup", "Mid-size"],
    "target_companies": ["Stripe", "Shopify", "Airbnb"],
    "industries": ["FinTech", "E-commerce"],
    "domains": ["Backend", "API Development"],
    "employment_type": "Full-time",
    "salary_range": "$150k-$200k",
    "max_emails": 50,
    "urgency": "normal"
}
```

**Response:**
```json
{
    "message": "Email sending process completed",
    "job_title": "Senior Backend Engineer",
    "total_emails_found": 50,
    "emails_sent": 50,
    "emails_failed": 0,
    "emails": [
        "recruiter@stripe.com",
        "hr@shopify.com",
        "talent@airbnb.com",
        "hiring@financetech.com",
        "careers@paymentcorp.io",
        "recruiter.sanfrancisco@jobsearch.com"
    ]
}
```

### 2. Get Email Logs
```http
GET /logs
```

**Response:**
```json
[
    {
        "id": 1,
        "job_title": "Software Engineer",
        "recipient_email": "recruiter.softwareengineer1@techcorp.com",
        "sent_at": "2025-01-27T21:30:00.123456",
        "status": "sent"
    }
]
```

### 3. Health Check
```http
GET /health
```

### 4. API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 💼 Example Usage

### Using curl:

```bash
# Send job application emails
curl -X POST "http://localhost:8000/send-emails" \
     -H "Content-Type: application/json" \
     -d '{
       "job_title": "Full Stack Developer",
       "max_emails": 3
     }'

# Get email logs
curl -X GET "http://localhost:8000/logs"
```

### Using Python requests:

```python
import requests

# Send emails
response = requests.post("http://localhost:8000/send-emails", json={
    "job_title": "Backend Developer",
    "max_emails": 5
})
print(response.json())

# Get logs
logs = requests.get("http://localhost:8000/logs")
print(logs.json())
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │───▶│   PostgreSQL    │    │   Gmail SMTP    │
│                 │    │                 │    │                 │
│ • Email Scraper │    │ • Email Logs    │    │ • Send Emails   │
│ • API Endpoints │    │ • Timestamps    │    │ • SMTP Client   │
│ • Async Tasks   │    │ • Status Track  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🗂️ Project Structure

```
job-email-outreach/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── docker-compose.yml  # Multi-service setup
├── init.sql            # Database initialization
├── .env.example        # Environment template
└── README.md           # This file
```

## 🔧 Development

### Local Development (without Docker):

```bash
# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL locally or use Docker for DB only
docker run -d --name postgres \
  -e POSTGRES_DB=job_outreach \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 postgres:15-alpine

# Run the application
python main.py
```

### Running Tests:

```bash
# Install test dependencies
pip install pytest httpx

# Run tests (you would create test files)
pytest tests/
```

## 🌍 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SENDER_EMAIL` | Your Gmail address | `rs3949427@gmail.com` |
| `SENDER_PASSWORD` | Gmail App Password | Required |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_USER` | Database username | `postgres` |
| `DB_PASSWORD` | Database password | `password` |
| `DB_NAME` | Database name | `job_outreach` |

## 🚦 Production Considerations

1. **Email Rate Limiting**: Add delays between emails to avoid spam detection
2. **Real Email Scraping**: Replace simulated scraper with actual Google/LinkedIn APIs
3. **Security**: Use proper secrets management, not environment variables in production
4. **Monitoring**: Add application monitoring and alerting
5. **Database**: Use managed PostgreSQL service for production
6. **Scaling**: Consider using Celery for background email tasks

## 🐛 Troubleshooting

### Common Issues:

1. **Email not sending**:
   - Check Gmail App Password is correct
   - Ensure 2FA is enabled on Gmail
   - Verify SMTP credentials

2. **Database connection issues**:
   - Check PostgreSQL is running
   - Verify connection credentials
   - Check network connectivity

3. **Docker issues**:
   - Ensure Docker daemon is running
   - Check port conflicts (8000, 5432)
   - Review container logs: `docker-compose logs`

### Logs:

```bash
# View application logs
docker-compose logs app

# View database logs
docker-compose logs db

# Follow logs in real-time
docker-compose logs -f
```

## 📄 License

This project is for educational purposes. Ensure compliance with email sending regulations and website terms of service when scraping.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feat/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

---

**Note**: This application currently uses simulated email scraping for demonstration. In production, integrate with proper APIs like Google Custom Search or LinkedIn API while respecting their terms of service and rate limits.
