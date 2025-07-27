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
    # Core job details
    job_title: str = Field(..., description="Job title/role to search for", example="Software Engineer")
    experience_level: Optional[str] = Field(None, description="Experience level (Entry/Mid/Senior/Lead/Principal)", example="Mid")
    experience_years: Optional[str] = Field(None, description="Years of experience", example="3-5 years")
    
    # Skills and technologies
    required_skills: Optional[List[str]] = Field(default=[], description="Required technical skills", example=["Python", "React", "AWS"])
    preferred_skills: Optional[List[str]] = Field(default=[], description="Preferred additional skills", example=["Docker", "Kubernetes"])
    
    # Location preferences
    locations: Optional[List[str]] = Field(default=[], description="Preferred job locations", example=["San Francisco", "New York", "Remote"])
    remote_ok: bool = Field(default=True, description="Open to remote positions")
    
    # Company preferences
    company_types: Optional[List[str]] = Field(default=[], description="Types of companies", example=["Startup", "MNC", "Mid-size"])
    target_companies: Optional[List[str]] = Field(default=[], description="Specific companies to target", example=["Google", "Netflix", "OpenAI"])
    company_size: Optional[str] = Field(None, description="Preferred company size", example="100-1000 employees")
    
    # Industry and domain
    industries: Optional[List[str]] = Field(default=[], description="Target industries", example=["FinTech", "HealthTech", "AI/ML"])
    domains: Optional[List[str]] = Field(default=[], description="Specific domains", example=["Backend", "Frontend", "DevOps"])
    
    # Job preferences
    employment_type: Optional[str] = Field(None, description="Employment type", example="Full-time")
    salary_range: Optional[str] = Field(None, description="Expected salary range", example="$120k-$180k")
    
    # Search parameters
    max_emails: int = Field(default=25, ge=1, le=200, description="Maximum number of emails to send")
    urgency: Optional[str] = Field("normal", description="Job search urgency", example="urgent")
    
    class Config:
        schema_extra = {
            "example": {
                "job_title": "Senior Backend Engineer",
                "experience_level": "Senior",
                "experience_years": "5-7 years",
                "required_skills": ["Python", "Django", "PostgreSQL", "AWS"],
                "preferred_skills": ["Docker", "Kubernetes", "Redis"],
                "locations": ["San Francisco", "New York", "Remote"],
                "remote_ok": True,
                "company_types": ["Startup", "Mid-size"],
                "target_companies": ["Stripe", "Shopify", "Airbnb"],
                "industries": ["FinTech", "E-commerce"],
                "domains": ["Backend", "API Development"],
                "employment_type": "Full-time",
                "salary_range": "$150k-$200k",
                "max_emails": 50,
                "urgency": "normal"
            }
        }

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
    """Enhanced email scraper with comprehensive job parameter support"""
    
    @staticmethod
    async def extract_emails_from_text(text: str) -> List[str]:
        """Extract email addresses from text using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return list(set(emails))  # Remove duplicates
    
    @staticmethod
    async def generate_company_emails(request: JobRequest) -> List[str]:
        """Generate realistic company emails based on job requirements"""
        emails = []
        job_clean = request.job_title.lower().replace(' ', '').replace('-', '')
        
        # Base email patterns
        base_patterns = [
            "recruiter", "hr", "talent", "hiring", "careers", "jobs", 
            "recruitment", "people", "human.resources", "talent.acquisition"
        ]
        
        # Company domains based on company types
        startup_domains = [
            "techstartup.io", "innovate.ai", "nextstep.com", "disruption.tech",
            "scalable.io", "fastgrow.co", "unicorn-startup.com", "venture.tech"
        ]
        
        mnc_domains = [
            "globaltech.com", "enterprise.corp", "worldwide.com", "international.biz",
            "multinational.org", "fortune500.com", "bigcorp.net", "megacorp.com"
        ]
        
        midsize_domains = [
            "growthcompany.com", "midsizefirm.net", "established.biz", "mature-tech.com",
            "solidfirm.co", "reliable-company.net", "steady-growth.com"
        ]
        
        # Industry-specific domains
        industry_domains = {
            "FinTech": ["financetech.com", "paymentcorp.io", "bankingtech.net", "cryptofirm.co"],
            "HealthTech": ["medtech.com", "healthinnovation.io", "biotech-corp.net", "digitalhealth.co"],
            "AI/ML": ["aicompany.tech", "mlstartup.ai", "datatech.io", "deeplearning.co"],
            "E-commerce": ["ecommtech.com", "retailtech.io", "marketplace.biz", "shopping-tech.net"],
            "EdTech": ["edtech-startup.com", "learningtech.io", "education-corp.net"],
            "Gaming": ["gamedev.studio", "gaming-corp.com", "entertainment.tech"],
            "SaaS": ["saascompany.com", "cloudtech.io", "software-corp.net"]
        }
        
        # Target company emails if specified
        if request.target_companies:
            for company in request.target_companies[:10]:  # Limit to 10 target companies
                clean_company = company.lower().replace(' ', '').replace(',', '')
                for pattern in base_patterns[:3]:  # Use top 3 patterns
                    emails.append(f"{pattern}@{clean_company}.com")
                    if len(emails) >= request.max_emails // 2:  # Half from target companies
                        break
        
        # Generate emails based on company types
        domains_to_use = []
        if request.company_types:
            for comp_type in request.company_types:
                if comp_type.lower() in ["startup", "start-up"]:
                    domains_to_use.extend(startup_domains)
                elif comp_type.lower() in ["mnc", "multinational", "enterprise", "large"]:
                    domains_to_use.extend(mnc_domains)
                elif comp_type.lower() in ["mid-size", "midsize", "medium"]:
                    domains_to_use.extend(midsize_domains)
        else:
            # If no company type specified, use all types
            domains_to_use = startup_domains + mnc_domains + midsize_domains
        
        # Add industry-specific domains
        if request.industries:
            for industry in request.industries:
                if industry in industry_domains:
                    domains_to_use.extend(industry_domains[industry])
        
        # Generate emails with various patterns
        email_count = 0
        for domain in domains_to_use:
            if email_count >= request.max_emails:
                break
            
            for pattern in base_patterns:
                if email_count >= request.max_emails:
                    break
                
                # Various email formats
                email_formats = [
                    f"{pattern}@{domain}",
                    f"{pattern}.{job_clean}@{domain}",
                    f"{job_clean}.{pattern}@{domain}",
                    f"{pattern}-{job_clean}@{domain}"
                ]
                
                for email_format in email_formats:
                    if email_count >= request.max_emails:
                        break
                    emails.append(email_format)
                    email_count += 1
        
        # Add location-based emails if specified
        if request.locations:
            for location in request.locations[:5]:  # Limit to 5 locations
                if email_count >= request.max_emails:
                    break
                clean_location = location.lower().replace(' ', '').replace(',', '')
                for pattern in ["recruiter", "hr", "jobs"]:
                    emails.append(f"{pattern}.{clean_location}@jobsearch.com")
                    email_count += 1
                    if email_count >= request.max_emails:
                        break
        
        # Remove duplicates and return requested number
        unique_emails = list(set(emails))
        return unique_emails[:request.max_emails]
    
    @staticmethod
    async def scrape_job_emails(request: JobRequest) -> List[str]:
        """
        Enhanced scraping based on comprehensive job requirements
        In production, this would integrate with multiple APIs and scraping sources
        """
        logger.info(f"Enhanced scraping for: {request.job_title}")
        logger.info(f"Experience: {request.experience_level} ({request.experience_years})")
        logger.info(f"Skills: {', '.join(request.required_skills + request.preferred_skills)}")
        logger.info(f"Locations: {', '.join(request.locations)}")
        logger.info(f"Company types: {', '.join(request.company_types)}")
        logger.info(f"Industries: {', '.join(request.industries)}")
        
        # Generate comprehensive email list
        emails = await EmailScraper.generate_company_emails(request)
        
        # In a real implementation, you would:
        # 1. Use Google Custom Search API with job-specific queries
        # 2. Search LinkedIn Sales Navigator API
        # 3. Use job board APIs (Indeed, Glassdoor, LinkedIn Jobs)
        # 4. Scrape company career pages
        # 5. Use AngelList API for startups
        # 6. Query Crunchbase for company information
        # 7. Use ZoomInfo or Apollo.io for contact discovery
        
        logger.info(f"Generated {len(emails)} emails for job search criteria")
        return emails

class EmailService:
    """Service for sending personalized emails"""
    
    @staticmethod
    def create_personalized_email(request: JobRequest, recipient_email: str) -> str:
        """Create highly personalized email content based on job requirements"""
        
        # Build skills section
        skills_text = ""
        if request.required_skills:
            skills_text += f"• Proficient in: {', '.join(request.required_skills)}\n"
        if request.preferred_skills:
            skills_text += f"• Additional experience with: {', '.join(request.preferred_skills)}\n"
        
        # Build experience section
        experience_text = ""
        if request.experience_level and request.experience_years:
            experience_text = f"As a {request.experience_level.lower()}-level professional with {request.experience_years} of experience, "
        elif request.experience_level:
            experience_text = f"As a {request.experience_level.lower()}-level professional, "
        elif request.experience_years:
            experience_text = f"With {request.experience_years} of experience, "
        else:
            experience_text = "As a dedicated software professional, "
        
        # Build location section
        location_text = ""
        if request.locations:
            if request.remote_ok:
                location_text = f"I am open to opportunities in {', '.join(request.locations)} as well as remote positions."
            else:
                location_text = f"I am specifically interested in opportunities in {', '.join(request.locations)}."
        elif request.remote_ok:
            location_text = "I am open to both on-site and remote opportunities."
        
        # Build company type preference
        company_text = ""
        if request.company_types:
            company_text = f"I am particularly interested in {', '.join(request.company_types).lower()} companies."
        
        # Build industry interest
        industry_text = ""
        if request.industries:
            industry_text = f"I am passionate about working in the {', '.join(request.industries)} space."
        
        # Build domain expertise
        domain_text = ""
        if request.domains:
            domain_text = f"My expertise spans {', '.join(request.domains).lower()} development."
        
        # Build salary expectation (if provided)
        salary_text = ""
        if request.salary_range:
            salary_text = f"My salary expectation is in the range of {request.salary_range}."
        
        # Build urgency indicator
        urgency_text = ""
        if request.urgency and request.urgency.lower() == "urgent":
            urgency_text = "I am actively seeking new opportunities and available for immediate start."
        
        # Create personalized email
        email_template = f"""
Dear Hiring Manager,

I hope this email finds you well. I am writing to express my strong interest in the {request.job_title} position at your organization.

{experience_text}I am excited about the opportunity to contribute to your team. My background includes:

{skills_text}• Strong problem-solving skills and ability to work in agile environments
• Passion for creating efficient, scalable solutions
{domain_text}

{industry_text} {company_text}

{location_text}

{urgency_text}

{salary_text}

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
        
        # Clean up extra whitespace and empty lines
        lines = [line.strip() for line in email_template.split('\n')]
        cleaned_lines = []
        for line in lines:
            if line or (cleaned_lines and cleaned_lines[-1]):  # Keep non-empty lines and single empty lines
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
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
        emails = await EmailScraper.scrape_job_emails(request)
        
        if not emails:
            raise HTTPException(status_code=404, detail="No recruiter emails found for this job criteria")
        
        # Step 2: Send emails
        sent_count = 0
        failed_count = 0
        
        for email in emails:
            # Create personalized email content
            subject = f"Application for {request.job_title} Position"
            body = EmailService.create_personalized_email(request, email)
            
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
