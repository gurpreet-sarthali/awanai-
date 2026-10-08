"""Google Drive API service."""

from __future__ import annotations

import io
from typing import Any

import httpx

from backend.exceptions.handlers import AppError


class GoogleDriveError(AppError):
    pass


class GoogleDriveService:
    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def _get_or_create_askmydata_folder(self) -> str:
        # Check if folder exists
        query = "mimeType='application/vnd.google-apps.folder' and name='AskMyData' and trashed=false"
        resp = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=self.headers,
            params={"q": query, "spaces": "drive", "fields": "files(id, name)"},
        )
        if resp.status_code != 200:
            raise GoogleDriveError(resp.status_code, "drive_error", "Failed to search for AskMyData folder.")
        
        files = resp.json().get("files", [])
        if files:
            return files[0]["id"]
        
        # Create folder
        metadata = {
            "name": "AskMyData",
            "mimeType": "application/vnd.google-apps.folder",
        }
        resp = httpx.post(
            "https://www.googleapis.com/drive/v3/files",
            headers=self.headers,
            json=metadata,
        )
        if resp.status_code != 200:
            raise GoogleDriveError(resp.status_code, "drive_error", "Failed to create AskMyData folder.")
        
        return resp.json()["id"]

    def upload_csv(self, filename: str, file_bytes: bytes) -> dict[str, Any]:
        """Upload a CSV file to the AskMyData folder."""
        folder_id = self._get_or_create_askmydata_folder()
        
        metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        
        files = {
            "metadata": (None, __import__("json").dumps(metadata), "application/json"),
            "file": (filename, file_bytes, "text/csv"),
        }
        
        resp = httpx.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers=self.headers,
            files=files,
        )
        
        if resp.status_code != 200:
            raise GoogleDriveError(resp.status_code, "drive_upload_error", "Failed to upload file to Google Drive.")
        
        return {
            "google_drive_file_id": resp.json()["id"],
            "google_drive_folder_id": folder_id,
            "file_size": len(file_bytes),
        }

    def download_csv(self, file_id: str) -> bytes:
        """Download a file from Google Drive."""
        resp = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
            headers=self.headers,
        )
        if resp.status_code == 404:
            raise GoogleDriveError(404, "file_not_found", "The dataset file was deleted or missing from Google Drive.")
        if resp.status_code != 200:
            raise GoogleDriveError(resp.status_code, "drive_download_error", "Failed to download file from Google Drive.")
        return resp.content

    def delete_file(self, file_id: str) -> None:
        """Delete a file from Google Drive."""
        resp = httpx.delete(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers=self.headers,
        )
        if resp.status_code not in (200, 204, 404):
            raise GoogleDriveError(resp.status_code, "drive_delete_error", "Failed to delete file from Google Drive.")

