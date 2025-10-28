from datetime import datetime
import pytz

def get_ist_time():
    """Get current time in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def convert_to_ist(utc_time):
    """Convert UTC time to IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return utc_time.replace(tzinfo=pytz.UTC).astimezone(ist)

def format_time_for_display(dt):
    """Format datetime for display"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")
