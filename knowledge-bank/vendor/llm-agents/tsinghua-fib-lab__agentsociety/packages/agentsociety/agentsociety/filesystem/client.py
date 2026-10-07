import os

__all__ = ["FileSystemClient"]


class FileSystemClient:
    """FileSystem client"""

    def __init__(self, home_dir: str):
        """Initialize FileSystem client"""
        self.home_dir = home_dir

    def get_absolute_path(self, remote_path: str) -> str:
        """Get absolute path"""
        return os.path.join(self.home_dir, remote_path.lstrip("/"))

    def upload(self, data: bytes, remote_path: str):
        """
        Upload bytes data to local file system

        Args:
            data: Bytes data to upload
            remote_path: Target path in local file system

        Returns:
            bool: Whether the upload is successful
        """
        local_path = self.get_absolute_path(remote_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)

    def download(self, remote_path: str) -> bytes:
        """
        Download bytes data from local file system

        Args:
            remote_path: Path of the file in local file system

        Returns:
            bytes | None: Downloaded bytes data, None if failed
        """
        local_path = self.get_absolute_path(remote_path)
        with open(local_path, "rb") as f:
            return f.read()

    def exists(self, remote_path: str) -> bool:
        """
        Check if the file exists in local file system
        """
        local_path = self.get_absolute_path(remote_path)
        return os.path.exists(local_path)

    def delete(self, remote_path: str):
        """
        Delete a file from local file system
        """
        local_path = self.get_absolute_path(remote_path)
        os.remove(local_path)
