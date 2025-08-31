import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    # API Keys and Models
    "AIRTABLE_API_KEY": os.getenv("AIRTABLE_API_KEY"),
    "AIRTABLE_BASE_ID": os.getenv("AIRTABLE_BASE_ID"),
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "EXCHANGE_RATE_API_KEY": os.getenv("EXCHANGE_RATE_API_KEY"),
    "GEMINI_MODEL": "gemini-2.5-flash",

    # Airtables
    "APPLICANTS_TABLE": "Applicants",
    "PERSONAL_DETAILS_TABLE": "Personal Details",
    "WORK_EXPERIENCE_TABLE": "Work Experience",
    "SALARY_PREFERENCES_TABLE": "Salary Preferences",
    "SHORTLISTED_LEADS_TABLE": "Shortlisted Leads",
    
    # Fields and their json names
    "FIELDS": {
        "personal": [
            ("Full Name", "name"),
            ("Email", "email"),
            ("Location", "location"),
            ("Applicants", "id")
        ],
        "salary": [
            ("Applicants", "id"),
            ("Preferred Rate", "rate"),
            ("Currency", "currency"),
            ("Minimum Rate", "min_rate"),
            ("Availability (hrs/wk)", "availability")
        ],
        "experience": [
            ("Applicants", "id"),
            ("Company", "company"),
            ("Title", "title"),
            ("Start", "start"),
            ("End", "end"),
            ("Technologies", "technologies")
        ]
    },

    # Configurations for shortlisting
    "ALLOWED_LOCATIONS": [
        "India", "United States", "Canada", "UK", "Germany"
    ],
    "MIN_AVAILABILITY_HRS": 20,
    "MAX_RATE_USD": 100,
    "MIN_YEARS_EXPERIENCE": 4
}
