#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================
 بوت تلغرام للذكاء الاصطناعي - جميع موديلات OpenRouter المجانية
==========================================================================
المميزات:
  • يجلب كل الموديلات المجانية تلقائياً من OpenRouter (السعر = 0 أو :free)
  • أقسام (أزرار): محادثة، برمجة، استدلال، رؤية/صور، توليد صور، صوت،
    سياق طويل، أدوات، خفيفة، كبيرة، الأحدث، + تصفح حسب الشركة
  • زر 🔄 تحديث الموديلات: يكتشف الموديلات الجديدة/المحذوفة ويعرضها
  • تحديث تلقائي دوري + إشعار للأدمن عند نزول موديلات جديدة
  • ذاكرة محادثة لكل مستخدم + System Prompt مخصص
  • دعم إرسال الصور (للموديلات التي تدعم الرؤية) وملفات نصية/كود
  • دعم الموديلات التي تولّد صوراً
  • إعادة محاولة تلقائية عند الضغط (429) + حل مشكلة الموديلات
    التي لا تدعم system prompt
  • بحث بالاسم: /search اسم
  • 🛡 لوحة تحكم أدمن كاملة (/admin): إحصائيات، إدارة المستخدمين (حظر/حدود/مراسلة)،
    بث جماعي، إدارة الموديلات والأقسام، إعدادات (صيانة/وضع خاص/اشتراك إجباري)،
    مشرفون، سجل أخطاء، نسخ احتياطي وتصدير CSV
  • 🧭 مزوّد ثانٍ: Conduit (يعمل جنباً إلى جنب مع OpenRouter، بزر منفصل لموديلاته)
  • 🎖 نظام فئات: مستخدم عادي/مميز بحدود يومية مختلفة، ترقية من الأدمن فقط
  • 🎁 نظام دعوات ونقاط: رابط دعوة شخصي، نقاط تتحوّل لرسائل إضافية تلقائياً
  • 🌐 لوحة تحكم ويب كاملة (اختيارية): تسجيل دخول بكلمة مرور، إحصائيات حيّة،
    إدارة مستخدمين وموديلات وبث وإعدادات، فحص صحة المزوّدين، تجربة موديل مباشرة،
    نسخ احتياطي وتصدير CSV — كل ذلك بدون لمس تلغرام

التثبيت:
    pip install "python-telegram-bot[job-queue]>=20.7" httpx aiohttp

التشغيل:
    ضع TELEGRAM_BOT_TOKEN و OPENROUTER_API_KEY (وCONDUIT_API_KEY إن رغبت)
    وWEB_PASSWORD لتفعيل لوحة الويب، كلها في أعلى الملف (أو كمتغيرات بيئة)
    ثم:  python openrouter_free_bot.py
    ثم افتح لوحة الويب على: http://127.0.0.1:8080 (أو المضيف/المنفذ الذي حددته)
