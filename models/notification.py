"""
Notification model for managing user notifications
"""

from datetime import datetime, timedelta
# Removed mongo import - using JSON storage

class Notification:
    def __init__(self, user_id, title, message, notification_type='info', 
                 priority='medium', action_url=None, expires_at=None):
        self.user_id = user_id
        self.title = title
        self.message = message
        self.type = notification_type  # info, warning, error, success
        self.priority = priority  # low, medium, high, urgent
        self.is_read = False
        self.action_url = action_url
        self.created_at = datetime.utcnow()
        self.expires_at = expires_at or (datetime.utcnow() + timedelta(days=30))
    
    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            '_id': getattr(self, '_id', None),
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'priority': self.priority,
            'is_read': self.is_read,
            'action_url': self.action_url,
            'created_at': self.created_at,
            'expires_at': self.expires_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create notification from dictionary"""
        notification = cls(
            user_id=data['user_id'],
            title=data['title'],
            message=data['message'],
            notification_type=data.get('type', 'info'),
            priority=data.get('priority', 'medium'),
            action_url=data.get('action_url'),
            expires_at=data.get('expires_at')
        )
        notification._id = data.get('_id')
        notification.is_read = data.get('is_read', False)
        notification.created_at = data.get('created_at', datetime.utcnow())
        return notification
    
    def save(self):
        """Save notification to database"""
        from models import notifications_collection
        
        notification_data = self.to_dict()
        notification_data.pop('_id', None)
        
        if hasattr(self, '_id') and self._id:
            notifications_collection.update_one(
                {'_id': self._id},
                {'$set': notification_data}
            )
        else:
            result = notifications_collection.insert_one(notification_data)
            self._id = result.inserted_id
        
        return self
    
    def mark_as_read(self):
        """Mark notification as read"""
        from models import notifications_collection
        
        self.is_read = True
        notifications_collection.update_one(
            {'_id': self._id},
            {'$set': {'is_read': True}}
        )
    
    def is_expired(self):
        """Check if notification is expired"""
        return datetime.utcnow() > self.expires_at
    
    @classmethod
    def find_by_user_id(cls, user_id, include_read=False, limit=50):
        """Find notifications for a user"""
        from models import notifications_collection
        
        query = {'user_id': user_id}
        if not include_read:
            query['is_read'] = False
        
        # Also filter out expired notifications
        query['expires_at'] = {'$gt': datetime.utcnow()}
        
        notifications_data = notifications_collection.find(query)\
            .sort('created_at', -1)\
            .limit(limit)
        
        return [cls.from_dict(notification_data) for notification_data in notifications_data]
    
    @classmethod
    def count_unread_by_user_id(cls, user_id):
        """Count unread notifications for a user"""
        from models import notifications_collection
        
        return notifications_collection.count_documents({
            'user_id': user_id,
            'is_read': False,
            'expires_at': {'$gt': datetime.utcnow()}
        })
    
    @classmethod
    def mark_all_as_read_by_user_id(cls, user_id):
        """Mark all notifications as read for a user"""
        from models import notifications_collection
        
        notifications_collection.update_many(
            {
                'user_id': user_id,
                'is_read': False
            },
            {'$set': {'is_read': True}}
        )
    
    @classmethod
    def create_bulk_notification(cls, user_ids, title, message, 
                                notification_type='info', priority='medium', 
                                action_url=None, expires_at=None):
        """Create notifications for multiple users"""
        from models import notifications_collection
        
        notifications = []
        for user_id in user_ids:
            notification_data = {
                'user_id': user_id,
                'title': title,
                'message': message,
                'type': notification_type,
                'priority': priority,
                'is_read': False,
                'action_url': action_url,
                'created_at': datetime.utcnow(),
                'expires_at': expires_at or (datetime.utcnow() + timedelta(days=30))
            }
            notifications.append(notification_data)
        
        if notifications:
            notifications_collection.insert_many(notifications)
        
        return len(notifications)
    
    @classmethod
    def cleanup_expired_notifications(cls):
        """Remove expired notifications"""
        from models import notifications_collection
        
        notifications_collection.delete_many({
            'expires_at': {'$lt': datetime.utcnow()}
        })
    
    @classmethod
    def create_indexes(cls):
        """Create database indexes"""
        # Note: JSON storage doesn't support indexes, but keeping method for MongoDB compatibility
        pass