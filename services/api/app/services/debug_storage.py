"""Debug storage for SerpAPI responses.

Saves JSON responses to files when SERPAPI_DEBUG is enabled.
Files are stored in /tmp/serpapi_debug/ and can be accessed via admin endpoints.
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("uvicorn.error")

DEBUG_DIR = Path("/tmp/serpapi_debug")
MAX_FILES = 100  # Keep last 100 files to avoid disk space issues


def ensure_debug_dir() -> Path:
    """Ensure debug directory exists."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    return DEBUG_DIR


def save_shopping_response(query: str, gl: str, data: dict[str, Any]) -> str | None:
    """Save shopping API response to file.

    Args:
        query: Search query.
        gl: Country code.
        data: JSON response data.

    Returns:
        Filename if saved, None if failed.
    """
    try:
        ensure_debug_dir()

        # Create filename: shopping_{timestamp}_{query_hash}.json
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        query_hash = hashlib.sha256(f"{query}:{gl}".encode()).hexdigest()[:8]
        filename = f"shopping_{timestamp}_{query_hash}.json"

        filepath = DEBUG_DIR / filename

        # Save JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "type": "shopping",
                    "query": query,
                    "gl": gl,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        logger.info(f"Saved SerpAPI shopping response to {filepath}")
        _cleanup_old_files()
        return filename
    except Exception as e:
        logger.warning(f"Failed to save shopping response: {e}")
        return None


def save_immersive_response(product_id: str, data: dict[str, Any]) -> str | None:
    """Save immersive API response to file.

    Args:
        product_id: Product ID.
        data: JSON response data.

    Returns:
        Filename if saved, None if failed.
    """
    try:
        ensure_debug_dir()

        # Create filename: immersive_{product_id}_{timestamp}.json
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Sanitize product_id for filename (remove special chars)
        safe_product_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in product_id)[:50]
        filename = f"immersive_{safe_product_id}_{timestamp}.json"

        filepath = DEBUG_DIR / filename

        # Save JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "type": "immersive",
                    "product_id": product_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        logger.info(f"Saved SerpAPI immersive response to {filepath}")
        _cleanup_old_files()
        return filename
    except Exception as e:
        logger.warning(f"Failed to save immersive response: {e}")
        return None


def list_debug_files(limit: int = 50) -> list[dict[str, Any]]:
    """List debug files with metadata.

    Args:
        limit: Maximum number of files to return.

    Returns:
        List of file metadata dicts.
    """
    try:
        if not DEBUG_DIR.exists():
            return []

        files = []
        for filepath in sorted(DEBUG_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
            if len(files) >= limit:
                break

            stat = filepath.stat()
            files.append(
                {
                    "filename": filepath.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": "shopping" if filepath.name.startswith("shopping_") else "immersive",
                }
            )

        return files
    except Exception as e:
        logger.warning(f"Failed to list debug files: {e}")
        return []


def get_debug_file(filename: str) -> dict[str, Any] | None:
    """Read debug file content.

    Args:
        filename: Filename (must be in DEBUG_DIR, no path traversal allowed).

    Returns:
        File content as dict, or None if not found/invalid.
    """
    try:
        # Security: prevent path traversal
        if "/" in filename or ".." in filename:
            return None

        filepath = DEBUG_DIR / filename
        if not filepath.exists() or not filepath.is_file():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read debug file {filename}: {e}")
        return None


def _cleanup_old_files() -> None:
    """Remove old files if we exceed MAX_FILES."""
    try:
        if not DEBUG_DIR.exists():
            return

        files = sorted(DEBUG_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
        if len(files) > MAX_FILES:
            # Remove oldest files
            for filepath in files[MAX_FILES:]:
                try:
                    filepath.unlink()
                    logger.debug(f"Removed old debug file: {filepath.name}")
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Failed to cleanup old debug files: {e}")