==========================================================================
"""

import asyncio
import base64
import copy
import csv
import hashlib
import hmac
import io
import json
import logging
import math
import os
import re
import secrets
import sys
import time
import zipfile
from datetime import datetime, timedelta
from html import escape as esc
from pathlib import Path

import httpx
from telegram import BotCommand, BotCommandScopeChat, InlineKeyboardButton as B, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==========================================================================
#                              الإعدادات
# ==========================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# مزوّد إضافي: Conduit (conduit.ozdoev.net) - بوابة متوافقة مع OpenAI API.
# اترك المفتاح كما هو (يحتوي "ضع_") لتعطيل هذا المزوّد كلياً.
# إن كان مسار الـ API عند هذا الموقع مختلفاً عن /v1 المعتاد، عدّل CONDUIT_BASE_URL.
CONDUIT_API_KEY = os.getenv("CONDUIT_API_KEY", "")
CONDUIT_BASE_URL = os.getenv("CONDUIT_BASE_URL", "https://conduit.ozdoev.net/v1")

# لوحة تحكم عبر الويب (اختيارية) — تحتاج: pip install aiohttp
# ضع كلمة مرور قوية (10+ حرفاً عشوائياً) لتفعيلها؛ اتركها كما هي لتعطيلها.
WEB_ENABLED = True
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")   # استخدم 0.0.0.0 فقط خلف بروكسي HTTPS موثوق
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "AbodSh12??")
WEB_TRUST_PROXY = False   # فعّلها فقط إذا كانت خلف Nginx/Caddy بـ HTTPS حقيقي
WEB_COOKIE_SECURE = False  # اجعلها True عند التشغيل خلف HTTPS

# معرفات المالكين (Owners): لهم كل الصلاحيات ويضيفون مشرفين آخرين من اللوحة.
# لمعرفة معرفك أرسل /id للبوت بعد تشغيله. مثال: [123456789]
# (الوضع الخاص وحظر المستخدمين وغيرها تُدار الآن من /admin)
ADMIN_IDS: list[int] = [7112459295]

AUTO_REFRESH_HOURS = 6          # كل كم ساعة يتحدث قائمة الموديلات تلقائياً (0 = تعطيل)
PAGE_SIZE = 8                   # عدد الموديلات في كل صفحة
PROVIDERS_PAGE_SIZE = 16        # عدد الشركات في كل صفحة
MAX_HISTORY = 20                # عدد رسائل الذاكرة لكل مستخدم
REQUEST_TIMEOUT = 180           # مهلة الطلب بالثواني
NEW_MODEL_DAYS = 30             # قسم "الأحدث": موديلات آخر كم يوم
MAX_DOC_BYTES = 200_000         # أقصى حجم ملف نصي

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, accurate AI assistant. "
    "Always reply in the same language the user writes in."
)

# موديلات مفضلة تُختار افتراضياً (أول واحد موجود)
PREFERRED_DEFAULTS = [
    "openrouter/free",
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-235b-a22b:free",
    "google/gemini-2.0-flash-exp:free",
]

OR_BASE = "https://openrouter.ai/api/v1"
DATA_DIR = Path(__file__).resolve().parent
CACHE_FILE = DATA_DIR / "models_cache.json"
USERS_FILE = DATA_DIR / "users.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
STATS_FILE = DATA_DIR / "stats.json"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("or-bot")

http: httpx.AsyncClient | None = None


# ==========================================================================
#                          أدوات مساعدة
# ==========================================================================
def or_headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/openrouter_free_bot",
        "X-Title": "OpenRouter Free Telegram Bot",
    }


def conduit_headers() -> dict:
    return {"Authorization": f"Bearer {CONDUIT_API_KEY}", "Content-Type": "application/json"}


def conduit_enabled() -> bool:
    return bool(CONDUIT_API_KEY) and "ضع_" not in CONDUIT_API_KEY


SRC_LABEL = {"or": "🆓 OpenRouter", "cd": "🧭 Conduit"}
SRC_ICON = {"or": "🆓", "cd": "🧭"}

# ---------------------- مزوّدون إضافيون (يُضافون من لوحة التحكم) ----------------------
# provider_type لكل مزوّد مخصّص: "openai_compatible" (رابط Base URL + Bearer، الافتراضي)
# أو "gemini" (Gemini Native API: x-goog-api-key، بدون Authorization: Bearer)
KNOWN_PROVIDERS = [  # قوائم جاهزة للإضافة السريعة من اللوحة — الأدمن يضع مفتاحه فقط
    {"name": "Groq", "base_url": "https://api.groq.com/openai/v1", "icon": "⚡", "provider_type": "openai_compatible",
     "note": "استدلال فائق السرعة، فيه موديلات مجانية بدون بطاقة ائتمان"},
    {"name": "Cerebras", "base_url": "https://api.cerebras.ai/v1", "icon": "🧠", "provider_type": "openai_compatible",
     "note": "حصة مجانية يومية سخية، بدون بطاقة ائتمان"},
    {"name": "Mistral", "base_url": "https://api.mistral.ai/v1", "icon": "🌬️", "provider_type": "openai_compatible",
     "note": "فئة Experiment المجانية (فعّلها من console.mistral.ai)"},
    {"name": "Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta", "icon": "✨",
     "provider_type": "gemini", "note": "Google AI Studio — مفتاح مجاني من aistudio.google.com/apikey"},
]


def custom_providers() -> list[dict]:
    return settings["providers"]


def provider_by_id(pid: str) -> dict | None:
    return next((p for p in settings["providers"] if p["id"] == pid), None)


def detect_provider_type(base_url: str) -> str:
    """تخمين نوع المزوّد من رابطه عندما لا يُحدَّد صراحة (متوافقة مع السجلات القديمة قبل هذا الحقل)."""
    return "gemini" if "generativelanguage.googleapis.com" in (base_url or "") else "openai_compatible"


def provider_type_of(p: dict) -> str:
    return p.get("provider_type") or detect_provider_type(p.get("base_url", ""))


def provider_headers(p: dict) -> dict:
    """رؤوس OpenAI-compatible (Bearer). لا تُستخدم مع مزوّدي Gemini — استخدم gemini_headers بدلاً منها."""
    return {"Authorization": f"Bearer {p['api_key']}", "Content-Type": "application/json"}


def gemini_headers(p: dict) -> dict:
    """رؤوس Gemini Native API: x-goog-api-key فقط، بلا Authorization: Bearer إطلاقاً."""
    return {"x-goog-api-key": p["api_key"], "Content-Type": "application/json"}


def gen_provider_id() -> str:
    existing = {p["id"] for p in settings["providers"]}
    while True:
        pid = "cp_" + secrets.token_hex(4)
        if pid not in existing:
            return pid


def mask_key(k: str) -> str:
    k = k or ""
    if len(k) <= 8:
        return "•" * len(k)
    return k[:4] + "…" + k[-4:]


def all_sources() -> list[tuple[str, str, str]]:
    """كل مصادر الموديلات النشطة: (src, name, icon) — المدمجة ثم المخصّصة."""
    out = [("or", "OpenRouter", "🆓")]
    if conduit_enabled():
        out.append(("cd", "Conduit", "🧭"))
    for p in settings["providers"]:
        if p.get("enabled", True):
            out.append((p["id"], p["name"], p.get("icon", "🔌")))
    return out


def src_label(src: str) -> str:
    if src in SRC_LABEL:
        return SRC_LABEL[src]
    p = provider_by_id(src)
    return f"{p.get('icon', '🔌')} {p['name']}" if p else src


def src_icon(src: str) -> str:
    if src in SRC_ICON:
        return SRC_ICON[src]
    p = provider_by_id(src)
    return p.get("icon", "🔌") if p else "🔌"


def extra_src_total(counts: dict) -> int:
    return sum(v for k, v in counts.items() if k not in ("or", "cd"))


def default_prov_name(src: str) -> str:
    if src == "or":
        return "openrouter"
    if src == "cd":
        return "conduit"
    p = provider_by_id(src)
    return (p["name"] if p else src).lower()


def md5s(s: str, n: int = 10) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:n]


def fmt_ctx(n: int) -> str:
    if not n:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def short_name(m: dict, limit: int = 42) -> str:
    name = re.sub(r"\s*\(free\)\s*", "", m["name"] or m.get("raw_id") or m["id"], flags=re.I).strip()
    return name if len(name) <= limit else name[: limit - 1] + "…"


def split_text(text: str, limit: int = 4000) -> list[str]:
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


async def safe_edit(query, text: str, markup=None):
    try:
        await query.edit_message_text(
            text, reply_markup=markup, parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ==========================================================================
#                  تحديد الموديلات المجانية + تصنيفها
# ==========================================================================
def is_free(m: dict) -> bool:
    mid = m.get("id", "")
    p = m.get("pricing") or {}
    if mid.endswith(":free"):
        return True
    if p.get("prompt") is None or p.get("completion") is None:
        return False
    try:
        vals = [float(p.get(k) or 0) for k in ("prompt", "completion", "request", "image")]
    except (TypeError, ValueError):
        return False
    return all(v == 0 for v in vals)


def normalize(m: dict, src: str = "or") -> dict:
    """يحوّل رد أي مزوّد (OpenRouter أو Conduit، كلاهما بصيغة OpenAI) إلى شكل موحّد.
    src: 'or' = OpenRouter، 'cd' = Conduit."""
    arch = m.get("architecture") or {}
    ins = arch.get("input_modalities")
    outs = arch.get("output_modalities")
    if not ins or not outs:  # صيغة قديمة مثل "text+image->text"، أو موديل OpenAI-compatible بسيط
        modality = arch.get("modality") or "text->text"
        left, _, right = modality.partition("->")
        ins = ins or [x for x in left.split("+") if x] or ["text"]
        outs = outs or [x for x in right.split("+") if x] or ["text"]
    rid = m["id"]
    prov = rid.split("/", 1)[0] if "/" in rid else default_prov_name(src)
    return {
        "id": f"{src}::{rid}",   # معرّف داخلي فريد (يُستخدم للتخزين/الأزرار)
        "raw_id": rid,           # المعرّف الحقيقي الذي يُرسل لواجهة المزوّد
        "src": src,
        "prov": prov,
        "name": m.get("name") or rid,
        "context": m.get("context_length") or m.get("context_window") or 0,
        "created": m.get("created") or 0,
        "in": list(ins),
        "out": list(outs),
        "params": list(m.get("supported_parameters") or []),
        "desc": (m.get("description") or "").strip()[:400],
        "call_mode": None,  # None = استدعاء OpenAI-compatible عادي عبر /chat/completions
    }


def normalize_gemini(m: dict, src: str) -> dict:
    """يحوّل رد Gemini Native (GET .../v1beta/models) إلى نفس الشكل الموحّد.
    شكل رد Gemini مختلف تماماً عن OpenAI: المفتاح "models" لا "data"، والمعرّف "models/xxx"،
    ولا يوجد context_length بل inputTokenLimit، ولا pricing إطلاقاً."""
    name_path = m.get("name", "")  # "models/gemini-1.5-pro"
    rid = name_path.split("/", 1)[-1] if "/" in name_path else name_path
    methods = m.get("supportedGenerationMethods") or m.get("supportedActions") or []
    # generateContent هو المسار القياسي؛ أي موديل لا يدعمه صراحة نعتبره يحتاج Interactions API
    call_mode = "generateContent" if "generateContent" in methods else "interactions"
    ins = ["text", "image"] if call_mode == "generateContent" else ["text"]
    return {
        "id": f"{src}::{rid}",
        "raw_id": rid,
        "src": src,
        "prov": default_prov_name(src),
        "name": m.get("displayName") or rid,
        "context": m.get("inputTokenLimit") or 0,
        "created": 0,
        "in": ins,
        "out": ["text"],
        "params": [],
        "desc": (m.get("description") or "").strip()[:400],
        "call_mode": call_mode,
    }


_SIZE_RE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)b(?![a-z])", re.I)


def size_b(m: dict) -> float:
    found = [float(x) for x in _SIZE_RE.findall(m["raw_id"])]
    return max(found) if found else 0.0


def has_kw(m: dict, kws) -> bool:
    s = (m["raw_id"] + " " + m["name"]).lower()
    return any(k in s for k in kws)


def is_text_out(m):  # موديلات تنتج نصاً
    return "text" in m["out"]


CATEGORIES = [
    ("all", "🌐 الكل", lambda m: True),
    ("new", f"🆕 الأحدث ({NEW_MODEL_DAYS} يوم)",
     lambda m: bool(m["created"]) and time.time() - m["created"] <= NEW_MODEL_DAYS * 86400),
    ("chat", "💬 محادثة عامة", lambda m: is_text_out(m)),
    ("code", "👨‍💻 برمجة",
     lambda m: has_kw(m, ("coder", "code", "devstral", "codestral", "deepcoder", "kat-dev"))
     or "coding" in m["desc"].lower() or "programming" in m["desc"].lower()),
    ("reason", "🧠 استدلال وتفكير",
     lambda m: "reasoning" in m["params"] or "include_reasoning" in m["params"]
     or has_kw(m, ("-r1", "reason", "thinking", "qwq", "think"))),
    ("vision", "👁️ رؤية وتحليل صور", lambda m: "image" in m["in"]),
    ("imggen", "🎨 توليد صور", lambda m: "image" in m["out"]),
    ("audio", "🎧 صوت", lambda m: "audio" in m["in"] or "audio" in m["out"]),
    ("long", "📚 سياق طويل (128K+)", lambda m: m["context"] >= 128_000),
    ("tools", "🛠️ أدوات / Function Calling", lambda m: "tools" in m["params"]),
    ("small", "⚡ خفيفة وسريعة",
     lambda m: 0 < size_b(m) <= 9 or has_kw(m, ("mini", "small", "nano", "lite", "flash"))),
    ("big", "🏋️ كبيرة وقوية (30B+)", lambda m: size_b(m) >= 30),
]
CAT_FN = {k: fn for k, _, fn in CATEGORIES}
CAT_LABEL = {k: label for k, label, _ in CATEGORIES}


def provider_of(m: dict) -> str:
    return m["prov"]


class ModelStore:
    def __init__(self):
        self.models: dict[str, dict] = {}
        self.by_hash: dict[str, str] = {}
        self.updated_at: float = 0
        self.lock = asyncio.Lock()

    # ---- تخزين ----
    def _set(self, models: dict):
        self.models = models
        self.by_hash = {md5s(i): i for i in models}
        self.updated_at = time.time()

    def load_cache(self):
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            self._set(data["models"])
            self.updated_at = data.get("updated_at", 0)
            log.info("Loaded %d models from cache", len(self.models))
        except Exception:
            pass

    def save_cache(self):
        try:
            CACHE_FILE.write_text(
                json.dumps({"updated_at": self.updated_at, "models": self.models},
                           ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Cache save failed: %s", e)

    # ---- جلب من كل المزوّدين ----
    async def refresh(self) -> dict:
        async with self.lock:
            fresh: dict[str, dict] = {}
            errors: list[str] = []

            # ---- OpenRouter (الموديلات المجانية + المضافة يدوياً) ----
            try:
                r = await http.get(f"{OR_BASE}/models", headers=or_headers(),
                                   params={"output_modalities": "all"})
                if r.status_code >= 400:  # احتياط لو لم يدعم البارامتر
                    r = await http.get(f"{OR_BASE}/models", headers=or_headers())
                r.raise_for_status()
                raw = r.json().get("data", [])
                extra_ids = set(settings["extra_models"])
                for m in raw:
                    if m.get("id") and (is_free(m) or m["id"] in extra_ids):
                        nm = normalize(m, "or")
                        fresh[nm["id"]] = nm
            except Exception as e:
                errors.append(f"OpenRouter: {e}")

            # ---- Conduit ----
            if conduit_enabled():
                try:
                    r = await http.get(f"{CONDUIT_BASE_URL}/models", headers=conduit_headers())
                    r.raise_for_status()
                    raw = r.json().get("data", [])
                    for m in raw:
                        if m.get("id"):
                            nm = normalize(m, "cd")
                            fresh[nm["id"]] = nm
                except Exception as e:
                    errors.append(f"Conduit: {e}")

            # ---- مزوّدون مخصّصون (يُضافون من لوحة التحكم) ----
            for p in list(settings["providers"]):
                if not p.get("enabled", True):
                    continue
                try:
                    if provider_type_of(p) == "gemini":
                        # Gemini Native: GET {base}/models برأس x-goog-api-key، والرد بمفتاح "models" لا "data"
                        r = await http.get(f"{p['base_url'].rstrip('/')}/models", headers=gemini_headers(p))
                        r.raise_for_status()
                        raw = r.json().get("models", [])
                        for m in raw:
                            if m.get("name"):
                                nm = normalize_gemini(m, p["id"])
                                fresh[nm["id"]] = nm
                    else:
                        r = await http.get(f"{p['base_url'].rstrip('/')}/models", headers=provider_headers(p))
                        r.raise_for_status()
                        raw = r.json().get("data", [])
                        for m in raw:
                            if m.get("id"):
                                nm = normalize(m, p["id"])
                                fresh[nm["id"]] = nm
                except Exception as e:
                    errors.append(f"{p['name']}: {e}")

            if not fresh:
                raise RuntimeError(" | ".join(errors) or "لم يتم العثور على أي موديل.")
            old_ids = set(self.models)
            added = sorted(set(fresh) - old_ids) if old_ids else []
            removed = sorted(old_ids - set(fresh)) if old_ids else []
            self._set(fresh)
            self.save_cache()
            return {
                "added": [fresh[i] for i in added],
                "removed": list(removed),
                "total": len(fresh),
                "first_load": not old_ids,
                "errors": errors,
            }

    # ---- استعلامات ----
    def sorted_models(self, models):
        return sorted(models, key=lambda m: (-(m["created"] or 0), m["name"].lower()))

    def providers(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for m in self.visible():
            out.setdefault(provider_of(m), []).append(m)
        return out

    def category_models(self, key: str) -> list[dict]:
        if key.startswith("p_"):
            h = key[2:]
            ms = [m for m in self.visible() if md5s(provider_of(m), 8) == h]
        elif key.startswith("src_"):
            src = key[4:]
            ms = [m for m in self.visible() if m["src"] == src]
        else:
            fn = CAT_FN.get(key)
            ms = [m for m in self.visible() if fn and fn(m)]
        return self.sorted_models(ms)

    def provider_name_by_key(self, key: str) -> str:
        h = key[2:]
        for p in self.providers():
            if md5s(p, 8) == h:
                return p
        return "?"

    def visible(self) -> list[dict]:
        hid = set(settings["hidden_models"])
        return [m for m in self.models.values() if m["id"] not in hid]

    def default_model(self) -> str | None:
        d = settings["default_model"]
        if d and d in self.models and not settings.is_hidden(d):
            return d
        for p in PREFERRED_DEFAULTS:
            comp = f"or::{p}"
            if comp in self.models and not settings.is_hidden(comp):
                return comp
        chat = [m for m in self.visible() if m["src"] == "or" and is_text_out(m) and "image" not in m["out"]]
        if chat:
            return max(chat, key=lambda m: m["context"])["id"]
        vis = self.visible()
        return vis[0]["id"] if vis else None

    def models_count_by_src(self) -> dict:
        out = {"or": 0, "cd": 0}
        for m in self.visible():
            out[m["src"]] = out.get(m["src"], 0) + 1
        return out

    def search(self, q: str) -> list[dict]:
        q = q.lower().strip()
        res = [m for m in self.visible() if q in m["raw_id"].lower() or q in m["name"].lower()]
        return self.sorted_models(res)


store = ModelStore()


# ==========================================================================
#                      بيانات المستخدمين والذاكرة
# ==========================================================================
def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data):
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        log.warning("Save %s failed: %s", path.name, e)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""


def fmt_dt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "—"


_bg_tasks: set = set()


def spawn(coro):
    """تشغيل مهمة في الخلفية مع منع حذفها من الذاكرة."""
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)
    return t


# ---------------------- إعدادات البوت (تُدار من لوحة الأدمن) ----------------------
SETTINGS_DEFAULT = {
    "maintenance": False,
    "maintenance_msg": "🛠 البوت تحت الصيانة حالياً، عاود المحاولة لاحقاً.",
    "private_mode": False,          # true = لا يستخدم البوت إلا المسموح لهم
    "welcome_text": "",
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "default_model": None,
    "limit_normal": 30,              # الحد اليومي للمستخدم العادي (0 = بلا حد)
    "limit_premium": 500,            # الحد اليومي للمستخدم المميز (0 = بلا حد)
    "ref_points": 10,                # نقاط/رسائل إضافية لكل شخص يُدعى بنجاح
    "premium_models": [],            # موديلات حصرية للمميزين فقط
    "providers": [],                 # مزوّدون إضافيون مُضافون من لوحة التحكم (OpenAI-compatible)
    "history_len": MAX_HISTORY,
    "force_sub": "",                # قناة الاشتراك الإجباري
    "force_sub_link": "",
    "allow_images": True,
    "allow_files": True,
    "notify_new_models": True,
    "notify_new_users": False,
    "hidden_models": [],
    "hidden_cats": [],
    "extra_models": [],
    "admins": [],
    "ban_msg": "🚫 تم حظرك من استخدام هذا البوت.",
}


class SettingsStore:
    def __init__(self):
        self.data = copy.deepcopy(SETTINGS_DEFAULT)
        self.data.update(_load_json(SETTINGS_FILE, {}))

    def __getitem__(self, k):
        return self.data.get(k, copy.deepcopy(SETTINGS_DEFAULT.get(k)))

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        _save_json(SETTINGS_FILE, self.data)

    def is_hidden(self, mid: str) -> bool:
        return mid in self.data["hidden_models"]

    def toggle_in(self, key: str, item) -> bool:
        lst = self.data.setdefault(key, [])
        if item in lst:
            lst.remove(item)
            state = False
        else:
            lst.append(item)
            state = True
        self.save()
        return state


# ---------------------- إحصائيات ----------------------
class StatsStore:
    def __init__(self):
        self.data = self._fresh()
        self.data.update(_load_json(STATS_FILE, {}))
        self.dirty = False
        self.last_save = 0.0

    @staticmethod
    def _fresh() -> dict:
        return {"total_msgs": 0, "total_tokens": 0, "total_errors": 0,
                "models": {}, "daily": {}, "errors": []}

    def reset(self):
        self.data.clear()
        self.data.update(self._fresh())
        self.flush(True)

    def record(self, model_id: str, tokens: int):
        d = self.data
        d["total_msgs"] += 1
        d["total_tokens"] += tokens
        d["models"][model_id] = d["models"].get(model_id, 0) + 1
        day = d["daily"].setdefault(today_str(), {"msgs": 0, "tokens": 0})
        day["msgs"] += 1
        day["tokens"] += tokens
        if len(d["daily"]) > 45:
            for k in sorted(d["daily"])[:-45]:
                del d["daily"][k]
        self.mark()

    def add_error(self, model_id: str, status, msg: str):
        d = self.data
        d["total_errors"] += 1
        d["errors"].append({"t": time.time(), "model": model_id, "status": status, "msg": (msg or "")[:300]})
        d["errors"] = d["errors"][-50:]
        self.mark()

    def mark(self):
        self.dirty = True
        self.flush()

    def flush(self, force: bool = False):
        if self.dirty and (force or time.time() - self.last_save > 15):
            _save_json(STATS_FILE, self.data)
            self.dirty = False
            self.last_save = time.time()


# ---------------------- المستخدمون ----------------------
USER_DEFAULTS = {
    "model": None, "system": None, "first_name": "", "username": "",
    "joined": 0, "last_seen": 0, "msg_count": 0, "tokens": 0,
    "day": "", "day_count": 0, "banned": False, "ban_reason": "",
    "allowed": False, "limit": None, "blocked_bot": False,
    "tier": "normal",           # "normal" أو "premium" (تُرقّى من الأدمن فقط)
    "points": 0,                # نقاط/رسائل إضافية من نظام الدعوة
    "invited_by": None,         # معرّف من دعاه لهذا البوت
    "referrals": 0,             # عدد من دعاهم هذا المستخدم بنجاح
    "referral_claimed": False,  # هل احتُسبت دعوته لصالح الداعي (مرة واحدة فقط)
}


class UserStore:
    def __init__(self):
        self.data: dict[str, dict] = _load_json(USERS_FILE, {})
        self.dirty = False
        self.last_save = 0.0

    def get(self, uid: int) -> dict:
        u = self.data.setdefault(str(uid), {})
        for k, v in USER_DEFAULTS.items():
            u.setdefault(k, v)
        return u

    def exists(self, uid: int) -> bool:
        return str(uid) in self.data

    def touch(self, tg_user) -> tuple[dict, bool]:
        is_new = str(tg_user.id) not in self.data
        u = self.get(tg_user.id)
        if is_new or not u["joined"]:
            u["joined"] = time.time()
        u["first_name"] = tg_user.full_name or tg_user.first_name or ""
        u["username"] = tg_user.username or ""
        u["last_seen"] = time.time()
        u["blocked_bot"] = False
        self.mark()
        return u, is_new

    def bump(self, uid: int, tokens: int = 0):
        u = self.get(uid)
        t = today_str()
        if u["day"] != t:
            u["day"], u["day_count"] = t, 0
        u["day_count"] += 1
        u["msg_count"] += 1
        u["tokens"] += tokens
        self.mark()

    def used_today(self, uid: int) -> int:
        u = self.get(uid)
        return u["day_count"] if u["day"] == today_str() else 0

    def all(self) -> list[tuple[int, dict]]:
        return [(int(k), self.get(int(k))) for k in list(self.data)]

    def find(self, q: str) -> list[tuple[int, dict]]:
        q = q.strip().lower().lstrip("@")
        if not q:
            return []
        if q.lstrip("-").isdigit():
            return [(int(q), self.get(int(q)))] if self.exists(int(q)) else []
        res = [(uid, u) for uid, u in self.all()
               if q in (u["username"] or "").lower() or q in (u["first_name"] or "").lower()]
        return sorted(res, key=lambda x: -x[1]["last_seen"])

    def filtered(self, kind: str) -> list[tuple[int, dict]]:
        us, now, t = self.all(), time.time(), today_str()
        if kind == "act":
            us = [x for x in us if now - x[1]["last_seen"] < 86400]
        elif kind == "new":
            us = [x for x in us if day_of(x[1]["joined"]) == t]
        elif kind == "ban":
            us = [x for x in us if x[1]["banned"]]
        elif kind == "alw":
            us = [x for x in us if x[1]["allowed"]]
        elif kind == "prem":
            us = [x for x in us if x[1]["tier"] == "premium"]
        return sorted(us, key=lambda x: -x[1]["last_seen"])

    def save(self):
        _save_json(USERS_FILE, self.data)
        self.dirty = False
        self.last_save = time.time()

    def mark(self):
        self.dirty = True
        if time.time() - self.last_save > 15:
            self.save()

    def flush(self, force: bool = False):
        if self.dirty and (force or time.time() - self.last_save > 15):
            self.save()


settings = SettingsStore()
stats = StatsStore()
users = UserStore()
histories: dict[int, list[dict]] = {}
user_locks: dict[int, asyncio.Lock] = {}


def user_lock(uid: int) -> asyncio.Lock:
    return user_locks.setdefault(uid, asyncio.Lock())


def is_owner(uid: int) -> bool:
    return uid in ADMIN_IDS


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS or uid in [int(x) for x in settings["admins"]]


def all_admin_ids() -> list[int]:
    return list(dict.fromkeys(list(ADMIN_IDS) + [int(x) for x in settings["admins"]]))


def current_model(uid: int) -> str | None:
    m = users.get(uid)["model"]
    return m if m in store.models and not settings.is_hidden(m) else None


def effective_system(uid: int) -> str:
    s = users.get(uid)["system"]
    if s and s != DEFAULT_SYSTEM_PROMPT:
        return s
    return settings["system_prompt"] or DEFAULT_SYSTEM_PROMPT


# ==========================================================================
#                             لوحات الأزرار
# ==========================================================================
def src_title(key: str) -> str | None:
    if not key.startswith("src_"):
        return None
    src = key[4:]
    name = {"or": "OpenRouter", "cd": "Conduit"}.get(src) or (provider_by_id(src) or {}).get("name", src)
    return f"{src_icon(src)} موديلات {name}"


def main_menu_text(uid: int) -> str:
    cur = current_model(uid)
    upd = datetime.fromtimestamp(store.updated_at).strftime("%Y-%m-%d %H:%M") if store.updated_at else "—"
    cur_txt = f"<code>{esc(store.models[cur]['raw_id'])}</code>" if cur else "الافتراضي (يُختار تلقائياً)"
    counts = store.models_count_by_src()
    rec = users.get(uid)
    tier_txt = "⭐ مميز" if rec["tier"] == "premium" else "👤 عادي"
    return (
        "🤖 <b>بوت الذكاء الاصطناعي — OpenRouter + Conduit</b>\n\n"
        f"📦 الموديلات المتاحة: <b>{len(store.visible())}</b> "
        f"(🆓 {counts.get('or', 0)} · 🧭 {counts.get('cd', 0)}"
        f"{' · 🔌 ' + str(extra_src_total(counts)) if extra_src_total(counts) else ''})\n"
        f"🕒 آخر تحديث: {upd}\n"
        f"👤 فئتك: {tier_txt}\n"
        f"✅ الموديل الحالي: {cur_txt}\n\n"
        "اختر قسماً لعرض موديلاته، ثم اضغط على الموديل لاختياره.\n"
        "بعدها أرسل أي رسالة وسيرد عليك 💬"
    )


def kb_main() -> InlineKeyboardMarkup:
    rows, row = [], []
    hidden_cats = set(settings["hidden_cats"])
    for key, label, _ in CATEGORIES:
        if key in hidden_cats:
            continue
        n = len(store.category_models(key))
        if n == 0 and key != "all":
            continue
        row.append(B(f"{label} ({n})", callback_data=f"c:{key}:0"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    counts = store.models_count_by_src()
    src_row, buf = [], []
    for src, name, icon in all_sources():
        n = counts.get(src, 0)
        if not n:
            continue
        buf.append(B(f"{icon} {name} فقط ({n})", callback_data=f"c:src_{src}:0"))
        if len(buf) == 2:
            src_row.append(buf)
            buf = []
    if buf:
        src_row.append(buf)
    rows.extend(src_row)
    rows.append([B(f"🏢 حسب الشركة ({len(store.providers())})", callback_data="pl:0")])
    rows.append([
        B("🎁 دعوة أصدقاء", callback_data="invite"),
        B("🗑️ محادثة جديدة", callback_data="new"),
    ])
    rows.append([B("🔄 تحديث الموديلات", callback_data="refresh")])
    return InlineKeyboardMarkup(rows)


def model_label(m: dict, cur: str | None) -> str:
    tick = "✅ " if m["id"] == cur else ""
    extra = src_icon(m["src"])
    if "image" in m["in"]:
        extra += "👁"
    if "image" in m["out"]:
        extra += "🎨"
    if m["id"] in settings["premium_models"]:
        extra += "⭐"
    return f"{tick}{short_name(m)} · {fmt_ctx(m['context'])} {extra}".strip()


def view_category(key: str, page: int, uid: int):
    models = store.category_models(key)
    pages = max(1, math.ceil(len(models) / PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    chunk = models[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    cur = current_model(uid)

    rows = [[B(model_label(m, cur), callback_data=f"m:{md5s(m['id'])}")] for m in chunk]
    nav = []
    if page > 0:
        nav.append(B("◀️ السابق", callback_data=f"c:{key}:{page - 1}"))
    nav.append(B(f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(B("التالي ▶️", callback_data=f"c:{key}:{page + 1}"))
    rows.append(nav)
    if key.startswith("p_"):
        rows.append([B("🔙 الشركات", callback_data="pl:0"), B("🏠 القائمة", callback_data="menu")])
        title = f"🏢 {store.provider_name_by_key(key)}"
    else:
        rows.append([B("🏠 القائمة الرئيسية", callback_data="menu")])
        title = src_title(key) or CAT_LABEL.get(key, key)

    text = (
        f"<b>{esc(title)}</b>\n"
        f"عدد الموديلات: {len(models)} | صفحة {page + 1}/{pages}\n"
        "الرقم بجانب الاسم = حجم السياق • 👁 رؤية • 🎨 توليد صور\n\n"
        "اضغط على موديل لاختياره 👇"
    )
    if not models:
        text = f"<b>{esc(title)}</b>\nلا توجد موديلات في هذا القسم حالياً."
    return text, InlineKeyboardMarkup(rows)


def view_providers(page: int):
    provs = sorted(store.providers().items(), key=lambda kv: (-len(kv[1]), kv[0]))
    pages = max(1, math.ceil(len(provs) / PROVIDERS_PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    chunk = provs[page * PROVIDERS_PAGE_SIZE:(page + 1) * PROVIDERS_PAGE_SIZE]
    rows, row = [], []
    for name, ms in chunk:
        row.append(B(f"{name} ({len(ms)})", callback_data=f"c:p_{md5s(name, 8)}:0"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(B("◀️", callback_data=f"pl:{page - 1}"))
    nav.append(B(f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(B("▶️", callback_data=f"pl:{page + 1}"))
    rows.append(nav)
    rows.append([B("🏠 القائمة الرئيسية", callback_data="menu")])
    return "🏢 <b>اختر الشركة المطوّرة:</b>", InlineKeyboardMarkup(rows)


def model_info_text(m: dict) -> str:
    prem = "\n⭐ <b>موديل حصري للمشتركين المميزين</b>" if m["id"] in settings["premium_models"] else ""
    return (
        "✅ <b>تم اختيار الموديل</b>\n\n"
        f"🏷 الاسم: {esc(m['name'])}\n"
        f"🆔 المعرّف: <code>{esc(m['raw_id'])}</code>\n"
        f"🔌 المصدر: {src_label(m['src'])}\n"
        f"📏 السياق: {fmt_ctx(m['context'])} توكن\n"
        f"⬇️ يستقبل: {esc(', '.join(m['in']))}\n"
        f"⬆️ ينتج: {esc(', '.join(m['out']))}"
        + prem
        + (f"\n📝 {esc(m['desc'][:300])}…\n" if m["desc"] else "")
        + "\nأرسل رسالتك الآن 👇"
    )


# ==========================================================================
#                        الاتصال مع مزوّدي الذكاء (OpenRouter / Conduit)
# ==========================================================================
class ORError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def friendly_error(e: ORError, src: str = "or") -> str:
    s = e.status
    who = re.sub(r"^\W+\s*", "", src_label(src)).strip() or src
    if s == 401:
        return f"🔑 مفتاح {who} غير صحيح أو منتهي. راجع الإعدادات في أعلى الملف."
    if s == 402:
        return f"💳 رصيد غير كافٍ في {who} أو الموديل يحتاج رصيداً. جرّب موديلاً آخر."
    if s == 404:
        return ("❌ هذا الموديل لم يعد متاحاً (ربما أُزيل أو لا يوجد مزوّد له).\n"
                "اضغط /models ثم 🔄 تحديث الموديلات، واختر موديلاً آخر.")
    if s == 408 or s == 0:
        return f"⏱ {e.message}"
    if s == 429:
        return (f"🚦 تجاوزت حد الطلبات عند {who} أو أن المزوّد مشغول.\n"
                "انتظر قليلاً أو اختر موديلاً آخر من /models.")
    if s in (502, 503, 504):
        return "🛠 المزوّد غير متاح مؤقتاً. حاول مجدداً أو غيّر الموديل."
    return f"⚠️ خطأ ({s}) من {who}: {e.message}"


async def provider_chat(base_url: str, headers: dict, model_id: str, messages: list, want_images: bool) -> dict:
    payload = {"model": model_id, "messages": messages}
    if want_images:
        payload["modalities"] = ["image", "text"]

    for attempt in range(3):
        try:
            r = await http.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException:
            raise ORError(0, "انتهت مهلة الطلب. الموديل بطيء، جرّب مرة أخرى.")
        except httpx.HTTPError as e:
            raise ORError(0, f"خطأ اتصال: {e}")

        try:
            data = r.json()
        except Exception:
            data = {}
        err = data.get("error") if isinstance(data, dict) else None

        if r.status_code == 200 and not err:
            return data

        status = r.status_code
        if r.status_code == 200 and isinstance(err, dict):
            code = err.get("code")
            status = code if isinstance(code, int) else 500
        msg = ""
        if isinstance(err, dict):
            msg = str(err.get("message") or "")
            raw = (err.get("metadata") or {}).get("raw")
            if isinstance(raw, str) and raw:
                msg += f" — {raw[:200]}"
        msg = msg or r.text[:300]

        if status in (429, 502, 503, 504) and attempt < 2:
            await asyncio.sleep(2 * (attempt + 1))
            continue
        raise ORError(status, msg)
    raise ORError(500, "فشل غير معروف")


def merge_system_into_user(messages: list) -> list:
    """لبعض الموديلات لا تدعم system prompt: ندمجه في أول رسالة مستخدم."""
    if not messages or messages[0]["role"] != "system":
        return messages
    sys_txt = messages[0]["content"]
    rest = copy.deepcopy(messages[1:])
    for m in rest:
        if m["role"] == "user":
            if isinstance(m["content"], str):
                m["content"] = f"{sys_txt}\n\n{m['content']}"
            else:
                m["content"] = [{"type": "text", "text": sys_txt}] + m["content"]
            break
    return rest


def parse_response(data: dict) -> tuple[str, list[bytes], int]:
    choices = data.get("choices") or []
    if not choices:
        raise ORError(500, "الموديل لم يُرجع أي رد.")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    text = (content or "").strip()

    images: list[bytes] = []
    for img in msg.get("images") or []:
        url = (img.get("image_url") or {}).get("url", "") if isinstance(img, dict) else ""
        if url.startswith("data:") and "," in url:
            try:
                images.append(base64.b64decode(url.split(",", 1)[1]))
            except Exception:
                pass
    usage = data.get("usage") or {}
    tokens = int(usage.get("total_tokens")
                 or ((usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)) or 0)
    return text, images, tokens


# ==========================================================================
#                   Gemini Native API (مختلف تماماً عن OpenAI-compatible)
# ==========================================================================
async def _gemini_post(url: str, headers: dict, payload: dict) -> dict:
    """POST عام لمسارَي Gemini (generateContent / interactions) مع نفس منطق إعادة المحاولة."""
    for attempt in range(3):
        try:
            r = await http.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise ORError(0, "انتهت مهلة الطلب. الموديل بطيء، جرّب مرة أخرى.")
        except httpx.HTTPError as e:
            raise ORError(0, f"خطأ اتصال: {e}")
        try:
            data = r.json()
        except Exception:
            data = {}
        err = data.get("error") if isinstance(data, dict) else None
        if r.status_code == 200 and not err:
            return data
        status = r.status_code
        msg = str((err or {}).get("message") or r.text[:300])
        if status in (429, 502, 503, 504) and attempt < 2:
            await asyncio.sleep(2 * (attempt + 1))
            continue
        raise ORError(status, msg)
    raise ORError(500, "فشل غير معروف")


def _gemini_convert_messages(messages: list) -> tuple[str | None, list]:
    """يحوّل رسائل OpenAI-style (system/user/assistant) إلى contents + system_instruction عند Gemini."""
    system_text = None
    contents = []
    for msg in messages:
        role, content = msg["role"], msg["content"]
        if role == "system":
            if isinstance(content, str) and content.strip():
                system_text = (system_text + "\n\n" + content) if system_text else content
            continue
        parts = []
        if isinstance(content, str):
            if content:
                parts.append({"text": content})
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text" and part.get("text"):
                    parts.append({"text": part["text"]})
                elif part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    if url.startswith("data:") and "," in url:
                        header, b64data = url.split(",", 1)
                        mime = header[5:].split(";")[0] or "image/jpeg"
                        parts.append({"inline_data": {"mime_type": mime, "data": b64data}})
        if parts:
            contents.append({"role": "model" if role == "assistant" else "user", "parts": parts})
    return system_text, contents


async def ask_gemini_generate_content(base_url: str, p: dict, raw_id: str, messages: list) -> tuple[str, list[bytes], int]:
    system_text, contents = _gemini_convert_messages(messages)
    payload = {"contents": contents}
    if system_text:
        payload["system_instruction"] = {"parts": [{"text": system_text}]}
    data = await _gemini_post(f"{base_url}/models/{raw_id}:generateContent", gemini_headers(p), payload)

    candidates = data.get("candidates") or []
    if not candidates:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        raise ORError(400 if block else 500, f"تم حظر الطلب من Gemini: {block}" if block else "الموديل لم يُرجع أي رد.")
    cparts = (candidates[0].get("content") or {}).get("parts") or []
    text = "\n".join(x.get("text", "") for x in cparts if isinstance(x, dict) and x.get("text")).strip()
    images: list[bytes] = []
    for x in cparts:
        inline = x.get("inlineData") or x.get("inline_data")
        if isinstance(inline, dict) and inline.get("data"):
            try:
                images.append(base64.b64decode(inline["data"]))
            except Exception:
                pass
    usage = data.get("usageMetadata") or {}
    tokens = int(usage.get("totalTokenCount") or 0)
    return text, images, tokens


async def ask_gemini_interactions(base_url: str, p: dict, raw_id: str, messages: list) -> tuple[str, list[bytes], int]:
    """لموديلات Gemini التي لا تدعم generateContent وتحتاج Interactions API.
    الـ Interactions API تأخذ مُدخلاً واحداً (input) لا مصفوفة رسائل، فندمج المحادثة في نص واحد مُهيكل."""
    lines = []
    for msg in messages:
        role, content = msg["role"], msg["content"]
        text = content if isinstance(content, str) else "\n".join(
            part.get("text", "") for part in (content or []) if isinstance(part, dict) and part.get("type") == "text")
        if not text:
            continue
        if role == "system":
            lines.append(f"[تعليمات النظام]\n{text}")
        elif role == "assistant":
            lines.append(f"[المساعد]\n{text}")
        else:
            lines.append(text)
    input_text = "\n\n".join(lines).strip() or "مرحباً"
    data = await _gemini_post(f"{base_url}/interactions", gemini_headers(p), {"model": raw_id, "input": input_text})

    if data.get("status") == "failed":
        raise ORError(500, str(data.get("error") or "فشل التفاعل (interaction) عند Gemini"))
    texts = []
    for step in data.get("steps") or []:
        if step.get("type") == "model_output":
            for c in step.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                    texts.append(c["text"])
    usage = data.get("usage") or {}
    tokens = int(usage.get("total_tokens") or 0)
    return "\n".join(texts).strip(), [], tokens


async def ask_gemini(model: dict, messages: list, p: dict) -> tuple[str, list[bytes], int]:
    base_url = p["base_url"].rstrip("/")
    if (model.get("call_mode") or "generateContent") == "generateContent":
        return await ask_gemini_generate_content(base_url, p, model["raw_id"], messages)
    return await ask_gemini_interactions(base_url, p, model["raw_id"], messages)


# ==========================================================================
def provider_conf(src: str) -> tuple[str, dict]:
    if src == "cd":
        return CONDUIT_BASE_URL, conduit_headers()
    if src != "or":
        p = provider_by_id(src)
        if p:
            return p["base_url"].rstrip("/"), provider_headers(p)
    return OR_BASE, or_headers()


async def ask_model(model: dict, messages: list) -> tuple[str, list[bytes], int]:
    if model["src"] not in ("or", "cd"):
        p = provider_by_id(model["src"])
        if p and provider_type_of(p) == "gemini":
            return await ask_gemini(model, messages, p)
    want_images = "image" in model["out"]
    base, headers = provider_conf(model["src"])
    try:
        data = await provider_chat(base, headers, model["raw_id"], messages, want_images)
    except ORError as e:
        if e.status == 400 and re.search(r"instruction|system|developer", e.message, re.I):
            data = await provider_chat(base, headers, model["raw_id"], merge_system_into_user(messages), want_images)
        else:
            raise
    return parse_response(data)


# ==========================================================================
#                               الأوامر
# ==========================================================================
_sub_cache: dict[int, tuple[float, bool]] = {}


async def is_subscribed(bot, uid: int, force: bool = False) -> bool:
    ch = settings["force_sub"]
    if not ch:
        return True
    c = _sub_cache.get(uid)
    if c and not force and time.time() - c[0] < 60:
        return c[1]
    ok = True
    try:
        mem = await bot.get_chat_member(ch, uid)
        ok = str(mem.status) in ("member", "administrator", "creator", "restricted")
    except Exception as e:  # لو فشل التحقق لا نمنع المستخدم
        log.warning("Force-sub check failed (is the bot admin in the channel?): %s", e)
        ok = True
    _sub_cache[uid] = (time.time(), ok)
    return ok


def sub_markup() -> InlineKeyboardMarkup:
    ch = str(settings["force_sub"])
    link = settings["force_sub_link"] or (f"https://t.me/{ch.lstrip('@')}" if ch.startswith("@") else "")
    rows = []
    if link:
        rows.append([B("📢 اشترك بالقناة", url=link)])
    rows.append([B("✅ تحققت من الاشتراك", callback_data="chksub")])
    return InlineKeyboardMarkup(rows)


async def deny(update: Update, text: str, markup=None):
    q = update.callback_query
    if q:
        try:
            await q.answer(text[:190], show_alert=True)
        except Exception:
            pass
        if markup and q.message:
            await q.message.reply_text(text, reply_markup=markup)
    elif update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=markup)


async def notify_admins(bot, text: str):
    for a in all_admin_ids():
        try:
            await bot.send_message(a, text, parse_mode=ParseMode.HTML)
        except Exception:
            pass


async def guard(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    rec, is_new = users.touch(user)
    if is_new and settings["notify_new_users"]:
        spawn(notify_admins(
            update.get_bot(),
            f"👤 <b>مستخدم جديد</b>\n{esc(user.full_name)} "
            f"{'@' + esc(user.username) if user.username else ''}\n<code>{user.id}</code>"))

    if is_admin(user.id):
        return True
    if rec["banned"]:
        reason = f"\nالسبب: {rec['ban_reason']}" if rec["ban_reason"] else ""
        await deny(update, settings["ban_msg"] + reason)
        return False
    if settings["maintenance"]:
        await deny(update, settings["maintenance_msg"])
        return False
    if settings["private_mode"] and not rec["allowed"]:
        await deny(update, f"🔒 هذا البوت خاص ولا يعمل إلا للمصرّح لهم.\nمعرفك: {user.id}")
        return False
    if not await is_subscribed(update.get_bot(), user.id):
        await deny(update, "📢 يجب الاشتراك في القناة أولاً لاستخدام البوت.", sub_markup())
        return False
    return True


def welcome_greeting(tg_user) -> str:
    name = esc(tg_user.first_name or "")
    custom = settings["welcome_text"]
    return esc(custom).replace("{name}", name) if custom else f"👋 أهلاً {name}!"


async def ensure_models() -> bool:
    if store.models:
        return True
    try:
        await store.refresh()
        return True
    except Exception as e:
        log.error("Model fetch failed: %s", e)
        return False


async def apply_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يمنح صاحب رابط الدعوة نقاطاً عند انضمام شخص جديد عبر /start ref_<id>."""
    user = update.effective_user
    if not context.args:
        return
    payload = context.args[0]
    if not payload.startswith("ref_"):
        return
    rec = users.get(user.id)
    if rec.get("invited_by") or rec.get("referral_claimed"):
        return
    if rec["msg_count"] > 0:  # ليس مستخدماً جديداً فعلياً، تجنّب استغلال الرابط
        return
    try:
        inviter_id = int(payload[4:])
    except ValueError:
        return
    if inviter_id == user.id or not users.exists(inviter_id):
        return
    rec["invited_by"] = inviter_id
    rec["referral_claimed"] = True
    inviter = users.get(inviter_id)
    pts = int(settings["ref_points"])
    inviter["points"] = int(inviter.get("points", 0)) + pts
    inviter["referrals"] = int(inviter.get("referrals", 0)) + 1
    users.save()
    try:
        name = esc(user.full_name or user.first_name or "صديق")
        await context.bot.send_message(
            inviter_id,
            f"🎉 <b>{name}</b> انضم عبر رابط دعوتك!\n🎁 حصلت على <b>{pts}</b> رسالة إضافية.",
            parse_mode=ParseMode.HTML)
    except Exception:
        pass


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    await apply_referral(update, context)
    if not await ensure_models():
        await update.message.reply_text("❌ تعذّر جلب الموديلات. تحقق من الإنترنت ومن مفاتيح المزوّدين.")
        return
    uid = update.effective_user.id
    await update.message.reply_text(
        welcome_greeting(update.effective_user) + "\n\n" + main_menu_text(uid),
        reply_markup=kb_main(), parse_mode=ParseMode.HTML,
    )


