"""
Resume Downloader - Handles downloading Google Drive resumes to local file system.
"""

import os
import re

import requests

from config.settings import settings
from core.logger import logger


class ResumeDownloader:
    """Handles parsing and downloading resumes correctly from external sources."""

    @staticmethod
    def download(resume_url: str) -> str:
        """
        Downloads a resume from the provided URL, particularly tailored for Google Drive links.
        Returns the absolute local path to the downloaded file, or None if failed.
        """
        if not resume_url:
            logger.error("No resume_url provided to download.")
            return None

        logger.info(f"Preparing to download resume from: {resume_url}")

        download_dir = os.path.abspath(settings.DOWNLOADED_RESUME_DIR)
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        # Standard file name, we'll overwrite it for each run locally since we only run one candidate at a time right now
        local_filename = "candidate_resume_downloaded.pdf"
        local_path = os.path.join(download_dir, local_filename)

        # Handle Google Drive Links
        if "drive.google.com" in resume_url:
            if "/folders/" in resume_url:
                logger.info("Detected Google Drive Folder Link. Extracting file ID from folder HTML...")
                file_id = ResumeDownloader._extract_id_from_folder(resume_url)
            else:
                file_id = ResumeDownloader._extract_gdrive_id(resume_url)
            
            if file_id:
                logger.info(
                    f"Extracted Google Drive File ID: {file_id}. Downloading..."
                )
                # The generic Google Drive direct download URL format
                download_url = (
                    f"https://drive.google.com/uc?export=download&id={file_id}"
                )

                try:
                    # Stream download to handle large files properly
                    response = requests.get(download_url, stream=True, timeout=30)
                    response.raise_for_status()

                    # Save the content locally
                    with open(local_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    # Simple check: if its html, it's not a pdf (usually auth block)
                    if os.path.getsize(local_path) < 100000:
                        with open(local_path, "r", errors="ignore") as f:
                            header = f.read(200)
                            if "<html" in header.lower():
                                logger.error(
                                    "Downloaded file appears to be HTML (Google Drive auth wall). Make sure link is 'Anyone with the link can view'."
                                )
                                return None

                    logger.info(f"Successfully saved resume to: {local_path}")
                    return local_path
                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to download Google Drive resume: {e}")
                    return None
            else:
                logger.error("Could not parse file ID from Google Drive URL.")
                return None

        # Handle regular direct HTTP links if provided alternatively
        elif resume_url.startswith("http"):
            try:
                logger.info("Attempting direct HTTP download...")
                response = requests.get(resume_url, stream=True, timeout=30)
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Successfully saved resume to: {local_path}")
                return local_path
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download standard URL resume: {e}")
                return None

        logger.error(f"Unsupported resume_url format: {resume_url}")
        return None

    @staticmethod
    def _extract_gdrive_id(url: str) -> str:
        """Extracts the file ID from a standard Google Drive shareable link."""
        # Detect standard "/d/FILE_ID/view" format
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)

        # Detect older "?id=FILE_ID" format
        match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def _extract_id_from_folder(url: str) -> str:
        """Tries to extract the first PDF file ID from a public Google Drive folder HTML source."""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            html = response.text
            
            # Google Drive folders embed file data in a massive JS array.
            # We look for a file ID sitting next to something ending in .pdf
            # Example pattern in the JSON-like data: ["1aBcDeFg_...","Resume.pdf"
            match = re.search(r'\["([a-zA-Z0-9_-]{28,33})","[^"]+\.pdf"', html, re.IGNORECASE)
            if match:
                return match.group(1)
            
            # Fallback: Just grab the first generic file ID we see in the folder payload
            fallback_match = re.search(r'\["([a-zA-Z0-9_-]{28,33})","[^"]+"', html)
            if fallback_match:
                return fallback_match.group(1)
                
            return None
        except Exception as e:
            logger.error(f"Failed to scrape folder link: {e}")
            return None

resume_downloader = ResumeDownloader()
