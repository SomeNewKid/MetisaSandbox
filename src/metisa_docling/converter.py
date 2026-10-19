"""Converts a document into a different format."""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import requests
from docling.datamodel.backend_options import ThreadedDoclingParseBackendOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.io import DocumentStream


def extract_from_sample_file(
    filename: str,
) -> str:
    """Retrieve data from sample file."""
    print("***** Called extract_from_sample_file")
    file_location = Path(__file__).parent / "examples" / filename
    print(f"***** File: {file_location}")
    if not file_location.is_file():
        raise FileNotFoundError(f"File not found: {filename}")
    print("***** File exists")

    artifacts_path = os.environ.get("DOCLING_ARTIFACTS_PATH", None)
    if not artifacts_path:
        raise RuntimeError("DOCLING_ARTIFACTS_PATH not set.")
    if not Path(artifacts_path).is_dir():
        raise RuntimeError("Artifacts path does not exist.")

    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
    )
    print("***** Debug 1")

    backend_options = ThreadedDoclingParseBackendOptions.model_validate(
        {"parser_threads": 1}
    )

    pdf_options = PdfFormatOption(
        pipeline_options=pipeline_options,
        backend_options=backend_options,
    )
    print("***** Debug 2")

    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF], format_options={InputFormat.PDF: pdf_options}
    )
    print("***** Debug 3")

    try:
        result = converter.convert(file_location)
        print("***** Debug 4")
    except Exception as error:
        print("***** Debug 5", error)
        raise

    if not result:
        print("***** Debug 6")

    if not result.document:
        print("***** Debug 7")

    markdown = result.document.export_to_markdown()

    if not markdown:
        print("***** Debug 8")

    print(markdown)

    return markdown


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

# While Docling can work with the internet, it is inferior than using Jina Reader.
# Moreover, allowing both Docling and Jina Reader to fetch content from the internet
# is redundant and poses potential security risks.  So, Docling will be disallowed
# from connecting to the internet.  This code, and these comments, remain for
# documentation and educational purposes.


def DISABLED_fetch_to_markdown(
    url: str,
) -> str:
    """Fetch the document at the specified URL and return its Markdown."""
    if not url:
        raise ValueError("URL is required.")
    if not url.startswith("https://"):
        raise ValueError("URL must use the HTTPS protocol.")

    content = _fetch_online_content(url)
    content_bytes = content.encode("utf-8")
    buffer = BytesIO(content_bytes)
    source = DocumentStream(name=url, stream=buffer)
    converter = DocumentConverter()
    result = converter.convert(source)
    return result.document.export_to_markdown()


def _fetch_online_content(url: str) -> str:
    """Fetch the document content from the specified URL."""
    if not url:
        raise ValueError("URL is required.")
    if not url.startswith("https://"):
        raise ValueError("URL must use the HTTPS protocol.")

    response = requests.get(url)
    response.raise_for_status()
    return response.text