async def cmd_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    uid = update.effective_user.id
    rec = users.get(uid)
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{uid}"
    await update.message.reply_text(
        "🎁 <b>ادعُ أصدقاءك واربح رسائل إضافية!</b>\n\n"
        f"🔗 رابط دعوتك:\n<code>{esc(link)}</code>\n\n"
        f"👥 عدد من دعوتهم بنجاح: <b>{rec.get('referrals', 0)}</b>\n"
        f"🎁 رصيدك الحالي من النقاط: <b>{rec.get('points', 0)}</b> رسالة إضافية\n\n"
        f"كل صديق ينضم لأول مرة عبر رابطك يمنحك <b>{int(settings['ref_points'])}</b> رسالة إضافية تُستخدم "
        "تلقائياً بعد وصولك لحدك اليومي 🎉",
        parse_mode=ParseMode.HTML,
    )


async def cmd_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not await ensure_models():
        await update.message.reply_text("❌ تعذّر جلب الموديلات.")
        return
    await update.message.reply_text(
        main_menu_text(update.effective_user.id),
        reply_markup=kb_main(), parse_mode=ParseMode.HTML,
    )


def refresh_report(res: dict) -> str:
    lines = ["✅ <b>تم تحديث قائمة الموديلات</b>", f"📦 المجموع الآن: <b>{res['total']}</b>"]
    counts = store.models_count_by_src()
    lines.append(f"🆓 OpenRouter: {counts.get('or', 0)} · 🧭 Conduit: {counts.get('cd', 0)}")
    if res.get("errors"):
        lines.append("\n⚠️ <b>تعذّر جلب بعض المزوّدين:</b>")
        for e in res["errors"]:
            lines.append(f"• {esc(str(e))[:200]}")
    if res.get("first_load"):
        lines.append("\nتم تحميل القائمة لأول مرة.")
    else:
        added, removed = res["added"], res["removed"]
        if added:
            lines.append(f"\n🆕 <b>موديلات جديدة ({len(added)}):</b>")
            for m in added[:20]:
                lines.append(f"• {src_icon(m['src'])} {esc(short_name(m, 46))} — <code>{esc(m['raw_id'])}</code>")
            if len(added) > 20:
                lines.append(f"… و{len(added) - 20} أخرى")
        else:
            lines.append("\nلا توجد موديلات جديدة.")
        if removed:
            lines.append(f"\n🗑 <b>موديلات أُزيلت ({len(removed)}):</b>")
            for i in removed[:10]:
                lines.append(f"• <code>{esc(i)}</code>")
    return "\n".join(lines)


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    wait = await update.message.reply_text("⏳ جاري تحديث الموديلات...")
    try:
        res = await store.refresh()
        await wait.edit_text(refresh_report(res), parse_mode=ParseMode.HTML,
                             reply_markup=InlineKeyboardMarkup([[B("🏠 القائمة", callback_data="menu")]]))
    except Exception as e:
        await wait.edit_text(f"❌ فشل التحديث: {esc(str(e))}", parse_mode=ParseMode.HTML)


async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    uid = update.effective_user.id
    mid = current_model(uid) or store.default_model()
    if not mid:
        await update.message.reply_text("لا توجد موديلات محمّلة. اضغط /start")
        return
    await update.message.reply_text(model_info_text(store.models[mid]).replace(
        "✅ <b>تم اختيار الموديل</b>", "🤖 <b>الموديل الحالي</b>"), parse_mode=ParseMode.HTML)


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    histories.pop(update.effective_user.id, None)
    await update.message.reply_text("🗑️ تم مسح الذاكرة. بدأنا محادثة جديدة.")


async def cmd_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    u = users.get(update.effective_user.id)
    arg = " ".join(context.args).strip() if context.args else ""
    if not arg:
        await update.message.reply_text(
            f"📝 System Prompt الحالي:\n\n{effective_system(update.effective_user.id)}\n\n"
            "لتغييره: /system نص جديد\nللإرجاع للافتراضي: /system reset")
        return
    u["system"] = None if arg.lower() == "reset" else arg[:2000]
    users.save()
    histories.pop(update.effective_user.id, None)
    await update.message.reply_text("✅ تم تحديث التعليمات (System Prompt) ومسح الذاكرة.")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    q = " ".join(context.args).strip() if context.args else ""
    if not q:
        await update.message.reply_text("اكتب: /search اسم_الموديل\nمثال: /search llama")
        return
    res = store.search(q)[:20]
    if not res:
        await update.message.reply_text("🔍 لا توجد نتائج.")
        return
    cur = current_model(update.effective_user.id)
    rows = [[B(model_label(m, cur), callback_data=f"m:{md5s(m['id'])}")] for m in res]
    rows.append([B("🏠 القائمة", callback_data="menu")])
    await update.message.reply_text(f"🔍 نتائج «{q}» ({len(res)}):", reply_markup=InlineKeyboardMarkup(rows))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    rec = users.get(update.effective_user.id)
    limit = rec["limit"] if rec["limit"] is not None else (
        settings["limit_premium"] if rec["tier"] == "premium" else settings["limit_normal"])
    await update.message.reply_text(
        "📖 <b>الأوامر</b>\n\n"
        "/start — القائمة الرئيسية\n"
        "/models — أقسام الموديلات (OpenRouter و Conduit)\n"
        "/refresh — تحديث قائمة الموديلات\n"
        "/search اسم — بحث عن موديل\n"
        "/current — الموديل الحالي\n"
        "/new — مسح ذاكرة المحادثة\n"
        "/system نص — تخصيص تعليمات الذكاء الاصطناعي\n"
        "/invite — رابط دعوتك ونقاطك\n\n"
        "💡 أرسل نصاً للمحادثة، أو صورة (لموديلات الرؤية 👁)، "
        "أو ملف نصي/كود لتحليله.\n"
        f"👤 فئتك: {'⭐ مميز' if rec['tier'] == 'premium' else '👤 عادي'} "
        f"| حدك اليومي: {limit or '∞'} رسالة\n"
        "⚠️ لبعض الموديلات حدود طلبات من المزوّد نفسه.",
        parse_mode=ParseMode.HTML,
    )


# ==========================================================================
#                         الأزرار (Callbacks)
# ==========================================================================
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""

    if data == "chksub":
        if not await is_subscribed(context.bot, q.from_user.id, force=True):
            await q.answer("❌ لم تشترك بعد", show_alert=True)
            return
        await q.answer("✅ تم التحقق")
        if not await guard(update):
            return
        if not store.models:
            await ensure_models()
        await safe_edit(q, main_menu_text(q.from_user.id), kb_main())
        return

    if not await guard(update):
        return
    uid = q.from_user.id

    if data.startswith("ad:"):
        await admin_callback(update, context)
        return

    if data == "noop":
        await q.answer()
        return

    if not store.models and not await ensure_models():
        await q.answer("تعذّر جلب الموديلات", show_alert=True)
        return

    if data == "menu":
        await q.answer()
        await safe_edit(q, main_menu_text(uid), kb_main())

    elif data == "invite":
        rec = users.get(uid)
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{uid}"
        await q.answer()
        await safe_edit(q,
            "🎁 <b>ادعُ أصدقاءك واربح رسائل إضافية!</b>\n\n"
            f"🔗 رابط دعوتك:\n<code>{esc(link)}</code>\n\n"
            f"👥 عدد من دعوتهم بنجاح: <b>{rec.get('referrals', 0)}</b>\n"
            f"🎁 رصيدك الحالي من النقاط: <b>{rec.get('points', 0)}</b> رسالة إضافية\n\n"
            f"كل صديق ينضم لأول مرة عبر رابطك يمنحك <b>{int(settings['ref_points'])}</b> رسالة إضافية.",
            InlineKeyboardMarkup([[B("🏠 القائمة الرئيسية", callback_data="menu")]]))

    elif data.startswith("c:"):
        _, key, page = data.split(":")
        await q.answer()
        text, markup = view_category(key, int(page), uid)
        await safe_edit(q, text, markup)

    elif data.startswith("pl:"):
        await q.answer()
        text, markup = view_providers(int(data.split(":")[1]))
        await safe_edit(q, text, markup)

    elif data.startswith("m:"):
        mid = store.by_hash.get(data[2:])
        if not mid or mid not in store.models or settings.is_hidden(mid):
            await q.answer("الموديل لم يعد متاحاً، حدّث القائمة", show_alert=True)
            return
        u = users.get(uid)
        u["model"] = mid
        users.save()
        await q.answer("✅ تم الاختيار")
        await safe_edit(q, model_info_text(store.models[mid]), InlineKeyboardMarkup([
            [B("🗑️ محادثة جديدة", callback_data="new"), B("🏠 القائمة", callback_data="menu")],
        ]))

    elif data == "new":
        histories.pop(uid, None)
        await q.answer("🗑️ تم مسح الذاكرة")

    elif data == "refresh":
        if time.time() - store.updated_at < 10:
            await q.answer("القائمة محدّثة للتو ✅")
            return
        await q.answer("⏳ جاري التحديث...")
        try:
            res = await store.refresh()
            await safe_edit(q, refresh_report(res),
                            InlineKeyboardMarkup([[B("🏠 القائمة الرئيسية", callback_data="menu")]]))
        except Exception as e:
            await safe_edit(q, f"❌ فشل التحديث: {esc(str(e))}",
                            InlineKeyboardMarkup([[B("🏠 القائمة", callback_data="menu")]]))
    else:
        await q.answer()


# ==========================================================================
#                         معالجة رسائل المحادثة
# ==========================================================================
TEXT_EXT = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".html", ".css", ".xml",
            ".yml", ".yaml", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".php",
            ".sh", ".sql", ".log", ".ini", ".toml", ".kt", ".swift", ".rb", ".lua"}


async def keep_typing(bot, chat_id: int, action=ChatAction.TYPING):
    try:
        while True:
            await bot.send_chat_action(chat_id, action)
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


async def reply_long(message, text: str):
    for chunk in split_text(text.strip() or "(رد فارغ)"):
        await message.reply_text(chunk, disable_web_page_preview=True)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    msg = update.message
    if not msg:
        return
    uid = update.effective_user.id

    if not store.models and not await ensure_models():
        await msg.reply_text("❌ تعذّر جلب الموديلات. حاول /refresh لاحقاً.")
        return

    # ---- تحديد الموديل ----
    mid = current_model(uid)
    if not mid:
        prev = users.get(uid)["model"]
        mid = store.default_model()
        users.get(uid)["model"] = mid
        users.save()
        if prev and prev != mid:
            await msg.reply_text(
                f"ℹ️ الموديل السابق ({prev}) لم يعد متاحاً، تم التحويل إلى:\n{mid}")
    model = store.models[mid]

    # ---- تجهيز المحتوى ----
    text = (msg.text or msg.caption or "").strip()
    image_bytes: bytes | None = None
    history_note = text

    if not is_admin(uid):
        if msg.photo and not settings["allow_images"]:
            await msg.reply_text("🖼 إرسال الصور معطّل حالياً من الإدارة.")
            return
        if msg.document and not settings["allow_files"]:
            await msg.reply_text("📎 إرسال الملفات معطّل حالياً من الإدارة.")
            return

    try:
        if msg.photo:
            f = await msg.photo[-1].get_file()
            image_bytes = bytes(await f.download_as_bytearray())
        elif msg.document:
            doc = msg.document
            ext = Path(doc.file_name or "").suffix.lower()
            if (doc.mime_type or "").startswith("image/"):
                f = await doc.get_file()
                image_bytes = bytes(await f.download_as_bytearray())
            elif ext in TEXT_EXT or (doc.mime_type or "").startswith("text/"):
                if doc.file_size and doc.file_size > MAX_DOC_BYTES:
                    await msg.reply_text(f"⚠️ الملف كبير. الحد الأقصى {MAX_DOC_BYTES // 1000}KB.")
                    return
                f = await doc.get_file()
                raw = bytes(await f.download_as_bytearray())
                body = raw.decode("utf-8", errors="replace")
                head = text or "حلّل هذا الملف ولخّص محتواه:"
                text = f"{head}\n\n--- {doc.file_name} ---\n{body}"
                history_note = f"{head}\n[ملف: {doc.file_name}]"
            else:
                await msg.reply_text("⚠️ نوع الملف غير مدعوم. أرسل نصاً أو صورة أو ملف نصي/كود.")
                return
    except Exception as e:
        await msg.reply_text(f"⚠️ تعذّر تحميل الملف: {e}")
        return

    if image_bytes is not None:
        if "image" not in model["in"]:
            await msg.reply_text(
                "👁 الموديل الحالي لا يدعم الصور.\n"
                "اختر موديلاً من قسم «👁️ رؤية وتحليل صور» عبر /models.")
            return
        b64 = base64.b64encode(image_bytes).decode()
        user_content = [
            {"type": "text", "text": text or "صف هذه الصورة بالتفصيل."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]
        history_note = f"[صورة] {text}".strip()
    else:
        if not text:
            return
        user_content = text

    # ---- القصر على المميزين ----
    used_points = False
    if not is_admin(uid):
        rec = users.get(uid)
        if mid in settings["premium_models"] and rec["tier"] != "premium":
            await msg.reply_text(
                "⭐ هذا الموديل حصري للمشتركين المميزين فقط.\n"
                "تواصل مع الإدارة للترقية، أو اختر موديلاً آخر عبر /models.")
            return

        # ---- الحد اليومي (حسب الفئة) + نقاط الدعوة ----
        limit = rec["limit"] if rec["limit"] is not None else (
            settings["limit_premium"] if rec["tier"] == "premium" else settings["limit_normal"])
        if limit and users.used_today(uid) >= limit:
            if rec.get("points", 0) > 0:
                used_points = True
            else:
                await msg.reply_text(
                    f"📏 وصلت لحدك اليومي ({limit} رسالة).\n"
                    "🎁 يمكنك كسب رسائل إضافية بدعوة أصدقائك: /invite\n"
                    "أو عُد غداً 🌙")
                return

    # ---- إرسال الطلب ----
    async with user_lock(uid):
        hist = histories.setdefault(uid, [])
        messages = [{"role": "system", "content": effective_system(uid)}] + hist + [
            {"role": "user", "content": user_content}
        ]
        action = ChatAction.UPLOAD_PHOTO if "image" in model["out"] else ChatAction.TYPING
        typing = asyncio.create_task(keep_typing(context.bot, msg.chat_id, action))
        try:
            answer, images, tokens = await ask_model(model, messages)
        except ORError as e:
            typing.cancel()
            stats.add_error(mid, e.status, e.message)
            await msg.reply_text(friendly_error(e, model["src"]))
            return
        except Exception as e:
            typing.cancel()
            stats.add_error(mid, 0, str(e))
            log.exception("Unexpected error")
            await msg.reply_text(f"⚠️ خطأ غير متوقع: {e}")
            return
        finally:
            typing.cancel()

        stats.record(mid, tokens)
        users.bump(uid, tokens)
        if used_points:
            rec = users.get(uid)
            rec["points"] = max(0, int(rec.get("points", 0)) - 1)
            users.mark()

        # حفظ الذاكرة
        hist.append({"role": "user", "content": history_note or "..."})
        hist.append({"role": "assistant", "content": answer or "[صورة]"})
        hl = max(2, int(settings["history_len"]))
        if len(hist) > hl:
            del hist[: len(hist) - hl]
            while hist and hist[0]["role"] != "user":
                hist.pop(0)

    # ---- إرسال الرد ----
    for img in images:
        try:
            await msg.reply_photo(photo=img)
        except Exception as e:
            log.warning("send photo failed: %s", e)
    if answer:
        await reply_long(msg, answer)
    elif not images:
        await msg.reply_text("⚠️ الموديل أرجع رداً فارغاً. جرّب إعادة الصياغة أو موديلاً آخر.")


# ==========================================================================
#                        🛡 لوحة تحكم الأدمن
# ==========================================================================
USER_PAGE = 8
USER_FILTERS = [("all", "الكل"), ("act", "نشط 24س"), ("new", "جدد اليوم"),
                 ("ban", "محظور"), ("alw", "مسموح"), ("prem", "⭐ مميز")]
TOGGLES = {
    "maintenance": "وضع الصيانة",
    "private_mode": "الوضع الخاص",
    "allow_images": "قبول الصور",
    "allow_files": "قبول الملفات",
    "notify_new_models": "إشعار بموديلات جديدة",
    "notify_new_users": "إشعار بمستخدم جديد",
}
SETTING_SPECS = {
    "limit_normal": ("📏 أرسل الحد اليومي للمستخدم <b>العادي</b> (رقم، <b>0</b> = بلا حد):", "int"),
    "limit_premium": ("⭐ أرسل الحد اليومي للمستخدم <b>المميز</b> (رقم، <b>0</b> = بلا حد):", "int"),
    "ref_points": ("🎁 أرسل عدد النقاط/الرسائل الإضافية التي يربحها المستخدم عن كل شخص يدعوه:", "int"),
    "history_len": ("🧠 أرسل عدد رسائل ذاكرة المحادثة (من 2 إلى 60):", "int"),
    "welcome_text": ("👋 أرسل رسالة الترحيب الجديدة. استخدم <code>{name}</code> لاسم المستخدم.\nأرسل <b>reset</b> للرجوع للافتراضية.", "text"),
    "system_prompt": ("📝 أرسل الـ System Prompt الافتراضي لكل المستخدمين.\nأرسل <b>reset</b> للرجوع للافتراضي.", "text"),
    "maintenance_msg": ("🛠 أرسل رسالة الصيانة التي تظهر للمستخدمين.", "text"),
    "ban_msg": ("🚫 أرسل رسالة الحظر التي تظهر للمحظورين.", "text"),
    "force_sub": ("📢 أرسل معرف القناة أو المجموعة مثل <code>@mychannel</code>\n"
                  "⚠️ يجب أن يكون البوت <b>مشرفاً</b> فيها.\nأرسل <b>off</b> للإيقاف.", "channel"),
}


def kb_back(target: str = "ad:home", label: str = "🔙 لوحة التحكم") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[B(label, callback_data=target)]])


def onoff(v) -> str:
    return "🟢" if v else "⚫"


# ---------------------------------- الرئيسية ----------------------------------
def admin_home_text() -> str:
    us, now = users.all(), time.time()
    act = sum(1 for _, u in us if now - u["last_seen"] < 86400)
    banned = sum(1 for _, u in us if u["banned"])
    today = stats.data["daily"].get(today_str(), {"msgs": 0})
    flags = []
    if settings["maintenance"]:
        flags.append("🛠 صيانة")
    if settings["private_mode"]:
        flags.append("🔒 خاص")
    if settings["force_sub"]:
        flags.append("📢 اشتراك إجباري")
    premc = sum(1 for _, u in us if u["tier"] == "premium")
    counts = store.models_count_by_src()
    return (
        "🛡 <b>لوحة تحكم الأدمن</b>\n\n"
        f"👥 المستخدمون: <b>{len(us)}</b> (نشط 24س: {act} | محظور: {banned} | ⭐ مميز: {premc})\n"
        f"💬 رسائل اليوم: <b>{today['msgs']}</b> | الإجمالي: {stats.data['total_msgs']}\n"
        f"🤖 الموديلات: {len(store.visible())} ظاهر من {len(store.models)} "
        f"(🆓 {counts.get('or', 0)} · 🧭 {counts.get('cd', 0)}"
        f"{' · 🔌 ' + str(extra_src_total(counts)) if extra_src_total(counts) else ''})\n"
        f"📏 الحد: عادي {settings['limit_normal'] or '∞'} / مميز {settings['limit_premium'] or '∞'} في اليوم\n"
        f"⚙️ الحالة: {' • '.join(flags) if flags else 'عادي ✅'}"
    )


def kb_admin_home(uid: int) -> InlineKeyboardMarkup:
    last = [B("🧰 أدوات", callback_data="ad:tools")]
    if is_owner(uid):
        last.append(B("🛡 المشرفون", callback_data="ad:adm"))
    return InlineKeyboardMarkup([
        [B("📊 الإحصائيات", callback_data="ad:stats"), B("👥 المستخدمون", callback_data="ad:users:all:0")],
        [B("📢 البث الجماعي", callback_data="ad:bc"), B("🤖 الموديلات", callback_data="ad:models")],
        [B("⚙️ الإعدادات", callback_data="ad:set"), B("📜 السجلات", callback_data="ad:logs")],
        last,
        [B("🔎 بحث عن مستخدم", callback_data="ad:find"), B("❌ إغلاق", callback_data="ad:close")],
    ])


# ---------------------------------- الإحصائيات ----------------------------------
def _bar(v: int, mx: int) -> str:
    return "▫️" if not v else "█" * max(1, round(v / max(mx, 1) * 10))


def stats_text() -> str:
    us, now, t = users.all(), time.time(), today_str()
    d = stats.data
    act24 = sum(1 for _, u in us if now - u["last_seen"] < 86400)
    act7 = sum(1 for _, u in us if now - u["last_seen"] < 7 * 86400)
    banned = sum(1 for _, u in us if u["banned"])
    blocked = sum(1 for _, u in us if u["blocked_bot"])
    new_today = sum(1 for _, u in us if day_of(u["joined"]) == t)
    td = d["daily"].get(t, {"msgs": 0, "tokens": 0})

    days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    vals = [d["daily"].get(x, {"msgs": 0})["msgs"] for x in days]
    mx = max(vals) if vals else 1
    chart = "\n".join(f"<code>{x[5:]}</code> {_bar(v, mx)} {v}" for x, v in zip(days, vals))

    top_m = sorted(d["models"].items(), key=lambda kv: -kv[1])[:5]
    top_u = sorted(us, key=lambda x: -x[1]["msg_count"])[:5]
    tm = "\n".join(f"{i}. <code>{esc(k)}</code> — {v}" for i, (k, v) in enumerate(top_m, 1)) or "—"
    tu = "\n".join(
        f"{i}. {esc(u['first_name'] or str(uid))} — {u['msg_count']}"
        for i, (uid, u) in enumerate(top_u, 1) if u["msg_count"]) or "—"
    return (
        "📊 <b>الإحصائيات</b>\n\n"
        f"👥 إجمالي المستخدمين: <b>{len(us)}</b>\n"
        f"🔥 نشط 24 ساعة: {act24} | 7 أيام: {act7}\n"
        f"🆕 جدد اليوم: {new_today}\n"
        f"🚫 محظورون: {banned} | حظروا البوت: {blocked}\n\n"
        f"💬 رسائل اليوم: <b>{td['msgs']}</b> | الإجمالي: {d['total_msgs']}\n"
        f"🧮 توكنات اليوم: {td['tokens']:,} | الإجمالي: {d['total_tokens']:,}\n"
        f"⚠️ الأخطاء: {d['total_errors']}\n\n"
        f"📈 <b>آخر 7 أيام:</b>\n{chart}\n\n"
        f"🏆 <b>أكثر الموديلات استخداماً:</b>\n{tm}\n\n"
        f"🥇 <b>أكثر المستخدمين نشاطاً:</b>\n{tu}"
    )


# ---------------------------------- المستخدمون ----------------------------------
def view_users(kind: str, page: int):
    lst = users.filtered(kind)
    pages = max(1, math.ceil(len(lst) / USER_PAGE))
    page = max(0, min(page, pages - 1))
    chunk = lst[page * USER_PAGE:(page + 1) * USER_PAGE]

    frow1 = [B(("• " if k == kind else "") + lb, callback_data=f"ad:users:{k}:0") for k, lb in USER_FILTERS[:3]]
    frow2 = [B(("• " if k == kind else "") + lb, callback_data=f"ad:users:{k}:0") for k, lb in USER_FILTERS[3:]]
    rows = [frow1, frow2]
    for uid, u in chunk:
        icon = "🚫" if u["banned"] else ("🔒" if u["allowed"] else "👤")
        name = (u["first_name"] or u["username"] or str(uid))[:16]
        rows.append([B(f"{icon} {name} · {u['msg_count']} 💬", callback_data=f"ad:u:{uid}")])
    nav = []
    if page > 0:
        nav.append(B("◀️", callback_data=f"ad:users:{kind}:{page - 1}"))
    nav.append(B(f"{page + 1}/{pages}", callback_data="ad:noop"))
    if page < pages - 1:
        nav.append(B("▶️", callback_data=f"ad:users:{kind}:{page + 1}"))
    rows.append(nav)
    rows.append([B("🔎 بحث", callback_data="ad:find"), B("🔙 لوحة التحكم", callback_data="ad:home")])
    label = dict(USER_FILTERS)[kind]
    return (f"👥 <b>المستخدمون — {label}</b>\nالعدد: {len(lst)}\n"
            "(🚫 محظور • 🔒 مسموح • ⭐ مميز • 👤 عادي)", InlineKeyboardMarkup(rows))


