import sys
import os
import logging
from pathlib import Path

# Add this debug code temporarily
print("=== DEBUG: Environment Variables ===")
import os
from dotenv import load_dotenv
load_dotenv()  # Explicitly load .env
print(f"Current working directory: {os.getcwd()}")
print(f"DB_PASSWORD from os.environ: {'SET' if os.getenv('DB_PASSWORD') else 'NOT SET'}")
print(f"DB_PASSWORD length: {len(os.getenv('DB_PASSWORD', ''))}")
print("=====================================")

# Add src directory to Python path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    import uvicorn
    from src.api.server import app
    from src.config.settings import settings
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all dependencies are installed:")
    print("pip install fastapi uvicorn sqlalchemy pydantic watchdog gitpython requests")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_requirements():
    """Check if all required dependencies are available"""
    required_modules = [
        'fastapi', 'uvicorn', 'sqlalchemy', 'pydantic', 
        'watchdog', 'git', 'requests'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print("Missing required modules:")
        for module in missing_modules:
            print(f"  - {module}")
        print("\nInstall missing modules with:")
        print(f"pip install {' '.join(missing_modules)}")
        return False
    
    return True

def main():
    """Main entry point"""
    print("=" * 60)
    print("AI-Powered Testing Companion - Watcher Service")
    print("=" * 60)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Display startup information
    print(f"📡 Starting API server...")
    print(f"🌐 Host: {settings.HOST}")
    print(f"🚪 Port: {settings.PORT}")
    print(f"🐛 Debug mode: {settings.DEBUG}")
    print(f"🤖 AI Backend URL: {settings.AI_BACKEND_URL}")
    print(f"📊 Max repositories: {settings.MAX_REPOSITORIES}")
    print("=" * 60)
    print("📚 API Documentation will be available at:")
    print(f"   http://{settings.HOST}:{settings.PORT}/docs")
    print("🔗 WebSocket live feed at:")
    print(f"   ws://{settings.HOST}:{settings.PORT}/ws/live-feed")
    print("=" * 60)
    
    try:
        # Start the server
        uvicorn.run(
            "src.api.server:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level="info" if not settings.DEBUG else "debug",
            access_log=True
        )
        
    except KeyboardInterrupt:
        print("\nShutting down Watcher Service...")
        logger.info("Server shutdown requested by user")
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()