"""
src/common.py — Common Utilities & Paths
"""
import os
import sys
from pathlib import Path

APP_NAME = "AI Recruitment System"


def _get_app_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        install_dir = Path(sys.executable).parent
        local_app_data = Path(os.environ.get("LOCALAPPDATA", str(install_dir)))
    else:
        install_dir = Path(__file__).parent.parent
        local_app_data = Path(os.environ.get("LOCALAPPDATA", str(install_dir)))

    primary = local_app_data / APP_NAME
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except Exception:
        fallback = Path.home() / ".ai_recruitment_system"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


if getattr(sys, "frozen", False):
    APP_RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    APP_INSTALL_DIR = Path(sys.executable).parent
else:
    APP_RESOURCE_DIR = Path(__file__).parent.parent
    APP_INSTALL_DIR = Path(__file__).parent.parent

APP_DATA_DIR = _get_app_data_dir()


def resource_path(relative: str) -> Path:
    return APP_RESOURCE_DIR / relative


def install_path(relative: str) -> Path:
    return APP_INSTALL_DIR / relative


def data_path(relative: str) -> Path:
    path = APP_DATA_DIR / "data" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return path



import asyncio
import json
import re
import sys
import time
from pathlib import Path

# Bring ai_mode over if needed
from src.ai_mode import get_app_mode

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

_ollama_client = None

def _ollama():
    global _ollama_client
    if _ollama_client is None:
        import ollama
        _ollama_client = ollama
    return _ollama_client

def _repair_json_string(s: str) -> str:
    return re.sub(r",\s*([\}\]])", r"\1", s)

def clean_json_response(text: str) -> dict:
    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return json.loads(_repair_json_string(text))
        except json.JSONDecodeError:
            try:
                start = text.index("{")
                end   = text.rindex("}") + 1
                json_str = text[start:end]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return json.loads(_repair_json_string(json_str))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"  [WARNING] JSON parse failed: {e}")
                return {}

clean_json = clean_json_response

async def call_ollama_async(system_msg: str, user_msg: str, temperature: float = 0.0, num_predict: int = 2048) -> str:
    import config
    import logging
    logger = logging.getLogger(__name__)
    attempts = getattr(config, "AI_RETRY_ATTEMPTS", 3)
    backoff  = getattr(config, "AI_RETRY_BACKOFF", 2)
    model    = getattr(config, "OLLAMA_MODEL", "llama3.2:3b")

    def _sync_call():
        for attempt in range(1, attempts + 1):
            try:
                response = _ollama().chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": user_msg},
                    ],
                    options={"temperature": temperature, "num_predict": num_predict},
                )
                return response["message"]["content"]
            except Exception as e:
                logger.error(f"  [ERROR] Ollama attempt {attempt}: {e}")
                if attempt < attempts:
                    time.sleep(backoff * attempt)
        return ""
    return await asyncio.get_event_loop().run_in_executor(None, _sync_call)

async def call_cloud_async(system_msg: str, user_msg: str, max_tokens: int = 2048) -> str:
    import config
    cloud_enabled = getattr(config, "CLOUD_ENABLED", False)
    cloud_model   = getattr(config, "CLOUD_MODEL", "claude-3-5-haiku-latest")
    anthropic_key = getattr(config, "ANTHROPIC_KEY", "")

    if not ANTHROPIC_AVAILABLE or not cloud_enabled:
        return ""
    client = anthropic.AsyncAnthropic(api_key=anthropic_key)
    msg = await client.messages.create(
        model=cloud_model,
        max_tokens=max_tokens,
        system=system_msg,
        messages=[{"role": "user", "content": user_msg}]
    )
    return msg.content[0].text

async def call_ai_async(system_msg: str, user_msg: str, temperature: float = 0.0, num_predict: int = 2048, local_timeout: float = 45.0) -> str:
    import logging
    logger = logging.getLogger(__name__)
    mode = get_app_mode()
    if mode == "privacy":
        try:
            return await asyncio.wait_for(
                call_ollama_async(system_msg, user_msg, temperature, num_predict),
                timeout=local_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"  [WARNING] Local Ollama call timed out ({local_timeout}s).")
            import config
            cloud_enabled = getattr(config, "CLOUD_ENABLED", False)
            anthropic_key = getattr(config, "ANTHROPIC_KEY", "")
            if cloud_enabled and ANTHROPIC_AVAILABLE and anthropic_key and anthropic_key != 'sk-ant-...':
                logger.info("  [INFO] Attempting Cloud Fallback (Anthropic) because local Ollama timed out...")
                try:
                    return await call_cloud_async(system_msg, user_msg, num_predict)
                except Exception as ce:
                    logger.error(f"  [ERROR] Cloud fallback failed: {ce}")
            return ""
        except Exception as e:
            logger.error(f"  [ERROR] Local Ollama call failed: {e}")
            import config
            cloud_enabled = getattr(config, "CLOUD_ENABLED", False)
            anthropic_key = getattr(config, "ANTHROPIC_KEY", "")
            if cloud_enabled and ANTHROPIC_AVAILABLE and anthropic_key and anthropic_key != 'sk-ant-...':
                logger.info("  [INFO] Attempting Cloud Fallback (Anthropic) due to local failure...")
                try:
                    return await call_cloud_async(system_msg, user_msg, num_predict)
                except Exception as ce:
                    logger.error(f"  [ERROR] Cloud fallback failed: {ce}")
            return ""
    else:
        from src.provider_router import router
        return await router.call(system_msg, user_msg, max_tokens=num_predict)

def call_ollama(system_msg: str, user_msg: str, temperature: float = 0.0, num_predict: int = 2048) -> str:
    import logging
    logger = logging.getLogger(__name__)
    try:
        return asyncio.run(call_ai_async(system_msg, user_msg, temperature, num_predict))
    except RuntimeError as e:
        err_str = str(e)
        if "cannot be called when another event loop is running" in err_str:
            import config as _cfg
            attempts = getattr(_cfg, "AI_RETRY_ATTEMPTS", 3)
            backoff  = getattr(_cfg, "AI_RETRY_BACKOFF", 2)
            model    = getattr(_cfg, "OLLAMA_MODEL", "llama3.2:3b")
            for attempt in range(1, attempts + 1):
                try:
                    response = _ollama().chat(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user",   "content": user_msg},
                        ],
                        options={"temperature": temperature, "num_predict": num_predict},
                    )
                    return response["message"]["content"]
                except Exception as se:
                    logger.error(f"  [ERROR] Ollama attempt {attempt}: {se}")
                    if attempt < attempts:
                        time.sleep(backoff * attempt)
            return ""
        logger.error(f"  [ERROR] AI call failed: {err_str}")
        return ""
    except Exception as e:
        logger.error(f"  [ERROR] call_ollama unexpected error: {e}")
        return ""
