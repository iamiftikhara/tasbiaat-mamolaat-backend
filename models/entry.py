"""
Entry model for daily Saalik submissions
"""

from datetime import datetime, date
# Removed bson import - using JSON storage
# Removed mongo import - using JSON storage

class Entry:
    """Daily entry model for Saalik submissions"""
    
    STATUSES = ['draft', 'submitted', 'reviewed']
    
    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.murabi_id = kwargs.get('murabi_id')
        self.date = kwargs.get('date')
        self.day_index = kwargs.get('day_index')
        self.saalik_level = kwargs.get('saalik_level')
        self.level_at_entry = kwargs.get('level_at_entry')
        self.categories = kwargs.get('categories', {})
        self.zikr_completed = kwargs.get('zikr_completed', False)
        self.status = kwargs.get('status', 'draft')
        self.comments = kwargs.get('comments', [])
        self.audit = kwargs.get('audit', [])
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    def compute_zikr_completed(self):
        """Compute if zikr is completed based on categories"""
        zikr_data = self.categories.get('zikr', {})
        
        # Check morning zikr
        morning_zikr = zikr_data.get('morning', [])
        morning_completed = all(item.get('done', False) for item in morning_zikr)
        
        # Check evening zikr
        evening_zikr = zikr_data.get('evening', [])
        evening_completed = all(item.get('done', False) for item in evening_zikr)
        
        self.zikr_completed = morning_completed and evening_completed
        return self.zikr_completed
    
    def add_comment(self, user_id, role, text):
        """Add a comment to the entry"""
        comment = {
            'by_user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'role': role,
            'text': text,
            'created_at': datetime.utcnow()
        }
        self.comments.append(comment)
        self.add_audit('comment_added', user_id, {'comment_text': text})
    
    def add_audit(self, action, user_id, meta=None):
        """Add audit log entry"""
        audit_entry = {
            'action': action,
            'by': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'at': datetime.utcnow(),
            'meta': meta or {}
        }
        self.audit.append(audit_entry)
    
    def to_dict(self):
        """Convert entry to dictionary"""
        return {
            '_id': str(self._id) if hasattr(self, '_id') else None,
            'user_id': str(self.user_id) if self.user_id else None,
            'murabi_id': str(self.murabi_id) if self.murabi_id else None,
            'date': self.date.isoformat() if isinstance(self.date, date) else self.date,
            'day_index': self.day_index,
            'saalik_level': self.saalik_level,
            'level_at_entry': self.level_at_entry,
            'categories': self.categories,
            'zikr_completed': self.zikr_completed,
            'status': self.status,
            'comments': [
                {
                    'by_user_id': str(comment['by_user_id']),
                    'role': comment['role'],
                    'text': comment['text'],
                    'created_at': comment['created_at'].isoformat()
                } for comment in self.comments
            ],
            'audit': [
                {
                    'action': audit['action'],
                    'by': str(audit['by']),
                    'at': audit['at'].isoformat(),
                    'meta': audit['meta']
                } for audit in self.audit
            ],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Entry instance from dictionary"""
        # Convert string dates back to date objects
        if 'date' in data and isinstance(data['date'], str):
            data['date'] = datetime.fromisoformat(data['date']).date()
        
        # Convert ObjectId strings back to ObjectId
        if 'user_id' in data and isinstance(data['user_id'], str):
            data['user_id'] = ObjectId(data['user_id'])
        if 'murabi_id' in data and isinstance(data['murabi_id'], str):
            data['murabi_id'] = ObjectId(data['murabi_id'])
        
        # Convert comment and audit timestamps
        if 'comments' in data:
            for comment in data['comments']:
                if 'created_at' in comment and isinstance(comment['created_at'], str):
                    comment['created_at'] = datetime.fromisoformat(comment['created_at'])
                if 'by_user_id' in comment and isinstance(comment['by_user_id'], str):
                    comment['by_user_id'] = ObjectId(comment['by_user_id'])
        
        if 'audit' in data:
            for audit in data['audit']:
                if 'at' in audit and isinstance(audit['at'], str):
                    audit['at'] = datetime.fromisoformat(audit['at'])
                if 'by' in audit and isinstance(audit['by'], str):
                    audit['by'] = ObjectId(audit['by'])
        
        entry = cls(**data)
        if '_id' in data:
            entry._id = data['_id']
        return entry
    
    def save(self):
        """Save entry to database"""
        self.updated_at = datetime.utcnow()
        entry_data = self.to_dict()
        entry_data.pop('_id', None)  # Remove _id for insert
        
        from models import entries_collection
        
        if hasattr(self, '_id') and self._id:
            # Update existing entry
            entries_collection.update_one(
                {'_id': self._id},
                {'$set': entry_data}
            )
        else:
            # Insert new entry
            entry_data.pop('_id', None)  # Remove _id for insert
            result = entries_collection.insert_one(entry_data)
            self._id = result.inserted_id
        
        return self
    
    @classmethod
    def find_by_id(cls, entry_id):
        """Find entry by ID"""
        from models import entries_collection
        
        entry_data = entries_collection.find_one({'_id': entry_id})
        if entry_data:
            return cls.from_dict(entry_data)
        return None
    
    @classmethod
    def find_by_user_and_date(cls, user_id, entry_date):
        """Find entry by user ID and date"""
        from models import entries_collection
        
        if isinstance(entry_date, str):
            entry_date = datetime.fromisoformat(entry_date).date()
        
        entry_data = entries_collection.find_one({
            'user_id': user_id,
            'date': entry_date.isoformat()
        })
        if entry_data:
            return cls.from_dict(entry_data)
        return None
    
    @classmethod
    def find_by_murabi(cls, murabi_id, status=None, start_date=None, end_date=None):
        """Find entries by Murabi with optional filters"""
        from models import entries_collection
        
        query = {'murabi_id': murabi_id}
        
        if status:
            query['status'] = status
        
        if start_date or end_date:
            date_query = {}
            if start_date:
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date).date()
                date_query['$gte'] = start_date.isoformat()
            if end_date:
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date).date()
                date_query['$lte'] = end_date.isoformat()
            query['date'] = date_query
        
        entries_data = entries_collection.find(query).sort('date', -1)
        return [cls.from_dict(entry_data) for entry_data in entries_data]
    
    @classmethod
    def find_by_user(cls, user_id, status=None, start_date=None, end_date=None):
        """Find entries by user with optional filters"""
        from models import entries_collection
        
        query = {'user_id': user_id}
        
        if status:
            query['status'] = status
        
        if start_date or end_date:
            date_query = {}
            if start_date:
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date).date()
                date_query['$gte'] = start_date.isoformat()
            if end_date:
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date).date()
                date_query['$lte'] = end_date.isoformat()
            query['date'] = date_query
        
        entries_data = entries_collection.find(query).sort('date', -1)
        return [cls.from_dict(entry_data) for entry_data in entries_data]
    
    @classmethod
    def get_weekly_summary(cls, murabi_ids, start_date, end_date):
        """Get weekly summary for Masool reports"""
        from models import entries_collection
        
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()
        
        pipeline = [
            {
                '$match': {
                    'murabi_id': {'$in': murabi_ids},
                    'date': {
                        '$gte': start_date.isoformat(),
                        '$lte': end_date.isoformat()
                    },
                    'status': 'submitted'
                }
            },
            {
                '$group': {
                    '_id': {
                        'murabi_id': '$murabi_id',
                        'user_id': '$user_id'
                    },
                    'total_entries': {'$sum': 1},
                    'zikr_completed_count': {
                        '$sum': {'$cond': ['$zikr_completed', 1, 0]}
                    },
                    'avg_level': {'$avg': '$saalik_level'}
                }
            }
        ]
        
        return list(entries_collection.aggregate(pipeline))
    
    @classmethod
    def create_indexes(cls):
        """Create database indexes for optimal performance"""
        # Note: JSON storage doesn't support indexes, but keeping method for MongoDB compatibility
        pass