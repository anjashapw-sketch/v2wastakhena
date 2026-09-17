"""
Num Info Bot — V6 FINAL EDITION
- Search works everywhere
- Auto-permissions via &admin= deep link
- Only group admins can add bot
- Welcome bonus (default 15cr)
- Number, Aadhaar APIs admin-panel configurable
- 🔒 Username To Info → TG2Num API (username/userid/link → converts to userid)
- No data found (all null) → NO credit deduction
- API Error reveal added (shows exact error from TG2Num API)
- Group Username Search enabled
- Smooth animation (4% step, 0.04s sleep, 0.18 interval)
- Removed Account/Used/Expires from TG2Num output
"""

import os, sys, re, json, time, random, string, threading, queue, traceback
import html as html_module, csv, io, signal
from urllib.parse import quote as urlquote
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests, telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from pymongo import MongoClient, ReturnDocument
from bson.objectid import ObjectId

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("num_info_bot")


def now(): return datetime.now()


def _env_int(k, d=0):
    try:
        v = os.getenv(k, d)
        if v is None or str(v).strip() == "": return d
        return int(v)
    except: return d


# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = _env_int("ADMIN_ID", 0)
API_URL = os.getenv("API_URL", "")
API_KEY = os.getenv("API_KEY", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@Phoneumber2Info_Robot")
BOT_USERNAME_CLEAN = BOT_USERNAME.replace('@', '')
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@itzanjasha")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "num2info_bot")
FORCE_CHANNELS_ENV = os.getenv("FORCE_CHANNELS", "")
CHANNEL_LINKS_ENV = os.getenv("CHANNEL_LINKS", "")
UPI_MANUAL_ID = os.getenv("UPI_MANUAL_ID", "")
UPI_MANUAL_QR = os.getenv("UPI_MANUAL_QR", "")

AADHAAR_URL = os.getenv("AADHAAR_URL", "https://api-manager-e7lm.onrender.com/api/v1/query")
AADHAAR_KEY = os.getenv("AADHAAR_KEY", "monu_c24e25e7ce9f32b8")
DEFAULT_AADHAAR_COST = _env_int("AADHAAR_COST", 10)

# TG2NUM (username/userid/link → userid lookup)
TG2NUM_URL = os.getenv("TG2NUM_URL", "https://tg2num-botadminshere.vercel.app/")
TG2NUM_KEY = os.getenv("TG2NUM_KEY", "")
DEFAULT_TG2NUM_COST = _env_int("TG2NUM_COST", 5)

FAM_CREATE_URL = os.getenv("FAM_CREATE_URL", "https://famgateway.in/api/create-order")
FAM_VERIFY_URL = os.getenv("FAM_VERIFY_URL", "https://famgateway.in/api/verify-order.php")
FAM_CHECKOUT_STATUS_URL = os.getenv("FAM_CHECKOUT_STATUS_URL", "https://famgateway.in/api/checkout-status.php")
FAM_API_KEY = os.getenv("FAM_API_KEY", "")
FAM_REDIRECT_URL = os.getenv("FAM_REDIRECT_URL", f"https://t.me/{BOT_USERNAME_CLEAN}")

DEFAULT_CREDITS_PER_RUPEE = _env_int("CREDITS_PER_RUPEE", 1)
DEFAULT_SEARCH_COST = _env_int("SEARCH_COST", 5)
DEFAULT_WELCOME_BONUS = _env_int("WELCOME_BONUS", 15)

SPINNER_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
DOT_FRAMES = [".", "..", "...", "...."]

ADD_GROUP_PERMS = "change_info+delete_messages+ban_users+invite_users+pin_messages+add_admins+manage_call+manage_chat"

logger.info(f"🔑 Aadhaar Key: {(AADHAAR_KEY or '')[:12]}...")


# ================= MONGODB =================
try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    mongo_client.admin.command("ping")
    logger.info("✅ MongoDB connected.")
except Exception as e:
    logger.critical(f"❌ MongoDB: {e}"); sys.exit(1)

db = mongo_client[DB_NAME]
users_col = db.users
payments_col = db.payments
promo_col = db.promo_codes
settings_col = db.settings
channels_col = db.force_channels
groups_col = db.groups
logs_col = db.action_logs


def init_db():
    try:
        users_col.create_index("user_id", unique=True)
        channels_col.create_index("channel_id", unique=True)
        groups_col.create_index("chat_id", unique=True)
        payments_col.create_index("status")
        payments_col.create_index("user_id")
        payments_col.create_index("order_id", sparse=True)
    except Exception as e:
        logger.warning(f"Index init: {e}")

    try: payments_col.drop_index("utr_1")
    except: pass
    try:
        payments_col.create_index("utr", unique=True,
            partialFilterExpression={"utr": {"$type": "string"}},
            name="utr_unique_partial")
    except: pass

    defaults = {
        "credits_per_rupee": DEFAULT_CREDITS_PER_RUPEE,
        "search_cost": DEFAULT_SEARCH_COST,
        "aadhaar_cost": DEFAULT_AADHAAR_COST,
        "tg2num_cost": DEFAULT_TG2NUM_COST,
        "welcome_bonus": DEFAULT_WELCOME_BONUS,
        "gateway_enabled": 0,
        "gateway_create_url": FAM_CREATE_URL,
        "gateway_verify_url": FAM_VERIFY_URL,
        "gateway_checkout_status_url": FAM_CHECKOUT_STATUS_URL,
        "gateway_api_key": FAM_API_KEY,
        "gateway_redirect_url": FAM_REDIRECT_URL,
        "upi_manual_id": UPI_MANUAL_ID or "not set",
        "upi_manual_qr": UPI_MANUAL_QR,
        "upi_manual_enabled": 1,
        "force_enabled": "1",
        "maintenance_mode": 0,
        "referral_bonus_referrer": 10,
        "referral_bonus_newuser": 5,
        "daily_free_credits": 0,
        "welcome_msg": "",
        # Number API
        "number_api_url": API_URL or "",
        "number_api_key": API_KEY or "",
        # Aadhaar API
        "aadhaar_api_url": AADHAAR_URL,
        "aadhaar_api_key": AADHAAR_KEY,
        # TG2Num API
        "tg2num_url": TG2NUM_URL,
        "tg2num_key": TG2NUM_KEY,
    }
    for k, v in defaults.items():
        try:
            if not settings_col.find_one({"key": k}):
                settings_col.insert_one({"key": k, "value": v})
        except: pass

    if channels_col.count_documents({}) == 0 and FORCE_CHANNELS_ENV:
        ids = [int(c.strip()) for c in FORCE_CHANNELS_ENV.split(",") if c.strip()]
        links = [l.strip() for l in CHANNEL_LINKS_ENV.split(",") if l.strip()] if CHANNEL_LINKS_ENV else []
        for i, cid in enumerate(ids):
            link = links[i] if i < len(links) else f"https://t.me/joinchat/{cid}"
            try: channels_col.insert_one({"channel_id": cid, "channel_link": link, "enabled": 1})
            except: pass
    logger.info("✅ DB initialized.")


def get_setting(k, d=None):
    try:
        doc = settings_col.find_one({"key": k})
        if not doc: return d
        v = doc.get("value")
        if v is None or v == "" or v == []:
            return d
        return v
    except: return d


def set_setting(k, v):
    try: settings_col.update_one({"key": k}, {"$set": {"value": v}}, upsert=True)
    except: pass


def get_num_api():
    return get_setting("number_api_url", API_URL) or "", get_setting("number_api_key", API_KEY) or ""


def get_aadhaar_api():
    return get_setting("aadhaar_api_url", AADHAAR_URL) or "", get_setting("aadhaar_api_key", AADHAAR_KEY) or ""


def get_tg2num_api():
    return get_setting("tg2num_url", TG2NUM_URL) or "", get_setting("tg2num_key", TG2NUM_KEY) or ""


# ================= USERS =================
def get_or_create_user(uid):
    try:
        u = users_col.find_one({"user_id": uid})
        if u: return u
        bonus = _env_int("WELCOME_BONUS", DEFAULT_WELCOME_BONUS)
        try:
            bonus = int(get_setting("welcome_bonus", DEFAULT_WELCOME_BONUS))
        except: pass
        try:
            users_col.update_one({"user_id": uid}, {"$setOnInsert": {
                "user_id": uid, "credits": bonus,
                "total_referrals": 0, "bonus_earned": 0,
                "banned": 0, "searches": 0, "aadhaar_searches": 0,
                "tg2num_searches": 0,
                "referred_by": None,
                "joined_at": now(), "last_seen": now()
            }}, upsert=True)
        except: pass
        u = users_col.find_one({"user_id": uid})
        return u or {"user_id": uid, "credits": 0, "banned": 0}
    except Exception as e:
        logger.error(f"get_or_create_user: {e}")
        return {"user_id": uid, "credits": 0, "banned": 0}


def get_credits(uid): return get_or_create_user(uid).get("credits", 0)


def add_credits(uid, amt):
    try:
        get_or_create_user(uid)
        users_col.update_one({"user_id": uid}, {"$inc": {"credits": amt}})
    except: pass


def deduct_credits(uid, amt):
    try: users_col.update_one({"user_id": uid}, {"$inc": {"credits": -amt}})
    except: pass


def incr_searches(uid):
    try: users_col.update_one({"user_id": uid}, {"$inc": {"searches": 1}})
    except: pass


def incr_aadhaar(uid):
    try: users_col.update_one({"user_id": uid}, {"$inc": {"aadhaar_searches": 1}})
    except: pass


def incr_tg2num(uid):
    try: users_col.update_one({"user_id": uid}, {"$inc": {"tg2num_searches": 1}})
    except: pass


def add_ref_bonus(rid):
    try:
        b = int(get_setting("referral_bonus_referrer", 10))
        users_col.update_one({"user_id": rid},
            {"$inc": {"credits": b, "total_referrals": 1, "bonus_earned": b}})
    except: pass


def try_claim_referral(new_uid, referrer_id):
    if new_uid == referrer_id: return False
    try:
        r = users_col.find_one_and_update(
            {"user_id": new_uid, "referred_by": None},
            {"$set": {"referred_by": referrer_id}})
        if not r: return False
        add_ref_bonus(referrer_id)
        nb = int(get_setting("referral_bonus_newuser", 5))
        add_credits(new_uid, nb)
        return True
    except: return False


def is_banned(uid):
    try:
        u = users_col.find_one({"user_id": uid})
        return u and u.get("banned", 0) == 1
    except: return False


def ban_user(uid):
    try: users_col.update_one({"user_id": uid}, {"$set": {"banned": 1}}, upsert=True)
    except: pass


def unban_user(uid):
    try: users_col.update_one({"user_id": uid}, {"$set": {"banned": 0}}, upsert=True)
    except: pass


def all_users():
    return [u["user_id"] for u in users_col.find({"banned": 0}, {"user_id": 1})]


def all_groups():
    try:
        return [g["chat_id"] for g in groups_col.find({"enabled": 1}, {"chat_id": 1})]
    except: return []


def total_groups():
    try: return groups_col.count_documents({"enabled": 1})
    except: return 0


def user_stats(uid):
    u = get_or_create_user(uid)
    return u.get("total_referrals", 0), u.get("bonus_earned", 0), u.get("searches", 0)


def total_users():
    try: return users_col.count_documents({"banned": 0})
    except: return 0


def total_banned():
    try: return users_col.count_documents({"banned": 1})
    except: return 0


def total_searches():
    try:
        a = list(users_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$searches"}}}]))
        return a[0]["t"] if a else 0
    except: return 0


def total_aadhaar_searches():
    try:
        a = list(users_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$aadhaar_searches"}}}]))
        return a[0]["t"] if a and a[0]["t"] else 0
    except: return 0


def total_tg2num_searches():
    try:
        a = list(users_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$tg2num_searches"}}}]))
        return a[0]["t"] if a and a[0]["t"] else 0
    except: return 0


def total_credits_in_circulation():
    try:
        a = list(users_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$credits"}}}]))
        return a[0]["t"] if a else 0
    except: return 0


def new_users_24h():
    try:
        cutoff = now() - timedelta(hours=24)
        return users_col.count_documents({"joined_at": {"$gte": cutoff}})
    except: return 0


def active_users_24h():
    try:
        cutoff = now() - timedelta(hours=24)
        return users_col.count_documents({"last_seen": {"$gte": cutoff}})
    except: return 0


def upd_last_seen(uid):
    try: users_col.update_one({"user_id": uid}, {"$set": {"last_seen": now()}})
    except: pass


def export_csv():
    try:
        us = list(users_col.find({}, {
            "user_id": 1, "credits": 1, "searches": 1, "aadhaar_searches": 1,
            "tg2num_searches": 1,
            "total_referrals": 1, "banned": 1, "joined_at": 1
        }))
        o = io.StringIO(); w = csv.writer(o)
        w.writerow(["User ID", "Credits", "Searches", "Aadhaar", "TG2Num", "Referrals", "Banned", "Joined"])
        for u in us:
            w.writerow([
                u.get("user_id"), u.get("credits", 0), u.get("searches", 0),
                u.get("aadhaar_searches", 0), u.get("tg2num_searches", 0),
                u.get("total_referrals", 0), u.get("banned", 0),
                u.get("joined_at", "").strftime("%Y-%m-%d") if u.get("joined_at") else ""
            ])
        return o.getvalue()
    except: return None


# ================= PAYMENTS =================
def create_payment(uid, amount, credits, pay_mode, screenshot_id=None,
                   order_id=None, payment_link=None, gateway_raw=None):
    doc = {
        "user_id": uid, "amount": amount, "credits": credits,
        "pay_mode": pay_mode, "screenshot_id": screenshot_id,
        "order_id": order_id, "payment_link": payment_link,
        "status": "pending", "created_at": now(),
        "approved_at": None, "approved_by": None,
        "reject_reason": None, "gateway_response": gateway_raw
    }
    try:
        r = payments_col.insert_one(doc)
        return str(r.inserted_id)
    except: return None


def get_payment(pid):
    try: return payments_col.find_one({"_id": ObjectId(pid)})
    except: return None


def get_pending():
    try: return list(payments_col.find({"status": "pending"}).sort("created_at", 1))
    except: return []


def approve_atomic(pid, aid):
    try: oid = ObjectId(pid)
    except: return False, None
    try:
        r = payments_col.find_one_and_update(
            {"_id": oid, "status": "pending"},
            {"$set": {"status": "approved", "approved_at": now(), "approved_by": aid}},
            return_document=ReturnDocument.AFTER)
        if not r: return False, payments_col.find_one({"_id": oid})
        return True, r
    except: return False, None


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


def attach_ss(pid, fid):
    try: payments_col.update_one({"_id": ObjectId(pid)}, {"$set": {"screenshot_id": fid}})
    except: pass


def pay_stats():
    try:
        p = payments_col.count_documents({"status": "pending"})
        a = payments_col.count_documents({"status": "approved"})
        r = payments_col.count_documents({"status": "rejected"})
        agg = list(payments_col.aggregate([
            {"$match": {"status": "approved"}},
            {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
        rev = agg[0]["t"] if agg else 0
        today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
        agg2 = list(payments_col.aggregate([
            {"$match": {"status": "approved", "approved_at": {"$gte": today_start}}},
            {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
        today_rev = agg2[0]["t"] if agg2 else 0
        return p, a, r, rev, today_rev
    except: return 0, 0, 0, 0, 0


# ================= PROMO =================
def all_promos():
    try: return list(promo_col.find().sort("_id", -1))
    except: return []


def gen_promo():
    c = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = ''.join(random.choices(c, k=12))
        try:
            if not promo_col.find_one({"code": code}): return code
        except: continue
    return ''.join(random.choices(c, k=12))


def save_promo(code, rc, mu, aid):
    try:
        promo_col.insert_one({
            "code": code, "reward_credits": rc, "max_users": mu,
            "used_count": 0, "used_by": [], "generated_by": aid,
            "created_at": datetime.now().strftime('%Y-%m-%d'), "active": 1})
    except: pass


def redeem_promo(code, uid):
    try:
        d = promo_col.find_one({"code": code})
        if not d: return None
        if d.get("active", 1) == 0: return None
        if uid in d.get("used_by", []): return -1
        if d.get("used_count", 0) >= d.get("max_users", 0): return None
        r = promo_col.find_one_and_update(
            {"code": code, "active": 1,
             "used_count": {"$lt": d.get("max_users", 0)},
             "used_by": {"$ne": uid}},
            {"$inc": {"used_count": 1}, "$push": {"used_by": uid}},
            return_document=ReturnDocument.AFTER)
        if not r: return -1
        reward = d.get("reward_credits", 0)
        add_credits(uid, reward)
        return reward
    except: return None


# ================= CHANNELS =================
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


# ================= AUTO UPI =================
def is_auto_upi_available():
    if int(get_setting("gateway_enabled", 0)) != 1: return False
    if not get_setting("gateway_create_url", ""): return False
    if not get_setting("gateway_api_key", ""): return False
    return True


def create_gateway_order(amount, uid):
    url = get_setting("gateway_create_url", "") or FAM_CREATE_URL
    key = get_setting("gateway_api_key", "")
    redirect = get_setting("gateway_redirect_url", "") or FAM_REDIRECT_URL
    if not url or not key: return False, None, None, None, None, "Not configured"
    try:
        headers = {"X-Api-Key": key, "Content-Type": "application/json"}
        payload = {"amount": float(amount), "redirect_url": redirect,
                   "customer_name": f"user_{uid}", "api_key": key}
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code not in (200, 201):
            return False, None, None, None, None, f"HTTP {r.status_code}"
        try: raw = r.json()
        except: return False, None, None, None, None, "Bad JSON"
        if raw.get("status") != "success":
            return False, None, None, None, None, f"Status: {raw.get('status')}"
        data = raw.get("data") or {}
        oid = data.get("order_id"); link = data.get("checkout_url")
        qr = data.get("qr_url"); upi = data.get("upi_id")
        if not oid: return False, None, None, None, None, "No order_id"
        return True, str(oid), link, qr, upi, raw
    except requests.exceptions.Timeout:
        return False, None, None, None, None, "Timeout"
    except Exception as e:
        return False, None, None, None, None, f"Error: {e}"


def verify_gateway_order(order_id):
    try:
        cs = get_setting("gateway_checkout_status_url", "") or FAM_CHECKOUT_STATUS_URL
        r = requests.get(f"{cs}?order_id={order_id}", timeout=15)
        if r.status_code == 200:
            try:
                raw = r.json()
                status = str(raw.get("status", "")).lower()
                if status == "success":
                    return True, "success", {"utr": raw.get("utr"),
                        "sender_name": raw.get("sender_name"),
                        "paid_at": raw.get("paid_at"), "amount": raw.get("amount"), "raw": raw}
                elif status in ("pending", "expired"):
                    return False, status, raw if isinstance(raw, dict) else None
            except: pass
    except: pass
    key = get_setting("gateway_api_key", "")
    v_url = get_setting("gateway_verify_url", "") or FAM_VERIFY_URL
    if not key or not v_url: return False, "config_error", None
    try:
        headers = {"X-Api-Key": key}
        params = {"api_key": key, "order_id": order_id}
        r = requests.get(v_url, headers=headers, params=params, timeout=15)
        if r.status_code == 404: return False, "not_found", None
        if r.status_code == 408: return False, "expired", None
        if r.status_code != 200: return False, f"http_{r.status_code}", None
        try: raw = r.json()
        except: return False, "bad_json", None
        status = str(raw.get("status", "")).lower()
        if status == "success":
            return True, "success", {"utr": raw.get("utr"),
                "sender_name": raw.get("sender_name"),
                "paid_at": raw.get("paid_at"), "amount": raw.get("amount"), "raw": raw}
        elif status in ("pending", "expired"):
            return False, status, raw if isinstance(raw, dict) else None
        else:
            return False, status or "unknown", raw if isinstance(raw, dict) else None
    except requests.exceptions.Timeout: return False, "timeout", None
    except: return False, "err", None


def send_qr_image(cid, qr_url, caption, kb, reply_to=None):
    try:
        r = requests.get(qr_url, timeout=15)
        if r.status_code == 200 and r.content and len(r.content) > 200:
            kw = {"caption": caption, "parse_mode": "HTML"}
            if kb: kw["reply_markup"] = kb
            if reply_to: kw["reply_to_message_id"] = reply_to
            return bot.send_photo(cid, r.content, **kw)
    except: pass
    return None


# ================= BOT INIT =================
bot = telebot.TeleBot(BOT_TOKEN)
try: bot.remove_webhook()
except: pass


# ================= SAFE CALLBACK ANSWER =================
_ack_lock = threading.Lock()
_answered_cbs = set()


def safe_answer(call, text=None, show_alert=False):
    cid = call.id
    with _ack_lock:
        if cid in _answered_cbs: return False
        _answered_cbs.add(cid)
        if len(_answered_cbs) > 20000:
            try:
                for x in list(_answered_cbs)[:10000]: _answered_cbs.discard(x)
            except: _answered_cbs.clear()
    try:
        bot.answer_callback_query(cid, text=text, show_alert=show_alert)
        return True
    except: return False


# ================= ANIMATION =================
def send_typing(cid):
    try: bot.send_chat_action(cid, 'typing')
    except: pass


def typing_loop(cid, stop_event, interval=4.0):
    while not stop_event.is_set():
        send_typing(cid)
        w = 0
        while w < interval and not stop_event.is_set():
            time.sleep(0.2); w += 0.2


class AnimMsg:
    def __init__(self, cid, *frames, interval=0.18, reply_to=None):
        self.cid = cid; self.frames = list(frames); self.interval = interval
        self.mid = None; self._stop = threading.Event(); self._t = None
        self._reply = reply_to; self._deleted = False
        self._edit_lock = threading.Lock()

    def start(self):
        try:
            kw = {"parse_mode": "HTML"}
            if self._reply: kw["reply_to_message_id"] = self._reply
            m = bot.send_message(self.cid, self.frames[0], **kw)
            self.mid = m.message_id
            self._t = threading.Thread(target=self._run, daemon=True)
            self._t.start()
            return True
        except: return False

    def _run(self):
        i = 1; last_text = self.frames[0] if self.frames else ""
        while not self._stop.is_set():
            if self._deleted or self.mid is None: return
            text = self.frames[i % len(self.frames)]
            if text != last_text:
                try:
                    with self._edit_lock:
                        if self._deleted or self.mid is None: return
                        bot.edit_message_text(text, self.cid, self.mid, parse_mode="HTML")
                    last_text = text
                except Exception as e:
                    err = str(e).lower()
                    if "not modified" not in err and "message to edit" not in err:
                        w = 0
                        while w < 0.5 and not self._stop.is_set():
                            time.sleep(0.04); w += 0.04
            i += 1
            w = 0
            while w < self.interval:
                if self._stop.is_set(): return
                time.sleep(0.04); w += 0.04

    def stop(self):
        self._stop.set()
        if self._t:
            try: self._t.join(timeout=2)
            except: pass

    def edit(self, text, mark=None):
        with self._edit_lock:
            if self._deleted or self.mid is None:
                try: bot.send_message(self.cid, text, parse_mode="HTML", reply_markup=mark)
                except: pass
                return
            try:
                bot.edit_message_text(text, self.cid, self.mid, parse_mode="HTML", reply_markup=mark)
            except Exception as e:
                err = str(e).lower()
                if "not modified" in err:
                    try: bot.edit_message_reply_markup(self.cid, self.mid, reply_markup=mark)
                    except: pass
                    return
                try:
                    m = bot.send_message(self.cid, text, parse_mode="HTML", reply_markup=mark)
                    self.mid = m.message_id
                except: pass

    def delete(self):
        self.stop(); self._deleted = True
        if self.mid is None: return
        try: bot.delete_message(self.cid, self.mid)
        except: pass


def progress_bar(pct, width=12):
    pct = max(0, min(100, int(pct)))
    filled = int(width * pct / 100)
    return "▰" * filled + "▱" * (width - filled) + f" {pct}%"


def build_search_frames(prefix="🔎 <b>Searching</b>"):
    """Smoother animation — 4% increments for buttery feel."""
    frames = []
    for i, pct in enumerate(range(0, 100, 4)):
        sp = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        frames.append(f"{sp} {prefix}\n<code>{progress_bar(pct)}</code>")
    frames.append(f"✅ {prefix}\n<code>{progress_bar(100)}</code>")
    return frames


# ================= POLLER =================
def poll_order_async(uid, cid, order_id, amount, credits, msg_id=None):
    for i in range(75):
        time.sleep(4)
        try:
            ok, status, info = verify_gateway_order(order_id)
            if ok:
                _credit_on_success(uid, cid, order_id, amount, credits, info, msg_id)
                return
            if status == "expired":
                _mark_expired(order_id)
                try:
                    bot.send_message(cid, f"⏰ <b>Session Expired</b>\nOrder: <code>{order_id}</code>",
                                     parse_mode='HTML')
                except: pass
                return
        except: continue
    _mark_expired(order_id)
    try:
        bot.send_message(cid, f"⏰ <b>Timeout</b>\nOrder: <code>{order_id}</code>", parse_mode='HTML')
    except: pass


def _mark_expired(order_id):
    try:
        payments_col.update_one({"order_id": order_id, "status": "pending"},
            {"$set": {"status": "expired", "expired_at": now()}})
    except: pass


def _credit_on_success(uid, cid, order_id, amount, credits, info, msg_id):
    p = payments_col.find_one({"order_id": order_id, "user_id": uid})
    if not p: return False
    updated = payments_col.find_one_and_update(
        {"_id": p["_id"], "status": "pending"},
        {"$set": {"status": "approved", "approved_at": now(),
                  "utr": (info.get("utr") if info else None) or f"FG_{order_id}",
                  "gateway_response": (info.get("raw") if info else None),
                  "auto_verified": True, "verified_at": now()}},
        return_document=ReturnDocument.AFTER)
    if not updated: return False
    add_credits(uid, credits)
    balance = get_credits(uid)
    txt = (f"✅ <b>Payment Verified!</b>\n\n💰 ₹{amount}\n💎 +{credits} credits\n"
           f"📊 Balance: {balance}\n🆔 <code>{order_id}</code>")
    if info and info.get("utr"): txt += f"\n🧾 UTR: <code>{info['utr']}</code>"
    edited = False
    if msg_id:
        try:
            bot.edit_message_caption(chat_id=cid, message_id=msg_id, caption=txt, parse_mode='HTML')
            edited = True
        except: pass
    if not edited:
        try: bot.send_message(cid, txt, parse_mode='HTML')
        except: pass
    try:
        bot.send_message(ADMIN_ID,
            f"⚡ <b>Auto-credited</b>\nUser: <code>{uid}</code>\n₹{amount} → {credits}cr",
            parse_mode='HTML')
    except: pass
    return True


# ================= BROADCAST =================
bcast_q = queue.Queue()


def _broadcast_all(msg, kw, admin_id):
    users = all_users()
    groups = all_groups()
    channels = [c["channel_id"] for c in all_channels()]

    ok_u = fail_u = ok_g = fail_g = ok_c = fail_c = 0
    pin_g = pin_c = 0

    for u in users:
        try:
            bot.send_message(u, msg, **kw)
            ok_u += 1
            time.sleep(0.04)
        except: fail_u += 1

    for g in groups:
        try:
            m = bot.send_message(g, msg, **kw)
            ok_g += 1
            try:
                bot.pin_chat_message(g, m.message_id, disable_notification=True)
                pin_g += 1
            except: pass
            time.sleep(0.04)
        except: fail_g += 1

    for c in channels:
        try:
            m = bot.send_message(c, msg, **kw)
            ok_c += 1
            try:
                bot.pin_chat_message(c, m.message_id, disable_notification=True)
                pin_c += 1
            except: pass
            time.sleep(0.04)
        except: fail_c += 1

    logger.info(f"Bcast: U={ok_u}/{len(users)} G={ok_g}/{len(groups)} C={ok_c}/{len(channels)}")
    if admin_id:
        try:
            bot.send_message(admin_id,
                f"📢 <b>Broadcast done</b>\n\n"
                f"👤 Users: ✅{ok_u} | ❌{fail_u}\n"
                f"💬 Groups: ✅{ok_g} | ❌{fail_g} (📌 {pin_g})\n"
                f"📢 Channels: ✅{ok_c} | ❌{fail_c} (📌 {pin_c})",
                parse_mode='HTML')
        except: pass


def bcast_worker():
    while True:
        try: task = bcast_q.get()
        except: continue
        if task is None: break
        try:
            msg, kw, admin_id = task
            _broadcast_all(msg, kw, admin_id)
        except Exception as e:
            logger.error(f"bcast_worker: {e}")
        finally: bcast_q.task_done()


threading.Thread(target=bcast_worker, daemon=True).start()


# ================= RATE LIMIT =================
_rl_lock = threading.Lock()
_rl_map = {}
RATE_LIMIT_SEC = 1.2
_RL_MAX = 50000


def rate_ok(uid):
    if uid == ADMIN_ID: return True
    with _rl_lock:
        if len(_rl_map) > _RL_MAX:
            try:
                for k in list(_rl_map.keys())[: _RL_MAX // 2]: _rl_map.pop(k, None)
            except: _rl_map.clear()
        last = _rl_map.get(uid, 0)
        if time.time() - last < RATE_LIMIT_SEC: return False
        _rl_map[uid] = time.time()
        return True


# ================= STATES =================
states = {}
def get_state(uid): return states.get(uid, {})
def set_state(uid, st): states[uid] = st
def clear_state(uid): states.pop(uid, None)


# ================= UTILS =================
def extract_num(text):
    if not text or not isinstance(text, str): return None
    m = re.search(r'(?<!\d)(?:\+?91[\-\s]?|0)?([6-9]\d{9})(?!\d)', text)
    if m: return m.group(1)
    digits = re.sub(r'\D', '', text, flags=re.UNICODE)
    if not digits: return None
    if   len(digits) == 14 and digits.startswith('0091'): digits = digits[4:]
    elif len(digits) == 13 and digits.startswith('091'):  digits = digits[3:]
    elif len(digits) == 12 and digits.startswith('91'):   digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):    digits = digits[1:]
    if len(digits) == 10 and digits[0] in '6789': return digits
    return None


def extract_aadhaar(text):
    if not text or not isinstance(text, str): return None
    m = re.search(r'(?<!\d)([2-9]\d{11})(?!\d)', text)
    if m: return m.group(1)
    digits = re.sub(r'\D', '', text, flags=re.UNICODE)
    if len(digits) == 12 and digits[0] in '23456789': return digits
    return None


def extract_tg_query(text):
    """
    Accepts: @username, username, 123456789 (userid), t.me/username, https://t.me/username
    Returns cleaned query string, or None if invalid.
    """
    if not text or not isinstance(text, str): return None
    t = text.strip()
    if not t: return None

    # t.me / telegram.me link → extract username/userid
    m = re.match(r'^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]{3,32})/?$', t, flags=re.I)
    if m: return m.group(1)

    # pure userid (numeric, 5-15 digits)
    if re.match(r'^\d{5,15}$', t): return t

    # @username or username (allow numbers, letters, underscores)
    t_clean = t[1:] if t.startswith('@') else t
    if re.match(r'^[A-Za-z0-9_]{4,32}$', t_clean): return t_clean

    return None


def fmt_json(phone, data):
    r = data.get('result', [])
    o = {"phone": phone,
         "summary": {"total_records": len(r),
                     "generated_at": datetime.now().strftime('%d-%b-%Y %I:%M %p')},
         "records": r}
    return f"<pre>{html_module.escape(json.dumps(o, indent=2, ensure_ascii=False))}</pre>"


def quote(t): return f"&gt; {t}\n\n"


# ================= WELCOME =================
def welcome_txt(uid, uname):
    u = get_or_create_user(uid)
    cr = u.get("credits", 0)
    if uid == ADMIN_ID:
        status = "👑 ᴀᴅᴍɪɴ · ♾️ ᴜɴʟɪᴍɪᴛᴇᴅ"
    elif u.get("banned"):
        status = "🚫 ʙᴀɴɴᴇᴅ"
    else:
        status = f"💎 {cr} ᴄʀᴇᴅɪᴛs"

    custom = get_setting("welcome_msg", "")
    if custom:
        return (custom.replace("{name}", uname).replace("{status}", status)
                       .replace("{credits}", str(cr)))

    cost = get_setting("search_cost", 5) or 5
    a_cost = get_setting("aadhaar_cost", DEFAULT_AADHAAR_COST) or DEFAULT_AADHAAR_COST
    t_cost = get_setting("tg2num_cost", DEFAULT_TG2NUM_COST) or DEFAULT_TG2NUM_COST

    return (
        f"╔═══════════════════════╗\n"
        f"   🔍 <b>ɪɴᴅɪᴀɴ ᴏsɪɴᴛ ʙᴏᴛ</b> 🔍\n"
        f"╚═══════════════════════╝\n\n"
        f"ʜᴇʟʟᴏ <b>{uname}</b> 👋\n\n"
        f"🎯 <b>ᴡʜᴀᴛ ɪ ᴄᴀɴ ᴅᴏ:</b>\n"
        f"  📞 <b>Number Lookup</b> → Name, Address, Circle\n"
        f"  🆔 <b>Aadhaar Lookup</b> → Full details, Mobile\n"
        f"  🔒 <b>Username To Info</b> → TG ID + Number\n"
        f"  🔗 <b>Group Support</b> → Add me & search in groups\n\n"
        f"⚡ <b>ǫᴜɪᴄᴋ sᴛᴀʀᴛ:</b>\n"
        f"  • Send <code>10-digit number</code> → search\n"
        f"  • Send <code>12-digit Aadhaar</code> → lookup\n"
        f"  • Use <code>🔒 Username To Info</code> menu\n"
        f"  • Type <code>/buy</code> for credits\n\n"
        f"💰 <b>ᴘʀɪᴄɪɴɢ:</b>\n"
        f"  🔎 Number: {cost} credits\n"
        f"  🆔 Aadhaar: {a_cost} credits\n"
        f"  🔒 Username: {t_cost} credits\n\n"
        f"📊 <b>ʏᴏᴜʀ sᴛᴀᴛᴜs:</b>\n  {status}\n\n"
        f"👑 <b>Owner:</b> {ADMIN_USERNAME}\n"
        f"🚀 <b>Bot:</b> {BOT_USERNAME}"
    )


def no_data_msg(uid):
    cr = get_credits(uid) if uid != ADMIN_ID else "♾️"
    return (f"😔 ɴᴏ ᴅᴀᴛᴀ ғᴏᴜɴᴅ\n\nᴛʜɪs ɴᴜᴍʙᴇʀ ɪs ɴᴏᴛ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ.\n\n"
            f"💎 ᴄʀᴇᴅɪᴛs: {cr}")


# ================= KEYBOARDS =================
def main_kb(uid):
    ia = (uid == ADMIN_ID)
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("📞 Number To Info"), KeyboardButton("🆔 Aadhaar Info"))
    kb.row(KeyboardButton("🔒 Username To Info"), KeyboardButton("🛒 Buy Credits"))
    kb.row(KeyboardButton("💰 Refer & Earn"), KeyboardButton("🎟 Redeem Code"))
    kb.row(KeyboardButton("👤 My Profile"), KeyboardButton("➕ Add to Group"))
    kb.row(KeyboardButton("❓ Help"), KeyboardButton("👑 Admin Panel" if ia else "ℹ️ About"))
    return kb


def admin_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("📊 Dashboard"), KeyboardButton("👥 Users"))
    kb.row(KeyboardButton("💰 Payments"), KeyboardButton("📦 Promo"))
    kb.row(KeyboardButton("📢 Broadcast"), KeyboardButton("📈 Analytics"))
    kb.row(KeyboardButton("⚙️ Force Join"), KeyboardButton("💬 Groups"))
    kb.row(KeyboardButton("🔧 Settings"), KeyboardButton("💎 Manage Credits"))
    kb.row(KeyboardButton("📤 Export Data"), KeyboardButton("🛠 Maintenance"))
    kb.row(KeyboardButton("👑 Bot Info"), KeyboardButton("🔙 Back to Menu"))
    return kb


def users_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("🚫 Ban", callback_data="ap_ban"),
           InlineKeyboardButton("✅ Unban", callback_data="ap_unban"))
    kb.row(InlineKeyboardButton("🔍 User Info", callback_data="ap_userinfo"),
           InlineKeyboardButton("📋 List", callback_data="ap_listusers"))
    kb.row(InlineKeyboardButton("🚫 Banned", callback_data="ap_banned"),
           InlineKeyboardButton("🏆 Top", callback_data="ap_topsearch"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def payments_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("⏳ Pending", callback_data="ap_pending"),
           InlineKeyboardButton("📜 Recent", callback_data="ap_recentpay"))
    kb.row(InlineKeyboardButton("💳 Settings", callback_data="ap_payset"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def promo_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("🎁 Generate", callback_data="ap_genpromo"),
           InlineKeyboardButton("📋 List", callback_data="ap_listpromo"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def broadcast_panel_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📢 All (Users+Groups+Channels)", callback_data="ap_bcastall"))
    kb.row(InlineKeyboardButton("👤 Users Only", callback_data="ap_bcastusers"))
    kb.row(InlineKeyboardButton("💬 Groups Only", callback_data="ap_bcastgroups"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def analytics_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("🏆 Searchers", callback_data="ap_topsearch"),
           InlineKeyboardButton("👥 Referrers", callback_data="ap_topref"))
    kb.row(InlineKeyboardButton("🆔 Aadhaar", callback_data="ap_topaadhaar"),
           InlineKeyboardButton("💰 Buyers", callback_data="ap_topbuyers"))
    kb.row(InlineKeyboardButton("📅 Daily", callback_data="ap_daily"),
           InlineKeyboardButton("📊 Full", callback_data="ap_fullreport"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def groups_panel_kb():
    add_link = f"https://t.me/{BOT_USERNAME_CLEAN}?startgroup=true&admin={ADD_GROUP_PERMS}"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.row(InlineKeyboardButton("📋 List Groups", callback_data="ap_listgroups"))
    kb.row(InlineKeyboardButton("➕ Add Bot", url=add_link))
    kb.row(InlineKeyboardButton("📢 Broadcast Groups", callback_data="ap_bcastgroups"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def settings_panel_kb():
    rate = get_setting("credits_per_rupee", 1) or 1
    cost = get_setting("search_cost", 5) or 5
    acost = get_setting("aadhaar_cost", DEFAULT_AADHAAR_COST) or DEFAULT_AADHAAR_COST
    tcost = get_setting("tg2num_cost", DEFAULT_TG2NUM_COST) or DEFAULT_TG2NUM_COST
    wb = get_setting("welcome_bonus", DEFAULT_WELCOME_BONUS) or DEFAULT_WELCOME_BONUS
    num_url = get_setting("number_api_url", "") or "(not set)"
    num_key = "✅" if get_setting("number_api_key", "") else "❌"
    aad_url = get_setting("aadhaar_api_url", "") or "(not set)"
    aad_key = "✅" if get_setting("aadhaar_api_key", "") else "❌"
    tg_url = get_setting("tg2num_url", "") or "(not set)"
    tg_key = "✅" if get_setting("tg2num_key", "") else "❌"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"💱 Rate: {rate}₹/credit", callback_data="ps_rate"))
    kb.add(InlineKeyboardButton(f"🔎 Number: {cost}cr", callback_data="ps_cost"))
    kb.add(InlineKeyboardButton(f"🆔 Aadhaar: {acost}cr", callback_data="ps_aadhaar"))
    kb.add(InlineKeyboardButton(f"🔒 Username: {tcost}cr", callback_data="ps_tg2num_cost"))
    kb.add(InlineKeyboardButton(f"🎁 Welcome Bonus: {wb}cr", callback_data="ps_welcome_bonus"))
    kb.add(InlineKeyboardButton("👋 Welcome Msg", callback_data="ps_welcome"))
    kb.add(InlineKeyboardButton("🎁 Referral Bonus", callback_data="ps_referral"))
    kb.add(InlineKeyboardButton("💎 Daily Free", callback_data="ps_daily"))
    kb.add(InlineKeyboardButton("━━━ 🔎 NUMBER API ━━━", callback_data="ps_noop"))
    kb.add(InlineKeyboardButton(f"🔗 URL: {num_url[:28]}", callback_data="ps_num_url"))
    kb.add(InlineKeyboardButton(f"🔑 Key: {num_key}", callback_data="ps_num_key"))
    kb.add(InlineKeyboardButton("━━━ 🆔 AADHAAR API ━━━", callback_data="ps_noop"))
    kb.add(InlineKeyboardButton(f"🔗 URL: {aad_url[:28]}", callback_data="ps_aad_url"))
    kb.add(InlineKeyboardButton(f"🔑 Key: {aad_key}", callback_data="ps_aad_key"))
    kb.add(InlineKeyboardButton("━━━ 🔒 USERNAME (TG2NUM) ━━━", callback_data="ps_noop"))
    kb.add(InlineKeyboardButton(f"🔗 URL: {tg_url[:28]}", callback_data="ps_tg2num_url"))
    kb.add(InlineKeyboardButton(f"🔑 Key: {tg_key}", callback_data="ps_tg2num_key"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def credits_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("➕ Add", callback_data="ap_addcred"),
           InlineKeyboardButton("➖ Remove", callback_data="ap_remcred"))
    kb.row(InlineKeyboardButton("💎 Set", callback_data="ap_setcred"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def force_kb():
    mgr = globals().get('manager')
    en = bool(mgr and mgr.global_enabled)
    st = "✅ ON" if en else "❌ OFF"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"🔄 Toggle ({st})", callback_data="fj_toggle"))
    kb.add(InlineKeyboardButton("➕ Add", callback_data="fj_add"))
    kb.add(InlineKeyboardButton("➖ Remove", callback_data="fj_remove"))
    kb.add(InlineKeyboardButton("📋 List", callback_data="fj_list"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def pay_settings_kb():
    rate = get_setting("credits_per_rupee", 1) or 1
    cost = get_setting("search_cost", 5) or 5
    acost = get_setting("aadhaar_cost", DEFAULT_AADHAAR_COST) or DEFAULT_AADHAAR_COST
    mid = get_setting("upi_manual_id", "not set") or "not set"
    mon = int(get_setting("upi_manual_enabled", 1))
    gw = int(get_setting("gateway_enabled", 0))
    avail = is_auto_upi_available()
    gws = "✅ Ready" if avail else ("⚠️ Setup" if gw else "🔴 OFF")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"💱 Rate: {rate}₹/credit", callback_data="ps_rate"))
    kb.add(InlineKeyboardButton(f"🔎 {cost}cr | 🆔 {acost}cr", callback_data="ps_cost"))
    kb.add(InlineKeyboardButton("━━━ ⚡ AUTO UPI ━━━", callback_data="ps_noop"))
    kb.add(InlineKeyboardButton(f"🔌 Gateway: {gws}", callback_data="ps_gw_toggle"))
    kb.add(InlineKeyboardButton(f"🔑 Key: {'✅' if get_setting('gateway_api_key','') else '❌'}", callback_data="ps_key"))
    kb.add(InlineKeyboardButton("━━━ 📋 MANUAL ━━━", callback_data="ps_noop"))
    kb.add(InlineKeyboardButton(f"{'🟢' if mon else '🔴'} UPI: {mid[:22]}", callback_data="ps_manual_id"))
    kb.add(InlineKeyboardButton("🖼 QR", callback_data="ps_manual_qr"))
    kb.add(InlineKeyboardButton(f"{'🔴 OFF' if mon else '🟢 ON'} Manual", callback_data="ps_manual_tog"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel_home"))
    return kb


def buy_kb():
    rate = get_setting("credits_per_rupee", 1) or 1
    cost = get_setting("search_cost", 5) or 5
    text = (f"🛒 <b>BUY CREDITS</b>\n\n"
            f"💱 Rate: <b>₹1 = {rate} credit</b>\n"
            f"🔎 1 Search = <b>{cost} credits</b>\n\n"
            f"📌 Kitne rupaye ka credit chahiye?")
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


def no_credits_msg(uid):
    cost = get_setting("search_cost", 5) or 5
    cr = get_credits(uid)
    return (f"⚠️ ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴄʀᴇᴅɪᴛs!\n\n"
            f"🔎 ᴘᴇʀ sᴇᴀʀᴄʜ: {cost}\n💎 ʏᴏᴜʀs: {cr}\n\n"
            f"1. Refer → +10\n2. Buy Credits")


def no_aadhaar_credits_msg(uid, cost):
    cr = get_credits(uid)
    return (f"⚠️ <b>Not enough credits!</b>\n\n"
            f"🆔 Per Aadhaar: {cost}\n💎 Yours: {cr}")


def no_tg2num_credits_msg(uid, cost):
    cr = get_credits(uid)
    return (f"⚠️ <b>Not enough credits!</b>\n\n"
            f"🔒 Per Search: {cost}\n💎 Yours: {cr}")


# ================= FORCE JOIN =================
class FJManager:
    def __init__(self, bot):
        self.bot = bot; self.pending = {}; self.msg = {}
        self.channels = []; self.global_enabled = False
        self._load()

    def _load(self):
        try: bi = self.bot.get_me()
        except:
            self.channels = []; self.global_enabled = False; return
        valid = []
        for c in all_channels():
            try:
                m = self.bot.get_chat_member(c["channel_id"], bi.id)
                if m.status in ('administrator', 'creator'):
                    valid.append((c["channel_id"], c["channel_link"]))
            except: pass
        self.channels = valid
        self.global_enabled = str(get_setting("force_enabled", "1")) == "1"

    def reload(self): self._load()
    def is_on(self): return self.global_enabled and bool(self.channels)

    def check(self, uid):
        if not self.is_on(): return None
        missing = []
        for cid, link in self.channels:
            try:
                m = self.bot.get_chat_member(cid, uid)
                if m.status not in ('member', 'administrator', 'creator'):
                    missing.append((cid, link))
            except: continue
        return missing if missing else None

    def ensure(self, uid, cid, pending=None):
        if self.check(uid) is None: return True
        if pending:
            ex = self.pending.get(uid)
            if not ex or ex.get('type') in ('welcome', 'unknown'):
                self.pending[uid] = pending
        old = self.msg.pop(uid, None)
        if old:
            try: self.bot.delete_message(cid, old)
            except: pass
        missing = self.check(uid)
        if not missing: return True
        kb = InlineKeyboardMarkup(row_width=1)
        for i, (ch, lk) in enumerate(missing[:100]):
            kb.add(InlineKeyboardButton(f"📢 Channel {i+1}", url=lk))
        kb.add(InlineKeyboardButton("✅ Verify", callback_data="force_verify"))
        try:
            s = self.bot.send_message(cid,
                "⚠️ Pehle channels join karo, phir <b>Verify</b> dabao.",
                parse_mode='HTML', reply_markup=kb)
            self.msg[uid] = s.message_id
        except: pass
        return False

    def verify_cb(self, call):
        uid = call.from_user.id
        cid = call.message.chat.id
        if self.check(uid) is None:
            safe_answer(call, "✅ Verified!")
            mid = self.msg.pop(uid, None)
            if mid:
                try: self.bot.delete_message(cid, mid)
                except: pass
            p = self.pending.pop(uid, None)
            if p: self._exec(uid, cid, p, call)
            else:
                uname = call.from_user.username or "user"
                self.bot.send_message(cid, welcome_txt(uid, uname),
                                      parse_mode='HTML', reply_markup=main_kb(uid))
        else:
            safe_answer(call, "❌ Not joined!", show_alert=True)
            self.msg.pop(uid, None); self.ensure(uid, cid)

    def _exec(self, uid, cid, p, call):
        t, d = p.get('type'), p.get('data')
        if t == 'number_search': process_search(uid, cid, d, None)
        elif t == 'aadhaar_search': process_aadhaar(uid, cid, d, None)
        elif t == 'tg2num_search': process_tg2num(uid, cid, d, None)
        elif t == 'menu_button': process_menu(uid, cid, d, None)
        elif t == 'promo_redeem': process_promo(uid, cid, d, None)
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
        if not link: link = f"https://t.me/joinchat/{cid}"
        try:
            bi = self.bot.get_me()
            m = self.bot.get_chat_member(cid, bi.id)
            if m.status not in ('administrator', 'creator'):
                return False, f"❌ Bot not admin ({m.status}). Make bot admin first."
        except Exception as e:
            return False, f"❌ {e}"
        if not add_channel_db(cid, link): return False, "⚠️ Already exists"
        self.reload()
        return True, "✅ Added"

    def rm(self, cid):
        if remove_channel_db(cid):
            self.reload(); return True, "Removed"
        return False, "Not found"


manager = None


_BLOCKING_STATES = {
    # User flows
    'aadhaar_input', 'tg2num_input', 'custom_amt', 'waiting_ss', 'manual_ss',
    'waiting_payment', 'redeem_code',
    # Admin text inputs
    'promo1', 'promo2', 'broadcast', 'ban', 'unban',
    'ps_rate', 'ps_cost', 'ps_aadhaar', 'ps_tg2num_cost',
    'ps_welcome_bonus', 'ps_welcome',
    'ps_referral', 'ps_daily', 'ps_key', 'ps_manual_id', 'ps_manual_qr',
    'ps_num_url', 'ps_num_key', 'ps_aad_url', 'ps_aad_key',
    'ps_tg2num_url', 'ps_tg2num_key',
    'fj_add', 'fj_add_link',
    'ap_addcred_input', 'ap_remcred_input', 'ap_setcred_input',
    'ap_userinfo_input', 'ap_bcast_input', 'ap_genpromo1', 'ap_genpromo2',
}

_ADMIN_INPUT_STATES = _BLOCKING_STATES
_SKIP_PROMO_DETECT = _BLOCKING_STATES


# ================= SEARCH: NUMBER =================
def process_search(uid, cid, phone, reply_to=None):
    if int(get_setting("maintenance_mode", 0)) == 1 and uid != ADMIN_ID:
        bot.send_message(cid, "🔧 Maintenance.", reply_to_message_id=reply_to); return
    if is_banned(uid):
        bot.send_message(cid, "🚫 Banned!", reply_to_message_id=reply_to); return
    cost = int(get_setting("search_cost", 5))
    if uid != ADMIN_ID and get_credits(uid) < cost:
        bot.send_message(cid, no_credits_msg(uid), reply_to_message_id=reply_to); return

    api_url, api_key = get_num_api()
    if not api_url:
        bot.send_message(cid, "❌ Number API not configured.", reply_to_message_id=reply_to); return

    send_typing(cid)
    frames = build_search_frames("🔎 <b>Searching</b>")
    am = AnimMsg(cid, *frames, interval=0.18, reply_to=reply_to)
    am.start()
    stop_typing = threading.Event()
    typing_thread = threading.Thread(target=typing_loop, args=(cid, stop_typing), daemon=True)
    typing_thread.start()

    try:
        url = f"{api_url}?number={phone}&key={api_key}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            am.stop(); am.edit(no_data_msg(uid)); return
        try: data = r.json()
        except: am.stop(); am.edit(no_data_msg(uid)); return
        if not (data.get("success") and data.get("found") and data.get("result")):
            am.stop(); am.edit(no_data_msg(uid)); return
        if uid != ADMIN_ID:
            deduct_credits(uid, cost); remaining = get_credits(uid)
        else: remaining = "♾️"
        incr_searches(uid)
        msg = fmt_json(phone, data)
        if uid != ADMIN_ID: msg += f"\n\n💎 ᴄʀᴇᴅɪᴛs ʟᴇғᴛ: {remaining}"
        am.stop(); am.delete()
        if len(msg) > 4000:
            try:
                buf = io.BytesIO(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))
                buf.name = f"info_{phone}.json"
                bot.send_document(cid, buf, caption=f"📄 Info {phone}", reply_to_message_id=reply_to)
            except:
                try: bot.send_message(cid, msg[:4000], parse_mode='HTML', reply_to_message_id=reply_to)
                except: pass
        else:
            bot.send_message(cid, msg, parse_mode='HTML', reply_to_message_id=reply_to)
    except requests.exceptions.Timeout:
        am.stop(); am.edit("⚠️ API timeout.")
    except requests.exceptions.ConnectionError:
        am.stop(); am.edit("⚠️ API down.")
    except Exception as e:
        logger.error(f"Search: {e}")
        am.stop(); am.edit("⚠️ Error.")
    finally:
        stop_typing.set()
        try: typing_thread.join(timeout=1)
        except: pass


# ================= SEARCH: AADHAAR =================
def process_aadhaar(uid, cid, aadhaar, reply_to=None):
    if int(get_setting("maintenance_mode", 0)) == 1 and uid != ADMIN_ID:
        bot.send_message(cid, "🔧 Maintenance.", reply_to_message_id=reply_to); return
    if is_banned(uid):
        bot.send_message(cid, "🚫 Banned!", reply_to_message_id=reply_to); return
    cost = int(get_setting("aadhaar_cost", DEFAULT_AADHAAR_COST)) or DEFAULT_AADHAAR_COST
    if uid != ADMIN_ID and get_credits(uid) < cost:
        bot.send_message(cid, no_aadhaar_credits_msg(uid, cost), reply_to_message_id=reply_to); return

    a_url, a_key = get_aadhaar_api()
    if not a_key:
        bot.send_message(cid, "❌ Aadhaar API not configured.", reply_to_message_id=reply_to); return

    send_typing(cid)
    frames = build_search_frames("🆔 <b>Aadhaar Lookup</b>")
    am = AnimMsg(cid, *frames, interval=0.18, reply_to=reply_to)
    am.start()
    stop_typing = threading.Event()
    typing_thread = threading.Thread(target=typing_loop, args=(cid, stop_typing), daemon=True)
    typing_thread.start()

    try:
        url = f"{a_url}?key={a_key}&q={aadhaar}"
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            am.stop(); am.edit(f"⚠️ API error ({r.status_code})"); return
        try: data = r.json()
        except: am.stop(); am.edit("⚠️ Bad response"); return
        if not data.get("status"):
            am.stop(); am.edit(f"😔 No data\n🆔 <code>{aadhaar}</code>"); return
        inner = data.get("data") or {}
        results = inner.get("results") or []
        if not results:
            am.stop(); am.edit("😔 No records"); return
        if uid != ADMIN_ID:
            deduct_credits(uid, cost); remaining = get_credits(uid)
        else: remaining = "♾️"
        incr_aadhaar(uid)
        out = f"🆔 <b>AADHAAR INFORMATION</b>\n🔢 <code>{aadhaar}</code>\n"
        out += f"📊 Records: <b>{len(results)}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, rec in enumerate(results, 1):
            out += f"<b>📄 Record {i}</b>\n"
            name = (rec.get("name") or "").strip()
            fname = (rec.get("fname") or "").strip()
            mobile = (rec.get("mobile") or "").strip()
            alt = (rec.get("alt") or "").strip() if rec.get("alt") else ""
            circle = (rec.get("circle") or "").strip()
            address = (rec.get("address") or "").strip()
            email = (rec.get("email") or "").strip() if rec.get("email") else ""
            if name: out += f"👤 <b>Name:</b> {html_module.escape(name)}\n"
            if fname: out += f"👨 <b>Father:</b> {html_module.escape(fname)}\n"
            if mobile: out += f"📱 <b>Mobile:</b> <code>{html_module.escape(mobile)}</code>\n"
            if alt: out += f"📞 <b>Alt:</b> <code>{html_module.escape(alt)}</code>\n"
            if circle: out += f"📡 <b>Circle:</b> {html_module.escape(circle)}\n"
            if email: out += f"📧 <b>Email:</b> {html_module.escape(email)}\n"
            if address:
                addr = address.replace('!', ', ').replace('  ', ' ').strip()
                out += f"🏠 <b>Address:</b> {html_module.escape(addr)}\n"
            out += "\n"
        out += "━━━━━━━━━━━━━━━━━━━━\n"
        out += f"💎 Credits left: <b>{remaining}</b>"
        am.stop(); am.delete()
        if len(out) > 3500:
            try:
                buf = io.BytesIO(out.encode('utf-8'))
                buf.name = f"aadhaar_{aadhaar}.txt"
                bot.send_document(cid, buf, caption=f"🆔 Aadhaar {aadhaar}", reply_to_message_id=reply_to)
            except:
                bot.send_message(cid, out[:3800], parse_mode='HTML', reply_to_message_id=reply_to)
        else:
            bot.send_message(cid, out, parse_mode='HTML', reply_to_message_id=reply_to)
    except requests.exceptions.Timeout:
        am.stop(); am.edit("⚠️ API timeout")
    except Exception as e:
        logger.error(f"Aadhaar: {e}")
        am.stop(); am.edit("⚠️ Error")
    finally:
        stop_typing.set()
        try: typing_thread.join(timeout=1)
        except: pass


# ================= SEARCH: TG2NUM (Username/UserID/Link) =================
def process_tg2num(uid, cid, query, reply_to=None):
    """
    Search TG by username / userid / link.
    If country, country_code, number ALL null → No data found, NO credit deduction.
    """
    if int(get_setting("maintenance_mode", 0)) == 1 and uid != ADMIN_ID:
        bot.send_message(cid, "🔧 Maintenance.", reply_to_message_id=reply_to); return
    if is_banned(uid):
        bot.send_message(cid, "🚫 Banned!", reply_to_message_id=reply_to); return

    cost = int(get_setting("tg2num_cost", DEFAULT_TG2NUM_COST)) or DEFAULT_TG2NUM_COST
    if uid != ADMIN_ID and get_credits(uid) < cost:
        bot.send_message(cid, no_tg2num_credits_msg(uid, cost), reply_to_message_id=reply_to); return

    api_url, api_key = get_tg2num_api()
    if not api_url:
        bot.send_message(cid, "❌ TG2Num API not configured.", reply_to_message_id=reply_to); return

    q = (query or "").strip()
    if not q:
        bot.send_message(cid, "❌ Invalid query.", reply_to_message_id=reply_to); return

    send_typing(cid)
    frames = build_search_frames("🔒 <b>Username Lookup</b>")
    am = AnimMsg(cid, *frames, interval=0.18, reply_to=reply_to)
    am.start()
    stop_typing = threading.Event()
    typing_thread = threading.Thread(target=typing_loop, args=(cid, stop_typing), daemon=True)
    typing_thread.start()

    try:
        sep = "&" if "?" in api_url else "?"
        params = f"id={urlquote(q)}"
        if api_key:
            params += f"&key={urlquote(api_key)}"
        url = f"{api_url}{sep}{params}"

        r = requests.get(url, timeout=45)
        if r.status_code != 200:
            am.stop(); am.edit(f"⚠️ API error ({r.status_code})"); return
        try: data = r.json()
        except: am.stop(); am.edit("⚠️ Bad response"); return

        if not data.get("success") and data.get("status") != "success":
            error_msg = data.get("message") or data.get("error") or "Unknown API Error"
            am.stop()
            am.edit(
                f"😔 <b>ʟᴏᴏᴋᴜᴘ ғᴀɪʟᴇᴅ</b>\n\n"
                f"🔎 Query: <code>{html_module.escape(q)}</code>\n"
                f"⚠️ Reason: <i>{html_module.escape(str(error_msg))}</i>\n\n"
                f"<b>Admin se contact karein.</b>"
            )
            return

        result = data.get("result") or {}
        tg_id = str(result.get("tg_id") or "").strip()
        country = result.get("country")
        country_code = result.get("country_code")
        number = result.get("number")

        # ✅ if all three null → No data found, NO credit deduction
        all_null = (country is None and country_code is None and number is None)

        if all_null:
            am.stop()
            am.edit(
                f"😔 <b>ɴᴏ ᴅᴀᴛᴀ ғᴏᴜɴᴅ</b>\n\n"
                f"🔎 Query: <code>{html_module.escape(q)}</code>\n"
                f"🆔 TG ID: <code>{html_module.escape(tg_id or 'N/A')}</code>\n\n"
                f"<i>Credits nahi kate gaye.</i>\n"
                f"💎 Balance: <b>{get_credits(uid) if uid != ADMIN_ID else '♾️'}</b>"
            )
            return

        # Data found → deduct
        if uid != ADMIN_ID:
            deduct_credits(uid, cost); remaining = get_credits(uid)
        else:
            remaining = "♾️"
        incr_tg2num(uid)

        # ✅ Output — sirf result ki info, koi account/used/expires nahi
        out = (
            f"🔒 <b>USERNAME → TG INFORMATION</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔎 <b>Query:</b> <code>{html_module.escape(q)}</code>\n"
            f"🆔 <b>TG ID:</b> <code>{html_module.escape(tg_id or 'N/A')}</code>\n"
        )
        if country is not None and str(country).strip():
            out += f"🌍 <b>Country:</b> {html_module.escape(str(country))}\n"
        if country_code is not None and str(country_code).strip():
            out += f"🏳️ <b>Country Code:</b> <code>{html_module.escape(str(country_code))}</code>\n"
        if number is not None and str(number).strip():
            out += f"📱 <b>Number:</b> <code>{html_module.escape(str(number))}</code>\n"

        out += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        out += f"💎 Credits left: <b>{remaining}</b>"

        am.stop(); am.delete()
        if len(out) > 3500:
            try:
                buf = io.BytesIO(out.encode('utf-8'))
                buf.name = f"tg_{re.sub(r'[^A-Za-z0-9_]', '_', q)[:40]}.txt"
                bot.send_document(cid, buf, caption=f"🔒 @{q[:40]}", reply_to_message_id=reply_to)
            except:
                bot.send_message(cid, out[:3800], parse_mode='HTML', reply_to_message_id=reply_to)
        else:
            bot.send_message(cid, out, parse_mode='HTML', reply_to_message_id=reply_to)

    except requests.exceptions.Timeout:
        am.stop(); am.edit("⚠️ API timeout")
    except requests.exceptions.ConnectionError:
        am.stop(); am.edit("⚠️ API down")
    except Exception as e:
        logger.error(f"TG2Num: {e}")
        am.stop(); am.edit("⚠️ Error")
    finally:
        stop_typing.set()
        try: typing_thread.join(timeout=1)
        except: pass


# ================= MENU =================
def process_menu(uid, cid, text, reply_to=None):
    upd_last_seen(uid)
    if int(get_setting("maintenance_mode", 0)) == 1 and uid != ADMIN_ID:
        bot.send_message(cid, "🔧 Maintenance.", reply_to_message_id=reply_to); return
    if is_banned(uid) and uid != ADMIN_ID:
        bot.send_message(cid, "🚫 Banned!", reply_to_message_id=reply_to); return

    if text == "👑 Admin Panel":
        if uid != ADMIN_ID:
            bot.send_message(cid, "❌ Admin only", reply_to_message_id=reply_to); return
        bot.send_message(cid,
            "👑 <b>ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ — ʟᴏʀᴅ ᴏғ ғᴇᴀᴛᴜʀᴇs</b>\n\nChoose a section 👇",
            parse_mode='HTML', reply_markup=admin_kb(), reply_to_message_id=reply_to)
        return

    if text == "📊 Dashboard":
        if uid != ADMIN_ID: return
        p, a, r, rev, today_rev = pay_stats()
        s = (f"📊 <b>ᴅᴀsʜʙᴏᴀʀᴅ</b>\n\n"
             f"👥 Users: <b>{total_users()}</b> | 🆕 {new_users_24h()}\n"
             f"🔥 Active: <b>{active_users_24h()}</b>\n"
             f"🚫 Banned: <b>{total_banned()}</b>\n"
             f"💬 Groups: <b>{total_groups()}</b>\n\n"
             f"🔍 Number: <b>{total_searches()}</b>\n"
             f"🆔 Aadhaar: <b>{total_aadhaar_searches()}</b>\n"
             f"🔒 Username: <b>{total_tg2num_searches()}</b>\n"
             f"💎 Credits: <b>{total_credits_in_circulation()}</b>\n\n"
             f"💰 Payments: ⏳{p} ✅{a} ❌{r}\n"
             f"💵 Revenue: <b>₹{rev}</b>\n"
             f"📅 Today: <b>₹{today_rev}</b>\n"
             f"🎁 Promos: {len(all_promos())}")
        bot.send_message(cid, s, parse_mode='HTML', reply_to_message_id=reply_to); return

    if text == "👥 Users":
        if uid != ADMIN_ID: return
        bot.send_message(cid, "👥 <b>ᴜsᴇʀs</b>", parse_mode='HTML',
                         reply_markup=users_panel_kb(), reply_to_message_id=reply_to); return

    if text == "💰 Payments":
        if uid != ADMIN_ID: return
        bot.send_message(cid, "💰 <b>ᴘᴀʏᴍᴇɴᴛs</b>", parse_mode='HTML',
                         reply_markup=payments_panel_kb(), reply_to_message_id=reply_to); return

    if text == "📦 Promo":
        if uid != ADMIN_ID: return
        bot.send_message(cid, "📦 <b>ᴘʀᴏᴍᴏ</b>", parse_mode='HTML',
                         reply_markup=promo_panel_kb(), reply_to_message_id=reply_to); return

    if text == "📢 Broadcast":
        if uid != ADMIN_ID: return
        bot.send_message(cid,
            f"📢 <b>ʙʀᴏᴀᴅᴄᴀsᴛ</b>\n\n"
            f"👤 Users: {total_users()}\n"
            f"💬 Groups: {total_groups()}\n"
            f"📢 Channels: {len(all_channels())}\n\n"
            f"Auto-pin in groups & channels ✅",
            parse_mode='HTML', reply_markup=broadcast_panel_kb(),
            reply_to_message_id=reply_to); return

    if text == "📈 Analytics":
        if uid != ADMIN_ID: return
        bot.send_message(cid, "📈 <b>ᴀɴᴀʟʏᴛɪᴄs</b>", parse_mode='HTML',
                         reply_markup=analytics_panel_kb(), reply_to_message_id=reply_to); return

    if text == "⚙️ Force Join":
        if uid != ADMIN_ID: return
        bot.send_message(cid, "⚙️ <b>ғᴏʀᴄᴇ ᴊᴏɪɴ</b>", parse_mode='HTML',
                         reply_markup=force_kb(), reply_to_message_id=reply_to); return

    if text == "💬 Groups":
        if uid != ADMIN_ID: return
        bot.send_message(cid, f"💬 <b>ɢʀᴏᴜᴘs ({total_groups()})</b>", parse_mode='HTML',
                         reply_markup=groups_panel_kb(), reply_to_message_id=reply_to); return

    if text == "🔧 Settings":
        if uid != ADMIN_ID: return
        bot.send_message(cid, "🔧 <b>sᴇᴛᴛɪɴɢs</b>", parse_mode='HTML',
                         reply_markup=settings_panel_kb(), reply_to_message_id=reply_to); return

    if text == "💎 Manage Credits":
        if uid != ADMIN_ID: return
        bot.send_message(cid, "💎 <b>ᴄʀᴇᴅɪᴛs</b>", parse_mode='HTML',
                         reply_markup=credits_panel_kb(), reply_to_message_id=reply_to); return

    if text == "📤 Export Data":
        if uid != ADMIN_ID: return
        csv_d = export_csv()
        if csv_d:
            try:
                bot.send_document(cid, csv_d.encode('utf-8'), visible_file_name="users.csv",
                                  caption=f"📤 {total_users()} users",
                                  reply_to_message_id=reply_to)
            except: pass
        return

    if text == "🛠 Maintenance":
        if uid != ADMIN_ID: return
        cur = int(get_setting("maintenance_mode", 0))
        nxt = 0 if cur else 1
        set_setting("maintenance_mode", nxt)
        st = "🟢 OFF" if nxt == 0 else "🔴 ON"
        bot.send_message(cid, f"🛠 Maintenance: <b>{st}</b>", parse_mode='HTML',
                         reply_to_message_id=reply_to); return

    if text == "👑 Bot Info":
        if uid != ADMIN_ID: return
        bi = bot.get_me()
        num_url, num_key = get_num_api()
        a_url, a_key = get_aadhaar_api()
        t_url, t_key = get_tg2num_api()
        s = (f"👑 <b>ʙᴏᴛ ɪɴғᴏ</b>\n\n"
             f"🤖 {bi.first_name}\n"
             f"🆔 <code>{bi.id}</code>\n"
             f"📛 @{bi.username}\n"
             f"💬 Groups: {total_groups()}\n"
             f"👥 Users: {total_users()}\n"
             f"🎁 Promos: {len(all_promos())}\n"
             f"🔎 Num API: {'🟢' if num_url and num_key else '🔴'}\n"
             f"🆔 Aadhaar API: {'🟢' if a_url and a_key else '🔴'}\n"
             f"🔒 TG2Num API: {'🟢' if t_url else '🔴'}\n"
             f"🔌 Auto UPI: {'🟢' if is_auto_upi_available() else '🔴'}")
        bot.send_message(cid, s, parse_mode='HTML', reply_to_message_id=reply_to); return

    if text == "🔙 Back to Menu":
        bot.send_message(cid, "🏠", reply_markup=main_kb(uid), reply_to_message_id=reply_to); return

    if text == "➕ Add to Group":
        add_link = f"https://t.me/{BOT_USERNAME_CLEAN}?startgroup=true&admin={ADD_GROUP_PERMS}"
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("➕ Add Bot (auto-admin)", url=add_link))
        txt = (
            "➕ <b>Add Bot to Your Group</b>\n\n"
            "1️⃣ Button dabao → group select karo\n"
            "   <i>(Wahi groups dikhenge jahan aap member ho)</i>\n\n"
            "2️⃣ Telegram <b>khud permissions ka popup</b> dikhayega\n"
            "   → ✅ <b>Allow / Yes</b> dabao\n\n"
            "3️⃣ Bas! Bot admin ban gaya with all permissions ✅\n\n"
            "⚠️ <b>Important:</b>\n"
            "Sirf <b>group Admin/Owner</b> hi bot add kar sakta hai\n"
            "(Agar aap admin nahi ho, bot leave kar dega)\n\n"
            f"👥 Bot already in <b>{total_groups()}</b> groups!"
        )
        bot.send_message(cid, txt, parse_mode='HTML', reply_markup=kb,
                         reply_to_message_id=reply_to); return

    if text == "📞 Number To Info":
        cost = get_setting("search_cost", 5) or 5
        bot.send_message(cid, f"📱 Send 10-digit number (cost: {cost}):",
                         reply_to_message_id=reply_to)

    elif text == "🆔 Aadhaar Info":
        cost = get_setting("aadhaar_cost", DEFAULT_AADHAAR_COST) or DEFAULT_AADHAAR_COST
        msg = bot.send_message(cid, f"🆔 Send 12-digit Aadhaar number (cost: {cost}):",
                               reply_to_message_id=reply_to)
        set_state(uid, {'state': 'aadhaar_input', 'prompt_msg_id': msg.message_id})

    elif text == "🔒 Username To Info":
        cost = get_setting("tg2num_cost", DEFAULT_TG2NUM_COST) or DEFAULT_TG2NUM_COST
        t_url, _ = get_tg2num_api()
        if not t_url:
            bot.send_message(cid,
                "⚠️ <b>Username lookup abhi available nahi hai</b>\n\n"
                "Admin se contact karo.",
                parse_mode='HTML', reply_to_message_id=reply_to)
            return
        msg = bot.send_message(cid,
            f"🔒 <b>Username / TG Lookup</b> (cost: {cost}cr)\n\n"
            f"Send any of these:\n"
            f"  • <code>@username</code>\n"
            f"  • <code>username</code>\n"
            f"  • <code>123456789</code> (userid)\n"
            f"  • <code>https://t.me/username</code>",
            parse_mode='HTML', reply_to_message_id=reply_to)
        set_state(uid, {'state': 'tg2num_input', 'prompt_msg_id': msg.message_id})

    elif text == "💰 Refer & Earn":
        link = f"https://t.me/{BOT_USERNAME_CLEAN}?start=ref_{uid}"
        refs, bonus, searches = user_stats(uid)
        rb = get_setting("referral_bonus_referrer", 10)
        nb = get_setting("referral_bonus_newuser", 5)
        r = quote("Referral") + (f"🔗 <b>YOUR LINK:</b>\n\n<code>{link}</code>\n\n"
                                  f"📌 +{rb} per referral, friend gets +{nb}\n\n"
                                  f"📊 Referrals: {refs} | Bonus: {bonus}")
        share_text = f"🔥 Best Indian OSINT Bot — phone + Aadhaar + Username lookup!\n\n{link}"
        share_url = f"https://t.me/share/url?url={link}&text={share_text}"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("📋 Copy", callback_data=f"copyref_{uid}"),
               InlineKeyboardButton("📤 Send", url=share_url))
        kb.row(InlineKeyboardButton("🔙 Back", callback_data="home"))
        bot.send_message(cid, r, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)

    elif text == "🛒 Buy Credits":
        t, kb = buy_kb()
        bot.send_message(cid, t, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)

    elif text == "🎟 Redeem Code":
        msg = bot.send_message(cid, "🎟 Send promo code:", reply_to_message_id=reply_to)
        set_state(uid, {'state': 'redeem_code', 'prompt_msg_id': msg.message_id})

    elif text == "👤 My Profile":
        u = get_or_create_user(uid)
        st = "👑 Admin" if uid == ADMIN_ID else ("🚫 Banned" if u.get("banned") else f"{u.get('credits',0)}cr")
        refs, bonus, searches = user_stats(uid)
        r = quote("Profile") + (f"👤 <b>Profile</b>\n\n🆔 <code>{uid}</code>\n📊 {st}\n"
                                 f"📌 Refs: {refs}\n🎁 Bonus: {bonus}\n"
                                 f"🔍 Number: {searches}\n"
                                 f"🆔 Aadhaar: {u.get('aadhaar_searches', 0)}\n"
                                 f"🔒 Username: {u.get('tg2num_searches', 0)}")
        bot.send_message(cid, r, parse_mode='HTML', reply_to_message_id=reply_to)

    elif text == "❓ Help":
        bot.send_message(cid, f"Contact: {ADMIN_USERNAME}", reply_to_message_id=reply_to)

    elif text == "ℹ️ About":
        bot.send_message(cid, f"ℹ️ OSINT bot\n{BOT_USERNAME}", reply_to_message_id=reply_to)


def process_promo(uid, cid, code, reply_to=None):
    r = redeem_promo(code, uid)
    h = quote(code)
    if r is None:
        bot.send_message(cid, h + "❌ Invalid/expired", parse_mode='HTML', reply_to_message_id=reply_to)
    elif r == -1:
        bot.send_message(cid, h + "⚠️ Already used", parse_mode='HTML', reply_to_message_id=reply_to)
    else:
        bot.send_message(cid, h + f"✅ +{r} credits!\nBalance: {get_credits(uid)}",
                         parse_mode='HTML', reply_to_message_id=reply_to)


# ================= PAYMENT =================
def show_amount(uid, cid, amount, reply_to=None, edit_mid=None):
    rate = int(get_setting("credits_per_rupee", 1)) or 1
    credits = amount * rate
    mon = int(get_setting("upi_manual_enabled", 1))
    auto_ok = is_auto_upi_available()
    text = (f"💳 <b>Deposit Request</b>\n\n💰 ₹{amount}\n"
            f"💎 You get: <b>{credits} credits</b>\n"
            f"💱 Rate: ₹1 = {rate} credit\n\n📌 Method:")
    kb = InlineKeyboardMarkup(row_width=1)
    if auto_ok: kb.add(InlineKeyboardButton("⚡ Auto UPI", callback_data=f"pm_auto_{amount}_{credits}"))
    else: kb.add(InlineKeyboardButton("⚡ Auto UPI — Unavailable", callback_data="auto_na"))
    if mon: kb.add(InlineKeyboardButton("📋 Manual UPI", callback_data=f"pm_manual_{amount}_{credits}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="buy"))
    if edit_mid:
        try: bot.edit_message_text(text, cid, edit_mid, parse_mode='HTML', reply_markup=kb); return
        except: pass
    bot.send_message(cid, text, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)


def show_manual_page(uid, cid, amount, credits, reply_to=None, edit_mid=None):
    upi = get_setting("upi_manual_id", "not set")
    qr = get_setting("upi_manual_qr", "")
    caption = (f"📋 <b>MANUAL UPI</b>\n\n💰 ₹{amount}\n💎 {credits} credits\n"
               f"📱 UPI: <code>{upi}</code>\n\n1. Pay\n2. I've Paid\n3. Screenshot")
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ I've Paid", callback_data=f"ip_manual_{amount}_{credits}"),
           InlineKeyboardButton("🔙 Back", callback_data="buy"))
    if edit_mid:
        try:
            bot.edit_message_text(caption, cid, edit_mid, parse_mode='HTML', reply_markup=kb)
            if qr and qr.startswith("http"): send_qr_image(cid, qr, "🖼 Scan", None, None)
            return
        except: pass
    if qr and qr.startswith("http"):
        if send_qr_image(cid, qr, caption, kb, reply_to): return
    bot.send_message(cid, caption, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)


def handle_auto_upi(uid, cid, amount, credits, reply_to=None, edit_mid=None):
    if not is_auto_upi_available():
        bot.send_message(cid, "⚡ Auto UPI unavailable.", reply_to_message_id=reply_to); return
    if edit_mid:
        try: bot.edit_message_text(f"⠋ ⚡ <b>Generating</b>\n<code>{progress_bar(0)}</code>",
                                    cid, edit_mid, parse_mode='HTML')
        except: pass
    frames = build_search_frames("⚡ <b>Generating order</b>")
    am = AnimMsg(cid, *frames, interval=0.18, reply_to=reply_to)
    am.start()
    try: ok, oid, link, qr, upi, raw = create_gateway_order(amount, uid)
    except Exception as e: ok, oid, link, qr, upi, raw = False, None, None, None, None, str(e)
    am.stop()
    if not ok:
        am.edit(f"⚠️ <b>Order failed</b>\n\n<i>{str(raw)[:200]}</i>"); return
    am.delete()
    pid = create_payment(uid, amount, credits, pay_mode="auto", order_id=oid, payment_link=link,
                         gateway_raw=raw if isinstance(raw, dict) else {"raw": str(raw)})
    if not pid:
        bot.send_message(cid, "⚠️ Save fail.", reply_to_message_id=reply_to); return
    set_state(uid, {'state': 'waiting_payment', 'order_id': oid, 'payment_id': pid,
                    'amount': amount, 'credits': credits, 'pay_mode': 'auto'})
    lines = [f"✅ <b>Payment Ready!</b>\n", f"💰 ₹{amount}", f"💎 {credits} credits",
             f"🆔 <code>{oid}</code>"]
    if upi: lines.append(f"📱 UPI: <code>{upi}</code>")
    lines.append(f"\n⏱ <i>5 min</i>")
    caption = "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=1)
    if link: kb.add(InlineKeyboardButton("💳 Pay Now", url=link))
    kb.add(InlineKeyboardButton("✅ Verify Payment", callback_data=f"cp_{oid}"))
    kb.add(InlineKeyboardButton("📸 Screenshot", callback_data=f"ss_{oid}"))
    kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="buy"))
    qr_msg = None
    if qr and qr.startswith("http"):
        qr_msg = send_qr_image(cid, qr, caption, kb, reply_to)
    if qr_msg:
        threading.Thread(target=poll_order_async,
                         args=(uid, cid, oid, amount, credits, qr_msg.message_id),
                         daemon=True).start()
    else:
        if qr: caption += f"\n\n🖼 <a href='{qr}'>QR Link</a>"
        bot.send_message(cid, caption, parse_mode='HTML', reply_markup=kb, reply_to_message_id=reply_to)
        threading.Thread(target=poll_order_async,
                         args=(uid, cid, oid, amount, credits, None),
                         daemon=True).start()


# ================= GROUP ADD =================
@bot.my_chat_member_handler()
def on_my_chat_member(update):
    try:
        chat = update.chat
        new_status = update.new_chat_member.status
        old_status = update.old_chat_member.status
    except: return
    if chat.type not in ('group', 'supergroup'): return

    if new_status in ('member', 'administrator') and old_status in ('left', 'kicked', 'restricted'):
        adder_id = update.from_user.id if update.from_user else None
        adder_name = update.from_user.first_name if update.from_user else "Unknown"

        is_admin_adder = False
        if adder_id == ADMIN_ID:
            is_admin_adder = True
        else:
            try:
                m = bot.get_chat_member(chat.id, adder_id)
                if m.status in ('administrator', 'creator'):
                    is_admin_adder = True
            except: pass

        if not is_admin_adder:
            try:
                bot.send_message(chat.id,
                    "❌ <b>Sorry!</b>\n\nSirf group <b>Admin/Owner</b> hi mujhe add kar sakta hai.\n\n"
                    "Aap admin ban jao, phir try karo. 👋",
                    parse_mode='HTML')
                time.sleep(2)
            except: pass
            try: bot.leave_chat(chat.id)
            except: pass
            try:
                bot.send_message(adder_id,
                    f"❌ <b>You're not an admin</b> of <b>{html_module.escape(chat.title or '')}</b>\n\n"
                    f"Only group admins can add me.", parse_mode='HTML')
            except: pass
            return

        try:
            groups_col.update_one(
                {"chat_id": chat.id},
                {"$set": {"chat_id": chat.id, "title": chat.title, "type": chat.type,
                          "added_at": now(), "enabled": 1, "added_by": adder_id}},
                upsert=True)
        except: pass

        bi = bot.get_me()
        bot_is_admin = False
        try:
            m = bot.get_chat_member(chat.id, bi.id)
            bot_is_admin = m.status in ('administrator', 'creator')
        except: pass

        try:
            bot.send_message(ADMIN_ID,
                f"✅ <b>Bot added to group!</b>\n\n"
                f"📛 <b>{html_module.escape(chat.title or '')}</b>\n"
                f"🆔 <code>{chat.id}</code>\n"
                f"👤 By: {adder_name} (<code>{adder_id}</code>)\n"
                f"🤖 Bot admin: {'✅' if bot_is_admin else '❌'}\n"
                f"📊 Total: {total_groups()}",
                parse_mode='HTML')
        except: pass

        try:
            if bot_is_admin:
                bot.send_message(chat.id,
                    f"🎉 <b>Thanks for adding me!</b>\n\n"
                    f"✅ Bot is admin with permissions\n\n"
                    f"📱 Send <code>10-digit number</code> → search\n"
                    f"🆔 Send <code>12-digit Aadhaar</code> → lookup\n"
                    f"🔒 Send <code>@username</code> or <code>/tg username</code> → TG lookup\n\n"
                    f"🔍 Ready to go!",
                    parse_mode='HTML')
            else:
                bot.send_message(chat.id,
                    f"🎉 <b>Thanks for adding me!</b>\n\n"
                    f"📱 Send <code>10-digit number</code> → search\n"
                    f"🆔 Send <code>12-digit Aadhaar</code> → lookup\n"
                    f"🔒 Send <code>@username</code> or <code>/tg username</code> → TG lookup\n\n"
                    f"⚠️ <b>Recommended:</b> Make me Admin with all permissions "
                    f"for auto-pin & smoother operations.",
                    parse_mode='HTML')
        except: pass

    elif new_status in ('left', 'kicked'):
        try: groups_col.update_one({"chat_id": chat.id}, {"$set": {"enabled": 0}})
        except: pass
        try:
            bot.send_message(ADMIN_ID,
                f"❌ <b>Bot removed</b>\n📛 {html_module.escape(chat.title or '')}",
                parse_mode='HTML')
        except: pass


# ================= COMMANDS =================
@bot.message_handler(commands=['start'], func=lambda m: m.chat.type == 'private')
def cmd_start(m):
    uid = m.from_user.id
    uname = m.from_user.username or "user"
    cid = m.chat.id
    clear_state(uid)
    upd_last_seen(uid)
    if is_banned(uid):
        bot.reply_to(m, "🚫 Banned!"); return
    was_existing = users_col.find_one({"user_id": uid}) is not None
    referrer_id = None
    if ' ' in m.text:
        parts = m.text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            try: referrer_id = int(parts[1].replace('ref_', ''))
            except: pass
    get_or_create_user(uid)
    if referrer_id:
        claimed = try_claim_referral(uid, referrer_id)
        if claimed:
            try: bot.send_message(referrer_id,
                f"🎉 New referral!\n+{get_setting('referral_bonus_referrer',10)}cr")
            except: pass
    if not was_existing and uid != ADMIN_ID:
        try:
            ref_info = f"🎁 Referred by: <code>{referrer_id}</code>" if referrer_id else "🚪 Direct"
            bot.send_message(ADMIN_ID,
                f"🆕 <b>New User!</b>\n\n👤 @{uname}\n🆔 <code>{uid}</code>\n{ref_info}\n"
                f"📊 Total: {total_users()}", parse_mode='HTML')
        except: pass
    if not manager.ensure(uid, cid, {"type": "start"}): return
    send_typing(cid)
    frames = [f"👋 <b>Welcome</b> {DOT_FRAMES[0]}", f"👋 <b>Welcome</b> {DOT_FRAMES[1]}",
              f"👋 <b>Welcome</b> {DOT_FRAMES[2]}", f"👋 <b>Welcome</b> {DOT_FRAMES[3]}"]
    am = AnimMsg(cid, *frames, interval=0.18, reply_to=m.message_id)
    if am.start():
        time.sleep(0.6); am.stop(); am.delete()
    bot.reply_to(m, welcome_txt(uid, uname), parse_mode='HTML', reply_markup=main_kb(uid))


@bot.message_handler(commands=['start'], func=lambda m: m.chat.type in ['group', 'supergroup'])
def cmd_start_group(m):
    try:
        groups_col.update_one(
            {"chat_id": m.chat.id},
            {"$set": {"chat_id": m.chat.id, "title": m.chat.title, "type": m.chat.type,
                      "enabled": 1, "added_at": now()}},
            upsert=True)
    except: pass
    bot.reply_to(m,
        "👋 <b>Hello Group!</b>\n\n"
        "📱 Send 10-digit number → search\n"
        "🆔 Send 12-digit Aadhaar → lookup\n"
        "🔒 Send <code>@username</code> or <code>/tg username</code> → TG lookup\n\n"
        f"💎 Balance: {get_credits(m.from_user.id) if m.from_user.id != ADMIN_ID else '♾️'}",
        parse_mode='HTML')


@bot.message_handler(commands=['addgroup'])
def cmd_addgroup(m):
    add_link = f"https://t.me/{BOT_USERNAME_CLEAN}?startgroup=true&admin={ADD_GROUP_PERMS}"
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("➕ Add Bot (auto-admin)", url=add_link))
    bot.reply_to(m,
        "➕ <b>Add me to your group!</b>\n\n"
        "✅ Telegram khud saari admin permissions maang lega\n"
        "✅ Aapko bas <b>Allow / Yes</b> dabana hai\n\n"
        "⚠️ Only group admins can add.",
        parse_mode='HTML', reply_markup=kb)


@bot.message_handler(commands=['buy'], func=lambda m: m.chat.type == 'private')
def cmd_buy(m):
    uid = m.from_user.id
    clear_state(uid)
    if not manager.ensure(uid, m.chat.id): return
    t, kb = buy_kb()
    bot.send_message(m.chat.id, t, parse_mode='HTML', reply_markup=kb)


@bot.message_handler(commands=['cancel'], func=lambda m: m.chat.type == 'private')
def cmd_cancel(m):
    uid = m.from_user.id
    clear_state(uid)
    bot.reply_to(m, "✅ Cancelled.")
    try: bot.send_message(m.chat.id, "🏠", reply_markup=main_kb(uid))
    except: pass


@bot.message_handler(commands=['testnum'])
def cmd_testnum(m):
    uid = m.from_user.id
    if uid != ADMIN_ID: return
    samples = ["9876543210","+919876543210","919876543210","98765 43210",
               "9198765 43210","+91 98765 43210","98765-43210","(+91) 98765-43210",
               "09876543210","0091 98765 43210","91-98765-43210",
               "Order 12345 call 9876543210 urgently","my num is 9876543210 plz"]
    lines = ["<b>extract_num:</b>\n"]
    for s in samples:
        r = extract_num(s)
        lines.append(f"{'✅' if r else '❌'} <code>{s}</code> → <code>{r}</code>")
    lines.append("\n<b>extract_aadhaar:</b>")
    for s in ["234567890123","934567890123","034567890123","123456789012"]:
        r = extract_aadhaar(s)
        lines.append(f"{'✅' if r else '❌'} <code>{s}</code> → <code>{r}</code>")
    lines.append("\n<b>extract_tg_query:</b>")
    for s in ["@itzanjasha","itzanjasha","123456789","https://t.me/itzanjasha",
              "t.me/itzanjasha","telegram.me/itzanjasha","ab","a"*40, "@123456789"]:
        r = extract_tg_query(s)
        lines.append(f"{'✅' if r else '❌'} <code>{s}</code> → <code>{r}</code>")
    bot.reply_to(m, "\n".join(lines), parse_mode='HTML')


# ================= MENU BUTTONS =================
_MENU_TEXTS = {
    "📞 Number To Info", "🆔 Aadhaar Info", "🔒 Username To Info",
    "💰 Refer & Earn", "🛒 Buy Credits",
    "🎟 Redeem Code", "👤 My Profile", "❓ Help", "ℹ️ About", "👑 Admin Panel",
    "📊 Dashboard", "👥 Users", "💰 Payments", "📦 Promo",
    "📢 Broadcast", "📈 Analytics", "⚙️ Force Join", "💬 Groups",
    "🔧 Settings", "💎 Manage Credits", "📤 Export Data", "🛠 Maintenance",
    "👑 Bot Info", "➕ Add to Group",
    "🔙 Back to Menu"
}


@bot.message_handler(func=lambda m: m.chat.type == 'private' and m.text in _MENU_TEXTS)
def menu_btn(m):
    uid = m.from_user.id
    cid = m.chat.id
    if not rate_ok(uid): return
    st = states.get(uid, {}).get('state')
    if st and st not in _ADMIN_INPUT_STATES:
        clear_state(uid)
    if not manager.ensure(uid, cid, {"type": "menu_button", "data": m.text}): return
    process_menu(uid, cid, m.text, m.message_id)


# ================= GROUP SEARCH =================
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup']
    and m.content_type == 'text' and extract_num(m.text) is not None)
def group_num_search(m):
    uid = m.from_user.id; cid = m.chat.id
    phone = extract_num(m.text)
    if not phone: return
    upd_last_seen(uid); get_or_create_user(uid)
    if not rate_ok(uid): return
    if is_banned(uid):
        try: bot.reply_to(m, "🚫 Banned")
        except: pass
        return
    cost = int(get_setting("search_cost", 5))
    if uid != ADMIN_ID and get_credits(uid) < cost:
        try: bot.reply_to(m, f"⚠️ Not enough credits.\n💎 Yours: {get_credits(uid)}\nDM: {BOT_USERNAME}")
        except: pass
        return
    process_search(uid, cid, phone, m.message_id)


@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup']
    and m.content_type == 'text' and extract_aadhaar(m.text) is not None)
def group_aadhaar_search(m):
    uid = m.from_user.id; cid = m.chat.id
    aad = extract_aadhaar(m.text)
    if not aad: return
    upd_last_seen(uid); get_or_create_user(uid)
    if not rate_ok(uid): return
    if is_banned(uid):
        try: bot.reply_to(m, "🚫 Banned")
        except: pass
        return
    cost = int(get_setting("aadhaar_cost", DEFAULT_AADHAAR_COST))
    if uid != ADMIN_ID and get_credits(uid) < cost:
        try: bot.reply_to(m, f"⚠️ Not enough credits.\nDM: {BOT_USERNAME}")
        except: pass
        return
    process_aadhaar(uid, cid, aad, m.message_id)


# ================= GROUP USERNAME SEARCH =================
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup']
    and m.content_type == 'text')
def group_tg_search(m):
    uid = m.from_user.id; cid = m.chat.id
    text = m.text.strip()
    
    # Restrict trigger words to avoid spamming in groups
    query = None
    if text.startswith('/tg ') or text.startswith('/username '):
        query = text.split(' ', 1)[1].strip()
    elif 't.me/' in text or 'telegram.me/' in text:
        query = extract_tg_query(text)
    elif text.startswith('@'):
        query = extract_tg_query(text)
    
    if not query: return # Ignore normal chat
        
    upd_last_seen(uid); get_or_create_user(uid)
    if not rate_ok(uid): return
    if is_banned(uid):
        try: bot.reply_to(m, "🚫 Banned")
        except: pass
        return
        
    cost = int(get_setting("tg2num_cost", DEFAULT_TG2NUM_COST))
    if uid != ADMIN_ID and get_credits(uid) < cost:
        try: bot.reply_to(m, f"⚠️ Not enough credits.\n💎 Yours: {get_credits(uid)}\nDM: {BOT_USERNAME}")
        except: pass
        return
        
    process_tg2num(uid, cid, query, m.message_id)


# ================= PRIVATE NUMBER HANDLER =================
@bot.message_handler(func=lambda m: m.chat.type == 'private'
    and m.content_type == 'text' and extract_num(m.text) is not None)
def num_search(m):
    uid = m.from_user.id; cid = m.chat.id
    st = states.get(uid, {}).get('state')
    phone = extract_num(m.text)
    if not phone: return
    if st == 'aadhaar_input':
        clear_state(uid)
    elif st == 'tg2num_input':
        return  # let text_handler take it
    elif st == 'redeem_code':
        return
    elif st in _BLOCKING_STATES:
        return
    upd_last_seen(uid)
    if not rate_ok(uid): return
    if not manager.ensure(uid, cid, {"type": "number_search", "data": phone}): return
    if st and st not in _BLOCKING_STATES:
        clear_state(uid)
    process_search(uid, cid, phone, m.message_id)


# ================= PHOTO HANDLER =================
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.type == 'private')
def photo_handler(m):
    uid = m.from_user.id; cid = m.chat.id
    upd_last_seen(uid)
    uname = m.from_user.username or "user"
    if not manager.ensure(uid, cid, {"type": "media"}): return
    if is_banned(uid):
        bot.reply_to(m, "🚫 Banned"); return
    st = states.get(uid, {}); s = st.get('state')

    if uid == ADMIN_ID and s == 'ap_bcast_input':
        us = all_users(); gs = all_groups(); chs = [c["channel_id"] for c in all_channels()]
        file_id = m.photo[-1].file_id
        def go():
            ok_u = fail_u = ok_g = fail_g = ok_c = fail_c = 0
            for u in us:
                try: bot.send_photo(u, file_id, caption="📢"); ok_u += 1; time.sleep(0.04)
                except: fail_u += 1
            for g in gs:
                try:
                    mm = bot.send_photo(g, file_id, caption="📢"); ok_g += 1
                    try: bot.pin_chat_message(g, mm.message_id, disable_notification=True)
                    except: pass
                    time.sleep(0.04)
                except: fail_g += 1
            for cc in chs:
                try:
                    mm = bot.send_photo(cc, file_id, caption="📢"); ok_c += 1
                    try: bot.pin_chat_message(cc, mm.message_id, disable_notification=True)
                    except: pass
                    time.sleep(0.04)
                except: fail_c += 1
            try:
                bot.send_message(uid,
                    f"📢 Photo bcast:\n"
                    f"👤 {ok_u}✅/{fail_u}❌\n💬 {ok_g}✅/{fail_g}❌ (pinned)\n"
                    f"📢 {ok_c}✅/{fail_c}❌ (pinned)")
            except: pass
        threading.Thread(target=go, daemon=True).start()
        bot.reply_to(m, "📢 Queued."); clear_state(uid); return

    if s == 'waiting_ss':
        pid = st.get('payment_id'); file_id = m.photo[-1].file_id
        if pid: attach_ss(pid, file_id); p = get_payment(pid)
        else:
            amt = st.get('amount', 0); cr = st.get('credits', 0); oid = st.get('order_id')
            pid = create_payment(uid, amt, cr, pay_mode="auto", screenshot_id=file_id, order_id=oid)
            p = get_payment(pid) if pid else None
        if p:
            try:
                txt = (f"⚠️ <b>Auto-fail → Manual</b>\n\n👤 @{uname} (<code>{uid}</code>)\n"
                       f"💵 ₹{p['amount']}\n💎 {p['credits']}\n🆔 <code>{pid}</code>")
                kb = InlineKeyboardMarkup()
                kb.row(InlineKeyboardButton("✅", callback_data=f"ap_{pid}"),
                       InlineKeyboardButton("❌", callback_data=f"rj_{pid}"))
                bot.send_photo(ADMIN_ID, file_id, caption=txt, parse_mode='HTML', reply_markup=kb)
                bot.reply_to(m, "✅ Sent to admin.")
            except: pass
        clear_state(uid); return

    if s == 'manual_ss':
        file_id = m.photo[-1].file_id
        amt = st.get('amount', 0); cr = st.get('credits', 0)
        pid = create_payment(uid, amt, cr, pay_mode="manual", screenshot_id=file_id)
        if not pid:
            bot.reply_to(m, "❌ Save error."); clear_state(uid); return
        try:
            txt = (f"📋 <b>NEW MANUAL</b>\n\n👤 @{uname} (<code>{uid}</code>)\n"
                   f"💵 ₹{amt}\n💎 {cr}\n🆔 <code>{pid}</code>")
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton("✅", callback_data=f"ap_{pid}"),
                   InlineKeyboardButton("❌", callback_data=f"rj_{pid}"))
            bot.send_photo(ADMIN_ID, file_id, caption=txt, parse_mode='HTML', reply_markup=kb)
            bot.reply_to(m, "✅ Received!")
        except: pass
        clear_state(uid); return

    if uid != ADMIN_ID:
        try: bot.reply_to(m, "📸 Screenshot sirf payment ke waqt bhejein. /buy se shuru karo.")
        except: pass


# ================= TEXT HANDLER =================
@bot.message_handler(content_types=['text'], func=lambda m: m.chat.type == 'private')
def text_handler(m):
    uid = m.from_user.id; cid = m.chat.id
    text = m.text.strip(); mid = m.message_id
    if text.startswith('/'): return
    if text in _MENU_TEXTS: return
    upd_last_seen(uid)
    if is_banned(uid) and uid != ADMIN_ID:
        bot.reply_to(m, "🚫 Banned"); return
    st = states.get(uid, {}); s = st.get('state')

    # ---------- USER: Aadhaar input ----------
    if s == 'aadhaar_input':
        try: bot.delete_message(cid, st.get('prompt_msg_id'))
        except: pass
        if extract_num(text) is not None:
            clear_state(uid)
            return
        aad = extract_aadhaar(text)
        if not aad:
            clear_state(uid)
            bot.reply_to(m, "❌ Invalid Aadhaar. 12 digits, first digit 2-9."); return
        clear_state(uid)
        if not manager.ensure(uid, cid, {"type": "aadhaar_search", "data": aad}): return
        process_aadhaar(uid, cid, aad, None); return

    # ---------- USER: TG2Num input ----------
    if s == 'tg2num_input':
        try: bot.delete_message(cid, st.get('prompt_msg_id'))
        except: pass
        try: bot.delete_message(cid, mid)
        except: pass
        q = extract_tg_query(text)
        if not q:
            clear_state(uid)
            bot.reply_to(m,
                "❌ Invalid input.\n"
                "Example: <code>@username</code> / <code>123456789</code> / <code>https://t.me/username</code>",
                parse_mode='HTML'); return
        clear_state(uid)
        if not manager.ensure(uid, cid, {"type": "tg2num_search", "data": q}): return
        process_tg2num(uid, cid, q, None); return

    # ---------- USER: Custom amount ----------
    if s == 'custom_amt':
        try:
            a = int(text)
            if a < 1: raise ValueError
        except: bot.reply_to(m, "❌ Valid amount"); return
        for key in ('prompt_msg_id', 'buy_msg_id'):
            try: bot.delete_message(cid, st.get(key))
            except: pass
        try: bot.delete_message(cid, mid)
        except: pass
        clear_state(uid); show_amount(uid, cid, a, None); return

    # ---------- USER: Redeem code ----------
    if s == 'redeem_code':
        try: bot.delete_message(cid, st.get('prompt_msg_id'))
        except: pass
        try: bot.delete_message(cid, mid)
        except: pass
        clear_state(uid)
        process_promo(uid, cid, text, None); return

    # ---------- ADMIN inputs ----------
    if uid == ADMIN_ID:
        if s == 'ap_bcast_input':
            target = st.get('target', 'all')
            if target == 'users':
                def ugo():
                    for u in all_users():
                        try: bot.send_message(u, text, parse_mode='HTML'); time.sleep(0.04)
                        except: pass
                threading.Thread(target=ugo, daemon=True).start()
                bot.reply_to(m, "📢 Users queued."); clear_state(uid); return
            elif target == 'groups':
                def ggo():
                    for g in all_groups():
                        try:
                            mm = bot.send_message(g, text, parse_mode='HTML')
                            try: bot.pin_chat_message(g, mm.message_id, disable_notification=True)
                            except: pass
                            time.sleep(0.04)
                        except: pass
                threading.Thread(target=ggo, daemon=True).start()
                bot.reply_to(m, "📢 Groups queued (pinned)."); clear_state(uid); return
            else:
                bcast_q.put((text, {'parse_mode': 'HTML'}, uid))
                bot.reply_to(m, "✅ Queued (all)."); clear_state(uid); return

        if s == 'ap_userinfo_input':
            try: tid = int(text)
            except:
                try: tid = bot.get_chat(text).id
                except: bot.reply_to(m, "❌ Not found"); clear_state(uid); return
            u = users_col.find_one({"user_id": tid})
            if not u: bot.reply_to(m, "❌ Not in DB"); clear_state(uid); return
            r = (f"👤 <b>User</b>\n\n🆔 <code>{tid}</code>\n"
                 f"💎 {u.get('credits', 0)}\n"
                 f"🔍 Number: {u.get('searches', 0)}\n"
                 f"🆔 Aadhaar: {u.get('aadhaar_searches', 0)}\n"
                 f"🔒 Username: {u.get('tg2num_searches', 0)}\n"
                 f"📌 Refs: {u.get('total_referrals', 0)}\n"
                 f"🚫 Banned: {u.get('banned', 0)}")
            bot.reply_to(m, r, parse_mode='HTML'); clear_state(uid); return

        if s == 'ap_addcred_input':
            parts = text.split()
            try:
                tid = int(parts[0]); amt = int(parts[1])
                add_credits(tid, amt)
                bot.reply_to(m, f"✅ +{amt} to <code>{tid}</code>", parse_mode='HTML')
            except: bot.reply_to(m, "❌ Format: <user_id> <amount>")
            clear_state(uid); return
        if s == 'ap_remcred_input':
            parts = text.split()
            try:
                tid = int(parts[0]); amt = int(parts[1])
                deduct_credits(tid, amt)
                bot.reply_to(m, f"✅ -{amt} from <code>{tid}</code>", parse_mode='HTML')
            except: bot.reply_to(m, "❌ Format: <user_id> <amount>")
            clear_state(uid); return
        if s == 'ap_setcred_input':
            parts = text.split()
            try:
                tid = int(parts[0]); amt = int(parts[1])
                users_col.update_one({"user_id": tid}, {"$set": {"credits": amt}}, upsert=True)
                bot.reply_to(m, f"✅ Set {amt} for <code>{tid}</code>", parse_mode='HTML')
            except: bot.reply_to(m, "❌ Format: <user_id> <amount>")
            clear_state(uid); return

        if s == 'ap_genpromo1':
            if text.isdigit():
                states[uid]['credits'] = int(text)
                states[uid]['state'] = 'ap_genpromo2'
                bot.reply_to(m, "Users?")
            else: bot.reply_to(m, "❌ Number")
            return
        if s == 'ap_genpromo2':
            if text.isdigit():
                lim = int(text); cr = st.get('credits')
                code = gen_promo()
                save_promo(code, cr, lim, uid)
                bot.reply_to(m, f"🎁 <code>{code}</code>\n{cr}cr × {lim}",
                             parse_mode='HTML')
                clear_state(uid)
            else: bot.reply_to(m, "❌ Number")
            return

        if s == 'ps_rate':
            try: r = int(text); set_setting("credits_per_rupee", r); bot.reply_to(m, f"✅ {r}")
            except: bot.reply_to(m, "❌ Number")
            clear_state(uid); return
        if s == 'ps_cost':
            try: sc = int(text); set_setting("search_cost", sc); bot.reply_to(m, f"✅ {sc}")
            except: bot.reply_to(m, "❌ Number")
            clear_state(uid); return
        if s == 'ps_aadhaar':
            try: ac = int(text); set_setting("aadhaar_cost", ac); bot.reply_to(m, f"✅ {ac}")
            except: bot.reply_to(m, "❌ Number")
            clear_state(uid); return
        if s == 'ps_tg2num_cost':
            try: tc = int(text); set_setting("tg2num_cost", tc); bot.reply_to(m, f"✅ {tc}cr")
            except: bot.reply_to(m, "❌ Number")
            clear_state(uid); return
        if s == 'ps_welcome_bonus':
            try:
                wb = int(text); set_setting("welcome_bonus", wb)
                sc = int(get_setting("search_cost", 5)) or 5
                bot.reply_to(m, f"✅ Welcome bonus: {wb}cr (~{wb//sc} searches)")
            except: bot.reply_to(m, "❌ Number")
            clear_state(uid); return
        if s == 'ps_welcome':
            set_setting("welcome_msg", text)
            bot.reply_to(m, "✅ Variables: {name} {status} {credits}")
            clear_state(uid); return
        if s == 'ps_referral':
            parts = text.split()
            try:
                rb = int(parts[0]); set_setting("referral_bonus_referrer", rb)
                if len(parts) > 1:
                    nb = int(parts[1]); set_setting("referral_bonus_newuser", nb)
                    bot.reply_to(m, f"✅ R:{rb} N:{nb}")
                else: bot.reply_to(m, f"✅ R:{rb}")
            except: bot.reply_to(m, "❌ Format: '10 5'")
            clear_state(uid); return
        if s == 'ps_daily':
            try: d = int(text); set_setting("daily_free_credits", d); bot.reply_to(m, f"✅ {d}")
            except: bot.reply_to(m, "❌ Number")
            clear_state(uid); return
        if s == 'ps_key':
            set_setting("gateway_api_key", text.strip()); bot.reply_to(m, "✅ Set"); clear_state(uid); return
        if s == 'ps_manual_id':
            set_setting("upi_manual_id", text.strip()); bot.reply_to(m, f"✅ {text}"); clear_state(uid); return
        if s == 'ps_manual_qr':
            set_setting("upi_manual_qr", text.strip()); bot.reply_to(m, "✅ Set"); clear_state(uid); return

        # Number API
        if s == 'ps_num_url':
            set_setting("number_api_url", text.strip())
            bot.reply_to(m, f"✅ Number URL set:\n<code>{text.strip()}</code>", parse_mode='HTML')
            clear_state(uid); return
        if s == 'ps_num_key':
            set_setting("number_api_key", text.strip())
            bot.reply_to(m, "✅ Number API Key set")
            clear_state(uid); return

        # Aadhaar API
        if s == 'ps_aad_url':
            set_setting("aadhaar_api_url", text.strip())
            bot.reply_to(m, f"✅ Aadhaar URL set:\n<code>{text.strip()}</code>", parse_mode='HTML')
            clear_state(uid); return
        if s == 'ps_aad_key':
            set_setting("aadhaar_api_key", text.strip())
            bot.reply_to(m, "✅ Aadhaar API Key set")
            clear_state(uid); return

        # TG2Num API
        if s == 'ps_tg2num_url':
            set_setting("tg2num_url", text.strip())
            bot.reply_to(m, f"✅ TG2Num URL set:\n<code>{text.strip()}</code>", parse_mode='HTML')
            clear_state(uid); return
        if s == 'ps_tg2num_key':
            set_setting("tg2num_key", text.strip())
            bot.reply_to(m, "✅ TG2Num Key set")
            clear_state(uid); return

        if s == 'fj_add':
            if text.startswith('@'):
                try: cid_ = bot.get_chat(text).id
                except Exception as e: bot.reply_to(m, f"❌ {e}"); clear_state(uid); return
            else:
                try: cid_ = int(text)
                except: bot.reply_to(m, "❌ Invalid"); clear_state(uid); return
            set_state(uid, {'state': 'fj_add_link', 'cid': cid_})
            bot.reply_to(m, "Link ya 'skip':"); return
        if s == 'fj_add_link':
            cid_ = st.get('cid')
            link = text if text.lower() != 'skip' else f"https://t.me/joinchat/{cid_}"
            ok, msg = manager.add(cid_, link)
            bot.reply_to(m, ("✅ " if ok else "❌ ") + msg)
            clear_state(uid); return
        if s == 'ban':
            t = text.replace('@', '').strip()
            try: tid = int(t)
            except:
                try: tid = bot.get_chat(f"@{t}").id
                except: bot.reply_to(m, "❌ Not found"); clear_state(uid); return
            ban_user(tid); bot.reply_to(m, f"✅ Banned {tid}"); clear_state(uid); return
        if s == 'unban':
            t = text.replace('@', '').strip()
            try: tid = int(t)
            except:
                try: tid = bot.get_chat(f"@{t}").id
                except: bot.reply_to(m, "❌ Not found"); clear_state(uid); return
            unban_user(tid); bot.reply_to(m, f"✅ Unbanned {tid}"); clear_state(uid); return

    # Promo auto-detect
    if (extract_num(text) is None and extract_aadhaar(text) is None
            and s not in _SKIP_PROMO_DETECT):
        try:
            if promo_col.find_one({"code": text}):
                process_promo(uid, cid, text, mid); return
        except: pass

    if extract_num(text) is not None: return
    if s and s not in ('waiting_payment',):
        bot.reply_to(m, "❓ Send /cancel to reset.")


# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    uid = call.from_user.id; cid = call.message.chat.id; d = call.data

    if d == "ps_noop": safe_answer(call); return
    if d == "auto_na": safe_answer(call, "Auto UPI unavailable", show_alert=True); return
    if d == "force_verify":
        if manager is None: safe_answer(call, "Not ready", show_alert=True); return
        manager.verify_cb(call); return

    if d == "admin_panel_home":
        if uid != ADMIN_ID: safe_answer(call, "Admin only", show_alert=True); return
        try: bot.edit_message_text("👑 Menu", cid, call.message.message_id, reply_markup=None)
        except: pass
        bot.send_message(cid, "👑 Menu", reply_markup=admin_kb())
        safe_answer(call); return

    if d.startswith('ap_'):
        if uid != ADMIN_ID: safe_answer(call, "Admin only", show_alert=True); return
        if d == 'ap_ban': set_state(uid, {'state': 'ban'}); bot.send_message(cid, "User ID/@username:"); safe_answer(call); return
        if d == 'ap_unban': set_state(uid, {'state': 'unban'}); bot.send_message(cid, "User ID/@username:"); safe_answer(call); return
        if d == 'ap_userinfo': set_state(uid, {'state': 'ap_userinfo_input'}); bot.send_message(cid, "User ID:"); safe_answer(call); return
        if d == 'ap_listusers':
            us = list(users_col.find({}, {"user_id": 1, "credits": 1}).sort("joined_at", -1).limit(30))
            txt = f"📋 <b>{len(us)} Users</b>\n\n"
            for u in us: txt += f"<code>{u['user_id']}</code> — {u.get('credits', 0)}cr\n"
            try: bot.edit_message_text(txt or "Empty", cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_banned':
            us = list(users_col.find({"banned": 1}, {"user_id": 1}).limit(30))
            txt = "🚫 <b>Banned</b>\n\n" + "\n".join(f"<code>{u['user_id']}</code>" for u in us)
            try: bot.edit_message_text(txt or "None", cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_topsearch':
            us = list(users_col.find({"searches": {"$gt": 0}}).sort("searches", -1).limit(10))
            txt = "🏆 <b>Top</b>\n\n" + "\n".join(
                f"{i}. <code>{u['user_id']}</code> — {u.get('searches',0)}" for i, u in enumerate(us, 1))
            try: bot.edit_message_text(txt or "None", cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_topref':
            us = list(users_col.find({"total_referrals": {"$gt": 0}}).sort("total_referrals", -1).limit(10))
            txt = "👥 <b>Refs</b>\n\n" + "\n".join(
                f"{i}. <code>{u['user_id']}</code> — {u.get('total_referrals',0)}" for i, u in enumerate(us, 1))
            try: bot.edit_message_text(txt or "None", cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_topaadhaar':
            us = list(users_col.find({"aadhaar_searches": {"$gt": 0}}).sort("aadhaar_searches", -1).limit(10))
            txt = "🆔 <b>Aadhaar</b>\n\n" + "\n".join(
                f"{i}. <code>{u['user_id']}</code> — {u.get('aadhaar_searches',0)}" for i, u in enumerate(us, 1))
            try: bot.edit_message_text(txt or "None", cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_topbuyers':
            agg = list(payments_col.aggregate([
                {"$match": {"status": "approved"}},
                {"$group": {"_id": "$user_id", "total": {"$sum": "$amount"}}},
                {"$sort": {"total": -1}}, {"$limit": 10}]))
            txt = "💰 <b>Buyers</b>\n\n" + "\n".join(
                f"{i}. <code>{u['_id']}</code> — ₹{u['total']}" for i, u in enumerate(agg, 1))
            try: bot.edit_message_text(txt or "None", cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_daily':
            today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
            nt = users_col.count_documents({"joined_at": {"$gte": today_start}})
            at = users_col.count_documents({"last_seen": {"$gte": today_start}})
            _, _, _, _, tr = pay_stats()
            txt = f"📅 <b>Today</b>\n\n🆕 {nt}\n🔥 {at}\n💵 ₹{tr}"
            try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_fullreport':
            p, a, r, rev, tr = pay_stats()
            txt = (f"📊 <b>REPORT</b>\n\n👥 {total_users()}\n🚫 {total_banned()}\n💬 {total_groups()}\n"
                   f"🔍 {total_searches()}\n🆔 {total_aadhaar_searches()}\n🔒 {total_tg2num_searches()}\n"
                   f"💎 {total_credits_in_circulation()}\n\n"
                   f"💰 ⏳{p} ✅{a} ❌{r}\n💵 ₹{rev}\n📅 ₹{tr}")
            try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_pending':
            ps = get_pending()
            if not ps: safe_answer(call, "None", show_alert=True); return
            kb = InlineKeyboardMarkup(row_width=1)
            for p in ps[:15]:
                ic = "⚡" if p.get("pay_mode") == "auto" else "📋"
                kb.add(InlineKeyboardButton(f"{ic} ₹{p['amount']} → {p['credits']}cr",
                                            callback_data=f"pv_{p['_id']}"))
            try: bot.edit_message_text("⏳ Pending:", cid, call.message.message_id, reply_markup=kb)
            except: pass
            safe_answer(call); return
        if d == 'ap_recentpay':
            rp = list(payments_col.find().sort("created_at", -1).limit(15))
            txt = "📜 <b>Recent</b>\n\n"
            for p in rp:
                ic = {"pending":"⏳","approved":"✅","rejected":"❌","expired":"⏰"}.get(p.get("status"),"❓")
                txt += f"{ic} ₹{p['amount']} → {p['credits']}cr | <code>{p['user_id']}</code>\n"
            try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_payset':
            try: bot.edit_message_text("💳", cid, call.message.message_id, reply_markup=pay_settings_kb())
            except: pass
            safe_answer(call); return
        if d == 'ap_genpromo':
            set_state(uid, {'state': 'ap_genpromo1'})
            bot.send_message(cid, "Credits?"); safe_answer(call); return
        if d == 'ap_listpromo':
            cs = all_promos()
            if not cs: safe_answer(call, "None", show_alert=True); return
            txt = "📋 <b>Codes</b>\n\n"
            for c in cs[:20]:
                txt += f"<code>{c['code']}</code> – {c['reward_credits']}cr {c['used_count']}/{c['max_users']}\n"
            try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return
        if d == 'ap_bcastall':
            set_state(uid, {'state': 'ap_bcast_input', 'target': 'all'})
            bot.send_message(cid, "Send message (users+groups+channels):")
            safe_answer(call); return
        if d == 'ap_bcastusers':
            set_state(uid, {'state': 'ap_bcast_input', 'target': 'users'})
            bot.send_message(cid, "Message for users:")
            safe_answer(call); return
        if d == 'ap_bcastgroups':
            set_state(uid, {'state': 'ap_bcast_input', 'target': 'groups'})
            bot.send_message(cid, "Message for groups (auto-pin):")
            safe_answer(call); return
        if d == 'ap_addcred':
            set_state(uid, {'state': 'ap_addcred_input'})
            bot.send_message(cid, "Format: <user_id> <amount>"); safe_answer(call); return
        if d == 'ap_remcred':
            set_state(uid, {'state': 'ap_remcred_input'})
            bot.send_message(cid, "Format: <user_id> <amount>"); safe_answer(call); return
        if d == 'ap_setcred':
            set_state(uid, {'state': 'ap_setcred_input'})
            bot.send_message(cid, "Format: <user_id> <amount>"); safe_answer(call); return
        if d == 'ap_listgroups':
            gs = list(groups_col.find({"enabled": 1}).sort("added_at", -1).limit(30))
            txt = f"💬 <b>Groups ({len(gs)})</b>\n\n"
            for g in gs:
                txt += f"• {html_module.escape(g.get('title') or '')} — <code>{g.get('chat_id')}</code>\n"
            try: bot.edit_message_text(txt or "None", cid, call.message.message_id, parse_mode='HTML')
            except: pass
            safe_answer(call); return

    if d.startswith('fj_'):
        if uid != ADMIN_ID or manager is None:
            safe_answer(call, "Admin only", show_alert=True); return
        if d == 'fj_toggle':
            manager.toggle()
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=force_kb())
            except: pass
            safe_answer(call); return
        if d == 'fj_list':
            chs = channel_list()
            txt = "📋 <b>Channels</b>\n\n" + "\n".join(f"<code>{c['channel_id']}</code>" for c in chs)
            try: bot.edit_message_text(txt or "None", cid, call.message.message_id, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙", callback_data="admin_panel_home")))
            except: pass
            safe_answer(call); return
        if d == 'fj_add':
            set_state(uid, {'state': 'fj_add'})
            try: bot.edit_message_text("Channel ID/@username:", cid, call.message.message_id)
            except: pass
            safe_answer(call); return
        if d == 'fj_remove':
            chs = channel_list()
            if not chs: safe_answer(call, "None", show_alert=True); return
            kb = InlineKeyboardMarkup(row_width=1)
            for c in chs:
                kb.add(InlineKeyboardButton(f"❌ {c['channel_id']}", callback_data=f"fj_del_{c['channel_id']}"))
            kb.add(InlineKeyboardButton("🔙", callback_data="admin_panel_home"))
            try: bot.edit_message_text("Remove:", cid, call.message.message_id, reply_markup=kb)
            except: pass
            safe_answer(call); return
        if d.startswith('fj_del_'):
            try: manager.rm(int(d.split('_')[2]))
            except: pass
            safe_answer(call); return

    if d.startswith('ps_'):
        if uid != ADMIN_ID: safe_answer(call, "Admin only", show_alert=True); return
        if d == 'ps_rate': set_state(uid, {'state': 'ps_rate'}); bot.send_message(cid, "Rate:"); safe_answer(call); return
        if d == 'ps_cost': set_state(uid, {'state': 'ps_cost'}); bot.send_message(cid, "Search cost:"); safe_answer(call); return
        if d == 'ps_aadhaar': set_state(uid, {'state': 'ps_aadhaar'}); bot.send_message(cid, "Aadhaar cost:"); safe_answer(call); return
        if d == 'ps_tg2num_cost': set_state(uid, {'state': 'ps_tg2num_cost'}); bot.send_message(cid, "Username search cost (credits):"); safe_answer(call); return
        if d == 'ps_welcome_bonus': set_state(uid, {'state': 'ps_welcome_bonus'}); bot.send_message(cid, "Welcome bonus (credits):"); safe_answer(call); return
        if d == 'ps_welcome': set_state(uid, {'state': 'ps_welcome'}); bot.send_message(cid, "Send welcome ({name} {status} {credits}):"); safe_answer(call); return
        if d == 'ps_referral': set_state(uid, {'state': 'ps_referral'}); bot.send_message(cid, "Format: '10 5'"); safe_answer(call); return
        if d == 'ps_daily': set_state(uid, {'state': 'ps_daily'}); bot.send_message(cid, "Daily:"); safe_answer(call); return
        if d == 'ps_key': set_state(uid, {'state': 'ps_key'}); bot.send_message(cid, "Key:"); safe_answer(call); return
        if d == 'ps_manual_id': set_state(uid, {'state': 'ps_manual_id'}); bot.send_message(cid, "UPI ID:"); safe_answer(call); return
        if d == 'ps_manual_qr': set_state(uid, {'state': 'ps_manual_qr'}); bot.send_message(cid, "QR URL:"); safe_answer(call); return
        if d == 'ps_num_url': set_state(uid, {'state': 'ps_num_url'}); bot.send_message(cid, "Number API URL:"); safe_answer(call); return
        if d == 'ps_num_key': set_state(uid, {'state': 'ps_num_key'}); bot.send_message(cid, "Number API Key:"); safe_answer(call); return
        if d == 'ps_aad_url': set_state(uid, {'state': 'ps_aad_url'}); bot.send_message(cid, "Aadhaar API URL:"); safe_answer(call); return
        if d == 'ps_aad_key': set_state(uid, {'state': 'ps_aad_key'}); bot.send_message(cid, "Aadhaar API Key:"); safe_answer(call); return
        if d == 'ps_tg2num_url': set_state(uid, {'state': 'ps_tg2num_url'}); bot.send_message(cid, "TG2Num API URL:\nExample: <code>https://tg2num-botadminshere.vercel.app/</code>", parse_mode='HTML'); safe_answer(call); return
        if d == 'ps_tg2num_key': set_state(uid, {'state': 'ps_tg2num_key'}); bot.send_message(cid, "TG2Num API Key (blank if none):"); safe_answer(call); return
        if d == 'ps_gw_toggle':
            cur = int(get_setting("gateway_enabled", 0))
            set_setting("gateway_enabled", 0 if cur else 1)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=pay_settings_kb())
            except: pass
            safe_answer(call); return
        if d == 'ps_manual_tog':
            cur = int(get_setting("upi_manual_enabled", 1))
            set_setting("upi_manual_enabled", 0 if cur else 1)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=pay_settings_kb())
            except: pass
            safe_answer(call); return

    if d.startswith('amt_'):
        if d == 'amt_custom':
            msg = bot.send_message(cid, "₹?")
            set_state(uid, {'state': 'custom_amt', 'prompt_msg_id': msg.message_id,
                            'buy_msg_id': call.message.message_id})
            safe_answer(call); return
        try: amt = int(d.split('_')[1])
        except: safe_answer(call); return
        show_amount(uid, cid, amt, reply_to=call.message.message_id, edit_mid=call.message.message_id)
        safe_answer(call); return

    if d.startswith('pm_'):
        parts = d.split('_')
        if len(parts) < 4: safe_answer(call); return
        mode = parts[1]
        try: amt = int(parts[2]); cr = int(parts[3])
        except: safe_answer(call); return
        if mode == "auto":
            handle_auto_upi(uid, cid, amt, cr, reply_to=call.message.message_id, edit_mid=call.message.message_id)
        else:
            show_manual_page(uid, cid, amt, cr, reply_to=call.message.message_id, edit_mid=call.message.message_id)
        safe_answer(call); return

    if d.startswith('ip_'):
        parts = d.split('_')
        if len(parts) < 4: safe_answer(call); return
        if parts[1] == "manual":
            try: amt = int(parts[2]); cr = int(parts[3])
            except: safe_answer(call); return
            set_state(uid, {'state': 'manual_ss', 'amount': amt, 'credits': cr})
            bot.send_message(cid, "📸 Screenshot:", reply_to_message_id=call.message.message_id)
        safe_answer(call); return

    if d.startswith('cp_'):
        oid = d.replace('cp_', '', 1)
        p = payments_col.find_one({"order_id": oid, "user_id": uid, "status": "pending"})
        if not p:
            existing = payments_col.find_one({"order_id": oid, "user_id": uid})
            if existing:
                st_e = existing.get("status")
                if st_e == "approved":
                    safe_answer(call, "✅ Already Verified!")
                    bal = get_credits(uid)
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.row(InlineKeyboardButton("🏠", callback_data="home"),
                           InlineKeyboardButton("🛒", callback_data="buy"))
                    txt = (f"✅ <b>Already Verified!</b>\n\n💰 ₹{existing.get('amount', 0)}\n"
                           f"💎 +{existing.get('credits', 0)}\n📊 {bal}\n🆔 <code>{oid}</code>")
                    try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML', reply_markup=kb)
                    except:
                        try: bot.edit_message_caption(cid, call.message.message_id, caption=txt, parse_mode='HTML', reply_markup=kb)
                        except: pass
                    return
                elif st_e == "expired": safe_answer(call, "⏰ Expired", show_alert=True); return
                elif st_e == "rejected": safe_answer(call, "❌ Rejected", show_alert=True); return
            safe_answer(call, "❌ Not found", show_alert=True); return

        amt = p["amount"]; cr = p["credits"]
        frames = build_search_frames("🔎 <b>Verifying</b>")
        am = AnimMsg(cid, *frames, interval=0.18, reply_to=call.message.message_id)
        am.start()
        ok, status, info = verify_gateway_order(oid)
        am.stop()
        if ok:
            sent = _credit_on_success(uid, cid, oid, amt, cr, info, None)
            if sent: am.delete()
            else: am.edit(f"✅ <b>Already Processed!</b>\n💰 {get_credits(uid)}")
            clear_state(uid)
        elif status == "expired":
            _mark_expired(oid); am.edit(f"⏰ <b>Expired</b>")
        else:
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton("🔄", callback_data=f"cp_{oid}"),
                   InlineKeyboardButton("📸", callback_data=f"ss_{oid}"))
            kb.add(InlineKeyboardButton("🔙", callback_data="buy"))
            am.edit(f"⏳ <b>Pending</b>\nStatus: {status}", mark=kb)
        safe_answer(call); return

    if d.startswith('ss_'):
        oid = d.replace('ss_', '', 1)
        p = payments_col.find_one({"order_id": oid, "user_id": uid})
        if not p: safe_answer(call, "Not found", show_alert=True); return
        set_state(uid, {'state': 'waiting_ss', 'payment_id': str(p["_id"]),
                        'amount': p["amount"], 'credits': p["credits"], 'order_id': oid})
        bot.send_message(cid, "📸 Screenshot:", reply_to_message_id=call.message.message_id)
        safe_answer(call); return

    if d.startswith('ap_') and ObjectId.is_valid(d.replace('ap_', '')):
        if uid != ADMIN_ID: safe_answer(call, "Admin only", show_alert=True); return
        pid = d.replace('ap_', '', 1)
        ok, p = approve_atomic(pid, uid)
        if not ok:
            safe_answer(call, "⚠️ Already", show_alert=True)
            try: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=None)
            except: pass
            return
        add_credits(p["user_id"], p["credits"])
        safe_answer(call, f"✅ +{p['credits']}")
        try:
            if call.message.caption:
                bot.edit_message_caption(cid, call.message.message_id,
                    caption=call.message.caption + "\n\n✅ Approved", parse_mode='HTML', reply_markup=None)
            else:
                bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=None)
        except: pass
        try:
            bot.send_message(p["user_id"],
                f"✅ <b>Approved!</b>\n💎 +{p['credits']}\n💰 {get_credits(p['user_id'])}",
                parse_mode='HTML')
        except: pass
        return

    if d.startswith('rj_'):
        if uid != ADMIN_ID: safe_answer(call, "Admin only", show_alert=True); return
        pid = d.replace('rj_', '', 1)
        ok, p = reject_atomic(pid, uid)
        if not ok:
            safe_answer(call, "⚠️ Already", show_alert=True); return
        safe_answer(call, "❌ Rejected")
        try:
            if call.message.caption:
                bot.edit_message_caption(cid, call.message.message_id,
                    caption=call.message.caption + "\n\n❌ Rejected", parse_mode='HTML', reply_markup=None)
            else:
                bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=None)
        except: pass
        try: bot.send_message(p["user_id"], "❌ Rejected", parse_mode='HTML')
        except: pass
        return

    if d.startswith('pv_'):
        if uid != ADMIN_ID: safe_answer(call, "Admin only", show_alert=True); return
        pid = d.replace('pv_', '', 1)
        p = get_payment(pid)
        if not p: safe_answer(call, "Not found", show_alert=True); return
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("✅", callback_data=f"ap_{pid}"),
               InlineKeyboardButton("❌", callback_data=f"rj_{pid}"))
        mode = "⚡" if p.get("pay_mode") == "auto" else "📋"
        txt = (f"💰 <b>{mode}</b>\n\n👤 <code>{p['user_id']}</code>\n₹{p['amount']}\n"
               f"💎 {p['credits']}\nOrder: <code>{p.get('order_id') or 'N/A'}</code>")
        try: bot.edit_message_text(txt, cid, call.message.message_id, parse_mode='HTML', reply_markup=kb)
        except: pass
        safe_answer(call); return

    if d == "home":
        clear_state(uid)
        bot.send_message(cid, "🏠", reply_markup=main_kb(uid))
        safe_answer(call); return
    if d == "close":
        try: bot.delete_message(cid, call.message.message_id)
        except: pass
        safe_answer(call); return
    if d == "buy":
        t, kb = buy_kb()
        try: bot.edit_message_text(t, cid, call.message.message_id, parse_mode='HTML', reply_markup=kb)
        except: bot.send_message(cid, t, parse_mode='HTML', reply_markup=kb,
                                 reply_to_message_id=call.message.message_id)
        safe_answer(call); return
    if d.startswith("copyref_"):
        try: tgt = int(d.split("_")[1])
        except: safe_answer(call); return
        link = f"https://t.me/{BOT_USERNAME_CLEAN}?start=ref_{tgt}"
        bot.send_message(cid, f"📋 <code>{link}</code>", parse_mode='HTML')
        safe_answer(call); return

    safe_answer(call)


# ================= SHUTDOWN =================
def graceful_shutdown(signum, frame):
    logger.info("🛑 Shutting down...")
    try: bot.stop_polling()
    except: pass
    sys.exit(0)


signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


# ================= ENTRY =================
if __name__ == "__main__":
    init_db()
    manager = FJManager(bot)
    logger.info("🚀 Bot starting (v6)...")
    logger.info(f"👑 Admin: {ADMIN_ID}")
    logger.info(f"🎁 Welcome bonus: {get_setting('welcome_bonus', DEFAULT_WELCOME_BONUS)}cr")
    logger.info(f"🔎 Search cost: {get_setting('search_cost', DEFAULT_SEARCH_COST)}cr")
    logger.info(f"🔌 Auto UPI: {'ON' if is_auto_upi_available() else 'OFF'}")
    n_url, n_key = get_num_api()
    logger.info(f"🔎 Num API: {'ON' if n_url and n_key else 'OFF'}")
    a_url, a_key = get_aadhaar_api()
    logger.info(f"🆔 Aadhaar API: {'ON' if a_url and a_key else 'OFF'}")
    t_url, _ = get_tg2num_api()
    logger.info(f"🔒 TG2Num API: {'ON' if t_url else 'OFF'}")
    logger.info(f"💬 Groups: {total_groups()}")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        logger.critical(f"Crashed: {e}")
