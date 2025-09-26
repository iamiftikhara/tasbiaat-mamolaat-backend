"""
Configuration settings for the Tasbiaat & Mamolaat API
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Database Configuration (JSON Storage)
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    
    # Redis settings (for session management and nonce storage)
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'tasbiaat-mamolaat-jwt-secret-key-default')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)  # Extended to 7 days
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ALGORITHM = 'HS256'  # Can be changed to RS256 for production
    
    # API Security
    SYSTEM_KEY_SECRET = os.environ.get('SYSTEM_KEY_SECRET')
    NONCE_EXPIRY_SECONDS = 240  # ±120s window
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://localhost:3001').split(',')
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL')
    
    # Business rules
    DEFAULT_CYCLE_DAYS = 40
    ZIKR_MODES = ['auto_restart', 'murabi_controlled']
    
    # Roles and permissions
    ROLES = ['Saalik', 'Murabi', 'Masool', 'Sheikh', 'Admin']
    ROLE_HIERARCHY = {
        'Admin': ['Sheikh', 'Masool', 'Murabi', 'Saalik', 'Admin'],
        'Sheikh': ['Masool', 'Murabi'],
        'Masool': ['Murabi', 'Saalik'],
        'Murabi': ['Saalik']
    }
    
    # Saalik levels
    SAALIK_LEVELS = list(range(7))  # 0-6
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    # Override with production values
    JWT_ALGORITHM = 'RS256'  # More secure for production

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    MONGO_URI = 'mongodb://localhost:27017/tasbiaat_mamolaat_test'
    REDIS_URL = 'redis://localhost:6379/2'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}