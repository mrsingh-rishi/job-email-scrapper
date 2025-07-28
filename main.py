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
import random
from urllib.parse import urlparse
from typing import Set

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
    max_emails: int = Field(default=25, ge=1, le=1000, description="Maximum number of emails to send")
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
        Real-world implementation with multiple data sources
        """
        logger.info(f"Enhanced scraping for: {request.job_title}")
        logger.info(f"Experience: {request.experience_level} ({request.experience_years})")
        logger.info(f"Skills: {', '.join(request.required_skills + request.preferred_skills)}")
        logger.info(f"Locations: {', '.join(request.locations)}")
        logger.info(f"Company types: {', '.join(request.company_types)}")
        logger.info(f"Industries: {', '.join(request.industries)}")
        
        # Combine multiple sources for comprehensive email discovery
        all_emails = set()
        
        # 1. Generate company-based emails (existing functionality)
        # company_emails = await EmailScraper.generate_company_emails(request)
        # all_emails.update(company_emails)
        
        # 2. Real-world implementations (can be enabled with API keys)
        try:
            # Google Search API implementation
            google_emails = await EmailScraper.scrape_google_search(request)
            logger.info(f"Scraped {len(google_emails)} emails from Google search")
            all_emails.update(google_emails)
            
            # LinkedIn job scraping (simulated)
            # linkedin_emails = await EmailScraper.scrape_linkedin_jobs(request)
            # logger.info(f"Scraped {len(linkedin_emails)} emails from LinkedIn")
            # all_emails.update(linkedin_emails)
            
            # # Job board APIs
            # job_board_emails = await EmailScraper.scrape_job_boards(request)
            # logger.info(f"Scraped {len(job_board_emails)} emails from job boards")
            # all_emails.update(job_board_emails)
            
            # # Company career pages
            # career_page_emails = await EmailScraper.scrape_career_pages(request)
            # logger.info(f"Scraped {len(career_page_emails)} emails from company career pages")
            # all_emails.update(career_page_emails)
            
            # # Startup databases
            # startup_emails = await EmailScraper.scrape_startup_databases(request)
            # logger.info(f"Scraped {len(startup_emails)} emails from startup databases")
            # all_emails.update(startup_emails)
            
        except Exception as e:
            logger.warning(f"Some scraping sources failed: {str(e)}")
        
        # Convert to list and limit results
        final_emails = list(all_emails)
        
        logger.info(f"Generated {len(final_emails)} emails from multiple sources")
        return final_emails
    
    @staticmethod
    async def scrape_google_search(request: JobRequest) -> List[str]:
        """
        Enhanced email scraping using Google Custom Search API with extensive search strategies
        Scrapes vast data and gets maximum number of emails from Google search
        """
        
        logger = logging.getLogger(__name__)
        
        # Email regex pattern
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # Extract and validate emails from text
        def extract_emails_from_text(text: str) -> Set[str]:
            if not text:
                return set()
            
            raw_emails = email_pattern.findall(text)
            valid_emails = set()
            
            for email in raw_emails:
                email = email.lower().strip()
                
                # Skip common false positives
                if any(skip in email for skip in [
                    'example.com', 'test.com', 'domain.com', 'email.com',
                    'noreply', 'no-reply', 'donotreply', 'do-not-reply',
                    'admin@', 'webmaster@', 'postmaster@', 'abuse@',
                    '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.doc'
                ]):
                    continue
                
                # Basic validation
                if len(email) > 5 and len(email) < 100 and email.count('@') == 1:
                    valid_emails.add(email)
            
            return valid_emails
        
        # Scrape additional emails from web pages
        async def scrape_page_content(session: aiohttp.ClientSession, url: str) -> Set[str]:
            emails = set()
            try:
                if not url.startswith(('http://', 'https://')):
                    return emails
                
                parsed = urlparse(url)
                if parsed.netloc in ['facebook.com', 'twitter.com', 'instagram.com', 'tiktok.com']:
                    return emails
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200 and 'text/html' in response.headers.get('content-type', ''):
                        content = await response.text()
                        found_emails = extract_emails_from_text(content)
                        emails.update(found_emails)
                        
            except Exception as e:
                logger.debug(f"Failed to scrape page {url}: {str(e)}")
            
            return emails
        
        # Perform search and extract emails
        async def search_and_extract(session: aiohttp.ClientSession, api_key: str, 
                                search_engine_id: str, query: str) -> Set[str]:
            emails = set()
            
            try:
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    'key': api_key,
                    'cx': search_engine_id,
                    'q': query,
                    'num': 10,
                    'start': 1
                }
                
                # Try multiple pages of results
                for start_index in [1, 11, 21]:  # Get first 3 pages
                    params['start'] = start_index
                    
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            for item in data.get('items', []):
                                snippet = item.get('snippet', '')
                                title = item.get('title', '')
                                link = item.get('link', '')
                                
                                # Extract emails from text
                                text_content = f"{snippet} {title} {link}"
                                found_emails = extract_emails_from_text(text_content)
                                emails.update(found_emails)
                                
                                # Try to fetch additional content from promising links
                                if any(keyword in link.lower() for keyword in ['career', 'job', 'contact', 'about', 'team']):
                                    additional_emails = await scrape_page_content(session, link)
                                    emails.update(additional_emails)
                        
                        elif response.status == 429:
                            logger.warning("Rate limit hit, backing off")
                            await asyncio.sleep(random.uniform(3, 6))
                            break
                        
                        # Small delay between page requests
                        await asyncio.sleep(0.3)
                        
            except Exception as e:
                logger.error(f"Search query failed for '{query}': {str(e)}")
            
            return emails
        
        # Main execution starts here
        all_emails = set()
        google_api_key = os.getenv('GOOGLE_API_KEY')
        search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        
        if not google_api_key or not search_engine_id:
            logger.info("Google API credentials not found, skipping Google search")
            return []
        
        try:
            job_title = request.job_title
            
            # Generate comprehensive search queries
            search_queries = []
            
            # Base query patterns
            base_patterns = [
                # Direct email searches
                f'"{job_title}" recruiter email contact',
                f'"{job_title}" hiring manager email',
                f'"{job_title}" HR email contact',
                f'"{job_title}" talent acquisition email',
                f'"{job_title}" recruitment consultant email',
                f'"{job_title}" headhunter email',
                f'"{job_title}" staffing email contact',
                f'"{job_title}" careers email',
                f'"{job_title}" jobs email',
                f'"{job_title}" recruiting email',
                f'"{job_title}" talent email',
                f'"{job_title}" hiring email',
                
                # Contact page searches
                f'"{job_title}" contact us email',
                f'"{job_title}" get in touch email',
                f'"{job_title}" reach out email',
                f'"{job_title}" connect email',
                f'"{job_title}" contact information',
                f'"{job_title}" contact details',
                
                # LinkedIn-style searches
                f'"{job_title}" linkedin recruiter email',
                f'"{job_title}" linkedin hiring manager',
                f'"{job_title}" linkedin talent acquisition',
                f'"{job_title}" linkedin recruiter contact',
                
                # Job board related
                f'"{job_title}" indeed recruiter email',
                f'"{job_title}" monster recruiter email',
                f'"{job_title}" glassdoor recruiter email',
                f'"{job_title}" ziprecruiter email',
                f'"{job_title}" dice recruiter email',
                f'"{job_title}" careerbuilder email',
                
                # Company-specific patterns
                f'"{job_title}" company recruiter email',
                f'"{job_title}" corporate recruiter email',
                f'"{job_title}" internal recruiter email',
                f'"{job_title}" enterprise recruiter email',
                f'"{job_title}" startup recruiter email',
                
                # Alternative search patterns
                f'recruiter "{job_title}" email contact',
                f'hiring manager "{job_title}" email',
                f'HR "{job_title}" contact email',
                f'talent acquisition "{job_title}" email',
                f'recruitment "{job_title}" contact',
            ]
            
            search_queries.extend(base_patterns)
            
            # Add location-specific searches (expanded)
            for location in request.locations[:6]:
                location_queries = [
                    f'"{job_title}" {location} recruiter email',
                    f'"{job_title}" {location} hiring manager',
                    f'"{job_title}" {location} HR contact',
                    f'"{job_title}" {location} talent acquisition',
                    f'"{job_title}" {location} jobs email',
                    f'"{job_title}" {location} careers email',
                    f'{location} "{job_title}" recruiter contact',
                    f'{location} "{job_title}" hiring email',
                    f'{location} "{job_title}" talent email',
                    f'{location} jobs "{job_title}" email',
                ]
                search_queries.extend(location_queries)
            
            # Add company-specific searches (expanded)
            for company in request.target_companies[:10]:
                company_queries = [
                    f'{company} "{job_title}" recruiter email',
                    f'{company} "{job_title}" hiring manager',
                    f'{company} "{job_title}" HR contact',
                    f'{company} "{job_title}" careers email',
                    f'{company} "{job_title}" talent acquisition',
                    f'{company} careers "{job_title}" contact',
                    f'{company} jobs "{job_title}" email',
                    f'{company} "{job_title}" recruitment',
                    f'{company} "{job_title}" hiring contact',
                    f'site:{company.lower().replace(" ", "")}.com "{job_title}" email',
                ]
                search_queries.extend(company_queries)
            
            # Add industry-specific searches
            for industry in request.industries[:6]:
                industry_queries = [
                    f'"{job_title}" {industry} recruiter email',
                    f'"{job_title}" {industry} hiring manager',
                    f'"{job_title}" {industry} talent acquisition',
                    f'"{job_title}" {industry} HR contact',
                    f'{industry} "{job_title}" recruiter contact',
                    f'{industry} "{job_title}" hiring email',
                    f'{industry} "{job_title}" talent email',
                    f'{industry} companies "{job_title}" recruiter',
                ]
                search_queries.extend(industry_queries)
            
            # Add domain-specific searches
            for domain in request.domains[:6]:
                domain_queries = [
                    f'"{job_title}" {domain} recruiter email',
                    f'"{job_title}" {domain} hiring contact',
                    f'"{job_title}" {domain} talent email',
                    f'{domain} "{job_title}" recruiter',
                    f'{domain} "{job_title}" hiring manager',
                ]
                search_queries.extend(domain_queries)
            
            # Add email domain searches
            email_domains = ['gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com', 'icloud.com']
            for domain in email_domains:
                search_queries.extend([
                    f'"{job_title}" recruiter @{domain}',
                    f'"{job_title}" hiring manager @{domain}',
                    f'"{job_title}" talent acquisition @{domain}',
                ])
            
            # Add specific recruiter company searches
            recruiter_companies = ['manpowergroup', 'randstad', 'adecco', 'kelly', 'robert half', 'hays']
            for company in recruiter_companies:
                search_queries.extend([
                    f'{company} "{job_title}" recruiter email',
                    f'{company} "{job_title}" consultant email',
                ])
            
            # Shuffle queries to distribute load
            random.shuffle(search_queries)
            
            # Limit total queries but make it substantial
            search_queries = search_queries[:80]  # Increased significantly
            
            # Process queries in batches to handle rate limits
            batch_size = 8
            query_batches = [search_queries[i:i + batch_size] for i in range(0, len(search_queries), batch_size)]
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=45),
                connector=aiohttp.TCPConnector(limit=15)
            ) as session:
                
                for batch_idx, batch in enumerate(query_batches):
                    logger.info(f"Processing batch {batch_idx + 1}/{len(query_batches)} with {len(batch)} queries")
                    
                    # Process batch queries concurrently
                    tasks = []
                    for query in batch:
                        task = search_and_extract(session, google_api_key, search_engine_id, query)
                        tasks.append(task)
                    
                    # Execute batch with concurrency control
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Collect emails from batch results
                    for result in batch_results:
                        if isinstance(result, set):
                            all_emails.update(result)
                        elif isinstance(result, Exception):
                            logger.warning(f"Query failed: {str(result)}")
                    
                    # Rate limiting between batches
                    if batch_idx < len(query_batches) - 1:
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                
                # Perform deep search based on found emails
                if len(all_emails) > 0:
                    logger.info("Performing deep search based on found email domains...")
                    
                    # Extract domains from found emails
                    domains = set()
                    for email in list(all_emails)[:15]:  # Use first 15 emails
                        if '@' in email:
                            domain = email.split('@')[1]
                            domains.add(domain)
                    
                    # Search for more emails from these domains
                    deep_search_queries = []
                    for domain in list(domains)[:8]:
                        deep_queries = [
                            f'"{job_title}" site:{domain} contact',
                            f'"{job_title}" site:{domain} email',
                            f'"{job_title}" site:{domain} careers',
                            f'"{job_title}" site:{domain} jobs',
                            f'recruiter site:{domain} "{job_title}"',
                            f'hiring manager site:{domain} "{job_title}"',
                            f'talent acquisition site:{domain}',
                        ]
                        deep_search_queries.extend(deep_queries)
                    
                    # Execute deep search queries
                    for query in deep_search_queries[:20]:  # Limit deep search
                        try:
                            deep_emails = await search_and_extract(session, google_api_key, search_engine_id, query)
                            all_emails.update(deep_emails)
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Deep search query failed: {str(e)}")
                
                # Additional targeted searches for high-value keywords
                if len(all_emails) < 50:  # If we don't have enough emails, try more targeted searches
                    logger.info("Performing additional targeted searches...")
                    
                    targeted_queries = [
                        f'"{job_title}" "email me" OR "contact me" OR "reach me"',
                        f'"{job_title}" "send resume" OR "apply now" email',
                        f'"{job_title}" "hiring now" email contact',
                        f'"{job_title}" "we are hiring" email',
                        f'"{job_title}" "join our team" email',
                        f'"{job_title}" "job opening" email contact',
                        f'"{job_title}" "position available" email',
                        f'"{job_title}" "career opportunity" email',
                    ]
                    
                    for query in targeted_queries:
                        try:
                            targeted_emails = await search_and_extract(session, google_api_key, search_engine_id, query)
                            all_emails.update(targeted_emails)
                            await asyncio.sleep(0.8)
                        except Exception as e:
                            logger.error(f"Targeted search query failed: {str(e)}")
                            
        except Exception as e:
            logger.error(f"Google search scraping failed: {str(e)}")

        unique_emails = list(all_emails)
        logger.info(f"Successfully scraped {len(unique_emails)} unique emails from Google search")
        logger.info(f"Generated {len(unique_emails)} emails from Google search")
        
        return unique_emails

    @staticmethod
    async def scrape_linkedin_jobs(request: JobRequest) -> List[str]:
        """
        Scrape LinkedIn job postings (simulated - requires LinkedIn API access)
        In production, use LinkedIn's official APIs with proper authentication
        """
        emails = []
        
        # Simulated LinkedIn-style emails based on job criteria
        linkedin_patterns = [
            'talent-acquisition', 'recruiting', 'people-ops', 'hr-business-partner',
            'senior-recruiter', 'technical-recruiter', 'hiring-manager'
        ]
        
        linkedin_domains = [
            'linkedin-corp.com', 'talent-solutions.linkedin.com', 'recruiting.linkedin.com'
        ]
        
        # Generate LinkedIn-style professional emails
        for company in request.target_companies[:10]:
            clean_company = company.lower().replace(' ', '').replace(',', '')
            for pattern in linkedin_patterns[:3]:
                emails.append(f"{pattern}@{clean_company}.com")
                emails.append(f"{pattern}.{clean_company}@company.com")
        
        # Add generic LinkedIn recruiter emails
        for domain in linkedin_domains:
            for pattern in linkedin_patterns[:2]:
                emails.append(f"{pattern}@{domain}")
        
        logger.info(f"Generated {len(emails)} LinkedIn-style emails")
        return emails[:15]
    
    @staticmethod
    async def scrape_job_boards(request: JobRequest) -> List[str]:
        """
        Scrape job boards like Indeed, Glassdoor, etc.
        In production, use official APIs where available
        """
        emails = []
        
        # Job board specific email patterns
        job_board_domains = {
            'indeed': ['employer-center@indeed.com', 'recruiting@indeed.com'],
            'glassdoor': ['employers@glassdoor.com', 'recruiting@glassdoor.com'],
            'monster': ['employers@monster.com', 'recruiting@monster.com'],
            'ziprecruiter': ['employers@ziprecruiter.com', 'recruiting@ziprecruiter.com']
        }
        
        # Generate job board sourced emails
        job_clean = request.job_title.lower().replace(' ', '-')
        
        for board, board_emails in job_board_domains.items():
            for base_email in board_emails:
                # Create job-specific variations
                emails.append(base_email)
                emails.append(f"{job_clean}.{base_email}")
        
        # Add location-based job board emails
        for location in request.locations[:3]:
            clean_location = location.lower().replace(' ', '-')
            emails.append(f"jobs-{clean_location}@jobboards.com")
            emails.append(f"recruiting-{clean_location}@careers.com")
        
        logger.info(f"Generated {len(emails)} job board emails")
        return emails[:10]
    
    @staticmethod
    async def scrape_career_pages(request: JobRequest) -> List[str]:
        """
        Scrape company career pages for contact information
        In production, implement web scraping with proper rate limiting
        """
        emails = []
        
        # Common career page email patterns
        career_patterns = [
            'careers', 'jobs', 'talent', 'recruiting', 'hr',
            'people', 'hiring', 'opportunities'
        ]
        
        # Generate career page emails for target companies
        for company in request.target_companies[:10]:
            clean_company = company.lower().replace(' ', '').replace(',', '')
            
            for pattern in career_patterns:
                emails.append(f"{pattern}@{clean_company}.com")
                emails.append(f"{pattern}@careers.{clean_company}.com")
        
        # Industry-specific career emails
        for industry in request.industries:
            industry_clean = industry.lower().replace('/', '').replace(' ', '')
            for pattern in career_patterns[:3]:
                emails.append(f"{pattern}@{industry_clean}-company.com")
        
        logger.info(f"Generated {len(emails)} career page emails")
        return emails[:12]
    
    @staticmethod
    async def scrape_startup_databases(request: JobRequest) -> List[str]:
        """
        Scrape startup databases like AngelList, Crunchbase
        In production, use official APIs with authentication
        """
        emails = []
        
        # Only process if user is interested in startups
        if not any('startup' in ct.lower() for ct in request.company_types):
            return emails
        
        # Startup-specific email patterns
        startup_roles = [
            'founder', 'co-founder', 'cto', 'vp-engineering',
            'head-of-talent', 'people-ops', 'talent-partner'
        ]
        
        startup_domains = [
            'angellist-startups.com', 'crunchbase-companies.com',
            'ycombinator-alumni.com', 'techstars-portfolio.com'
        ]
        
        # Generate startup ecosystem emails
        job_clean = request.job_title.lower().replace(' ', '-')
        
        for domain in startup_domains:
            for role in startup_roles[:3]:
                emails.append(f"{role}@{domain}")
                emails.append(f"{role}-{job_clean}@{domain}")
        
        # Industry-specific startup emails
        for industry in request.industries:
            if industry in ['FinTech', 'SaaS', 'AI/ML']:
                industry_clean = industry.lower().replace('/', '').replace(' ', '')
                emails.append(f"hiring@{industry_clean}-startup.io")
                emails.append(f"jobs@{industry_clean}-ventures.com")
        
        logger.info(f"Generated {len(emails)} startup database emails")
        return emails[:8]

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
    
    @staticmethod
    async def get_existing_emails() -> set:
        """Get all email addresses that have been contacted before"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT recipient_email FROM email_logs"
            )
            return {row['recipient_email'] for row in rows}
    
    @staticmethod
    async def get_existing_emails_for_job(job_title: str) -> set:
        """Get email addresses already contacted for a specific job title"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT recipient_email FROM email_logs WHERE job_title = $1",
                job_title
            )
            return {row['recipient_email'] for row in rows}
    
    @staticmethod
    async def get_recent_emails(days: int = 30) -> set:
        """Get email addresses contacted within the last N days"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT recipient_email FROM email_logs WHERE sent_at >= NOW() - INTERVAL '%s days'",
                days
            )
            return {row['recipient_email'] for row in rows}

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
    Enhanced with email deduplication to prevent sending to existing contacts
    """
    try:
        logger.info(f"Processing request for job: {request.job_title}, max emails: {request.max_emails}")
        
        # Step 1: Scrape emails
        scraped_emails = await EmailScraper.scrape_job_emails(request)
        
        if not scraped_emails:
            raise HTTPException(status_code=404, detail="No recruiter emails found for this job criteria")
        
        # Step 2: Filter out emails that have already been contacted
        existing_emails = await DatabaseService.get_existing_emails()
        logger.info(f"Found {len(existing_emails)} emails in database to exclude")
        
        # Remove emails that have already been contacted
        new_emails = [email for email in scraped_emails if email not in existing_emails]
        skipped_count = len(scraped_emails) - len(new_emails)
        
        if skipped_count > 0:
            logger.info(f"Skipping {skipped_count} emails that have already been contacted")
        
        if not new_emails:
            return {
                "message": "No new emails to send - all scraped emails have been contacted before",
                "job_title": request.job_title,
                "total_emails_scraped": len(scraped_emails),
                "emails_skipped_duplicate": skipped_count,
                "new_emails_found": 0,
                "emails_sent": 0,
                "emails_failed": 0,
                "emails": []
            }
        
        # Step 3: Send emails only to new contacts
        sent_count = 0
        failed_count = 0
        sent_emails = []
        
        for email in new_emails:
            # Create personalized email content
            subject = f"Application for {request.job_title} Position"
            body = EmailService.create_personalized_email(request, email)
            
            # Send email
            success = await EmailService.send_email(email, subject, body)
            
            # Log to database (both successful and failed attempts)
            status = "sent" if success else "failed"
            await DatabaseService.log_email(request.job_title, email, status)
            
            if success:
                sent_count += 1
                sent_emails.append(email)
                logger.info(f"✅ Sent email to {email}")
            else:
                failed_count += 1
                logger.warning(f"❌ Failed to send email to {email}")
            
            # Add small delay to avoid rate limiting
            await asyncio.sleep(1)
        
        return {
            "message": "Email sending process completed with deduplication",
            "job_title": request.job_title,
            "total_emails_scraped": len(scraped_emails),
            "emails_skipped_duplicate": skipped_count,
            "new_emails_found": len(new_emails),
            "emails_sent": sent_count,
            "emails_failed": failed_count,
            "emails": sent_emails
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

@app.get("/existing-emails")
async def get_existing_emails():
    """
    Get all email addresses that have been contacted before
    """
    try:
        existing_emails = await DatabaseService.get_existing_emails()
        return {
            "message": "Retrieved existing email addresses",
            "total_existing_emails": len(existing_emails),
            "existing_emails": sorted(list(existing_emails))
        }
    except Exception as e:
        logger.error(f"Error fetching existing emails: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/existing-emails/{job_title}")
async def get_existing_emails_for_job(job_title: str):
    """
    Get email addresses already contacted for a specific job title
    """
    try:
        existing_emails = await DatabaseService.get_existing_emails_for_job(job_title)
        return {
            "message": f"Retrieved existing emails for job: {job_title}",
            "job_title": job_title,
            "total_existing_emails": len(existing_emails),
            "existing_emails": sorted(list(existing_emails))
        }
    except Exception as e:
        logger.error(f"Error fetching existing emails for job {job_title}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/recent-emails/{days}")
async def get_recent_emails(days: int = 30):
    """
    Get email addresses contacted within the last N days
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        recent_emails = await DatabaseService.get_recent_emails(days)
        return {
            "message": f"Retrieved emails contacted in the last {days} days",
            "days": days,
            "total_recent_emails": len(recent_emails),
            "recent_emails": sorted(list(recent_emails))
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recent emails: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