def view_user(target: int):
    u = users.get(target)
    is_prem = u["tier"] == "premium"
    limit = u["limit"] if u["limit"] is not None else (
        settings["limit_premium"] if is_prem else settings["limit_normal"])
    lim_txt = ("∞" if not limit else str(limit)) + (" (مخصص)" if u["limit"] is not None else " (عام)")
    if u["banned"]:
        status = "🚫 محظور" + (f" — {esc(u['ban_reason'])}" if u["ban_reason"] else "")
    else:
        status = "✅ نشط"
    inviter = f"<code>{u['invited_by']}</code>" if u.get("invited_by") else "لا يوجد"
    text = (
        f"👤 <b>{esc(u['first_name'] or '—')}</b>\n"
        f"🆔 <code>{target}</code> | {'@' + esc(u['username']) if u['username'] else 'بدون يوزر'}\n"
        f"📅 انضم: {fmt_dt(u['joined'])}\n"
        f"🕒 آخر نشاط: {fmt_dt(u['last_seen'])}\n"
        f"💬 الرسائل: {u['msg_count']} | اليوم: {users.used_today(target)} / {lim_txt}\n"
        f"🧮 التوكنات: {u['tokens']:,}\n"
        f"🤖 الموديل: <code>{esc((store.models.get(u['model']) or {}).get('raw_id', u['model'] or 'افتراضي'))}</code>\n"
        f"📌 الحالة: {status}\n"
        f"🎖 الفئة: {'⭐ مميز' if is_prem else '👤 عادي'}\n"
        f"🎁 النقاط (رسائل إضافية): {u.get('points', 0)}\n"
        f"👥 دعا: {u.get('referrals', 0)} شخص | دُعي من: {inviter}\n"
        f"🔒 مسموح (للوضع الخاص): {'نعم' if u['allowed'] else 'لا'}"
        + ("\n⚠️ هذا المستخدم حظر البوت" if u["blocked_bot"] else "")
    )
    rows = [
        [B("✅ فك الحظر" if u["banned"] else "🚫 حظر", callback_data=f"ad:ub:{target}"),
         B("➖ إزالة السماح" if u["allowed"] else "🔒 سماح", callback_data=f"ad:ua:{target}")],
        [B("⬇️ تنزيل لعادي" if is_prem else "⭐ ترقية لمميز", callback_data=f"ad:ut:{target}"),
         B("🎁 تعديل النقاط", callback_data=f"ad:up:{target}")],
        [B("🎯 حد يومي مخصص", callback_data=f"ad:ul:{target}"), B("🔄 تصفير عداد اليوم", callback_data=f"ad:ur:{target}")],
        [B("✉️ مراسلة", callback_data=f"ad:um:{target}"), B("🗑 مسح ذاكرته", callback_data=f"ad:uc:{target}")],
        [B("♻️ إعادة ضبط موديله/تعليماته", callback_data=f"ad:ux:{target}")],
        [B("🔙 المستخدمون", callback_data="ad:users:all:0")],
    ]
    return text, InlineKeyboardMarkup(rows)


# ---------------------------------- البث ----------------------------------
def bc_targets(kind: str) -> list[int]:
    if kind == "adm":
        return all_admin_ids()
    now = time.time()
    out = []
    for uid, u in users.all():
        if u["banned"] or u["blocked_bot"]:
            continue
        if kind == "act" and now - u["last_seen"] > 7 * 86400:
            continue
        out.append(uid)
    return out


def bc_menu():
    text = ("📢 <b>البث الجماعي</b>\n\nاختر الفئة المستهدفة، ثم أرسل الرسالة "
            "(نص/صورة/فيديو/ملف...) وستظهر لك معاينة قبل الإرسال.")
    kb = InlineKeyboardMarkup([
        [B(f"📢 كل المستخدمين ({len(bc_targets('all'))})", callback_data="ad:bc:all")],
        [B(f"🔥 النشطون آخر 7 أيام ({len(bc_targets('act'))})", callback_data="ad:bc:act")],
        [B("🧪 تجربة (المشرفون فقط)", callback_data="ad:bc:adm")],
        [B("🔙 لوحة التحكم", callback_data="ad:home")],
    ])
    return text, kb


async def _copy_retry(bot, chat_id, src_chat, src_msg):
    try:
        await bot.copy_message(chat_id, src_chat, src_msg)
    except RetryAfter as e:
        ra = e.retry_after.total_seconds() if hasattr(e.retry_after, "total_seconds") else float(e.retry_after)
        await asyncio.sleep(ra + 1)
        await bot.copy_message(chat_id, src_chat, src_msg)


async def run_broadcast(bot, status_msg, pend: dict, targets: list[int], bot_data: dict):
    ok = fail = blocked = 0
    total = len(targets)
    try:
        for i, uid in enumerate(targets, 1):
            try:
                await _copy_retry(bot, uid, pend["chat"], pend["msg"])
                ok += 1
            except Forbidden:
                blocked += 1
                users.get(uid)["blocked_bot"] = True
            except TelegramError as e:
                fail += 1
                log.warning("broadcast to %s failed: %s", uid, e)
            await asyncio.sleep(0.05)
            if i % 25 == 0:
                try:
                    await status_msg.edit_text(f"📤 جاري الإرسال... {i}/{total}")
                except Exception:
                    pass
        users.flush(True)
        await status_msg.edit_text(
            f"✅ <b>انتهى البث</b>\n\n📬 نجح: {ok}\n🚫 حظروا البوت: {blocked}\n❌ فشل: {fail}\n📊 المجموع: {total}",
            parse_mode=ParseMode.HTML, reply_markup=kb_back())
    except Exception as e:
        log.exception("broadcast crashed")
        try:
            await status_msg.edit_text(f"⚠️ توقف البث: {e}\nنجح {ok} من {total}")
        except Exception:
            pass
    finally:
        bot_data["bc_running"] = False


# ---------------------------------- الموديلات ----------------------------------
async def fetch_all_models_raw() -> list[dict]:
    r = await http.get(f"{OR_BASE}/models", headers=or_headers(), params={"output_modalities": "all"})
    if r.status_code >= 400:
        r = await http.get(f"{OR_BASE}/models", headers=or_headers())
    r.raise_for_status()
    return r.json().get("data", [])


def view_models_admin():
    d = settings["default_model"]
    counts = store.models_count_by_src()
    text = (
        "🤖 <b>إدارة الموديلات</b>\n\n"
        f"📦 المجموع: {len(store.models)} | الظاهر: {len(store.visible())} "
        f"(🆓 {counts.get('or', 0)} · 🧭 {counts.get('cd', 0)}"
        f"{' · 🔌 ' + str(extra_src_total(counts)) if extra_src_total(counts) else ''})\n"
        f"⭐ الافتراضي: <code>{esc((store.models.get(d) or {}).get('raw_id', 'تلقائي'))}</code>\n"
        f"🙈 المخفية: {len(settings['hidden_models'])} | 🗂 الأقسام المخفية: {len(settings['hidden_cats'])}\n"
        f"⭐ حصرية للمميزين: {len(settings['premium_models'])}\n"
        f"💎 المضافة يدوياً (OpenRouter): {len(settings['extra_models'])}\n"
        f"🕒 آخر تحديث: {fmt_dt(store.updated_at)}"
    )
    kb = InlineKeyboardMarkup([
        [B("⭐ تعيين موديل افتراضي", callback_data="ad:mdef"), B("🧹 إلغاء الافتراضي", callback_data="ad:mdefclr")],
        [B("🙈 إخفاء/إظهار موديل", callback_data="ad:mhide"), B(f"📋 المخفية ({len(settings['hidden_models'])})", callback_data="ad:mlist")],
        [B("⭐ حصر موديل للمميزين", callback_data="ad:mprem"), B(f"📋 الحصرية ({len(settings['premium_models'])})", callback_data="ad:mplist")],
        [B("🗂 إدارة الأقسام", callback_data="ad:mcat"), B("➕ إضافة موديل يدوياً (OR)", callback_data="ad:madd")],
        [B(f"💎 الموديلات المضافة ({len(settings['extra_models'])})", callback_data="ad:mext"), B("🔄 تحديث الآن", callback_data="ad:mref")],
        [B(f"🔌 مزوّدون إضافيون ({len(settings['providers'])})", callback_data="ad:prov")],
        [B("🔙 لوحة التحكم", callback_data="ad:home")],
    ])
    return text, kb


