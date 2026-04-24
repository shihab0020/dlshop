"""DL Shop visitor tracking — IP geolocation with Redis caching."""

import frappe
from frappe.utils import now_datetime

_GEO_TTL = 86400  # cache each IP's country for 24 hours
_PRIVATE_PREFIXES = ("10.", "172.16.", "192.168.", "127.", "::1", "localhost")


@frappe.whitelist(allow_guest=True)
def log_visit(page=None):
    """Record a page visit. Called from JS beacon (once per session per page)."""
    try:
        settings = frappe.get_cached_doc("DL Shop Settings")
        if not settings.enable_visitor_tracking:
            return {"ok": True}
        ip = _client_ip()
        if not ip:
            return {"ok": True}
        if not settings.track_private_ips and any(ip.startswith(p) for p in _PRIVATE_PREFIXES):
            return {"ok": True}
        geo = _geo_lookup(ip)
        frappe.get_doc({
            "doctype": "DL Shop Visitor Log",
            "timestamp":    now_datetime(),
            "ip_address":   ip[:45],
            "country":      geo.get("country", ""),
            "country_code": geo.get("countryCode", ""),
            "city":         geo.get("city", ""),
            "page":         (page or "")[:200],
            "user":         frappe.session.user if frappe.session.user != "Guest" else "",
            "session_id":   (frappe.session.sid or "")[:100],
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass
    return {"ok": True}


def log_order(sales_order):
    """Attach IP + country to an order. Called internally from checkout."""
    try:
        settings = frappe.get_cached_doc("DL Shop Settings")
        if not settings.enable_visitor_tracking:
            return
        ip = _client_ip()
        if not ip:
            return
        if not settings.track_private_ips and any(ip.startswith(p) for p in _PRIVATE_PREFIXES):
            return
        geo = _geo_lookup(ip)
        frappe.get_doc({
            "doctype": "DL Shop Visitor Log",
            "timestamp":    now_datetime(),
            "ip_address":   ip[:45],
            "country":      geo.get("country", ""),
            "country_code": geo.get("countryCode", ""),
            "city":         geo.get("city", ""),
            "page":         "/checkout",
            "sales_order":  sales_order,
            "user":         frappe.session.user if frappe.session.user != "Guest" else "",
            "session_id":   (frappe.session.sid or "")[:100],
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass


def _client_ip():
    """Return real client IP respecting reverse-proxy headers."""
    try:
        req = frappe.local.request
        xff = req.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return req.headers.get("X-Real-IP") or getattr(req, "remote_addr", "") or ""
    except Exception:
        return ""


def _geo_lookup(ip):
    """Return {country, countryCode, city} for an IP. Cached in Redis 24 h."""
    cache_key = f"dlshop_geo:{ip}"
    try:
        cached = frappe.cache().get_value(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    result = {}
    try:
        import requests as _req
        resp = _req.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,countryCode,city"},
            timeout=3,
        )
        data = resp.json()
        if data.get("status") == "success":
            result = {
                "country":     data.get("country", ""),
                "countryCode": data.get("countryCode", ""),
                "city":        data.get("city", ""),
            }
    except Exception:
        pass

    try:
        frappe.cache().set_value(cache_key, result, expires_in_sec=_GEO_TTL)
    except Exception:
        pass

    return result
