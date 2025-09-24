"""
Models package initialization
"""

from utils.json_storage import get_collection

from .user import User
from .entry import Entry
from .level import Level
from .session import Session
from .notification import Notification
from .audit_log import AuditLog

# Collections using JSON storage
users_collection = get_collection('users')
entries_collection = get_collection('entries')
levels_collection = get_collection('levels')
sessions_collection = get_collection('sessions')
notifications_collection = get_collection('notifications')
audit_logs_collection = get_collection('audit_logs')

__all__ = ['User', 'Entry', 'Level', 'Session', 'Notification', 'AuditLog']