def view_providers_admin():
    counts = store.models_count_by_src()
    rows = []
    for src, name, icon in all_sources():
        n = counts.get(src, 0)
        if src == "or":
            rows.append([B(f"🆓 OpenRouter — {n} موديل", callback_data="ad:noop")])
        elif src == "cd":
            rows.append([B(f"🧭 Conduit — {n} موديل", callback_data="ad:noop")])
    lines = ["🔌 <b>المزوّدون الإضافيون</b>\n",
             "🆓 OpenRouter و🧭 Conduit مُعدّان من أعلى الملف (env).",
             "من هنا تضيف أي خدمة OpenAI-compatible (رابط + مفتاح)، أو ✨ Gemini Native.\n"]
    for p in settings["providers"]:
        n = counts.get(p["id"], 0)
        st = "🟢" if p.get("enabled", True) else "⚫"
        ptype_tag = " · ✨ Gemini Native" if provider_type_of(p) == "gemini" else ""
        lines.append(f"{st} {p.get('icon', '🔌')} <b>{esc(p['name'])}</b> — {n} موديل{ptype_tag}\n<code>{esc(p['base_url'])}</code>")
        rows.append([
            B(f"{'⏸ تعطيل' if p.get('enabled', True) else '▶️ تفعيل'}", callback_data=f"ad:ptg:{p['id']}"),
            B("🩺 اختبار", callback_data=f"ad:ptest:{p['id']}"),
            B("🗑 حذف", callback_data=f"ad:pdel:{p['id']}"),
        ])
    if not settings["providers"]:
        lines.append("\nلا يوجد مزوّدون إضافيون بعد.")
    lines.append("\n⚡️ إضافة سريعة (تحتاج فقط مفتاحك):")
    quick = [B(f"{kp['icon']} {kp['name']}", callback_data=f"ad:pknown:{i}") for i, kp in enumerate(KNOWN_PROVIDERS)]
    for i in range(0, len(quick), 2):
        rows.append(quick[i:i + 2])
    rows.append([B("➕ إضافة مزوّد مخصّص يدوياً", callback_data="ad:padd")])
    rows.append([B("🔙 الموديلات", callback_data="ad:models")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ---------------------------------- الإعدادات ----------------------------------
def view_settings():
    s = settings
    fs = str(s["force_sub"]) if s["force_sub"] else "مغلق"
    text = (
        "⚙️ <b>إعدادات البوت</b>\n\n"
        "🟢 مفعّل • ⚫ معطّل (اضغط للتبديل)\n\n"
        "• <b>الوضع الخاص</b>: لا يستخدم البوت إلا من تسمح لهم (بطاقة المستخدم أو /allow).\n"
        "• <b>الحدود اليومية</b>: منفصلة للعادي والمميز (المشرفون مستثنون).\n"
        "• <b>نقاط الدعوة</b>: رسائل إضافية تُمنح تلقائياً عند دعوة شخص جديد.\n"
        f"• <b>الاشتراك الإجباري</b>: {esc(fs)}"
    )
    tg = lambda k: B(f"{onoff(s[k])} {TOGGLES[k]}", callback_data=f"ad:tg:{k}")
    kb = InlineKeyboardMarkup([
        [tg("maintenance"), B("✏️ رسالة الصيانة", callback_data="ad:sp:maintenance_msg")],
        [tg("private_mode")],
        [tg("allow_images"), tg("allow_files")],
        [tg("notify_new_models")],
        [tg("notify_new_users")],
        [B(f"📏 حد العادي: {s['limit_normal'] or '∞'}", callback_data="ad:sp:limit_normal"),
         B(f"⭐ حد المميز: {s['limit_premium'] or '∞'}", callback_data="ad:sp:limit_premium")],
        [B(f"🎁 نقاط الدعوة: {s['ref_points']}", callback_data="ad:sp:ref_points"),
         B(f"🧠 الذاكرة: {s['history_len']}", callback_data="ad:sp:history_len")],
        [B("👋 رسالة الترحيب", callback_data="ad:sp:welcome_text"), B("📝 System Prompt", callback_data="ad:sp:system_prompt")],
        [B("📢 قناة الاشتراك الإجباري", callback_data="ad:sp:force_sub"), B("🚫 رسالة الحظر", callback_data="ad:sp:ban_msg")],
        [B("🔙 لوحة التحكم", callback_data="ad:home")],
    ])
    return text, kb


# ---------------------------------- المشرفون ----------------------------------
def view_admins():
    lines = ["🛡 <b>المشرفون</b>\n"]
    rows = []
    for a in ADMIN_IDS:
        u = users.get(a) if users.exists(a) else None
        lines.append(f"👑 مالك: <code>{a}</code> {esc(u['first_name']) if u else ''}")
    for a in settings["admins"]:
        a = int(a)
        u = users.get(a) if users.exists(a) else None
        lines.append(f"🛡 مشرف: <code>{a}</code> {esc(u['first_name']) if u else ''}")
        rows.append([B(f"🗑 إزالة {a}", callback_data=f"ad:adr:{a}")])
    lines.append("\nالمشرفون لهم كل صلاحيات اللوحة ما عدا إدارة المشرفين.")
    rows.append([B("➕ إضافة مشرف", callback_data="ad:ada")])
    rows.append([B("🔙 لوحة التحكم", callback_data="ad:home")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ---------------------------------- السجلات والأدوات ----------------------------------
def logs_text() -> str:
    errs = stats.data["errors"][-15:][::-1]
    if not errs:
        return "📜 <b>سجل الأخطاء</b>\n\n✅ لا توجد أخطاء مسجّلة."
    lines = ["📜 <b>آخر الأخطاء</b>\n"]
    for e in errs:
        lines.append(f"• {fmt_dt(e['t'])} | <b>{esc(str(e['status']))}</b> | <code>{esc(e['model'])}</code>\n   {esc(e['msg'][:140])}")
    return "\n".join(lines)


def view_tools():
    text = "🧰 <b>أدوات الإدارة</b>"
    kb = InlineKeyboardMarkup([
        [B("💾 نسخة احتياطية (JSON)", callback_data="ad:bk"), B("📤 تصدير المستخدمين CSV", callback_data="ad:csv")],
        [B("🧹 مسح ذاكرة كل المحادثات", callback_data="ad:clh"), B("🔄 تحديث الموديلات", callback_data="ad:mref")],
        [B("♻️ تصفير الإحصائيات", callback_data="ad:stclr")],
        [B("🔙 لوحة التحكم", callback_data="ad:home")],
    ])
    return text, kb


# ---------------------------------- طلب إدخال من الأدمن ----------------------------------
async def prompt(q, context, kind: str, text: str, **extra):
    context.user_data["await"] = {"kind": kind, **extra}
    await safe_edit(q, text + "\n\n<i>للإلغاء اضغط الزر أو أرسل /cancel</i>",
                    InlineKeyboardMarkup([[B("❌ إلغاء", callback_data="ad:cancel")]]))


# ---------------------------------- معالج أزرار اللوحة ----------------------------------
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if not is_admin(uid):
        await q.answer("⛔ للمشرفين فقط", show_alert=True)
        return
    parts = (q.data or "").split(":")
    cmd = parts[1] if len(parts) > 1 else "home"
    args = parts[2:]
    bot = context.bot

    if cmd == "noop":
        await q.answer()

    elif cmd in ("home", "cancel"):
        context.user_data.pop("await", None)
        await q.answer()
        await safe_edit(q, admin_home_text(), kb_admin_home(uid))

    elif cmd == "close":
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass

    elif cmd == "stats":
        await q.answer()
        await safe_edit(q, stats_text(), InlineKeyboardMarkup([
            [B("🔄 تحديث", callback_data="ad:stats")], [B("🔙 لوحة التحكم", callback_data="ad:home")]]))

    # ---------- المستخدمون ----------
    elif cmd == "users":
        await q.answer()
        text, kb = view_users(args[0], int(args[1]))
        await safe_edit(q, text, kb)

    elif cmd == "find":
        await q.answer()
        await prompt(q, context, "find_user", "🔎 أرسل معرف المستخدم (ID) أو @يوزر أو جزءاً من الاسم:")

    elif cmd == "u":
        await q.answer()
        text, kb = view_user(int(args[0]))
        await safe_edit(q, text, kb)

    elif cmd in ("ub", "ua", "ul", "um", "uc", "ur", "ux", "ut", "up"):
        target = int(args[0])
        u = users.get(target)
        if cmd == "ub":
            if is_admin(target):
                await q.answer("لا يمكن حظر مشرف", show_alert=True)
                return
            u["banned"] = not u["banned"]
            u["ban_reason"] = "" if not u["banned"] else "بقرار الإدارة"
            users.save()
            await q.answer("🚫 تم الحظر" if u["banned"] else "✅ تم فك الحظر")
        elif cmd == "ua":
            u["allowed"] = not u["allowed"]
            users.save()
            await q.answer("🔒 تمت إضافته للمسموحين" if u["allowed"] else "تمت إزالته من المسموحين")
        elif cmd == "ut":
            u["tier"] = "normal" if u["tier"] == "premium" else "premium"
            users.save()
            await q.answer("⭐ تمت الترقية لمميز" if u["tier"] == "premium" else "⬇️ تم التنزيل لعادي")
        elif cmd == "up":
            await q.answer()
            await prompt(q, context, "u_points",
                         "🎁 أرسل عدد النقاط الجديد (رقم مطلق)، أو فرق بعلامة + أو -\n"
                         "مثال: <code>50</code> لتعيين 50، أو <code>+10</code> أو <code>-5</code> لتعديل الحالي.\n"
                         f"النقاط الحالية: {u.get('points', 0)}", uid=target)
            return
        elif cmd == "ul":
            await q.answer()
            await prompt(q, context, "u_limit", "🎯 أرسل الحد اليومي لهذا المستخدم (رقم، <b>0</b> = بلا حد)\n"
                         "أو <b>reset</b> للرجوع للحد العام.", uid=target)
            return
        elif cmd == "um":
            await q.answer()
            await prompt(q, context, "u_msg", "✉️ أرسل الرسالة التي تريد إيصالها لهذا المستخدم:", uid=target)
            return
        elif cmd == "uc":
            histories.pop(target, None)
            await q.answer("🗑 تم مسح ذاكرته")
        elif cmd == "ur":
            u["day"], u["day_count"] = "", 0
            users.save()
            await q.answer("🔄 تم تصفير عداد اليوم")
        elif cmd == "ux":
            u["model"], u["system"] = None, None
            users.save()
            await q.answer("♻️ تمت إعادة الضبط")
        text, kb = view_user(target)
        await safe_edit(q, text, kb)

    # ---------- البث ----------
    elif cmd == "bc":
        if not args:
            await q.answer()
            text, kb = bc_menu()
            await safe_edit(q, text, kb)
        else:
            await q.answer()
            await prompt(q, context, "bc_msg", "📢 أرسل الآن الرسالة التي تريد بثها (نص/صورة/فيديو/ملف...).", target=args[0])

    elif cmd == "bcx":
        context.bot_data.get("bc_pending", {}).pop(uid, None)
        await q.answer("تم الإلغاء")
        await safe_edit(q, "❌ تم إلغاء البث.", kb_back())

    elif cmd == "bcgo":
        pend = context.bot_data.get("bc_pending", {}).pop(uid, None)
        if not pend:
            await q.answer("انتهت صلاحية الطلب", show_alert=True)
            return
        if context.bot_data.get("bc_running"):
            await q.answer("يوجد بث يعمل الآن، انتظر حتى ينتهي", show_alert=True)
            return
        targets = bc_targets(pend["kind"])
        await q.answer("🚀 بدأ الإرسال")
        context.bot_data["bc_running"] = True
        await safe_edit(q, f"📤 جاري الإرسال إلى {len(targets)} مستخدم...", None)
        spawn(run_broadcast(bot, q.message, pend, targets, context.bot_data))

    # ---------- الموديلات ----------
    elif cmd == "models":
        await q.answer()
        text, kb = view_models_admin()
        await safe_edit(q, text, kb)

    elif cmd == "mdef":
        await q.answer()
        await prompt(q, context, "def_model", "⭐ أرسل جزءاً من اسم/معرّف الموديل الذي تريده افتراضياً (مثال: <code>llama</code>):")

    elif cmd == "mdefclr":
        settings["default_model"] = None
        await q.answer("🧹 أُلغي الموديل الافتراضي المخصص")
        text, kb = view_models_admin()
        await safe_edit(q, text, kb)

    elif cmd == "sd":
        mid = store.by_hash.get(args[0])
        if not mid:
            await q.answer("الموديل غير موجود، حدّث القائمة", show_alert=True)
            return
        settings["default_model"] = mid
        await q.answer("⭐ تم التعيين")
        text, kb = view_models_admin()
        await safe_edit(q, text, kb)

    elif cmd == "mhide":
        await q.answer()
        await prompt(q, context, "hide_model", "🙈 أرسل جزءاً من اسم الموديل الذي تريد إخفاءه/إظهاره:")

    elif cmd == "th":
        mid = store.by_hash.get(args[0])
        if not mid:
            await q.answer("الموديل غير موجود", show_alert=True)
            return
        hidden = settings.toggle_in("hidden_models", mid)
        await q.answer("🙈 تم إخفاؤه" if hidden else "✅ تم إظهاره")
        text, kb = view_models_admin()
        await safe_edit(q, text, kb)

    elif cmd == "mlist":
        await q.answer()
        hid = settings["hidden_models"][:25]
        rows = [[B(f"✅ إظهار: {short_name(store.models.get(m, {'name': m, 'id': m}), 36)}",
                   callback_data=f"ad:th:{md5s(m)}")] for m in hid]
        rows.append([B("🔙 الموديلات", callback_data="ad:models")])
        await safe_edit(q, f"📋 <b>الموديلات المخفية ({len(settings['hidden_models'])})</b>\n"
                        + ("اضغط لإظهار موديل:" if hid else "لا يوجد."), InlineKeyboardMarkup(rows))

    elif cmd == "mprem":
        await q.answer()
        await prompt(q, context, "prem_model",
                     "⭐ أرسل جزءاً من اسم الموديل لجعله حصرياً للمميزين أو إعادته عاماً:")

    elif cmd == "tp":
        mid = store.by_hash.get(args[0])
        if not mid:
            await q.answer("الموديل غير موجود", show_alert=True)
            return
        prem = settings.toggle_in("premium_models", mid)
        await q.answer("⭐ صار حصرياً للمميزين" if prem else "✅ صار متاحاً للجميع")
        text, kb = view_models_admin()
        await safe_edit(q, text, kb)

    elif cmd == "mplist":
        await q.answer()
        pl = settings["premium_models"][:25]
        rows = [[B(f"✅ إتاحة للجميع: {short_name(store.models.get(m, {'name': m, 'id': m}), 30)}",
                   callback_data=f"ad:tp:{md5s(m)}")] for m in pl]
        rows.append([B("🔙 الموديلات", callback_data="ad:models")])
        await safe_edit(q, f"⭐ <b>الموديلات الحصرية للمميزين ({len(settings['premium_models'])})</b>\n"
                        + ("اضغط لإتاحة موديل للجميع:" if pl else "لا يوجد."), InlineKeyboardMarkup(rows))

    elif cmd == "mcat":
        await q.answer()
        hid = set(settings["hidden_cats"])
        rows = [[B(f"{'🚫' if k in hid else '✅'} {label} ({len(store.category_models(k))})",
                   callback_data=f"ad:tc:{k}")] for k, label, _ in CATEGORIES if k != "all"]
        rows.append([B("🔙 الموديلات", callback_data="ad:models")])
        await safe_edit(q, "🗂 <b>إدارة الأقسام</b>\nاضغط لإخفاء/إظهار القسم من قائمة المستخدمين:", InlineKeyboardMarkup(rows))

    elif cmd == "tc":
        settings.toggle_in("hidden_cats", args[0])
        await q.answer("تم")
        hid = set(settings["hidden_cats"])
        rows = [[B(f"{'🚫' if k in hid else '✅'} {label} ({len(store.category_models(k))})",
                   callback_data=f"ad:tc:{k}")] for k, label, _ in CATEGORIES if k != "all"]
        rows.append([B("🔙 الموديلات", callback_data="ad:models")])
        await safe_edit(q, "🗂 <b>إدارة الأقسام</b>\nاضغط لإخفاء/إظهار القسم من قائمة المستخدمين:", InlineKeyboardMarkup(rows))

    elif cmd == "madd":
        await q.answer()
        await prompt(q, context, "add_extra",
                     "➕ أرسل <b>معرّف الموديل بالضبط</b> كما في OpenRouter (مثال: <code>openai/gpt-4o-mini</code>).\n"
                     "سيُضاف حتى لو كان مدفوعاً (سيُخصم من رصيدك).")

    elif cmd == "mext":
        await q.answer()
        rows = [[B(f"🗑 إزالة: {m[:40]}", callback_data=f"ad:xr:{md5s(m)}")] for m in settings["extra_models"]]
        rows.append([B("🔙 الموديلات", callback_data="ad:models")])
        await safe_edit(q, f"💎 <b>الموديلات المضافة يدوياً ({len(settings['extra_models'])})</b>\n"
                        + ("اضغط لإزالة موديل:" if rows[:-1] else "لا يوجد."), InlineKeyboardMarkup(rows))

    elif cmd == "xr":
        for m in list(settings["extra_models"]):
            if md5s(m) == args[0]:
                settings["extra_models"].remove(m)
                settings.save()
        await q.answer("🗑 أُزيل")
        try:
            await store.refresh()
        except Exception:
            pass
        text, kb = view_models_admin()
        await safe_edit(q, text, kb)

    elif cmd == "mref":
        await q.answer("⏳ جاري التحديث...")
        try:
            res = await store.refresh()
            await safe_edit(q, refresh_report(res), kb_back("ad:models", "🔙 الموديلات"))
        except Exception as e:
            await safe_edit(q, f"❌ فشل التحديث: {esc(str(e))}", kb_back("ad:models", "🔙 الموديلات"))

    # ---------- المزوّدون الإضافيون ----------
    elif cmd == "prov":
        await q.answer()
        text, kb = view_providers_admin()
        await safe_edit(q, text, kb)

    elif cmd == "padd":
        await q.answer()
        await prompt(q, context, "padd_name",
                     "➕ <b>إضافة مزوّد جديد</b> (OpenAI-compatible، أو ✨ Gemini Native إن كان رابطه "
                     "generativelanguage.googleapis.com — يُكتشف تلقائياً)\n\n"
                     "الخطوة 1/3 — أرسل اسم المزوّد (مثال: Groq):")

    elif cmd == "pknown":
        idx = int(args[0])
        if not (0 <= idx < len(KNOWN_PROVIDERS)):
            await q.answer("غير صالح", show_alert=True)
            return
        kp = KNOWN_PROVIDERS[idx]
        await q.answer()
        await prompt(q, context, "padd_key",
                     f"➕ إضافة {kp['icon']} <b>{esc(kp['name'])}</b>\n"
                     f"الرابط: <code>{esc(kp['base_url'])}</code>\n"
                     f"النوع: {'✨ Gemini Native' if kp['provider_type'] == 'gemini' else 'OpenAI-compatible'}\n\n"
                     "أرسل مفتاح API الخاص بك:",
                     name=kp["name"], base_url=kp["base_url"],
                     provider_type=kp["provider_type"], icon=kp["icon"])

    elif cmd == "ptg":
        p = provider_by_id(args[0])
        if not p:
            await q.answer("المزوّد غير موجود", show_alert=True)
            return
        p["enabled"] = not p.get("enabled", True)
        settings.save()
        await q.answer("▶️ تم التفعيل" if p["enabled"] else "⏸ تم التعطيل")
        try:
            await store.refresh()
        except Exception:
            pass
        text, kb = view_providers_admin()
        await safe_edit(q, text, kb)

    elif cmd == "pdel":
        p = provider_by_id(args[0])
        if not p:
            await q.answer("المزوّد غير موجود", show_alert=True)
            return
        settings["providers"] = [x for x in settings["providers"] if x["id"] != args[0]]
        await q.answer(f"🗑 حُذف {p['name']}")
        try:
            await store.refresh()
        except Exception:
            pass
        text, kb = view_providers_admin()
        await safe_edit(q, text, kb)

    elif cmd == "ptest":
        p = provider_by_id(args[0])
        if not p:
            await q.answer("المزوّد غير موجود", show_alert=True)
            return
        await q.answer("⏳ جاري الاختبار...")
        t = time.time()
        ptype = provider_type_of(p)
        headers = gemini_headers(p) if ptype == "gemini" else provider_headers(p)
        try:
            r = await http.get(f"{p['base_url'].rstrip('/')}/models", headers=headers, timeout=15)
            js = r.json() if r.status_code < 400 else {}
            if ptype == "gemini":
                ms = js.get("models", [])
                sample = "، ".join(x.get("name", "").split("/", 1)[-1] for x in ms[:5])
            else:
                ms = js.get("data", [])
                sample = "، ".join(m.get("id", "") for m in ms[:5])
            ok = r.status_code < 400
            type_tag = " (✨ Gemini Native)" if ptype == "gemini" else ""
            msg = (f"{'✅' if ok else '❌'} {p['name']}{type_tag} — كود {r.status_code} — {int((time.time()-t)*1000)}ms\n"
                   f"عدد الموديلات: {len(ms)}\n{esc(sample) if ok else esc((r.text or '')[:200])}")
        except Exception as e:
            msg = f"❌ {p['name']} — فشل الاتصال: {esc(str(e)[:200])}"
        await context.bot.send_message(uid, msg, parse_mode=ParseMode.HTML)
        text, kb = view_providers_admin()
        await safe_edit(q, text, kb)

    # ---------- الإعدادات ----------
    elif cmd == "set":
        await q.answer()
        text, kb = view_settings()
        await safe_edit(q, text, kb)

    elif cmd == "tg":
        key = args[0]
        if key not in TOGGLES:
            await q.answer()
            return
        settings[key] = not settings[key]
        await q.answer(f"{TOGGLES[key]}: {'مفعّل' if settings[key] else 'معطّل'}")
        text, kb = view_settings()
        await safe_edit(q, text, kb)

    elif cmd == "sp":
        key = args[0]
        if key not in SETTING_SPECS:
            await q.answer()
            return
        await q.answer()
        await prompt(q, context, f"set:{key}", SETTING_SPECS[key][0])

    # ---------- المشرفون ----------
    elif cmd in ("adm", "ada", "adr"):
        if not is_owner(uid):
            await q.answer("⛔ هذه الصفحة للمالك فقط", show_alert=True)
            return
        if cmd == "ada":
            await q.answer()
            await prompt(q, context, "add_admin", "➕ أرسل معرف (ID) المشرف الجديد (رقم). يمكنه معرفته بإرسال /id للبوت.")
            return
        if cmd == "adr":
            rid = int(args[0])
            if rid in [int(x) for x in settings["admins"]]:
                settings["admins"] = [x for x in settings["admins"] if int(x) != rid]
            await q.answer("🗑 أُزيل المشرف")
        else:
            await q.answer()
        text, kb = view_admins()
        await safe_edit(q, text, kb)

    # ---------- السجلات والأدوات ----------
    elif cmd == "logs":
        await q.answer()
        await safe_edit(q, logs_text(), InlineKeyboardMarkup([
            [B("🗑 مسح السجل", callback_data="ad:logclr"), B("🔄 تحديث", callback_data="ad:logs")],
            [B("🔙 لوحة التحكم", callback_data="ad:home")]]))

    elif cmd == "logclr":
        stats.data["errors"] = []
        stats.flush(True)
        await q.answer("تم المسح")
        await safe_edit(q, logs_text(), kb_back())

    elif cmd == "tools":
        await q.answer()
        text, kb = view_tools()
        await safe_edit(q, text, kb)

    elif cmd == "bk":
        await q.answer("⏳ جاري التجهيز...")
        users.flush(True)
        stats.flush(True)
        for name, data in (("users.json", users.data), ("settings.json", settings.data), ("stats.json", stats.data)):
            await bot.send_document(q.message.chat_id, io.BytesIO(json.dumps(data, ensure_ascii=False, indent=1).encode()),
                                    filename=name)

    elif cmd == "csv":
        await q.answer("⏳ جاري التجهيز...")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "name", "username", "joined", "last_seen", "messages", "tokens", "banned", "allowed", "model"])
        for u_id, u in users.all():
            w.writerow([u_id, u["first_name"], u["username"], fmt_dt(u["joined"]), fmt_dt(u["last_seen"]),
                        u["msg_count"], u["tokens"], u["banned"], u["allowed"], u["model"] or ""])
        await bot.send_document(q.message.chat_id, io.BytesIO(("\ufeff" + buf.getvalue()).encode("utf-8")), filename="users.csv")

    elif cmd == "clh":
        n = len(histories)
        histories.clear()
        await q.answer(f"🧹 تم مسح ذاكرة {n} محادثة", show_alert=True)

    elif cmd == "stclr":
        await q.answer()
        await safe_edit(q, "⚠️ هل تريد فعلاً تصفير كل الإحصائيات؟", InlineKeyboardMarkup([
            [B("✅ نعم، صفّر", callback_data="ad:stclr2"), B("❌ لا", callback_data="ad:tools")]]))

    elif cmd == "stclr2":
        stats.reset()
        await q.answer("♻️ تم التصفير")
        text, kb = view_tools()
        await safe_edit(q, text, kb)

    else:
        await q.answer()


# ---------------------------------- استقبال مدخلات الأدمن (نصوص) ----------------------------------
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE, st: dict):
    msg = update.message
    bot = context.bot
    kind = st["kind"]
    text = (msg.text or msg.caption or "").strip()
    H = ParseMode.HTML

    if kind == "bc_msg":
        context.bot_data.setdefault("bc_pending", {})[msg.from_user.id] = {
            "chat": msg.chat_id, "msg": msg.message_id, "kind": st["target"]}
        n = len(bc_targets(st["target"]))
        await bot.copy_message(msg.chat_id, msg.chat_id, msg.message_id)
        await msg.reply_text(
            f"👆 معاينة الرسالة.\nسيتم الإرسال إلى <b>{n}</b> مستخدم. هل تؤكد؟", parse_mode=H,
            reply_markup=InlineKeyboardMarkup([[B(f"✅ إرسال ({n})", callback_data="ad:bcgo"),
                                                B("❌ إلغاء", callback_data="ad:bcx")]]))

    elif kind == "find_user":
        res = users.find(text)[:15]
        if not res:
            await msg.reply_text("🔎 لا توجد نتائج. جرّب مرة أخرى أو /cancel")
            return
        if len(res) == 1:
            t, kb = view_user(res[0][0])
            await msg.reply_text(t, parse_mode=H, reply_markup=kb)
        else:
            rows = [[B(f"{'🚫' if u['banned'] else '👤'} {(u['first_name'] or u['username'] or str(i))[:18]} · {i}",
                       callback_data=f"ad:u:{i}")] for i, u in res]
            rows.append([B("🔙 لوحة التحكم", callback_data="ad:home")])
            await msg.reply_text(f"🔎 النتائج ({len(res)}):", reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "u_limit":
        if text.lower() in ("reset", "-", "default"):
            val = None
        elif text.isdigit():
            val = int(text)
        else:
            await msg.reply_text("⚠️ أرسل رقماً صحيحاً أو reset")
            return
        users.get(st["uid"])["limit"] = val
        users.save()
        t, kb = view_user(st["uid"])
        await msg.reply_text("✅ تم التحديث.\n\n" + t, parse_mode=H, reply_markup=kb)

    elif kind == "u_points":
        u = users.get(st["uid"])
        raw = text.strip()
        try:
            if raw.startswith(("+", "-")):
                u["points"] = max(0, int(u.get("points", 0)) + int(raw))
            else:
                u["points"] = max(0, int(raw))
        except ValueError:
            await msg.reply_text("⚠️ أرسل رقماً صحيحاً، أو بعلامة + أو - مثل +10")
            return
        users.save()
        t, kb = view_user(st["uid"])
        await msg.reply_text("✅ تم تحديث النقاط.\n\n" + t, parse_mode=H, reply_markup=kb)

    elif kind == "u_msg":
        target = st["uid"]
        try:
            if msg.text:
                await bot.send_message(target, "📩 <b>رسالة من الإدارة</b>\n\n" + esc(text), parse_mode=H)
            else:
                await bot.copy_message(target, msg.chat_id, msg.message_id)
            await msg.reply_text("✅ تم إرسال الرسالة.", reply_markup=kb_back(f"ad:u:{target}", "🔙 المستخدم"))
        except Forbidden:
            users.get(target)["blocked_bot"] = True
            await msg.reply_text("🚫 المستخدم حظر البوت، تعذّر الإرسال.")
        except TelegramError as e:
            await msg.reply_text(f"❌ فشل الإرسال: {e}")

    elif kind in ("def_model", "hide_model", "prem_model"):
        ql = text.lower()
        res = [m for m in store.sorted_models(store.models.values())
               if ql and (ql in m["raw_id"].lower() or ql in m["name"].lower())][:15]
        if not res:
            await msg.reply_text("🔎 لا توجد نتائج. جرّب كلمة أخرى أو /cancel")
            return
        rows = []
        for m in res:
            h = md5s(m["id"])
            if kind == "def_model":
                rows.append([B(f"⭐ {short_name(m, 38)}", callback_data=f"ad:sd:{h}")])
            elif kind == "hide_model":
                hid = settings.is_hidden(m["id"])
                rows.append([B(f"{'✅ إظهار' if hid else '🚫 إخفاء'}: {short_name(m, 30)}", callback_data=f"ad:th:{h}")])
            else:
                prem = m["id"] in settings["premium_models"]
                rows.append([B(f"{'✅ إتاحة للجميع' if prem else '⭐ حصر للمميزين'}: {short_name(m, 26)}", callback_data=f"ad:tp:{h}")])
        rows.append([B("🔙 الموديلات", callback_data="ad:models")])
        await msg.reply_text(f"🔎 النتائج ({len(res)}) — اضغط لاختيار الموديل:", reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "add_extra":
        raw = await fetch_all_models_raw()
        mid = text.strip()
        hit = next((m for m in raw if m.get("id") == mid), None)
        if not hit:
            sugg = [m["id"] for m in raw if mid and mid.lower() in m["id"].lower()][:10]
            extra = ("\n\nهل تقصد:\n" + "\n".join(f"<code>{esc(s)}</code>" for s in sugg)) if sugg else ""
            await msg.reply_text("❌ لم أجد موديلاً بهذا المعرّف بالضبط." + extra, parse_mode=H)
            return
        if mid not in settings["extra_models"]:
            settings["extra_models"].append(mid)
            settings.save()
        await store.refresh()
        await msg.reply_text(f"✅ تمت إضافة <code>{esc(mid)}</code> وسيظهر في قسم «الكل».", parse_mode=H,
                             reply_markup=kb_back("ad:models", "🔙 الموديلات"))

    elif kind.startswith("set:"):
        name = kind[4:]
        typ = SETTING_SPECS[name][1]
        if typ == "int":
            if not text.isdigit():
                await msg.reply_text("⚠️ أرسل رقماً صحيحاً.")
                return
            val = int(text)
            if name == "history_len" and not (2 <= val <= 60):
                await msg.reply_text("⚠️ القيمة يجب أن تكون بين 2 و 60.")
                return
            settings[name] = val
        elif typ == "channel":
            if text.lower() in ("off", "reset", "-"):
                settings["force_sub"] = ""
                settings["force_sub_link"] = ""
            else:
                try:
                    chat = await bot.get_chat(text if text.startswith("@") or not text.lstrip("-").isdigit() else int(text))
                    me = await bot.get_chat_member(chat.id, bot.id)
                    if str(me.status) not in ("administrator", "creator"):
                        await msg.reply_text("⚠️ البوت ليس مشرفاً في هذه القناة. اجعله مشرفاً ثم أعد المحاولة.")
                        return
                except Exception as e:
                    await msg.reply_text(f"❌ تعذّر الوصول للقناة: {e}\nتأكد من المعرف وأن البوت مشرف فيها.")
                    return
                settings["force_sub"] = f"@{chat.username}" if chat.username else chat.id
                link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
                if not link:
                    try:
                        link = await bot.export_chat_invite_link(chat.id)
                    except Exception:
                        link = ""
                settings["force_sub_link"] = link
                _sub_cache.clear()
        else:
            settings[name] = SETTINGS_DEFAULT[name] if text.lower() == "reset" else text[:3000]
        t, kb = view_settings()
        await msg.reply_text("✅ تم الحفظ.\n\n" + t, parse_mode=H, reply_markup=kb)

    elif kind == "padd_name":
        name = text.strip()[:60]
        if not name:
            await msg.reply_text("⚠️ الاسم فارغ، أرسل اسماً صحيحاً أو /cancel")
            return
        context.user_data["await"] = {"kind": "padd_url", "name": name}
        await msg.reply_text(
            f"✅ الاسم: {esc(name)}\n\n"
            "الخطوة 2/3 — أرسل رابط الموديلات (Base URL)\n"
            "مثال: <code>https://api.groq.com/openai/v1</code>", parse_mode=H)
        return

    elif kind == "padd_url":
        base_url = text.strip().rstrip("/")
        if not re.match(r"^https?://\S+$", base_url):
            await msg.reply_text("⚠️ الرابط غير صحيح، يجب أن يبدأ بـ http:// أو https:// — أعد الإرسال أو /cancel")
            return
        if any(p["base_url"].rstrip("/") == base_url for p in settings["providers"]):
            await msg.reply_text("⚠️ يوجد مزوّد مضاف بنفس هذا الرابط مسبقاً. أرسل رابطاً آخر أو /cancel")
            return
        context.user_data["await"] = {"kind": "padd_key", "name": st["name"], "base_url": base_url}
        await msg.reply_text(
            f"✅ الرابط: <code>{esc(base_url)}</code>\n\nالخطوة 3/3 — أرسل مفتاح API الخاص بهذا المزوّد:", parse_mode=H)
        return

    elif kind == "padd_key":
        api_key = text.strip()
        if not api_key:
            await msg.reply_text("⚠️ المفتاح فارغ، أرسل المفتاح أو /cancel")
            return
        ptype = st.get("provider_type") or detect_provider_type(st["base_url"])
        icon = st.get("icon") or ("✨" if ptype == "gemini" else "🔌")
        p = {"id": gen_provider_id(), "name": st["name"], "base_url": st["base_url"], "api_key": api_key,
             "enabled": True, "icon": icon, "provider_type": ptype}
        settings["providers"] = settings["providers"] + [p]
        found, err = 0, None
        try:
            res = await store.refresh()
            found = sum(1 for m in store.models.values() if m["src"] == p["id"])
            if res.get("errors"):
                err = " | ".join(res["errors"])
        except Exception as e:
            err = str(e)
        type_tag = " ✨ Gemini Native" if ptype == "gemini" else ""
        report = f"✅ تمت إضافة <b>{esc(p['name'])}</b>{type_tag}\nعدد الموديلات المكتشفة: <b>{found}</b>"
        if found == 0:
            report += ("\n⚠️ لم يُعثر على أي موديل — تحقّق من صحة الرابط والمفتاح "
                       "(جرّب زر 🩺 اختبار من قائمة المزوّدين).")
        if err:
            report += f"\n⚠️ {esc(err[:300])}"
        t, kb = view_providers_admin()
        await msg.reply_text(report + "\n\n" + t, parse_mode=H, reply_markup=kb)

    elif kind == "add_admin":
        if not is_owner(msg.from_user.id):
            await msg.reply_text("⛔ للمالك فقط.")
        elif not text.lstrip("-").isdigit():
            await msg.reply_text("⚠️ أرسل معرفاً رقمياً صحيحاً.")
            return
        else:
            new = int(text)
            if new not in ADMIN_IDS and new not in [int(x) for x in settings["admins"]]:
                settings["admins"] = list(settings["admins"]) + [new]
            t, kb = view_admins()
            await msg.reply_text("✅ تمت الإضافة.\n\n" + t, parse_mode=H, reply_markup=kb)

    context.user_data.pop("await", None)


async def admin_input_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    if not msg or not user or not is_admin(user.id):
        return
    st = context.user_data.get("await")
    if not st:
        return
    try:
        await handle_admin_input(update, context, st)
    except Exception as e:
        log.exception("admin input error")
        context.user_data.pop("await", None)
        await msg.reply_text(f"⚠️ خطأ: {e}")
    raise ApplicationHandlerStop


# ---------------------------------- أوامر الأدمن ----------------------------------
async def admin_only(update: Update) -> bool:
    if not await guard(update):
        return False
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return False
    return True


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(f"🆔 معرفك: {u.id}\n💬 معرف المحادثة: {update.effective_chat.id}")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.pop("await", None):
        await update.message.reply_text("❌ تم إلغاء العملية.")
    else:
        await update.message.reply_text("لا توجد عملية لإلغائها.")


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    context.user_data.pop("await", None)
    await update.message.reply_text(admin_home_text(), parse_mode=ParseMode.HTML,
                                    reply_markup=kb_admin_home(update.effective_user.id))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await admin_only(update):
        await update.message.reply_text(stats_text(), parse_mode=ParseMode.HTML)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await admin_only(update):
        text, kb = bc_menu()
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


def _arg_uid(context) -> int | None:
    a = context.args[0] if context.args else ""
    return int(a) if a.lstrip("-").isdigit() else None


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    target = _arg_uid(context)
    if target is None:
        await update.message.reply_text("الاستخدام: /ban ID [السبب]")
        return
    if is_admin(target):
        await update.message.reply_text("⛔ لا يمكن حظر مشرف.")
        return
    u = users.get(target)
    u["banned"], u["ban_reason"] = True, " ".join(context.args[1:])
    users.save()
    await update.message.reply_text(f"🚫 تم حظر {target}.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    target = _arg_uid(context)
    if target is None:
        await update.message.reply_text("الاستخدام: /unban ID")
        return
    u = users.get(target)
    u["banned"], u["ban_reason"] = False, ""
    users.save()
    await update.message.reply_text(f"✅ تم فك الحظر عن {target}.")


async def _set_allow(update, context, value: bool):
    if not await admin_only(update):
        return
    target = _arg_uid(context)
    if target is None:
        await update.message.reply_text(f"الاستخدام: /{'allow' if value else 'disallow'} ID")
        return
    users.get(target)["allowed"] = value
    users.save()
    await update.message.reply_text(("🔒 تمت إضافة " if value else "➖ تمت إزالة ") + f"{target} " + ("للمسموحين." if value else "من المسموحين."))


async def cmd_allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_allow(update, context, True)


async def cmd_disallow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_allow(update, context, False)


async def cmd_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    q = " ".join(context.args)
    res = users.find(q)[:15]
    if not res:
        await update.message.reply_text("الاستخدام: /user ID أو @يوزر أو اسم\n(لا توجد نتائج)")
    elif len(res) == 1:
        t, kb = view_user(res[0][0])
        await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        rows = [[B(f"{(u['first_name'] or u['username'] or str(i))[:18]} · {i}", callback_data=f"ad:u:{i}")] for i, u in res]
        await update.message.reply_text(f"🔎 النتائج ({len(res)}):", reply_markup=InlineKeyboardMarkup(rows))


async def flush_job(context: ContextTypes.DEFAULT_TYPE):
    users.flush()
    stats.flush()


# ==========================================================================
#                    التحديث التلقائي + الإشعارات
# ==========================================================================
async def auto_refresh_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        res = await store.refresh()
    except Exception as e:
        log.warning("Auto refresh failed: %s", e)
        return
    log.info("Auto refresh OK: %d models (+%d)", res["total"], len(res["added"]))
    if res["added"] and settings["notify_new_models"] and all_admin_ids():
        text = "🔔 <b>نزلت موديلات مجانية جديدة!</b>\n\n" + refresh_report(res)
        for admin in all_admin_ids():
            try:
                await context.bot.send_message(admin, text, parse_mode=ParseMode.HTML)
            except Exception:
                pass


# ==========================================================================
#                        🌐 لوحة التحكم عبر الويب
# ==========================================================================
# كل المنطق في دوال op_* (تأخذ dict وترجع dict) وطبقة aiohttp رقيقة فوقها.
WEB_COOKIE = "orb_sid"
WEB_SESSION_TTL = 12 * 3600
WEB_STARTED_AT = time.time()
BOT_REF: dict = {"bot": None, "runner": None}
SESSIONS: dict[str, dict] = {}
LOGIN_FAILS: dict[str, list] = {}
AUDIT_FILE = DATA_DIR / "audit.json"
audit_log: list = _load_json(AUDIT_FILE, [])
BC_STATE = {"running": False, "total": 0, "sent": 0, "failed": 0, "blocked": 0,
            "started": 0, "finished": 0, "target": ""}


class WebError(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.msg = msg
        self.status = status


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def client_ip(req) -> str:
    try:
        if WEB_TRUST_PROXY:
            xf = req.headers.get("X-Forwarded-For", "")
            if xf:
                return xf.split(",")[0].strip()
        return req.remote or "?"
    except Exception:
        return "?"


def audit(action: str, detail: str = "", ip: str = ""):
    audit_log.append({"t": time.time(), "a": action, "d": str(detail)[:300], "ip": ip})
    del audit_log[:-300]
    _save_json(AUDIT_FILE, audit_log)


# ---------------------------------- الجلسات ----------------------------------
def new_session(ip: str) -> tuple[str, dict]:
    now = time.time()
    for k in [k for k, s in SESSIONS.items() if s["exp"] < now]:
        SESSIONS.pop(k, None)
    tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = {"csrf": secrets.token_urlsafe(24), "exp": now + WEB_SESSION_TTL, "ip": ip}
    return tok, SESSIONS[tok]


def get_session(tok: str | None) -> dict | None:
    if not tok:
        return None
    s = SESSIONS.get(tok)
    if not s or s["exp"] < time.time():
        SESSIONS.pop(tok, None)
        return None
    s["exp"] = time.time() + WEB_SESSION_TTL
    return s


def check_password(pw: str) -> bool:
    return hmac.compare_digest(pw.encode("utf-8"), WEB_PASSWORD.encode("utf-8"))


def login_locked(ip: str) -> int:
    rec = LOGIN_FAILS.get(ip)
    if rec and rec[1] > time.time():
        return int(rec[1] - time.time()) + 1
    return 0


def login_failed(ip: str):
    rec = LOGIN_FAILS.get(ip) or [0, 0]
    rec[0] += 1
    if rec[0] >= 5:
        rec = [0, time.time() + 300]
    LOGIN_FAILS[ip] = rec
    if len(LOGIN_FAILS) > 500:
        LOGIN_FAILS.clear()


# ---------------------------------- تحويل البيانات ----------------------------------
def model_raw(mid: str) -> str:
    m = store.models.get(mid)
    return m["raw_id"] if m else (mid or "")


def user_row(uid: int, u: dict) -> dict:
    prem = u["tier"] == "premium"
    limit = u["limit"] if u["limit"] is not None else (
        settings["limit_premium"] if prem else settings["limit_normal"])
    return {
        "id": str(uid), "name": u["first_name"], "username": u["username"], "tier": u["tier"],
        "banned": u["banned"], "ban_reason": u["ban_reason"], "allowed": u["allowed"],
        "blocked_bot": u["blocked_bot"], "msgs": u["msg_count"], "tokens": u["tokens"],
        "points": u["points"], "referrals": u["referrals"], "invited_by": u["invited_by"],
        "joined": u["joined"], "last": u["last_seen"], "today": users.used_today(uid),
        "limit": limit, "limit_custom": u["limit"],
        "model": model_raw(u["model"]) if u["model"] else "",
    }


def model_row(m: dict) -> dict:
    return {
        "id": m["id"], "raw": m["raw_id"], "name": m["name"], "src": m["src"], "prov": m["prov"],
        "ctx": m["context"], "in": m["in"], "out": m["out"],
        "hidden": settings.is_hidden(m["id"]),
        "premium": m["id"] in settings["premium_models"],
        "default": m["id"] == settings["default_model"],
    }


# ---------------------------------- العمليات ----------------------------------
async def op_me(data, req=None):
    return {"ok": True, "csrf": req["sess"]["csrf"] if req is not None else ""}


async def op_stats(data, req=None):
    us = users.all()
    now, t, d = time.time(), today_str(), stats.data
    days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(13, -1, -1)]
    joined: dict[str, int] = {}
    for _, u in us:
        k = day_of(u["joined"])
        joined[k] = joined.get(k, 0) + 1
    daily = [{"day": x[5:], "msgs": d["daily"].get(x, {}).get("msgs", 0),
              "tokens": d["daily"].get(x, {}).get("tokens", 0), "new": joined.get(x, 0)} for x in days]
    counts = store.models_count_by_src()
    td = d["daily"].get(t, {"msgs": 0, "tokens": 0})
    top_m = sorted(d["models"].items(), key=lambda kv: -kv[1])[:8]
    top_u = [x for x in sorted(us, key=lambda x: -x[1]["msg_count"])[:8] if x[1]["msg_count"]]
    return {
        "users": len(us),
        "active24": sum(1 for _, u in us if now - u["last_seen"] < 86400),
        "active7": sum(1 for _, u in us if now - u["last_seen"] < 7 * 86400),
        "new_today": sum(1 for _, u in us if day_of(u["joined"]) == t),
        "premium": sum(1 for _, u in us if u["tier"] == "premium"),
        "banned": sum(1 for _, u in us if u["banned"]),
        "blocked": sum(1 for _, u in us if u["blocked_bot"]),
        "points_total": sum(int(u["points"]) for _, u in us),
        "referrals_total": sum(int(u["referrals"]) for _, u in us),
        "msgs_today": td["msgs"], "tokens_today": td["tokens"],
        "total_msgs": d["total_msgs"], "total_tokens": d["total_tokens"], "errors": d["total_errors"],
        "models": {"total": len(store.models), "visible": len(store.visible()),
                   "or": counts.get("or", 0), "cd": counts.get("cd", 0), "extra": extra_src_total(counts),
                   "hidden": len(settings["hidden_models"]), "premium": len(settings["premium_models"])},
        "daily": daily,
        "top_models": [{"name": model_raw(k), "n": v} for k, v in top_m],
        "top_users": [{"id": str(uid), "name": u["first_name"] or u["username"] or str(uid),
                       "n": u["msg_count"]} for uid, u in top_u],
        "flags": {"maintenance": settings["maintenance"], "private": settings["private_mode"],
                  "force_sub": str(settings["force_sub"] or "")},
        "limits": {"normal": settings["limit_normal"], "premium": settings["limit_premium"],
                   "ref": settings["ref_points"]},
        "uptime": int(now - WEB_STARTED_AT), "bc_running": BC_STATE["running"],
        "models_updated": store.updated_at, "conduit": conduit_enabled(),
    }


async def op_users(data, req=None):
    f = data.get("f", "all")
    q = str(data.get("q") or "").strip().lower().lstrip("@")
    page = max(1, _int(data.get("page"), 1))
    size = min(100, max(5, _int(data.get("size"), 20)))
    lst = users.filtered(f if f in ("act", "new", "ban", "alw", "prem") else "all")
    if q:
        lst = [(i, u) for i, u in lst
               if q in str(i) or q in (u["username"] or "").lower() or q in (u["first_name"] or "").lower()]
    keys = {"msgs": lambda x: -x[1]["msg_count"], "points": lambda x: -x[1]["points"],
            "joined": lambda x: -x[1]["joined"], "tokens": lambda x: -x[1]["tokens"]}
    lst = sorted(lst, key=keys.get(data.get("sort"), lambda x: -x[1]["last_seen"]))
    total = len(lst)
    pages = max(1, math.ceil(total / size))
    page = min(page, pages)
    return {"total": total, "page": page, "pages": pages,
            "users": [user_row(i, u) for i, u in lst[(page - 1) * size:page * size]]}


async def op_user_get(data, req=None):
    uid = _int(data.get("id"))
    if uid is None or not users.exists(uid):
        raise WebError("المستخدم غير موجود", 404)
    return {"user": user_row(uid, users.get(uid))}


async def op_user_action(data, req=None):
    uid = _int(data.get("id"))
    if uid is None or not users.exists(uid):
        raise WebError("المستخدم غير موجود", 404)
    a, v = str(data.get("action", "")), data.get("value")
    u = users.get(uid)
    if a == "ban":
        if is_admin(uid):
            raise WebError("لا يمكن حظر مشرف")
        u["banned"], u["ban_reason"] = True, str(v or "بقرار الإدارة")[:200]
    elif a == "unban":
        u["banned"], u["ban_reason"] = False, ""
    elif a == "tier":
        if v not in ("normal", "premium"):
            raise WebError("فئة غير صحيحة")
        u["tier"] = v
    elif a == "allow":
        u["allowed"] = bool(v)
    elif a == "points":
        raw = str(v).strip()
        try:
            u["points"] = max(0, int(u["points"]) + int(raw)) if raw.startswith(("+", "-")) else max(0, int(raw))
        except ValueError:
            raise WebError("قيمة النقاط غير صحيحة")
    elif a == "limit":
        raw = str(v if v is not None else "").strip()
        if raw == "" or raw.lower() == "reset":
            u["limit"] = None
        elif raw.isdigit():
            u["limit"] = int(raw)
        else:
            raise WebError("الحد غير صحيح")
    elif a == "clear":
        histories.pop(uid, None)
    elif a == "reset_day":
        u["day"], u["day_count"] = "", 0
    elif a == "reset_user":
        u["model"], u["system"] = None, None
    elif a == "message":
        text = str(v or "").strip()
        if not text:
            raise WebError("الرسالة فارغة")
        try:
            await BOT_REF["bot"].send_message(uid, "📩 رسالة من الإدارة\n\n" + text[:3500])
        except Forbidden:
            u["blocked_bot"] = True
            users.save()
            raise WebError("المستخدم حظر البوت، تعذّر الإرسال")
        except TelegramError as e:
            raise WebError(f"فشل الإرسال: {e}")
    else:
        raise WebError("إجراء غير معروف")
    users.save()
    audit(f"user:{a}", f"{uid}" + ("" if a == "message" else f" {str(v)[:60]}"), client_ip(req))
    return {"ok": True, "user": user_row(uid, u)}


async def op_models(data, req=None):
    rows = sorted(store.models.values(), key=lambda m: (m["src"], m["name"].lower()))
    return {"models": [model_row(m) for m in rows], "default": store.default_model(),
            "updated": store.updated_at}


async def op_model_action(data, req=None):
    mid, a = data.get("id"), str(data.get("action", ""))
    m = store.models.get(mid)
    if not m:
        raise WebError("الموديل غير موجود", 404)
    if a == "hide":
        settings.toggle_in("hidden_models", mid)
    elif a == "premium":
        settings.toggle_in("premium_models", mid)
    elif a == "default":
        settings["default_model"] = mid
    elif a == "undefault":
        settings["default_model"] = None
    else:
        raise WebError("إجراء غير معروف")
    audit(f"model:{a}", m["raw_id"], client_ip(req))
    return {"ok": True, "model": model_row(m), "default": store.default_model()}


async def op_models_refresh(data, req=None):
    try:
        res = await store.refresh()
    except Exception as e:
        raise WebError(f"فشل التحديث: {e}", 502)
    audit("models:refresh", f"total={res['total']} +{len(res['added'])}", client_ip(req))
    return {"total": res["total"], "errors": res.get("errors", []), "removed": res["removed"][:30],
            "added": [{"raw": m["raw_id"], "name": m["name"], "src": m["src"]} for m in res["added"][:50]]}


# ---------------------------------- مزوّدون (OpenRouter/Conduit المدمجان + مزوّدون مخصّصون) ----------------------------------
def provider_row(p: dict) -> dict:
    n = store.models_count_by_src().get(p["id"], 0)
    return {"id": p["id"], "name": p["name"], "base_url": p["base_url"], "key_masked": mask_key(p["api_key"]),
            "enabled": p.get("enabled", True), "icon": p.get("icon", "🔌"), "models": n, "custom": True,
            "provider_type": provider_type_of(p)}


async def op_providers(data, req=None):
    or_n = store.models_count_by_src().get("or", 0)
    cd_n = store.models_count_by_src().get("cd", 0)
    builtin = [
        {"id": "or", "name": "OpenRouter", "base_url": OR_BASE,
         "key_masked": mask_key(OPENROUTER_API_KEY) if "ضع_" not in OPENROUTER_API_KEY else "", "enabled": True,
         "icon": "🆓", "models": or_n, "custom": False, "provider_type": "openai_compatible",
         "configured": "ضع_" not in OPENROUTER_API_KEY},
        {"id": "cd", "name": "Conduit", "base_url": CONDUIT_BASE_URL,
         "key_masked": mask_key(CONDUIT_API_KEY) if conduit_enabled() else "", "enabled": conduit_enabled(),
         "icon": "🧭", "models": cd_n, "custom": False, "provider_type": "openai_compatible",
         "configured": conduit_enabled()},
    ]
    return {"providers": builtin + [provider_row(p) for p in settings["providers"]],
            "known": KNOWN_PROVIDERS}


def _validate_provider_fields(name, base_url, api_key):
    name = str(name or "").strip()[:60]
    base_url = str(base_url or "").strip().rstrip("/")
    api_key = str(api_key or "").strip()
    if not name:
        raise WebError("اسم المزوّد مطلوب")
    if not re.match(r"^https?://[^\s]+$", base_url):
        raise WebError("رابط الموديلات (Base URL) غير صحيح — يجب أن يبدأ بـ http:// أو https://")
    if not api_key:
        raise WebError("مفتاح API مطلوب")
    return name, base_url, api_key


def _norm_provider_type(v, base_url: str) -> str:
    v = str(v or "").strip()
    return v if v in ("openai_compatible", "gemini") else detect_provider_type(base_url)


async def op_provider_add(data, req=None):
    name, base_url, api_key = _validate_provider_fields(data.get("name"), data.get("base_url"), data.get("api_key"))
    if any(p["base_url"].rstrip("/") == base_url for p in settings["providers"]):
        raise WebError("يوجد مزوّد مضاف بنفس الرابط مسبقاً")
    ptype = _norm_provider_type(data.get("provider_type"), base_url)
    p = {"id": gen_provider_id(), "name": name, "base_url": base_url, "api_key": api_key,
         "enabled": True, "icon": str(data.get("icon") or ("✨" if ptype == "gemini" else "🔌"))[:4],
         "provider_type": ptype}
    settings["providers"] = settings["providers"] + [p]
    audit("provider:add", f"{name} {base_url} ({ptype})", client_ip(req))
    try:
        res = await store.refresh()
        found = sum(1 for m in store.models.values() if m["src"] == p["id"])
        return {"ok": True, "provider": provider_row(p), "models_found": found, "refresh_errors": res.get("errors", [])}
    except Exception as e:
        return {"ok": True, "provider": provider_row(p), "models_found": 0, "refresh_errors": [str(e)]}


async def op_provider_update(data, req=None):
    pid = str(data.get("id") or "")
    p = provider_by_id(pid)
    if not p:
        raise WebError("المزوّد غير موجود", 404)
    changed = False
    if "enabled" in data:
        p["enabled"] = bool(data["enabled"])
        changed = True
    if any(k in data for k in ("name", "base_url", "api_key", "provider_type")):
        name = data.get("name", p["name"])
        base_url = data.get("base_url", p["base_url"])
        api_key = data.get("api_key") or p["api_key"]  # مفتاح فارغ = إبقاء القديم
        name, base_url, api_key = _validate_provider_fields(name, base_url, api_key)
        # يُحدَّد النوع صراحة إن أُرسل، وإلا يُعاد تخمينه فقط عند تغيّر الرابط
        ptype = str(data.get("provider_type") or "").strip()
        if ptype not in ("openai_compatible", "gemini"):
            ptype = provider_type_of(p) if base_url == p["base_url"].rstrip("/") else detect_provider_type(base_url)
        p.update(name=name, base_url=base_url, api_key=api_key, provider_type=ptype)
        changed = True
    if changed:
        settings.save()
        audit("provider:update", pid, client_ip(req))
        try:
            await store.refresh()
        except Exception:
            pass
    return {"ok": True, "provider": provider_row(p)}


async def op_provider_delete(data, req=None):
    pid = str(data.get("id") or "")
    p = provider_by_id(pid)
    if not p:
        raise WebError("المزوّد غير موجود", 404)
    settings["providers"] = [x for x in settings["providers"] if x["id"] != pid]
    audit("provider:delete", f"{pid} {p['name']}", client_ip(req))
    try:
        await store.refresh()
    except Exception:
        pass
    return {"ok": True}


async def op_provider_test(data, req=None):
    pid = data.get("id")
    if pid:
        if pid == "or":
            base_url, headers, ptype = OR_BASE, or_headers(), "openai_compatible"
        elif pid == "cd":
            if not conduit_enabled():
                raise WebError("Conduit غير مفعّل (لا يوجد مفتاح)")
            base_url, headers, ptype = CONDUIT_BASE_URL, conduit_headers(), "openai_compatible"
        else:
            p = provider_by_id(pid)
            if not p:
                raise WebError("المزوّد غير موجود", 404)
            ptype = provider_type_of(p)
            base_url = p["base_url"].rstrip("/")
            headers = gemini_headers(p) if ptype == "gemini" else provider_headers(p)
    else:
        name, base_url, api_key = _validate_provider_fields(data.get("name"), data.get("base_url"), data.get("api_key"))
        ptype = _norm_provider_type(data.get("provider_type"), base_url)
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"} if ptype == "gemini" else \
                  {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    t = time.time()
    try:
        r = await http.get(f"{base_url}/models", headers=headers, timeout=15)
        js = r.json() if r.status_code < 400 else {}
        if ptype == "gemini":
            ms = js.get("models") or []
            names = [x.get("name", "").split("/", 1)[-1] for x in ms[:5]]
        else:
            ms = js.get("data") or []
            names = [x.get("id", "") for x in ms[:5]]
        ok = r.status_code < 400
        return {"ok": ok, "status": r.status_code, "ms": int((time.time() - t) * 1000), "count": len(ms),
                "sample": ", ".join(names) if ok else (r.text or "")[:200], "provider_type": ptype}
    except Exception as e:
        return {"ok": False, "status": 0, "ms": int((time.time() - t) * 1000), "count": 0,
                "sample": str(e)[:200], "provider_type": ptype}


WEB_SETTINGS_SPEC = [
    ("عام", "maintenance", "وضع الصيانة", "bool", "يمنع كل المستخدمين عدا المشرفين"),
    ("عام", "maintenance_msg", "رسالة الصيانة", "text", ""),
    ("عام", "private_mode", "الوضع الخاص", "bool", "لا يستخدم البوت إلا المسموح لهم"),
    ("عام", "welcome_text", "رسالة الترحيب", "text", "استخدم {name} لاسم المستخدم. اتركها فارغة للافتراضية"),
    ("عام", "system_prompt", "System Prompt الافتراضي", "text", "تعليمات الذكاء الاصطناعي لكل المستخدمين"),
    ("عام", "ban_msg", "رسالة الحظر", "text", ""),
    ("الحدود والنقاط", "limit_normal", "الحد اليومي للعادي", "int", "0 = بلا حد"),
    ("الحدود والنقاط", "limit_premium", "الحد اليومي للمميز", "int", "0 = بلا حد"),
    ("الحدود والنقاط", "ref_points", "نقاط الدعوة لكل شخص", "int", "رسائل إضافية للداعي"),
    ("الحدود والنقاط", "history_len", "طول ذاكرة المحادثة", "int", "من 2 إلى 60 رسالة"),
    ("الصلاحيات", "allow_images", "قبول الصور", "bool", ""),
    ("الصلاحيات", "allow_files", "قبول الملفات", "bool", ""),
    ("الإشعارات", "notify_new_models", "إشعار المشرفين بموديلات جديدة", "bool", ""),
    ("الإشعارات", "notify_new_users", "إشعار المشرفين بمستخدم جديد", "bool", ""),
    ("الاشتراك الإجباري", "force_sub", "قناة الاشتراك", "str", "مثل @mychannel — البوت يجب أن يكون مشرفاً. فارغ = إيقاف"),
]
WEB_SPEC_MAP = {k: (g, l, t) for g, k, l, t, _ in WEB_SETTINGS_SPEC}


async def op_settings_get(data, req=None):
    vals = {k: (str(settings[k] or "") if k == "force_sub" else settings[k]) for k in WEB_SPEC_MAP}
    spec = [{"group": g, "key": k, "label": l, "type": t, "help": h} for g, k, l, t, h in WEB_SETTINGS_SPEC]
    return {"values": vals, "spec": spec}


async def _apply_force_sub(val: str) -> str | None:
    if not val:
        settings["force_sub"], settings["force_sub_link"] = "", ""
        _sub_cache.clear()
        return None
    bot = BOT_REF["bot"]
    try:
        chat = await bot.get_chat(val if val.startswith("@") or not val.lstrip("-").isdigit() else int(val))
        me = await bot.get_chat_member(chat.id, bot.id)
        if str(me.status) not in ("administrator", "creator"):
            return "البوت ليس مشرفاً في هذه القناة"
    except Exception as e:
        return f"تعذّر الوصول للقناة: {e}"
    settings["force_sub"] = f"@{chat.username}" if chat.username else chat.id
    link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
    if not link:
        try:
            link = await bot.export_chat_invite_link(chat.id)
        except Exception:
            link = ""
    settings["force_sub_link"] = link
    _sub_cache.clear()
    return None


async def op_settings_set(data, req=None):
    changes = data.get("changes")
    if not isinstance(changes, dict):
        raise WebError("بيانات غير صحيحة")
    errors, applied = [], []
    for k, v in changes.items():
        if k not in WEB_SPEC_MAP:
            errors.append(f"{k}: إعداد غير معروف")
            continue
        typ = WEB_SPEC_MAP[k][2]
        try:
            if k == "force_sub":
                if str(v).strip() != str(settings["force_sub"] or ""):
                    err = await _apply_force_sub(str(v).strip())
                    if err:
                        errors.append(f"{WEB_SPEC_MAP[k][1]}: {err}")
                        continue
                    applied.append(k)
                continue
            if typ == "bool":
                val = bool(v)
            elif typ == "int":
                val = int(v)
                if val < 0 or val > 10_000_000:
                    raise ValueError("خارج المدى")
                if k == "history_len" and not 2 <= val <= 60:
                    raise ValueError("يجب أن تكون بين 2 و 60")
            else:
                val = str(v)[:3000]
                if k == "system_prompt" and not val.strip():
                    val = DEFAULT_SYSTEM_PROMPT
            if settings[k] != val:
                settings[k] = val
                applied.append(k)
        except (ValueError, TypeError) as e:
            errors.append(f"{WEB_SPEC_MAP[k][1]}: {e}")
    if applied:
        audit("settings", ", ".join(applied), client_ip(req))
    vals = (await op_settings_get({}))["values"]
    return {"ok": not errors, "applied": applied, "errors": errors, "values": vals}


async def op_logs(data, req=None):
    return {"errors": stats.data["errors"][-50:][::-1]}


async def op_logs_clear(data, req=None):
    stats.data["errors"] = []
    stats.flush(True)
    audit("logs:clear", "", client_ip(req))
    return {"ok": True}


async def op_audit(data, req=None):
    return {"items": audit_log[-100:][::-1]}


def web_targets(kind: str) -> list[int]:
    if kind == "adm":
        return all_admin_ids()
    now, out = time.time(), []
    for uid, u in users.all():
        if u["banned"] or u["blocked_bot"]:
            continue
        if kind == "act" and now - u["last_seen"] > 7 * 86400:
            continue
        if kind == "prem" and u["tier"] != "premium":
            continue
        if kind == "normal" and u["tier"] == "premium":
            continue
        out.append(uid)
    return out


async def _run_web_broadcast(text: str, html_mode: bool, targets: list[int]):
    bot, st = BOT_REF["bot"], BC_STATE
    pm = ParseMode.HTML if html_mode else None
    try:
        for uid in targets:
            try:
                await bot.send_message(uid, text, parse_mode=pm, disable_web_page_preview=True)
                st["sent"] += 1
            except RetryAfter as e:
                ra = e.retry_after.total_seconds() if hasattr(e.retry_after, "total_seconds") else float(e.retry_after)
                await asyncio.sleep(ra + 1)
                try:
                    await bot.send_message(uid, text, parse_mode=pm, disable_web_page_preview=True)
                    st["sent"] += 1
                except Exception:
                    st["failed"] += 1
            except Forbidden:
                st["blocked"] += 1
                users.get(uid)["blocked_bot"] = True
            except TelegramError as e:
                st["failed"] += 1
                log.warning("web broadcast to %s failed: %s", uid, e)
            await asyncio.sleep(0.05)
    finally:
        st["running"] = False
        st["finished"] = time.time()
        users.flush(True)


async def op_bc_start(data, req=None):
    text = str(data.get("text") or "").strip()
    kind = data.get("target", "all")
    if not text:
        raise WebError("الرسالة فارغة")
    if len(text) > 4000:
        raise WebError("الرسالة أطول من 4000 حرف")
    if kind not in ("all", "act", "prem", "normal", "adm"):
        raise WebError("فئة غير صحيحة")
    if BC_STATE["running"]:
        raise WebError("يوجد بث يعمل الآن", 409)
    targets = web_targets(kind)
    if not targets:
        raise WebError("لا يوجد مستلمون")
    BC_STATE.update(running=True, total=len(targets), sent=0, failed=0, blocked=0,
                    started=time.time(), finished=0, target=kind)
    spawn(_run_web_broadcast(text, bool(data.get("html")), targets))
    audit("broadcast", f"{kind} → {len(targets)}", client_ip(req))
    return {"ok": True, "total": len(targets)}


async def op_bc_status(data, req=None):
    return dict(BC_STATE)


async def _probe(name: str, url: str, headers: dict, info=None) -> dict:
    t = time.time()
    try:
        r = await http.get(url, headers=headers, timeout=15)
        ok = r.status_code < 400
        detail = ""
        if ok and info:
            try:
                detail = info(r.json())
            except Exception:
                detail = ""
        elif not ok:
            detail = r.text[:160]
        return {"name": name, "ok": ok, "status": r.status_code, "ms": int((time.time() - t) * 1000), "detail": detail}
    except Exception as e:
        return {"name": name, "ok": False, "status": 0, "ms": int((time.time() - t) * 1000), "detail": str(e)[:160]}


def _or_key_info(j: dict) -> str:
    d = j.get("data") or {}
    bits = []
    for k, lab in (("label", "الاسم"), ("usage", "الاستهلاك"), ("limit", "الحد"), ("is_free_tier", "مجاني")):
        if d.get(k) is not None:
            bits.append(f"{lab}: {d[k]}")
    return " · ".join(bits)


async def op_health(data, req=None):
    checks = []
    t = time.time()
    try:
        me = await BOT_REF["bot"].get_me()
        checks.append({"name": "Telegram", "ok": True, "status": 200, "ms": int((time.time() - t) * 1000),
                       "detail": "@" + str(me.username)})
    except Exception as e:
        checks.append({"name": "Telegram", "ok": False, "status": 0, "ms": int((time.time() - t) * 1000),
                       "detail": str(e)[:160]})
    checks.append(await _probe("OpenRouter (المفتاح)", f"{OR_BASE}/key", or_headers(), _or_key_info))
    checks.append(await _probe("OpenRouter (الموديلات)", f"{OR_BASE}/models", or_headers()))
    if conduit_enabled():
        checks.append(await _probe("Conduit", f"{CONDUIT_BASE_URL}/models", conduit_headers()))
    else:
        checks.append({"name": "Conduit", "ok": False, "status": 0, "ms": 0, "detail": "غير مفعّل (لا يوجد مفتاح)"})
    now = time.time()
    return {"checks": checks, "system": {
        "uptime": int(now - WEB_STARTED_AT), "python": sys.version.split()[0], "users": len(users.data),
        "histories": len(histories), "models": len(store.models), "sessions": len(SESSIONS),
        "cache_age": int(now - store.updated_at) if store.updated_at else None}}


async def op_playground(data, req=None):
    m = store.models.get(data.get("model"))
    text = str(data.get("message") or "").strip()
    if not m:
        raise WebError("الموديل غير موجود", 404)
    if not text:
        raise WebError("اكتب رسالة للتجربة")
    sysmsg = str(data.get("system") or "").strip() or settings["system_prompt"] or DEFAULT_SYSTEM_PROMPT
    t = time.time()
    try:
        answer, images, tokens = await ask_model(
            m, [{"role": "system", "content": sysmsg}, {"role": "user", "content": text[:8000]}])
    except ORError as e:
        raise WebError(friendly_error(e, m["src"]), 502)
    except Exception as e:
        raise WebError(str(e), 500)
    audit("playground", m["raw_id"], client_ip(req))
    return {"text": answer, "tokens": tokens, "ms": int((time.time() - t) * 1000), "images": len(images)}


async def op_tools(data, req=None):
    a = data.get("action")
    if a == "clear_histories":
        n = len(histories)
        histories.clear()
        audit("tools:clear_histories", str(n), client_ip(req))
        return {"ok": True, "msg": f"تم مسح ذاكرة {n} محادثة"}
    if a == "flush":
        users.flush(True)
        stats.flush(True)
        settings.save()
        return {"ok": True, "msg": "تم حفظ كل البيانات على القرص"}
    if a == "reset_stats":
        if not data.get("confirm"):
            raise WebError("يلزم التأكيد")
        stats.reset()
        audit("tools:reset_stats", "", client_ip(req))
        return {"ok": True, "msg": "تم تصفير الإحصائيات"}
    raise WebError("إجراء غير معروف")


WEB_API = {
    ("GET", "/api/me"): op_me,
    ("GET", "/api/stats"): op_stats,
    ("GET", "/api/users"): op_users,
    ("GET", "/api/user"): op_user_get,
    ("POST", "/api/user"): op_user_action,
    ("GET", "/api/models"): op_models,
    ("POST", "/api/model"): op_model_action,
    ("POST", "/api/models/refresh"): op_models_refresh,
    ("GET", "/api/providers"): op_providers,
    ("POST", "/api/provider"): op_provider_add,
    ("POST", "/api/provider/update"): op_provider_update,
    ("POST", "/api/provider/delete"): op_provider_delete,
    ("POST", "/api/provider/test"): op_provider_test,
    ("GET", "/api/settings"): op_settings_get,
    ("POST", "/api/settings"): op_settings_set,
    ("GET", "/api/logs"): op_logs,
    ("POST", "/api/logs/clear"): op_logs_clear,
    ("GET", "/api/audit"): op_audit,
    ("POST", "/api/broadcast"): op_bc_start,
    ("GET", "/api/broadcast/status"): op_bc_status,
    ("POST", "/api/health"): op_health,
    ("POST", "/api/playground"): op_playground,
    ("POST", "/api/tools"): op_tools,
}


def build_backup_zip() -> bytes:
    users.flush(True)
    stats.flush(True)
    settings.save()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in (USERS_FILE, SETTINGS_FILE, STATS_FILE, AUDIT_FILE, CACHE_FILE):
            if p.exists():
                z.write(p, p.name)
    return buf.getvalue()


def users_csv_bytes() -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "username", "tier", "joined", "last_seen", "messages", "tokens",
                "points", "referrals", "invited_by", "banned", "allowed", "model"])
    for uid, u in users.all():
        w.writerow([uid, u["first_name"], u["username"], u["tier"], fmt_dt(u["joined"]), fmt_dt(u["last_seen"]),
                    u["msg_count"], u["tokens"], u["points"], u["referrals"], u["invited_by"] or "",
                    u["banned"], u["allowed"], model_raw(u["model"]) if u["model"] else ""])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


# ---------------------------------- طبقة aiohttp ----------------------------------
def build_web_app():
    from aiohttp import web
    from urllib.parse import urlparse

    def jresp(data, status=200):
        return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False))

    @web.middleware
    async def security_mw(request, handler):
        try:
            path = request.path
            if request.method not in ("GET", "HEAD", "OPTIONS") and not WEB_TRUST_PROXY:
                origin = request.headers.get("Origin")
                if origin and urlparse(origin).netloc != request.host:
                    return jresp({"error": "origin"}, 403)
            if path.startswith("/api/") and path != "/api/login":
                sess = get_session(request.cookies.get(WEB_COOKIE))
                if not sess:
                    return jresp({"error": "unauthorized"}, 401)
                request["sess"] = sess
                if request.method not in ("GET", "HEAD", "OPTIONS"):
                    if not hmac.compare_digest(request.headers.get("X-CSRF", ""), sess["csrf"]):
                        return jresp({"error": "csrf"}, 403)
            resp = await handler(request)
        except web.HTTPException as ex:
            resp = ex
        except Exception:
            log.exception("web handler error")
            resp = jresp({"error": "خطأ داخلي في الخادم"}, 500)
        h = resp.headers
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/"):
            h["Cache-Control"] = "no-store"
        if WEB_COOKIE_SECURE:
            h["Strict-Transport-Security"] = "max-age=31536000"
        return resp

    async def h_index(request):
        nonce = secrets.token_urlsafe(16)
        csp = ("default-src 'none'; script-src 'nonce-%s'; style-src 'unsafe-inline'; connect-src 'self'; "
               "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'" % nonce)
        return web.Response(text=WEB_INDEX_HTML.replace("__NONCE__", nonce), content_type="text/html",
                            headers={"Content-Security-Policy": csp, "Cache-Control": "no-store"})

    async def h_healthz(request):
        return web.Response(text="ok")

    async def h_login(request):
        ip = client_ip(request)
        wait = login_locked(ip)
        if wait:
            return jresp({"error": f"محاولات كثيرة، انتظر {wait} ثانية"}, 429)
        try:
            data = await request.json()
        except Exception:
            data = {}
        pw = str(data.get("password", "")) if isinstance(data, dict) else ""
        if check_password(pw):
            LOGIN_FAILS.pop(ip, None)
            tok, sess = new_session(ip)
            resp = jresp({"ok": True, "csrf": sess["csrf"]})
            resp.set_cookie(WEB_COOKIE, tok, httponly=True, samesite="Strict",
                            secure=WEB_COOKIE_SECURE, max_age=WEB_SESSION_TTL, path="/")
            audit("login", "", ip)
            return resp
        login_failed(ip)
        audit("login:failed", "", ip)
        await asyncio.sleep(1)
        return jresp({"error": "كلمة المرور غير صحيحة"}, 401)

    async def h_logout(request):
        SESSIONS.pop(request.cookies.get(WEB_COOKIE, ""), None)
        resp = jresp({"ok": True})
        resp.del_cookie(WEB_COOKIE, path="/")
        return resp

    async def h_backup(request):
        audit("backup", "", client_ip(request))
        name = datetime.now().strftime("bot-backup-%Y%m%d-%H%M.zip")
        return web.Response(body=build_backup_zip(), content_type="application/zip",
                            headers={"Content-Disposition": f'attachment; filename="{name}"'})

    async def h_csv(request):
        audit("export:csv", "", client_ip(request))
        return web.Response(body=users_csv_bytes(), content_type="text/csv", charset="utf-8",
                            headers={"Content-Disposition": 'attachment; filename="users.csv"'})

    async def h_api(request):
        fn = WEB_API.get((request.method, request.path))
        if not fn:
            raise web.HTTPNotFound()
        if request.method == "GET":
            data = dict(request.query)
        else:
            try:
                data = await request.json()
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}
        try:
            return jresp(await fn(data, request))
        except WebError as e:
            return jresp({"error": e.msg}, e.status)

    app = web.Application(middlewares=[security_mw], client_max_size=1_000_000)
    app.router.add_get("/", h_index)
    app.router.add_get("/healthz", h_healthz)
    app.router.add_post("/api/login", h_login)
    app.router.add_post("/api/logout", h_logout)
    app.router.add_get("/api/backup", h_backup)
    app.router.add_get("/api/users.csv", h_csv)
    app.router.add_route("*", "/api/{tail:.*}", h_api)
    return app


