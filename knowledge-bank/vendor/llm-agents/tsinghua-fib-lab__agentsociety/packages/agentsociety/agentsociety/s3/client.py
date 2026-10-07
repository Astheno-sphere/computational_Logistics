from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError

__all__ = ["S3Config"]


class S3Config(BaseModel):
    """S3 configuration"""

    enabled: bool = Field(default=False)
    """Whether S3 is enabled"""

    endpoint: str = ""
    """S3 endpoint"""

    access_key: str = ""
    """S3 access key"""

    secret_key: str = ""
    """S3 secret key"""

    bucket: str = ""
    """S3 bucket"""

    region: str = ""
    """S3 region"""

    prefix: str = Field(default="")
    """S3 prefix"""


class S3Client:
    """S3 client"""

    def __init__(self, config: S3Config):
        """Initialize S3 client"""
        self.config = config

        self.client = boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name=config.region,
            use_ssl=False,
        )

    def _get_s3_path(self, remote_path: str) -> str:
        """Get S3 path"""
        return f"{self.config.prefix.rstrip('/')}/{remote_path.lstrip('/')}"

    def upload(self, data: bytes, remote_path: str):
        """
        Upload bytes data to S3

        Args:
            data: Bytes data to upload
            remote_path: Target path in S3

        Returns:
            bool: Whether the upload is successful
        """
        s3_path = self._get_s3_path(remote_path)
        self.client.put_object(Body=data, Bucket=self.config.bucket, Key=s3_path)

    def download(self, remote_path: str) -> bytes:
        """
        Download bytes data from S3

        Args:
            remote_path: Path of the file in S3

        Returns:
            bytes | None: Downloaded bytes data, None if failed
        """
        s3_path = self._get_s3_path(remote_path)
        response = self.client.get_object(Bucket=self.config.bucket, Key=s3_path)
        return response["Body"].read()

    def exists(self, remote_path: str) -> bool:
        """
        Check if the file exists in S3
        """
        s3_path = self._get_s3_path(remote_path)
        try:
            self.client.head_object(Bucket=self.config.bucket, Key=s3_path)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                raise e

    def delete(self, remote_path: str):
        """
        Delete a file from S3
        """
        s3_path = self._get_s3_path(remote_path)
        self.client.delete_object(Bucket=self.config.bucket, Key=s3_path)
