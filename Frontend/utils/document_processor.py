import io
import ipaddress
import socket
import subprocess
import tempfile
from urllib.parse import urlparse

import requests
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from bs4 import BeautifulSoup


MAX_FETCH_BYTES = 2_000_000
REQUEST_TIMEOUT_SECONDS = 10


class DocumentProcessingError(Exception):
    """Raised when a document source cannot be processed into usable text."""


def _extract_text_with_pypdf2(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text() or ""
        text += extracted + "\n"
    return text


def _extract_text_with_pdftotext(file_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(file_bytes)
        temp_pdf.flush()
        result = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", "-layout", "-nopgbrk", temp_pdf.name, "-"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    if result.returncode != 0:
        detail = (result.stderr or "").strip() or "The PDF parser returned a non-zero exit status."
        raise DocumentProcessingError(detail)

    return result.stdout


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file with a fallback parser for harder PDFs."""
    extraction_errors = []

    try:
        text = _extract_text_with_pypdf2(file_bytes)
        if text.strip():
            return text
        extraction_errors.append("PyPDF2 extracted no readable text.")
    except (PdfReadError, NotImplementedError, ValueError) as exc:
        extraction_errors.append(f"PyPDF2 failed: {exc}")
    except Exception as exc:
        extraction_errors.append(f"PyPDF2 failed unexpectedly: {exc}")

    try:
        text = _extract_text_with_pdftotext(file_bytes)
        if text.strip():
            return text
        extraction_errors.append("pdftotext extracted no readable text.")
    except subprocess.TimeoutExpired:
        extraction_errors.append("pdftotext timed out while reading the PDF.")
    except FileNotFoundError:
        extraction_errors.append("pdftotext is not installed on this system.")
    except DocumentProcessingError as exc:
        extraction_errors.append(f"pdftotext failed: {exc}")
    except Exception as exc:
        extraction_errors.append(f"pdftotext failed unexpectedly: {exc}")

    detail = " ".join(extraction_errors)
    raise DocumentProcessingError(
        "This PDF could not be processed into readable text. "
        "Try a different PDF, export it again, or paste the relevant text manually."
        + (f" Details: {detail}" if detail else "")
    )


def _is_public_ip(ip_value: str) -> bool:
    ip = ipaddress.ip_address(ip_value)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_public_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are supported.")
    if not parsed.hostname:
        raise ValueError("The URL must include a hostname.")

    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("Local or internal hosts are not allowed.")

    try:
        resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError("The hostname could not be resolved.") from exc

    for _, _, _, _, sockaddr in resolved:
        if not _is_public_ip(sockaddr[0]):
            raise ValueError("Private, loopback, or reserved network targets are not allowed.")

    return parsed.geturl()


def _download_limited_text(url: str) -> str:
    with requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        stream=True,
        allow_redirects=False,
        headers={"User-Agent": "On-Chain-Due-Diligence-Workstation/1.0"},
    ) as response:
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and not any(token in content_type for token in ("text/", "html", "xml")):
            raise ValueError("Only HTML and plain-text pages are supported.")

        body = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            body.extend(chunk)
            if len(body) > MAX_FETCH_BYTES:
                raise ValueError("The fetched page is too large. Keep URL sources under 2 MB.")

        encoding = response.encoding or "utf-8"
        return body.decode(encoding, errors="replace")


def extract_text_from_url(url: str) -> str:
    """Fetch a public URL and extract visible text using BeautifulSoup."""
    try:
        safe_url = _validate_public_url(url)
        html = _download_limited_text(safe_url)
        soup = BeautifulSoup(html, "html.parser")

        for script in soup(["script", "style"]):
            script.extract()

        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return "\n".join(chunk for chunk in chunks if chunk)
    except ValueError as exc:
        raise DocumentProcessingError(f"URL validation failed: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise DocumentProcessingError("The URL could not be fetched.") from exc
    except Exception as exc:
        raise DocumentProcessingError(
            "An unexpected error occurred while processing the page."
        ) from exc
