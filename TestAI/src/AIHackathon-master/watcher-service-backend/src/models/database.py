from sqlalchemy import create_engine, Column, String, Boolean, Integer, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
import os
from urllib.parse import quote_plus

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)  # Auto-incrementing user ID
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Repository(Base):
    __tablename__ = "repositories"
    
    # MySQL-optimized column definitions
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)  # Added index for better performance
    path = Column(String(500), nullable=False, unique=True)  # Added unique constraint
    is_watching = Column(Boolean, default=False, nullable=False, index=True)  # Added index
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_change = Column(DateTime, nullable=True, index=True)
    total_changes = Column(Integer, default=0, nullable=False)
    
    # Relationship
    changes = relationship("FileChange", back_populates="repository", cascade="all, delete-orphan")

class FileChange(Base):
    __tablename__ = "file_changes"
    
    # MySQL-optimized column definitions
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Add user relationship
    file_path = Column(String(500), nullable=False, index=True)
    relative_path = Column(String(500), nullable=False, index=True)
    change_type = Column(String(20), nullable=False, index=True)  # modified, created, deleted
    git_diff = Column(Text)  # MySQL Text can handle large content
    author = Column(String(255), index=True)
    author_email = Column(String(255), index=True)
    commit_hash = Column(String(40), index=True)
    file_extension = Column(String(10), index=True)
    lines_added = Column(Integer, default=0, nullable=False)
    lines_removed = Column(Integer, default=0, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_processed = Column(Boolean, default=False, nullable=False, index=True)
    sent_to_ai = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    repository = relationship("Repository", back_populates="changes")
    user = relationship("User")

# MySQL Database Configuration
def get_database_url():
    """
    Build MySQL database URL from environment variables or defaults
    """
    # Get database configuration from environment variables
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "watcher_service")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    # URL encode password to handle special characters
    if DB_PASSWORD:
        DB_PASSWORD = quote_plus(DB_PASSWORD)
    
    # Build connection string
    if DB_PASSWORD:
        DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        DATABASE_URL = f"mysql+pymysql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    return DATABASE_URL

# Create engine with MySQL-specific optimizations
DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    # MySQL-specific engine options
    pool_size=10,                    # Connection pool size
    max_overflow=20,                 # Maximum overflow connections
    pool_pre_ping=True,              # Verify connections before use
    pool_recycle=3600,               # Recycle connections every hour
    echo=False,                      # Set to True for SQL debugging
    # MySQL-specific options
    connect_args={
        "charset": "utf8mb4",        # Support for full UTF-8 including emojis
        "autocommit": False,
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_database_if_not_exists():
    """
    Create the database if it doesn't exist
    This function should be called before creating tables
    """
    try:
        from sqlalchemy import create_engine, text
        
        # Get database config
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "3306")
        DB_NAME = os.getenv("DB_NAME", "watcher_service")
        DB_USER = os.getenv("DB_USER", "root")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "")
        
        # URL encode password
        if DB_PASSWORD:
            DB_PASSWORD = quote_plus(DB_PASSWORD)
        
        # Create connection to MySQL server (without specifying database)
        if DB_PASSWORD:
            server_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"
        else:
            server_url = f"mysql+pymysql://{DB_USER}@{DB_HOST}:{DB_PORT}"
        
        # Connect to MySQL server
        server_engine = create_engine(server_url)
        
        # Create database if it doesn't exist
        with server_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(f"SHOW DATABASES LIKE '{DB_NAME}'"))
            if not result.fetchone():
                # Create database with UTF-8 support
                conn.execute(text(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                print(f"Created database: {DB_NAME}")
            else:
                print(f"Database {DB_NAME} already exists")
        
        server_engine.dispose()
        return True
        
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

def init_database():
    """
    Initialize database - create database if needed and create tables
    """
    try:
        # Create database if it doesn't exist
        create_database_if_not_exists()
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("Database tables created/verified successfully")
        return True
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

def test_connection():
    """
    Test database connection and return status
    """
    try:
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        return {
            "status": "success",
            "message": "Database connection successful",
            "database_url": DATABASE_URL.replace(DB_PASSWORD if 'DB_PASSWORD' in locals() else '', '***') if 'DB_PASSWORD' in locals() else DATABASE_URL
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}",
            "database_url": DATABASE_URL.replace(DB_PASSWORD if 'DB_PASSWORD' in locals() else '', '***') if 'DB_PASSWORD' in locals() else DATABASE_URL
        }

# For backward compatibility
def get_session():
    """Get database session (alternative to get_db)"""
    return SessionLocal()