"""
================================================================
  Num Info Bot — v31 FJ REAL-TIME CHECK
  ✅ FJ: only missing channels shown in prompt
  ✅ FJ: public → real get_chat_member check (left = block)
  ✅ FJ: private → join-request sent = pass
  ✅ FJ: transient errors skip (never wrong-block)
  ✅ FJ: no grace period (real-time every message)
  ✅ All v29 payment/atomic/group fixes retained
================================================================
"""

import os, sys, re, json, time, random, string, threading, queue
import asyncio
import html as html_module, csv, io
from datetime import datetime, timedelta

import requests
import telebot
import telebot.util
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from pymongo import MongoClient, ReturnDocument
from bson.objectid import ObjectId

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("num_info_bot")

def now(): return datetime.now()
def env(k, d):
    v = os.getenv(k)
    return v if v else d

# =================================================================
#  AESTHETIC
# =================================================================
_SMALLCAPS = {
    'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ғ','g':'ɢ','h':'ʜ',
    'i':'ɪ','j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ',
    'q':'ǫ','r':'ʀ','s':'ꜱ','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x',
    'y':'ʏ','z':'ᴢ',
    '0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷',
    '8':'⁸','9':'⁹',
}
_DIV = "━━━━━━━━━━━━━━━━━━━━"
_DIV_SOFT = "— — — — — — — — — — — —"

def fancy(t): return "".join(_SMALLCAPS.get(c.lower(), c) for c in str(t))
def div(): return _DIV
def div_soft(): return _DIV_SOFT
def fancy_dt(): return now().strftime("%d-%b-%Y %I:%M %p")

# =================================================================
#  CONFIG
# =================================================================
BOT_TOKEN       = env("BOT_TOKEN", "")
ADMIN_ID        = int(env("ADMIN_ID", "0"))
BOT_USERNAME    = env("BOT_USERNAME", "@Phoneumber2Info_Robot")
ADMIN_USERNAME  = env("ADMIN_USERNAME", "@itzanjasha")

TG2NUM_URL      = env("TG2NUM_URL", "https://tg2num-botadminshere.vercel.app/")
TG2NUM_KEY      = env("TG2NUM_KEY", "")
TG2NUM_COST     = int(env("TG2NUM_COST", "5"))

API_URL         = env("API_URL", "")
API_KEY         = env("API_KEY", "")
SEARCH_COST     = int(env("SEARCH_COST", "5"))

AADHAAR_URL     = env("AADHAAR_URL", "https://apihitech.vercel.app/search")
AADHAAR_KEY     = env("AADHAAR_KEY", "")
AADHAAR_COST    = int(env("AADHAAR_COST", "10"))

VEHICLE_URL     = env("VEHICLE_URL", "https://rc-x.paskhinpf9.workers.dev/")
VEHICLE_KEY     = env("VEHICLE_KEY", "")
VEHICLE_COST    = int(env("VEHICLE_COST", "10"))

WELCOME_BONUS   = int(env("WELCOME_BONUS", "30"))
REFERRAL_BONUS  = int(env("REFERRAL_BONUS", "10"))
DAILY_TRIES     = int(env("DAILY_TRIES", "0"))

MONGO_URI       = env("MONGO_URI", "")
DB_NAME         = env("DB_NAME", "num2info_bot")

FORCE_CHANNELS_ENV = env("FORCE_CHANNELS", "")
CHANNEL_LINKS_ENV  = env("CHANNEL_LINKS", "")

CREDITS_PER_RUPEE = int(env("CREDITS_PER_RUPEE", "1"))
MIN_PAYMENT       = int(env("MIN_PAYMENT_AMOUNT", "1"))
MAX_PAYMENT       = int(env("MAX_PAYMENT_AMOUNT", "50000"))

UPI_MANUAL_ID     = env("UPI_MANUAL_ID", "")
UPI_MANUAL_QR     = env("UPI_MANUAL_QR", "")

FAM_CREATE_URL    = env("FAM_CREATE_URL", "")
FAM_VERIFY_URL    = env("FAM_VERIFY_URL", "")
FAM_CHECKOUT_URL  = env("FAM_CHECKOUT_STATUS_URL", "")
FAM_API_KEY       = env("FAM_API_KEY", "")
FAM_REDIRECT_URL  = env("FAM_REDIRECT_URL", "")

PYRO_API_ID       = int(env("PYRO_API_ID", "0"))
PYRO_API_HASH     = env("PYRO_API_HASH", "")
PYRO_SESSION      = env("PYRO_SESSION", "")

WELCOME_EMOJIS = ["🌟","🚀","💫","🌈","🔥","⚡","🎯","💎","🌸","✨","🎉","💪","⭐","🦋","🍀"]
ORDER_LIFETIME = 300
CACHE_MAX_AGE_DAYS = 30
MSG_SAFE_LIMIT = 3800
GROUP_AUTO_DELETE_SECONDS = 3600

if not BOT_TOKEN: logger.critical("❌ BOT_TOKEN missing"); sys.exit(1)
if not MONGO_URI: logger.critical("❌ MONGO_URI missing"); sys.exit(1)

def mask_secret(s, secret):
    if not secret or not s: return s
    try: return str(s).replace(str(secret), "***")
    except: return s

# =================================================================
#  MONGODB
# =================================================================
def connect_mongo():
    last = None
    for i in range(3):
        try:
            c = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
            c.admin.command("ping")
            logger.info(f"✅ MongoDB connected (attempt {i+1})")
            return c
        except Exception as e:
            last = e; logger.warning(f"⚠️ Mongo {i+1}: {e}"); time.sleep(3)
    logger.critical(f"❌ MongoDB failed: {last}"); sys.exit(1)

mongo_client = connect_mongo()
db = mongo_client[DB_NAME]
users_col    = db.users
payments_col = db.payments
promo_col    = db.promo_codes
settings_col = db.settings
channels_col = db.force_channels
tg_users_col = db.tg_users
groups_col   = db.groups
logs_col     = db.logs
admins_col   = db.admins
feedback_col = db.feedback

def init_db():
    try:
        users_col.create_index("user_id", unique=True)
        channels_col.create_index("channel_id", unique=True)
        payments_col.create_index("status")
        payments_col.create_index("user_id")
        payments_col.create_index("order_id", sparse=True)
        payments_col.create_index([("status", 1), ("created_at", -1)])
        tg_users_col.create_index("user_id", unique=True)
        tg_users_col.create_index("username_lower", sparse=True)
        groups_col.create_index("chat_id", unique=True)
        admins_col.create_index("user_id", unique=True)
    except Exception as e: logger.warning(f"⚠️ Index: {e}")
    try: payments_col.drop_index("utr_1")
    except: pass
    try:
        payments_col.create_index("utr", unique=True,
            partialFilterExpression={"utr": {"$type": "string"}},
            name="utr_unique_partial")
    except Exception as e: logger.warning(f"⚠️ utr: {e}")

    defaults = {
        "credits_per_rupee": CREDITS_PER_RUPEE,
        "search_cost": SEARCH_COST, "aadhaar_cost": AADHAAR_COST,
        "tg2num_cost": TG2NUM_COST, "vehicle_cost": VEHICLE_COST,
        "welcome_bonus": WELCOME_BONUS, "referral_bonus": REFERRAL_BONUS,
        "referral_enabled": 1, "daily_tries": DAILY_TRIES,
        "gateway_enabled": 0,
        "gateway_create_url": FAM_CREATE_URL,
        "gateway_checkout_status_url": FAM_CHECKOUT_URL,
        "gateway_api_key": FAM_API_KEY,
        "gateway_redirect_url": FAM_REDIRECT_URL,
        "upi_manual_id": UPI_MANUAL_ID, "upi_manual_qr": UPI_MANUAL_QR,
        "upi_manual_enabled": 1, "force_enabled": "1", "maintenance_mode": 0,
        "min_payment": MIN_PAYMENT, "max_payment": MAX_PAYMENT,
        "group_enabled": 1,
        "group_welcome": "👋 Bot added! Type /start to begin.",
        "group_auto_delete": 1,
        "group_auto_delete_seconds": GROUP_AUTO_DELETE_SECONDS,
        "broadcast_pin": 0, "broadcast_forward": 0,
        "welcome_emoji": "", "powered_by": "", "about_text": "",
        "api_url_env": API_URL, "api_key_env": API_KEY,
        "tg2num_url_env": TG2NUM_URL, "tg2num_key_env": TG2NUM_KEY,
        "aadhaar_url_env": AADHAAR_URL, "aadhaar_key_env": AADHAAR_KEY,
        "vehicle_url_env": VEHICLE_URL, "vehicle_key_env": VEHICLE_KEY,
        "welcome_media": "", "welcome_media_type": "",
        "support_link": "", "upi_extra_note": "",
        "fj_custom_msg": "",
        "aadhaar_live_url": "https://apihitech.vercel.app/search?q=",
    }
    try:
        existing_keys = set(d["key"] for d in settings_col.find({}, {"key": 1}))
        bulk_ops = []
        for k, v in defaults.items():
            if k not in existing_keys:
                bulk_ops.append({"key": k, "value": v})
        if bulk_ops:
            try: settings_col.insert_many(bulk_ops, ordered=False)
            except: pass
    except: pass

    if channels_col.count_documents({}) == 0 and FORCE_CHANNELS_ENV:
        ids = [int(c.strip()) for c in FORCE_CHANNELS_ENV.split(",") if c.strip()]
        links = [l.strip() for l in CHANNEL_LINKS_ENV.split(",") if l.strip()] if CHANNEL_LINKS_ENV else []
        for i, cid in enumerate(ids):
            link = links[i] if i < len(links) else f"https://t.me/joinchat/{cid}"
            try: channels_col.insert_one({"channel_id": cid, "channel_link": link, "enabled": 1})
            except: pass
    logger.info("✅ DB initialized")

def get_setting(k, d=None):
    try:
        doc = settings_col.find_one({"key": k})
        return doc["value"] if doc else d
    except: return d

def set_setting(k, v):
    try: settings_col.update_one({"key": k}, {"$set": {"value": v}}, upsert=True)
    except: pass

def log_action(admin_id, action, details=None):
    try:
        logs_col.insert_one({"admin_id": admin_id, "action": action,
            "details": details or "", "at": now()})
    except: pass

def is_main_admin(uid): return uid == ADMIN_ID
def is_sub_admin(uid):
    if uid == ADMIN_ID: return True
    try: return admins_col.find_one({"user_id": uid}) is not None
    except: return False
def is_admin_user(uid): return uid == ADMIN_ID or is_sub_admin(uid)

# =================================================================
#  USER
# =================================================================
def today_str(): return now().strftime("%Y-%m-%d")

def get_or_create_user(uid):
    try:
        u = users_col.find_one({"user_id": uid})
        if u: return u
        wb = int(get_setting("welcome_bonus", WELCOME_BONUS))
        doc = {
            "user_id": uid, "credits": wb,
            "total_referrals": 0, "bonus_earned": 0,
            "banned": 0, "searches": 0,
            "tries_used": 0, "tries_date": today_str(),
            "fj_verified": False,
            "fj_verified_at": None,
            "fj_requested_channels": [],
            "pending_referrer": None,
            "joined_at": now(), "last_seen": now()
        }
        users_col.update_one({"user_id": uid}, {"$setOnInsert": doc}, upsert=True)
        return users_col.find_one({"user_id": uid}) or doc
    except Exception as e:
        logger.error(f"get_or_create_user: {e}")
        return {"user_id": uid, "credits": 0, "banned": 0, "fj_requested_channels": []}

def get_credits(uid): return get_or_create_user(uid).get("credits", 0)

def add_credits(uid, amt):
    try:
        get_or_create_user(uid)
        users_col.update_one({"user_id": uid}, {"$inc": {"credits": amt}})
        return True
    except Exception as e:
        logger.error(f"add_credits: {e}")
        return False

def deduct_credits(uid, amt):
    try:
        res = users_col.find_one_and_update(
            {"user_id": uid, "credits": {"$gte": amt}},
            {"$inc": {"credits": -amt}},
            return_document=ReturnDocument.AFTER)
        return res is not None
    except Exception as e:
        logger.error(f"deduct_credits: {e}"); return False

def incr_searches(uid):
    try: users_col.update_one({"user_id": uid}, {"$inc": {"searches": 1}})
    except: pass

def get_tries_remaining(uid):
    if is_admin_user(uid): return "unlimited"
    limit = int(get_setting("daily_tries", DAILY_TRIES))
    if limit <= 0: return "unlimited"
    try:
        u = get_or_create_user(uid)
        used = int(u.get("tries_used", 0))
        if u.get("tries_date") != today_str():
            users_col.update_one({"user_id": uid},
                {"$set": {"tries_used": 0, "tries_date": today_str()}})
            used = 0
        return max(0, limit - used)
    except: return limit

def consume_try(uid):
    if is_admin_user(uid): return True
    limit = int(get_setting("daily_tries", DAILY_TRIES))
    if limit <= 0: return True
    try:
        today = today_str()
        users_col.update_one(
            {"user_id": uid, "tries_date": {"$ne": today}},
            {"$set": {"tries_used": 0, "tries_date": today}})
        res = users_col.find_one_and_update(
            {"user_id": uid, "tries_used": {"$lt": limit}},
            {"$inc": {"tries_used": 1}},
            return_document=ReturnDocument.AFTER)
        return res is not None
    except Exception as e:
        logger.error(f"consume_try: {e}"); return True

def tries_display(uid):
    r = get_tries_remaining(uid)
    if r == "unlimited": return f"{fancy('unlimited')} ♾️"
    return str(r)

def add_referral_bonus(rid):
    try:
        if is_banned(rid): return False
        b = int(get_setting("referral_bonus", REFERRAL_BONUS))
        users_col.update_one({"user_id": rid},
            {"$inc": {"credits": b, "total_referrals": 1, "bonus_earned": b}})
        return True
    except: return False

def is_banned(uid):
    try:
        u = users_col.find_one({"user_id": uid})
        return u and u.get("banned", 0) == 1
    except: return False

def is_fj_verified(uid):
    try:
        u = users_col.find_one({"user_id": uid}, {"fj_verified": 1})
        return bool(u and u.get("fj_verified"))
    except: return False

def mark_fj_verified(uid):
    """Sirf stats ke liye — gating real-time check se hoti hai"""
    try:
        users_col.update_one({"user_id": uid},
            {"$set": {"fj_verified": True, "fj_verified_at": now()}},
            upsert=True)
    except Exception as e:
        logger.error(f"mark_fj_verified: {e}")

def unmark_fj_verified(uid):
    try:
        users_col.update_one({"user_id": uid},
            {"$set": {"fj_verified": False, "fj_requested_channels": []},
             "$unset": {"fj_verified_at": ""}})
    except: pass

def mark_join_request(uid, cid):
    try:
        users_col.update_one(
            {"user_id": uid},
            {"$addToSet": {"fj_requested_channels": cid}},
            upsert=True)
        logger.info(f"📥 Join request tracked: U{uid} → C{cid}")
    except Exception as e:
        logger.error(f"mark_join_request: {e}")

def has_join_request(uid, cid):
    try:
        u = users_col.find_one({"user_id": uid}, {"fj_requested_channels": 1})
        if not u: return False
        return cid in u.get("fj_requested_channels", [])
    except: return False

def clear_join_requests(uid):
    try:
        users_col.update_one({"user_id": uid},
            {"$set": {"fj_requested_channels": []}})
    except: pass

def clear_channel_join_request(uid, cid):
    try:
        users_col.update_one({"user_id": uid},
            {"$pull": {"fj_requested_channels": cid}})
    except: pass

def ban_user(uid):
    try: users_col.update_one({"user_id": uid}, {"$set": {"banned": 1}}, upsert=True)
    except: pass

def unban_user(uid):
    try: users_col.update_one({"user_id": uid}, {"$set": {"banned": 0}}, upsert=True)
    except: pass

def all_users():
    try: return [u["user_id"] for u in users_col.find({"banned": 0}, {"user_id": 1})]
    except: return []

def user_stats(uid):
    u = get_or_create_user(uid)
    return u.get("total_referrals",0), u.get("bonus_earned",0), u.get("searches",0)

def total_users():
    try: return users_col.count_documents({"banned": 0})
    except: return 0

