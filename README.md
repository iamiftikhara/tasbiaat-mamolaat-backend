# Tasbiaat Mamolaat Backend API

A comprehensive Flask-based REST API for managing Saalik spiritual practices, daily entries, and hierarchical user management system.

## Features

- **User Management**: Hierarchical role-based system (Admin, Sheikh, Masool, Murabi, Saalik)
- **Authentication**: JWT-based authentication with session management
- **Daily Entries**: Track spiritual practices with level-based validation
- **Reporting**: Weekly, monthly, and custom period reports with analytics
- **Admin Tools**: Bulk operations, system cleanup, and monitoring
- **Notifications**: System-wide and targeted notifications
- **Audit Logging**: Comprehensive activity tracking
- **Rate Limiting**: API protection and abuse prevention

## System Architecture

### User Hierarchy
```
Admin
└── Sheikh
    └── Masool
        └── Murabi
            └── Saalik (Levels 0-6)
```

### Saalik Levels
- **Level 0**: Basic entry (Kalma, Darood, Istighfar)
- **Level 1**: Adds Tasbihat
- **Level 2**: Adds Fikr-e-Maut
- **Level 3**: Adds Muraqaba
- **Level 4**: Adds Tilawat
- **Level 5**: Adds Tahajjud
- **Level 6**: Complete practice set

## Installation

### Prerequisites
- Python 3.8+
- MongoDB 4.4+
- Redis 6.0+ (for rate limiting and caching)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tasbiaat-mamolaat-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   Create a `.env` file in the root directory:
   ```env
   # Flask Configuration
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your-super-secret-key-here
   
   # Database Configuration
   MONGODB_URI=mongodb://localhost:27017/tasbiaat_mamolaat
   MONGODB_DB=tasbiaat_mamolaat
   
   # Redis Configuration (for rate limiting)
   REDIS_URL=redis://localhost:6379/0
   
   # JWT Configuration
   JWT_SECRET_KEY=your-jwt-secret-key-here
   JWT_ACCESS_TOKEN_EXPIRES=3600  # 1 hour
   JWT_REFRESH_TOKEN_EXPIRES=2592000  # 30 days
   
   # Rate Limiting
   RATELIMIT_STORAGE_URL=redis://localhost:6379/1
   
   # Logging
   LOG_LEVEL=INFO
   LOG_FILE=logs/app.log
   
   # Security
   BCRYPT_LOG_ROUNDS=12
   
   # API Configuration
   API_VERSION=v1
   MAX_CONTENT_LENGTH=16777216  # 16MB
   ```

5. **Database Setup**
   ```bash
   # Start MongoDB service
   # Windows (if installed as service)
   net start MongoDB
   
   # Linux
   sudo systemctl start mongod
   
   # Mac
   brew services start mongodb-community
   ```

6. **Initialize Database**
   ```bash
   python -c "
   from app import app
   from models.level import Level
   from models.user import User
   
   with app.app_context():
       # Initialize default levels
       Level.initialize_default_levels()
       print('Default levels initialized')
       
       # Create admin user (optional)
       admin = User.create_user(
           name='System Admin',
           phone='+923001234567',
           email='admin@example.com',
           password='AdminPassword123!',
           role='Admin'
       )
       print(f'Admin user created: {admin.email}')
   "
   ```

7. **Run the application**
   ```bash
   # Development
   python app.py
   
   # Production with Gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

## API Documentation

### Base URL
```
http://localhost:5000/api/v1
```

### Authentication
All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

### Main Endpoints

#### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - Logout current session
- `POST /auth/logout-all` - Logout all sessions
- `POST /auth/refresh` - Refresh JWT token
- `GET /auth/me` - Get current user info

#### Users
- `POST /users` - Create new user
- `GET /users` - List users (role-based)
- `GET /users/<user_id>` - Get user details
- `PUT /users/<user_id>` - Update user
- `POST /users/<user_id>/reset-cycle` - Reset user's cycle

#### Daily Entries
- `POST /entries` - Create/update daily entry
- `GET /entries` - List entries (role-based)
- `GET /entries/<entry_id>` - Get entry details
- `POST /entries/<entry_id>/comment` - Add comment
- `GET /entries/summary` - Get entry summary

#### Reports
- `GET /reports/weekly` - Weekly reports
- `GET /reports/monthly` - Monthly reports
- `GET /reports/custom` - Custom period reports
- `GET /reports/analytics` - Advanced analytics

#### Admin
- `GET /admin/system/status` - System health
- `POST /admin/users/bulk-cycle-reset` - Bulk cycle reset
- `POST /admin/users/bulk-level-update` - Bulk level updates
- `POST /admin/system/cleanup` - System cleanup
- `POST /admin/system/notifications/broadcast` - Broadcast notifications

### Response Format
All API responses follow this format:
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Development

### Project Structure
```
tasbiaat-mamolaat-backend/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables
├── models/               # Database models
│   ├── __init__.py
│   ├── user.py
│   ├── entry.py
│   ├── level.py
│   ├── session.py
│   ├── notification.py
│   └── audit_log.py
├── routes/               # API routes
│   ├── __init__.py
│   ├── auth.py
│   ├── users.py
│   ├── entries.py
│   ├── reports.py
│   ├── admin.py
│   └── levels.py
├── utils/                # Utility functions
│   ├── __init__.py
│   ├── auth.py
│   ├── decorators.py
│   ├── validators.py
│   └── helpers.py
├── config/               # Configuration files
│   └── __init__.py
└── logs/                 # Application logs
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .
```

## Deployment

### Production Checklist
- [ ] Set strong SECRET_KEY and JWT_SECRET_KEY
- [ ] Configure production MongoDB with authentication
- [ ] Set up Redis for production
- [ ] Configure proper logging
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Configure backup strategy
- [ ] Set up log rotation

### Docker Deployment (Optional)
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Environment Variables for Production
```env
FLASK_ENV=production
SECRET_KEY=<strong-secret-key>
JWT_SECRET_KEY=<strong-jwt-secret>
MONGODB_URI=mongodb://username:password@host:port/database
REDIS_URL=redis://username:password@host:port/db
LOG_LEVEL=WARNING
```

## Security Considerations

1. **Authentication**: JWT tokens with configurable expiration
2. **Authorization**: Role-based access control with hierarchy
3. **Rate Limiting**: Configurable per-endpoint limits
4. **Input Validation**: Comprehensive validation for all inputs
5. **Password Security**: Bcrypt hashing with configurable rounds
6. **Audit Logging**: All actions logged with user context
7. **Session Management**: Token-based with revocation support

## Monitoring and Maintenance

### Health Checks
- `GET /admin/system/status` - System health metrics
- Monitor MongoDB connection
- Monitor Redis connection
- Check disk space and memory usage

### Maintenance Tasks
- Regular database cleanup: `POST /admin/system/cleanup`
- Audit log rotation
- Session cleanup
- Notification cleanup

### Backup Strategy
- Daily MongoDB backups
- Configuration file backups
- Log file archival

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   - Check MongoDB service status
   - Verify connection string in .env
   - Check network connectivity

2. **JWT Token Invalid**
   - Check JWT_SECRET_KEY configuration
   - Verify token expiration settings
   - Check system clock synchronization

3. **Rate Limit Exceeded**
   - Check Redis connection
   - Review rate limit configuration
   - Monitor API usage patterns

4. **Permission Denied**
   - Verify user role and hierarchy
   - Check endpoint access requirements
   - Review audit logs for context

### Logs
Application logs are stored in `logs/app.log` and include:
- Request/response details
- Authentication events
- Error messages with stack traces
- Performance metrics

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the troubleshooting section above