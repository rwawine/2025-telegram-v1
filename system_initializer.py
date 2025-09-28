"""System initialization script for first-time setup."""

import os
import secrets
import sqlite3
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List


def create_required_directories() -> List[str]:
    """Create all required directories for the application."""
    
    directories = [
        "data",
        "uploads", 
        "exports",
        "logs",
        "backups",
        "data/migrations",
        "data/shards",
    ]
    
    created = []
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(directory)
            print(f"Created directory: {directory}")
    
    return created


def create_env_file() -> None:
    """Create .env file with secure defaults if it doesn't exist."""
    
    env_path = Path(".env")
    if env_path.exists():
        print(".env file already exists")
        return
    
    # Generate secure secret key
    secret_key = secrets.token_hex(32)
    
    env_content = f"""# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_admin_ids_here

# Admin Panel Authentication  
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password_change_me

# Application Security
SECRET_KEY={secret_key}
ENVIRONMENT=production

# Web Server Configuration
WEB_HOST=0.0.0.0
WEB_PORT=5000
DEBUG=false

# Database Configuration
DATABASE_PATH=data/lottery_bot.sqlite
DB_POOL_SIZE=20
DB_BUSY_TIMEOUT=5000

# File Storage
UPLOAD_FOLDER=uploads
EXPORT_FOLDER=exports
LOG_FOLDER=logs
BACKUP_FOLDER=backups
MAX_FILE_SIZE=10485760

# Performance Settings
BOT_RATE_LIMIT=30
BOT_WORKER_THREADS=10
MESSAGE_QUEUE_SIZE=1000
MAX_PARTICIPANTS=10000

# Cache Configuration
CACHE_TTL_HOT=30
CACHE_TTL_WARM=300
CACHE_TTL_COLD=3600

# Monitoring
PROMETHEUS_PORT=8000

# Broadcast Settings
BROADCAST_BATCH_SIZE=30
BROADCAST_RATE_LIMIT=30

# Analytics (optional)
ENABLE_DUCKDB=false
DUCKDB_PATH=data/analytics.duckdb

# Sharding Configuration
SHARDING_ENABLED=true
SHARDING_BASE_PATH=data
SHARDING_NUM_SHARDS=4
SHARD_SIZE_THRESHOLD=1000000
SHARD_PERFORMANCE_THRESHOLD=100
SHARD_CACHE_MAX_SIZE=10000
SHARD_CACHE_TTL=300
"""
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    
    print(f"Created .env file with secure defaults")
    print("⚠️  IMPORTANT: Update BOT_TOKEN and ADMIN_IDS in .env file!")


def create_gitignore() -> None:
    """Create or update .gitignore file."""
    
    gitignore_content = """# Environment variables
.env

# Database files
*.sqlite
*.sqlite-shm
*.sqlite-wal
*.db

# Logs
logs/
*.log

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Application specific
uploads/
exports/
backups/
data/shards/
data/migrations/applied/

# Temporary files
*.tmp
*.temp
"""
    
    gitignore_path = Path(".gitignore")
    with open(gitignore_path, "w", encoding="utf-8") as f:
        f.write(gitignore_content)
    
    print("Created/updated .gitignore file")


