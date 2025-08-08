import logging
import os
import threading
from pathlib import Path

import boto3
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FileUploader:
    def __init__(self, bucket, key):
        """Initialize the FileUploader with an S3 bucket name.

        Args:
            bucket (str): The name of the S3 bucket to upload to
            key (str): The name of the to be stored file
        """
        session = boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN")
        )
        self.s3_client = session.client("s3")
        self.bucket = bucket
        self.key = key
        self._upload_thread = None

    def upload_file(self, file_path: str, callback=None):
        """Start an asynchronous upload of a file to S3.

        Args:
            file_path (str): Path to the local file to upload
            callback (callable, optional): Function to call when upload completes
        """
        self._upload_thread = threading.Thread(target=self._upload_worker, args=(file_path, callback), daemon=True)
        self._upload_thread.start()

    def _upload_worker(self, file_path: str, callback=None):
        """Background thread that handles the actual file upload.

        Args:
            file_path (str): Path to the local file to upload
            callback (callable, optional): Function to call when upload completes
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Get presigned URL for upload
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={'Bucket': self.bucket, 'Key': self.key},
                ExpiresIn=3600
            )
            
            # Upload file using requests to presigned URL
            with open(str(file_path), 'rb') as f:
                response = requests.put(presigned_url, data=f)
                response.raise_for_status()

            logger.info(f"Successfully uploaded {file_path} to s3://{self.bucket}/{self.key}")

            if callback:
                callback(True)

        except Exception as e:
            logger.error(f"Upload error: {e}")
            if callback:
                callback(False)

    def wait_for_upload(self):
        """Wait for the current upload to complete."""
        if self._upload_thread and self._upload_thread.is_alive():
            self._upload_thread.join()

    def delete_file(self, file_path: str):
        """Delete a file from the local filesystem."""
        file_path = Path(file_path)
        if file_path.exists():
            file_path.unlink()
