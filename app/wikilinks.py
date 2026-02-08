"""Wikilink resolution and backlink tracking."""

from pathlib import Path
from typing import Optional

from app import config


class WikilinkIndex:
    """Lazy-built index for wikilink resolution."""

    def __init__(self):
        self._cache: Optional[dict[str, list[str]]] = None

    def _build_index(self) -> dict[str, list[str]]:
        """Scan vault and build filename -> paths mapping."""
        index: dict[str, list[str]] = {}
        vault_dir = Path(config.get().vault_dir)

        if not vault_dir.exists():
            return index

        for md_file in vault_dir.rglob("*.md"):
            # Skip hidden directories and private folders
            if any(part.startswith(".") or part.startswith("_") for part in md_file.relative_to(vault_dir).parts[:-1]):
                continue

            filename = md_file.stem
            relative_path = str(md_file.relative_to(vault_dir))

            if filename not in index:
                index[filename] = []
            index[filename].append(relative_path)

        return index

    def get_index(self) -> dict[str, list[str]]:
        """Get or build the filename index."""
        if self._cache is None:
            self._cache = self._build_index()
        return self._cache

    def invalidate_cache(self):
        """Clear the cache (call when vault changes)."""
        self._cache = None

    def resolve(self, filename: str) -> list[str]:
        """Resolve a filename to all matching paths."""
        return self.get_index().get(filename, [])


class BacklinkFinder:
    """Find notes that link to a given filename."""

    WIKILINK_RE = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'

    def __init__(self, vault_dir: str):
        self.vault_dir = Path(vault_dir)

    def find_backlinks(self, target_filename: str) -> list[dict]:
        """
        Find all notes that contain a wikilink to target_filename.
        Returns list of {path, title, snippet}.
        """
        import re

        backlinks = []
        vault_dir = self.vault_dir

        if not vault_dir.exists():
            return backlinks

        for md_file in vault_dir.rglob("*.md"):
            # Skip hidden directories and private folders
            if any(part.startswith(".") or part.startswith("_") for part in md_file.relative_to(vault_dir).parts[:-1]):
                continue

            try:
                content = md_file.read_text(encoding='utf-8')
            except (IOError, UnicodeDecodeError):
                continue

            # Check if this file links to target
            matches = list(re.finditer(self.WIKILINK_RE, content))
            for match in matches:
                linked_name = match.group(1).strip()
                if linked_name == target_filename:
                    # Extract snippet around the wikilink
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    snippet = content[start:end].replace('\n', ' ').strip()

                    # Get title from frontmatter or filename
                    title = self._extract_title(content, md_file)

                    backlinks.append({
                        "path": str(md_file.relative_to(vault_dir)),
                        "title": title,
                        "snippet": f"...{snippet}..."
                    })
                    break  # Only record each note once

        return backlinks

    def _extract_title(self, content: str, file: Path) -> str:
        """Extract title from frontmatter or use filename."""
        import re

        # Try frontmatter title
        frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', frontmatter, re.MULTILINE)
            if title_match:
                return title_match.group(1).strip()

        # Try first H1
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if h1_match:
            return h1_match.group(1).strip()

        # Fallback to filename
        return file.stem


# Global instances (initialized on first use)
_wikilink_index: Optional[WikilinkIndex] = None

def get_wikilink_index() -> WikilinkIndex:
    """Get or create the global wikilink index."""
    global _wikilink_index
    if _wikilink_index is None:
        _wikilink_index = WikilinkIndex()
    return _wikilink_index


def get_backlink_finder() -> BacklinkFinder:
    """Get a backlink finder instance."""
    return BacklinkFinder(config.get().vault_dir)
