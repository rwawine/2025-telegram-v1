"""Automatic backup service for database and critical files."""

import asyncio
import shutil
import sqlite3
import gzip
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import json


logger = logging.getLogger(__name__)


class BackupService:
    """Service for automatic database and file backups."""
    
    def __init__(
        self,
        db_path: str = "data/lottery_bot.sqlite",
        backup_dir: str = "backups",
        max_age_days: int = 2,
        backup_interval_hours: int = 6,
        compress: bool = True
    ):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.max_age_days = max_age_days
        self.backup_interval = backup_interval_hours * 3600  # Convert to seconds
        self.compress = compress
        self.running = False
        self.backup_task: Optional[asyncio.Task] = None
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Backup service initialized: {self.backup_dir}, max_age={max_age_days} days, interval={backup_interval_hours}h")
    
    def create_backup_filename(self, suffix: str = "") -> str:
        """Generate backup filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lottery_bot_backup_{timestamp}{suffix}"
        if self.compress:
            filename += ".gz"
        return filename
    
    def backup_database(self) -> Path:
        """Create a backup of the SQLite database."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        
        backup_filename = self.create_backup_filename("_db.sqlite")
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Use SQLite backup API for safe backup
            source_conn = sqlite3.connect(self.db_path)
            
            if self.compress:
                # Create temporary file for backup, then compress
                temp_backup = self.backup_dir / f"temp_{backup_filename.replace('.gz', '')}"
                backup_conn = sqlite3.connect(temp_backup)
                source_conn.backup(backup_conn)
                backup_conn.close()
                
                # Compress the backup
                with open(temp_backup, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove temporary file
                temp_backup.unlink()
            else:
                # Direct backup without compression
                backup_conn = sqlite3.connect(backup_path)
                source_conn.backup(backup_conn)
                backup_conn.close()
            
            source_conn.close()
            
            logger.info(f"Database backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            raise
    
    def backup_config_files(self) -> List[Path]:
        """Backup critical configuration files."""
        config_files = [
            ".env",
            "config.py", 
            "requirements.txt"
        ]
        
        backed_up_files = []
        
        for config_file in config_files:
            source_path = Path(config_file)
            if source_path.exists():
                backup_filename = self.create_backup_filename(f"_{source_path.stem}{source_path.suffix}")
                backup_path = self.backup_dir / backup_filename
                
                try:
                    if self.compress:
                        with open(source_path, 'rb') as f_in:
                            with gzip.open(backup_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                    else:
                        shutil.copy2(source_path, backup_path)
                    
                    backed_up_files.append(backup_path)
                    logger.debug(f"Config backup created: {backup_path}")
                    
                except Exception as e:
                    logger.warning(f"Failed to backup {config_file}: {e}")
        
        return backed_up_files
    
    def backup_uploads(self) -> Optional[Path]:
        """Backup uploads directory if it exists and has content."""
        uploads_dir = Path("uploads")
        if not uploads_dir.exists() or not any(uploads_dir.iterdir()):
            return None
        
        backup_filename = self.create_backup_filename("_uploads.tar")
        backup_path = self.backup_dir / backup_filename
        
        try:
            import tarfile
            
            # Create tar archive
            with tarfile.open(backup_path, 'w:gz' if self.compress else 'w') as tar:
                tar.add(uploads_dir, arcname='uploads')
            
            logger.info(f"Uploads backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.warning(f"Failed to backup uploads: {e}")
            return None
    
    def create_backup_manifest(self, db_backup: Path, config_backups: List[Path], uploads_backup: Optional[Path]) -> Path:
        """Create a manifest file with backup information."""
        manifest_filename = self.create_backup_filename("_manifest.json")
        manifest_path = self.backup_dir / manifest_filename
        
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "database_backup": str(db_backup.name),
            "config_backups": [str(f.name) for f in config_backups],
            "uploads_backup": str(uploads_backup.name) if uploads_backup else None,
            "compressed": self.compress,
            "total_files": 1 + len(config_backups) + (1 if uploads_backup else 0)
        }
        
        try:
            manifest_content = json.dumps(manifest, indent=2, ensure_ascii=False)
            
            if self.compress:
                with gzip.open(manifest_path, 'wt', encoding='utf-8') as f:
                    f.write(manifest_content)
            else:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(manifest_content)
            
            logger.debug(f"Backup manifest created: {manifest_path}")
            return manifest_path
            
        except Exception as e:
            logger.warning(f"Failed to create backup manifest: {e}")
            return manifest_path
    
    def cleanup_old_backups(self):
        """Keep only the latest 2 backup sets (based on manifest files)."""
        try:
            # Find all manifest files to identify backup sets
            manifest_files = []
            for file_path in self.backup_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith("lottery_bot_backup_") and "_manifest.json" in file_path.name:
                    manifest_files.append(file_path)
            
            # Sort by creation time (newest first)
            manifest_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Keep only the latest 2 backup sets
            keep_count = 2
            if len(manifest_files) <= keep_count:
                logger.debug(f"Only {len(manifest_files)} backup sets found, no cleanup needed")
                return
            
            # Files to keep (from the latest 2 backup sets)
            files_to_keep = set()
            
            for manifest_file in manifest_files[:keep_count]:
                # Parse manifest to get all related files
                try:
                    # Try to read as gzip first, then as regular JSON
                    manifest_data = None
                    try:
                        with gzip.open(manifest_file, 'rt', encoding='utf-8') as f:
                            manifest_data = json.load(f)
                    except (gzip.BadGzipFile, OSError):
                        # Not a gzip file, try as regular JSON
                        with open(manifest_file, 'r', encoding='utf-8') as f:
                            manifest_data = json.load(f)
                    
                    if manifest_data:
                        # Add manifest file itself
                        files_to_keep.add(manifest_file.name)
                        
                        # Add all files from this backup set
                        if manifest_data.get('database_backup'):
                            files_to_keep.add(manifest_data['database_backup'])
                        
                        for config_file in manifest_data.get('config_backups', []):
                            files_to_keep.add(config_file)
                        
                        if manifest_data.get('uploads_backup'):
                            files_to_keep.add(manifest_data['uploads_backup'])
                        
                except Exception as e:
                    logger.warning(f"Failed to parse manifest {manifest_file}: {e}")
                    # Keep the manifest file anyway to be safe
                    files_to_keep.add(manifest_file.name)
            
            # Remove old backup files
            removed_count = 0
            removed_size = 0
            
            for file_path in self.backup_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith("lottery_bot_backup_"):
                    if file_path.name not in files_to_keep:
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            removed_count += 1
                            removed_size += file_size
                            logger.debug(f"Removed old backup: {file_path.name}")
                        except Exception as e:
                            logger.warning(f"Failed to remove old backup {file_path}: {e}")
            
            if removed_count > 0:
                removed_mb = removed_size / (1024 * 1024)
                logger.info(f"🧹 Cleaned up {removed_count} old backup files ({removed_mb:.1f} MB freed), kept latest {keep_count} backup sets")
            else:
                logger.debug("No old backups to clean up")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
    
    def create_full_backup(self) -> bool:
        """Create a complete backup of all critical data."""
        try:
            logger.info("Starting full backup...")
            
            # Backup database
            db_backup = self.backup_database()
            
            # Backup config files
            config_backups = self.backup_config_files()
            
            # Backup uploads
            uploads_backup = self.backup_uploads()
            
            # Create manifest
            self.create_backup_manifest(db_backup, config_backups, uploads_backup)
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            total_files = 1 + len(config_backups) + (1 if uploads_backup else 0)
            logger.info(f"✅ Full backup completed successfully! Files: {total_files}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Full backup failed: {e}")
            return False
    
    async def backup_loop(self):
        """Main backup loop running in background."""
        logger.info(f"🔄 Backup loop started (interval: {self.backup_interval/3600:.1f}h)")
        
        # Create initial backup
        self.create_full_backup()
        
        while self.running:
            try:
                # Wait for next backup interval
                await asyncio.sleep(self.backup_interval)
                
                if self.running:  # Check if still running after sleep
                    self.create_full_backup()
                    
            except asyncio.CancelledError:
                logger.info("Backup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in backup loop: {e}")
                # Continue running even if backup fails
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def start(self):
        """Start the backup service."""
        if self.running:
            logger.warning("Backup service is already running")
            return
        
        self.running = True
        self.backup_task = asyncio.create_task(self.backup_loop())
        logger.info("🚀 Backup service started")
    
    async def stop(self):
        """Stop the backup service."""
        if not self.running:
            return
        
        self.running = False
        
        if self.backup_task:
            self.backup_task.cancel()
            try:
                await self.backup_task
            except asyncio.CancelledError:
                pass
            self.backup_task = None
        
        logger.info("⏹️ Backup service stopped")
    
    def get_backup_info(self) -> dict:
        """Get information about existing backups."""
        try:
            backup_files = []
            total_size = 0
            expired_count = 0
            
            import time
            current_time = time.time()
            max_age_seconds = self.max_age_days * 24 * 3600
            
            for file_path in self.backup_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith("lottery_bot_backup_"):
                    stat = file_path.stat()
                    age_seconds = current_time - stat.st_mtime
                    age_days = (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
                    
                    backup_info = {
                        "name": file_path.name,
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "age_days": age_days,
                        "expires_soon": age_seconds > (max_age_seconds * 0.8)  # Mark if expires in 20% of max age
                    }
                    
                    backup_files.append(backup_info)
                    total_size += stat.st_size
                    
                    if age_seconds > max_age_seconds:
                        expired_count += 1
            
            backup_files.sort(key=lambda x: x["created"], reverse=True)
            
            return {
                "backup_count": len(backup_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "latest_backup": backup_files[0]["created"] if backup_files else None,
                "oldest_backup": backup_files[-1]["created"] if backup_files else None,
                "backup_files": backup_files[:10],  # Show only latest 10
                "running": self.running,
                "interval_hours": self.backup_interval / 3600,
                "max_age_days": self.max_age_days,
                "expired_count": expired_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup info: {e}")
            return {"error": str(e)}


# Global backup service instance
_backup_service: Optional[BackupService] = None


def get_backup_service() -> Optional[BackupService]:
    """Get the global backup service instance."""
    return _backup_service


def init_backup_service(
    db_path: str = "data/lottery_bot.sqlite",
    backup_dir: str = "backups",
    max_age_days: int = 2,
    backup_interval_hours: int = 6
) -> BackupService:
    """Initialize the global backup service."""
    global _backup_service
    
    _backup_service = BackupService(
        db_path=db_path,
        backup_dir=backup_dir,
        max_age_days=max_age_days,
        backup_interval_hours=backup_interval_hours
    )
    
    return _backup_service
