"""
Models package initialization
"""

import os
from utils.json_storage import get_collection as get_json_collection
from utils.mongo_db import get_collection as get_mongo_collection

from .user import User
from .entry import Entry
from .level import Level
from .session import Session
from .notification import Notification
from .audit_log import AuditLog

# Determine which storage to use
USE_MONGODB = os.environ.get('MONGO_URI') is not None

# Get the appropriate collection function
get_collection_func = get_mongo_collection if USE_MONGODB else get_json_collection

# Initialize collections
users_collection = get_collection_func('users')
entries_collection = get_collection_func('entries')
levels_collection = get_collection_func('levels')
sessions_collection = get_collection_func('sessions')
notifications_collection = get_collection_func('notifications')
audit_logs_collection = get_collection_func('audit_logs')

# Print which storage is being used
if USE_MONGODB:
    print("Using MongoDB for data storage")
else:
    print("Using JSON file storage for data")

__all__ = ['User', 'Entry', 'Level', 'Session', 'Notification', 'AuditLog']