"""Utilities for parsing markdown files with frontmatter."""

import re
from pathlib import Path
from typing import Any, Dict, Optional


def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.
    
    Returns:
        Tuple of (frontmatter dict, content without frontmatter)
    """
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if not match:
        return {}, content
    
    frontmatter_text = match.group(1)
    content_text = match.group(2)
    
    # Simple YAML parsing (basic key: value pairs)
    frontmatter = {}
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Handle list values
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip().strip('"\'') for v in value[1:-1].split(',')]
            # Handle boolean values
            elif value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            # Handle numeric values
            elif value.isdigit():
                value = int(value)
            else:
                # Remove quotes if present
                value = value.strip('"\'')
            
            frontmatter[key] = value
    
    return frontmatter, content_text


def read_markdown_file(file_path: Path) -> tuple[Dict[str, Any], str]:
    """Read a markdown file and parse its frontmatter.
    
    Returns:
        Tuple of (frontmatter dict, content)
    """
    content = file_path.read_text(encoding='utf-8')
    return parse_frontmatter(content)


def find_markdown_files(docs_dir: Path) -> list[Path]:
    """Find all markdown files in the docs directory."""
    return list(docs_dir.rglob('*.md'))


def get_doc_by_id(docs_dir: Path, doc_id: str) -> Optional[tuple[Path, Dict[str, Any], str]]:
    """Find a document by its frontmatter ID.
    
    Returns:
        Tuple of (file_path, frontmatter, content) or None if not found
    """
    for md_file in find_markdown_files(docs_dir):
        try:
            frontmatter, content = read_markdown_file(md_file)
            if frontmatter.get('id') == doc_id:
                return md_file, frontmatter, content
        except Exception:
            continue
    return None


