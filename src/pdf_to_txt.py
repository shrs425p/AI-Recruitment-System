import io  # BytesIO for in-memory image conversion
import logging

logger = logging.getLogger(__name__)
import re  # Regex — used to clean whitespace in extracted text
import sys  # Used for sys.exit() in the watcher
import time  # Used for sleep() in the polling loop
from pathlib import Path  # Modern cross-platform path handling

import pytesseract  # Python wrapper for the Tesseract OCR engine
from PIL import Image  # Pillow — open PNG/JPG image files
from pypdf import PdfReader  # Pure-Python PDF parsing (BSD-3 licensed)

from src.common import data_path, install_path
from src.security import decrypt_bytes

logger = logging.getLogger("ars.pdf_to_txt")

# ─────────────────────────────────────────────
# TESSERACT OCR ENGINE PATH
# ─────────────────────────────────────────────

_bundled_tesseract = install_path("models/Tesseract-OCR") / "tesseract.exe"
if _bundled_tesseract.exists():
    pytesseract.pytesseract.tesseract_cmd = str(_bundled_tesseract)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

INPUT_FOLDER            = data_path("resumes")      # Folder where uploaded resumes are placed
OUTPUT_FOLDER           = data_path("output/txt")   # Folder where extracted .txt files are saved

# Threshold (characters) used to decide whether a PDF has real embedded text.
# If direct extraction yields fewer characters than this, the PDF is treated as
# a scanned image and OCR is used instead.
MIN_DIGITAL_TEXT_LENGTH = 800

# How frequently (seconds) the watcher loop checks for new files.
WATCH_INTERVAL_SECONDS  = 5

# ─────────────────────────────────────────────
# EXTRACT DIRECT TEXT FROM DIGITAL PDF
# ─────────────────────────────────────────────

def extract_direct_text(pdf_input):
    """
    Extract embedded text from a digital PDF using pypdf.

    This is fast (~milliseconds) because it reads text already stored in the
    PDF rather than running OCR. Works for PDFs created by Word, LaTeX, etc.

    Accepts a file path (str or Path) or raw bytes. Transparently decrypts
    encrypted files at rest if needed.

    Returns:
        str — extracted text (may be empty for scanned PDFs).
    """
    try:
        if isinstance(pdf_input, (bytes, bytearray)):
            decrypted = decrypt_bytes(pdf_input)
        else:
            path = Path(pdf_input)
            if not path.exists():
                return ""
            decrypted = decrypt_bytes(path.read_bytes())

        reader = PdfReader(io.BytesIO(decrypted))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.info(f"> [extract_direct_text] Error: {e}")
        return ""

def extract_docx_text(docx_input):
    """
    Extract text and table contents from a Microsoft Word (.docx) document.

    Accepts a file path (str or Path) or raw bytes. Transparently decrypts
    encrypted files at rest if needed.

    Returns:
        str — extracted text.
    """
    try:
        import docx

        if isinstance(docx_input, (bytes, bytearray)):
            decrypted = decrypt_bytes(docx_input)
        else:
            path = Path(docx_input)
            if not path.exists():
                return ""
            decrypted = decrypt_bytes(path.read_bytes())

        doc = docx.Document(io.BytesIO(decrypted))
        lines = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                lines.append(txt)

        # Extract structured content from tables
        for table in doc.tables:
            for row in table.rows:
                cells_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                seen = set()
                unique_cells = []
                for c in cells_text:
                    if c not in seen:
                        seen.add(c)
                        unique_cells.append(c)
                if unique_cells:
                    lines.append(" | ".join(unique_cells))

        return "\n".join(lines).strip()
    except Exception as e:
        logger.warning(f"> [extract_docx_text] Error: {e}")
        return ""


# ─────────────────────────────────────────────
# CLEAN EXTRACTED TEXT
# ─────────────────────────────────────────────

def clean_text(text):
    """
    Normalise raw extracted text so it is clean and consistent.

    Steps:
      - Remove null bytes that can appear in some PDFs.
      - Normalise Windows-style line endings (\\r\\n → \\n).
      - Collapse runs of 3+ blank lines into a single blank line
        (preserves paragraph breaks without excessive whitespace).
      - Collapse multiple spaces/tabs into a single space.
    """
    text = text.replace("\x00", "")        # Remove null bytes (binary artefacts)
    text = text.replace("\r\n", "\n")      # Normalise Windows line endings → Unix
    text = re.sub(r'\n{3,}', '\n\n', text) # Collapse 3+ blank lines → 1 blank line
    text = re.sub(r'[ \t]+', ' ', text)    # Collapse multiple spaces/tabs → single space
    return text.strip()

# ─────────────────────────────────────────────
# PROCESS A SINGLE FILE
# ─────────────────────────────────────────────

