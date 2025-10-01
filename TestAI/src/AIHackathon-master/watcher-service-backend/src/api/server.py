import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session
import logging

# Import your custom modules
from src.watcher.file_watcher import WatcherManager
from src.processor.change_processor import ChangeProcessor, get_change_processor
from src.config.settings import settings, print_config_summary
from ..models.database import get_db, Repository, FileChange, engine, Base, init_database, test_connection

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
watcher_manager = WatcherManager()
change_processor = None
websocket_connections: Set[WebSocket] = set()

# Pydantic models for API requests/responses
class RepoRequest(BaseModel):
    name: str
    path: str
    
    @validator('path')
    def validate_path(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"Path does not exist: {v}")
        return os.path.abspath(v)

class RepoResponse(BaseModel):
    id: str
    name: str
    path: str
    is_watching: bool
    created_at: str
    last_change: Optional[str]
    total_changes: int

class ChangeResponse(BaseModel):
    id: str
    repository_id: str
    repository_name: str
    relative_path: str
    change_type: str
    author: str
    timestamp: str
    lines_added: int
    lines_removed: int
    file_extension: str
    is_processed: bool
    sent_to_ai: bool
    git_diff: Optional[str] = None  # Add this
    formatted_changes: Optional[str] = None

class StatusResponse(BaseModel):
    service_status: str
    total_repositories: int
    watching_repositories: int
    total_changes: int
    ai_backend_status: str
    database_status: str
    uptime: str

# Startup and shutdown lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Watcher Service API...")
    
    # Print configuration summary
    print_config_summary()
    
    # Test database connection
    db_status = test_connection()
    if db_status["status"] != "success":
        logger.error(f"Database connection failed: {db_status['message']}")
        logger.error("Please check your MySQL configuration and ensure MySQL is running")
        raise Exception(f"Database connection failed: {db_status['message']}")
    
    logger.info("Database connection successful")
    
    # Initialize database (create database and tables if needed)
    if not init_database():
        logger.error("Failed to initialize database")
        raise Exception("Database initialization failed")
    
    logger.info("Database tables created/verified")
    
    # Initialize change processor
    global change_processor
    change_processor = get_change_processor(settings.AI_BACKEND_URL)
    
    # Add change callback to watcher manager
    watcher_manager.add_change_callback(handle_file_change)
    
    # Load existing repositories from database
    await load_existing_repositories()
    
    logger.info("Watcher Service API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Watcher Service API...")
    watcher_manager.stop_all()
    logger.info("All watchers stopped")

