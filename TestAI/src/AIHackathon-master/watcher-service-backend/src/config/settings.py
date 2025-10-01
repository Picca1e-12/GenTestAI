from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Configuration
    HOST: str = "localhost"
    PORT: int = 8001
    DEBUG: bool = True
    
    # MySQL Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "watcher_service"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_CHARSET: str = "utf8mb4"
    
    # Database Connection Pool Settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600  # 1 hour
    DB_POOL_PRE_PING: bool = True
    
    # AI Backend Integration
    AI_BACKEND_URL: str = "http://localhost:54321"
    AI_BACKEND_TIMEOUT: int = 30
    
    # File Watching Configuration
    IGNORED_PATTERNS: list = [
        "*.pyc", "*.log", "*.tmp",
        "node_modules/*", ".git/*", 
        "venv/*", "__pycache__/*"
    ]
    
    # Monitoring Settings
    MAX_REPOSITORIES: int = 10
    CHANGE_BATCH_SIZE: int = 100
    WEBSOCKET_HEARTBEAT: int = 30
    
    # Environment-specific overrides
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Create global settings instance
settings = Settings()

# Validation functions
def validate_db_connection_settings():
    """
    Validate that all required database settings are present
    """
    required_fields = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"]
    missing_fields = []
    
    for field in required_fields:
        value = getattr(settings, field, None)
        if not value:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValueError(f"Missing required database configuration: {', '.join(missing_fields)}")
    
    return True

def get_database_url():
    """
    Build database URL from settings
    """
    from urllib.parse import quote_plus
    
    # Validate settings first
    validate_db_connection_settings()
    
    # URL encode password to handle special characters
    password = quote_plus(settings.DB_PASSWORD) if settings.DB_PASSWORD else ""
    
    # Build connection string
    if password:
        return f"mysql+pymysql://{settings.DB_USER}:{password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset={settings.DB_CHARSET}"
    else:
        return f"mysql+pymysql://{settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset={settings.DB_CHARSET}"

# Display current configuration (for debugging)
def print_config_summary():
    """
    Print current configuration (without sensitive data)
    """
    print("Current Configuration:")
    print(f"  API: {settings.HOST}:{settings.PORT}")
    print(f"  Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"  Database User: {settings.DB_USER}")
    print(f"  AI Backend: {settings.AI_BACKEND_URL}")
    print(f"  Max Repositories: {settings.MAX_REPOSITORIES}")
    print(f"  Debug Mode: {settings.DEBUG}")