def process_file(file_path: Path, output_path: Path):
    """
    Convert a single PDF or image resume to a plain .txt file.

    Logic:
      1. Skip if the output .txt already exists (idempotent — safe to re-run).
      2. For PDFs: try direct text extraction first; fall back to OCR if short.
      3. For images (PNG/JPG): always use OCR.
      4. Clean the extracted text.
      5. Skip saving if the result is empty (avoids blank files).
      6. Write the .txt file next to the other converted resumes.

    Returns:
      True  — new file was processed and saved.
      False — file was skipped (already exists) or extraction yielded nothing.
    """
    # Build the expected output path  (e.g. resumes/John.pdf → output/txt/John.txt)
    target_txt = output_path / f"{file_path.stem}.txt"

    # Skip files that have already been converted — avoids reprocessing on restart
    if target_txt.exists():
        return False  # Already done, not a new file

    logger.info(f"> Processing: {file_path.name}...")

    try:
        full_text = ""
        raw_bytes = file_path.read_bytes()
        file_bytes = decrypt_bytes(raw_bytes)

        if file_path.suffix.lower() == '.docx':
            full_text = extract_docx_text(file_bytes)
            logger.info("(Word DOCX Text)")
        elif file_path.suffix.lower() == '.pdf':
            # Try cheap direct extraction first
            extracted_text = extract_direct_text(file_bytes)

            if len(extracted_text) > MIN_DIGITAL_TEXT_LENGTH:
                # PDF has proper embedded text — use it directly (fast path)
                full_text = extracted_text
                logger.info("(Direct Text)")
            else:
                # Scanned PDF or mixed pages — extract page images via pypdf and OCR
                ocr_text = ""
                try:
                    reader = PdfReader(io.BytesIO(file_bytes))
                    for page in reader.pages:
                        page_direct = page.extract_text() or ""
                        if page_direct.strip():
                            ocr_text += page_direct + "\n"
                        for img_file in page.images:
                            try:
                                ocr_text += pytesseract.image_to_string(img_file.image) + "\n"
                            except Exception as err:
                                logger.info(f"> OCR image extraction failed for page item: {err}")
                except Exception as e:
                    logger.info(f"> [pypdf OCR Fallback] Error reading pages: {e}")

                full_text = ocr_text if ocr_text.strip() else extracted_text
                logger.info("(OCR Fallback)" if full_text else "(No Text Found)")

        else:
            # PNG / JPG — always OCR because there is no embedded text layer
            full_text = pytesseract.image_to_string(Image.open(io.BytesIO(file_bytes)))
            logger.info("(Image OCR)")

        # Clean up the raw text regardless of how it was extracted
        full_text = clean_text(full_text)

        # Guard: do not save a blank file (OCR may produce nothing for blank pages)
        if not full_text.strip():
            logger.info("> Empty output, skipping save.")
            return False

        # Write the cleaned text to disk in UTF-8 encoding
        target_txt.parent.mkdir(parents=True, exist_ok=True)
        with open(target_txt, "w", encoding="utf-8") as f:
            f.write(full_text)

        logger.info("> Success")
        return True  # Signal to caller that a new file was created

    except Exception as e:
        logger.info(f"> Failed! {e}")
        return False

# ─────────────────────────────────────────────
# MAIN: INFINITE WATCH LOOP
# ─────────────────────────────────────────────

def run_watcher():
    """
    Poll the resumes/ folder every WATCH_INTERVAL_SECONDS seconds and process
    any new PDF/Word/image files found. Runs forever until Ctrl+C is pressed.

    Useful for running as a standalone background service during a recruitment
    session where resumes are being added in real-time.
    """
    input_path  = INPUT_FOLDER
    output_path = OUTPUT_FOLDER

    # Create folders if they don't exist (first-time setup)
    input_path.mkdir(exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 50)
    logger.info("   RESUME -> TXT LIVE WATCHER STARTED")
    logger.info("=" * 50)
    logger.info(f"> Watching folder : {input_path}")
    logger.info(f"> Output folder   : {output_path}")
    logger.info(f"> Check interval  : every {WATCH_INTERVAL_SECONDS} seconds")
    logger.info("> Supported types : PDF, DOCX, PNG, JPG, JPEG")
    logger.info("> Press Ctrl+C to stop\n")

    processed_count = 0  # Counter for reporting at end of session

    while True:
        try:
            # List only files (not subdirectories) with supported extensions
            files = [
                f for f in input_path.iterdir()
                if f.is_file()                                          # skip directories
                and f.suffix.lower() in ['.pdf', '.docx', '.png', '.jpg', '.jpeg']  # only resume formats
            ]

            new_files_found = False

            for file_path in files:
                is_new = process_file(file_path, output_path)
                if is_new:
                    processed_count += 1
                    new_files_found = True  # suppress idle message this cycle

            # Show an idle status indicator when there is nothing new to process
            if not new_files_found:
                logger.info(f"\r> Watching... (processed so far: {processed_count}) | waiting for new files...")

            time.sleep(WATCH_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            # Ctrl+C pressed — exit cleanly with a summary
            logger.info("\n\n> Watcher stopped safely.")
            logger.info(f"> Total files processed this session: {processed_count}")
            sys.exit(0)

        except Exception as e:
            # Unexpected error — log and keep watching (resilient)
            logger.info(f"\n> [Watcher Error] {e} — retrying in {WATCH_INTERVAL_SECONDS}s...")
            time.sleep(WATCH_INTERVAL_SECONDS)
            continue

# Entry point when run directly: python pdf_to_txt.py
if __name__ == "__main__":
    run_watcher()
