"""
Level model for Saalik spiritual levels
"""

from datetime import datetime
# Removed mongo import - using JSON storage

class Level:
    """Saalik spiritual level model"""
    
    def __init__(self, **kwargs):
        self.level = kwargs.get('level')
        self.name_urdu = kwargs.get('name_urdu')
        self.description = kwargs.get('description')
        self.required_fields = kwargs.get('required_fields', [])
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    def to_dict(self):
        """Convert level to dictionary"""
        return {
            '_id': getattr(self, '_id', None),
            'level': self.level,
            'name_urdu': self.name_urdu,
            'description': self.description,
            'required_fields': self.required_fields,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Level instance from dictionary"""
        level = cls(**data)
        if '_id' in data:
            level._id = data['_id']
        return level
    
    def save(self):
        """Save level to database"""
        from models import levels_collection
        
        self.updated_at = datetime.utcnow()
        level_data = self.to_dict()
        level_data.pop('_id', None)
        
        if hasattr(self, '_id') and self._id:
            levels_collection.update_one(
                {'_id': self._id},
                {'$set': level_data}
            )
        else:
            result = levels_collection.insert_one(level_data)
            self._id = result.inserted_id
        
        return self
    
    @classmethod
    def find_by_level(cls, level_num):
        """Find level by level number"""
        from models import levels_collection
        
        level_data = levels_collection.find_one({'level': level_num})
        if level_data:
            return cls.from_dict(level_data)
        return None
    
    @classmethod
    def get_all_levels(cls):
        """Get all levels sorted by level number"""
        from models import levels_collection
        
        levels_data = levels_collection.find().sort('level', 1)
        return [cls.from_dict(level_data) for level_data in levels_data]
    
    @classmethod
    def initialize_default_levels(cls):
        """Initialize default levels from master plan"""
        from models import levels_collection
        
        default_levels = [
            {
                "level": 0,
                "name_urdu": "ابتدائی",
                "description": "قائم تعلق اصلاحی یا بیعت ابھی آغاز کا معمولات کیا۔ کیا نہیں ہوا۔ نہیں",
                "required_fields": ["categories.farayz", "categories.zikr"]
            },
            {
                "level": 1,
                "name_urdu": "معمولات ابتدائی",
                "description": "اور اذکار تسبیحات، مرد روز بنیادی جسمی پابندی کی نمازوں اعمال۔ اور موت، مراقبہ ذکر، آواز بلند آغاز کا تعاملات",
                "required_fields": ["categories.farayz", "categories.zikr", "categories.quran_tilawat"]
            },
            {
                "level": 2,
                "name_urdu": "بالجبر ذکر",
                "description": "مراقبہ دلیلی، ذکر کا سانسوں عمل، کا حضوری کی دل اور",
                "required_fields": ["categories.farayz", "categories.zikr", "categories.quran_tilawat", "categories.nawafil"]
            },
            {
                "level": 3,
                "name_urdu": "الفاس پاس",
                "description": "کی (اللہ معیت مشق) کی لطائف (اللہ صفاتی احساس)، کا برادری (رجوع) مکمل طرف کی",
                "required_fields": ["categories.farayz", "categories.zikr", "categories.quran_tilawat", "categories.nawafil", "categories.hifazat"]
            },
            {
                "level": 4,
                "name_urdu": "لطائف",
                "description": "کرتے فکر، و ذکر کا سطح اعلی، مقامات روحانی",
                "required_fields": ["categories.farayz", "categories.zikr", "categories.quran_tilawat", "categories.nawafil", "categories.hifazat", "categories.sleep_wake"]
            },
            {
                "level": 5,
                "name_urdu": "الاذکار سلطان",
                "description": "اور مراقبے ترین اعلی کی توحید سفر کا فنا مکمل سالک کے اللہ",
                "required_fields": ["categories.farayz", "categories.zikr", "categories.quran_tilawat", "categories.nawafil", "categories.hifazat", "categories.sleep_wake"]
            },
            {
                "level": 6,
                "name_urdu": "اثبات نفی",
                "description": "اعلی ترین مراقبے اور ذکر کی انتہا",
                "required_fields": ["categories.farayz", "categories.zikr", "categories.quran_tilawat", "categories.nawafil", "categories.hifazat", "categories.sleep_wake"]
            }
        ]
        
        for level_data in default_levels:
            existing = cls.find_by_level(level_data['level'])
            if not existing:
                level = cls(**level_data)
                level.save()
    
    @classmethod
    def create_indexes(cls):
        """Create database indexes"""
        # Note: JSON storage doesn't support indexes, but keeping method for MongoDB compatibility
        pass