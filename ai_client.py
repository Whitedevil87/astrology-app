import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

try:
    from groq import Groq
    import httpx
    GROQ_SDK_AVAILABLE = True
    HTTPX_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False
    HTTPX_AVAILABLE = False
    Groq = None  # type: ignore
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)


def openai_guru_reply(system: str, user: str) -> Optional[str]:
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    logger.info(f"Chat attempt: groq_key_set={bool(groq_key)}, openai_key_set={bool(openai_key)}")
    if groq_key and GROQ_SDK_AVAILABLE:
        return _groq_chat(system, user, groq_key)
    elif groq_key and not GROQ_SDK_AVAILABLE:
        logger.warning("⚠️  Groq key set but groq SDK not available. Install: pip install groq")
        return _groq_http_fallback(system, user, groq_key)
    if openai_key:
        return _openai_chat(system, user, openai_key)

    logger.error("❌ No API key available (GROQ_API_KEY or OPENAI_API_KEY not set)")
    return None


def _groq_chat(system: str, user: str, api_key: str) -> Optional[str]:
    if not GROQ_SDK_AVAILABLE or Groq is None:
        logger.warning("⚠️ Groq SDK not available, falling back to HTTP")
        return _groq_http_fallback(system, user, api_key)

    try:
        model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.1-8b-instant"
        logger.info(f"🔄 Using Groq SDK with model '{model}'")
        if HTTPX_AVAILABLE:
            try:
                http_client = httpx.Client(trust_env=False)
                client = Groq(api_key=api_key, http_client=http_client)
            except Exception as httpx_err:
                logger.warning(f"⚠️ Could not create explicit httpx client: {httpx_err}. Retrying without it.")
                client = Groq(api_key=api_key)
        else:
            client = Groq(api_key=api_key)

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model,
            temperature=0.65,
            max_tokens=900,
        )

        result = chat_completion.choices[0].message.content.strip()
        logger.info(f"✅ Groq chat success ({len(result)} chars)")
        return result

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        if "model_decommissioned" in error_msg:
            logger.error("❌ Model Decommissioned from Groq - Update GROQ_MODEL env var")
            logger.error("   Current model may be deprecated. Visit: https://console.groq.com/docs/deprecations")
            logger.error("   Try: GROQ_MODEL=llama-3.1-8b-instant or llama-3.3-70b-versatile")
        elif "401" in error_msg or "Unauthorized" in error_msg:
            logger.error("❌ 401 Unauthorized from Groq - Invalid API key")
        elif "403" in error_msg or "Forbidden" in error_msg or "1010" in error_msg:
            logger.error("❌ 403 Forbidden/1010 from Groq - Check API key permissions or try new key")
        elif "429" in error_msg or "Rate limit" in error_msg:
            logger.error("❌ 429 Rate Limited from Groq - Wait before retrying")
        elif "ConnectTimeout" in error_type or "ReadTimeout" in error_type:
            logger.error("❌ Timeout from Groq (60s) - Network issue or service slow")
        else:
            logger.error(f"❌ Groq error: {error_type}: {error_msg[:300]}")
        return None


def _groq_http_fallback(system: str, user: str, api_key: str) -> Optional[str]:
    try:
        model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.1-8b-instant"
        logger.info(f"🔄 Using Groq HTTP fallback with model '{model}'")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.65,
            "max_tokens": 900,
        }

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            response_text = resp.read().decode("utf-8", errors="replace")
            data = json.loads(response_text)

        if "choices" not in data or not data["choices"]:
            logger.error(f"❌ Invalid Groq response structure: {response_text[:300]}")
            return None

        result = str(data["choices"][0]["message"]["content"]).strip()
        logger.info(f"✅ Groq HTTP fallback success ({len(result)} chars)")
        return result

    except urllib.error.HTTPError as e:
        status_code = e.code
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if status_code == 401:
            logger.error("❌ 401 Unauthorized from Groq - Invalid API key")
        elif status_code == 403:
            logger.error("❌ 403 Forbidden from Groq - Check API key permissions")
            if error_body:
                logger.error(f"   Response: {error_body[:200]}")
        elif status_code == 429:
            logger.error("❌ 429 Rate Limited from Groq")
        else:
            logger.error(f"❌ HTTP {status_code} from Groq")
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        logger.error(f"❌ Groq connection error: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"❌ Groq response parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected Groq error: {type(e).__name__}: {e}")
        return None


def _openai_chat(system: str, user: str, api_key: str) -> Optional[str]:
    try:
        model = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
        logger.info(f"🔄 Using OpenAI with model '{model}'")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.65,
            "max_tokens": 900,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        result = str(data["choices"][0]["message"]["content"]).strip()
        logger.info(f"✅ OpenAI chat success ({len(result)} chars)")
        return result
    except urllib.error.HTTPError as e:
        if e.code == 401:
            logger.error("❌ 401 Unauthorized from OpenAI - Invalid API key")
        elif e.code == 429:
            logger.error("❌ 429 Rate Limited from OpenAI")
        else:
            logger.error(f"❌ HTTP {e.code} from OpenAI")
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        logger.error(f"❌ OpenAI connection error: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"❌ OpenAI response parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected OpenAI error: {type(e).__name__}: {e}")
        return None
