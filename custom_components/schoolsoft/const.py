"""Constants for the SchoolSoft integration."""
from datetime import timedelta

DOMAIN = "schoolsoft"
PLATFORMS = ["calendar", "sensor"]
CONF_SCHOOL_URL = "school_url"
CONF_STUDENT_NAME = "student_name"
DEFAULT_SCHOOL_URL = "https://sms.schoolsoft.se/robertsfors"
DEFAULT_STUDENT_NAME = "Student"
UPDATE_INTERVAL = timedelta(minutes=30)