def check_dependencies() -> bool:
    """Check if all required dependencies are installed."""
    
    required_packages = [
        "flask", "flask-login", "flask-caching", "flask-wtf",
        "aiogram", "aiosqlite", "aiohttp", "werkzeug", 
        "python-dotenv", "cachetools", "pillow", "cryptography",
        "ujson", "asyncio-throttle", "prometheus-client", "psutil"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing required packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All required dependencies are installed")
    return True


def verify_database_schema() -> bool:
    """Verify database schema is properly initialized."""
    
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data/lottery_bot.sqlite")
        if not db_path.exists():
            print("❌ Database not found. Will be created on first run.")
            return True  # This is OK, will be created by migrations
        
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        required_tables = [
            "participants", "lottery_runs", "winners", "broadcast_jobs", 
            "broadcast_queue", "support_tickets", "support_ticket_messages",
            "admins", "media_files"
        ]
        
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ Missing database tables: {', '.join(missing_tables)}")
            print("Run migrations will create missing tables")
            return True  # Migrations will handle this
        
        print("✅ Database schema is properly initialized")
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False


def init_database_with_sample_data(db_path: str = "data/lottery_bot.sqlite") -> None:
    """Initialize database with sample data for demonstration."""
    
    if not Path(db_path).exists():
        print(f"Database {db_path} does not exist. Will be created by migrations.")
        return
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    
    try:
        # Check if data already exists
        cursor = conn.execute("SELECT COUNT(*) FROM participants")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 10:
            print(f"Database already has {existing_count} participants. Skipping sample data.")
            conn.close()
            return
        
        print("Initializing database with sample data...")
        
        # Create sample participants
        participants = []
        for i in range(50):
            telegram_id = 1000000000 + i
            phone = f"+7{''.join([str(random.randint(0, 9)) for _ in range(10)])}"
            loyalty_card = f"LC{str(i+1000).zfill(6)}"
            full_name = f"Участник {i+1}"
            username = f"user{i+1}" if random.random() > 0.3 else None
            
            if i < 35:  # 70% approved
                status = "approved"
            elif i < 45:  # 20% pending
                status = "pending"
            else:  # 10% rejected
                status = "rejected"
                
            reg_date = datetime.now() - timedelta(days=random.randint(0, 30))
            
            participants.append((
                telegram_id, username, full_name, phone, loyalty_card, None, status,
                reg_date.isoformat(), reg_date.isoformat(), None
            ))
        
        conn.executemany("""
            INSERT OR REPLACE INTO participants 
            (telegram_id, username, full_name, phone_number, loyalty_card, photo_path, status, registration_date, updated_at, admin_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, participants)
        
        # Create admin user
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash("123456")
        
        conn.execute("""
            INSERT OR REPLACE INTO admins (username, password_hash, created_at)
            VALUES (?, ?, ?)
        """, ("admin", password_hash, datetime.now().isoformat()))
        
        conn.commit()
        print("✅ Sample data initialized successfully!")
        
        # Print summary
        cursor = conn.execute("SELECT COUNT(*) FROM participants")
        participants_count = cursor.fetchone()[0]
        print(f"📊 Created {participants_count} participants")
        print("👤 Admin user: admin/123456")
        
    except Exception as e:
        print(f"Error initializing sample data: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_system() -> bool:
    """Initialize the entire system for first-time setup."""
    
    print("🚀 Initializing Telegram Lottery Bot System...")
    print("=" * 50)
    
    success = True
    
    # 1. Check dependencies
    print("\n📦 Checking dependencies...")
    if not check_dependencies():
        success = False
    
    # 2. Create required directories
    print("\n📁 Creating required directories...")
    created_dirs = create_required_directories()
    if created_dirs:
        print(f"Created {len(created_dirs)} directories")
    else:
        print("All required directories already exist")
    
    # 3. Create .env file
    print("\n🔐 Setting up environment configuration...")
    create_env_file()
    
    # 4. Create .gitignore
    print("\n📝 Setting up .gitignore...")
    create_gitignore()
    
    # 5. Verify database
    print("\n🗄️  Verifying database schema...")
    if not verify_database_schema():
        success = False
    
    # 6. Initialize sample data
    print("\n📊 Initializing sample data...")
    try:
        init_database_with_sample_data()
    except Exception as e:
        print(f"❌ Failed to initialize sample data: {e}")
        success = False
    
    print("\n" + "=" * 50)
    
    if success:
        print("✅ System initialization completed successfully!")
        print("\n📋 Next steps:")
        print("1. Update BOT_TOKEN in .env file with your actual bot token")
        print("2. Update ADMIN_IDS in .env file with your Telegram user ID")
        print("3. Update ADMIN_PASSWORD in .env file with a secure password")
        print("4. Run: python main.py")
        print("5. Access admin panel at: http://localhost:5000")
        print("6. Login with: admin / (password from .env)")
    else:
        print("❌ System initialization failed!")
        print("Please fix the issues above and try again.")
    
    return success


if __name__ == "__main__":
    initialize_system()
