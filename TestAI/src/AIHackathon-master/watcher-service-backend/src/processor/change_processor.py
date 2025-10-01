import json
import uuid
import asyncio
import requests
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChangeProcessor:
    """
    Processes file changes, saves to database, and communicates with AI backend
    """
    
    def __init__(self, ai_backend_url: str = "http://localhost:5432"):
        self.ai_backend_url = ai_backend_url
        self.ai_timeout = 30
        self.max_retries = 3
        
    def process_file_change(self, file_path: str, change_type: str, change_data: Dict, db: Session) -> Optional[str]:
        """
        Main entry point for processing file changes
        Returns the change_id if successful, None if failed
        """
        try:
            # Step 1: Validate change data
            if not self._validate_change_data(change_data):
                logger.error(f"Invalid change data for {file_path}")
                return None
            
            # Step 2: Save to database
            change_id = self._save_change_to_db(change_data, db)
            if not change_id:
                logger.error(f"Failed to save change to database: {file_path}")
                return None
            
            # Step 3: Send to AI backend (async in background)
            self._queue_for_ai_processing(change_id, db)
            
            logger.info(f"Successfully processed change: {change_data['relative_path']} ({change_type})")
            return change_id
            
        except Exception as e:
            logger.error(f"Error processing file change {file_path}: {e}")
            return None
    
    def _validate_change_data(self, change_data: Dict) -> bool:
        """
        Validate that change data contains all required fields
        """
        required_fields = [
            "repository_id", "file_path", "relative_path", "change_type",
            "timestamp", "file_extension", "author", "author_email"
        ]
        
        for field in required_fields:
            if field not in change_data:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate change_type
        if change_data["change_type"] not in ["created", "modified", "deleted"]:
            logger.error(f"Invalid change_type: {change_data['change_type']}")
            return False
        
        return True
    
    def _get_or_create_user(self, author_email: str, author_name: str, db: Session) -> int:
        """
        Get existing user ID or create new user with auto-incrementing ID
        Returns the user ID (integer)
        """
        try:
            # Import here to avoid circular imports
            from ..models.database import User
            
            # Check if user already exists
            user = db.query(User).filter(User.email == author_email).first()
            
            if user:
                return user.id
            
            # Create new user
            new_user = User(
                email=author_email,
                name=author_name
            )
            
            db.add(new_user)
            db.flush()  # This assigns the auto-incremented ID
            
            logger.info(f"Created new user: ID {new_user.id} for {author_email}")
            return new_user.id
            
        except Exception as e:
            logger.error(f"Error getting/creating user for {author_email}: {e}")
            return None
    
    def _save_change_to_db(self, change_data: Dict, db: Session) -> Optional[str]:
        """
        Save file change to database
        Returns change_id if successful, None if failed
        """
        try:
            # Import here to avoid circular imports
            from ..models.database import FileChange, Repository
            
            # Get or create user
            user_id = self._get_or_create_user(
                change_data["author_email"], 
                change_data["author"], 
                db
            )
            
            if user_id is None:
                logger.error("Failed to get/create user")
                return None
            
            # Generate unique change ID
            change_id = str(uuid.uuid4())
            
            # Create FileChange record
            file_change = FileChange(
                id=change_id,
                repository_id=change_data["repository_id"],
                user_id=user_id,  # Now we have the auto-incrementing user ID
                file_path=change_data["file_path"],
                relative_path=change_data["relative_path"],
                change_type=change_data["change_type"],
                git_diff=change_data.get("git_diff", ""),
                author=change_data["author"],
                author_email=change_data["author_email"],
                commit_hash=change_data.get("commit_hash"),
                file_extension=change_data["file_extension"],
                lines_added=change_data.get("lines_added", 0),
                lines_removed=change_data.get("lines_removed", 0),
                timestamp=datetime.fromisoformat(change_data["timestamp"].replace('Z', '+00:00')),
                is_processed=False,
                sent_to_ai=False
            )
            
            # Add to database
            db.add(file_change)
            
            # Update repository statistics
            repo = db.query(Repository).filter(Repository.id == change_data["repository_id"]).first()
            if repo:
                repo.last_change = datetime.utcnow()
                repo.total_changes = (repo.total_changes or 0) + 1
            
            # Commit transaction
            db.commit()
            
            logger.info(f"Saved change to database: {change_id} (user_id: {user_id})")
            return change_id
            
        except Exception as e:
            logger.error(f"Error saving change to database: {e}")
            db.rollback()
            return None
    
    def _queue_for_ai_processing(self, change_id: str, db: Session):
        """
        Queue change for AI processing (runs in background)
        """
        try:
            # For now, process immediately
            # In production, you might use a proper queue like Celery
            success = self._send_change_to_ai(change_id, db)
            
            if success:
                logger.info(f"Successfully sent change {change_id} to AI backend")
            else:
                logger.warning(f"Failed to send change {change_id} to AI backend")
                
        except Exception as e:
            logger.error(f"Error queueing change {change_id} for AI processing: {e}")
    
    def _send_change_to_ai(self, change_id: str, db: Session) -> bool:
        """
        Send specific change to AI backend
        """
        try:
            # Import here to avoid circular imports
            from ..models.database import FileChange, Repository
            
            # Get change from database
            change = db.query(FileChange).join(Repository).filter(FileChange.id == change_id).first()
            if not change:
                logger.error(f"Change {change_id} not found in database")
                return False
            
            # Skip if already sent
            if change.sent_to_ai:
                logger.info(f"Change {change_id} already sent to AI")
                return True
            
            # Prepare payload for AI backend
            payload = self._prepare_ai_payload(change)
            
            # Send to AI backend with retries
            success = self._send_to_ai_with_retries(payload)
            
            if success:
                # Mark as sent to AI
                change.sent_to_ai = True
                change.is_processed = True
                db.commit()
                return True
            else:
                logger.error(f"Failed to send change {change_id} to AI after all retries")
                return False
                
        except Exception as e:
            logger.error(f"Error sending change {change_id} to AI: {e}")
            return False
    
    def _prepare_ai_payload(self, change) -> Dict:
        """
        Prepare JSON payload for AI backend in the format your boyfriend expects
        """
        # Get file content versions
        previous_content, current_content = self._get_file_versions(change)
        
        return {
            "user_id": change.user_id,  # Auto-incrementing integer ID
            "file_path": change.relative_path,
            "change_type": change.change_type,
            "previousV": previous_content,
            "currentV": current_content
        }
    
    def _get_file_versions(self, change) -> tuple:
        """
        Get previous and current file content based on change type
        """
        try:
            if change.change_type == "created":
                previous = "empty"  # Changed from ""
                current = self._read_current_file(change)
                return previous, current if current else "empty"
                
            elif change.change_type == "deleted":
                previous = self._extract_content_from_diff(change.git_diff)
                return previous if previous else "empty", "empty"  # Changed from ""
                
            else:  # modified
                current = self._read_current_file(change)
                previous = self._get_previous_version(change)
                
                # Replace empty strings with "empty"
                current = current if current else "empty"
                previous = previous if previous else "empty"
                
                return previous, current
                
        except Exception as e:
            logger.error(f"Error getting file versions for {change.relative_path}: {e}")
            return "empty", "empty"  # Changed from "", ""
    
    def _read_current_file(self, change) -> str:
        """
        Read current file content from disk
        """
        try:
            with open(change.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading current file {change.file_path}: {e}")
            return ""
    
    def _get_previous_version(self, change) -> str:
        """
        Get previous version of file from git or diff
        """
        try:
            # Try to get from git first
            from git import Repo
            repo = Repo(change.repository.path)
            
            try:
                # Get file content from HEAD
                return repo.git.show(f"HEAD:{change.relative_path}")
            except:
                # If that fails, try to extract from diff
                return self._extract_content_from_diff(change.git_diff)
                
        except Exception as e:
            logger.error(f"Error getting previous version for {change.relative_path}: {e}")
            return ""
    
    def _extract_content_from_diff(self, git_diff: str) -> str:
        """
        Extract content from git diff (basic implementation)
        This is a simplified version - you might want to make it more robust
        """
        if not git_diff:
            return ""
        
        # This is a very basic extraction - you may need to improve this
        lines = git_diff.split('\n')
        content_lines = []
        
        for line in lines:
            if line.startswith('-') and not line.startswith('---'):
                content_lines.append(line[1:])  # Remove the '-' prefix
            elif not line.startswith('+') and not line.startswith('@@') and not line.startswith('diff'):
                content_lines.append(line)
        
        return '\n'.join(content_lines)
    
    def _send_to_ai_with_retries(self, payload: Dict) -> bool:
        """
        Send payload to AI backend with retry logic
        """

        logger.info(f"Sending payload to AI backend: {json.dumps(payload, indent=2)}")
   

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Sending to AI backend (attempt {attempt}/{self.max_retries})")
                
                response = requests.post(
                    f"{self.ai_backend_url}/api/changes",  # Updated endpoint path
                    json=payload,
                    timeout=self.ai_timeout,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "WatcherService/1.0.0"
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"AI backend accepted change: user_id={payload['user_id']}")
                    return True
                elif response.status_code == 400:
                    logger.error(f"AI backend rejected change (bad request): {response.text}")
                    return False  # Don't retry on 400 errors
                else:
                    logger.warning(f"AI backend returned status {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout sending to AI backend (attempt {attempt})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error to AI backend (attempt {attempt})")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error to AI backend (attempt {attempt}): {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries:
                wait_time = 2 ** attempt  # 2, 4, 8 seconds
                logger.info(f"Waiting {wait_time} seconds before retry...")
                import time
                time.sleep(wait_time)
        
        logger.error(f"Failed to send to AI backend after {self.max_retries} attempts")
        return False
    
    def process_unsent_changes(self, db: Session, limit: int = 10) -> Dict[str, any]:
        """
        Process changes that haven't been sent to AI yet
        """
        try:
            # Import here to avoid circular imports
            from ..models.database import FileChange
            
            # Get unsent changes
            unsent_changes = db.query(FileChange).filter(
                FileChange.sent_to_ai == False
            ).order_by(FileChange.timestamp.asc()).limit(limit).all()
            
            if not unsent_changes:
                return {
                    "success": True,
                    "processed": 0,
                    "message": "No unsent changes found"
                }
            
            results = []
            success_count = 0
            
            for change in unsent_changes:
                success = self._send_change_to_ai(change.id, db)
                results.append({
                    "change_id": change.id,
                    "user_id": change.user_id,
                    "relative_path": change.relative_path,
                    "sent": success
                })
                
                if success:
                    success_count += 1
            
            return {
                "success": True,
                "processed": len(results),
                "successful": success_count,
                "failed": len(results) - success_count,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error processing unsent changes: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed": 0
            }
    
    def get_change_statistics(self, db: Session, repository_id: Optional[str] = None) -> Dict:
        """
        Get statistics about processed changes
        """
        try:
            # Import here to avoid circular imports
            from ..models.database import FileChange
            
            # Base query
            query = db.query(FileChange)
            
            # Filter by repository if specified
            if repository_id:
                query = query.filter(FileChange.repository_id == repository_id)
            
            # Get counts
            total_changes = query.count()
            sent_to_ai = query.filter(FileChange.sent_to_ai == True).count()
            not_sent = total_changes - sent_to_ai
            
            # Get changes by type
            created_count = query.filter(FileChange.change_type == "created").count()
            modified_count = query.filter(FileChange.change_type == "modified").count()
            deleted_count = query.filter(FileChange.change_type == "deleted").count()
            
            # Get recent activity (last 24 hours)
            from datetime import timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_changes = query.filter(FileChange.timestamp >= yesterday).count()
            
            return {
                "total_changes": total_changes,
                "sent_to_ai": sent_to_ai,
                "pending_ai": not_sent,
                "success_rate": (sent_to_ai / total_changes * 100) if total_changes > 0 else 0,
                "by_type": {
                    "created": created_count,
                    "modified": modified_count,
                    "deleted": deleted_count
                },
                "recent_activity": {
                    "last_24h": recent_changes
                },
                "repository_id": repository_id,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting change statistics: {e}")
            return {
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }
    
    def retry_failed_changes(self, db: Session, hours_back: int = 1, limit: int = 20) -> Dict:
        """
        Retry changes that failed to send to AI backend
        """
        try:
            # Import here to avoid circular imports
            from ..models.database import FileChange
            from datetime import timedelta
            
            # Get changes from the last N hours that haven't been sent
            since_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            failed_changes = db.query(FileChange).filter(
                and_(
                    FileChange.sent_to_ai == False,
                    FileChange.timestamp >= since_time
                )
            ).order_by(FileChange.timestamp.desc()).limit(limit).all()
            
            if not failed_changes:
                return {
                    "success": True,
                    "message": f"No failed changes found in the last {hours_back} hours",
                    "retried": 0
                }
            
            results = []
            success_count = 0
            
            for change in failed_changes:
                logger.info(f"Retrying failed change: {change.relative_path}")
                success = self._send_change_to_ai(change.id, db)
                
                results.append({
                    "change_id": change.id,
                    "user_id": change.user_id,
                    "relative_path": change.relative_path,
                    "original_timestamp": change.timestamp.isoformat(),
                    "retry_successful": success
                })
                
                if success:
                    success_count += 1
            
            return {
                "success": True,
                "retried": len(results),
                "successful": success_count,
                "failed": len(results) - success_count,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error retrying failed changes: {e}")
            return {
                "success": False,
                "error": str(e),
                "retried": 0
            }
    
    def health_check(self) -> Dict:
        """
        Check if AI backend is reachable
        """
        try:
            response = requests.get(
                f"{self.ai_backend_url}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                return {
                    "ai_backend_status": "healthy",
                    "response_time": response.elapsed.total_seconds(),
                    "url": self.ai_backend_url
                }
            else:
                return {
                    "ai_backend_status": "unhealthy",
                    "status_code": response.status_code,
                    "url": self.ai_backend_url
                }
                
        except requests.exceptions.RequestException as e:
            return {
                "ai_backend_status": "unreachable",
                "error": str(e),
                "url": self.ai_backend_url
            }


# Factory function for dependency injection
def get_change_processor(ai_backend_url: str = "http://localhost:5432") -> ChangeProcessor:
    """
    Factory function to create ChangeProcessor instance
    """
    return ChangeProcessor(ai_backend_url=ai_backend_url)