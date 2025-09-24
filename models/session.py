"""
Session model for user authentication sessions
"""

from datetime import datetime, timedelta
# Removed mongo import - using JSON storage
import secrets

class Session:
    """User session model for JWT token management"""
    
    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.token_id = kwargs.get('token_id', secrets.token_urlsafe(32))
        self.device_info = kwargs.get('device_info', {})
        self.ip_address = kwargs.get('ip_address')
        self.user_agent = kwargs.get('user_agent')
        self.is_active = kwargs.get('is_active', True)
        self.last_activity = kwargs.get('last_activity', datetime.utcnow())
        self.expires_at = kwargs.get('expires_at', datetime.utcnow() + timedelta(days=30))
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    def to_dict(self):
        """Convert session to dictionary"""
        return {
            '_id': str(self._id) if hasattr(self, '_id') else None,
            'user_id': str(self.user_id) if self.user_id else None,
            'token_id': self.token_id,
            'device_info': self.device_info,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'is_active': self.is_active,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Session instance from dictionary"""
        session = cls(**data)
        if '_id' in data:
            session._id = data['_id']
        return session
    
    def save(self):
        """Save session to database"""
        self.updated_at = datetime.utcnow()
        session_data = self.to_dict()
        session_data.pop('_id', None)
        
        from models import sessions_collection
        
        if hasattr(self, '_id') and self._id:
            sessions_collection.update_one(
                {'_id': self._id},
                {'$set': session_data}
            )
        else:
            result = sessions_collection.insert_one(session_data)
            self._id = result.inserted_id
        
        return self
    
    def update_activity(self):
        """Update last activity timestamp"""
        from models import sessions_collection
        
        self.last_activity = datetime.utcnow()
        sessions_collection.update_one(
            {'_id': self._id},
            {'$set': {'last_activity': self.last_activity}}
        )
    
    def deactivate(self):
        """Deactivate session"""
        from models import sessions_collection
        
        self.is_active = False
        self.updated_at = datetime.utcnow()
        sessions_collection.update_one(
            {'_id': self._id},
            {'$set': {
                'is_active': self.is_active,
                'updated_at': self.updated_at
            }}
        )
    
    def is_expired(self):
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self):
        """Check if session is valid (active and not expired)"""
        return self.is_active and not self.is_expired()
    
    @classmethod
    def find_by_token_id(cls, token_id):
        """Find session by token ID"""
        from models import sessions_collection
        
        session_data = sessions_collection.find_one({'token_id': token_id})
        if session_data:
            return cls.from_dict(session_data)
        return None
    
    @classmethod
    def find_by_user_id(cls, user_id):
        """Find all sessions for a user"""
        from models import sessions_collection
        
        sessions_data = sessions_collection.find({'user_id': user_id})
        return [cls.from_dict(session_data) for session_data in sessions_data]
    
    @classmethod
    def find_active_by_user_id(cls, user_id):
        """Find active sessions for a user"""
        from models import sessions_collection
        
        sessions_data = sessions_collection.find({
            'user_id': user_id,
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        return [cls.from_dict(session_data) for session_data in sessions_data]
    
    @classmethod
    def deactivate_all_user_sessions(cls, user_id):
        """Deactivate all sessions for a user"""
        from models import sessions_collection
        
        sessions_collection.update_many(
            {'user_id': user_id},
            {'$set': {
                'is_active': False,
                'updated_at': datetime.utcnow()
            }}
        )
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """Remove expired sessions"""
        from models import sessions_collection
        
        sessions_collection.delete_many({
            'expires_at': {'$lt': datetime.utcnow()}
        })
    
    @classmethod
    def create_indexes(cls):
        """Create database indexes"""
        # Note: JSON storage doesn't support indexes, but keeping method for MongoDB compatibility
        pass