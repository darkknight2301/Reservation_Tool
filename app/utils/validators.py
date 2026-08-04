"""Reusable, framework-agnostic field validators used by Pydantic schemas."""
import ipaddress
import re

_HOSTNAME_LABEL_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


def validate_ip_address(value: str) -> bool:
    """Return True if ``value`` is a syntactically valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def validate_hostname(value: str) -> bool:
    """
    Return True if ``value`` is a syntactically valid DNS hostname.

    Follows RFC 1123: each dot-separated label is 1-63 characters, using
    letters/digits/hyphens, and does not start or end with a hyphen. Total
    length must not exceed 253 characters.
    """
    if not value or len(value) > 253:
        return False
    hostname = value[:-1] if value.endswith(".") else value
    labels = hostname.split(".")
    return all(_HOSTNAME_LABEL_RE.match(label) for label in labels)
