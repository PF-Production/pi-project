#!/usr/bin/env python3
"""
Download audio files from URLs specified in .env.local
Maps the URLs to the following filenames:
- WAV_SUM_URL -> files/sum.wav (full mix stereo for 2ch mode)
- WAV_INSTRUMENTS_URL -> files/instruments.wav (L-R surround for 4ch mode)
- WAV_VOX_SUB_URL -> files/vox_sub.wav (L=vox, R=sub for 4ch mode)
"""

import os
import sys
from pathlib import Path
from urllib.request import urlopen

from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(".env.local")

# File mappings
FILE_MAPPINGS = {
    "WAV_SUM_URL": "files/sum.wav",
    "WAV_INSTRUMENTS_URL": "files/instruments.wav",
    "WAV_VOX_SUB_URL": "files/vox_sub.wav",
}


def download_file(url, filepath):
    """Download a file from URL to filepath"""
    if not url:
        print(f"  ⊘ Skipping {filepath} - no URL provided")
        return False

    try:
        filepath_obj = Path(filepath)
        filepath_obj.parent.mkdir(parents=True, exist_ok=True)

        print(f"  Downloading {filepath}...")
        with urlopen(url) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 8192

            with open(filepath, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"    {progress:.1f}%", end="\r")

        print(f"  ✓ {filepath}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to download {filepath}: {e}")
        return False


def main():
    print("Downloading audio files from .env.local URLs...\n")

    success_count = 0
    for env_var, filepath in FILE_MAPPINGS.items():
        url = os.getenv(env_var)
        if url and download_file(url, filepath):
            success_count += 1

    print(f"\nDownloaded {success_count}/{len(FILE_MAPPINGS)} files")

    if success_count == 0:
        print("\nNo files downloaded. Please populate .env.local with URLs:")
        for env_var in FILE_MAPPINGS.keys():
            print(f"  {env_var}=<url>")
        sys.exit(1)


if __name__ == "__main__":
    main()