def total_searches():
    try:
        a = list(users_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$searches"}}}]))
        return a[0]["t"] if a else 0
    except: return 0

def new_users_24h():
    try:
        c = now() - timedelta(hours=24)
        return users_col.count_documents({"joined_at": {"$gte": c}})
    except: return 0

def upd_last_seen(uid):
    try: users_col.update_one({"user_id": uid}, {"$set": {"last_seen": now()}})
    except: pass

def export_csv():
    try:
        us = list(users_col.find({}, {"user_id":1,"credits":1,"searches":1,
                                       "total_referrals":1,"banned":1,"joined_at":1}))
        o = io.StringIO(); w = csv.writer(o)
        w.writerow(["User ID","Credits","Searches","Referrals","Banned","Joined"])
        for u in us:
            w.writerow([u.get("user_id"),u.get("credits",0),u.get("searches",0),
                u.get("total_referrals",0),u.get("banned",0),
                u.get("joined_at","").strftime("%Y-%m-%d") if u.get("joined_at") else ""])
        return o.getvalue()
    except: return None

# =================================================================
#  GROUPS
# =================================================================
def register_group(chat_id, title, username=None):
    try:
        groups_col.update_one({"chat_id": chat_id},
            {"$set": {"title": title, "username": username, "last_seen": now()},
             "$setOnInsert": {"added_at": now(), "enabled": 1}}, upsert=True)
    except: pass

def remove_group(chat_id):
    try: groups_col.delete_one({"chat_id": chat_id})
    except: pass

def all_groups():
    try: return list(groups_col.find().sort("added_at", -1))
    except: return []

def group_count():
    try: return groups_col.count_documents({})
    except: return 0

# =================================================================
#  CACHE
# =================================================================
def cache_tg_user(user):
    try:
        if not user or getattr(user, 'is_bot', False): return
        doc = {"user_id": user.id,
            "username": getattr(user, 'username', None),
            "first_name": getattr(user, 'first_name', '') or "",
            "last_name": getattr(user, 'last_name', '') or "",
            "full_name": f"{getattr(user,'first_name','') or ''} {getattr(user,'last_name','') or ''}".strip(),
            "cached_at": now(), "last_seen": now()}
        upd = {"$set": doc}
        if doc.get("username"): upd["$set"]["username_lower"] = doc["username"].lower()
        tg_users_col.update_one({"user_id": user.id}, upd, upsert=True)
    except: pass

def cache_dict(d):
    try:
        if not d or not d.get("user_id"): return
        doc = {"user_id": d["user_id"]}
        for k in ("username","first_name","last_name","full_name","bio",
                  "is_bot","is_premium","is_verified"):
            if d.get(k) is not None: doc[k] = d[k]
        doc["cached_at"] = now(); doc["last_seen"] = now()
        upd = {"$set": doc}
        if d.get("username"): upd["$set"]["username_lower"] = d["username"].lower()
        else: upd["$unset"] = {"username_lower": ""}
        tg_users_col.update_one({"user_id": d["user_id"]}, upd, upsert=True)
    except: pass

def get_cached_user(uid=None, username=None):
    try:
        q = {}
        if uid is not None: q["user_id"] = uid
        elif username: q["username_lower"] = username.lower()
        else: return None
        u = tg_users_col.find_one(q)
        if not u: return None
        ca = u.get("cached_at")
        if ca and (now() - ca).days > CACHE_MAX_AGE_DAYS: return None
        return u
    except: return None

# =================================================================
#  PYROGRAM
# =================================================================
pyro = None; _pyro_loop = None; _pyro_ready = False; _pyro_me = None; _pyro_error = None

def _ensure_main_loop():
    try: asyncio.set_event_loop(asyncio.new_event_loop())
    except: pass

def init_pyrogram():
    global _pyro_loop, _pyro_ready, _pyro_error
    _ensure_main_loop()
    if not PYRO_SESSION or not PYRO_API_ID or not PYRO_API_HASH:
        logger.warning("⚠️ Pyrogram not configured"); _pyro_error = "no_session"; return
    try: from pyrogram import Client  # noqa
    except ImportError as e:
        logger.error(f"❌ pyrogram: {e}"); _pyro_error = "no_lib"; return
    _pyro_loop = asyncio.new_event_loop()
    def _runner():
        asyncio.set_event_loop(_pyro_loop)
        try: _pyro_loop.run_until_complete(_boot())
        except Exception as e:
            logger.error(f"❌ Pyro: {e}"); _pyro_error = f"{type(e).__name__}: {e}"
    threading.Thread(target=_runner, daemon=True, name="PyroRunner").start()
    for _ in range(60):
        if _pyro_ready: break
        time.sleep(0.5)
    if not _pyro_ready: logger.warning(f"⚠️ Pyro not ready ({_pyro_error})")

async def _boot():
    global pyro, _pyro_ready, _pyro_me, _pyro_error
    try:
        from pyrogram import Client
        from pyrogram.errors import AuthKeyUnregistered, AuthKeyDuplicated
    except ImportError as e: _pyro_error = f"import: {e}"; return
    try:
        pyro = Client("pyro_session", api_id=PYRO_API_ID, api_hash=PYRO_API_HASH,
            session_string=PYRO_SESSION, in_memory=True, no_updates=True)
        await pyro.start(); await asyncio.sleep(0.3)
        _pyro_me = await pyro.get_me()
        _pyro_ready = True
        logger.info(f"✅ Pyrogram: @{_pyro_me.username or _pyro_me.id}")
    except AuthKeyUnregistered: _pyro_error = "auth_key_unregistered"; return
    except AuthKeyDuplicated: _pyro_error = "auth_key_duplicated"; return
    except Exception as e: _pyro_error = f"{type(e).__name__}: {e}"; return
    while True:
        try: await asyncio.sleep(3600)
        except asyncio.CancelledError: break

def pyro_resolve_username(username, timeout=20):
    if not _pyro_ready or not pyro or not _pyro_loop: return None
    try:
        u = username.strip().lstrip("@")
        if not u: return None
        fut = asyncio.run_coroutine_threadsafe(_resolve_u_async(u), _pyro_loop)
        return fut.result(timeout=timeout)
    except Exception as e: logger.error(f"resolve_u: {e}"); return None

def pyro_resolve_id(uid, timeout=15):
    if not _pyro_ready or not pyro or not _pyro_loop: return None
    try:
        fut = asyncio.run_coroutine_threadsafe(_resolve_id_async(int(uid)), _pyro_loop)
        return fut.result(timeout=timeout)
    except Exception as e: logger.error(f"resolve_id: {e}"); return None

async def _resolve_u_async(username):
    try:
        from pyrogram.errors import UsernameNotOccupied, UsernameInvalid, FloodWait
        user = await pyro.get_users(username); return await _u_to_info(user)
    except UsernameNotOccupied: return {"error": "not_found"}
    except UsernameInvalid: return {"error": "invalid"}
    except FloodWait as e: return {"error": f"flood_{e.value}s"}
    except Exception as e: logger.error(f"_resolve_u: {e}"); return None

async def _resolve_id_async(uid):
    try:
        from pyrogram.errors import PeerIdInvalid, FloodWait
        user = await pyro.get_users(uid); return await _u_to_info(user)
    except PeerIdInvalid: return {"error": "peer_id_invalid"}
    except FloodWait as e: return {"error": f"flood_{e.value}s"}
    except Exception as e: logger.error(f"_resolve_id: {e}"); return None

async def _u_to_info(user):
    info = {"user_id": user.id, "username": user.username,
        "first_name": getattr(user, 'first_name', '') or "",
        "last_name": getattr(user, 'last_name', '') or "",
        "is_bot": getattr(user, 'is_bot', False),
        "is_premium": getattr(user, 'is_premium', False),
        "is_verified": getattr(user, 'is_verified', False),
        "source": "mtproto"}
    info["full_name"] = f"{info['first_name']} {info['last_name']}".strip()
    return info

# =================================================================
#  APIs
# =================================================================
def query_number(phone):
    api_url = get_setting("api_url_env", API_URL)
    api_key = get_setting("api_key_env", API_KEY)
    if not api_url: return False, None, "API URL not configured"
    try:
        base_url = api_url.rstrip('/')
        url = f"{base_url}/?number={phone}"
        if api_key: url += f"&key={api_key}"
        logger.info(f"📞 Number API: {mask_secret(url, api_key)}")
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200: return False, None, f"HTTP {r.status_code}"
        try: data = r.json()
        except: return False, None, "Invalid JSON"
        if not data.get("success"): return False, None, data.get("message", "API error")
        if not data.get("result") and not data.get("data"): return False, None, "No data"
        return True, data, None
    except requests.exceptions.Timeout: return False, None, "Timeout"
    except Exception as e: return False, None, str(e)

def query_aadhaar(aadhaar):
    a_url = get_setting("aadhaar_url_env", AADHAAR_URL) or "https://apihitech.vercel.app/search?q="
    a_key = get_setting("aadhaar_key_env", AADHAAR_KEY)
    if not a_url: return False, None, "Aadhaar URL not configured"
    try:
        base = str(a_url).strip()
        a = re.sub(r'\D', '', str(aadhaar))
        if base.endswith('='): url = f"{base}{a}"
        elif '?' in base:
            if 'q=' in base or 'aadhaar=' in base: url = f"{base}{a}"
            else: url = f"{base}&q={a}"
        else: url = f"{base}?q={a}"
        if a_key:
            sep = '&' if '?' in url else '?'
            url += f"{sep}key={a_key}"
        logger.info(f"🆔 Aadhaar API: {mask_secret(url, a_key)}")
        r = requests.get(url, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            logger.error(f"Aadhaar HTTP {r.status_code}: {r.text[:300]}")
            return False, None, f"HTTP {r.status_code}"
        try: data = r.json()
        except Exception as e:
            logger.error(f"Aadhaar JSON error: {e} | raw: {r.text[:300]}")
            return False, None, "Invalid JSON"
        logger.info(f"🆔 Aadhaar resp: {json.dumps(data, default=str)[:500]}")
        if isinstance(data, dict):
            if data.get("success") is False: return False, None, data.get("message", "Not found")
            if data.get("status") in ("error", "fail", "failed"): return False, None, data.get("message", "Not found")
            if data.get("error"): return False, None, str(data.get("error"))
        return True, data, None
    except requests.exceptions.Timeout: return False, None, "Timeout"
    except Exception as e: return False, None, str(e)

def query_vehicle(vehicle):
    v_url = get_setting("vehicle_url_env", VEHICLE_URL) or "https://rc-x.paskhinpf9.workers.dev/"
    v_key = get_setting("vehicle_key_env", VEHICLE_KEY)
    if not v_url: return False, None, "Vehicle URL not configured"
    try:
        base = str(v_url).strip()
        v = re.sub(r'[\s\-]', '', str(vehicle)).upper()
        if base.endswith('='): url = f"{base}{requests.utils.quote(v)}"
        elif 'vehicle=' in base: url = f"{base}{requests.utils.quote(v)}"
        elif '?' in base: url = f"{base}&vehicle={requests.utils.quote(v)}"
        else: url = f"{base}?vehicle={requests.utils.quote(v)}"
        if v_key:
            sep = '&' if '?' in url else '?'
            url += f"{sep}key={v_key}"
        logger.info(f"🚗 Vehicle API: {mask_secret(url, v_key)}")
        r = requests.get(url, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            logger.error(f"Vehicle HTTP {r.status_code}: {r.text[:300]}")
            return False, None, f"HTTP {r.status_code}"
        try: data = r.json()
        except Exception as e:
            logger.error(f"Vehicle JSON error: {e}")
            return False, None, "Invalid JSON"
        logger.info(f"🚗 Vehicle resp: {json.dumps(data, default=str)[:500]}")
        if isinstance(data, dict):
            if data.get("success") is False: return False, None, data.get("message", "Not found")
            if data.get("status") in ("error", "fail", "failed"): return False, None, data.get("message", "Not found")
            if data.get("error"): return False, None, str(data.get("error"))
        return True, data, None
    except requests.exceptions.Timeout: return False, None, "Timeout"
    except Exception as e: return False, None, str(e)

def query_tg2num_id(tg_id):
    tg_url = get_setting("tg2num_url_env", TG2NUM_URL)
    tg_key = get_setting("tg2num_key_env", TG2NUM_KEY)
    if not tg_url: return False, None, "TG2NUM_URL not configured"
    try:
        tg_id_str = str(tg_id).strip()
        base = tg_url.rstrip("/")
        url = f"{base}/?id={requests.utils.quote(tg_id_str)}"
        if tg_key: url += f"&key={tg_key}"
        logger.info(f"🔍 TG2Num URL: {mask_secret(url, tg_key)}")
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            logger.error(f"TG2Num HTTP {r.status_code}: {r.text[:300]}")
            return False, None, f"HTTP {r.status_code}"
        try: data = r.json()
        except Exception as e:
            logger.error(f"TG2Num JSON error: {e}")
            return False, None, "Invalid JSON"
        logger.info(f"🔍 TG2Num response: {json.dumps(data, default=str)[:500]}")
        if not data.get("success"):
            return False, None, data.get("message", "API returned success=false")
        result = data.get("result")
        if isinstance(result, list) and result: result = result[0]
        if not isinstance(result, dict) or not result.get("number"):
            return False, None, "No number in result"
        return True, result, None
    except requests.exceptions.Timeout: return False, None, "Timeout"
    except Exception as e: return False, None, str(e)

# =================================================================
#  RESOLVER
# =================================================================
def resolve_any(query):
    q = str(query).strip()
    if "t.me/" in q or "telegram.me/" in q:
        part = q.split("t.me/")[-1] if "t.me/" in q else q.split("telegram.me/")[-1]
        part = part.split("?")[0].strip("/")
        if "/" in part: part = part.split("/")[0]
        q = part
    q = q.lstrip("@")
    if not q: return None, None

    if q.isdigit():
        uid = int(q)
        u = get_cached_user(uid=uid)
        if u: u["source"] = "cache"; return u, "cache"
        if _pyro_ready:
            r = pyro_resolve_id(uid, timeout=15)
            if r and r.get("user_id"):
                cache_dict(r); return r, "mtproto"
        try:
            chat = bot.get_chat(uid)
            info = {"user_id": chat.id,
                "username": getattr(chat, 'username', None),
                "first_name": getattr(chat, 'first_name', None),
                "last_name": getattr(chat, 'last_name', None),
                "full_name": f"{getattr(chat,'first_name','') or ''} {getattr(chat,'last_name','') or ''}".strip(),
                "source": "telegram_api"}
            cache_dict(info); return info, "telegram_api"
        except Exception as e: logger.warning(f"bot.get_chat({uid}): {e}")
        return None, None

    u = get_cached_user(username=q)
    if u: u["source"] = "cache"; return u, "cache"
    if _pyro_ready:
        r = pyro_resolve_username(q, timeout=20)
        if r and r.get("user_id"):
            cache_dict(r); return r, "mtproto"
    try:
        chat = bot.get_chat(f"@{q}")
        info = {"user_id": chat.id,
            "username": getattr(chat, 'username', None),
            "first_name": getattr(chat, 'first_name', None),
            "last_name": getattr(chat, 'last_name', None),
            "full_name": f"{getattr(chat,'first_name','') or ''} {getattr(chat,'last_name','') or ''}".strip(),
            "source": "telegram_api"}
        cache_dict(info); return info, "telegram_api"
    except Exception as e: logger.warning(f"bot.get_chat(@{q}): {e}")
    return None, None

# =================================================================
#  PAYMENTS
# =================================================================
def create_payment(uid, cid, amount, credits, pay_mode, screenshot_id=None,
                    order_id=None, payment_link=None, gateway_raw=None):
    doc = {"user_id": uid, "chat_id": cid, "amount": amount, "credits": credits,
        "pay_mode": pay_mode, "screenshot_id": screenshot_id,
        "order_id": order_id, "payment_link": payment_link,
        "status": "pending", "credited": False, "created_at": now(),
        "approved_at": None, "approved_by": None,
        "reject_reason": None, "gateway_response": gateway_raw}
    try: return str(payments_col.insert_one(doc).inserted_id)
    except Exception as e: logger.error(f"create_payment: {e}"); return None

def get_payment(pid):
    try: return payments_col.find_one({"_id": ObjectId(pid)})
    except: return None

def get_pending():
    try: return list(payments_col.find({"status": "pending"}).sort("created_at", 1))
    except: return []

def _credit_payment_atomic(p):
    if not p: return False
    pid = p["_id"]
    claimed = payments_col.find_one_and_update(
        {"_id": pid, "credited": {"$ne": True}},
        {"$set": {"credited": True, "credited_at": now()}},
        return_document=ReturnDocument.AFTER)
    if not claimed:
        logger.info(f"Payment {pid} already credited — skipping")
        return False
    ok = add_credits(claimed["user_id"], claimed["credits"])
    if not ok:
        payments_col.update_one({"_id": pid},
            {"$set": {"credited": False, "credit_error": "add_credits failed"}})
        logger.error(f"❌ CRITICAL: credit failed for payment {pid}")
        return False
    return True

def approve_atomic(pid, aid):
    try: oid = ObjectId(pid)
    except: return False, None
    r = payments_col.find_one_and_update(
        {"_id": oid, "status": "pending"},
        {"$set": {"status": "approved", "approved_at": now(), "approved_by": aid}},
        return_document=ReturnDocument.AFTER)
    if not r:
        return False, payments_col.find_one({"_id": oid})
    _credit_payment_atomic(r)
    return True, r

def reject_atomic(pid, aid, reason="Rejected"):
    try: oid = ObjectId(pid)
    except: return False, None
    try:
        r = payments_col.find_one_and_update(
            {"_id": oid, "status": "pending"},
            {"$set": {"status": "rejected", "rejected_at": now(),
                      "approved_by": aid, "reject_reason": reason}},
            return_document=ReturnDocument.AFTER)
        if not r: return False, payments_col.find_one({"_id": oid})
        return True, r
    except: return False, None

def pay_stats():
    try:
        p = payments_col.count_documents({"status": "pending"})
        a = payments_col.count_documents({"status": "approved"})
        r = payments_col.count_documents({"status": "rejected"})
        agg = list(payments_col.aggregate([{"$match": {"status": "approved"}},
            {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
        rev = agg[0]["t"] if agg else 0
        return p, a, r, rev
    except: return 0, 0, 0, 0

def total_credits_sold():
    try:
        agg = list(payments_col.aggregate([{"$match": {"status": "approved"}},
            {"$group": {"_id": None, "t": {"$sum": "$credits"}}}]))
        return agg[0]["t"] if agg else 0
    except: return 0

def revenue_24h():
    try:
        c = now() - timedelta(hours=24)
        agg = list(payments_col.aggregate([
            {"$match": {"status": "approved", "approved_at": {"$gte": c}}},
            {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
        return agg[0]["t"] if agg else 0
    except: return 0

def revenue_7d():
    try:
        c = now() - timedelta(days=7)
        agg = list(payments_col.aggregate([
            {"$match": {"status": "approved", "approved_at": {"$gte": c}}},
            {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
        return agg[0]["t"] if agg else 0
    except: return 0

def all_promos():
    try: return list(promo_col.find().sort("_id", -1))
    except: return []

def gen_promo():
    c = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = ''.join(random.choices(c, k=12))
        if not promo_col.find_one({"code": code}): return code
    return ''.join(random.choices(c, k=12))

def save_promo(code, rc, mu, aid):
    try:
        promo_col.insert_one({"code": code, "reward_credits": rc, "max_users": mu,
            "used_count": 0, "used_by": [], "generated_by": aid,
            "created_at": datetime.now().strftime('%Y-%m-%d'), "active": 1})
        return True
    except Exception as e:
        logger.error(f"save_promo: {e}")
        return False

def redeem_promo(code, uid):
    try:
        d = promo_col.find_one({"code": code})
        if not d: return None
        if d.get("active", 1) == 0: return None
        if uid in d.get("used_by", []): return -1
        res = promo_col.find_one_and_update(
            {"code": code, "active": 1,
             "used_count": {"$lt": d.get("max_users", 0)},
             "used_by": {"$ne": uid}},
            {"$inc": {"used_count": 1}, "$push": {"used_by": uid}},
            return_document=ReturnDocument.AFTER)
        if not res:
            return -1 if uid in d.get("used_by", []) else None
        r = res.get("reward_credits", 0)
        add_credits(uid, r)
        return r
    except Exception as e:
        logger.error(f"redeem_promo: {e}"); return None

def all_channels():
    try: return list(channels_col.find({"enabled": 1}))
    except: return []

def channel_list():
    try: return list(channels_col.find().sort("_id", 1))
    except: return []

def add_channel_db(cid, link):
    try:
        if channels_col.find_one({"channel_id": cid}): return False
        channels_col.insert_one({"channel_id": cid, "channel_link": link, "enabled": 1})
        return True
    except: return False

def remove_channel_db(cid):
    try: return channels_col.delete_one({"channel_id": cid}).deleted_count > 0
    except: return False

def is_auto_upi_available():
    if int(get_setting("gateway_enabled", 0)) != 1: return False
    if not get_setting("gateway_create_url", ""): return False
    if not get_setting("gateway_api_key", ""): return False
    return True

def create_gateway_order(amount, uid):
    url = get_setting("gateway_create_url", "") or FAM_CREATE_URL
    key = get_setting("gateway_api_key", "") or FAM_API_KEY
    redirect = get_setting("gateway_redirect_url", "") or FAM_REDIRECT_URL
    if not url or not key: return False, None, None, None, None, "Not configured"
    try:
        headers = {"X-Api-Key": key, "Content-Type": "application/json"}
        payload = {"amount": float(amount), "redirect_url": redirect,
                   "customer_name": f"user_{uid}", "api_key": key}
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code not in (200, 201): return False, None, None, None, None, f"HTTP {r.status_code}"
        try: raw = r.json()
        except: return False, None, None, None, None, "Bad JSON"
        if raw.get("status") != "success":
            return False, None, None, None, None, f"Status: {raw.get('status')}"
        data = raw.get("data") or {}
        oid = data.get("order_id")
        if not oid: return False, None, None, None, None, "No order_id"
        return True, str(oid), data.get("checkout_url"), data.get("qr_url"), data.get("upi_id"), raw
    except requests.exceptions.Timeout: return False, None, None, None, None, "Timeout"
    except Exception as e: return False, None, None, None, None, f"Error: {e}"

def verify_gateway_order(order_id):
    cs = get_setting("gateway_checkout_status_url", "") or FAM_CHECKOUT_URL
    try:
        r = requests.get(f"{cs}?order_id={order_id}", timeout=15)
        if r.status_code == 200:
            try:
                raw = r.json()
                status = str(raw.get("status", "")).lower()
                if status == "success":
                    return True, "success", {"utr": raw.get("utr"),
                        "sender_name": raw.get("sender_name"),
                        "paid_at": raw.get("paid_at"),
                        "amount": raw.get("amount"), "raw": raw}
                elif status in ("pending", "expired"): return False, status, raw
            except: pass
    except: pass
    return False, "error", None

def download_qr_bytes(qr_url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(qr_url, timeout=15, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 100: return r.content
        except: pass
        time.sleep(1)
    return None

def send_qr_image(cid, qr_url, caption, kb, reply_to=None):
    content = download_qr_bytes(qr_url)
    if not content: return None
    try:
        kw = {"caption": caption, "parse_mode": "HTML", "reply_markup": kb}
        if reply_to: kw["reply_to_message_id"] = reply_to
        return bot.send_photo(cid, content, **kw)
    except Exception as e: logger.error(f"[QR] {e}"); return None

# =================================================================
#  BOT INIT
# =================================================================
bot = telebot.TeleBot(BOT_TOKEN)
try: bot.remove_webhook()
except: pass

_bot_me_cache = None
def get_bot_me():
    global _bot_me_cache
    if _bot_me_cache is None:
        try: _bot_me_cache = bot.get_me()
        except Exception as e:
            logger.error(f"get_bot_me: {e}")
            return None
    return _bot_me_cache

def send_typing(cid):
    try: bot.send_chat_action(cid, 'typing')
    except: pass

def safe_ans(call, text=None, alert=False):
    try:
        if text is None: bot.answer_callback_query(call.id)
        else: bot.answer_callback_query(call.id, text, show_alert=alert)
    except: pass

# =================================================================
#  FOOTER
# =================================================================
def build_footer(uid):
    powered = get_setting("powered_by", "") or f"{BOT_USERNAME} | {ADMIN_USERNAME}"
    return (f"{div_soft()}\n"
            f"📅 {fancy('generated')}: {fancy_dt()}\n"
            f"🛡️ {fancy('powered by')} {powered}\n"
            f"{div_soft()}\n"
            f"🎯 {fancy('tries remaining')}: <b>{tries_display(uid)}</b>")

# =================================================================
#  ANIMATION
# =================================================================
class AnimMsg:
    EDIT_INTERVAL = 1.1; BAR_LEN = 18
    SPINNERS = ["◐", "◓", "◑", "◒"]
    def __init__(self, cid, stages=None, title="PROCESSING", reply_to=None):
        self.cid = cid; self.reply_to = reply_to
        self.title = fancy(title)
        self.mid = None; self._stop = threading.Event(); self._t = None
        self._start_time = time.time()
        self._dead = False
        self._lock = threading.Lock()
        self.frames = self._build(stages or [])
    def _build(self, stages):
        frames = []; total = len(stages) or 1; BAR = self.BAR_LEN
        for idx, stage in enumerate(stages):
            label = fancy(stage.get("label", "Working"))
            emojis = stage.get("emojis", ["⏳"]); duration = stage.get("duration", 1.5)
            n_frames = max(2, int(duration / self.EDIT_INTERVAL))
            for i in range(n_frames):
                sf = (i + 1) / n_frames; ov = (idx + sf) / total
                pct = min(99, int(ov * 100))
                filled = int(BAR * ov)
                bar = "█" * filled + "░" * (BAR - filled)
                spin = self.SPINNERS[i % len(self.SPINNERS)]
                emoji = emojis[i % len(emojis)]
                step_txt = fancy(f"step {idx+1} of {total}")
                frames.append(f"<b>🎯 {self.title}</b>\n{div()}\n"
                    f"<code>{bar}</code> <b>{pct}%</b>\n\n"
                    f"{spin} {emoji} <b>{label}</b>\n<i>{step_txt}</i>")
        return frames
    def start(self):
        try:
            kw = {"parse_mode": "HTML"}
            if self.reply_to: kw["reply_to_message_id"] = self.reply_to
            m = bot.send_message(self.cid, self.frames[0], **kw)
            self.mid = m.message_id
            self._t = threading.Thread(target=self._run, daemon=True); self._t.start()
            return True
        except Exception as e:
            logger.warning(f"AnimMsg.start: {e}"); return False
    def _run(self):
        i = 1
        while not self._stop.is_set() and i < len(self.frames):
            if self._dead: return
            try: bot.edit_message_text(self.frames[i], self.cid, self.mid, parse_mode="HTML")
            except Exception as e:
                err = str(e).lower()
                if "message to edit not found" in err or "message can't be edited" in err:
                    self._dead = True; return
                if "too many requests" in err: time.sleep(3); continue
            i += 1
            end = time.time() + self.EDIT_INTERVAL
            while time.time() < end:
                if self._stop.is_set(): return
                time.sleep(0.1)
        while not self._stop.is_set() and not self._dead:
            try: bot.edit_message_text(self.frames[-1], self.cid, self.mid, parse_mode="HTML")
            except Exception as e:
                if "message to edit not found" in str(e).lower():
                    self._dead = True; return
            time.sleep(2)
    def stop(self):
        self._stop.set()
        if self._t:
            try: self._t.join(timeout=3)
            except: pass
    def flash_complete(self, delay=0.4):
        with self._lock:
            if self._dead: return
            elapsed = time.time() - self._start_time
            bar = "█" * self.BAR_LEN
            text = (f"<b>🎯 {self.title}</b>\n{div()}\n"
                    f"<code>{bar}</code> <b>100%</b>\n\n"
                    f"✅ <b>{fancy('complete')}</b>\n<i>⏱ {fancy(f'took {elapsed:.1f}s')}</i>")
            try: bot.edit_message_text(text, self.cid, self.mid, parse_mode="HTML")
            except: pass
        time.sleep(delay)
    def edit(self, text, mark=None):
        with self._lock:
            if self._dead:
                try: bot.send_message(self.cid, text, parse_mode="HTML", reply_markup=mark)
                except Exception as e: logger.error(f"AnimMsg send: {e}")
                return
            try: bot.edit_message_text(text, self.cid, self.mid, parse_mode="HTML", reply_markup=mark)
            except Exception as e:
                logger.warning(f"AnimMsg edit: {e}")
                try: bot.send_message(self.cid, text, parse_mode="HTML", reply_markup=mark)
                except Exception as e2: logger.error(f"AnimMsg fallback: {e2}")
    def delete(self):
        try: bot.delete_message(self.cid, self.mid)
        except: pass

def err_frame(title, message):
    return (f"<b>❌ {fancy(title)}</b>\n{div()}\n"
            f"<code>{'░'*18}</code> <b>0%</b>\n\n{message}")

# =================================================================
#  STAGES
# =================================================================
def stg_number(): return [
    {"label": "Connecting to server",   "emojis": ["📡","🌐","🔌"], "duration": 1.1},
    {"label": "Authenticating API",     "emojis": ["🔐","🔑","✔️"], "duration": 1.0},
    {"label": "Searching database",     "emojis": ["🔎","🔍","🧠"], "duration": 2.0},
    {"label": "Fetching records",       "emojis": ["📥","📦","📂"], "duration": 1.5},
    {"label": "Parsing data",           "emojis": ["🧩","🔧","⚙️"], "duration": 1.0}]
def stg_aadhaar(): return [
    {"label": "Connecting Aadhaar API", "emojis": ["🛰️","📡","🌐"], "duration": 1.2},
    {"label": "Verifying identity",     "emojis": ["🔐","🔒","🛡️"], "duration": 1.5},
    {"label": "Fetching records",       "emojis": ["📥","📦","📊"], "duration": 2.0},
    {"label": "Assembling dossier",     "emojis": ["🧩","📋","✅"], "duration": 1.2}]
def stg_vehicle(): return [
    {"label": "Connecting RTO server",  "emojis": ["🛰️","📡","🌐"], "duration": 1.2},
    {"label": "Searching RC database",  "emojis": ["🔎","🔍","📂"], "duration": 1.8},
    {"label": "Fetching vehicle info",  "emojis": ["📥","📦","📊"], "duration": 1.5},
    {"label": "Assembling records",     "emojis": ["🧩","📋","✅"], "duration": 1.0}]
def stg_tg(): return [
    {"label": "Resolving username",     "emojis": ["🔍","🔎","🧭"], "duration": 1.4},
    {"label": "Querying MTProto",       "emojis": ["🛰️","📡","🌐"], "duration": 1.4},
    {"label": "Fetching profile",       "emojis": ["👤","📋","📊"], "duration": 1.4},
    {"label": "Calling TG2Num API",     "emojis": ["🔌","⚡","✅"], "duration": 1.4}]
def stg_create(): return [
    {"label": "Contacting gateway",     "emojis": ["⚡","🌐","📡"], "duration": 1.2},
    {"label": "Generating order",       "emojis": ["🔐","🎫","💳"], "duration": 1.5},
    {"label": "Rendering QR",           "emojis": ["🎨","🖼️","📸"], "duration": 1.0}]
def stg_verify(): return [
    {"label": "Pinging gateway",        "emojis": ["📡","🔌","🌐"], "duration": 1.0},
    {"label": "Reading bank records",   "emojis": ["📧","📬","💌"], "duration": 1.8},
    {"label": "Confirming UTR",         "emojis": ["🏦","🔐","✔️"], "duration": 1.5}]

# =================================================================
#  NO-DATA / LOW-CREDIT
# =================================================================
def no_data_msg(uid, svc="number"):
    if svc == "number": line = "ᴛʜɪꜱ ɴᴜᴍʙᴇʀ ɪꜱ ɴᴏᴛ ɪɴ ᴏᴜʀ ᴅᴀᴛᴀꜱᴇᴛꜱ."
    elif svc == "aadhaar": line = "ᴛʜɪꜱ ᴀᴀᴅʜᴀᴀʀ ɪꜱ ɴᴏᴛ ɪɴ ᴏᴜʀ ᴅᴀᴛᴀꜱᴇᴛꜱ."
    elif svc == "vehicle": line = "ᴛʜɪꜱ ᴠᴇʜɪᴄʟᴇ ɪꜱ ɴᴏᴛ ɪɴ ᴏᴜʀ ᴅᴀᴛᴀꜱᴇᴛꜱ."
    else: line = "ᴛʜɪꜱ ᴜꜱᴇʀ ɪꜱ ɴᴏᴛ ɪɴ ᴏᴜʀ ᴅᴀᴛᴀꜱᴇᴛꜱ."
    return (f"😔 <b>{fancy('no data found')}</b>\n\n"
            f"{line}\nᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɴᴏᴛʜᴇʀ {svc}.\n\n"
            f"{div_soft()}\n💎 ᴄʀᴇᴅɪᴛꜱ <b>{fancy('not deducted')}</b>\n"
            f"🎯 {fancy('tries remaining')}: <b>{tries_display(uid)}</b>")

def no_tries_msg(uid):
    return (f"⏳ <b>{fancy('daily limit reached')}</b>\n\n"
            f"ᴀᴀᴊ ᴋᴀ ʟɪᴍɪᴛ ᴋʜᴀᴛᴀᴍ.\nᴋᴀʟ ᴅᴏʙᴀʀᴀ ᴛʀʏ ᴋᴀʀᴇɪɴ.\n\n"
            f"{div_soft()}\n🎯 ᴛʀɪᴇꜱ: <b>0</b>")

def low_credit_text(uid, need, have):
    return (f"⚠️ <b>{fancy('not enough credits')}</b>\n\n"
            f"ɴᴇᴇᴅᴇᴅ: <b>{need} ᴄʀ</b>\nʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ: <b>{have} ᴄʀ</b>\n\n"
            f"{div_soft()}\n🎯 ᴛʀɪᴇꜱ: <b>{tries_display(uid)}</b>\n\n"
            f"📌 ʀᴇꜰᴇʀ ꜰʀɪᴇɴᴅ ᴏʀ ʙᴜʏ ᴄʀᴇᴅɪᴛꜱ:")

def low_credit_kb(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("🎁 ʀᴇꜰᴇʀ & ᴇᴀʀɴ", callback_data=f"copyref_{uid}"),
           InlineKeyboardButton("💳 ʙᴜʏ ᴄʀᴇᴅɪᴛꜱ", callback_data="buy"))
    return kb

# =================================================================
#  INPUT HELPERS
# =================================================================
def extract_phone_digits(text):
    if not text: return None
    d = re.sub(r'\D', '', str(text))
    if not d: return None
    if d.startswith("00"): d = d[2:]
    if len(d) == 12 and d.startswith("91") and d[2] in "6789": return d[2:]
    if len(d) == 11 and d.startswith("0") and d[1] in "6789": return d[1:]
    if len(d) == 13 and d.startswith("091") and d[3] in "6789": return d[3:]
    if len(d) == 10 and d[0] in "6789": return d
    return None

def is_vehicle_number(text):
    if not text: return False
    v = re.sub(r'[\s\-]', '', str(text)).upper()
    return bool(re.match(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$', v))

def classify_input(text):
    if not text: return None, None
    t = text.strip()
    if not t: return None, None
    if "t.me/" in t or "telegram.me/" in t:
        part = t.split("t.me/")[-1] if "t.me/" in t else t.split("telegram.me/")[-1]
        part = part.split("?")[0].strip("/")
        if "/" in part: part = part.split("/")[0]
        if not part: return None, None
        if part.startswith("+") or part.startswith("joinchat"): return None, None
        if part.isdigit(): return "tgid", part
        return "username", part
    if t.startswith("@"):
        u = t[1:].strip()
        if 5 <= len(u) <= 32 and re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', u):
            return "username", u
        return None, None
    if t.isdigit():
        phone = extract_phone_digits(t)
        if phone: return "number", phone
        if len(t) == 12: return "aadhaar", t
        if 5 <= len(t) <= 15: return "tgid", t
        return None, None
    if t.startswith("+"):
        phone = extract_phone_digits(t)
        if phone: return "number", phone
        d = re.sub(r'\D', '', t)
        if 5 <= len(d) <= 15: return "tgid", d
        return None, None
    if is_vehicle_number(t): return "vehicle", re.sub(r'[\s\-]', '', t).upper()
    if re.match(r'^[\+\d\s\-\(\)]+$', t):
        phone = extract_phone_digits(t)
        if phone: return "number", phone
        d = re.sub(r'\D', '', t)
        if 5 <= len(d) <= 15: return "tgid", d
        return None, None
    if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', t): return "username", t
    return None, None

def is_maintenance(): return int(get_setting("maintenance_mode", 0)) == 1
def referral_enabled(): return int(get_setting("referral_enabled", 1)) == 1
def group_enabled(): return int(get_setting("group_enabled", 1)) == 1
def group_auto_delete(): return int(get_setting("group_auto_delete", 1)) == 1
def group_auto_delete_seconds():
    try: return int(get_setting("group_auto_delete_seconds", GROUP_AUTO_DELETE_SECONDS))
    except: return GROUP_AUTO_DELETE_SECONDS

def normalize_phone(num, cc=None):
    if not num: return None
    n = re.sub(r'\D', '', str(num))
    cc_d = re.sub(r'\D', '', str(cc or ""))
    if n.startswith("00"): n = n[2:]
    if cc_d:
        if n.startswith(cc_d) and len(n) > len(cc_d): return n
        return f"{cc_d}{n}"
    if len(n) == 10 and n[0] in "6789": return f"91{n}"
    return n

# =================================================================
#  JSON OUTPUT
# =================================================================
_FIELD_ALIASES = {
    "name": ("name","full_name","fullname","customer_name","user_name"),
    "father": ("father","father_name","fathername","fname","guardian","fathers_name"),
    "address": ("address","addr","full_address","add","permanent_address"),
    "aadhaar": ("aadhaar","aadhar","aadhaar_number","aadhar_no","uid","aadhaar_no"),
    "alt": ("alt","alternate","alt_number","alt_mobile","alternate_number","alt_no"),
    "circle": ("circle","operator","operator_circle","network","telecom"),
    "num": ("num","number","phone","mobile","mobile_number","phone_number","primary_number"),
    "email": ("email","mail","email_id"),
    "dob": ("dob","date_of_birth","birthdate","birthday"),
    "gender": ("gender","sex"),
    "pincode": ("pincode","pin","zip","zipcode","postal_code"),
    "state": ("state","state_name"),
    "district": ("district","dist"),
    "village": ("village","city","town","tehsil"),
    "tg_id": ("tg_id","telegram_id","user_id"),
    "country": ("country","nation"),
    "country_code": ("country_code","cc","code"),
    "vehicle_number": ("vehicle_number","reg_no","registration_number","vehicle","v_number"),
    "owner_name": ("owner_name","owner","owner_full_name"),
    "chassis": ("chassis","chassis_no","chassis_number"),
    "engine": ("engine","engine_no","engine_number"),
    "fuel": ("fuel","fuel_type"),
    "vehicle_class": ("vehicle_class","class","v_class"),
    "maker": ("maker","manufacturer","make"),
    "model": ("model","vehicle_model"),
    "reg_date": ("reg_date","registration_date","reg_dt"),
    "insurance": ("insurance","insurance_company","insurer","insurance_upto"),
    "fitness": ("fitness","fitness_upto","fit_upto"),
    "puc": ("puc","puc_upto","puc_no","puc_number"),
    "rto": ("rto","rto_code","rto_name"),
    "financer": ("financer","finance","bank"),
    "mobile": ("mobile","phone","contact","mobile_number"),
}

def _get_field(rec, key):
    if not isinstance(rec, dict): return None
    aliases = _FIELD_ALIASES.get(key, (key,))
    low = {k.lower(): v for k, v in rec.items() if isinstance(k, str)}
    for a in aliases:
        v = low.get(a.lower())
        if v not in (None, "", "null", "None"): return v
    return None

def _clean_val(v):
    if v is None: return ""
    s = str(v).strip()
    if s in ("", "null", "None", "nan", "N/A", "n/a", "-"): return ""
    return s

def _extract_number_records(data):
    if not isinstance(data, dict):
        if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
        return []
    if "result" in data:
        res = data["result"]
        if isinstance(res, list): return [x for x in res if isinstance(x, dict)]
        if isinstance(res, dict): return [res]
        return []
    for key in ("data", "results", "records", "info", "list"):
        if key in data:
            res = data[key]
            if isinstance(res, list): return [x for x in res if isinstance(x, dict)]
            if isinstance(res, dict): return [res]
            return []
    return [data]

def record_to_json_dict(rec):
    if not isinstance(rec, dict): return {}
    out = {}
    mapping = [
        ("name", "name"), ("father", "father_name"), ("address", "address"),
        ("village", "village"), ("district", "district"), ("state", "state"),
        ("pincode", "pincode"), ("aadhaar", "aadhaar"), ("dob", "dob"),
        ("gender", "gender"), ("alt", "alternate_number"), ("circle", "circle"),
        ("email", "email"), ("num", "number"), ("tg_id", "tg_id"),
        ("country", "country"), ("country_code", "country_code"),
        ("vehicle_number", "vehicle_number"), ("owner_name", "owner_name"),
        ("chassis", "chassis_number"), ("engine", "engine_number"),
        ("fuel", "fuel_type"), ("vehicle_class", "vehicle_class"),
        ("maker", "maker"), ("model", "model"), ("reg_date", "registration_date"),
        ("insurance", "insurance"), ("fitness", "fitness_upto"),
        ("puc", "puc_upto"), ("rto", "rto"), ("financer", "financer"),
    ]
    for key, json_key in mapping:
        v = _clean_val(_get_field(rec, key))
        if v and json_key not in out:
            out[json_key] = v
    low = {k.lower(): v for k, v in rec.items() if isinstance(k, str)}
    covered = set()
    for key, _ in mapping:
        for a in _FIELD_ALIASES.get(key, (key,)): covered.add(a.lower())
    for k, v in low.items():
        if k in covered: continue
        cv = _clean_val(v)
        if cv and k not in out: out[k] = cv
    return out

def build_json_text(records, query_info=None):
    if not records: return None
    results = []
    for rec in records:
        jd = record_to_json_dict(rec)
        if jd: results.append(jd)
    if not results: return None
    payload = {"summary": f"{len(results)} record(s) found"}
    if query_info: payload["query"] = query_info
    payload["results"] = results
    return json.dumps(payload, indent=2, ensure_ascii=False)

# =================================================================
#  USER KEYBOARDS
# =================================================================
def main_kb(uid):
    ia = is_admin_user(uid)
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("📞 Number To Info"), KeyboardButton("🔒 Username To Info"))
    kb.row(KeyboardButton("🆔 Aadhaar To Info"), KeyboardButton("🚗 Vehicle Info"))
    kb.row(KeyboardButton("🛒 Buy Credits"), KeyboardButton("💰 Refer & Earn"))
    kb.row(KeyboardButton("🎟 Redeem Code"), KeyboardButton("👤 My Profile"))
    kb.row(KeyboardButton("➕ Add Me To Group"), KeyboardButton("❓ Help"))
    kb.row(KeyboardButton("ℹ️ About"))
    if ia: kb.row(KeyboardButton("👑 ADMIN PANEL"))
    return kb

# =================================================================
#  ADMIN KEYBOARDS
# =================================================================
def admin_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("📊 Dashboard"), KeyboardButton("👥 Users"))
    kb.row(KeyboardButton("💳 Payments"), KeyboardButton("🔧 Services"))
    kb.row(KeyboardButton("🎟 Promos"), KeyboardButton("📢 Broadcast"))
    kb.row(KeyboardButton("📢 Force Join"), KeyboardButton("👥 Groups"))
    kb.row(KeyboardButton("⚙️ Settings"), KeyboardButton("🛡️ Security"))
    kb.row(KeyboardButton("📈 Analytics"), KeyboardButton("💾 Backup"))
    kb.row(KeyboardButton("🚀 Bot Info"), KeyboardButton("📝 Logs"))
    kb.row(KeyboardButton("📮 Feedback"), KeyboardButton("🔙 Back to Menu"))
    return kb

def dashboard_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("🔄 Refresh", callback_data="adm_dash_refresh"),
           InlineKeyboardButton("📥 Export", callback_data="adm_dash_export"))
    kb.row(InlineKeyboardButton("📊 Detailed Stats", callback_data="adm_dash_detailed"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def users_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("🔍 Search User", callback_data="adm_user_search"),
           InlineKeyboardButton("🚫 Ban User", callback_data="adm_user_ban"))
    kb.row(InlineKeyboardButton("✅ Unban User", callback_data="adm_user_unban"),
           InlineKeyboardButton("📋 Banned List", callback_data="adm_user_banned_list"))
    kb.row(InlineKeyboardButton("💎 Add Credits", callback_data="adm_user_addcr"),
           InlineKeyboardButton("➖ Remove Credits", callback_data="adm_user_remcr"))
    kb.row(InlineKeyboardButton("💰 Set Balance", callback_data="adm_user_setcr"),
           InlineKeyboardButton("📊 User Full Info", callback_data="adm_user_fullinfo"))
    kb.row(InlineKeyboardButton("📊 Top Searches", callback_data="adm_user_top_searches"),
           InlineKeyboardButton("🎁 Top Referrers", callback_data="adm_user_top_refs"))
    kb.row(InlineKeyboardButton("🔥 Active 24h", callback_data="adm_user_active"),
           InlineKeyboardButton("💎 Top Rich", callback_data="adm_user_rich"))
    kb.row(InlineKeyboardButton("📥 Export CSV", callback_data="adm_user_export"),
           InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def payments_kb():
    p, a, r, rev = pay_stats()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton(f"⏳ Pending ({p})", callback_data="adm_pay_pending"))
    kb.row(InlineKeyboardButton(f"✅ Approved ({a})", callback_data="adm_pay_approved"))
    kb.row(InlineKeyboardButton(f"❌ Rejected ({r})", callback_data="adm_pay_rejected"))
    kb.row(InlineKeyboardButton(f"💰 Revenue: ₹{rev} (24h: ₹{revenue_24h()})", callback_data="adm_pay_revenue"))
    kb.row(InlineKeyboardButton("💎 Manual Credit", callback_data="adm_pay_manual"))
    kb.row(InlineKeyboardButton("🧾 Recent Payments", callback_data="adm_pay_recent"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def services_kb():
    sc = get_setting("search_cost", 5); ac = get_setting("aadhaar_cost", 10)
    tc = get_setting("tg2num_cost", 5); vc = get_setting("vehicle_cost", 10)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton(f"📞 Number Cost: {sc}cr", callback_data="adm_svc_numcost"))
    kb.row(InlineKeyboardButton(f"🔒 Username Cost: {tc}cr", callback_data="adm_svc_tgcost"))
    kb.row(InlineKeyboardButton(f"🆔 Aadhaar Cost: {ac}cr", callback_data="adm_svc_aadhaarcost"))
    kb.row(InlineKeyboardButton(f"🚗 Vehicle Cost: {vc}cr", callback_data="adm_svc_vehiclecost"))
    kb.row(InlineKeyboardButton("🔗 API Endpoints", callback_data="adm_svc_endpoints"))
    kb.row(InlineKeyboardButton("🧪 Test APIs (Live)", callback_data="adm_svc_test"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def services_endpoints_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📞 Number API URL", callback_data="adm_ep_numurl"))
    kb.row(InlineKeyboardButton("📞 Number API Key", callback_data="adm_ep_numkey"))
    kb.row(InlineKeyboardButton("🔒 TG2Num URL", callback_data="adm_ep_tgurl"))
    kb.row(InlineKeyboardButton("🔒 TG2Num Key", callback_data="adm_ep_tgkey"))
    kb.row(InlineKeyboardButton("🆔 Aadhaar URL", callback_data="adm_ep_aadhaarurl"))
    kb.row(InlineKeyboardButton("🆔 Aadhaar Key", callback_data="adm_ep_aadhaarkey"))
    kb.row(InlineKeyboardButton("🚗 Vehicle URL", callback_data="adm_ep_vehicleurl"))
    kb.row(InlineKeyboardButton("🚗 Vehicle Key", callback_data="adm_ep_vehiclekey"))
    kb.row(InlineKeyboardButton("🔄 View All Current", callback_data="adm_ep_viewall"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_svc_back"))
    return kb

def promos_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📦 Generate Promo", callback_data="adm_promo_gen"))
    kb.row(InlineKeyboardButton("📋 List Promos", callback_data="adm_promo_list"))
    kb.row(InlineKeyboardButton("📊 Promo Stats", callback_data="adm_promo_stats"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def broadcast_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📝 Text Broadcast", callback_data="adm_bc_text"))
    kb.row(InlineKeyboardButton("📸 Photo Broadcast", callback_data="adm_bc_photo"))
    kb.row(InlineKeyboardButton("🎬 Video Broadcast", callback_data="adm_bc_video"))
    kb.row(InlineKeyboardButton("📢 Broadcast to Groups", callback_data="adm_bc_groups"))
    kb.row(InlineKeyboardButton("⚙️ Broadcast Settings", callback_data="adm_bc_settings"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def broadcast_settings_kb():
    pin = "🟢 ON" if int(get_setting("broadcast_pin", 0)) else "🔴 OFF"
    fwd = "🟢 ON" if int(get_setting("broadcast_forward", 0)) else "🔴 OFF"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton(f"📌 Pin Broadcast: {pin}", callback_data="adm_bc_tog_pin"))
    kb.row(InlineKeyboardButton(f"↗️ Forward Tag: {fwd}", callback_data="adm_bc_tog_fwd"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_bc_back"))
    return kb

def force_kb():
    en = manager.global_enabled if manager else False
    st = "✅ ON" if en else "❌ OFF"
    active = len(manager.active) if manager else 0
    inactive = len(manager.inactive) if manager else 0
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton(f"🔄 Toggle ({st})", callback_data="fj_toggle"))
    kb.row(InlineKeyboardButton("➕ Add Channel", callback_data="fj_add"),
           InlineKeyboardButton("➖ Remove Channel", callback_data="fj_remove"))
    kb.row(InlineKeyboardButton(f"📋 List ({active}✅/{inactive}⚠️)", callback_data="fj_list"),
           InlineKeyboardButton("📊 FJ Stats", callback_data="fj_stats"))
    kb.row(InlineKeyboardButton("🔄 Recheck Channels", callback_data="fj_recheck"))
    kb.row(InlineKeyboardButton("✏️ Custom Message", callback_data="fj_set_msg"))
    kb.row(InlineKeyboardButton("🔄 Reset User Verify", callback_data="fj_reset_user"))
    kb.row(InlineKeyboardButton("🧪 Test Prompt", callback_data="fj_test"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def groups_kb():
    enabled = "🟢 ON" if group_enabled() else "🔴 OFF"
    auto_del = "🟢 ON" if group_auto_delete() else "🔴 OFF"
    secs = group_auto_delete_seconds()
    mins = secs // 60
    time_str = f"{mins}m" if mins < 60 else f"{mins//60}h"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton(f"🔀 Group Mode: {enabled}", callback_data="adm_grp_toggle"))
    kb.row(InlineKeyboardButton(f"🗑 Auto Delete ({time_str}): {auto_del}", callback_data="adm_grp_tog_autodel"))
    kb.row(InlineKeyboardButton("⏱ Set Delete Time", callback_data="adm_grp_set_deltime"))
    kb.row(InlineKeyboardButton("📋 List Groups", callback_data="adm_grp_list"))
    kb.row(InlineKeyboardButton("📢 Broadcast to Groups", callback_data="adm_grp_bc"))
    kb.row(InlineKeyboardButton("📝 Group Welcome Msg", callback_data="adm_grp_welcome"))
    kb.row(InlineKeyboardButton("🗑 Leave All Groups", callback_data="adm_grp_leave_all"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def settings_main_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("💎 Economics", callback_data="ads_eco"))
    kb.row(InlineKeyboardButton("🔍 Service Costs", callback_data="ads_costs"))
    kb.row(InlineKeyboardButton("🎯 Tries & Limits", callback_data="ads_tries"))
    kb.row(InlineKeyboardButton("💳 Payment", callback_data="ads_pay"))
    kb.row(InlineKeyboardButton("⚙️ System", callback_data="ads_sys"))
    kb.row(InlineKeyboardButton("🎨 Customization", callback_data="ads_custom"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def admin_economics_kb():
    wb = get_setting("welcome_bonus", WELCOME_BONUS)
    rb = get_setting("referral_bonus", REFERRAL_BONUS)
    rate = get_setting("credits_per_rupee", 1)
    ref = "🟢 ON" if referral_enabled() else "🔴 OFF"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"💎 Welcome Bonus: {wb}cr", callback_data="ads_set_welcome"))
    kb.add(InlineKeyboardButton(f"🎁 Referral Bonus: {rb}cr", callback_data="ads_set_refbonus"))
    kb.add(InlineKeyboardButton(f"💱 Rate: ₹1 = {rate}cr", callback_data="ads_set_rate"))
    kb.add(InlineKeyboardButton(f"🔀 Referral System: {ref}", callback_data="ads_tog_ref"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="ads_back"))
    return kb

def admin_costs_kb():
    sc = get_setting("search_cost", 5); ac = get_setting("aadhaar_cost", 10)
    tc = get_setting("tg2num_cost", 5); vc = get_setting("vehicle_cost", 10)
    mn = get_setting("min_payment", MIN_PAYMENT); mx = get_setting("max_payment", MAX_PAYMENT)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"📞 Number: {sc}cr", callback_data="ads_set_scost"))
    kb.add(InlineKeyboardButton(f"🆔 Aadhaar: {ac}cr", callback_data="ads_set_acost"))
    kb.add(InlineKeyboardButton(f"🔒 Username: {tc}cr", callback_data="ads_set_tcost"))
    kb.add(InlineKeyboardButton(f"🚗 Vehicle: {vc}cr", callback_data="ads_set_vcost"))
    kb.add(InlineKeyboardButton(f"💵 Min Pay: ₹{mn}", callback_data="ads_set_minpay"))
    kb.add(InlineKeyboardButton(f"💵 Max Pay: ₹{mx}", callback_data="ads_set_maxpay"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="ads_back"))
    return kb

def admin_tries_kb():
    dt = get_setting("daily_tries", DAILY_TRIES)
    dt_str = f"{dt}" if dt > 0 else "∞ Unlimited"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"🎯 Daily Tries: {dt_str}", callback_data="ads_set_tries"))
    kb.add(InlineKeyboardButton("♾️ Set Unlimited (0)", callback_data="ads_tries_unlimited"))
    kb.add(InlineKeyboardButton("🔄 Reset ALL Users Tries", callback_data="ads_tries_reset_all"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="ads_back"))
    return kb

def admin_pay_kb():
    gw = int(get_setting("gateway_enabled", 0))
    mon = int(get_setting("upi_manual_enabled", 1))
    upi = get_setting("upi_manual_id", "not set") or "not set"
    avail = is_auto_upi_available()
    gws = "🟢 ON" if avail else ("⚠️ Setup" if gw else "🔴 OFF")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"🔌 Gateway: {gws}", callback_data="ads_tog_gw"))
    kb.add(InlineKeyboardButton("🔑 Gateway API Key", callback_data="ads_set_gwkey"))
    kb.add(InlineKeyboardButton("🔗 Create URL", callback_data="ads_set_gwcreate"))
    kb.add(InlineKeyboardButton("🔗 Status URL", callback_data="ads_set_gwstatus"))
    kb.add(InlineKeyboardButton("🌐 Redirect URL", callback_data="ads_set_gwredirect"))
    kb.add(InlineKeyboardButton(f"{'🟢' if mon else '🔴'} UPI: {str(upi)[:20]}", callback_data="ads_set_upiid"))
    kb.add(InlineKeyboardButton("🖼 QR URL", callback_data="ads_set_upiqr"))
    kb.add(InlineKeyboardButton(f"{'🔴 OFF' if mon else '🟢 ON'} Manual", callback_data="ads_tog_manual"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="ads_back"))
    return kb

def admin_sys_kb():
    mm = "🟢 ON" if is_maintenance() else "🔴 OFF"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"🔧 Maintenance: {mm}", callback_data="ads_tog_mm"))
    kb.add(InlineKeyboardButton("📤 Export Users CSV", callback_data="ads_export"))
    kb.add(InlineKeyboardButton("🛰️ Pyrogram Health", callback_data="ads_pyro"))
    kb.add(InlineKeyboardButton("💾 Mongo Health", callback_data="ads_mongo"))
    kb.add(InlineKeyboardButton("🔄 Restart Pyrogram", callback_data="ads_pyro_restart"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="ads_back"))
    return kb

def admin_custom_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🛡️ Powered By Text", callback_data="ads_set_powered"))
    kb.add(InlineKeyboardButton("💬 Welcome Emoji", callback_data="ads_set_welcome_emoji"))
    kb.add(InlineKeyboardButton("📢 About Text", callback_data="ads_set_about"))
    kb.add(InlineKeyboardButton("📞 Support Link", callback_data="ads_set_support"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="ads_back"))
    return kb

def security_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("🚫 Banned Users", callback_data="adm_sec_banned"))
    kb.row(InlineKeyboardButton("⚠️ Maintenance Mode", callback_data="adm_sec_maint"))
    kb.row(InlineKeyboardButton("👑 Sub-Admins", callback_data="adm_sec_subadmins"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def subadmins_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("➕ Add Sub-Admin", callback_data="adm_sub_add"))
    kb.row(InlineKeyboardButton("➖ Remove Sub-Admin", callback_data="adm_sub_remove"))
    kb.row(InlineKeyboardButton("📋 List Sub-Admins", callback_data="adm_sub_list"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_sec_back"))
    return kb

def analytics_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📊 User Growth (7d)", callback_data="adm_an_growth"))
    kb.row(InlineKeyboardButton("🔍 Search Trends", callback_data="adm_an_searches"))
    kb.row(InlineKeyboardButton("💰 Revenue Chart", callback_data="adm_an_revenue"))
    kb.row(InlineKeyboardButton("🏆 Top Users", callback_data="adm_an_top"))
    kb.row(InlineKeyboardButton("🚗 Vehicle Searches", callback_data="adm_an_vehicle"))
    kb.row(InlineKeyboardButton("🆔 Aadhaar Searches", callback_data="adm_an_aadhaar"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def backup_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📤 Export Users CSV", callback_data="adm_bk_users"))
    kb.row(InlineKeyboardButton("📤 Export Payments CSV", callback_data="adm_bk_payments"))
    kb.row(InlineKeyboardButton("💾 Full JSON Backup", callback_data="adm_bk_full"))
    kb.row(InlineKeyboardButton("📮 Export Feedback", callback_data="adm_bk_feedback"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def botinfo_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("🔄 Refresh", callback_data="adm_info_refresh"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

def feedback_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📖 View Feedback", callback_data="adm_fb_view"))
    kb.row(InlineKeyboardButton("🗑 Clear All Feedback", callback_data="adm_fb_clear"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="adm_back"))
    return kb

# =================================================================
#  BUY / WELCOME
# =================================================================
def buy_kb():
    rate = get_setting("credits_per_rupee", 1)
    try: rate = int(rate)
    except: rate = 1
    if rate <= 0: rate = 1
    sc = get_setting("search_cost", 5); tc = get_setting("tg2num_cost", 5)
    ac = get_setting("aadhaar_cost", 10); vc = get_setting("vehicle_cost", 10)
    text = (f"🛒 <b>{fancy('buy credits')}</b>\n\n"
            f"💱 ʀᴀᴛᴇ: <b>₹1 = {rate} ᴄʀ</b>\n\n"
            f"📞 ɴᴜᴍʙᴇʀ: {sc}ᴄʀ\n🔒 ᴜꜱᴇʀɴᴀᴍᴇ: {tc}ᴄʀ\n"
            f"🆔 ᴀᴀᴅʜᴀᴀʀ: {ac}ᴄʀ\n🚗 ᴠᴇʜɪᴄʟᴇ: {vc}ᴄʀ\n\n"
            f"📌 ᴀᴍᴏᴜɴᴛ ꜱᴇʟᴇᴄᴛ ᴋᴀʀᴇɪɴ:")
    kb = InlineKeyboardMarkup(row_width=3)
    kb.row(InlineKeyboardButton("₹10", callback_data="amt_10"),
           InlineKeyboardButton("₹50", callback_data="amt_50"),
           InlineKeyboardButton("₹100", callback_data="amt_100"))
    kb.row(InlineKeyboardButton("₹200", callback_data="amt_200"),
           InlineKeyboardButton("₹500", callback_data="amt_500"),
           InlineKeyboardButton("✏️ Custom", callback_data="amt_custom"))
    kb.row(InlineKeyboardButton("🏠 HOME", callback_data="home"),
           InlineKeyboardButton("❌ CLOSE", callback_data="close"))
    return text, kb

def welcome_txt(uid, uname):
    e = get_setting("welcome_emoji", "") or random.choice(WELCOME_EMOJIS)
    u = get_or_create_user(uid)
    cr = u.get("credits", 0)
    banned = u.get("banned")
    if is_admin_user(uid): cd = "♾️ ᴜɴʟɪᴍɪᴛᴇᴅ"
    elif banned: cd = "🚫 ʙᴀɴɴᴇᴅ"
    else: cd = f"{cr} ᴄʀ"
    wb = get_setting("welcome_bonus", WELCOME_BONUS)
    bonus_line = ""
    if not banned:
        bonus_line = f"🎁 <b>{fancy('welcome bonus')}: {wb} ꜰʀᴇᴇ ᴄʀᴇᴅɪᴛꜱ!</b>\n\n"
    return (f"👋 <b>{fancy('hello')}</b> @{uname}\n"
            f"🆔 <code>{uid}</code>\n"
            f"💎 ᴄʀᴇᴅɪᴛꜱ: {cd}\n"
            f"🎯 ᴛʀɪᴇꜱ: {tries_display(uid)}\n\n"
            f"{bonus_line}"
            f"<b>{fancy('services')}:</b>\n"
            f"📞 ɴᴜᴍʙᴇʀ — {get_setting('search_cost',5)}ᴄʀ\n"
            f"🔒 ᴜꜱᴇʀɴᴀᴍᴇ — {get_setting('tg2num_cost',5)}ᴄʀ\n"
            f"🆔 ᴀᴀᴅʜᴀᴀʀ — {get_setting('aadhaar_cost',10)}ᴄʀ\n"
            f"🚗 ᴠᴇʜɪᴄʟᴇ — {get_setting('vehicle_cost',10)}ᴄʀ\n\n{e}")

# =================================================================
#  FORCE JOIN MANAGER — v31 REAL-TIME
# =================================================================
class FJManager:
    def __init__(self, bot):
        self.bot = bot
        self.pending = {}
        self.msg = {}
        self.channels = []
        self.active = []
        self.inactive = []
        self.global_enabled = False
        self._load()

    def _load(self):
        try:
            bi = self.bot.get_me()
            if not bi:
                raise Exception("get_me returned None")
        except Exception as e:
            logger.error(f"❌ FJ _load: get_me failed: {e}")
            self.channels = []; self.active = []; self.inactive = []
            self.global_enabled = False
            return

        all_chs = []
        active = []
        inactive = []
        for c in all_channels():
            cid = c.get("channel_id")
            link = c.get("channel_link") or ""
            all_chs.append((cid, link))
            try:
                m = self.bot.get_chat_member(cid, bi.id)
                if m.status in ('administrator', 'creator'):
                    active.append((cid, link))
                else:
                    inactive.append((cid, link, f"bot is '{m.status}'"))
                    logger.warning(f"⚠️ FJ: bot is '{m.status}' in {cid}")
            except Exception as e:
                err = str(e)
                inactive.append((cid, link, err[:100]))
                logger.warning(f"⚠️ FJ: cannot check {cid}: {err[:150]}")

        self.channels = all_chs
        self.active = active
        self.inactive = inactive
        self.global_enabled = str(get_setting("force_enabled", "1")) == "1"
        logger.info(f"✅ FJ: {len(all_chs)} total, {len(active)} active, {len(inactive)} inactive, enabled={self.global_enabled}")

    def reload(self): self._load()

    def is_on(self):
        return self.global_enabled and bool(self.channels)

    def _is_private(self, link):
        s = str(link or "")
        return ('+' in s) or ('joinchat' in s)

    def _is_active(self, cid):
        return any(c[0] == cid for c in self.active)

    def check(self, uid, force=False):
        """
        ✅ v31 REAL-TIME:
        - Public channel: get_chat_member call. Not member → missing.
        - Private channel: fj_requested_channels me hai → pass, warna missing.
        - Transient errors (FloodWait/timeout/bot-perm) → SKIP (block nahi).
        - Koi grace period nahi. Har baar real check.
        """
        if not self.is_on(): return None
        if is_admin_user(uid): return None

        u = users_col.find_one({"user_id": uid}, {"fj_requested_channels": 1})
        requested = set(u.get("fj_requested_channels", [])) if u else set()

        missing = []
        for cid, link in self.channels:
            # Bot jis channel me admin nahi hai, usko skip karo
            if not self._is_active(cid):
                continue

            is_priv = self._is_private(link)

            # ---- PRIVATE CHANNEL: sirf join-request check ----
            if is_priv:
                if cid not in requested:
                    missing.append((cid, link))
                    logger.info(f"FJ: U{uid} no request for private C{cid}")
                continue

            # ---- PUBLIC CHANNEL: real membership check ----
            try:
                m = self.bot.get_chat_member(cid, uid)
                status = m.status
                is_member = status in ('member', 'administrator', 'creator')
                if status == 'restricted' and getattr(m, 'is_member', False):
                    is_member = True

                if not is_member:
                    missing.append((cid, link))
                    logger.info(f"FJ: U{uid} NOT in public C{cid} (status={status})")
            except Exception as e:
                err = str(e).lower()
                # ✅ Sirf DEFINITIVE "not member" errors pe block karo
                definitive = (
                    'user not found' in err or
                    'user_not_participant' in err or
                    'participant not found' in err or
                    'participant_id_invalid' in err or
                    'user is not a member' in err or
                    'user was kicked' in err or
                    'chat member not found' in err
                )
                if definitive:
                    missing.append((cid, link))
                    logger.info(f"FJ: U{uid} definitively not in C{cid}: {e}")
                else:
                    # ⚠️ Bot-perm / FloodWait / network → skip (block nahi)
                    logger.warning(f"FJ skip U{uid} C{cid} (transient): {e}")

        return missing if missing else None

    def ensure(self, uid, cid, pending=None):
        try:
            chat = self.bot.get_chat(cid)
            if chat.type != 'private': return True
        except: return True

        if is_admin_user(uid): return True

        missing = self.check(uid)
        if not missing:
            if pending is None: self.pending.pop(uid, None)
            return True

        if pending is not None:
            self.pending[uid] = pending

        # Purana FJ prompt delete
        old = self.msg.pop(uid, None)
        if old:
            try: self.bot.delete_message(cid, old)
            except: pass

        # ✅ SIRF missing channels ke buttons
        kb = InlineKeyboardMarkup(row_width=1)
        seen = set()
        idx = 0
        for cid_, lk in missing:
            if cid_ in seen: continue
            seen.add(cid_)
            idx += 1
            kb.add(InlineKeyboardButton(f"📢 Channel {idx}", url=lk))
        kb.add(InlineKeyboardButton("✅ Verify", callback_data="force_verify"))

        custom_msg = get_setting("fj_custom_msg", "")
        if custom_msg:
            text = custom_msg
        else:
            text = (f"⚠️ <b>{fancy('please join channels')}</b>\n\n"
                    f"ᴊᴏɪɴ ᴋᴀʀᴋᴇ ᴠᴇʀɪꜰʏ ᴅᴀʙᴀᴏ.\n\n"
                    f"<i>Private channel hai to Request bhejo, phir Verify dabao.</i>")

        try:
            s = self.bot.send_message(cid, text, parse_mode='HTML', reply_markup=kb)
            self.msg[uid] = s.message_id
            try:
                settings_col.update_one({"key": "fj_stats_blocks"},
                    {"$inc": {"value": 1}}, upsert=True)
            except: pass
            logger.info(f"FJ prompt sent to {uid} ({len(missing)} missing)")
        except Exception as e:
            logger.error(f"FJ prompt send failed: {e}")
        return False

    def verify_cb(self, call):
        uid = call.from_user.id
        cid = call.message.chat.id

        logger.info(f"FJ verify clicked by {uid}")
        missing = self.check(uid)

        if missing is None:
            mark_fj_verified(uid)
            _process_pending_referral(uid)

            mid = self.msg.pop(uid, None)
            if mid:
                try: self.bot.delete_message(cid, mid)
                except: pass
            p = self.pending.pop(uid, None)
            if p:
                self._exec(uid, cid, p, call)
            else:
                uname = call.from_user.username or "user"
                self.bot.send_message(cid, welcome_txt(uid, uname),
                    parse_mode='HTML', reply_markup=main_kb(uid))
            try:
                settings_col.update_one({"key": "fj_stats_verifies"},
                    {"$inc": {"value": 1}}, upsert=True)
            except: pass
            try:
                bot.send_message(ADMIN_ID,
                    f"✅ <b>FJ Verified</b>\n"
                    f"👤 @{call.from_user.username or 'user'}\n"
                    f"🆔 <code>{uid}</code>",
                    parse_mode='HTML')
            except: pass
            safe_ans(call, "✅ Verified!")
        else:
            old_mid = self.msg.pop(uid, None)
            if old_mid:
                try: self.bot.delete_message(cid, old_mid)
                except: pass
            safe_ans(call, f"❌ {len(missing)} channel(s) pending!", True)
            self.ensure(uid, cid)

    def _exec(self, uid, cid, p, call):
        t, d = p.get('type'), p.get('data')
        if t == 'number_search': process_number(uid, cid, d)
        elif t == 'aadhaar_search': process_aadhaar(uid, cid, d)
        elif t == 'vehicle_search': process_vehicle(uid, cid, d)
        elif t == 'tg2num_search': process_tg2num(uid, cid, d)
        elif t == 'menu_button': process_menu(uid, cid, d)
        elif t == 'promo_redeem': process_promo(uid, cid, d)
        else:
            uname = call.from_user.username or "user"
            self.bot.send_message(cid, welcome_txt(uid, uname),
                parse_mode='HTML', reply_markup=main_kb(uid))

    def toggle(self):
        cur = str(get_setting("force_enabled", "1")) == "1"
        set_setting("force_enabled", "0" if cur else "1")
        self.reload()
        return not cur

    def add(self, cid, link=None):
        if not link: return False, "Invite link required"
        if not link.startswith("http"): return False, "Invalid link (must start with http)"
        try:
            bi = self.bot.get_me()
            m = self.bot.get_chat_member(cid, bi.id)
            if m.status not in ('administrator', 'creator'):
                logger.warning(f"⚠️ Bot is '{m.status}' in {cid} — FJ will be lenient")
        except Exception as e:
            logger.warning(f"⚠️ Cannot verify bot admin: {e}")
        if not add_channel_db(cid, link): return False, "Already exists"
        self.reload()
        return True, "Added ✅"

    def rm(self, cid):
        if remove_channel_db(cid):
            self.reload()
            return True, "Removed"
        return False, "Not found"

    def stats(self):
        try:
            blocks = settings_col.find_one({"key": "fj_stats_blocks"})
            verifies = settings_col.find_one({"key": "fj_stats_verifies"})
            verified_count = users_col.count_documents({"fj_verified": True})
            return {
                "blocks": blocks.get("value", 0) if blocks else 0,
                "verifies": verifies.get("value", 0) if verifies else 0,
                "verified_users": verified_count,
                "total": len(self.channels),
                "active": len(self.active),
                "inactive": len(self.inactive),
            }
        except: return {"blocks": 0, "verifies": 0, "verified_users": 0,
                        "total": 0, "active": 0, "inactive": 0}

# =================================================================
#  PENDING REFERRAL PROCESSING (post-FJ)
# =================================================================
def _process_pending_referral(uid):
    try:
        u = users_col.find_one({"user_id": uid})
        if not u: return
        rid = u.get("pending_referrer")
        if not rid: return
        if u.get("referral_credited"): return
        if not referral_enabled(): return
        res = users_col.find_one_and_update(
            {"user_id": uid, "pending_referrer": rid, "referral_credited": {"$ne": True}},
            {"$set": {"referral_credited": True, "referred_by": rid}},
            return_document=ReturnDocument.AFTER)
        if not res: return
        add_referral_bonus(rid)
        try:
            rb = get_setting("referral_bonus", 10)
            bot.send_message(rid, f"🎉 ɴᴇᴡ ʀᴇꜰᴇʀʀᴀʟ ᴠᴇʀɪꜰɪᴇᴅ!\n+{rb}ᴄʀ")
        except: pass
    except Exception as e:
        logger.error(f"_process_pending_referral: {e}")

manager = None
states = {}

# =================================================================
#  SEND RESULT
# =================================================================
def _split_safe(text, limit=MSG_SAFE_LIMIT):
    if len(text) <= limit: return [text]
    parts = []
    rem = text
    while rem:
        if len(rem) <= limit:
            parts.append(rem); break
        chunk = rem[:limit]
        idx = chunk.rfind('\n\n')
        if idx < limit // 3:
            idx = chunk.rfind('\n')
        if idx < limit // 3:
            idx = limit
        piece = rem[:idx]
        opens = piece.count('<pre>')
        closes = piece.count('</pre>')
        if opens > closes:
            piece = piece + '</pre>'
            rem = '<pre>' + rem[idx:]
        else:
            rem = rem[idx:]
        parts.append(piece)
    return parts

def send_result(uid, cid, txt, reply_to=None, reply_markup=None, is_group_msg=False):
    is_private = (cid == uid or cid > 0)
    if is_private:
        parts = _split_safe(txt, MSG_SAFE_LIMIT)
        sent_any = False
        for i, part in enumerate(parts):
            kw = {'parse_mode': 'HTML', 'disable_web_page_preview': True}
            if i == 0 and reply_to: kw['reply_to_message_id'] = reply_to
            if i == len(parts) - 1 and reply_markup: kw['reply_markup'] = reply_markup
            try:
                bot.send_message(cid, part, **kw); sent_any = True
            except Exception as e:
                logger.error(f"❌ send_result part {i+1}/{len(parts)} failed: {e}")
                try:
                    plain = re.sub(r'<[^>]+>', '', part)
                    plain = html_module.unescape(plain)
                    bot.send_message(cid, plain[:4000]); sent_any = True
                except Exception as e2:
                    logger.error(f"❌ Fallback failed: {e2}")
        if sent_any: logger.info(f"✅ Result sent to {uid} (private)")
        return

    logger.info(f"📢 Group result for U{uid} in group {cid}")
    parts = _split_safe(txt, MSG_SAFE_LIMIT)
    sent_msgs = []
    for i, part in enumerate(parts):
        kw = {'parse_mode': 'HTML', 'disable_web_page_preview': True}
        if i == 0 and reply_to: kw['reply_to_message_id'] = reply_to
        if i == len(parts) - 1 and reply_markup: kw['reply_markup'] = reply_markup
        try:
            m = bot.send_message(cid, part, **kw)
            sent_msgs.append(m.message_id)
        except Exception as e:
            logger.error(f"Group send failed: {e}")
            try:
                plain = re.sub(r'<[^>]+>', '', part)
                plain = html_module.unescape(plain)
                m = bot.send_message(cid, plain[:4000])
                sent_msgs.append(m.message_id)
            except Exception as e2:
                logger.error(f"Group fallback failed: {e2}")

    if sent_msgs and group_auto_delete():
        delay = group_auto_delete_seconds()
        delete_ids = list(sent_msgs)
        def _del():
            time.sleep(delay)
            for mid in delete_ids:
                try: bot.delete_message(cid, mid)
                except: pass
            logger.info(f"🗑 Auto-deleted {len(delete_ids)} bot msgs in group {cid} after {delay}s")
        threading.Thread(target=_del, daemon=True).start()

# =================================================================
#  PROCESS: NUMBER
# =================================================================
def process_number(uid, cid, phone, reply_to=None):
    if is_maintenance() and not is_admin_user(uid):
        bot.send_message(cid, f"🔧 {fancy('maintenance')}", reply_to_message_id=reply_to); return
    if is_banned(uid) and not is_admin_user(uid):
        bot.send_message(cid, f"🚫 {fancy('banned')}", reply_to_message_id=reply_to); return

    clean = extract_phone_digits(phone)
    if not clean:
        bot.send_message(cid,
            f"❌ <b>{fancy('invalid number')}</b>\n\nᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴀ ᴠᴀʟɪᴅ 10-ᴅɪɢɪᴛ ɪɴᴅɪᴀɴ ᴍᴏʙɪʟᴇ ɴᴜᴍʙᴇʀ.\nᴇx: <code>9876543210</code>",
            parse_mode='HTML', reply_to_message_id=reply_to); return
    phone = clean
    cost = int(get_setting("search_cost", 5))
    is_priv = is_admin_user(uid)

    if not is_priv and get_credits(uid) < cost:
        bot.send_message(cid, low_credit_text(uid, cost, get_credits(uid)),
                         parse_mode='HTML', reply_to_message_id=reply_to,
                         reply_markup=low_credit_kb(uid)); return

    if not consume_try(uid):
        bot.send_message(cid, no_tries_msg(uid), parse_mode='HTML',
                         reply_to_message_id=reply_to); return

    send_typing(cid)
    am = AnimMsg(cid, stages=stg_number(), title="NUMBER SEARCH", reply_to=reply_to)
    am.start()
    ok, data, msg = query_number(phone)
    am.stop()
    if not ok:
        logger.warning(f"Number search failed for {phone}: {msg}")
        am.edit(err_frame("NO DATA", no_data_msg(uid, "number"))); return
    records = _extract_number_records(data)
    if not records:
        am.edit(err_frame("NO DATA", no_data_msg(uid, "number"))); return
    if not is_priv:
        if not deduct_credits(uid, cost):
            am.edit(err_frame("ERROR", low_credit_text(uid, cost, get_credits(uid)))); return
        remaining = get_credits(uid)
    else: remaining = "♾️"
    incr_searches(uid)
    am.flash_complete(); am.delete()

    query_info = {"number": phone, "type": "phone"}
    json_text = build_json_text(records, query_info)
    if not json_text:
        send_result(uid, cid, no_data_msg(uid, "number"), reply_to=reply_to); return

    header = f"📞 <b>{fancy('number info')}</b> — <code>{phone}</code>\n\n"
    footer = "\n\n"
    if not is_priv:
        footer += f"{div_soft()}\n💎 ᴄʀᴇᴅɪᴛꜱ ʟᴇꜰᴛ: <b>{remaining}</b>\n"
    footer += build_footer(uid)
    safe_json = html_module.escape(json_text)
    txt = header + f"<pre>{safe_json}</pre>" + footer
    send_result(uid, cid, txt, reply_to=reply_to)

# =================================================================
#  PROCESS: AADHAAR
# =================================================================
def process_aadhaar(uid, cid, aadhaar, reply_to=None):
    if is_maintenance() and not is_admin_user(uid):
        bot.send_message(cid, f"🔧 {fancy('maintenance')}", reply_to_message_id=reply_to); return
    if is_banned(uid) and not is_admin_user(uid):
        bot.send_message(cid, f"🚫 {fancy('banned')}", reply_to_message_id=reply_to); return

    aadhaar = re.sub(r'\D', '', str(aadhaar))
    if len(aadhaar) != 12:
        bot.send_message(cid,
            f"❌ <b>{fancy('invalid aadhaar')}</b>\n\nᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ 12-ᴅɪɢɪᴛ ᴀᴀᴅʜᴀᴀʀ.",
            parse_mode='HTML', reply_to_message_id=reply_to); return

    cost = int(get_setting("aadhaar_cost", 10))
    is_priv = is_admin_user(uid)

    if not is_priv and get_credits(uid) < cost:
        bot.send_message(cid, low_credit_text(uid, cost, get_credits(uid)),
                         parse_mode='HTML', reply_to_message_id=reply_to,
                         reply_markup=low_credit_kb(uid)); return

    if not consume_try(uid):
        bot.send_message(cid, no_tries_msg(uid), parse_mode='HTML',
                         reply_to_message_id=reply_to); return

    send_typing(cid)
    am = AnimMsg(cid, stages=stg_aadhaar(), title="AADHAAR SEARCH", reply_to=reply_to)
    am.start()
    ok, data, msg = query_aadhaar(aadhaar)
    am.stop()
    if not ok:
        logger.warning(f"Aadhaar search failed: {msg}")
        am.edit(err_frame("NO DATA", no_data_msg(uid, "aadhaar"))); return
    records = _extract_number_records(data)
    if not records:
        am.edit(err_frame("NO DATA", no_data_msg(uid, "aadhaar"))); return
    if not is_priv:
        if not deduct_credits(uid, cost):
            am.edit(err_frame("ERROR", low_credit_text(uid, cost, get_credits(uid)))); return
        remaining = get_credits(uid)
    else: remaining = "♾️"
    incr_searches(uid)
    am.flash_complete(); am.delete()

    query_info = {"aadhaar": f"****{aadhaar[-4:]}", "type": "aadhaar"}
    json_text = build_json_text(records, query_info)
    if not json_text:
        send_result(uid, cid, no_data_msg(uid, "aadhaar"), reply_to=reply_to); return

    header = f"🆔 <b>{fancy('aadhaar info')}</b> — <code>****{aadhaar[-4:]}</code>\n\n"
    footer = "\n\n"
    if not is_priv:
        footer += f"{div_soft()}\n💎 ᴄʀᴇᴅɪᴛꜱ ʟᴇꜰᴛ: <b>{remaining}</b>\n"
    footer += build_footer(uid)
    safe_json = html_module.escape(json_text)
    txt = header + f"<pre>{safe_json}</pre>" + footer
    send_result(uid, cid, txt, reply_to=reply_to)

# =================================================================
#  PROCESS: VEHICLE
# =================================================================
def process_vehicle(uid, cid, vehicle, reply_to=None):
    if is_maintenance() and not is_admin_user(uid):
        bot.send_message(cid, f"🔧 {fancy('maintenance')}", reply_to_message_id=reply_to); return
    if is_banned(uid) and not is_admin_user(uid):
        bot.send_message(cid, f"🚫 {fancy('banned')}", reply_to_message_id=reply_to); return

    v = re.sub(r'[\s\-]', '', str(vehicle)).upper()
    if not re.match(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$', v):
        bot.send_message(cid,
            f"❌ <b>{fancy('invalid vehicle number')}</b>\n\n"
            f"ᴇx: <code>JH15U4500</code>\nᴇx: <code>DL01AB1234</code>\nᴇx: <code>MH12DE1234</code>",
            parse_mode='HTML', reply_to_message_id=reply_to); return
    vehicle = v

    cost = int(get_setting("vehicle_cost", 10))
    is_priv = is_admin_user(uid)

    if not is_priv and get_credits(uid) < cost:
        bot.send_message(cid, low_credit_text(uid, cost, get_credits(uid)),
                         parse_mode='HTML', reply_to_message_id=reply_to,
                         reply_markup=low_credit_kb(uid)); return

    if not consume_try(uid):
        bot.send_message(cid, no_tries_msg(uid), parse_mode='HTML',
                         reply_to_message_id=reply_to); return

    send_typing(cid)
    am = AnimMsg(cid, stages=stg_vehicle(), title="VEHICLE SEARCH", reply_to=reply_to)
    am.start()
    ok, data, msg = query_vehicle(vehicle)
    am.stop()
    if not ok:
        logger.warning(f"Vehicle search failed: {msg}")
        am.edit(err_frame("NO DATA", no_data_msg(uid, "vehicle"))); return
    records = _extract_number_records(data)
    if not records:
        am.edit(err_frame("NO DATA", no_data_msg(uid, "vehicle"))); return
    if not is_priv:
        if not deduct_credits(uid, cost):
            am.edit(err_frame("ERROR", low_credit_text(uid, cost, get_credits(uid)))); return
        remaining = get_credits(uid)
    else: remaining = "♾️"
    incr_searches(uid)
    am.flash_complete(); am.delete()

    query_info = {"vehicle": vehicle, "type": "vehicle"}
    json_text = build_json_text(records, query_info)
    if not json_text:
        send_result(uid, cid, no_data_msg(uid, "vehicle"), reply_to=reply_to); return

    header = f"🚗 <b>{fancy('vehicle info')}</b> — <code>{vehicle}</code>\n\n"
    footer = "\n\n"
    if not is_priv:
        footer += f"{div_soft()}\n💎 ᴄʀᴇᴅɪᴛꜱ ʟᴇꜰᴛ: <b>{remaining}</b>\n"
    footer += build_footer(uid)
    safe_json = html_module.escape(json_text)
    txt = header + f"<pre>{safe_json}</pre>" + footer
    send_result(uid, cid, txt, reply_to=reply_to)

# =================================================================
#  PROCESS: USERNAME
# =================================================================
def process_tg2num(uid, cid, query, reply_to=None):
    if is_maintenance() and not is_admin_user(uid):
        bot.send_message(cid, f"🔧 {fancy('maintenance')}", reply_to_message_id=reply_to); return
    if is_banned(uid) and not is_admin_user(uid):
        bot.send_message(cid, f"🚫 {fancy('banned')}", reply_to_message_id=reply_to); return

    cost = int(get_setting("tg2num_cost", 5))
    is_priv = is_admin_user(uid)
    if not is_priv and get_credits(uid) < cost:
        bot.send_message(cid, low_credit_text(uid, cost, get_credits(uid)),
                         parse_mode='HTML', reply_to_message_id=reply_to,
                         reply_markup=low_credit_kb(uid)); return

    if not consume_try(uid):
        bot.send_message(cid, no_tries_msg(uid), parse_mode='HTML',
                         reply_to_message_id=reply_to); return

    send_typing(cid)
    am = AnimMsg(cid, stages=stg_tg(), title="USERNAME SEARCH", reply_to=reply_to)
    am.start()
    resolved, src = resolve_any(query)
    tg_id = None
    if resolved and resolved.get("user_id"):
        tg_id = resolved.get("user_id")
        logger.info(f"✅ Resolved {query} → TG ID {tg_id} via {src}")
    else:
        logger.warning(f"⚠️ Could not resolve {query}")
    if not tg_id and str(query).strip().isdigit():
        tg_id = int(str(query).strip())

    result = None
    if tg_id:
        ok_c, res_c, msg_c = query_tg2num_id(tg_id)
        if ok_c: result = res_c
        else: logger.warning(f"TG2Num API failed: {msg_c}")

    am.stop()
    if not result or not result.get("number"):
        am.edit(err_frame("NO DATA", no_data_msg(uid, "username"))); return

    if not is_priv:
        if not deduct_credits(uid, cost):
            am.edit(err_frame("ERROR", low_credit_text(uid, cost, get_credits(uid)))); return
        remaining = get_credits(uid)
    else: remaining = "♾️"
    incr_searches(uid)
    am.flash_complete(); am.delete()

    api_tg_id = result.get("tg_id") or tg_id
    country = result.get("country"); cc = result.get("country_code"); number = result.get("number")

    json_obj = {"tg_id": str(api_tg_id) if api_tg_id else "", "country": country or "",
                "country_code": cc or "", "number": number or ""}
    query_info = {"query": str(query), "type": "username"}
    tg_payload = {"summary": "1 record(s) found", "query": query_info, "results": [json_obj]}
    json_text = json.dumps(tg_payload, indent=2, ensure_ascii=False)

    lines = [f"🔒 <b>{fancy('username to info')}</b> — <code>{html_module.escape(str(query))}</code>\n",
             f"<pre>{html_module.escape(json_text)}</pre>"]
    if src:
        src_map = {"mtproto": "🛰️ ᴍᴛᴘʀᴏᴛᴏ", "cache": "💾 ᴄᴀᴄʜᴇ", "telegram_api": "🌐 ᴛᴇʟᴇɢʀᴀᴍ ᴀᴘɪ"}
        lines.append(f"\n📡 ꜱᴏᴜʀᴄᴇ: {src_map.get(src, src)}")
    if not is_priv:
        lines.append(f"💎 ᴄʀᴇᴅɪᴛꜱ ʟᴇꜰᴛ: <b>{remaining}</b>")
    lines.append(""); lines.append(build_footer(uid))

    reply_markup = None
    full_number = normalize_phone(number, cc) if number else None
    if full_number:
        wa_msg = random.choice(["Hi", "Hello", "Hey", "Hi!", "Hello 👋", "Hey there"])
        wa_url = f"https://wa.me/{full_number}?text={requests.utils.quote(wa_msg)}"
        reply_markup = InlineKeyboardMarkup(row_width=1)
        reply_markup.row(InlineKeyboardButton("💬 ᴡʜᴀᴛꜱᴀᴘᴘ", url=wa_url))
    send_result(uid, cid, "\n".join(lines), reply_to=reply_to, reply_markup=reply_markup)

# =================================================================
#  MENU PROCESSOR
# =================================================================
def process_menu(uid, cid, text, reply_to=None):
    upd_last_seen(uid)
    is_admin = is_admin_user(uid)
    is_group = cid < 0

    if is_group:
        if text in ("👑 ADMIN PANEL",):
            try:
                bot.send_message(cid, "❌ Admin panel only in private chat.", reply_to_message_id=reply_to)
            except: pass
            return
        if text == "🔙 Back to Menu":
            bot.send_message(cid, "🏠 Menu private mein /start karein.", reply_to_message_id=reply_to); return
        if text in ("📞 Number To Info", "🔒 Username To Info", "🆔 Aadhaar To Info", "🚗 Vehicle Info"):
            states[uid] = {'state': {
                "📞 Number To Info": 'awaiting_number',
                "🔒 Username To Info": 'awaiting_username',
                "🆔 Aadhaar To Info": 'awaiting_aadhaar',
                "🚗 Vehicle Info": 'awaiting_vehicle',
            }.get(text, '')}
            bot.send_message(cid,
                f"📩 <b>{fancy('send your query')}</b>\n\nᴀᴀᴘ ᴅᴀʙᴀʏᴇ <code>{text}</code> — ᴀʙ ᴛʏᴘᴇ ᴋᴀʀᴇɪɴ.",
                parse_mode='HTML', reply_to_message_id=reply_to)
            return
        bot.send_message(cid,
            f"💬 <b>{fancy('private only')}</b>\n\nʏᴇ ꜱᴜᴠɪᴅʜᴀ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ ᴍᴇ ʜᴀɪ.\n➡️ @{BOT_USERNAME.replace('@','')}",
            parse_mode='HTML', reply_to_message_id=reply_to)
        return

    if text == "👑 ADMIN PANEL":
        if not is_admin:
            bot.send_message(cid, "❌ Admin only", reply_to_message_id=reply_to); return
        txt = (f"👑 <b>{fancy('admin panel v31')}</b>\n{div()}\n"
               f"ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴜʟᴛʀᴀ ᴄᴏɴᴛʀᴏʟ ᴄᴇɴᴛᴇʀ")
        bot.send_message(cid, txt, parse_mode='HTML',
            reply_markup=admin_kb(), reply_to_message_id=reply_to); return

    if text == "🔙 Back to Menu":
        bot.send_message(cid, f"🔙 {fancy('menu')}", reply_markup=main_kb(uid),
            reply_to_message_id=reply_to); return

    if is_admin:
        if text == "📊 Dashboard":
            p, a, r, rev = pay_stats()
            txt = (f"📊 <b>{fancy('dashboard')}</b>\n{div()}\n\n"
                   f"👥 ᴜꜱᴇʀꜱ: <b>{total_users()}</b>\n"
                   f"🆕 ɴᴇᴡ (24ʜ): <b>{new_users_24h()}</b>\n"
                   f"👥 ɢʀᴏᴜᴘꜱ: <b>{group_count()}</b>\n"
                   f"🔍 ꜱᴇᴀʀᴄʜᴇꜱ: <b>{total_searches()}</b>\n"
                   f"✅ ꜰᴊ ᴠᴇʀɪꜰɪᴇᴅ: <b>{users_col.count_documents({'fj_verified': True})}</b>\n\n"
                   f"💰 ᴘᴇɴᴅɪɴɢ: <b>{p}</b> | ✅ <b>{a}</b> | ❌ <b>{r}</b>\n"
                   f"💵 ᴛᴏᴛᴀʟ ʀᴇᴠᴇɴᴜᴇ: <b>₹{rev}</b>\n"
                   f"📈 ʀᴇᴠ (24ʜ): <b>₹{revenue_24h()}</b>\n"
                   f"💎 ᴄʀᴇᴅɪᴛꜱ ꜱᴏʟᴅ: <b>{total_credits_sold()}</b>\n\n"
                   f"🛰️ ᴘʏʀᴏ: <b>{'✅ ON' if _pyro_ready else '🔴 OFF'}</b>\n"
                   f"🔧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ: <b>{'🟢 ON' if is_maintenance() else '🔴 OFF'}</b>")
            bot.send_message(cid, txt, parse_mode='HTML',
                reply_markup=dashboard_kb(), reply_to_message_id=reply_to); return

        if text == "👥 Users":
            bot.send_message(cid, f"👥 <b>{fancy('user management')}</b>", parse_mode='HTML',
                reply_markup=users_kb(), reply_to_message_id=reply_to); return
        if text == "💳 Payments":
            bot.send_message(cid, f"💳 <b>{fancy('payment management')}</b>", parse_mode='HTML',
                reply_markup=payments_kb(), reply_to_message_id=reply_to); return
        if text == "🔧 Services":
            bot.send_message(cid, f"🔧 <b>{fancy('service configuration')}</b>", parse_mode='HTML',
                reply_markup=services_kb(), reply_to_message_id=reply_to); return
        if text == "🎟 Promos":
            bot.send_message(cid, f"🎟 <b>{fancy('promo management')}</b>", parse_mode='HTML',
                reply_markup=promos_kb(), reply_to_message_id=reply_to); return
        if text == "📢 Broadcast":
            bot.send_message(cid, f"📢 <b>{fancy('broadcast center')}</b>", parse_mode='HTML',
                reply_markup=broadcast_kb(), reply_to_message_id=reply_to); return
        if text == "📢 Force Join":
            bot.send_message(cid, f"📢 <b>{fancy('force join')}</b>", parse_mode='HTML',
                reply_markup=force_kb(), reply_to_message_id=reply_to); return
        if text == "👥 Groups":
            txt = f"👥 <b>{fancy('group management')}</b>\n{div()}\n\nᴛᴏᴛᴀʟ ɢʀᴏᴜᴘꜱ: <b>{group_count()}</b>"
            bot.send_message(cid, txt, parse_mode='HTML',
                reply_markup=groups_kb(), reply_to_message_id=reply_to); return
        if text == "⚙️ Settings":
            bot.send_message(cid, f"⚙️ <b>{fancy('admin settings')}</b>",
                parse_mode='HTML', reply_markup=settings_main_kb(), reply_to_message_id=reply_to); return
        if text == "🛡️ Security":
            bot.send_message(cid, f"🛡️ <b>{fancy('security center')}</b>", parse_mode='HTML',
                reply_markup=security_kb(), reply_to_message_id=reply_to); return
        if text == "📈 Analytics":
            bot.send_message(cid, f"📈 <b>{fancy('analytics')}</b>",
                parse_mode='HTML', reply_markup=analytics_kb(), reply_to_message_id=reply_to); return
        if text == "💾 Backup":
            bot.send_message(cid, f"💾 <b>{fancy('backup & export')}</b>",
                parse_mode='HTML', reply_markup=backup_kb(), reply_to_message_id=reply_to); return
        if text == "📮 Feedback":
            cnt = feedback_col.count_documents({})
            bot.send_message(cid, f"📮 <b>Feedback ({cnt})</b>",
                parse_mode='HTML', reply_markup=feedback_kb(), reply_to_message_id=reply_to); return
        if text == "🚀 Bot Info":
            uptime = time.time() - _start_time
            hh = int(uptime // 3600); mm = int((uptime % 3600) // 60)
            me = get_bot_me()
            txt = (f"🚀 <b>{fancy('bot info')}</b>\n{div()}\n\n"
                   f"📛 ɴᴀᴍᴇ: <b>{BOT_USERNAME}</b>\n"
                   f"🆔 ɪᴅ: <code>{me.id if me else '?'}</code>\n"
                   f"⏱ ᴜᴘᴛɪᴍᴇ: <b>{hh}h {mm}m</b>\n"
                   f"🛰️ ᴘʏʀᴏɢʀᴀᴍ: <b>{'✅ READY' if _pyro_ready else '🔴 DISABLED'}</b>\n"
                   f"💾 ᴍᴏɴɢᴏ: <b>✅ CONNECTED</b>\n"
                   f"🐍 ᴠᴇʀꜱɪᴏɴ: <b>v31 FJ REAL-TIME</b>\n"
                   f"👑 ᴀᴅᴍɪɴ: <b>{ADMIN_ID}</b>")
            bot.send_message(cid, txt, parse_mode='HTML',
                reply_markup=botinfo_kb(), reply_to_message_id=reply_to); return
        if text == "📝 Logs":
            try:
                logs = list(logs_col.find().sort("at", -1).limit(20))
                if not logs:
                    bot.send_message(cid, "No logs yet.", reply_to_message_id=reply_to); return
                r = f"📝 <b>{fancy('recent logs')}</b>\n{div()}\n\n"
                for lg in logs:
                    t = lg.get("at", "").strftime("%d-%b %H:%M") if lg.get("at") else "?"
                    r += f"<code>{t}</code> | {lg.get('action','?')}\n"
                bot.send_message(cid, r[:4000], parse_mode='HTML', reply_to_message_id=reply_to)
            except Exception as e:
                bot.send_message(cid, f"❌ {e}", reply_to_message_id=reply_to)
            return

    if is_maintenance() and not is_admin:
        bot.send_message(cid, f"🔧 {fancy('maintenance')}", reply_to_message_id=reply_to); return
    if is_banned(uid) and not is_admin:
        bot.send_message(cid, f"🚫 {fancy('banned')}", reply_to_message_id=reply_to); return

    if text == "📞 Number To Info":
        states[uid] = {'state': 'awaiting_number'}
        bot.send_message(cid, f"📱 <b>{fancy('send number')}</b>\n\n"
            f"ꜱᴜᴘᴘᴏʀᴛᴇᴅ:\n• <code>9876543210</code>\n• <code>+919876543210</code>\n• <code>98765 43210</code>\n\n"
            f"ᴄᴏꜱᴛ: {get_setting('search_cost',5)}ᴄʀ",
            parse_mode='HTML', reply_to_message_id=reply_to)
    elif text == "🔒 Username To Info":
        states[uid] = {'state': 'awaiting_username'}
        bot.send_message(cid, f"🔒 <b>{fancy('username to info')}</b>\n\nꜱᴇɴᴅ:\n"
            f"• <code>@username</code>\n• <code>username</code>\n• <code>t.me/username</code>\n• <code>user_id</code>\n\n"
            f"ᴄᴏꜱᴛ: {get_setting('tg2num_cost',5)}ᴄʀ",
            parse_mode='HTML', reply_to_message_id=reply_to)
    elif text == "🆔 Aadhaar To Info":
        states[uid] = {'state': 'awaiting_aadhaar'}
        bot.send_message(cid, f"🆔 <b>{fancy('send 12-digit aadhaar')}</b>\n\nᴄᴏꜱᴛ: {get_setting('aadhaar_cost',10)}ᴄʀ",
            parse_mode='HTML', reply_to_message_id=reply_to)
    elif text == "🚗 Vehicle Info":
        states[uid] = {'state': 'awaiting_vehicle'}
        bot.send_message(cid,
            f"🚗 <b>{fancy('send vehicle number')}</b>\n\n"
            f"• <code>JH15U4500</code>\n• <code>DL01AB1234</code>\n• <code>MH-12-DE-1234</code>\n\n"
            f"ᴄᴏꜱᴛ: {get_setting('vehicle_cost',10)}ᴄʀ",
            parse_mode='HTML', reply_to_message_id=reply_to)
    elif text == "💰 Refer & Earn":
        link = f"https://t.me/{BOT_USERNAME.replace('@','')}?start=ref_{uid}"
        refs, bonus, searches = user_stats(uid)
        rb = get_setting("referral_bonus", 10)
        r = (f"🎁 <b>{fancy('refer and earn')}</b>\n\n"
             f"🔗 ʏᴏᴜʀ ʟɪɴᴋ:\n<code>{link}</code>\n\n"
             f"📌 +{rb} ᴄʀ ᴘᴇʀ ʀᴇꜰᴇʀʀᴀʟ\n"
             f"<i>(Bonus tab milega jab aapka refer FJ verify kar lega)</i>\n\n"
             f"📊 ʀᴇꜰꜱ: {refs} | ʙᴏɴᴜꜱ: {bonus}")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("📋 Copy", callback_data=f"copyref_{uid}"),
               InlineKeyboardButton("🔙", callback_data="home"))
        bot.send_message(cid, r, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)
    elif text == "🛒 Buy Credits":
        t, kb = buy_kb()
        bot.send_message(cid, t, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)
    elif text == "🎟 Redeem Code":
        states[uid] = {'state': 'awaiting_promo'}
        bot.send_message(cid, "🎟 Send code:", reply_to_message_id=reply_to)
    elif text == "👤 My Profile":
        u = get_or_create_user(uid)
        st = "👑 ᴀᴅᴍɪɴ" if is_admin else ("🚫 ʙᴀɴɴᴇᴅ" if u.get("banned") else f"{u.get('credits',0)} ᴄʀ")
        refs, bonus, searches = user_stats(uid)
        r = (f"👤 <b>{fancy('profile')}</b>\n\n🆔 <code>{uid}</code>\n"
             f"💎 ᴄʀᴇᴅɪᴛꜱ: {st}\n🎯 ᴛʀɪᴇꜱ: {tries_display(uid)}\n"
             f"📌 ʀᴇꜰꜱ: {refs}\n🎁 ʙᴏɴᴜꜱ: {bonus}\n🔍 ꜱᴇᴀʀᴄʜᴇꜱ: {searches}")
        bot.send_message(cid, r, parse_mode='HTML', reply_to_message_id=reply_to)
    elif text == "➕ Add Me To Group":
        bot_username = BOT_USERNAME.replace('@','')
        group_url = f"https://t.me/{bot_username}?startgroup=true"
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=group_url))
        bot.send_message(cid,
            f"👥 <b>{fancy('add me to your group')}</b>\n\n"
            f"ᴀᴅᴅ ᴛʜɪꜱ ʙᴏᴛ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ᴜꜱᴇ ᴀʟʟ ꜰᴇᴀᴛᴜʀᴇꜱ!\n\n📌 ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ",
            parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)
    elif text == "❓ Help":
        bot.send_message(cid, f"📞 ᴄᴏɴᴛᴀᴄᴛ: {ADMIN_USERNAME}\n\nᴜꜱᴇ /start ꜰᴏʀ ᴍᴇɴᴜ",
            reply_to_message_id=reply_to)
    elif text == "ℹ️ About":
        about = get_setting("about_text", "") or f"ℹ️ ᴏꜱɪɴᴛ ʙᴏᴛ ᴠ31\n{BOT_USERNAME}"
        bot.send_message(cid, about, reply_to_message_id=reply_to)

def process_promo(uid, cid, code, reply_to=None):
    r = redeem_promo(code, uid)
    if r is None:
        bot.send_message(cid, "❌ Invalid/expired", parse_mode='HTML', reply_to_message_id=reply_to)
    elif r == -1:
        bot.send_message(cid, "⚠️ Already used", parse_mode='HTML', reply_to_message_id=reply_to)
    else:
        bot.send_message(cid, f"✅ +{r} ᴄʀ!\nʙᴀʟᴀɴᴄᴇ: {get_credits(uid)}",
            parse_mode='HTML', reply_to_message_id=reply_to)

# =================================================================
#  PAYMENT FLOWS
# =================================================================
def show_amount(uid, cid, amount, reply_to=None):
    rate = int(get_setting("credits_per_rupee", 1))
    if rate <= 0: rate = 1
    credits = amount * rate
    mon = int(get_setting("upi_manual_enabled", 1))
    auto_ok = is_auto_upi_available()
    text = (f"💳 <b>{fancy('deposit request')}</b>\n\n💰 ₹{amount}\n💎 <b>{credits} ᴄʀ</b>\n"
            f"💱 ₹1 = {rate}\n\n📌 ᴄʜᴏᴏꜱᴇ:")
    kb = InlineKeyboardMarkup(row_width=1)
    if auto_ok:
        kb.add(InlineKeyboardButton("⚡ Auto UPI", callback_data=f"pm_auto_{amount}_{credits}"))
    else:
        kb.add(InlineKeyboardButton("⚡ Auto UPI (Unavailable)", callback_data="auto_na"))
    if mon:
        kb.add(InlineKeyboardButton("📋 Manual UPI", callback_data=f"pm_manual_{amount}_{credits}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="buy"))
    bot.send_message(cid, text, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)

def show_manual(uid, cid, amount, credits, reply_to=None):
    upi = get_setting("upi_manual_id", "not set")
    qr = get_setting("upi_manual_qr", "")
    caption = (f"📋 <b>{fancy('manual upi')}</b>\n\n💰 ₹{amount}\n💎 {credits}ᴄʀ\n"
               f"📱 ᴜᴘɪ: <code>{upi}</code>\n\n1. ᴘᴀʏ\n2. ᴛᴀᴘ ✅\n3. ꜱᴇɴᴅ ꜱᴄʀᴇᴇɴꜱʜᴏᴛ")
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ I've Paid", callback_data=f"ip_manual_{amount}_{credits}"),
           InlineKeyboardButton("🔙 Back", callback_data="buy"))
    if qr and qr.startswith("http"):
        try:
            bot.send_photo(cid, qr, caption=caption, parse_mode='HTML',
                reply_markup=kb, reply_to_message_id=reply_to); return
        except: pass
    bot.send_message(cid, caption, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)

def handle_auto_upi(uid, cid, amount, credits, reply_to=None):
    if not is_auto_upi_available():
        bot.send_message(cid, "⚡ Unavailable.", reply_to_message_id=reply_to); return
    am = AnimMsg(cid, stages=stg_create(), title="CREATING ORDER", reply_to=reply_to)
    am.start()
    try: ok, oid, link, qr, upi, raw = create_gateway_order(amount, uid)
    except Exception as e: ok, oid, link, qr, upi, raw = False, None, None, None, None, str(e)
    am.stop()
    if not ok:
        am.edit(err_frame("ORDER FAILED", f"<i>{str(raw)[:200]}</i>")); return
    am.flash_complete(); am.delete()
    pid = create_payment(uid, cid, amount, credits, pay_mode="auto", order_id=oid, payment_link=link)
    states[uid] = {'state': 'waiting_payment', 'order_id': oid, 'payment_id': pid,
                    'amount': amount, 'credits': credits, 'pay_mode': 'auto'}
    lines = [f"✅ <b>{fancy('payment ready')}</b>\n", f"💰 ₹{amount} → 💎 {credits}",
             f"🆔 <code>{oid}</code>"]
    if upi: lines.append(f"📱 ᴜᴘɪ: <code>{upi}</code>")
    lines.append(f"\n⏱ 5 ᴍɪɴ ꜱᴇꜱꜱɪᴏɴ")
    caption = "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=1)
    if link: kb.add(InlineKeyboardButton("💳 Pay Now", url=link))
    kb.add(InlineKeyboardButton("🔄 Check Status", callback_data=f"cp_{oid}"))
    kb.add(InlineKeyboardButton("📸 Screenshot", callback_data=f"ss_{oid}"))
    kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="buy"))
    qr_msg = None
    if qr and qr.startswith("http"):
        qr_msg = send_qr_image(cid, qr, caption, kb, reply_to)
    if qr_msg:
        threading.Thread(target=poll_order_async,
            args=(uid, cid, oid, amount, credits, qr_msg.message_id), daemon=True).start()
    else:
        if qr: caption += f"\n\n🖼 <a href='{qr}'>QR</a>"
        bot.send_message(cid, caption, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)
        threading.Thread(target=poll_order_async,
            args=(uid, cid, oid, amount, credits, None), daemon=True).start()

# =================================================================
#  POLLER
# =================================================================
def poll_order_async(uid, cid, order_id, amount, credits, msg_id=None):
    checks = 0
    while checks < 70:
        time.sleep(3 if checks < 10 else 6); checks += 1
        try:
            ok, status, info = verify_gateway_order(order_id)
            if ok: _credit_on_success(uid, cid, order_id, amount, credits, info, msg_id); return
            if status == "expired": _mark_expired(order_id); return
        except Exception as e: logger.warning(f"[POLL] {checks}: {e}")
    _mark_expired(order_id)

def _mark_expired(order_id):
    try: payments_col.update_one({"order_id": order_id, "status": "pending"},
        {"$set": {"status": "expired", "expired_at": now()}})
    except: pass

def _credit_on_success(uid, cid, order_id, amount, credits, info, msg_id):
    p = payments_col.find_one({"order_id": order_id, "user_id": uid, "status": "pending"})
    if not p: return
    utr = (info.get("utr") if info else None) or f"FG_{order_id}"
    u = payments_col.find_one_and_update(
        {"_id": p["_id"], "status": "pending"},
        {"$set": {"status": "approved", "approved_at": now(), "utr": utr,
                  "gateway_response": (info.get("raw") if info else None),
                  "auto_verified": True}},
        return_document=ReturnDocument.AFTER)
    if not u:
        u = payments_col.find_one({"_id": p["_id"]})
    if not u: return
    credited_now = _credit_payment_atomic(u)
    if not credited_now:
        logger.info(f"Payment {order_id} already credited")
    txt = (f"✅ <b>{fancy('payment verified')}</b>\n\n💰 ₹{amount}\n💎 +{credits}ᴄʀ\n"
           f"📊 ʙᴀʟᴀɴᴄᴇ: {get_credits(uid)}\n🆔 <code>{order_id}</code>")
    if info and info.get("utr"): txt += f"\n🧾 {info['utr']}"
    if msg_id:
        try: bot.edit_message_caption(chat_id=cid, message_id=msg_id, caption=txt, parse_mode='HTML'); return
        except: pass
    try: bot.send_message(cid, txt, parse_mode='HTML')
    except: pass

def resume_pending_orders():
    try:
        pending = list(payments_col.find({"status":"pending","pay_mode":"auto","order_id":{"$exists":True,"$ne":None}}))
    except: return
    for p in pending:
        c = p.get("created_at")
        if c and (now() - c).total_seconds() > ORDER_LIFETIME:
            _mark_expired(p["order_id"]); continue
        cid = p.get("chat_id") or p.get("user_id")
        if cid:
            threading.Thread(target=poll_order_async,
                args=(p["user_id"], cid, p["order_id"], p["amount"], p["credits"], None),
                daemon=True).start()

# =================================================================
#  BROADCAST
# =================================================================
bcast_q = queue.Queue()
def bcast_worker():
    while True:
        task = bcast_q.get()
        if task is None: break
        us, msg, kw = task
        pin = int(get_setting("broadcast_pin", 0))
        for u in us:
            try:
                sent = bot.send_message(u, msg, **kw)
                if pin:
                    try: bot.pin_chat_message(u, sent.message_id)
                    except: pass
                time.sleep(0.05)
            except: pass
        bcast_q.task_done()

threading.Thread(target=bcast_worker, daemon=True).start()

def bcast_photo_worker(us, file_id, caption):
    pin = int(get_setting("broadcast_pin", 0))
    for u in us:
        try:
            sent = bot.send_photo(u, file_id, caption=caption)
            if pin:
                try: bot.pin_chat_message(u, sent.message_id)
                except: pass
            time.sleep(0.05)
        except: pass

_start_time = time.time()

# =================================================================
#  COMMANDS
# =================================================================
@bot.message_handler(commands=['start'])
def cmd_start(m):
    uid = m.from_user.id
    uname = m.from_user.username or "user"
    cid = m.chat.id
    is_group = m.chat.type in ('group', 'supergroup')

    cache_tg_user(m.from_user); upd_last_seen(uid)
    if is_banned(uid) and not is_admin_user(uid):
        bot.reply_to(m, f"🚫 {fancy('banned')}"); return
    get_or_create_user(uid)

    if ' ' in m.text:
        parts = m.text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            try: rid = int(parts[1].replace('ref_', ''))
            except: rid = None
            if rid and rid != uid and referral_enabled():
                ex = users_col.find_one({"user_id": uid})
                if ex and not ex.get("referred_by") and not ex.get("pending_referrer"):
                    users_col.update_one({"user_id": uid},
                        {"$set": {"pending_referrer": rid}})

    if is_group and group_enabled():
        register_group(m.chat.id, m.chat.title, getattr(m.chat, 'username', None))
        bot.reply_to(m, f"👋 <b>{fancy('hello')}</b> @{uname}\n\nᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ ᴍᴇ /start ᴋᴀʀᴇɪɴ ᴛᴏ ᴜꜱᴇ ʙᴏᴛ.\n➡️ @{BOT_USERNAME.replace('@','')}",
                     parse_mode='HTML')
        return

    if m.chat.type == 'private':
        if not manager.ensure(uid, cid, {"type": "start"}): return
    bot.reply_to(m, welcome_txt(uid, uname), parse_mode='HTML', reply_markup=main_kb(uid))

@bot.message_handler(commands=['buy'])
def cmd_buy(m):
    uid = m.from_user.id
    cache_tg_user(m.from_user)
    if m.chat.type != 'private':
        bot.reply_to(m, f"💬 ᴘʀɪᴠᴀᴛᴇ ᴍᴇ ᴜꜱᴇ ᴋᴀʀᴇɪɴ: @{BOT_USERNAME.replace('@','')}")
        return
    if not manager.ensure(uid, m.chat.id): return
    t, kb = buy_kb()
    bot.send_message(m.chat.id, t, parse_mode='HTML', reply_markup=kb)

@bot.message_handler(commands=['admin'])
def cmd_admin(m):
    uid = m.from_user.id
    if not is_admin_user(uid):
        bot.reply_to(m, "❌ Admin only"); return
    if m.chat.type != 'private':
        bot.reply_to(m, "❌ Admin panel only in private chat."); return
    bot.reply_to(m, f"👑 <b>{fancy('admin panel')}</b>", parse_mode='HTML', reply_markup=admin_kb())

@bot.message_handler(commands=['addgroup'])
def cmd_addgroup(m):
    bot_username = BOT_USERNAME.replace('@','')
    group_url = f"https://t.me/{bot_username}?startgroup=true"
    kb = InlineKeyboardMarkup().row(InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=group_url))
    bot.reply_to(m, f"👥 <b>{fancy('add me to group')}</b>", parse_mode='HTML', reply_markup=kb)

@bot.message_handler(commands=['my_tries'])
def cmd_my_tries(m):
    bot.reply_to(m, f"🎯 ᴛʀɪᴇꜱ: <b>{tries_display(m.from_user.id)}</b>", parse_mode='HTML')

@bot.message_handler(commands=['help'])
def cmd_help(m):
    txt = (
        f"❓ <b>{fancy('help')}</b>\n{div()}\n\n"
        f"<b>{fancy('commands')}:</b>\n"
        f"/start — ᴍᴀɪɴ ᴍᴇɴᴜ\n/buy — ʙᴜʏ ᴄʀᴇᴅɪᴛꜱ\n"
        f"/my_tries — ʀᴇᴍᴀɪɴɪɴɢ ᴛʀɪᴇꜱ\n/help — ᴛʜɪꜱ ᴍᴇꜱꜱᴀɢᴇ\n"
        f"/addgroup — ᴀᴅᴅ ʙᴏᴛ ᴛᴏ ɢʀᴏᴜᴘ\n/feedback — ꜱᴇɴᴅ ꜰᴇᴇᴅʙᴀᴄᴋ\n\n"
        f"<b>{fancy('services')}:</b>\n"
        f"📞 ɴᴜᴍʙᴇʀ ᴛᴏ ɪɴꜰᴏ\n🔒 ᴜꜱᴇʀɴᴀᴍᴇ ᴛᴏ ɪɴꜰᴏ\n"
        f"🆔 ᴀᴀᴅʜᴀᴀʀ ᴛᴏ ɪɴꜰᴏ\n🚗 ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ\n\n"
        f"{div_soft()}\n📞 ᴄᴏɴᴛᴀᴄᴛ: {ADMIN_USERNAME}")
    bot.reply_to(m, txt, parse_mode='HTML')

@bot.message_handler(commands=['feedback'])
def cmd_feedback(m):
    states[m.from_user.id] = {'state': 'feedback'}
    bot.reply_to(m, "📮 Send your feedback/suggestion:")

@bot.message_handler(commands=['pyro_health'])
def cmd_pyro_health(m):
    if m.from_user.id != ADMIN_ID:
        bot.reply_to(m, "❌ Admin only"); return
    info = [f"🛰️ <b>Pyrogram</b>",
            f"Session: {'✅' if PYRO_SESSION else '❌'}",
            f"Ready: {'✅' if _pyro_ready else '❌'}",
            f"Error: <code>{_pyro_error or 'none'}</code>"]
    if _pyro_ready and _pyro_me:
        info.append(f"Account: @{_pyro_me.username or _pyro_me.id}")
    bot.reply_to(m, "\n".join(info), parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def cmd_stats(m):
    if not is_admin_user(m.from_user.id):
        bot.reply_to(m, "❌ Admin only"); return
    p, a, r, rev = pay_stats()
    txt = (f"📊 <b>Quick Stats</b>\n\n👥 Users: {total_users()}\n"
           f"👥 Groups: {group_count()}\n🔍 Searches: {total_searches()}\n"
           f"✅ FJ Verified: {users_col.count_documents({'fj_verified': True})}\n"
           f"💰 Revenue: ₹{rev}\n⏳ Pending: {p}")
    bot.reply_to(m, txt, parse_mode='HTML')

# =================================================================
#  CHAT JOIN REQUEST
# =================================================================
@bot.chat_join_request_handler(func=lambda r: True)
def on_join_request(r):
    try:
        cid = r.chat.id
        uid = r.from_user.id
        uname = r.from_user.username or "user"
        fname = r.from_user.first_name or ""
        logger.info(f"📥 Join request: {uid} (@{uname}) → {cid}")

        fj_cids = [c[0] for c in manager.channels] if manager else []
        if cid in fj_cids:
            mark_join_request(uid, cid)
            logger.info(f"✅ Join request tracked: U{uid} → C{cid}")

        try:
            bot.send_message(ADMIN_ID,
                f"📥 <b>New Channel Join Request</b>\n\n"
                f"👤 <b>{fname}</b> (@{uname})\n"
                f"🆔 <code>{uid}</code>\n📢 Channel: <code>{cid}</code>\n\n"
                f"<i>Open channel → Join Requests → Approve/Reject manually.</i>",
                parse_mode='HTML')
        except: pass

        try:
            bot.send_message(uid,
                f"✅ <b>{fancy('join request received')}</b>\n\n"
                f"ᴀᴅᴍɪɴ ᴊᴀʟᴅ ʜɪ ᴀᴘᴘʀᴏᴠᴇ ᴋᴀʀᴇɢᴀ.\n"
                f"ᴀᴀᴘ ᴀʙ ʙᴏᴛ ᴜꜱᴇ ᴋᴀʀ ꜱᴀᴋᴛᴇ ʜᴀɪɴ — Verify dabao!",
                parse_mode='HTML')
        except: pass
    except Exception as e:
        logger.error(f"join_request handler error: {e}")

# =================================================================
#  MENU BUTTONS
# =================================================================
ALL_MENU_BUTTONS = [
    "📞 Number To Info","🔒 Username To Info","🆔 Aadhaar To Info","🚗 Vehicle Info",
    "🛒 Buy Credits","💰 Refer & Earn","🎟 Redeem Code","👤 My Profile",
    "➕ Add Me To Group","❓ Help","ℹ️ About","👑 ADMIN PANEL",
    "📊 Dashboard","👥 Users","💳 Payments","🔧 Services","🎟 Promos",
    "📢 Broadcast","📢 Force Join","👥 Groups","⚙️ Settings","🛡️ Security",
    "📈 Analytics","💾 Backup","🚀 Bot Info","📝 Logs","📮 Feedback","🔙 Back to Menu"
]

@bot.message_handler(func=lambda m: m.text in ALL_MENU_BUTTONS)
def menu_btn(m):
    uid = m.from_user.id
    cid = m.chat.id
    cache_tg_user(m.from_user)
    is_group = m.chat.type in ('group', 'supergroup')
    if is_group and group_enabled():
        register_group(m.chat.id, m.chat.title, getattr(m.chat, 'username', None))
    if m.chat.type == 'private':
        if not manager.ensure(uid, cid, {"type": "menu_button", "data": m.text}): return
    process_menu(uid, cid, m.text, m.message_id)

# =================================================================
#  TEXT HANDLER
# =================================================================
@bot.message_handler(
    content_types=['text'],
    func=lambda m: (
        m.text not in ALL_MENU_BUTTONS and
        not m.text.startswith('/')
    )
)
def text_handler(m):
    uid = m.from_user.id
    cid = m.chat.id
    text = m.text.strip()
    mid = m.message_id

    cache_tg_user(m.from_user); upd_last_seen(uid)
    if m.chat.type in ('group', 'supergroup') and group_enabled():
        register_group(m.chat.id, m.chat.title, getattr(m.chat, 'username', None))
    if is_banned(uid) and not is_admin_user(uid):
        bot.reply_to(m, f"🚫 {fancy('banned')}"); return

    st = states.get(uid, {}); s = st.get('state')
    bypass = s in ('promo1','promo2','broadcast','ban','unban','manual_ss','waiting_payment',
        'waiting_ss','custom_amt','ads_input','fj_add','fj_add_link','user_search',
        'user_addcr','user_remcr','user_setcr','sub_add','grp_welcome','bc_custom','manual_credit',
        'awaiting_number','awaiting_username','awaiting_aadhaar','awaiting_promo',
        'awaiting_vehicle','feedback','user_fullinfo','fj_custom_msg','fj_reset_user')
    is_admin = is_admin_user(uid)
    if not is_admin and is_maintenance() and not bypass:
        bot.send_message(cid, f"🔧 {fancy('maintenance')}", reply_to_message_id=mid); return

    if not bypass and m.chat.type == 'private' and not is_admin:
        _k, _v = classify_input(text)
        if _k == "number": _pending = {"type": "number_search", "data": _v}
        elif _k == "aadhaar": _pending = {"type": "aadhaar_search", "data": _v}
        elif _k == "vehicle": _pending = {"type": "vehicle_search", "data": _v}
        elif not text.startswith('/') and len(text) == 12 and text.isalnum() and text.isupper():
            _pending = {"type": "promo_redeem", "data": text}
        else: _pending = {"type": "start"}
        if not manager.ensure(uid, cid, _pending): return

    if s == 'awaiting_number': states[uid] = {}; process_number(uid, cid, text, mid); return
    if s == 'awaiting_username': states[uid] = {}; process_tg2num(uid, cid, text, mid); return
    if s == 'awaiting_aadhaar': states[uid] = {}; process_aadhaar(uid, cid, text, mid); return
    if s == 'awaiting_vehicle': states[uid] = {}; process_vehicle(uid, cid, text, mid); return
    if s == 'awaiting_promo': states[uid] = {}; process_promo(uid, cid, text, mid); return

    if s == 'feedback':
        try:
            feedback_col.insert_one({"user_id": uid, "text": text[:1000],
                "at": now(), "username": m.from_user.username or ""})
            bot.reply_to(m, "✅ Thanks for your feedback!")
            try:
                bot.send_message(ADMIN_ID,
                    f"📮 <b>New Feedback</b>\n👤 <code>{uid}</code>\n@{m.from_user.username or 'user'}\n\n{text[:800]}",
                    parse_mode='HTML')
            except: pass
        except: bot.reply_to(m, "❌ Failed")
        states[uid] = {}; return

    if len(text) == 12 and text.isalnum() and text.isupper():
        try:
            if promo_col.find_one({"code": text}): process_promo(uid, cid, text, mid); return
        except: pass

    if is_admin:
        if s == 'ads_input':
            field = st.get('field')
            try:
                int_fields = ('welcome_bonus','referral_bonus','search_cost','aadhaar_cost',
                              'tg2num_cost','vehicle_cost','credits_per_rupee','daily_tries',
                              'min_payment','max_payment','group_auto_delete_seconds')
                if field in int_fields:
                    val = int(text); set_setting(field, val)
                    bot.reply_to(m, f"✅ <b>{field}</b> = {val}", parse_mode='HTML')
                else:
                    set_setting(field, text.strip())
                    show_val = text.strip()
                    if field.endswith("_key_env") and len(show_val) > 4:
                        show_val = "***" + show_val[-4:]
                    bot.reply_to(m, f"✅ <b>{field}</b> updated:\n<code>{html_module.escape(show_val[:300])}</code>",
                                 parse_mode='HTML')
            except Exception as e: bot.reply_to(m, f"❌ Invalid: {e}")
            log_action(uid, f"set_{field}", text[:100])
            states[uid] = {}
            panel = st.get('panel', 'main')
            if panel == 'eco': bot.send_message(cid, "⚙️ Economics:", reply_markup=admin_economics_kb())
            elif panel == 'costs': bot.send_message(cid, "⚙️ Costs:", reply_markup=admin_costs_kb())
            elif panel == 'tries': bot.send_message(cid, "⚙️ Tries:", reply_markup=admin_tries_kb())
            elif panel == 'pay': bot.send_message(cid, "⚙️ Payment:", reply_markup=admin_pay_kb())
            elif panel == 'custom': bot.send_message(cid, "🎨 Custom:", reply_markup=admin_custom_kb())
            elif panel == 'endpoints': bot.send_message(cid, "🔗 Endpoints:", reply_markup=services_endpoints_kb())
            elif panel == 'groups': bot.send_message(cid, "👥 Groups:", reply_markup=groups_kb())
            else: bot.send_message(cid, "⚙️ Settings:", reply_markup=settings_main_kb())
            return

        if s == 'user_search':
            try:
                t = text.replace('@','').strip()
                if t.isdigit(): u = users_col.find_one({"user_id": int(t)})
                else: u = tg_users_col.find_one({"username_lower": t.lower()})
                if not u: bot.reply_to(m, "❌ Not found"); states[uid] = {}; return
                target_id = u.get("user_id")
                ud = users_col.find_one({"user_id": target_id}) or {}
                txt = (f"👤 <b>User Details</b>\n{div()}\n\n"
                       f"🆔 <code>{target_id}</code>\n📛 @{u.get('username','N/A')}\n"
                       f"👋 {u.get('full_name','N/A')}\n💎 Credits: {ud.get('credits',0)}\n"
                       f"🔍 Searches: {ud.get('searches',0)}\n📌 Refs: {ud.get('total_referrals',0)}\n"
                       f"🚫 Banned: {'Yes' if ud.get('banned') else 'No'}\n"
                       f"✅ FJ Verified: {'Yes' if ud.get('fj_verified') else 'No'}\n"
                       f"📥 FJ Requests: {len(ud.get('fj_requested_channels', []))} channels\n"
                       f"📅 Joined: {ud.get('joined_at','?')}")
                bot.reply_to(m, txt, parse_mode='HTML')
            except Exception as e: bot.reply_to(m, f"❌ {e}")
            states[uid] = {}; return

        if s == 'user_fullinfo':
            try:
                tid = int(text.strip())
                ud = users_col.find_one({"user_id": tid}) or {}
                tu = tg_users_col.find_one({"user_id": tid}) or {}
                pays = list(payments_col.find({"user_id": tid, "status": "approved"}))
                total_paid = sum(p.get("amount", 0) for p in pays)
                total_cr = sum(p.get("credits", 0) for p in pays)
                req_chs = ud.get("fj_requested_channels", [])
                txt = (f"👤 <b>Full User Info</b>\n{div()}\n\n"
                       f"🆔 <code>{tid}</code>\n📛 @{tu.get('username','N/A')}\n"
                       f"👋 {tu.get('full_name','N/A')}\n\n"
                       f"💎 Credits: <b>{ud.get('credits',0)}</b>\n"
                       f"🔍 Searches: {ud.get('searches',0)}\n📌 Refs: {ud.get('total_referrals',0)}\n"
                       f"🎁 Bonus: {ud.get('bonus_earned',0)}\n🚫 Banned: {'Yes' if ud.get('banned') else 'No'}\n"
                       f"✅ FJ Verified: {'Yes' if ud.get('fj_verified') else 'No'}\n"
                       f"📥 FJ Requests: {len(req_chs)} channels {req_chs}\n"
                       f"🎯 Tries: {ud.get('tries_used',0)} used\n\n"
                       f"💰 <b>Payments</b>\nTotal Paid: ₹{total_paid}\n"
                       f"Credits Bought: {total_cr}\nCount: {len(pays)}")
                bot.reply_to(m, txt, parse_mode='HTML')
            except Exception as e: bot.reply_to(m, f"❌ {e}")
            states[uid] = {}; return

        if s == 'user_addcr':
            try:
                parts = text.split(); tid = int(parts[0]); amt = int(parts[1])
                add_credits(tid, amt)
                bot.reply_to(m, f"✅ Added {amt}cr to {tid}\nNew: {get_credits(tid)}")
                log_action(uid, "add_credits", f"{tid}:{amt}")
            except: bot.reply_to(m, "❌ Usage: <user_id> <amount>")
            states[uid] = {}; return

        if s == 'user_remcr':
            try:
                parts = text.split(); tid = int(parts[0]); amt = int(parts[1])
                deduct_credits(tid, amt)
                bot.reply_to(m, f"✅ Removed {amt}cr from {tid}\nNew: {get_credits(tid)}")
                log_action(uid, "remove_credits", f"{tid}:{amt}")
            except: bot.reply_to(m, "❌ Usage: <user_id> <amount>")
            states[uid] = {}; return

        if s == 'user_setcr':
            try:
                parts = text.split(); tid = int(parts[0]); amt = int(parts[1])
                users_col.update_one({"user_id": tid}, {"$set": {"credits": amt}}, upsert=True)
                bot.reply_to(m, f"✅ Set balance for {tid} = {amt}cr")
                log_action(uid, "set_credits", f"{tid}:{amt}")
            except: bot.reply_to(m, "❌ Usage: <user_id> <new_balance>")
            states[uid] = {}; return

        if s == 'ban':
            t = text.replace('@','').strip()
            try: tid = int(t)
            except:
                try: tid = bot.get_chat(f"@{t}").id
                except: bot.reply_to(m, "❌ Not found"); states[uid] = {}; return
            if tid == uid: bot.reply_to(m, "❌ Can't ban yourself!"); states[uid] = {}; return
            if tid == ADMIN_ID: bot.reply_to(m, "❌ Can't ban main admin!"); states[uid] = {}; return
            ban_user(tid); bot.reply_to(m, f"✅ Banned {tid}")
            log_action(uid, "ban", str(tid))
            states[uid] = {}; return

        if s == 'unban':
            t = text.replace('@','').strip()
            try: tid = int(t)
            except:
                try: tid = bot.get_chat(f"@{t}").id
                except: bot.reply_to(m, "❌ Not found"); states[uid] = {}; return
            unban_user(tid); bot.reply_to(m, f"✅ Unbanned {tid}")
            log_action(uid, "unban", str(tid))
            states[uid] = {}; return

        if s == 'sub_add':
            if not is_main_admin(uid):
                bot.reply_to(m, "❌ Only main admin can add sub-admins"); states[uid] = {}; return
            t = text.replace('@','').strip()
            try: tid = int(t)
            except:
                try: tid = bot.get_chat(f"@{t}").id
                except: bot.reply_to(m, "❌ Not found"); states[uid] = {}; return
            try:
                admins_col.insert_one({"user_id": tid, "added_by": uid, "added_at": now()})
                bot.reply_to(m, f"✅ Added sub-admin {tid}")
                log_action(uid, "subadmin_add", str(tid))
            except: bot.reply_to(m, "❌ Already exists")
            states[uid] = {}; return

        if s == 'sub_remove':
            if not is_main_admin(uid):
                bot.reply_to(m, "❌ Only main admin can remove sub-admins"); states[uid] = {}; return
            try:
                tid = int(text.strip())
                admins_col.delete_one({"user_id": tid})
                bot.reply_to(m, f"✅ Removed sub-admin {tid}")
                log_action(uid, "subadmin_rm", str(tid))
            except: bot.reply_to(m, "❌ Invalid")
            states[uid] = {}; return

        if s == 'grp_welcome':
            set_setting("group_welcome", text.strip())
            bot.reply_to(m, "✅ Group welcome message set")
            states[uid] = {}; return

        if s == 'promo1':
            if text.isdigit():
                states[uid]['credits'] = int(text); states[uid]['state'] = 'promo2'
                bot.reply_to(m, "Ab kitne users?")
            else: bot.reply_to(m, "❌ Number")
            return

        if s == 'promo2':
            if text.isdigit():
                lim = int(text); cr = states[uid].get('credits')
                code = gen_promo()
                if save_promo(code, cr, lim, uid):
                    bot.reply_to(m, f"🎁 <code>{code}</code>\n{cr}cr × {lim}", parse_mode='HTML')
                    log_action(uid, "promo_gen", f"{code}:{cr}:{lim}")
                else:
                    bot.reply_to(m, "❌ Failed to save promo (duplicate code?)")
                states[uid] = {}
            else: bot.reply_to(m, "❌ Number")
            return

        if s == 'broadcast':
            bcast_q.put((all_users(), text, {'parse_mode':'HTML'}))
            bot.reply_to(m, "✅ Queued to all users.")
            log_action(uid, "broadcast_text")
            states[uid] = {}; return

        if s == 'bc_custom':
            targets = st.get('targets', [])
            bcast_q.put((targets, text, {'parse_mode':'HTML'}))
            bot.reply_to(m, f"✅ Queued to {len(targets)} targets.")
            states[uid] = {}; return

        if s == 'manual_credit':
            try:
                parts = text.split(); tid = int(parts[0]); amt = int(parts[1])
                add_credits(tid, amt)
                bot.reply_to(m, f"✅ Manually credited {amt}cr to {tid}")
                log_action(uid, "manual_credit", f"{tid}:{amt}")
            except: bot.reply_to(m, "❌ Usage: <user_id> <amount>")
            states[uid] = {}; return

        if s == 'fj_add':
            if text.startswith('@'):
                try: cid_ = bot.get_chat(text).id
                except Exception as e: bot.reply_to(m, f"❌ {e}"); states[uid]={}; return
            else:
                try: cid_ = int(text)
                except: bot.reply_to(m, "❌ Invalid"); states[uid]={}; return
            states[uid] = {'state': 'fj_add_link', 'cid': cid_}
            bot.reply_to(m, "Send channel invite link (must start with https://t.me/):")
            return

        if s == 'fj_add_link':
            cid_ = st.get('cid')
            link = text.strip()
            if not link or link.lower() == 'skip':
                bot.reply_to(m, "❌ Invite link required"); states[uid] = {}; return
            ok, msg = manager.add(cid_, link)
            bot.reply_to(m, ("✅ " if ok else "❌ ") + msg)
            log_action(uid, "fj_add", f"{cid_}")
            states[uid] = {}; return

        if s == 'fj_custom_msg':
            txt = text.strip()
            if txt.lower() == 'reset':
                set_setting("fj_custom_msg", "")
                bot.reply_to(m, "✅ Reset to default message")
            else:
                set_setting("fj_custom_msg", txt)
                bot.reply_to(m, f"✅ Custom FJ message set:\n<code>{html_module.escape(txt[:200])}</code>",
                             parse_mode='HTML')
            log_action(uid, "fj_custom_msg", txt[:80])
            states[uid] = {}
            bot.send_message(cid, "📢 Force Join:", reply_markup=force_kb())
            return

        if s == 'fj_reset_user':
            try:
                tid = int(text.strip())
                unmark_fj_verified(tid)
                bot.reply_to(m, f"✅ Reset ALL verify data for <code>{tid}</code>", parse_mode='HTML')
            except:
                bot.reply_to(m, "❌ Invalid user_id")
            states[uid] = {}
            bot.send_message(cid, "📢 Force Join:", reply_markup=force_kb())
            return

    if s == 'custom_amt':
        try:
            a = int(text)
            mn = int(get_setting("min_payment", MIN_PAYMENT)); mx = int(get_setting("max_payment", MAX_PAYMENT))
            if a < mn or a > mx: bot.reply_to(m, f"❌ ₹{mn}–₹{mx}"); return
        except: bot.reply_to(m, "❌ Valid amount"); return
        states[uid] = {}; show_amount(uid, cid, a, mid); return

    kind, value = classify_input(text)
    if kind == "number":
        if m.chat.type == 'private' and not manager.ensure(uid, cid, {"type":"number_search","data":value}): return
        process_number(uid, cid, value, mid); return
    elif kind == "aadhaar":
        if m.chat.type == 'private' and not manager.ensure(uid, cid, {"type":"aadhaar_search","data":value}): return
        process_aadhaar(uid, cid, value, mid); return
    elif kind == "vehicle":
        if m.chat.type == 'private' and not manager.ensure(uid, cid, {"type":"vehicle_search","data":value}): return
        process_vehicle(uid, cid, value, mid); return

# =================================================================
#  GROUP HANDLERS
# =================================================================
@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(m):
    try:
        me = get_bot_me()
        if not me: return
        for member in m.new_chat_members:
            if member.id == me.id:
                if group_enabled():
                    register_group(m.chat.id, m.chat.title, getattr(m.chat, 'username', None))
                    wl = get_setting("group_welcome", "👋 Bot added! Type /start to begin.")
                    bot.send_message(m.chat.id, wl)
                    logger.info(f"✅ Bot added to group: {m.chat.title} ({m.chat.id})")
    except Exception as e: logger.error(f"new_members: {e}")

@bot.message_handler(content_types=['left_chat_member'])
def on_left_member(m):
    try:
        me = get_bot_me()
        if not me: return
        if m.left_chat_member.id == me.id:
            remove_group(m.chat.id)
            logger.info(f"❌ Bot removed from group: {m.chat.title}")
    except: pass

# =================================================================
#  PHOTO HANDLER
# =================================================================
@bot.message_handler(content_types=['photo'])
def photo_h(m):
    uid = m.from_user.id
    cid = m.chat.id
    cache_tg_user(m.from_user); upd_last_seen(uid)
    st = states.get(uid, {}); s = st.get('state')

    payment_states = ('waiting_ss', 'manual_ss')
    if s not in payment_states:
        if m.chat.type == 'private' and not manager.ensure(uid, cid, {"type":"media"}): return

    if is_banned(uid) and not is_admin_user(uid): bot.reply_to(m, "🚫 Banned"); return

    if s in payment_states:
        file_id = m.photo[-1].file_id
        pid = st.get('payment_id')
        if pid:
            existing = get_payment(pid)
            already_notified = existing.get("admin_notified", False) if existing else False
            payments_col.update_one({"_id": ObjectId(pid)}, {"$set": {"screenshot_id": file_id}})
            p = get_payment(pid)
        else:
            amt = st.get('amount', 0); cr = st.get('credits', 0)
            pm = "manual" if s == 'manual_ss' else "auto"
            pid = create_payment(uid, cid, amt, cr, pm, screenshot_id=file_id, order_id=st.get('order_id'))
            p = get_payment(pid)
            already_notified = False
        if p:
            if already_notified:
                bot.reply_to(m, "✅ Screenshot updated. Admin already notified.")
                states[uid] = {}; return
            try:
                uname = bot.get_chat(uid).username or "user"
                txt = (f"📋 <b>PAYMENT</b>\n\n👤 @{uname} (<code>{uid}</code>)\n"
                       f"💵 ₹{p['amount']}\n💎 {p['credits']}\n🆔 <code>{pid}</code>")
                kb = InlineKeyboardMarkup()
                kb.row(InlineKeyboardButton("✅ Approve", callback_data=f"ap_{pid}"),
                       InlineKeyboardButton("❌ Reject", callback_data=f"rj_{pid}"))
                admin_ids = [ADMIN_ID] + [a['user_id'] for a in admins_col.find()]
                sent_ok = False
                for aid in set(admin_ids):
                    try:
                        bot.send_photo(aid, file_id, caption=txt, parse_mode='HTML', reply_markup=kb)
                        sent_ok = True
                    except: pass
                if sent_ok:
                    payments_col.update_one({"_id": ObjectId(pid)}, {"$set": {"admin_notified": True}})
                    bot.reply_to(m, "✅ Sent to admin.")
                else:
                    bot.reply_to(m, "⚠️ Admin notification failed. Try again.")
            except Exception as e:
                logger.error(f"Forward: {e}")
        states[uid] = {}; return

    if is_admin_user(uid) and s == 'broadcast':
        file_id = m.photo[-1].file_id
        caption = m.caption or "📢 Broadcast"
        users = all_users()
        threading.Thread(target=bcast_photo_worker,
            args=(users, file_id, caption), daemon=True).start()
        bot.reply_to(m, f"📢 Photo broadcast queued to {len(users)} users.")
        states[uid] = {}

@bot.message_handler(content_types=['video','document','audio','sticker','animation','voice'])
def bcast_media(m):
    uid = m.from_user.id
    if not is_admin_user(uid): return
    if states.get(uid, {}).get('state') != 'broadcast': return
    us = all_users(); ct = m.content_type
    def go():
        pin = int(get_setting("broadcast_pin", 0))
        for u in us:
            try:
                sent = None
                if ct=='video': sent = bot.send_video(u, m.video.file_id, caption="📢")
                elif ct=='document': sent = bot.send_document(u, m.document.file_id, caption="📢")
                elif ct=='audio': sent = bot.send_audio(u, m.audio.file_id, caption="📢")
                elif ct=='sticker': sent = bot.send_sticker(u, m.sticker.file_id)
                elif ct=='animation': sent = bot.send_animation(u, m.animation.file_id, caption="📢")
                elif ct=='voice': sent = bot.send_voice(u, m.voice.file_id, caption="📢")
                if pin and sent:
                    try: bot.pin_chat_message(u, sent.message_id)
                    except: pass
                time.sleep(0.05)
            except: pass
    threading.Thread(target=go, daemon=True).start()
    bot.reply_to(m, "📢 Queued."); states[uid] = {}

# =================================================================
#  CALLBACK HANDLER
# =================================================================
@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    uid = call.from_user.id
    cid = call.message.chat.id
    d = call.data
    cache_tg_user(call.from_user)
    is_admin = is_admin_user(uid)

    if d == "adm_back":
        if not is_admin: safe_ans(call); return
        try: bot.delete_message(cid, call.message.message_id)
        except: pass
        bot.send_message(cid, "👑 Admin Panel", reply_markup=admin_kb()); safe_ans(call); return

    if d == "adm_dash_refresh":
        if not is_admin: safe_ans(call); return
        p, a, r, rev = pay_stats()
        txt = (f"📊 <b>{fancy('dashboard')}</b>\n{div()}\n\n"
               f"👥 ᴜꜱᴇʀꜱ: <b>{total_users()}</b>\n"
               f"🆕 ɴᴇᴡ (24ʜ): <b>{new_users_24h()}</b>\n"
               f"👥 ɢʀᴏᴜᴘꜱ: <b>{group_count()}</b>\n"
               f"🔍 ꜱᴇᴀʀᴄʜᴇꜱ: <b>{total_searches()}</b>\n\n"
               f"💰 ᴘᴇɴᴅɪɴɢ: <b>{p}</b> | ✅ <b>{a}</b> | ❌ <b>{r}</b>\n"
               f"💵 ʀᴇᴠᴇɴᴜᴇ: <b>₹{rev}</b> | 24ʜ: <b>₹{revenue_24h()}</b>\n7ᴅ: <b>₹{revenue_7d()}</b>")
        try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML', reply_markup=dashboard_kb())
        except: pass
        safe_ans(call, "✅ Refreshed"); return

    if d == "adm_dash_export":
        if not is_admin: safe_ans(call); return
        csv_d = export_csv()
        if csv_d:
            try:
                bio = io.BytesIO(csv_d.encode('utf-8')); bio.name = "users.csv"
                bot.send_document(cid, bio, caption="📥 Users Export")
            except: pass
        safe_ans(call); return

    if d == "adm_dash_detailed":
        if not is_admin: safe_ans(call); return
        p, a, r, rev = pay_stats()
        txt = (f"📊 <b>Detailed Stats</b>\n{div()}\n\n"
               f"<b>Users</b>\n• Total: {total_users()}\n• Banned: {users_col.count_documents({'banned':1})}\n"
               f"• New 24h: {new_users_24h()}\n"
               f"• FJ Verified: {users_col.count_documents({'fj_verified': True})}\n"
               f"• Cached TG: {tg_users_col.count_documents({})}\n\n"
               f"<b>Groups</b>\n• Total: {group_count()}\n\n"
               f"<b>Payments</b>\n• Pending: {p}\n• Approved: {a}\n• Rejected: {r}\n"
               f"• Total Revenue: ₹{rev}\n• 24h: ₹{revenue_24h()}\n• 7d: ₹{revenue_7d()}\n"
               f"• Credits Sold: {total_credits_sold()}\n\n"
               f"<b>Services</b>\n• Searches: {total_searches()}\n"
               f"• Promos: {promo_col.count_documents({})}\n• Feedback: {feedback_col.count_documents({})}")
        bot.send_message(cid, txt, parse_mode='HTML')
        safe_ans(call); return

    if d == "adm_user_search": states[uid] = {'state': 'user_search'}; bot.send_message(cid, "🔍 Send user_id or @username:"); safe_ans(call); return
    if d == "adm_user_ban": states[uid] = {'state': 'ban'}; bot.send_message(cid, "🚫 Send user_id or @username to ban:"); safe_ans(call); return
    if d == "adm_user_unban": states[uid] = {'state': 'unban'}; bot.send_message(cid, "✅ Send user_id or @username to unban:"); safe_ans(call); return
    if d == "adm_user_banned_list":
        banned = list(users_col.find({"banned": 1}).limit(50))
        if not banned: bot.send_message(cid, "No banned users."); safe_ans(call); return
        txt = f"🚫 <b>Banned Users ({len(banned)})</b>\n\n"
        for b in banned: txt += f"<code>{b.get('user_id')}</code>\n"
        bot.send_message(cid, txt, parse_mode='HTML'); safe_ans(call); return
    if d == "adm_user_addcr": states[uid] = {'state': 'user_addcr'}; bot.send_message(cid, "💎 Send: <user_id> <amount>"); safe_ans(call); return
    if d == "adm_user_remcr": states[uid] = {'state': 'user_remcr'}; bot.send_message(cid, "➖ Send: <user_id> <amount>"); safe_ans(call); return
    if d == "adm_user_setcr": states[uid] = {'state': 'user_setcr'}; bot.send_message(cid, "💰 Send: <user_id> <new_balance>"); safe_ans(call); return
    if d == "adm_user_fullinfo": states[uid] = {'state': 'user_fullinfo'}; bot.send_message(cid, "👤 Send user_id:"); safe_ans(call); return
    if d == "adm_user_top_searches":
        tops = list(users_col.find({"searches":{"$gt":0}}).sort("searches",-1).limit(10))
        if not tops: bot.send_message(cid, "None"); safe_ans(call); return
        txt = "🏆 <b>Top Searchers</b>\n\n"
        for u in tops: txt += f"<code>{u['user_id']}</code> — {u.get('searches',0)}\n"
        bot.send_message(cid, txt, parse_mode='HTML'); safe_ans(call); return
    if d == "adm_user_top_refs":
        tops = list(users_col.find({"total_referrals":{"$gt":0}}).sort("total_referrals",-1).limit(10))
        if not tops: bot.send_message(cid, "None"); safe_ans(call); return
        txt = "🎁 <b>Top Referrers</b>\n\n"
        for u in tops: txt += f"<code>{u['user_id']}</code> — {u.get('total_referrals',0)}\n"
        bot.send_message(cid, txt, parse_mode='HTML'); safe_ans(call); return
    if d == "adm_user_active":
        c = now() - timedelta(hours=24)
        cnt = users_col.count_documents({"last_seen": {"$gte": c}})
        bot.send_message(cid, f"🔥 Active (24h): <b>{cnt}</b>", parse_mode='HTML'); safe_ans(call); return
    if d == "adm_user_rich":
        tops = list(users_col.find().sort("credits",-1).limit(10))
        txt = "💎 <b>Top Rich Users</b>\n\n"
        for u in tops: txt += f"<code>{u['user_id']}</code> — {u.get('credits',0)}cr\n"
        bot.send_message(cid, txt, parse_mode='HTML'); safe_ans(call); return
    if d == "adm_user_export":
        csv_d = export_csv()
        if csv_d:
            try:
                bio = io.BytesIO(csv_d.encode('utf-8')); bio.name = "users.csv"
                bot.send_document(cid, bio, caption=f"📥 {total_users()} users")
            except: pass
        safe_ans(call); return

    if d == "adm_pay_pending":
        ps = get_pending()
        if not ps: bot.send_message(cid, "No pending payments."); safe_ans(call); return
        kb = InlineKeyboardMarkup(row_width=1)
        for p in ps[:20]:
            ic = "⚡" if p.get("pay_mode")=="auto" else "📋"
            kb.add(InlineKeyboardButton(f"{ic} ₹{p['amount']} → {p['credits']}cr | U{p['user_id']}",
                callback_data=f"pv_{str(p['_id'])}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="adm_back_pay"))
        bot.send_message(cid, f"💰 <b>Pending ({len(ps)})</b>", parse_mode='HTML', reply_markup=kb)
        safe_ans(call); return
    if d == "adm_pay_approved":
        bot.send_message(cid, f"✅ Approved: {payments_col.count_documents({'status': 'approved'})}")
        safe_ans(call); return
    if d == "adm_pay_rejected":
        bot.send_message(cid, f"❌ Rejected: {payments_col.count_documents({'status': 'rejected'})}")
        safe_ans(call); return
    if d == "adm_pay_revenue":
        p, a, r, rev = pay_stats()
        bot.send_message(cid, f"💰 Total: ₹{rev}\n24h: ₹{revenue_24h()}\n7d: ₹{revenue_7d()}\n"
                              f"Credits sold: {total_credits_sold()}\nApproved: {a} | Rejected: {r}")
        safe_ans(call); return
    if d == "adm_pay_manual":
        states[uid] = {'state': 'manual_credit'}
        bot.send_message(cid, "💎 Send: <user_id> <amount>"); safe_ans(call); return
    if d == "adm_pay_recent":
        ps = list(payments_col.find().sort("created_at", -1).limit(15))
        if not ps: bot.send_message(cid, "No payments."); safe_ans(call); return
        txt = "🧾 <b>Recent Payments</b>\n\n"
        for p in ps:
            emoji = "⏳" if p.get("status")=="pending" else ("✅" if p.get("status")=="approved" else "❌")
            txt += f"{emoji} ₹{p['amount']} → {p['credits']}cr | U{p['user_id']}\n"
        bot.send_message(cid, txt[:4000], parse_mode='HTML'); safe_ans(call); return
    if d == "adm_back_pay":
        try: bot.delete_message(cid, call.message.message_id)
        except: pass
        bot.send_message(cid, "💳 Payment", reply_markup=payments_kb()); safe_ans(call); return

    if d == "adm_svc_back":
        try: bot.edit_message_text("🔧 Services", cid, call.message.message_id, reply_markup=services_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_svc_numcost":
        states[uid] = {'state': 'ads_input', 'field': 'search_cost', 'panel': 'main'}
        bot.send_message(cid, "📞 Number cost:"); safe_ans(call); return
    if d == "adm_svc_tgcost":
        states[uid] = {'state': 'ads_input', 'field': 'tg2num_cost', 'panel': 'main'}
        bot.send_message(cid, "🔒 Username cost:"); safe_ans(call); return
    if d == "adm_svc_aadhaarcost":
        states[uid] = {'state': 'ads_input', 'field': 'aadhaar_cost', 'panel': 'main'}
        bot.send_message(cid, "🆔 Aadhaar cost:"); safe_ans(call); return
    if d == "adm_svc_vehiclecost":
        states[uid] = {'state': 'ads_input', 'field': 'vehicle_cost', 'panel': 'main'}
        bot.send_message(cid, "🚗 Vehicle cost:"); safe_ans(call); return
    if d == "adm_svc_endpoints":
        try: bot.edit_message_text("🔗 Endpoints", cid, call.message.message_id, reply_markup=services_endpoints_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_svc_test":
        results = [
            f"📞 Number API: {'✅' if get_setting('api_url_env', API_URL) else '❌'}",
            f"🔒 TG2Num API: {'✅' if get_setting('tg2num_url_env', TG2NUM_URL) else '❌'}",
            f"🆔 Aadhaar API: {'✅' if get_setting('aadhaar_url_env', AADHAAR_URL) else '❌'}",
            f"🚗 Vehicle API: {'✅' if get_setting('vehicle_url_env', VEHICLE_URL) else '❌'}",
            f"🛰️ Pyrogram: {'✅' if _pyro_ready else '❌'}",
        ]
        bot.send_message(cid, "🧪 <b>API Health</b>\n\n" + "\n".join(results), parse_mode='HTML')
        safe_ans(call); return

    ep_map = {
        'adm_ep_numurl': ('api_url_env', 'Number API URL', False),
        'adm_ep_numkey': ('api_key_env', 'Number API Key', True),
        'adm_ep_tgurl': ('tg2num_url_env', 'TG2Num URL', False),
        'adm_ep_tgkey': ('tg2num_key_env', 'TG2Num Key', True),
        'adm_ep_aadhaarurl': ('aadhaar_url_env', 'Aadhaar API URL', False),
        'adm_ep_aadhaarkey': ('aadhaar_key_env', 'Aadhaar API Key', True),
        'adm_ep_vehicleurl': ('vehicle_url_env', 'Vehicle API URL', False),
        'adm_ep_vehiclekey': ('vehicle_key_env', 'Vehicle API Key', True),
    }
    if d in ep_map:
        if not is_admin: safe_ans(call); return
        field, prompt, is_secret = ep_map[d]
        current = get_setting(field, "") or "not set"
        if is_secret and len(str(current)) > 4: current = "***" + str(current)[-4:]
        states[uid] = {'state': 'ads_input', 'field': field, 'panel': 'endpoints'}
        try:
            bot.edit_message_text(
                f"✏️ <b>{prompt}</b>\n\nᴄᴜʀʀᴇɴᴛ: <code>{html_module.escape(str(current))[:200]}</code>\n\nꜱᴇɴᴅ ɴᴇᴡ ᴠᴀʟᴜᴇ:",
                cid, call.message.message_id, parse_mode='HTML')
        except:
            bot.send_message(cid, f"✏️ {prompt}\nCurrent: {current}\n\nSend new value:")
        safe_ans(call); return

    if d == "adm_ep_viewall":
        if not is_admin: safe_ans(call); return
        vals = []
        for k, label in [("api_url_env","Number URL"),("api_key_env","Number Key"),
            ("tg2num_url_env","TG2Num URL"),("tg2num_key_env","TG2Num Key"),
            ("aadhaar_url_env","Aadhaar URL"),("aadhaar_key_env","Aadhaar Key"),
            ("vehicle_url_env","Vehicle URL"),("vehicle_key_env","Vehicle Key")]:
            v = get_setting(k, "") or "not set"
            if "key" in k and len(str(v)) > 4: v = "***" + str(v)[-4:]
            vals.append(f"<b>{label}</b>:\n<code>{html_module.escape(str(v)[:150])}</code>")
        bot.send_message(cid, "🔗 <b>All Endpoints</b>\n\n" + "\n\n".join(vals), parse_mode='HTML')
        safe_ans(call); return

    if d == "adm_promo_gen":
        states[uid] = {'state': 'promo1'}; bot.send_message(cid, "🎟 Kitne credits ka code?"); safe_ans(call); return
    if d == "adm_promo_list":
        cs = all_promos()
        if not cs: bot.send_message(cid, "No promos."); safe_ans(call); return
        r = "🎟 <b>Promo Codes</b>\n\n"
        for c in cs[:20]: r += f"<code>{c['code']}</code> – {c['reward_credits']}cr, {c['used_count']}/{c['max_users']}\n"
        bot.send_message(cid, r, parse_mode='HTML'); safe_ans(call); return
    if d == "adm_promo_stats":
        cs = all_promos(); total = len(cs); used = sum(c.get("used_count", 0) for c in cs)
        bot.send_message(cid, f"🎟 Promos: {total}\nTotal Redeems: {used}"); safe_ans(call); return

    if d == "adm_bc_text": states[uid] = {'state': 'broadcast'}; bot.send_message(cid, "📝 Send broadcast text:"); safe_ans(call); return
    if d == "adm_bc_photo": states[uid] = {'state': 'broadcast'}; bot.send_message(cid, "📸 Send photo with caption:"); safe_ans(call); return
    if d == "adm_bc_video": states[uid] = {'state': 'broadcast'}; bot.send_message(cid, "🎬 Send video with caption:"); safe_ans(call); return
    if d == "adm_bc_groups":
        groups = all_groups()
        if not groups: bot.send_message(cid, "No groups."); safe_ans(call); return
        states[uid] = {'state': 'bc_custom', 'targets': [g["chat_id"] for g in groups]}
        bot.send_message(cid, f"📢 Send broadcast to {len(groups)} groups:"); safe_ans(call); return
    if d == "adm_bc_settings":
        try: bot.edit_message_text("⚙️ Broadcast Settings", cid, call.message.message_id, reply_markup=broadcast_settings_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_bc_tog_pin":
        cur = int(get_setting("broadcast_pin", 0)); set_setting("broadcast_pin", 0 if cur else 1)
        try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=broadcast_settings_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_bc_tog_fwd":
        cur = int(get_setting("broadcast_forward", 0)); set_setting("broadcast_forward", 0 if cur else 1)
        try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=broadcast_settings_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_bc_back":
        try: bot.edit_message_text("📢 Broadcast", cid, call.message.message_id, reply_markup=broadcast_kb())
        except: pass
        safe_ans(call); return

    if d == "adm_grp_toggle":
        cur = int(get_setting("group_enabled", 1)); set_setting("group_enabled", 0 if cur else 1)
        try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=groups_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_grp_tog_autodel":
        cur = int(get_setting("group_auto_delete", 1)); set_setting("group_auto_delete", 0 if cur else 1)
        try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=groups_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_grp_set_deltime":
        states[uid] = {'state': 'ads_input', 'field': 'group_auto_delete_seconds', 'panel': 'groups'}
        cur = group_auto_delete_seconds()
        bot.send_message(cid,
            f"⏱ <b>Set Auto-Delete Time</b>\n\nᴄᴜʀʀᴇɴᴛ: <b>{cur}s</b> ({cur//60} min)\n\n"
            f"ꜱᴇɴᴅ ꜱᴇᴄᴏɴᴅꜱ (ᴇx: 3600 = 1 ʜᴏᴜʀ):", parse_mode='HTML')
        safe_ans(call); return
    if d == "adm_grp_list":
        gs = all_groups()
        if not gs: bot.send_message(cid, "No groups."); safe_ans(call); return
        txt = f"👥 <b>Groups ({len(gs)})</b>\n\n"
        for g in gs[:30]: txt += f"📌 <b>{g.get('title','?')}</b>\n   <code>{g.get('chat_id')}</code>\n"
        bot.send_message(cid, txt, parse_mode='HTML'); safe_ans(call); return
    if d == "adm_grp_bc":
        gs = all_groups()
        if not gs: bot.send_message(cid, "No groups."); safe_ans(call); return
        states[uid] = {'state': 'bc_custom', 'targets': [g["chat_id"] for g in gs]}
        bot.send_message(cid, f"📢 Send broadcast to {len(gs)} groups:"); safe_ans(call); return
    if d == "adm_grp_welcome":
        states[uid] = {'state': 'grp_welcome'}
        bot.send_message(cid, f"📝 Current: {get_setting('group_welcome', '')}\n\nSend new welcome message:")
        safe_ans(call); return
    if d == "adm_grp_leave_all":
        gs = all_groups(); count = 0
        for g in gs:
            try:
                bot.leave_chat(g["chat_id"]); remove_group(g["chat_id"]); count += 1; time.sleep(0.3)
            except: pass
        bot.send_message(cid, f"✅ Left {count} groups"); safe_ans(call); return

    if d == "adm_sec_banned":
        bot.send_message(cid, f"🚫 Banned: {users_col.count_documents({'banned': 1})}"); safe_ans(call); return
    if d == "adm_sec_maint":
        cur = int(get_setting("maintenance_mode", 0)); set_setting("maintenance_mode", 0 if cur else 1)
        bot.send_message(cid, f"🔧 Maintenance: {'ON' if not cur else 'OFF'}"); safe_ans(call); return
    if d == "adm_sec_subadmins":
        try: bot.edit_message_text("👑 Sub-Admins", cid, call.message.message_id, reply_markup=subadmins_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_sec_back":
        try: bot.edit_message_text("🛡️ Security", cid, call.message.message_id, reply_markup=security_kb())
        except: pass
        safe_ans(call); return
    if d == "adm_sub_add":
        if not is_main_admin(uid): safe_ans(call, "❌ Only main admin", True); return
        states[uid] = {'state': 'sub_add'}
        bot.send_message(cid, "👑 Send user_id or @username to add as sub-admin:"); safe_ans(call); return
    if d == "adm_sub_remove":
        if not is_main_admin(uid): safe_ans(call, "❌ Only main admin", True); return
        states[uid] = {'state': 'sub_remove'}
        bot.send_message(cid, "Send user_id to remove:"); safe_ans(call); return
    if d == "adm_sub_list":
        subs = list(admins_col.find())
        if not subs: bot.send_message(cid, "No sub-admins."); safe_ans(call); return
        r = "👑 <b>Sub-Admins</b>\n\n"
        for s in subs: r += f"<code>{s['user_id']}</code>\n"
        bot.send_message(cid, r, parse_mode='HTML'); safe_ans(call); return

    if d == "adm_an_growth":
        days = []
        for i in range(7):
            day = now() - timedelta(days=i)
            start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            cnt = users_col.count_documents({"joined_at": {"$gte": start, "$lt": end}})
            days.append(f"{start.strftime('%d-%b')}: {cnt}")
        bot.send_message(cid, "📊 <b>7 Day Growth</b>\n\n" + "\n".join(reversed(days)), parse_mode='HTML')
        safe_ans(call); return
    if d == "adm_an_searches": bot.send_message(cid, f"🔍 Total: {total_searches()}"); safe_ans(call); return
    if d == "adm_an_revenue":
        p, a, r, rev = pay_stats()
        bot.send_message(cid, f"💰 Total: ₹{rev}\n24h: ₹{revenue_24h()}\n7d: ₹{revenue_7d()}"); safe_ans(call); return
    if d == "adm_an_top":
        tops = list(users_col.find().sort("searches",-1).limit(5))
        r = "🏆 <b>Top Users</b>\n\n"
        for u in tops: r += f"<code>{u['user_id']}</code> — 🔍{u.get('searches',0)} 💰{u.get('credits',0)}\n"
        bot.send_message(cid, r, parse_mode='HTML'); safe_ans(call); return
    if d == "adm_an_vehicle": bot.send_message(cid, f"🚗 Total searches: {total_searches()}"); safe_ans(call); return
    if d == "adm_an_aadhaar": bot.send_message(cid, f"🆔 Total searches: {total_searches()}"); safe_ans(call); return

    if d == "adm_bk_users":
        csv_d = export_csv()
        if csv_d:
            try:
                bio = io.BytesIO(csv_d.encode('utf-8')); bio.name = "users.csv"
                bot.send_document(cid, bio, caption="📤 Users Backup")
            except: pass
        safe_ans(call); return
    if d == "adm_bk_payments":
        try:
            ps = list(payments_col.find({}))
            o = io.StringIO(); w = csv.writer(o)
            w.writerow(["ID","User","Amount","Credits","Status","Created"])
            for p in ps:
                w.writerow([str(p.get("_id")),p.get("user_id"),p.get("amount"),p.get("credits"),p.get("status"),p.get("created_at","")])
            bio = io.BytesIO(o.getvalue().encode('utf-8')); bio.name = "payments.csv"
            bot.send_document(cid, bio, caption="📤 Payments Backup")
        except: pass
        safe_ans(call); return
    if d == "adm_bk_full":
        try:
            data = {
                "users": list(users_col.find({}, {"_id": 0})),
                "payments": list(payments_col.find({}, {"_id": 0})),
                "promos": list(promo_col.find({}, {"_id": 0})),
                "groups": list(groups_col.find({}, {"_id": 0})),
                "settings": list(settings_col.find({}, {"_id": 0})),
                "feedback": list(feedback_col.find({}, {"_id": 0})),
                "exported_at": now().isoformat()
            }
            bio = io.BytesIO(json.dumps(data, default=str, indent=2).encode('utf-8'))
            bio.name = "full_backup.json"
            bot.send_document(cid, bio, caption="💾 Full Backup")
        except Exception as e: bot.send_message(cid, f"❌ {e}")
        safe_ans(call); return
    if d == "adm_bk_feedback":
        try:
            fbs = list(feedback_col.find({}, {"_id": 0}))
            bio = io.BytesIO(json.dumps(fbs, default=str, indent=2).encode('utf-8'))
            bio.name = "feedback.json"
            bot.send_document(cid, bio, caption=f"📮 {len(fbs)} feedback")
        except: pass
        safe_ans(call); return

    if d == "adm_info_refresh":
        try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=botinfo_kb())
        except: pass
        safe_ans(call); return

    if d == "adm_fb_view":
        fbs = list(feedback_col.find().sort("at", -1).limit(10))
        if not fbs: bot.send_message(cid, "No feedback yet."); safe_ans(call); return
        txt = "📮 <b>Recent Feedback</b>\n\n"
        for f in fbs:
            t = f.get("at", "").strftime("%d-%b %H:%M") if f.get("at") else "?"
            txt += f"<code>{t}</code> | <code>{f.get('user_id')}</code>\n{f.get('text','')[:200]}\n{div_soft()}\n"
        bot.send_message(cid, txt[:4000], parse_mode='HTML'); safe_ans(call); return
    if d == "adm_fb_clear":
        cnt = feedback_col.count_documents({}); feedback_col.delete_many({})
        bot.send_message(cid, f"✅ Cleared {cnt} feedback"); safe_ans(call); return

    if d == "force_verify":
        if manager: manager.verify_cb(call)
        return

    if d.startswith('fj_'):
        if not is_admin: safe_ans(call); return
        if d == 'fj_toggle':
            manager.toggle()
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=force_kb())
            except: pass
            safe_ans(call); return
        if d == 'fj_list':
            txt = "📋 <b>Force Join Channels</b>\n\n"
            if manager.active:
                txt += "<b>✅ Active (Bot is Admin):</b>\n"
                for cid_, link in manager.active:
                    priv = "🔒" if ('+' in link or 'joinchat' in link) else "🌐"
                    txt += f"{priv} <code>{cid_}</code>\n   <i>{link[:60]}</i>\n"
            if manager.inactive:
                txt += "\n<b>⚠️ Inactive (Bot NOT admin):</b>\n"
                for cid_, link, reason in manager.inactive[:10]:
                    txt += f"❌ <code>{cid_}</code>\n   <i>{reason[:60]}</i>\n"
            if not manager.channels:
                txt += "<i>No channels. Add one first.</i>\n\n"
                txt += "<i>Note: Bot must be admin in channel for FJ to work properly.</i>"
            kb_r = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Recheck", callback_data="fj_recheck"))
            try:
                bot.edit_message_text(txt[:4000], cid, call.message.message_id, parse_mode='HTML', reply_markup=kb_r)
            except: pass
            safe_ans(call); return
        if d == 'fj_add':
            states[uid] = {'state': 'fj_add'}
            try: bot.edit_message_text("Send channel ID/@username:", cid, call.message.message_id)
            except: pass
            safe_ans(call); return
        if d == 'fj_remove':
            chs = channel_list()
            if not chs: safe_ans(call); return
            kb = InlineKeyboardMarkup(row_width=1)
            for c in chs: kb.add(InlineKeyboardButton(f"❌ {c['channel_id']}", callback_data=f"fj_del_{c['channel_id']}"))
            kb.add(InlineKeyboardButton("🔙", callback_data="adm_back"))
            try: bot.edit_message_text("Remove:", cid, call.message.message_id, reply_markup=kb)
            except: pass
            safe_ans(call); return
        if d.startswith('fj_del_'):
            manager.rm(int(d.split('_')[2])); safe_ans(call, "Removed"); return
        if d == 'fj_stats':
            s = manager.stats()
            txt = (f"📊 <b>Force Join Stats</b>\n{div()}\n\n"
                   f"📢 Total Channels: <b>{s['total']}</b>\n"
                   f"✅ Active: <b>{s['active']}</b>\n"
                   f"⚠️ Inactive: <b>{s['inactive']}</b>\n\n"
                   f"🚫 Total Blocks: <b>{s['blocks']}</b>\n"
                   f"✅ Total Verifies: <b>{s['verifies']}</b>\n"
                   f"👥 Verified Users: <b>{s['verified_users']}</b>\n\n"
                   f"🔀 Enabled: <b>{'Yes ✅' if manager.global_enabled else 'No ❌'}</b>")
            bot.send_message(cid, txt, parse_mode='HTML'); safe_ans(call); return
        if d == 'fj_set_msg':
            states[uid] = {'state': 'fj_custom_msg'}
            cur = get_setting("fj_custom_msg", "") or "(default)"
            bot.send_message(cid,
                f"✏️ <b>Custom FJ Message</b>\n\n"
                f"<b>Current:</b>\n<code>{html_module.escape(str(cur)[:300])}</code>\n\n"
                f"<i>Send new message (HTML allowed)</i>\n"
                f"<i>Or send <code>reset</code> to restore default</i>",
                parse_mode='HTML')
            safe_ans(call); return
        if d == 'fj_reset_user':
            states[uid] = {'state': 'fj_reset_user'}
            bot.send_message(cid, "🔄 Send user_id to reset ALL verify data:"); safe_ans(call); return
        if d == 'fj_recheck':
            manager.reload()
            safe_ans(call, f"✅ Reloaded", True)
            txt = (f"🔄 <b>Reloaded</b>\n\n"
                   f"✅ Active: <b>{len(manager.active)}</b>\n"
                   f"⚠️ Inactive: <b>{len(manager.inactive)}</b>\n"
                   f"📢 Total: <b>{len(manager.channels)}</b>")
            bot.send_message(cid, txt, parse_mode='HTML')
            return
        if d == 'fj_test':
            kb_test = InlineKeyboardMarkup(row_width=1)
            for i, (ch, lk) in enumerate(manager.channels[:10]):
                kb_test.add(InlineKeyboardButton(f"📢 Channel {i+1}", url=lk))
            kb_test.add(InlineKeyboardButton("✅ Verify", callback_data="ps_noop"))
            custom = get_setting("fj_custom_msg", "")
            preview = custom if custom else (f"⚠️ <b>{fancy('please join channels')}</b>\n\nᴊᴏɪɴ ᴋᴀʀᴋᴇ ᴠᴇʀɪꜰʏ ᴅᴀʙᴀᴏ.\n\n<i>Private channel hai to Request bhejo, phir Verify dabao.</i>")
            bot.send_message(cid, f"🧪 <b>FJ Prompt Preview</b>\n{div()}\n\n{preview}",
                parse_mode='HTML', reply_markup=kb_test)
            safe_ans(call, "Preview shown"); return

    if d.startswith('ads_'):
        if not is_admin: safe_ans(call); return
        if d == 'ads_back':
            try: bot.edit_message_text("⚙️ Settings", cid, call.message.message_id, reply_markup=settings_main_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_eco':
            try: bot.edit_message_text("💎 Economics", cid, call.message.message_id, parse_mode='HTML', reply_markup=admin_economics_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_costs':
            try: bot.edit_message_text("🔍 Costs", cid, call.message.message_id, parse_mode='HTML', reply_markup=admin_costs_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_tries':
            try: bot.edit_message_text("🎯 Tries", cid, call.message.message_id, parse_mode='HTML', reply_markup=admin_tries_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_pay':
            try: bot.edit_message_text("💳 Payment", cid, call.message.message_id, parse_mode='HTML', reply_markup=admin_pay_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_sys':
            try: bot.edit_message_text("⚙️ System", cid, call.message.message_id, parse_mode='HTML', reply_markup=admin_sys_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_custom':
            try: bot.edit_message_text("🎨 Customization", cid, call.message.message_id, parse_mode='HTML', reply_markup=admin_custom_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_tog_ref':
            cur = int(get_setting("referral_enabled", 1)); set_setting("referral_enabled", 0 if cur else 1)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=admin_economics_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_tog_mm':
            cur = int(get_setting("maintenance_mode", 0)); set_setting("maintenance_mode", 0 if cur else 1)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=admin_sys_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_tog_gw':
            cur = int(get_setting("gateway_enabled", 0)); set_setting("gateway_enabled", 0 if cur else 1)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=admin_pay_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_tog_manual':
            cur = int(get_setting("upi_manual_enabled", 1)); set_setting("upi_manual_enabled", 0 if cur else 1)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=admin_pay_kb())
            except: pass
            safe_ans(call); return
        if d == 'ads_tries_unlimited':
            set_setting("daily_tries", 0)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=admin_tries_kb())
            except: pass
            safe_ans(call, "✅ Unlimited"); return
        if d == 'ads_tries_reset_all':
            users_col.update_many({}, {"$set": {"tries_used": 0, "tries_date": today_str()}})
            safe_ans(call, "✅ Reset all", True); return
        if d == 'ads_export':
            csv_d = export_csv()
            if csv_d:
                try:
                    bio = io.BytesIO(csv_d.encode('utf-8')); bio.name = "users.csv"
                    bot.send_document(cid, bio, caption="📤 Export")
                except: pass
            safe_ans(call); return
        if d == 'ads_pyro':
            info = [f"🛰️ Pyrogram", f"Ready: {'✅' if _pyro_ready else '❌'}",
                    f"Error: <code>{_pyro_error or 'none'}</code>"]
            bot.send_message(cid, "\n".join(info), parse_mode='HTML'); safe_ans(call); return
        if d == 'ads_pyro_restart':
            bot.send_message(cid, "🔄 Restart Pyrogram... (server restart recommended)"); safe_ans(call); return
        if d == 'ads_mongo':
            try:
                mongo_client.admin.command("ping")
                bot.send_message(cid, f"✅ Mongo OK\nUsers: {users_col.count_documents({})}\nPayments: {payments_col.count_documents({})}")
            except Exception as e: bot.send_message(cid, f"❌ {e}")
            safe_ans(call); return
        setter_map = {
            'ads_set_welcome': ('welcome_bonus','eco','Welcome bonus:'),
            'ads_set_refbonus': ('referral_bonus','eco','Referral bonus:'),
            'ads_set_rate': ('credits_per_rupee','eco','Credits per ₹1:'),
            'ads_set_scost': ('search_cost','costs','Number cost:'),
            'ads_set_acost': ('aadhaar_cost','costs','Aadhaar cost:'),
            'ads_set_tcost': ('tg2num_cost','costs','Username cost:'),
            'ads_set_vcost': ('vehicle_cost','costs','Vehicle cost:'),
            'ads_set_minpay': ('min_payment','costs','Min ₹:'),
            'ads_set_maxpay': ('max_payment','costs','Max ₹:'),
            'ads_set_tries': ('daily_tries','tries','Daily tries:'),
            'ads_set_gwkey': ('gateway_api_key','pay','API key:'),
            'ads_set_gwcreate': ('gateway_create_url','pay','Create URL:'),
            'ads_set_gwstatus': ('gateway_checkout_status_url','pay','Status URL:'),
            'ads_set_gwredirect': ('gateway_redirect_url','pay','Redirect URL:'),
            'ads_set_upiid': ('upi_manual_id','pay','UPI ID:'),
            'ads_set_upiqr': ('upi_manual_qr','pay','QR URL:'),
            'ads_set_powered': ('powered_by','custom','Powered by text:'),
            'ads_set_about': ('about_text','custom','About text:'),
            'ads_set_welcome_emoji': ('welcome_emoji','custom','Welcome emoji:'),
            'ads_set_support': ('support_link','custom','Support link:'),
        }
        if d in setter_map:
            field, panel, prompt = setter_map[d]
            current = get_setting(field, "") or "not set"
            states[uid] = {'state': 'ads_input', 'field': field, 'panel': panel}
            bot.send_message(cid, f"✏️ {prompt}\nCurrent: <code>{html_module.escape(str(current)[:100])}</code>",
                             parse_mode='HTML')
            safe_ans(call); return
        safe_ans(call); return

    if d == "ps_noop": safe_ans(call); return
    if d == "auto_na": safe_ans(call, "Auto UPI unavailable", True); return
    if d.startswith('amt_'):
        if d == 'amt_custom':
            states[uid] = {'state':'custom_amt'}
            mn = int(get_setting("min_payment", MIN_PAYMENT)); mx = int(get_setting("max_payment", MAX_PAYMENT))
            bot.send_message(cid, f"₹{mn}–₹{mx} kitna?")
            safe_ans(call); return
        try: amt = int(d.split('_')[1])
        except: safe_ans(call); return
        show_amount(uid, cid, amt, call.message.message_id); safe_ans(call); return
    if d.startswith('pm_'):
        parts = d.split('_'); mode = parts[1]; amt = int(parts[2]); cr = int(parts[3])
        if mode == "auto": handle_auto_upi(uid, cid, amt, cr, call.message.message_id)
        else: show_manual(uid, cid, amt, cr, call.message.message_id)
        safe_ans(call); return
    if d.startswith('ip_'):
        parts = d.split('_'); amt = int(parts[2]); cr = int(parts[3])
        states[uid] = {'state':'manual_ss','amount':amt,'credits':cr}
        bot.send_message(cid, "📸 Send screenshot:", reply_to_message_id=call.message.message_id)
        safe_ans(call); return
    if d.startswith('cp_'):
        oid = d.replace('cp_','',1)
        p = payments_col.find_one({"order_id":oid,"user_id":uid,"status":"pending"})
        if not p: safe_ans(call, "Not found"); return
        amt = p["amount"]; cr = p["credits"]
        am = AnimMsg(cid, stages=stg_verify(), title="VERIFYING", reply_to=call.message.message_id)
        am.start()
        ok, status, info = verify_gateway_order(oid)
        am.stop()
        if ok:
            _credit_on_success(uid, cid, oid, amt, cr, info, None)
            am.flash_complete()
            am.edit(f"✅ <b>Verified</b>\n💎 +{cr}\n💰 {get_credits(uid)}")
            states[uid] = {}
        else:
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton("🔄 Check Again", callback_data=f"cp_{oid}"),
                   InlineKeyboardButton("📸 Screenshot", callback_data=f"ss_{oid}"))
            am.edit(f"⏳ Pending", mark=kb)
        safe_ans(call); return
    if d.startswith('ss_'):
        oid = d.replace('ss_','',1)
        p = payments_col.find_one({"order_id":oid,"user_id":uid})
        if not p: safe_ans(call, "Not found"); return
        states[uid] = {'state':'waiting_ss','payment_id':str(p["_id"]),
                        'amount':p["amount"],'credits':p["credits"],'order_id':oid}
        bot.send_message(cid, "📸 Send screenshot.", reply_to_message_id=call.message.message_id)
        safe_ans(call); return
    if d.startswith('ap_'):
        if not is_admin: safe_ans(call); return
        pid = d.replace('ap_','',1)
        ok, p = approve_atomic(pid, uid)
        if not ok: safe_ans(call, "Already processed", True); return
        try:
            if call.message.caption:
                bot.edit_message_caption(cid, call.message.message_id,
                    caption=call.message.caption + "\n\n✅ Approved", parse_mode='HTML', reply_markup=None)
        except: pass
        try:
            bot.send_message(p["user_id"], f"✅ <b>Approved</b>\n💎 +{p['credits']}\n💰 {get_credits(p['user_id'])}",
                parse_mode='HTML')
        except: pass
        safe_ans(call, "✅ Approved"); return
    if d.startswith('rj_'):
        if not is_admin: safe_ans(call); return
        pid = d.replace('rj_','',1)
        ok, p = reject_atomic(pid, uid)
        if not ok: safe_ans(call, "Already processed", True); return
        try:
            if call.message.caption:
                bot.edit_message_caption(cid, call.message.message_id,
                    caption=call.message.caption + "\n\n❌ Rejected", parse_mode='HTML', reply_markup=None)
        except: pass
        try: bot.send_message(p["user_id"], "❌ Payment Rejected")
        except: pass
        safe_ans(call, "❌ Rejected"); return
    if d.startswith('pv_'):
        if not is_admin: safe_ans(call); return
        pid = d.replace('pv_','',1)
        p = get_payment(pid)
        if not p: safe_ans(call, "Not found"); return
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("✅ Approve", callback_data=f"ap_{pid}"),
               InlineKeyboardButton("❌ Reject", callback_data=f"rj_{pid}"))
        mode = "⚡ Auto" if p.get("pay_mode")=="auto" else "📋 Manual"
        txt = f"💰 <b>{mode}</b>\n\n👤 <code>{p['user_id']}</code>\n₹{p['amount']}\n💎 {p['credits']}\nOrder: <code>{p.get('order_id') or 'N/A'}</code>"
        try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML', reply_markup=kb)
        except: pass
        safe_ans(call); return

    if d == "home":
        bot.send_message(cid, "🏠", reply_markup=main_kb(uid)); safe_ans(call); return
    if d == "close":
        try: bot.delete_message(cid, call.message.message_id)
        except: pass
        safe_ans(call); return
    if d == "buy":
        t, kb = buy_kb()
        bot.send_message(cid, t, parse_mode='HTML', reply_markup=kb, reply_to_message_id=call.message.message_id)
        safe_ans(call); return
    if d.startswith("copyref_"):
        try: tgt = int(d.split("_")[1])
        except: tgt = uid
        link = f"https://t.me/{BOT_USERNAME.replace('@','')}?start=ref_{tgt}"
        bot.send_message(cid, f"🔗 <b>Referral Link</b>\n\n<code>{link}</code>", parse_mode='HTML')
        safe_ans(call); return
    safe_ans(call)

# =================================================================
#  ENTRY
# =================================================================
if __name__ == "__main__":
    init_db()
    manager = FJManager(bot)
    logger.info("🚀 Bot v31 FJ REAL-TIME starting...")
    init_pyrogram()
    logger.info(f"👑 Admin: {ADMIN_ID}")
    logger.info(f"🛰️ Pyrogram: {'READY' if _pyro_ready else 'DISABLED'}")
    logger.info(f"📞 Number API: {API_URL}")
    logger.info(f"🆔 Aadhaar API: {AADHAAR_URL}")
    logger.info(f"🚗 Vehicle API: {VEHICLE_URL}")
    logger.info(f"🎁 Welcome Bonus: {WELCOME_BONUS} CREDITS")
    logger.info(f"⏱ Group Auto-Delete: {GROUP_AUTO_DELETE_SECONDS}s")
    logger.info(f"📢 Force Join: {len(manager.active)} active, {len(manager.inactive)} inactive")
    resume_pending_orders()

    try:
        bot.set_my_commands([
            BotCommand("start", "🏠 Main Menu"),
            BotCommand("buy", "🛒 Buy Credits"),
            BotCommand("my_tries", "🎯 My Tries"),
            BotCommand("feedback", "📮 Send Feedback"),
            BotCommand("help", "❓ Help"),
            BotCommand("addgroup", "➕ Add to Group"),
        ])
    except: pass

    try:
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=30,
            allowed_updates=telebot.util.update_types
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.critical(f"Crashed: {e}")
