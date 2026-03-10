"""
Helper functions for tool operations
"""
import os
import subprocess


def check_http_protocol(target: str, timeout: int = 3) -> str:
    """
    Check if target responds to HTTP or HTTPS and return the working URL.
    
    Args:
        target: The target domain or URL
        timeout: Timeout for curl requests in seconds
        
    Returns:
        URL with working protocol (http:// or https://)
    """
    # If target already has protocol, return as-is
    if target.startswith('http://') or target.startswith('https://'):
        return target
    
    # Try https first
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', str(timeout), f'https://{target}'],
            capture_output=True,
            text=True,
            timeout=timeout + 1
        )
        if result.stdout.strip() == '200':
            return f'https://{target}'
    except Exception:
        pass
    
    # Try http
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', str(timeout), f'http://{target}'],
            capture_output=True,
            text=True,
            timeout=timeout + 1
        )
        if result.stdout.strip() == '200':
            return f'http://{target}'
    except Exception:
        pass
    
    # Default to https if neither works
    return f'https://{target}'


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')
    # Remove null bytes
    filename = filename.replace('\x00', '')
    # Limit length
    return filename[:255]