# Create FastAPI app
app = FastAPI(
    title="Watcher Service API",
    description="AI-Powered Testing Companion - File Watcher Service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup time for uptime calculation
startup_time = datetime.utcnow()

# Helper functions
async def load_existing_repositories():
    """Load existing repositories from database and add to watcher manager"""
    db = next(get_db())
    try:
        repositories = db.query(Repository).all()
        for repo in repositories:
            watcher_manager.add_repository(repo.id, repo.path)
            if repo.is_watching:
                watcher_manager.start_watching(repo.id)
        logger.info(f"Loaded {len(repositories)} repositories from database")
    except Exception as e:
        logger.error(f"Error loading repositories from database: {e}")
        db.rollback()
    finally:
        db.close()

def handle_file_change(file_path: str, change_type: str, change_data: Dict):
    """Callback for file changes - processes and broadcasts"""
    try:
        # Get database session
        db = next(get_db())
        
        try:
            # Process the change
            change_id = change_processor.process_file_change(file_path, change_type, change_data, db)
            
            if change_id:
                # Broadcast to WebSocket clients
                asyncio.create_task(broadcast_change(change_data))
                logger.info(f"Processed and broadcasted change: {change_id}")
            
        except Exception as e:
            logger.error(f"Error processing file change {file_path}: {e}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling file change {file_path}: {e}")

async def broadcast_change(change_data: Dict):
    """Broadcast change to all connected WebSocket clients"""
    if not websocket_connections:
        return
    
    # Prepare WebSocket message
    message = {
        "type": "file_change",
        "data": {
            "id": str(uuid.uuid4()),  # Temporary ID for WebSocket
            "repository_name": change_data.get("repository_name", "Unknown"),
            "relative_path": change_data["relative_path"],
            "change_type": change_data["change_type"],
            "timestamp": change_data["timestamp"],
            "author": change_data["author"],
            "file_extension": change_data["file_extension"],
            "lines_added": change_data["lines_added"],
            "lines_removed": change_data["lines_removed"],
            "formatted_changes": change_data.get("formatted_changes", "")
        }
    }
    
    # Send to all connected clients
    disconnected_clients = set()
    for websocket in websocket_connections:
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error broadcasting to WebSocket client: {e}")
            disconnected_clients.add(websocket)
    
    # Remove disconnected clients
    websocket_connections -= disconnected_clients

# API Endpoints

@app.get("/health", response_model=StatusResponse)
async def health_check(db: Session = Depends(get_db)):
    """Service health check with detailed status including database"""
    try:
        # Get repository statistics
        total_repos = db.query(Repository).count()
        watching_repos = db.query(Repository).filter(Repository.is_watching == True).count()
        total_changes = db.query(FileChange).count()
        
        # Check AI backend health
        ai_health = change_processor.health_check()
        
        # Check database status
        db_status = test_connection()
        
        # Calculate uptime
        uptime = str(datetime.utcnow() - startup_time)
        
        return StatusResponse(
            service_status="healthy",
            total_repositories=total_repos,
            watching_repositories=watching_repos,
            total_changes=total_changes,
            ai_backend_status=ai_health["ai_backend_status"],
            database_status=db_status["status"],
            uptime=uptime
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/database/status")
async def get_database_status():
    """Get detailed database connection status"""
    try:
        db_status = test_connection()
        
        # Get additional database info if connected
        if db_status["status"] == "success":
            db = next(get_db())
            try:
                from sqlalchemy import text
                
                # Get MySQL version
                version_result = db.execute(text("SELECT VERSION() as version"))
                mysql_version = version_result.fetchone()[0]
                
                # Get database size info
                db_name = settings.DB_NAME
                size_query = text("""
                    SELECT 
                        table_schema as 'Database',
                        ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) as 'Size_MB'
                    FROM information_schema.tables 
                    WHERE table_schema = :db_name
                    GROUP BY table_schema
                """)
                size_result = db.execute(size_query, {"db_name": db_name})
                size_row = size_result.fetchone()
                database_size = size_row[1] if size_row else 0
                
                # Get table info
                table_query = text("""
                    SELECT table_name, table_rows, 
                           ROUND(((data_length + index_length) / 1024 / 1024), 2) as size_mb
                    FROM information_schema.tables 
                    WHERE table_schema = :db_name
                    ORDER BY table_name
                """)
                table_result = db.execute(table_query, {"db_name": db_name})
                tables = [
                    {
                        "name": row[0], 
                        "rows": row[1] or 0, 
                        "size_mb": row[2] or 0
                    } 
                    for row in table_result.fetchall()
                ]
                
                db_status.update({
                    "mysql_version": mysql_version,
                    "database_size_mb": database_size,
                    "tables": tables,
                    "connection_pool": {
                        "size": engine.pool.size(),
                        "checked_out": engine.pool.checkedout(),
                        "overflow": engine.pool.overflow()
                    }
                })
                
            finally:
                db.close()
        
        return db_status
        
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        return {
            "status": "error",
            "message": f"Error getting database status: {str(e)}"
        }

@app.post("/database/test")
async def test_database_operations():
    """Test basic database operations"""
    try:
        db = next(get_db())
        try:
            from sqlalchemy import text
            
            # Test basic operations
            tests = {
                "connection": False,
                "read": False,
                "transaction": False
            }
            
            # Test connection
            db.execute(text("SELECT 1"))
            tests["connection"] = True
            
            # Test read operation
            count = db.query(Repository).count()
            tests["read"] = True
            
            # Test transaction
            db.begin()
            db.rollback()
            tests["transaction"] = True
            
            return {
                "status": "success",
                "message": "All database operations successful",
                "tests": tests,
                "repository_count": count
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Database operation test failed: {e}")
        return {
            "status": "error",
            "message": f"Database test failed: {str(e)}",
            "tests": {"connection": False, "read": False, "transaction": False}
        }

@app.post("/repos", response_model=RepoResponse)
async def add_repository(repo_data: RepoRequest, db: Session = Depends(get_db)):
    """Add a new repository to watch"""
    try:
        # Check if repository already exists
        existing = db.query(Repository).filter(Repository.path == repo_data.path).first()
        if existing:
            raise HTTPException(status_code=400, detail="Repository already exists")
        
        # Check max repositories limit
        repo_count = db.query(Repository).count()
        if repo_count >= settings.MAX_REPOSITORIES:
            raise HTTPException(status_code=400, detail=f"Maximum {settings.MAX_REPOSITORIES} repositories allowed")
        
        # Create repository record
        repo_id = str(uuid.uuid4())
        new_repo = Repository(
            id=repo_id,
            name=repo_data.name,
            path=repo_data.path,
            is_watching=False,
            created_at=datetime.utcnow(),
            total_changes=0
        )
        
        db.add(new_repo)
        db.commit()
        db.refresh(new_repo)
        
        # Add to watcher manager
        success = watcher_manager.add_repository(repo_id, repo_data.path)
        if not success:
            db.delete(new_repo)
            db.commit()
            raise HTTPException(status_code=400, detail="Failed to initialize repository watcher")
        
        logger.info(f"Added repository: {repo_data.name} at {repo_data.path}")
        
        return RepoResponse(
            id=new_repo.id,
            name=new_repo.name,
            path=new_repo.path,
            is_watching=new_repo.is_watching,
            created_at=new_repo.created_at.isoformat(),
            last_change=new_repo.last_change.isoformat() if new_repo.last_change else None,
            total_changes=new_repo.total_changes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding repository: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add repository: {str(e)}")

@app.delete("/repos/{repo_id}")
async def remove_repository(repo_id: str, db: Session = Depends(get_db)):
    """Remove repository from watching"""
    try:
        # Find repository
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Stop watching if active
        watcher_manager.stop_watching(repo_id)
        watcher_manager.remove_repository(repo_id)
        
        # Delete from database (this will cascade to file_changes)
        db.delete(repo)
        db.commit()
        
        logger.info(f"Removed repository: {repo.name}")
        return {"message": f"Repository {repo.name} removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing repository {repo_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove repository: {str(e)}")

@app.get("/repos", response_model=List[RepoResponse])
async def list_repositories(db: Session = Depends(get_db)):
    """List all watched repositories"""
    try:
        repositories = db.query(Repository).order_by(Repository.created_at.desc()).all()
        
        return [
            RepoResponse(
                id=repo.id,
                name=repo.name,
                path=repo.path,
                is_watching=repo.is_watching,
                created_at=repo.created_at.isoformat(),
                last_change=repo.last_change.isoformat() if repo.last_change else None,
                total_changes=repo.total_changes or 0
            )
            for repo in repositories
        ]
        
    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")

@app.post("/repos/{repo_id}/start")
async def start_watching_repo(repo_id: str, db: Session = Depends(get_db)):
    """Start watching specific repository"""
    try:
        # Find repository
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Start watching
        success = watcher_manager.start_watching(repo_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start watching repository")
        
        # Update database
        repo.is_watching = True
        db.commit()
        
        logger.info(f"Started watching repository: {repo.name}")
        return {"message": f"Started watching {repo.name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting watcher for {repo_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start watching: {str(e)}")

@app.post("/repos/{repo_id}/stop")
async def stop_watching_repo(repo_id: str, db: Session = Depends(get_db)):
    """Stop watching specific repository"""
    try:
        # Find repository
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Stop watching
        success = watcher_manager.stop_watching(repo_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to stop watching repository")
        
        # Update database
        repo.is_watching = False
        db.commit()
        
        logger.info(f"Stopped watching repository: {repo.name}")
        return {"message": f"Stopped watching {repo.name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping watcher for {repo_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to stop watching: {str(e)}")

@app.get("/repos/{repo_id}/status")
async def get_repo_status(repo_id: str, db: Session = Depends(get_db)):
    """Get detailed status of specific repository"""
    try:
        # Find repository
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Get watcher status
        watcher_status = watcher_manager.watchers.get(repo_id)
        if watcher_status:
            detailed_status = watcher_status.get_repo_status()
        else:
            detailed_status = {"error": "Watcher not found"}
        
        return {
            "database_info": {
                "id": repo.id,
                "name": repo.name,
                "path": repo.path,
                "is_watching": repo.is_watching,
                "total_changes": repo.total_changes or 0,
                "last_change": repo.last_change.isoformat() if repo.last_change else None
            },
            "watcher_info": detailed_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting repo status for {repo_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get repo status: {str(e)}")

@app.get("/changes", response_model=List[ChangeResponse])
async def get_recent_changes(
    limit: int = 50, 
    repository_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get recent file changes with optional repository filter"""
    try:
        # Build query
        query = db.query(FileChange).join(Repository)
        
        if repository_id:
            query = query.filter(FileChange.repository_id == repository_id)
        
        # Get recent changes
        changes = query.order_by(FileChange.timestamp.desc()).limit(limit).all()
        
        return [
            ChangeResponse(
                id=change.id,
                repository_id=change.repository_id,
                repository_name=change.repository.name,
                relative_path=change.relative_path,
                change_type=change.change_type,
                author=change.author,
                timestamp=change.timestamp.isoformat(),
                lines_added=change.lines_added,
                lines_removed=change.lines_removed,
                file_extension=change.file_extension,
                is_processed=change.is_processed,
                sent_to_ai=change.sent_to_ai,
                git_diff=change.git_diff,  # Add this
                formatted_changes=getattr(change, 'formatted_changes', None)  # Add this if available
            )
            for change in changes
        ]
        
    except Exception as e:
        logger.error(f"Error getting recent changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get changes: {str(e)}")

@app.post("/changes/process-pending")
async def process_pending_changes(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Process changes that haven't been sent to AI yet"""
    try:
        result = change_processor.process_unsent_changes(db, limit=20)
        
        return {
            "message": "Pending changes processed",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Error processing pending changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process pending changes: {str(e)}")

@app.get("/stats")
async def get_statistics(repository_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Get comprehensive statistics"""
    try:
        # Get change statistics
        change_stats = change_processor.get_change_statistics(db, repository_id)
        
        # Get watcher statistics
        watcher_stats = watcher_manager.get_watching_count()
        
        # Get AI backend health
        ai_health = change_processor.health_check()
        
        return {
            "change_statistics": change_stats,
            "watcher_statistics": watcher_stats,
            "ai_backend_health": ai_health,
            "service_uptime": str(datetime.utcnow() - startup_time)
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

# WebSocket endpoint for real-time updates
@app.websocket("/ws/live-feed")
async def websocket_live_feed(websocket: WebSocket):
    """WebSocket endpoint for real-time change updates"""
    await websocket.accept()
    websocket_connections.add(websocket)
    
    try:
        logger.info(f"WebSocket client connected. Total connections: {len(websocket_connections)}")
        
        # Send welcome message
        welcome_message = {
            "type": "connection_established",
            "data": {
                "message": "Connected to Watcher Service live feed",
                "timestamp": datetime.utcnow().isoformat(),
                "total_connections": len(websocket_connections)
            }
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # Keep connection alive with periodic heartbeat
        while True:
            try:
                # Wait for any message from client (heartbeat or close)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=settings.WEBSOCKET_HEARTBEAT)
                
                # Echo back heartbeat if received
                if message == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                heartbeat = {
                    "type": "heartbeat",
                    "data": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "connections": len(websocket_connections)
                    }
                }
                await websocket.send_text(json.dumps(heartbeat))
                
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        websocket_connections.discard(websocket)
        logger.info(f"WebSocket client removed. Total connections: {len(websocket_connections)}")

# Additional utility endpoints
@app.post("/repos/start-all")
async def start_all_repositories(db: Session = Depends(get_db)):
    """Start watching all repositories"""
    try:
        results = watcher_manager.start_all()
        
        # Update database
        for repo_id, success in results.items():
            if success:
                repo = db.query(Repository).filter(Repository.id == repo_id).first()
                if repo:
                    repo.is_watching = True
        
        db.commit()
        
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        return {
            "message": f"Started {successful}/{total} repositories",
            "details": results
        }
        
    except Exception as e:
        logger.error(f"Error starting all repositories: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start all repositories: {str(e)}")

@app.post("/repos/stop-all")
async def stop_all_repositories(db: Session = Depends(get_db)):
    """Stop watching all repositories"""
    try:
        results = watcher_manager.stop_all()
        
        # Update database
        for repo_id, success in results.items():
            if success:
                repo = db.query(Repository).filter(Repository.id == repo_id).first()
                if repo:
                    repo.is_watching = False
        
        db.commit()
        
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        return {
            "message": f"Stopped {successful}/{total} repositories",
            "details": results
        }
        
    except Exception as e:
        logger.error(f"Error stopping all repositories: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to stop all repositories: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Watcher Service API server with MySQL...")
    uvicorn.run(
        "server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )