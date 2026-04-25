"""Utility functions for dlshop - Jinja helpers, pricing, stock, cart logic."""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, get_url


# --------------------------------------------------------------------------- #
# Settings helper
# --------------------------------------------------------------------------- #

def get_settings():
    return frappe.get_cached_doc("DL Shop Settings")


def has_app_permission() -> bool:
    """Check if the current user has permission to access DL Shop."""
    from frappe.utils import modules as frappe_modules
    try:
        allowed = [m["module_name"] for m in frappe_modules.get_modules_from_all_apps_for_user()]
        if "Dlshop" not in allowed:
            return False
    except Exception:
        pass
    roles = frappe.get_roles()
    return any(r in roles for r in ["System Manager", "Sales Manager", "Sales User", "Administrator"])


# --------------------------------------------------------------------------- #
# Language helpers
# --------------------------------------------------------------------------- #

def get_current_lang():
    """Detect language from URL segment: /shop/ar → ar, /shop/en → en, /shop → en."""
    try:
        path = (frappe.local.request.path if getattr(frappe.local, "request", None) else "") or ""
    except Exception:
        path = ""
    parts = path.strip("/").split("/")
    if "ar" in parts:
        return "ar"
    return "en"


# Pages where lang goes AFTER the root: /shop/en, /shop/en/phones
_LANG_AFTER_ROOT = {"shop", "cart", "checkout", "search", "auth"}
# Pages where lang goes AT THE END: /account/orders/en, /contact/en
_LANG_AT_END = {"account", "contact", "privacy", "terms"}
_LOCALIZABLE_PAGES = _LANG_AFTER_ROOT | _LANG_AT_END


def localize_url(url, lang):
    """Inject lang segment into internal shop URLs.

    /shop → /shop/en           /shop/phones → /shop/en/phones   (lang after root)
    /account → /account/en     /account/orders → /account/orders/en  (lang at end)
    External URLs and unknown paths are returned unchanged.
    """
    if not url or not url.startswith("/"):
        return url
    path, _, qs = url.partition("?")
    parts = path.strip("/").split("/")
    if not parts or parts[0] not in _LOCALIZABLE_PAGES:
        return url
    root = parts[0]
    rest = parts[1:]
    if root in _LANG_AT_END:
        # Strip any existing lang segment (wherever it sits) then append
        rest = [p for p in rest if p not in ("ar", "en")]
        rest = rest + [lang]
    else:
        # Replace existing lang at position 0, or insert it there
        if rest and rest[0] in ("ar", "en"):
            rest[0] = lang
        else:
            rest = [lang] + rest
    result = "/" + "/".join([root] + rest)
    return result + "?" + qs if qs else result


def switch_lang_url(path):
    """Swap ar↔en in the current URL path for the language switcher."""
    parts = path.strip("/").split("/")
    new_parts = []
    replaced = False
    for p in parts:
        if p == "ar":
            new_parts.append("en")
            replaced = True
        elif p == "en":
            new_parts.append("ar")
            replaced = True
        else:
            new_parts.append(p)
    if not replaced:
        # No lang segment yet (e.g. plain /shop) — insert 'ar' after first segment
        new_parts = ([new_parts[0], "ar"] + new_parts[1:]) if new_parts else ["ar"]
    return "/" + "/".join(new_parts) if new_parts else "/"


def is_rtl(lang=None):
    return (lang or get_current_lang()) == "ar"


def bilingual(en_val, ar_val, lang=None):
    """Return AR value if lang is ar, else EN value."""
    lang = lang or get_current_lang()
    return ar_val if (lang == "ar" and ar_val) else (en_val or ar_val or "")


# --------------------------------------------------------------------------- #
# Pricing helpers
# --------------------------------------------------------------------------- #

def get_item_price(item_code, settings=None, qty=1):
    """Get item price from ERPNext price list. Returns 0 if not found."""
    if not settings:
        settings = get_settings()
    price_list = settings.default_price_list or "Standard Selling"
    try:
        price = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": price_list, "selling": 1},
            "price_list_rate",
        )
        return flt(price or 0)
    except Exception:
        return 0


def get_display_price(dl_item, settings=None):
    """Return (display_price, original_price, has_discount) for a DL Shop Item."""
    if not settings:
        settings = get_settings()
    base_price = flt(dl_item.custom_price) if dl_item.custom_price_enabled and dl_item.custom_price else get_item_price(dl_item.item_code, settings)
    if dl_item.sale_price and dl_item.is_on_sale:
        return flt(dl_item.sale_price), base_price, True
    return base_price, 0, False


def format_currency(amount, currency=None, settings=None):
    """Format currency for display using the official SAMA Saudi Riyal symbol (U+20C1)."""
    if not settings:
        settings = get_settings()
    currency = currency or settings.default_currency or "SAR"
    if currency == "SAR":
        return f"⃁ {flt(amount):,.2f}"  # U+20C1 — SAMA official Saudi Riyal sign, symbol left of amount
    return f"{currency} {flt(amount):,.2f}"


def currency(amount, cur=None, settings=None):
    """Jinja filter alias for format_currency."""
    return format_currency(amount, cur, settings)


# --------------------------------------------------------------------------- #
# Stock helpers
# --------------------------------------------------------------------------- #

def get_item_stock(item_code, warehouse=None, settings=None):
    """Returns actual stock qty. Returns -1 if warehouse not configured (treat as unlimited)."""
    if not warehouse:
        if not settings:
            settings = get_settings()
        warehouse = settings.default_warehouse
    if not warehouse:
        return -1  # unlimited
    try:
        stock = frappe.db.get_value(
            "Bin",
            {"item_code": item_code, "warehouse": warehouse},
            "actual_qty",
        )
        return flt(stock or 0)
    except Exception:
        return 0


def is_in_stock(item_code, warehouse=None, settings=None, dl_item=None):
    """Check availability — respects virtual stock if enabled on the DL Shop Item."""
    # Resolve DL Shop Item doc if not provided
    if dl_item is None:
        dl_item = frappe.db.get_value(
            "DL Shop Item",
            {"item_code": item_code, "is_published": 1},
            ["allow_virtual_stock", "virtual_stock_limit"],
            as_dict=True,
        ) or frappe._dict()

    if dl_item.get("allow_virtual_stock"):
        limit = (dl_item.get("virtual_stock_limit") or 0)
        if limit == 0:
            return True  # unlimited virtual stock
        # Count active pending/open Sales Order items for this item_code
        used = _count_active_virtual_orders(item_code)
        return used < limit

    qty = get_item_stock(item_code, warehouse, settings)
    return qty != 0  # -1 means unlimited, positive = in stock


def get_virtual_stock_remaining(item_code, dl_item=None):
    """Return remaining virtual stock (-1 = unlimited, 0 = none left, N = remaining)."""
    if dl_item is None:
        dl_item = frappe.db.get_value(
            "DL Shop Item",
            {"item_code": item_code, "is_published": 1},
            ["allow_virtual_stock", "virtual_stock_limit"],
            as_dict=True,
        ) or frappe._dict()

    if not dl_item.get("allow_virtual_stock"):
        return None  # not virtual — caller should use physical stock

    limit = (dl_item.get("virtual_stock_limit") or 0)
    if limit == 0:
        return -1  # unlimited

    used = _count_active_virtual_orders(item_code)
    return max(0, limit - used)


def _count_active_virtual_orders(item_code):
    """Sum qty from open Sales Orders for virtual stock counting."""
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(soi.qty), 0)
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE soi.item_code = %s
          AND so.docstatus = 1
          AND so.status NOT IN ('Completed', 'Cancelled')
        """,
        item_code,
    )
    return flt(result[0][0] if result else 0)


# --------------------------------------------------------------------------- #
# Variant helpers
# --------------------------------------------------------------------------- #

def get_item_variants(template_item_code):
    """Return list of published variants for a template item."""
    variants = frappe.get_all(
        "Item",
        filters={"variant_of": template_item_code, "disabled": 0},
        fields=["name", "item_name", "variant_of"],
    )
    result = []
    for v in variants:
        attrs = frappe.get_all(
            "Item Variant Attribute",
            filters={"parent": v.name},
            fields=["attribute", "attribute_value"],
        )
        v["attributes"] = attrs
        result.append(v)
    return result


def get_variant_attributes(template_item_code):
    """Return list of variant attributes with their possible values."""
    attrs = frappe.get_all(
        "Item Variant Attribute",
        filters={"parent": template_item_code},
        fields=["attribute"],
    )
    result = []
    for attr in attrs:
        values = frappe.get_all(
            "Item Attribute Value",
            filters={"parent": attr["attribute"]},
            fields=["attribute_value", "abbr"],
            order_by="idx",
        )
        result.append({"attribute": attr["attribute"], "values": values})
    return result


# --------------------------------------------------------------------------- #
# Cart helpers
# --------------------------------------------------------------------------- #

def get_cart_session_id():
    """Return user email (logged in) or session cookie ID."""
    try:
        user = frappe.session.user
    except Exception:
        return "guest"
    if user and user != "Guest":
        return user
    try:
        return frappe.session.sid or "guest"
    except Exception:
        return "guest"


def get_or_create_cart():
    """Get active cart for current session, or create one."""
    session_id = get_cart_session_id()
    existing = frappe.db.get_value(
        "DL Shop Cart",
        {"session_id": session_id, "status": "Active"},
        "name",
    )
    if existing:
        return frappe.get_doc("DL Shop Cart", existing)
    cart = frappe.get_doc(
        {
            "doctype": "DL Shop Cart",
            "session_id": session_id,
            "status": "Active",
        }
    )
    cart.insert(ignore_permissions=True)
    frappe.db.commit()
    return cart


def get_cart_count():
    """Return total item qty in active cart."""
    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart",
        {"session_id": session_id, "status": "Active"},
        "name",
    )
    if not cart_name:
        return 0
    result = frappe.db.sql(
        "SELECT SUM(qty) FROM `tabDL Shop Cart Item` WHERE parent = %s",
        cart_name,
    )
    return int(result[0][0] or 0) if result else 0


def recalculate_cart(cart):
    """Recalculate cart totals including coupon and shipping."""
    settings = get_settings()
    subtotal = 0
    for item in cart.items:
        if not item.rate:
            item.rate = get_item_price(item.item_code, settings)
        item.amount = flt(item.qty) * flt(item.rate)
        subtotal += item.amount
    cart.subtotal = subtotal
    # Apply coupon
    discount = 0
    if cart.coupon_code:
        discount = calculate_coupon_discount(cart.coupon_code, subtotal, cart.items)
    cart.coupon_discount = discount
    # Shipping
    cart.shipping_charge = flt(cart.shipping_charge or 0)
    cart.grand_total = subtotal - discount + cart.shipping_charge
    return cart


# --------------------------------------------------------------------------- #
# Coupon helpers
# --------------------------------------------------------------------------- #

def calculate_coupon_discount(coupon_code, subtotal, items):
    """Return discount amount for a coupon."""
    if not coupon_code:
        return 0
    coupon = frappe.db.get_value(
        "DL Shop Coupon",
        {"coupon_code": coupon_code, "is_active": 1},
        ["name", "discount_type", "discount_value", "minimum_order_amount", "maximum_discount_amount",
         "valid_from", "valid_to", "maximum_uses", "used_count", "applies_to"],
        as_dict=True,
    )
    if not coupon:
        return 0
    from frappe.utils import getdate, today
    if coupon.valid_from and getdate(coupon.valid_from) > getdate(today()):
        return 0
    if coupon.valid_to and getdate(coupon.valid_to) < getdate(today()):
        return 0
    if coupon.maximum_uses and coupon.used_count >= coupon.maximum_uses:
        return 0
    if coupon.minimum_order_amount and subtotal < flt(coupon.minimum_order_amount):
        return 0
    if coupon.discount_type == "Percentage":
        discount = subtotal * flt(coupon.discount_value) / 100
        if coupon.maximum_discount_amount:
            discount = min(discount, flt(coupon.maximum_discount_amount))
    else:
        discount = min(flt(coupon.discount_value), subtotal)
    return flt(discount)


def validate_coupon(coupon_code, subtotal):
    """Validate coupon and return status dict."""
    coupon = frappe.db.get_value(
        "DL Shop Coupon",
        {"coupon_code": coupon_code},
        ["name", "is_active", "discount_type", "discount_value", "minimum_order_amount",
         "valid_from", "valid_to", "maximum_uses", "used_count", "description_en", "description_ar"],
        as_dict=True,
    )
    if not coupon:
        return {"valid": False, "message": _("Invalid coupon code")}
    if not coupon.is_active:
        return {"valid": False, "message": _("This coupon is no longer active")}
    from frappe.utils import getdate, today
    if coupon.valid_from and getdate(coupon.valid_from) > getdate(today()):
        return {"valid": False, "message": _("This coupon is not yet valid")}
    if coupon.valid_to and getdate(coupon.valid_to) < getdate(today()):
        return {"valid": False, "message": _("This coupon has expired")}
    if coupon.maximum_uses and coupon.used_count >= coupon.maximum_uses:
        return {"valid": False, "message": _("This coupon has reached its usage limit")}
    if coupon.minimum_order_amount and subtotal < flt(coupon.minimum_order_amount):
        return {
            "valid": False,
            "message": _("Minimum order amount is {0}").format(format_currency(coupon.minimum_order_amount)),
        }
    discount = calculate_coupon_discount(coupon_code, subtotal, [])
    return {"valid": True, "discount": discount, "coupon": coupon}


# --------------------------------------------------------------------------- #
# Jinja template methods and filters
# --------------------------------------------------------------------------- #

def jinja_methods():
    return {
        "get_settings": get_settings,
        "get_current_lang": get_current_lang,
        "is_rtl": is_rtl,
        "bilingual": bilingual,
        "get_display_price": get_display_price,
        "format_currency": format_currency,
        "is_in_stock": is_in_stock,
        "get_cart_count": get_cart_count,
        "get_nav_items": get_nav_items,
        "get_footer_sections": get_footer_sections,
        "get_categories": get_categories,
        "get_hero_banners": get_hero_banners,
        "get_featured_items": get_featured_items,
    }


def jinja_filters():
    return {
        "currency": format_currency,
        "bilingual": bilingual,
    }


# --------------------------------------------------------------------------- #
# Navigation & layout helpers
# --------------------------------------------------------------------------- #

def get_nav_items(lang=None):
    """Return top-level nav items with children, URLs localized to lang."""
    if not lang:
        lang = get_current_lang()
    items = frappe.get_all(
        "DL Shop Navigation Item",
        filters={"is_active": 1, "parent_item": ["is", "not set"]},
        fields=["name", "label_en", "label_ar", "url", "icon_class", "open_in_new_tab"],
        order_by="sort_order asc",
    )
    for item in items:
        item["label"] = bilingual(item["label_en"], item["label_ar"], lang)
        item["url"] = localize_url(item["url"], lang)
        item["children"] = frappe.get_all(
            "DL Shop Navigation Item",
            filters={"is_active": 1, "parent_item": item["name"]},
            fields=["label_en", "label_ar", "url", "icon_class", "open_in_new_tab"],
            order_by="sort_order asc",
        )
        for child in item["children"]:
            child["label"] = bilingual(child["label_en"], child["label_ar"], lang)
            child["url"] = localize_url(child["url"], lang)
    return items


def get_footer_sections(lang=None):
    """Return footer sections with links, URLs localized to lang."""
    if not lang:
        lang = get_current_lang()
    sections = frappe.get_all(
        "DL Shop Footer Section",
        filters={"is_active": 1},
        fields=["name", "title_en", "title_ar"],
        order_by="sort_order asc",
    )
    for sec in sections:
        sec["title"] = bilingual(sec["title_en"], sec["title_ar"], lang)
        sec["links"] = frappe.get_all(
            "DL Shop Footer Link",
            filters={"parent": sec["name"]},
            fields=["label_en", "label_ar", "url", "open_in_new_tab"],
        )
        for link in sec["links"]:
            link["label"] = bilingual(link["label_en"], link["label_ar"], lang)
            link["url"] = localize_url(link["url"], lang)
    return sections


def get_categories(lang=None, published_only=True):
    """Return all categories for nav/sidebar."""
    filters = {"parent_category": ["is", "not set"]}
    if published_only:
        filters["is_published"] = 1
    categories = frappe.get_all(
        "DL Shop Category",
        filters=filters,
        fields=["name", "category_name_en", "category_name_ar", "route", "image", "icon_class"],
        order_by="sort_order asc",
    )
    for cat in categories:
        cat["name_display"] = bilingual(cat["category_name_en"], cat["category_name_ar"], lang)
        cat["children"] = frappe.get_all(
            "DL Shop Category",
            filters={"parent_category": cat["name"], "is_published": 1},
            fields=["name", "category_name_en", "category_name_ar", "route", "image"],
            order_by="sort_order asc",
        )
        for child in cat["children"]:
            child["name_display"] = bilingual(child["category_name_en"], child["category_name_ar"], lang)
    return categories


def get_hero_banners():
    """Return active hero banners ordered by sort_order."""
    return frappe.get_all(
        "DL Shop Banner",
        filters={"is_active": 1, "banner_type": "Hero"},
        fields=["name", "title_en", "title_ar", "subtitle_en", "subtitle_ar",
                "desktop_image", "mobile_image", "link", "button_text_en",
                "button_text_ar", "text_color", "overlay_opacity"],
        order_by="sort_order asc",
    )


def get_featured_items(limit=8, lang=None):
    """Return featured published items for homepage."""
    settings = get_settings()
    items = frappe.get_all(
        "DL Shop Item",
        filters={"is_published": 1, "is_featured": 1},
        fields=["name", "web_item_name_en", "web_item_name_ar", "featured_image",
                "route", "is_on_sale", "sale_price", "is_new_arrival", "item_code",
                "badge_text_en", "badge_text_ar"],
        order_by="sort_order asc",
        limit=limit,
    )
    for item in items:
        item["name_display"] = bilingual(item["web_item_name_en"], item["web_item_name_ar"], lang)
        item["badge"] = bilingual(item["badge_text_en"], item["badge_text_ar"], lang)
        price, orig, has_discount = get_display_price(frappe._dict(item), settings)
        item["price"] = price
        item["original_price"] = orig
        item["has_discount"] = has_discount
    return items


# --------------------------------------------------------------------------- #
# ERPNext master-data helpers
# --------------------------------------------------------------------------- #

def get_default_customer_group():
    """Return the first valid Customer Group, preferring common retail names."""
    for name in ("Individual", "Retail", "Wholesale", "All Customer Groups"):
        if frappe.db.exists("Customer Group", name):
            return name
    return frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "Individual"


# --------------------------------------------------------------------------- #
# Rate limiting helper
# --------------------------------------------------------------------------- #

def _rate_limit(key, limit=10, window=60):
    """
    Simple fixed-window rate limiter using Frappe's Redis cache.
    Raises frappe.ValidationError when the limit is exceeded.
    Falls back silently if Redis is unavailable so it never breaks the request.
    """
    try:
        import time
        ip = getattr(frappe.local, "request_ip", None) or "unknown"
        bucket = int(time.time() / window)
        cache_key = f"dl_rl:{key}:{ip}:{bucket}"
        count = (frappe.cache().get_value(cache_key) or 0) + 1
        frappe.cache().set_value(cache_key, count, expires_in_sec=window * 2)
        if count > limit:
            frappe.throw(_("Too many requests. Please try again later."))
    except frappe.ValidationError:
        raise
    except Exception:
        pass  # Never break the request if Redis/cache is unavailable
