# privacy_setup.py - Silent Ollama Install + Model Pull

import subprocess  # nosec B404
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import ai_mode

_cancelled = False


def _validate_download_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError("Ollama installer downloads must use HTTPS.")

def is_ollama_installed() -> bool:
    """Check if Ollama is already installed and running in the path or local folder."""
    try:
        # Fixed local CLI command.
        result = subprocess.run(  # nosec B603, B607
            ["ollama", "--version"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_model_pulled(model: str) -> bool:
    """Check if the required model is already downloaded."""
    try:
        # Fixed local CLI command.
        result = subprocess.run(  # nosec B603, B607
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10,
        )
        simple_model = model.split(":")[0]
        return simple_model in result.stdout
    except Exception:
        return False


def download_ollama(progress_callback=None):
    """
    Download Ollama installer with progress updates.
    progress_callback(percent, message) — update UI progress bar.
    """
    installer_path = Path("ollama_setup.exe")

    def _report(count, block_size, total):
        global _cancelled
        if _cancelled:
            raise Exception("Cancelled by user")
        if total > 0 and progress_callback:
            percent = min(int(count * block_size * 100 / total), 100)
            progress_callback(percent, f"Downloading Ollama... {percent}%")

    print("> Downloading Ollama...")
    _validate_download_url(ai_mode.OLLAMA_DOWNLOAD_URL)
    # HTTPS URL is validated above.
    urllib.request.urlretrieve(  # nosec B310
        ai_mode.OLLAMA_DOWNLOAD_URL,
        installer_path,
        _report,
    )
    return installer_path


def install_ollama(installer_path: Path, progress_callback=None):
    """Run Ollama installer silently."""
    global _cancelled
    if _cancelled:
        return False
    if progress_callback:
        progress_callback(0, "Installing Ollama (this will run silently)...")

    try:
        subprocess.run([str(installer_path), "/S"], check=True)  # nosec B603
        time.sleep(5)   # give installer time to finish and register service
        return True
    except Exception as e:
        print(f"Error during installation: {e}")
        return False


def run_setup_process(progress_callback=None) -> bool:
    """Run the entire local Ollama install and model pull process."""
    global _cancelled
    _cancelled = False

    try:
        if is_ollama_installed():
            if progress_callback:
                progress_callback(30, "Ollama already installed. Checking model...")
        else:
            if progress_callback:
                progress_callback(10, "Starting Ollama download...")
            inst = download_ollama(progress_callback)
            if progress_callback:
                progress_callback(50, "Installing Ollama silently...")
            ok = install_ollama(inst, progress_callback)
            if not ok:
                return False
            # Clean up installer file
            if inst.exists():
                try:
                    inst.unlink()
                except Exception:
                    pass

        # Now check/pull model
        import config
        model = getattr(config, 'OLLAMA_MODEL', 'llama3.2:3b')
        if is_model_pulled(model):
            if progress_callback:
                progress_callback(100, f"Model {model} already pulled.")
            return True

        if progress_callback:
            progress_callback(60, f"Pulling model {model} (this may take a few minutes)...")

        # Pull model via subprocess
        if _cancelled:
            return False

        subprocess.run(["ollama", "pull", model], check=True)  # nosec B603, B607

        if progress_callback:
            progress_callback(100, f"Model {model} successfully pulled!")
        return True

    except Exception as e:
        print(f"Error during setup: {e}")
        if progress_callback:
            progress_callback(0, f"Failed: {e}")
        return False


def cancel_setup():
    """Cancel the ongoing setup process."""
    global _cancelled
    _cancelled = True
    print("[INFO] Setup cancellation requested.")