async def start_web(app_tg: Application):
    if not WEB_ENABLED:
        return
    if not WEB_PASSWORD or "ضع_" in WEB_PASSWORD:
        log.warning("🌐 لوحة الويب معطّلة: ضع WEB_PASSWORD (كلمة مرور قوية) في أعلى الملف.")
        return
    try:
        from aiohttp import web
    except ImportError:
        log.warning("🌐 لوحة الويب تحتاج مكتبة aiohttp:  pip install aiohttp")
        return
    if len(WEB_PASSWORD) < 10:
        log.warning("⚠️ كلمة مرور لوحة الويب قصيرة (أقل من 10 أحرف). الأفضل كلمة أطول وعشوائية.")
    BOT_REF["bot"] = app_tg.bot
    try:
        runner = web.AppRunner(build_web_app(), access_log=None)
        await runner.setup()
        await web.TCPSite(runner, WEB_HOST, WEB_PORT).start()
        BOT_REF["runner"] = runner
        log.info("🌐 Web panel: http://%s:%s", WEB_HOST, WEB_PORT)
    except OSError as e:
        log.error("🌐 تعذّر تشغيل لوحة الويب على %s:%s — %s", WEB_HOST, WEB_PORT, e)


WEB_INDEX_HTML = r"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>لوحة تحكم البوت</title>
<style>
:root{color-scheme:dark;--bg:#0e131f;--card:#161d2f;--card2:#1e2845;--tx:#e8edf7;--mut:#8d99b5;--pri:#4f8cff;--ok:#2ecc71;--dan:#ff5d5d;--warn:#f5b041;--bd:#26304f}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--tx);font:14px/1.6 system-ui,-apple-system,"Segoe UI",Tahoma,Arial,sans-serif}
[hidden]{display:none!important}a{color:var(--pri);text-decoration:none}
.mut{color:var(--mut);font-size:12.5px}.code{font-family:ui-monospace,Menlo,Consolas,monospace;direction:ltr;unicode-bidi:plaintext}
h3{margin:0 0 12px;font-size:16px}
input,select,textarea{background:#0f1526;color:var(--tx);border:1px solid var(--bd);border-radius:10px;padding:9px 12px;font:inherit;max-width:100%}
input:focus,select:focus,textarea:focus{outline:2px solid var(--pri);outline-offset:-1px}
textarea{width:100%;resize:vertical}
.btn{background:var(--card2);color:var(--tx);border:1px solid var(--bd);border-radius:10px;padding:8px 14px;cursor:pointer;font:inherit;display:inline-block}
.btn:hover{border-color:var(--pri)}.btn.pri{background:var(--pri);border-color:var(--pri);color:#fff}
.btn.dan{background:#3a1c24;border-color:#6b2a35;color:#ff9a9a}.btn.warn{background:#3a2f18;border-color:#6b5525;color:#ffd08a}
.btn.sm{padding:4px 9px;font-size:12.5px}.btn.big{padding:12px 22px;font-size:15px}
#login{min-height:100vh;display:grid;place-items:center;padding:20px}
.lbox{background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:28px;width:100%;max-width:370px;text-align:center}
.lbox input{width:100%;margin:14px 0 10px}.lbox .btn{width:100%}#lerr{color:var(--dan);min-height:22px;margin-top:8px}
.app{display:flex;min-height:100vh}
#side{width:210px;background:var(--card);border-inline-end:1px solid var(--bd);padding:14px 10px;position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:6px}
#side .logo{font-weight:700;font-size:16px;padding:6px 12px 12px}
#nav{display:flex;flex-direction:column;gap:3px}
#nav a{display:flex;gap:8px;align-items:center;padding:9px 12px;border-radius:10px;color:var(--tx)}
#nav a.on,#nav a:hover{background:var(--card2)}#nav a.lo{margin-top:10px;color:var(--dan)}
main{flex:1;min-width:0;padding:18px 22px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:16px;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin-bottom:14px}
.stat{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px;display:flex;gap:12px;align-items:center}
.stat .ic{font-size:26px}.stat .v{font-size:22px;font-weight:700}.stat .l{color:var(--mut);font-size:12.5px}.stat .s{color:var(--mut);font-size:11.5px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center}.bar input{flex:1;min-width:180px}
.tw{overflow-x:auto;border:1px solid var(--bd);border-radius:12px}
table{width:100%;border-collapse:collapse;background:var(--card)}
th,td{padding:9px 12px;text-align:start;border-bottom:1px solid var(--bd);white-space:nowrap}
th{color:var(--mut);font-weight:600;font-size:12.5px;background:#121a2b}
tr[data-act=user]{cursor:pointer}tr[data-act=user]:hover{background:var(--card2)}tr.dim{opacity:.5}
td .code{font-size:12px}.acts{display:flex;gap:6px;flex-wrap:wrap}
.pill{border-radius:20px;padding:2px 10px;font-size:12px;background:var(--card2)}.pill.p{background:#3a2f18;color:#ffd08a}.pill.b{background:#3a1c24;color:#ff9a9a}
.ov{position:fixed;inset:0;background:#000a;display:grid;place-items:center;padding:14px;z-index:50}
.dlg{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:20px;width:100%;max-width:560px;max-height:92vh;overflow:auto;position:relative}
.dlg .x{position:absolute;inset-inline-start:12px;top:12px;background:none;border:0;color:var(--mut);cursor:pointer;font-size:16px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;margin:12px 0}.kv span{color:var(--mut)}
.row2{display:flex;gap:8px;margin-top:10px}.row2 input,.row2 textarea{flex:1}
.row{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:10px 0;border-bottom:1px solid var(--bd)}
.row:last-child{border:0}.row>div:last-child{flex:0 0 min(320px,50%)}.row input[type=text],.row input[type=number]{width:100%}
.sw{position:relative;display:inline-block;width:46px;height:26px}.sw input{opacity:0;width:0;height:0}
.sw i{position:absolute;inset:0;background:#2b3556;border-radius:26px;cursor:pointer;transition:.2s}
.sw i:before{content:"";position:absolute;width:20px;height:20px;top:3px;inset-inline-start:3px;background:#fff;border-radius:50%;transition:.2s}
.sw input:checked+i{background:var(--ok)}.sw input:checked+i:before{transform:translateX(-20px)}
.hc{padding:9px 12px;border:1px solid var(--bd);border-radius:10px;margin-top:8px}.hc.ok{border-color:#1f6b45}.hc.bad{border-color:#6b2a35}
.prog{height:10px;background:#0f1526;border-radius:8px;overflow:hidden;margin:10px 0}.prog>i{display:block;height:100%;background:var(--pri)}
svg .bar{fill:var(--pri)}svg .ax{fill:var(--mut);font-size:11px}
#toasts{position:fixed;bottom:18px;inset-inline-start:18px;display:flex;flex-direction:column;gap:8px;z-index:99}
.toast{background:#1d3b2b;border:1px solid #1f6b45;padding:10px 16px;border-radius:10px;max-width:340px}.toast.bad{background:#3a1c24;border-color:#6b2a35}
.pre{white-space:pre-wrap;background:#0f1526;border:1px solid var(--bd);border-radius:10px;padding:12px;margin-top:10px;max-height:380px;overflow:auto}
@media(max-width:800px){.app{flex-direction:column}#side{width:100%;height:auto;position:static;flex-direction:row;overflow-x:auto;padding:8px}#side .logo{display:none}
#nav{flex-direction:row}#nav a span{display:none}#nav a.lo{margin:0}main{padding:12px}.two{grid-template-columns:1fr}.row{flex-direction:column;align-items:stretch}.row>div:last-child{flex:1}}
</style></head><body>
<div id="login" hidden><div class="lbox"><div style="font-size:40px">🤖</div><h3>لوحة تحكم البوت</h3>
<input id="pw" type="password" placeholder="كلمة المرور" autocomplete="current-password">
<button class="btn pri" data-act="login">دخول</button><div id="lerr"></div></div></div>
<div class="app" id="app" hidden><aside id="side"><div class="logo">🤖 لوحة التحكم</div><nav id="nav"></nav></aside><main id="view"></main></div>
<div id="toasts"></div>
<script nonce="__NONCE__">
(()=>{'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ft=t=>t?new Date(t*1000).toLocaleString('en-GB',{hour12:false}).replace(',',''):'—';
const nf=n=>Number(n||0).toLocaleString('en-US');
const fctx=n=>!n?'؟':n>=1e6?(n/1e6).toFixed(1).replace('.0','')+'M':n>=1e3?Math.round(n/1e3)+'K':String(n);
const dur=s=>{const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return(d?d+'ي ':'')+(h?h+'س ':'')+m+'د'};
let CSRF='',CUR='dash',TIMER=null,BCT=null,DEB=null;
const U={q:'',f:'all',page:1,sort:'last'};let MODELS=[],MQ='',MS='all';
function toast(m,bad){const t=document.createElement('div');t.className='toast'+(bad?' bad':'');t.textContent=m;$('#toasts').appendChild(t);setTimeout(()=>t.remove(),3800)}
async function api(path,body){
  const o={credentials:'same-origin',headers:{'X-CSRF':CSRF}};
  if(body!==undefined){o.method='POST';o.headers['Content-Type']='application/json';o.body=JSON.stringify(body)}
  const r=await fetch(path,o);
  if(r.status===401&&path!=='/api/login'){showLogin();throw new Error('انتهت الجلسة، سجّل الدخول')}
  let j={};try{j=await r.json()}catch(e){}
  if(!r.ok)throw new Error(j.error||('خطأ '+r.status));
  return j}
function stopTimers(){clearInterval(TIMER);clearInterval(BCT);TIMER=BCT=null}
function showLogin(){stopTimers();closeModal();$('#app').hidden=true;$('#login').hidden=false;$('#pw').focus()}
async function boot(){try{const r=await api('/api/me');CSRF=r.csrf;$('#login').hidden=true;$('#app').hidden=false;buildNav();go(location.hash.slice(1)||'dash')}catch(e){showLogin()}}
async function doLogin(){try{const r=await api('/api/login',{password:$('#pw').value});CSRF=r.csrf;$('#pw').value='';$('#lerr').textContent='';boot()}catch(e){$('#lerr').textContent=e.message}}
const TABS=[['dash','📊','لوحة القيادة'],['users','👥','المستخدمون'],['models','🤖','الموديلات'],['prov','🔌','المزوّدون'],['bc','📢','البث'],['set','⚙️','الإعدادات'],['tools','🧰','الأدوات'],['logs','📜','الأخطاء'],['audit','🛡','النشاط']];
function buildNav(){$('#nav').innerHTML=TABS.map(([k,i,l])=>`<a href="#${k}" data-act="nav" data-k="${k}">${i} <span>${l}</span></a>`).join('')+'<a href="#" data-act="logout" class="lo">🚪 <span>خروج</span></a>'}
function go(k){if(!VIEWS[k])k='dash';CUR=k;location.hash=k;$$('#nav a').forEach(a=>a.classList.toggle('on',a.dataset.k===k));stopTimers();closeModal();
  $('#view').innerHTML='<div class="mut">… جاري التحميل</div>';
  VIEWS[k]().catch(e=>{$('#view').innerHTML='<div class="card">❌ '+esc(e.message)+'</div>'})}
function closeModal(){const m=$('#modal');if(m)m.remove()}
function openModal(h){closeModal();const d=document.createElement('div');d.id='modal';d.className='ov';d.innerHTML='<div class="dlg"><button class="x" data-act="close">✖</button>'+h+'</div>';document.body.appendChild(d)}

/* ---------- لوحة القيادة ---------- */
async function dashRender(){
  const s=await api('/api/stats');
  const c=(i,l,v,sub)=>`<div class="stat"><div class="ic">${i}</div><div><div class="v">${v}</div><div class="l">${l}</div>${sub?`<div class="s">${sub}</div>`:''}</div></div>`;
  const mx=Math.max(1,...s.daily.map(d=>d.msgs)),W=700,H=180,bw=W/s.daily.length;
  const bars=s.daily.map((d,i)=>{const h=Math.round(d.msgs/mx*(H-50));return `<g><rect class="bar" x="${i*bw+7}" y="${H-24-h}" width="${bw-14}" height="${Math.max(h,2)}" rx="4"><title>${esc(d.day)}: ${d.msgs} رسالة، ${d.new} مستخدم جديد</title></rect><text class="ax" x="${i*bw+bw/2}" y="${H-8}" text-anchor="middle">${esc(d.day)}</text><text class="ax" x="${i*bw+bw/2}" y="${H-28-h}" text-anchor="middle">${d.msgs||''}</text></g>`}).join('');
  const fl=[];if(s.flags.maintenance)fl.push('🛠 صيانة');if(s.flags.private)fl.push('🔒 خاص');if(s.flags.force_sub)fl.push('📢 '+esc(s.flags.force_sub));
  $('#view').innerHTML=`<div class="grid">
  ${c('👥','المستخدمون',nf(s.users),`نشط 24س: ${nf(s.active24)} · 7 أيام: ${nf(s.active7)}`)}
  ${c('🆕','جدد اليوم',nf(s.new_today))}${c('⭐','مميزون',nf(s.premium),`محظور: ${s.banned} · حظروا البوت: ${s.blocked}`)}
  ${c('💬','رسائل اليوم',nf(s.msgs_today),`الإجمالي: ${nf(s.total_msgs)}`)}${c('🧮','توكنات اليوم',nf(s.tokens_today),`الإجمالي: ${nf(s.total_tokens)}`)}
  ${c('⚠️','الأخطاء',nf(s.errors))}${c('🎁','النقاط المتاحة',nf(s.points_total),`دعوات ناجحة: ${nf(s.referrals_total)}`)}
  ${c('🤖','الموديلات',nf(s.models.visible),`🆓 ${s.models.or} · 🧭 ${s.models.cd} · مخفي ${s.models.hidden} · حصري ${s.models.premium}`)}
  ${c('⏱','مدة التشغيل',dur(s.uptime),fl.join(' · ')||'الحالة: عادي ✅')}
  ${c('📏','الحدود اليومية',`${s.limits.normal||'∞'} / ${s.limits.premium||'∞'}`,`عادي / مميز · نقاط الدعوة ${s.limits.ref}`)}</div>
  <div class="card"><h3>📈 آخر 14 يوماً (الرسائل)</h3><svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${bars}</svg></div>
  <div class="two"><div class="card"><h3>🏆 أكثر الموديلات استخداماً</h3>${s.top_models.length?`<table>${s.top_models.map(m=>`<tr><td class="code">${esc(m.name)}</td><td>${nf(m.n)}</td></tr>`).join('')}</table>`:'<div class="mut">لا بيانات بعد</div>'}</div>
  <div class="card"><h3>🥇 أكثر المستخدمين نشاطاً</h3>${s.top_users.length?`<table>${s.top_users.map(u=>`<tr data-act="user" data-id="${esc(u.id)}"><td>${esc(u.name)}</td><td>${nf(u.n)}</td></tr>`).join('')}</table>`:'<div class="mut">لا بيانات بعد</div>'}</div></div>`}
async function vDash(){await dashRender();TIMER=setInterval(()=>{if(CUR==='dash'&&!$('#modal'))dashRender().catch(()=>{})},15000)}

/* ---------- المستخدمون ---------- */
async function vUsers(){
  const F=[['all','الكل'],['act','نشط 24س'],['new','جدد اليوم'],['prem','⭐ مميز'],['ban','محظور'],['alw','مسموح']];
  const S=[['last','آخر نشاط'],['msgs','الرسائل'],['points','النقاط'],['tokens','التوكنات'],['joined','الانضمام']];
  $('#view').innerHTML=`<div class="bar"><input id="uq" placeholder="بحث: اسم / يوزر / ID" value="${esc(U.q)}">
  <select id="uf">${F.map(([k,l])=>`<option value="${k}" ${U.f===k?'selected':''}>${l}</option>`).join('')}</select>
  <select id="us">${S.map(([k,l])=>`<option value="${k}" ${U.sort===k?'selected':''}>ترتيب: ${l}</option>`).join('')}</select>
  <a class="btn" href="/api/users.csv">📤 CSV</a></div><div id="ulist"></div>`;
  await loadUsers()}
async function loadUsers(){
  const r=await api(`/api/users?q=${encodeURIComponent(U.q)}&f=${U.f}&page=${U.page}&sort=${U.sort}`);
  U.page=r.page;
  $('#ulist').innerHTML=`<div class="mut" style="margin-bottom:8px">${nf(r.total)} مستخدم · صفحة ${r.page}/${r.pages}</div>
  <div class="tw"><table><thead><tr><th>ID</th><th>الاسم</th><th>الفئة</th><th>الرسائل</th><th>اليوم</th><th>النقاط</th><th>آخر نشاط</th><th>الحالة</th></tr></thead><tbody>
  ${r.users.map(u=>`<tr data-act="user" data-id="${esc(u.id)}"><td class="code">${esc(u.id)}</td><td>${esc(u.name||'—')} <span class="mut">${u.username?'@'+esc(u.username):''}</span></td>
  <td>${u.tier==='premium'?'<span class="pill p">⭐ مميز</span>':'<span class="pill">عادي</span>'}</td><td>${nf(u.msgs)}</td><td>${u.today}/${u.limit||'∞'}</td><td>${nf(u.points)}</td><td>${ft(u.last)}</td>
  <td>${u.banned?'<span class="pill b">🚫 محظور</span>':u.blocked_bot?'<span class="pill">حظر البوت</span>':'✅'}</td></tr>`).join('')||'<tr><td colspan="8" class="mut">لا نتائج</td></tr>'}</tbody></table></div>
  <div class="bar" style="margin-top:10px"><button class="btn" data-act="upage" data-d="-1" ${r.page<=1?'disabled':''}>▶ السابق</button><button class="btn" data-act="upage" data-d="1" ${r.page>=r.pages?'disabled':''}>التالي ◀</button></div>`}
function userModal(u){
  const b=(a,l,cls,v)=>`<button class="btn sm ${cls||''}" data-act="uact" data-a="${a}" data-id="${esc(u.id)}" ${v!==undefined?`data-v="${v}"`:''}>${l}</button>`;
  openModal(`<h3>${u.tier==='premium'?'⭐ ':''}${esc(u.name||'—')} <span class="mut">${u.username?'@'+esc(u.username):''}</span></h3>
  <div class="kv"><span>ID</span><b class="code">${esc(u.id)}</b><span>انضم</span><b>${ft(u.joined)}</b><span>آخر نشاط</span><b>${ft(u.last)}</b>
  <span>الرسائل</span><b>${nf(u.msgs)} (اليوم ${u.today}/${u.limit||'∞'}${u.limit_custom!==null?' · مخصص':''})</b><span>التوكنات</span><b>${nf(u.tokens)}</b>
  <span>النقاط</span><b>${nf(u.points)}</b><span>دعا</span><b>${u.referrals}</b><span>دُعي من</span><b class="code">${esc(u.invited_by||'—')}</b>
  <span>الموديل</span><b class="code">${esc(u.model||'افتراضي')}</b><span>الحالة</span><b>${u.banned?'🚫 محظور'+(u.ban_reason?' — '+esc(u.ban_reason):''):'✅ نشط'}${u.blocked_bot?' · حظر البوت':''}</b>
  <span>مسموح</span><b>${u.allowed?'نعم':'لا'}</b></div>
  <div class="acts">${u.tier==='premium'?b('tier','⬇️ تنزيل لعادي','','normal'):b('tier','⭐ ترقية لمميز','warn','premium')}
  ${u.banned?b('unban','✅ فك الحظر','pri'):''}${b('allow',u.allowed?'➖ إزالة السماح':'🔒 سماح','',!u.allowed)}
  ${b('reset_day','🔄 تصفير اليوم')}${b('clear','🗑 مسح ذاكرته')}${b('reset_user','♻️ إعادة ضبط موديله')}</div>
  <div class="row2"><input id="mp" placeholder="نقاط: 50 أو +10 أو -5">${b('points','🎁 تطبيق')}</div>
  <div class="row2"><input id="ml" placeholder="حد يومي مخصص (فارغ = العام)" value="${u.limit_custom??''}">${b('limit','🎯 حفظ')}</div>
  <div class="row2"><input id="mr" placeholder="سبب الحظر (اختياري)">${u.banned?'':b('ban','🚫 حظر','dan')}</div>
  <div class="row2"><textarea id="mm" rows="3" placeholder="رسالة تصل للمستخدم من البوت"></textarea>${b('message','✉️ إرسال','pri')}</div>`)}

/* ---------- الموديلات ---------- */
async function vModels(){
  const r=await api('/api/models');MODELS=r.models;
  const S=[['all','كل المصادر'],['or','🆓 OpenRouter'],['cd','🧭 Conduit'],['hidden','🙈 المخفية'],['premium','⭐ الحصرية']];
  $('#view').innerHTML=`<div class="bar"><input id="mq" placeholder="بحث في الموديلات" value="${esc(MQ)}"><select id="ms">${S.map(([k,l])=>`<option value="${k}" ${MS===k?'selected':''}>${l}</option>`).join('')}</select>
  <button class="btn pri" data-act="mrefresh">🔄 تحديث من المزوّدين</button></div>
  <div class="mut" id="mcount" style="margin-bottom:8px"></div><div id="mlist"></div>`;renderModels()}
function renderModels(){
  const q=MQ.toLowerCase();
  const rows=MODELS.filter(m=>(MS==='all'||m.src===MS||(MS==='hidden'&&m.hidden)||(MS==='premium'&&m.premium))&&(!q||m.raw.toLowerCase().includes(q)||m.name.toLowerCase().includes(q)));
  $('#mcount').textContent=`${rows.length} من ${MODELS.length}`+(rows.length>400?' (يُعرض أول 400)':'');
  const b=(m,a,l,cls)=>`<button class="btn sm ${cls||''}" data-act="mact" data-a="${a}" data-id="${esc(m.id)}">${l}</button>`;
  $('#mlist').innerHTML=`<div class="tw"><table><thead><tr><th></th><th>الموديل</th><th>السياق</th><th>الوسائط</th><th>إجراءات</th></tr></thead><tbody>
  ${rows.slice(0,400).map(m=>`<tr class="${m.hidden?'dim':''}"><td>${m.src==='cd'?'🧭':'🆓'}</td><td><b>${esc(m.name)}</b><div class="mut code">${esc(m.raw)}</div></td><td>${fctx(m.ctx)}</td>
  <td>${m.in.includes('image')?'👁 ':''}${m.out.includes('image')?'🎨':''}</td>
  <td class="acts">${b(m,'premium',m.premium?'⭐ حصري':'⭐ عام',m.premium?'warn':'')}${b(m,'hide',m.hidden?'🙈 مخفي':'👁 ظاهر',m.hidden?'dan':'')}${m.default?b(m,'undefault','✅ افتراضي','pri'):b(m,'default','تعيين افتراضي')}</td></tr>`).join('')}</tbody></table></div>`}

/* ---------- البث ---------- */
async function vBc(){
  $('#view').innerHTML=`<div class="card"><h3>📢 بث رسالة جماعية</h3>
  <div class="bar"><select id="bt"><option value="all">كل المستخدمين</option><option value="act">النشطون آخر 7 أيام</option><option value="prem">⭐ المميزون</option><option value="normal">العاديون</option><option value="adm">🧪 تجربة: المشرفون فقط</option></select>
  <label class="mut"><input type="checkbox" id="bh"> تنسيق HTML (&lt;b&gt; &lt;i&gt; &lt;a href&gt; &lt;code&gt;)</label></div>
  <textarea id="bx" rows="7" maxlength="4000" placeholder="نص الرسالة..."></textarea>
  <div style="margin-top:10px"><button class="btn pri big" data-act="bcsend">📤 إرسال</button></div></div>
  <div class="card" id="bcs"></div>`;bcPoll();BCT=setInterval(bcPoll,2000)}
async function bcPoll(){
  const s=await api('/api/broadcast/status');if(CUR!=='bc')return;
  const done=s.sent+s.failed+s.blocked,pct=s.total?Math.round(done/s.total*100):0;
  $('#bcs').innerHTML=s.total?`<h3>${s.running?'⏳ جاري الإرسال...':'✅ آخر بث'}</h3><div class="prog"><i style="width:${pct}%"></i></div>
  <div>${done}/${s.total} (${pct}%) · 📬 نجح ${s.sent} · 🚫 حظروا البوت ${s.blocked} · ❌ فشل ${s.failed}</div>`:'<div class="mut">لا يوجد بث سابق في هذه الجلسة.</div>'}

/* ---------- الإعدادات ---------- */
async function vSet(){
  const r=await api('/api/settings'),g={};r.spec.forEach(s=>(g[s.group]=g[s.group]||[]).push(s));let h='';
  for(const[k,items]of Object.entries(g)){h+=`<div class="card"><h3>${esc(k)}</h3>`+items.map(s=>{
    const v=r.values[s.key];let i;
    if(s.type==='bool')i=`<label class="sw"><input type="checkbox" data-key="${s.key}" data-type="bool" ${v?'checked':''}><i></i></label>`;
    else if(s.type==='int')i=`<input type="number" min="0" data-key="${s.key}" data-type="int" value="${esc(v)}">`;
    else if(s.type==='text')i=`<textarea rows="3" data-key="${s.key}" data-type="text">${esc(v)}</textarea>`;
    else i=`<input type="text" data-key="${s.key}" data-type="str" value="${esc(v)}" dir="ltr">`;
    return `<div class="row"><div><b>${esc(s.label)}</b>${s.help?`<div class="mut">${esc(s.help)}</div>`:''}</div><div>${i}</div></div>`}).join('')+'</div>'}
  $('#view').innerHTML=h+'<button class="btn pri big" data-act="saveset">💾 حفظ الإعدادات</button>'}

/* ---------- المزوّدون ---------- */
const PTYPE_LABEL={openai_compatible:'OpenAI-compatible',gemini:'✨ Gemini Native'};
async function vProv(){
  const r=await api('/api/providers');
  const known=r.known.map(k=>`<button class="btn sm" data-act="pknown" data-name="${esc(k.name)}" data-url="${esc(k.base_url)}" data-icon="${esc(k.icon)}" data-type="${esc(k.provider_type)}">${k.icon} ${esc(k.name)}</button>`).join(' ');
  $('#view').innerHTML=`<div class="card"><h3>➕ إضافة مزوّد جديد</h3>
  <div class="mut" style="margin-bottom:8px">إضافة سريعة (تحتاج فقط لصق مفتاحك): ${known}</div>
  <div class="row2"><input id="pn" placeholder="اسم المزوّد" style="flex:1"><input id="pi" placeholder="أيقونة (اختياري)" style="max-width:80px" maxlength="4">
  <select id="pt" style="max-width:220px"><option value="openai_compatible">OpenAI-compatible (Endpoint+Key)</option><option value="gemini">✨ Gemini Native (Google AI)</option></select></div>
  <div class="row2"><input id="pu" placeholder="رابط الموديلات Base URL — مثال: https://api.example.com/v1" dir="ltr" style="flex:2"></div>
  <div class="row2"><input id="pk" type="password" placeholder="API Key" dir="ltr" style="flex:1">
  <button class="btn" data-act="ptest_new">🩺 اختبار</button><button class="btn pri" data-act="padd">➕ إضافة</button></div>
  <div class="mut" id="ptypehint" style="margin-top:4px"></div>
  <div id="ptestres"></div></div>
  <div id="plist"></div>`;
  renderProv(r.providers)}
function renderProv(list){
  const b=(p,a,l,cls)=>`<button class="btn sm ${cls||''}" data-act="pact" data-a="${a}" data-id="${esc(p.id)}">${l}</button>`;
  $('#plist').innerHTML=`<div class="tw"><table><thead><tr><th></th><th>المزوّد</th><th>النوع</th><th>الرابط</th><th>المفتاح</th><th>الموديلات</th><th>إجراءات</th></tr></thead><tbody>
  ${list.map(p=>`<tr class="${p.enabled?'':'dim'}"><td>${esc(p.icon)}</td><td><b>${esc(p.name)}</b>${p.custom?'':'<div class="mut">مدمج</div>'}</td>
  <td>${p.provider_type==='gemini'?'<span class="pill p">✨ Gemini</span>':'<span class="pill">OpenAI</span>'}</td>
  <td class="code" style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(p.base_url)}</td>
  <td class="code">${p.key_masked||(p.custom?'':'<span class="mut">غير مُعدّ</span>')}</td><td>${p.models}</td>
  <td class="acts">${b(p,'test','🩺 اختبار')}${p.custom?b(p,'toggle',p.enabled?'⏸ تعطيل':'▶️ تفعيل'):''}${p.custom?b(p,'edit','✏️ تعديل'):''}${p.custom?b(p,'del','🗑 حذف','dan'):''}</td></tr>`).join('')}
  </tbody></table></div><div id="presbox"></div>`}
function providerModal(p){
  openModal(`<h3>${esc(p.icon)} تعديل ${esc(p.name)}</h3>
  <div class="row2"><input id="epn" placeholder="الاسم" value="${esc(p.name)}">
  <select id="ept"><option value="openai_compatible" ${p.provider_type!=='gemini'?'selected':''}>OpenAI-compatible</option><option value="gemini" ${p.provider_type==='gemini'?'selected':''}>✨ Gemini Native</option></select></div>
  <div class="row2"><input id="epu" placeholder="Base URL" value="${esc(p.base_url)}" dir="ltr"></div>
  <div class="row2"><input id="epk" type="password" placeholder="مفتاح جديد (اتركه فارغاً للإبقاء على الحالي)" dir="ltr"></div>
  <div class="row2"><button class="btn pri" data-act="psave" data-id="${esc(p.id)}">💾 حفظ</button></div>`)}
document.addEventListener('change', e=>{if(e.target.id==='pt')$('#ptypehint').textContent=e.target.value==='gemini'?'سيُستخدم x-goog-api-key و generateContent/interactions بدل Bearer.':'';});
document.addEventListener('click', async e=>{
  const t=e.target.closest('[data-act]');if(!t)return;const a=t.dataset.act;
  try{switch(a){
    case 'pknown':$('#pn').value=t.dataset.name;$('#pu').value=t.dataset.url;$('#pi').value=t.dataset.icon;$('#pt').value=t.dataset.type;$('#pt').dispatchEvent(new Event('change'));$('#pk').focus();return;
    case 'ptest_new':{t.disabled=true;$('#ptestres').innerHTML='<div class="mut">… جاري الاختبار</div>';try{
      const r=await api('/api/provider/test',{name:$('#pn').value,base_url:$('#pu').value,api_key:$('#pk').value,provider_type:$('#pt').value});
      $('#ptestres').innerHTML=`<div class="hc ${r.ok?'ok':'bad'}">${r.ok?'✅':'❌'} ${r.status||''} · ${r.ms}ms · ${r.count} موديل<div class="mut">${esc(r.sample)}</div></div>`}finally{t.disabled=false}return}
    case 'padd':{t.disabled=true;try{
      const r=await api('/api/provider',{name:$('#pn').value,base_url:$('#pu').value,api_key:$('#pk').value,icon:$('#pi').value,provider_type:$('#pt').value});
      toast(`✅ أُضيف ${r.provider.name} — ${r.models_found} موديل`+(r.refresh_errors.length?' ⚠️ '+r.refresh_errors.join(' | '):''),r.refresh_errors.length>0);
      await vProv()}finally{t.disabled=false}return}
    case 'pact':{const ac=t.dataset.a,id=t.dataset.id;
      if(ac==='test'){$('#presbox').innerHTML='<div class="mut">… جاري الاختبار</div>';const r=await api('/api/provider/test',{id});
        $('#presbox').innerHTML=`<div class="hc ${r.ok?'ok':'bad'}">${r.ok?'✅':'❌'} ${r.status||''} · ${r.ms}ms · ${r.count} موديل<div class="mut">${esc(r.sample)}</div></div>`;return}
      if(ac==='toggle'){const cur=t.textContent.includes('تعطيل');const r=await api('/api/provider/update',{id,enabled:!cur});toast('✅ تم');return await vProv()}
      if(ac==='del'){if(!confirm('حذف هذا المزوّد؟ ستختفي موديلاته من البوت.'))return;await api('/api/provider/delete',{id});toast('🗑 تم الحذف');return await vProv()}
      if(ac==='edit'){const r=await api('/api/providers');const p=r.providers.find(x=>x.id===id);if(p)providerModal(p);return}
      return}
    case 'psave':{t.disabled=true;try{
      const r=await api('/api/provider/update',{id:t.dataset.id,name:$('#epn').value,base_url:$('#epu').value,api_key:$('#epk').value,provider_type:$('#ept').value});
      toast('✅ تم الحفظ');closeModal();await vProv()}finally{t.disabled=false}return}
  }}catch(err){toast(err.message,1)}});

/* ---------- الأدوات ---------- */
async function vTools(){
  const r=await api('/api/models'),by={or:'🆓 OpenRouter',cd:'🧭 Conduit'};
  const opts=['or','cd'].map(s=>{const l=r.models.filter(m=>m.src===s&&!m.hidden);return l.length?`<optgroup label="${by[s]}">${l.map(m=>`<option value="${esc(m.id)}">${esc(m.name)} — ${esc(m.raw)}</option>`).join('')}</optgroup>`:''}).join('');
  $('#view').innerHTML=`<div class="card"><h3>🩺 فحص الصحة</h3><button class="btn pri" data-act="health">تشغيل الفحص</button><div id="hres"></div></div>
  <div class="card"><h3>🧪 تجربة موديل</h3><div class="bar"><select id="pm" style="flex:1;min-width:220px">${opts}</select></div>
  <textarea id="ps" rows="2" placeholder="System Prompt (اختياري)"></textarea><textarea id="pt" rows="4" placeholder="اكتب رسالة للتجربة..." style="margin-top:8px"></textarea>
  <div style="margin-top:10px"><button class="btn pri" data-act="pg">▶ تشغيل</button></div><div id="pres"></div></div>
  <div class="card"><h3>💾 النسخ الاحتياطي والتصدير</h3><div class="acts"><a class="btn" href="/api/backup">⬇️ نسخة احتياطية (ZIP)</a><a class="btn" href="/api/users.csv">📤 المستخدمون CSV</a></div></div>
  <div class="card"><h3>🧹 صيانة</h3><div class="acts"><button class="btn" data-act="tool" data-a="flush">💾 حفظ كل البيانات الآن</button>
  <button class="btn warn" data-act="tool" data-a="clear_histories">🧹 مسح ذاكرة كل المحادثات</button><button class="btn dan" data-act="tool" data-a="reset_stats">♻️ تصفير الإحصائيات</button></div></div>`}

/* ---------- السجلات ---------- */
async function vLogs(){
  const r=await api('/api/logs');
  $('#view').innerHTML=`<div class="bar"><button class="btn dan" data-act="logclr">🗑 مسح السجل</button></div>`+(r.errors.length?`<div class="tw"><table><thead><tr><th>الوقت</th><th>الرمز</th><th>الموديل</th><th>الرسالة</th></tr></thead><tbody>
  ${r.errors.map(e=>`<tr><td>${ft(e.t)}</td><td>${esc(e.status)}</td><td class="code">${esc(e.model)}</td><td style="white-space:normal">${esc(e.msg)}</td></tr>`).join('')}</tbody></table></div>`:'<div class="card">✅ لا توجد أخطاء مسجّلة.</div>')}
async function vAudit(){
  const r=await api('/api/audit');
  $('#view').innerHTML=r.items.length?`<div class="tw"><table><thead><tr><th>الوقت</th><th>الإجراء</th><th>التفاصيل</th><th>IP</th></tr></thead><tbody>
  ${r.items.map(e=>`<tr><td>${ft(e.t)}</td><td>${esc(e.a)}</td><td style="white-space:normal">${esc(e.d)}</td><td class="code">${esc(e.ip)}</td></tr>`).join('')}</tbody></table></div>`:'<div class="card">لا يوجد نشاط مسجّل بعد.</div>'}
const VIEWS={dash:vDash,users:vUsers,models:vModels,prov:vProv,bc:vBc,set:vSet,tools:vTools,logs:vLogs,audit:vAudit};

/* ---------- الأحداث ---------- */
async function openUser(id){const r=await api('/api/user?id='+encodeURIComponent(id));userModal(r.user)}
document.addEventListener('click',async e=>{
  if(e.target.id==='modal'){closeModal();return}
  const t=e.target.closest('[data-act]');if(!t)return;const a=t.dataset.act;
  if(a==='nav'||a==='logout')e.preventDefault();
  try{switch(a){
    case 'login':return doLogin();
    case 'nav':return go(t.dataset.k);
    case 'logout':await api('/api/logout',{});CSRF='';return showLogin();
    case 'close':return closeModal();
    case 'user':return await openUser(t.dataset.id);
    case 'upage':U.page=Math.max(1,U.page+Number(t.dataset.d));return await loadUsers();
    case 'uact':{const ac=t.dataset.a;let v=t.dataset.v;
      if(ac==='points')v=$('#mp').value;else if(ac==='limit')v=$('#ml').value;else if(ac==='message')v=$('#mm').value;else if(ac==='ban')v=$('#mr').value;
      else if(ac==='allow')v=(v==='true');
      if((ac==='clear'||ac==='reset_user')&&!confirm('متأكد؟'))return;
      const r=await api('/api/user',{id:t.dataset.id,action:ac,value:v});toast('✅ تم');userModal(r.user);if(CUR==='users')loadUsers();return}
    case 'mact':{const r=await api('/api/model',{id:t.dataset.id,action:t.dataset.a});
      MODELS=MODELS.map(m=>m.id===r.model.id?r.model:(t.dataset.a==='default'?{...m,default:false}:m));renderModels();return toast('✅ تم')}
    case 'mrefresh':{t.disabled=true;toast('⏳ جاري التحديث...');try{const r=await api('/api/models/refresh',{});
      toast(`✅ ${r.total} موديل · جديد ${r.added.length} · محذوف ${r.removed.length}`+(r.errors.length?' ⚠️ '+r.errors.join(' | '):''),r.errors.length>0);await vModels()}finally{t.disabled=false}return}
    case 'bcsend':{const text=$('#bx').value.trim();if(!text)return toast('اكتب الرسالة',1);
      if(!confirm('تأكيد إرسال البث؟'))return;
      const r=await api('/api/broadcast',{text,target:$('#bt').value,html:$('#bh').checked});toast(`📤 بدأ الإرسال إلى ${r.total}`);return bcPoll()}
    case 'saveset':{const ch={};$$('[data-key]').forEach(i=>{const ty=i.dataset.type;ch[i.dataset.key]=ty==='bool'?i.checked:ty==='int'?Number(i.value):i.value});
      const r=await api('/api/settings',{changes:ch});r.errors.forEach(x=>toast('❌ '+x,1));if(r.applied.length)toast('✅ حُفظ: '+r.applied.length+' إعداد');else if(!r.errors.length)toast('لا تغييرات');return}
    case 'health':{t.disabled=true;$('#hres').innerHTML='<div class="mut">… جاري الفحص</div>';try{const r=await api('/api/health',{});const s=r.system;
      $('#hres').innerHTML=r.checks.map(c=>`<div class="hc ${c.ok?'ok':'bad'}">${c.ok?'✅':'❌'} <b>${esc(c.name)}</b> <span class="mut">${c.status||''} · ${c.ms}ms</span><div class="mut">${esc(c.detail)}</div></div>`).join('')
      +`<div class="mut" style="margin-top:10px">⏱ ${dur(s.uptime)} · Python ${esc(s.python)} · مستخدمون ${s.users} · محادثات في الذاكرة ${s.histories} · موديلات ${s.models} · جلسات ويب ${s.sessions}${s.cache_age!==null?' · عمر القائمة '+dur(s.cache_age):''}</div>`}finally{t.disabled=false}return}
    case 'pg':{t.disabled=true;$('#pres').innerHTML='<div class="mut">… جاري التشغيل</div>';try{const r=await api('/api/playground',{model:$('#pm').value,system:$('#ps').value,message:$('#pt').value});
      $('#pres').innerHTML=`<div class="mut" style="margin-top:8px">⏱ ${r.ms}ms · 🧮 ${r.tokens} توكن${r.images?' · 🎨 '+r.images+' صورة (لا تُعرض هنا)':''}</div><div class="pre">${esc(r.text||'(رد فارغ)')}</div>`}catch(err){$('#pres').innerHTML='';throw err}finally{t.disabled=false}return}
    case 'tool':{const ac=t.dataset.a;if(ac!=='flush'&&!confirm('هل أنت متأكد؟'))return;const r=await api('/api/tools',{action:ac,confirm:true});return toast('✅ '+r.msg)}
    case 'logclr':if(!confirm('مسح سجل الأخطاء؟'))return;await api('/api/logs/clear',{});return vLogs()}
  }catch(err){toast(err.message,1)}});
document.addEventListener('input',e=>{const t=e.target;
  if(t.id==='uq'){clearTimeout(DEB);DEB=setTimeout(()=>{U.q=t.value;U.page=1;loadUsers().catch(x=>toast(x.message,1))},300)}
  else if(t.id==='mq'){MQ=t.value;renderModels()}});
document.addEventListener('change',e=>{const t=e.target;
  if(t.id==='uf'){U.f=t.value;U.page=1;loadUsers()}else if(t.id==='us'){U.sort=t.value;U.page=1;loadUsers()}else if(t.id==='ms'){MS=t.value;renderModels()}});
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.id==='pw')doLogin();if(e.key==='Escape')closeModal()});
boot();
})();
</script></body></html>
"""



async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Handler error", exc_info=context.error)


async def post_init(app: Application):
    global http
    http = httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=20))
    store.load_cache()
    if not store.models or time.time() - store.updated_at > 3600:
        try:
            await store.refresh()
            log.info("Fetched %d free models", len(store.models))
        except Exception as e:
            log.error("Initial fetch failed: %s", e)
    await app.bot.set_my_commands([
        BotCommand("start", "القائمة الرئيسية"),
        BotCommand("models", "أقسام الموديلات"),
        BotCommand("refresh", "تحديث الموديلات المجانية"),
        BotCommand("search", "بحث عن موديل"),
        BotCommand("current", "الموديل الحالي"),
        BotCommand("new", "محادثة جديدة"),
        BotCommand("system", "تخصيص تعليمات الذكاء"),
        BotCommand("invite", "رابط دعوتك ونقاطك"),
        BotCommand("help", "المساعدة"),
        BotCommand("id", "معرّفك"),
        BotCommand("cancel", "إلغاء العملية الحالية"),
    ])
    if not all_admin_ids():
        log.warning("⚠️ ADMIN_IDS فارغة: لن تعمل لوحة الأدمن. ضع معرفك (من /id) في أعلى الملف.")
    admin_cmds = [
        BotCommand("admin", "لوحة التحكم"), BotCommand("stats", "الإحصائيات"),
        BotCommand("broadcast", "بث جماعي"), BotCommand("user", "بيانات مستخدم"),
        BotCommand("ban", "حظر مستخدم"), BotCommand("unban", "فك الحظر"),
        BotCommand("allow", "سماح لمستخدم"), BotCommand("disallow", "إزالة السماح"),
    ]
    try:
        base = list(await app.bot.get_my_commands())
        for a in all_admin_ids():
            try:
                await app.bot.set_my_commands(base + admin_cmds, scope=BotCommandScopeChat(a))
            except Exception:
                pass
    except Exception as e:
        log.warning("admin commands scope failed: %s", e)
    await start_web(app)


async def post_shutdown(app: Application):
    users.flush(True)
    stats.flush(True)
    settings.save()
    if BOT_REF.get("runner"):
        try:
            await BOT_REF["runner"].cleanup()
        except Exception:
            pass
    if http:
        await http.aclose()


def main():
    if "ضع_" in TELEGRAM_BOT_TOKEN or "ضع_" in OPENROUTER_API_KEY:
        raise SystemExit("⚠️ ضع TELEGRAM_BOT_TOKEN و OPENROUTER_API_KEY في أعلى الملف أولاً.")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["models", "menu"], cmd_models))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("current", cmd_current))
    app.add_handler(CommandHandler(["new", "reset"], cmd_new))
    app.add_handler(CommandHandler("system", cmd_system))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("invite", cmd_invite))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(
        (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.Document.ALL, on_message))
    # ---- لوحة الأدمن ----
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, admin_input_router), group=-1)
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("user", cmd_user))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("allow", cmd_allow))
    app.add_handler(CommandHandler("disallow", cmd_disallow))
    app.add_error_handler(on_error)
    if app.job_queue:
        app.job_queue.run_repeating(flush_job, interval=60, first=60)

    if AUTO_REFRESH_HOURS > 0:
        if app.job_queue:
            app.job_queue.run_repeating(
                auto_refresh_job, interval=AUTO_REFRESH_HOURS * 3600, first=AUTO_REFRESH_HOURS * 3600)
        else:
            log.warning('JobQueue غير متوفر. ثبّت:  pip install "python-telegram-bot[job-queue]"')

    log.info("Bot started ✅")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
