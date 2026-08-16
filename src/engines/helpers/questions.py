import re
import base64
import json
import requests

from .constants import (
    BAD_EXT,
    SUSPICIOUS_EXT,
    TRACKING_PARAMS,
    PROMOTIONAL_PARAMS,
    UNSUBSCRIBE_PARAMS,
    HIGH_RISK_KEYWORDS,
    URL_SHORTENERS,
    GROQ_SECURITY_SYSTEM_PROMPT
)
from src.network import network

def has_unsubscribe_header(msg):
    return 'list-unsubscribe' in msg.headers

def has_malware(msg):
    if msg.attachments:
        return any(att.filename.lower().endswith(BAD_EXT) for att in msg.attachments)
    return False

def has_suspicious_docs(msg) -> bool:
    if msg.attachments:
        return any(att.filename.lower().endswith(SUSPICIOUS_EXT) for att in msg.attachments)
    return False

def has_spy_pixel(msg):
    html_body = msg.html.lower() if msg.html else ""
    if not html_body or "<img" not in html_body:
        return False

    for tag in re.findall(r"<img[^>]+>", html_body):
        if "src=" in tag and any(param in tag for param in TRACKING_PARAMS):
            return True

        has_attr_width = re.search(r'\bwidth\s*=\s*["\']?[01](px)?["\']?', tag)
        has_attr_height = re.search(r'\bheight\s*=\s*["\']?[01](px)?["\']?', tag)

        has_css_width = re.search(r'\bwidth\s*:\s*[01](px)?\b', tag)
        has_css_height = re.search(r'\bheight\s*:\s*[01](px)?\b', tag)

        if (has_attr_width or has_css_width) and (has_attr_height or has_css_height):
            return True

    return False

@network.online
def has_malevolent_text(msg, vt_groq_data: dict) -> bool:
    groq_url = "https://api.groq.com/openai/v1/chat/completions"

    vt_key = vt_groq_data.get("vt_api_key", "")
    groq_key = vt_groq_data.get("groq_api_key", "")

    body = msg.text if msg.text else ""
    if not body and msg.html:
        body = re.sub(r'<[^>]+>', '', msg.html)
    if not body.strip():
        return False

    body_lower = body.lower()
    score = 0

    urls = re.findall(r'https?://[^\s<>"\']+', body)
    for url in urls:
        if any(shortener in url for shortener in URL_SHORTENERS):
            score += 25
        if any(trigger in url for trigger in ["login", "verify", "secure", "update"]):
            score += 15

    for keyword, value in HIGH_RISK_KEYWORDS.items():
        if keyword in body_lower:
            score += value

    if score < 30:
        return False
    if score >= 80:
        return True

    if urls and vt_key:
        for url in urls[:3]:
            try:
                url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
                headers = {"x-apikey": vt_key}
                response = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers, timeout=4)
                if response.status_code == 200:
                    stats = response.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    if stats.get("malicious", 0) > 1 or stats.get("phishing", 0) > 1:
                        return True
            except Exception:
                pass

    if groq_key:
        payload = {
            "model": "llama-3.1-8b-instant",
            "response_format": {"type": "json_object"},
            "max_tokens": 15,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "system",
                    "content": GROQ_SECURITY_SYSTEM_PROMPT
                },
                {"role": "user", "content": body[:1500]}
            ]
        }

        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }

        max_retries = 2
        for attempt in range(max_retries):
            try:
                res = requests.post(groq_url, json=payload, headers=headers, timeout=5)
                if res.status_code == 200:
                    res_json = json.loads(res.json()["choices"][0]["message"]["content"])
                    return bool(res_json.get("is_malevolent", False))
            except (requests.RequestException, KeyError, IndexError, ValueError):
                if attempt == max_retries - 1:
                    pass
                continue

    return False

def is_promotional(msg):
    for param in PROMOTIONAL_PARAMS:
        if param in msg.headers:
            return True

    precedence = msg.headers.get("precedence", [])
    if any(p.lower() in ["bulk", "list", "junk"] for p in precedence):
        return True

    body = (msg.text or "") + (msg.html or "")
    body_lower = body.lower()
    for param in UNSUBSCRIBE_PARAMS:
        if re.search(param, body_lower):
            return True

    return False

def is_expired(msg, max_days):
    email_date = msg.date
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc) if email_date.tzinfo else datetime.now()
    return (now - email_date).days > max_days

def is_only_text(msg):
    return not bool(msg.attachments)
