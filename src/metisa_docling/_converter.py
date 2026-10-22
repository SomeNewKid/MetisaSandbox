"""Converts a document into a different format."""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from docling.datamodel.backend_options import ThreadedDoclingParseBackendOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.io import DocumentStream
from transformers import AutoTokenizer


def extract_markdown_from_document(
    filename: str,
) -> str:
    """Retrieve data from sample file."""
    if not filename:
        raise ValueError("Filename is required.")

    stream = _get_document_stream(filename)

    document = _convert_pdf_stream_to_docling_document(stream)

    return document.export_to_markdown()


def get_chunks_from_document(
    filename: str,
) -> list[str]:
    """Retrieve data from sample file."""
    if not filename:
        raise ValueError("Filename is required.")

    stream = _get_document_stream(filename)

    document = _convert_pdf_stream_to_docling_document(stream)

    hf_tokenizer = AutoTokenizer.from_pretrained(
        "/models/embedding",
        local_files_only=True,
    )

    tokenizer = HuggingFaceTokenizer(
        tokenizer=hf_tokenizer,
        max_tokens=256,
    )

    chunker = HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
    )

    chunks: list[str] = []
    for chunk in chunker.chunk(dl_doc=document):
        chunk_text = chunker.contextualize(chunk=chunk)
        chunks.append(chunk_text)

    return chunks


def _convert_pdf_stream_to_docling_document(
    document_source: DocumentStream,
) -> DoclingDocument:
    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
    )

    backend_options = ThreadedDoclingParseBackendOptions.model_validate(
        {"parser_threads": 1}
    )

    pdf_options = PdfFormatOption(
        pipeline_options=pipeline_options,
        backend_options=backend_options,
    )

    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF], format_options={InputFormat.PDF: pdf_options}
    )

    result = converter.convert(document_source)

    return result.document


def _get_document_stream(
    filename: str,
) -> DocumentStream:
    if not filename:
        raise ValueError("Filename is required.")

    artifacts_path = os.environ.get("DOCLING_ARTIFACTS_PATH", None)
    if not artifacts_path:
        raise RuntimeError("DOCLING_ARTIFACTS_PATH not set.")
    if not Path(artifacts_path).is_dir():
        raise RuntimeError("Artifacts path does not exist.")

    encoded_filename = quote(filename, safe="/")
    document_url = f"http://metisa-documents:8080/{encoded_filename}"

    with requests.Session() as session:
        # Internal container traffic must bypass Squid.
        session.trust_env = False
        response = session.get(document_url, timeout=(5, 240))
        response.raise_for_status()
        document_bytes = response.content

    if not document_bytes:
        raise RuntimeError("Documents server returned an empty document.")

    document_buffer = BytesIO(document_bytes)
    return DocumentStream(
        name=filename,
        stream=document_buffer,
    )


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
