"""
Audit log model for tracking system activities
"""

from datetime import datetime
# Removed mongo import - using JSON storage

class AuditLog:
    def __init__(self, user_id, action, resource_type, resource_id=None, 
                 details=None, ip_address=None, user_agent=None):
        self.user_id = user_id
        self.action = action  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, etc.
        self.resource_type = resource_type  # USER, ENTRY, SESSION, etc.
        self.resource_id = resource_id
        self.details = details or {}
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.timestamp = datetime.utcnow()
    
    def to_dict(self):
        """Convert audit log to dictionary"""
        return {
            '_id': getattr(self, '_id', None),
            'user_id': self.user_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create audit log from dictionary"""
        audit_log = cls(
            user_id=data['user_id'],
            action=data['action'],
            resource_type=data['resource_type'],
            resource_id=data.get('resource_id'),
            details=data.get('details', {}),
            ip_address=data.get('ip_address'),
            user_agent=data.get('user_agent')
        )
        audit_log._id = data.get('_id')
        audit_log.timestamp = data.get('timestamp', datetime.utcnow())
        return audit_log
    
    def save(self):
        """Save audit log to database"""
        from models import audit_logs_collection
        import logging
        
        log_data = self.to_dict()
        log_data.pop('_id', None)
        
        try:
            result = audit_logs_collection.insert_one(log_data)
            self._id = result.inserted_id
            return self
        except Exception as e:
            # Log the error but don't crash the application
            logging.error(f"Failed to save audit log: {str(e)}")
            # Still return self to allow the application to continue
            return self
    
    @classmethod
    def log_action(cls, user_id, action, resource_type, resource_id=None, 
                   details=None, ip_address=None, user_agent=None):
        """Create and save an audit log entry"""
        try:
            audit_log = cls(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent
            )
            return audit_log.save()
        except Exception as e:
            import logging
            logging.error(f"Failed to create audit log: {str(e)}")
            # Return None instead of raising an exception
            return None
    
    @classmethod
    def find_by_user_id(cls, user_id, limit=100, skip=0):
        """Find audit logs for a specific user"""
        from models import audit_logs_collection
        
        logs_data = audit_logs_collection.find({'user_id': user_id})\
            .sort('timestamp', -1)\
            .skip(skip)\
            .limit(limit)
        
        return [cls.from_dict(log_data) for log_data in logs_data]
    
    @classmethod
    def find_by_resource(cls, resource_type, resource_id, limit=50):
        """Find audit logs for a specific resource"""
        from models import audit_logs_collection
        
        logs_data = audit_logs_collection.find({
            'resource_type': resource_type,
            'resource_id': resource_id
        }).sort('timestamp', -1).limit(limit)
        
        return [cls.from_dict(log_data) for log_data in logs_data]
    
    @classmethod
    def find_by_action(cls, action, limit=100, skip=0):
        """Find audit logs by action type"""
        from models import audit_logs_collection
        
        logs_data = audit_logs_collection.find({'action': action})\
            .sort('timestamp', -1)\
            .skip(skip)\
            .limit(limit)
        
        return [cls.from_dict(log_data) for log_data in logs_data]
    
    @classmethod
    def find_by_date_range(cls, start_date, end_date, limit=200, skip=0):
        """Find audit logs within a date range"""
        from models import audit_logs_collection
        
        logs_data = audit_logs_collection.find({
            'timestamp': {
                '$gte': start_date,
                '$lte': end_date
            }
        }).sort('timestamp', -1).skip(skip).limit(limit)
        
        return [cls.from_dict(log_data) for log_data in logs_data]
    
    @classmethod
    def get_user_activity_summary(cls, user_id, days=30):
        """Get activity summary for a user"""
        from models import audit_logs_collection
        from datetime import timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get activity counts by action
        pipeline = [
            {
                '$match': {
                    'user_id': user_id,
                    'timestamp': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': '$action',
                    'count': {'$sum': 1}
                }
            }
        ]
        
        activity_data = list(audit_logs_collection.aggregate(pipeline))
        
        # Get total activity count
        total_activities = audit_logs_collection.count_documents({
            'user_id': user_id,
            'timestamp': {'$gte': start_date}
        })
        
        return {
            'total_activities': total_activities,
            'activity_breakdown': {item['_id']: item['count'] for item in activity_data},
            'period_days': days
        }
    
    @classmethod
    def get_system_activity_summary(cls, days=7):
        """Get system-wide activity summary"""
        from models import audit_logs_collection
        from datetime import timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get activity counts by resource type
        pipeline = [
            {
                '$match': {
                    'timestamp': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': '$resource_type',
                    'count': {'$sum': 1}
                }
            }
        ]
        
        resource_data = list(audit_logs_collection.aggregate(pipeline))
        
        # Get activity counts by action
        action_pipeline = [
            {
                '$match': {
                    'timestamp': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': '$action',
                    'count': {'$sum': 1}
                }
            }
        ]
        
        action_data = list(audit_logs_collection.aggregate(action_pipeline))
        
        # Get total activity count
        total_activities = audit_logs_collection.count_documents({
            'timestamp': {'$gte': start_date}
        })
        
        return {
            'total_activities': total_activities,
            'resource_breakdown': {item['_id']: item['count'] for item in resource_data},
            'action_breakdown': {item['_id']: item['count'] for item in action_data},
            'period_days': days
        }
    
    @classmethod
    def cleanup_old_logs(cls, days_to_keep=90):
        """Remove audit logs older than specified days"""
        from models import audit_logs_collection
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        result = audit_logs_collection.delete_many({
            'timestamp': {'$lt': cutoff_date}
        })
        
        return result.deleted_count
    
    @classmethod
    def create_indexes(cls):
        """Create database indexes"""
        # Note: JSON storage doesn't support indexes, but keeping method for MongoDB compatibility
        pass