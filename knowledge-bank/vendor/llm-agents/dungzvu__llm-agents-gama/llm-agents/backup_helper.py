from pathlib import Path
from typing import Union, Optional
import shutil
import os

from loguru import logger

def backup_file_if_exists(file_path: Union[str, Path], max_backups: int = 100) -> Optional[Path]:
    """
    Backup a file by renaming it with a numeric suffix if it exists.
    
    Args:
        file_path: Path to the file to backup
        max_backups: Maximum number of backup files to keep
    
    Returns:
        Path to the backup file if created, None if original file didn't exist
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return None
    
    # Find the next available backup number
    backup_number = 0
    while backup_number < max_backups:
        backup_path = file_path.with_suffix(f"{file_path.suffix}.{backup_number}")
        if not backup_path.exists():
            break
        backup_number += 1
    else:
        # If we've reached max_backups, remove the oldest and shift others
        return _rotate_backups(file_path, max_backups)
    
    # Rename the original file
    file_path.rename(backup_path)
    logger.info(f"Backed up {file_path} to {backup_path}")
    
    return backup_path

def _rotate_backups(file_path: Path, max_backups: int) -> Path:
    """Rotate backup files when max_backups is reached."""
    
    # Remove the oldest backup (highest number)
    oldest_backup = file_path.with_suffix(f"{file_path.suffix}.{max_backups - 1}")
    if oldest_backup.exists():
        oldest_backup.unlink()
    
    # Shift all backups up by one
    for i in range(max_backups - 2, -1, -1):
        current_backup = file_path.with_suffix(f"{file_path.suffix}.{i}")
        if current_backup.exists():
            next_backup = file_path.with_suffix(f"{file_path.suffix}.{i + 1}")
            current_backup.rename(next_backup)
    
    # Rename the original file to .0
    backup_path = file_path.with_suffix(f"{file_path.suffix}.0")
    file_path.rename(backup_path)
    print(f"Rotated backups and backed up {file_path} to {backup_path}")
    
    return backup_path
