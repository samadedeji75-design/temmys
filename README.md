# School Result Management System

This project is a Flask-based School Result Management System scaffold for Phase 0.

## Features
- Flask application factory with `create_app()`
- Environment-based configuration
- Blueprint structure for admin, teacher, portal, auth, and API
- Bootstrap 5 and jQuery base template
- Flask-SQLAlchemy and Flask-Migrate integration
- Basic test coverage

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Copy `.env.example` to `.env` and adjust values.
4. Run the app:
   ```bash
   python app.py
   ```

## Testing
```bash
pytest
```
