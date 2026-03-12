import pytesseract                     # Python wrapper for the Tesseract OCR engine
from PIL import Image                  # Pillow — open PNG/JPG image files
from pathlib import Path               # Modern cross-platform path handling
import fitz                            # PyMuPDF — extract text + render pages to images
import io                              # BytesIO for in-memory image conversion
import sys                             # Used for sys.exit() in the watcher
import re                              # Regex — used to clean whitespace in extracted text
import time                            # Used for sleep() in the polling loop
from app_paths import data_path, install_path

# ─────────────────────────────────────────────
# TESSERACT OCR ENGINE PATH
# ─────────────────────────────────────────────

# Point pytesseract at the bundled Tesseract binary so the system PATH is not
# required — makes the app portable without extra install steps for the user.
pytesseract.pytesseract.tesseract_cmd = str(install_path("Tesseract-OCR") / "tesseract.exe")

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

def extract_direct_text(pdf_path):
    """
    Extract embedded text from a digital PDF using PyMuPDF (fitz).

    This is fast (~milliseconds) because it reads text already stored in the
    PDF rather than running OCR.  Works for PDFs created by Word, LaTeX, etc.

    Returns:
        str — extracted text (may be empty for scanned PDFs).
    """
    try:
        with fitz.open(pdf_path) as doc:
            text = ""
            for page in doc:
                # get_text("text") returns plain text without layout styling
                text += page.get_text("text") + "\n"
            return text.strip()
    except Exception as e:
        print(f"> [extract_direct_text] Error: {e}")
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

    print(f"> Processing: {file_path.name}...", end=" ", flush=True)

    try:
        full_text = ""

        if file_path.suffix.lower() == '.pdf':
            # Try cheap direct extraction first
            extracted_text = extract_direct_text(str(file_path))

            if len(extracted_text) > MIN_DIGITAL_TEXT_LENGTH:
                # PDF has proper embedded text — use it directly (fast path)
                full_text = extracted_text
                print("(Direct Text)", end=" ")
            else:
                # Likely a scanned PDF — render pages to images via PyMuPDF then OCR
                # matrix with zoom=3 gives ~300 dpi (72 * 3 ≈ 216–300 effective)
                with fitz.open(str(file_path)) as doc:
                    for page in doc:
                        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        full_text += pytesseract.image_to_string(img) + "\n"
                print("(OCR Fallback)", end=" ")

        else:
            # PNG / JPG — always OCR because there is no embedded text layer
            full_text = pytesseract.image_to_string(Image.open(file_path))
            print("(Image OCR)", end=" ")

        # Clean up the raw text regardless of how it was extracted
        full_text = clean_text(full_text)

        # Guard: do not save a blank file (OCR may produce nothing for blank pages)
        if not full_text.strip():
            print("> Empty output, skipping save.")
            return False

        # Write the cleaned text to disk in UTF-8 encoding
        with open(target_txt, "w", encoding="utf-8") as f:
            f.write(full_text)

        print("> Success")
        return True  # Signal to caller that a new file was created

    except Exception as e:
        print(f"> Failed! {e}")
        return False

# ─────────────────────────────────────────────
# MAIN: INFINITE WATCH LOOP
# ─────────────────────────────────────────────

def run_watcher():
    """
    Poll the resumes/ folder every WATCH_INTERVAL_SECONDS seconds and process
    any new PDF/image files found.  Runs forever until Ctrl+C is pressed.

    Useful for running as a standalone background service during a recruitment
    session where resumes are being added in real-time.
    """
    input_path  = INPUT_FOLDER
    output_path = OUTPUT_FOLDER

    # Create folders if they don't exist (first-time setup)
    input_path.mkdir(exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("   PDF -> TXT LIVE WATCHER STARTED")
    print("=" * 50)
    print(f"> Watching folder : {input_path}")
    print(f"> Output folder   : {output_path}")
    print(f"> Check interval  : every {WATCH_INTERVAL_SECONDS} seconds")
    print(f"> Supported types : PDF, PNG, JPG, JPEG")
    print(f"> Press Ctrl+C to stop\n")

    processed_count = 0  # Counter for reporting at end of session

    while True:
        try:
            # List only files (not subdirectories) with supported extensions
            files = [
                f for f in input_path.iterdir()
                if f.is_file()                                          # skip directories
                and f.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg']  # only resume formats
            ]

            new_files_found = False

            for file_path in files:
                is_new = process_file(file_path, output_path)
                if is_new:
                    processed_count += 1
                    new_files_found = True  # suppress idle message this cycle

            # Show an idle status indicator when there is nothing new to process
            if not new_files_found:
                print(f"\r> Watching... (processed so far: {processed_count}) | waiting for new files...", end="", flush=True)

            time.sleep(WATCH_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            # Ctrl+C pressed — exit cleanly with a summary
            print(f"\n\n> Watcher stopped safely.")
            print(f"> Total files processed this session: {processed_count}")
            sys.exit(0)

        except Exception as e:
            # Unexpected error — log and keep watching (resilient)
            print(f"\n> [Watcher Error] {e} — retrying in {WATCH_INTERVAL_SECONDS}s...")
            time.sleep(WATCH_INTERVAL_SECONDS)
            continue

# Entry point when run directly: python pdf_to_txt.py
if __name__ == "__main__":
    run_watcher()
