import os
from datetime import timedelta

from dotenv import load_dotenv

if os.path.exists('.env'):
    load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    MONGO_URI = os.getenv('MONGODB_URI')
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    CAPTCHA_SECRET_KEY = os.getenv('CAPTCHA_SECRET_KEY')
    CDN_KEY = os.getenv('CDN_KEY')
    CDN_URL = os.getenv('CDN_API')
    CAPTCHA_URL = os.getenv('CAPTCHA_URL')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'