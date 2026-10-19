"""Converts a document into a different format."""

from __future__ import annotations

from io import BytesIO

import requests
from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream

# Docling's Quickstart guide shows the following code:
#
#   ```
#   from docling.document_converter import DocumentConverter
#
#   source = "https://arxiv.org/pdf/2408.09869"  # file path or URL
#   converter = DocumentConverter()
#   doc = converter.convert(source).document
#
#   print(doc.export_to_markdown())  # output: "### Docling Technical Report[...]"
#   ```
#
# However, Docling performs a DNS safety check using socket.getaddrinfo(), 
# which does not use the Squid Proxy. This causes the DNS safety check to fail, 
# and Docling will not fetch content from the requested URL source.
# Hence, we fetch the content ourselves and provide it to Docling as a DocumentStream.

def convert_to_markdown(
    url: str,
) -> str:
    """Fetch the document at the specified URL and return its Markdown."""
    if not url:
        raise ValueError("URL is required.")
    if not url.startswith("https://"):
        raise ValueError("URL must use the HTTPS protocol.")

    content = _fetch_document(url)
    content_bytes = content.encode("utf-8")
    buffer = BytesIO(content_bytes)
    source = DocumentStream(name=url, stream=buffer)
    converter = DocumentConverter()
    result = converter.convert(source)
    return result.document.export_to_markdown()


def _fetch_document(url: str) -> str:
    """Fetch the document content from the specified URL."""
    if not url:
        raise ValueError("URL is required.")
    if not url.startswith("https://"):
        raise ValueError("URL must use the HTTPS protocol.")

    response = requests.get(url)
    response.raise_for_status()
    return response.text