"""
Job Email Outreach Application
FastAPI-based application for scraping recruiter emails and sending personalized outreach emails.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncpg
from datetime import datetime
import os
import re
import aiohttp
from bs4 import BeautifulSoup
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - setup and cleanup"""
    global db_pool
    # Startup
    db_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        database=os.getenv("DB_NAME", "job_outreach"),
        min_size=1,
        max_size=10
    )
    
    # Create tables if they don't exist
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id SERIAL PRIMARY KEY,
                job_title VARCHAR(255) NOT NULL,
                recipient_email VARCHAR(255) NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'sent'
            )
        """)
    
    logger.info("Database connection established and tables created")
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()
    logger.info("Database connection closed")

app = FastAPI(
    title="Job Email Outreach API",
    description="Scrape recruiter emails and send personalized job application emails",
    version="1.0.0",
    lifespan=lifespan
)

# Pydantic models
class JobRequest(BaseModel):
    job_title: str = Field(..., description="Job title to search for")
    max_emails: int = Field(default=10, ge=1, le=50, description="Maximum number of emails to send")

class EmailLog(BaseModel):
    id: int
    job_title: str
    recipient_email: str
    sent_at: datetime
    status: str

# Configuration
class Config:
    # Email configuration
    SENDER_NAME = "Rishi Singh"
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "rs3949427@gmail.com")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your_app_password")
    RESUME_URL = "https://drive.google.com/file/d/1837oezUk6Uz1rCsElKmn0oMUFGJovvx4/view"
    GITHUB_URL = "https://github.com/mrsingh-rishi"
    LINKEDIN_URL = "https://www.linkedin.com/in/rishi-singh-332a481a4/"
    
    # SMTP configuration
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

config = Config()

class EmailScraper:
    """Simulated email scraper (replace with actual scraping logic)"""
    
    @staticmethod
    async def extract_emails_from_text(text: str) -> List[str]:
        """Extract email addresses from text using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return list(set(emails))  # Remove duplicates
    
    @staticmethod
    async def scrape_job_emails(job_title: str, max_emails: int) -> List[str]:
        """
        Simulate scraping recruiter emails for a job title
        In production, this would integrate with Google Search API or LinkedIn API
        """
        # Simulated recruiter emails for demonstration
        simulated_emails = [
            f"recruiter.{job_title.lower().replace(' ', '')}1@techcorp.com",
            f"hr.{job_title.lower().replace(' ', '')}@startup.io",
            f"talent.acquisition@{job_title.lower().replace(' ', '')}.com",
            f"hiring.manager@bigtech.com",
            f"recruiter@{job_title.lower().replace(' ', '')}-jobs.com",
            f"careers@{job_title.lower().replace(' ', '')}.org",
            f"jobs@{job_title.lower().replace(' ', '')}-company.net",
            f"recruitment@{job_title.lower().replace(' ', '')}.co",
        ]
        
        # In a real implementation, you would:
        # 1. Use Google Custom Search API or web scraping
        # 2. Search for job postings related to the job title
        # 3. Extract contact emails from job postings
        # 4. Use LinkedIn API (if available) to find recruiter profiles
        
        logger.info(f"Simulated scraping for job title: {job_title}")
        
        # Return limited number of emails
        return simulated_emails[:max_emails]

class EmailService:
    """Service for sending personalized emails"""
    
    @staticmethod
    def create_personalized_email(job_title: str, recipient_email: str) -> str:
        """Create personalized email content"""
        email_template = f"""
Dear Hiring Manager,

I hope this email finds you well. I am writing to express my strong interest in the {job_title} position at your organization.

As a passionate software engineer with experience in full-stack development, I am excited about the opportunity to contribute to your team. My background includes:

• Full-stack web development with modern frameworks
• Experience with Python, JavaScript, and various databases
• Strong problem-solving skills and ability to work in agile environments
• Passion for creating efficient, scalable solutions

I have attached my resume for your review and would welcome the opportunity to discuss how my skills and enthusiasm can contribute to your team's success.

You can also find more about my work:
• Resume: {config.RESUME_URL}
• GitHub: {config.GITHUB_URL}
• LinkedIn: {config.LINKEDIN_URL}

Thank you for considering my application. I look forward to hearing from you.

Best regards,
{config.SENDER_NAME}
{config.SENDER_EMAIL}
        """
        return email_template.strip()
    
    @staticmethod
    async def send_email(recipient_email: str, subject: str, body: str) -> bool:
        """Send email using SMTP"""
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = config.SENDER_EMAIL
            message["To"] = recipient_email
            message["Subject"] = subject
            
            # Add body to email
            message.attach(MIMEText(body, "plain"))
            
            # Create SMTP session
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()  # Enable TLS encryption
            server.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
            
            # Send email
            text = message.as_string()
            server.sendmail(config.SENDER_EMAIL, recipient_email, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
            return False

class DatabaseService:
    """Service for database operations"""
    
    @staticmethod
    async def log_email(job_title: str, recipient_email: str, status: str = "sent"):
        """Log sent email to database"""
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO email_logs (job_title, recipient_email, status) VALUES ($1, $2, $3)",
                job_title, recipient_email, status
            )
    
    @staticmethod
    async def get_email_logs() -> List[EmailLog]:
        """Retrieve all email logs from database"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, job_title, recipient_email, sent_at, status FROM email_logs ORDER BY sent_at DESC"
            )
            return [EmailLog(**dict(row)) for row in rows]

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Job Email Outreach API",
        "version": "1.0.0",
        "endpoints": {
            "POST /send-emails": "Send job application emails",
            "GET /logs": "Get email sending logs"
        }
    }

@app.post("/send-emails")
async def send_job_emails(request: JobRequest):
    """
    Main endpoint to scrape emails and send personalized job application emails
    """
    try:
        logger.info(f"Processing request for job: {request.job_title}, max emails: {request.max_emails}")
        
        # Step 1: Scrape emails
        emails = await EmailScraper.scrape_job_emails(request.job_title, request.max_emails)
        
        if not emails:
            raise HTTPException(status_code=404, detail="No recruiter emails found for this job title")
        
        # Step 2: Send emails
        sent_count = 0
        failed_count = 0
        
        for email in emails:
            # Create personalized email content
            subject = f"Application for {request.job_title} Position"
            body = EmailService.create_personalized_email(request.job_title, email)
            
            # Send email
            success = await EmailService.send_email(email, subject, body)
            
            # Log to database
            status = "sent" if success else "failed"
            await DatabaseService.log_email(request.job_title, email, status)
            
            if success:
                sent_count += 1
            else:
                failed_count += 1
            
            # Add small delay to avoid rate limiting
            await asyncio.sleep(1)
        
        return {
            "message": "Email sending process completed",
            "job_title": request.job_title,
            "total_emails_found": len(emails),
            "emails_sent": sent_count,
            "emails_failed": failed_count,
            "emails": emails
        }
        
    except Exception as e:
        logger.error(f"Error processing job email request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/logs", response_model=List[EmailLog])
async def get_email_logs():
    """
    Get all email logs from the database
    """
    try:
        logs = await DatabaseService.get_email_logs()
        return logs
    except Exception as e:
        logger.error(f"Error fetching email logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
