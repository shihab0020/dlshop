"""Account API - wishlist, orders, profile, newsletter."""

import frappe
from frappe import _
from frappe.utils import now_datetime, validate_email_address, cint

from dlshop.utils import get_settings


@frappe.whitelist()
def get_orders(page=1, page_size=10):
    """Return current user's orders (Sales Orders)."""
    page = max(1, cint(page) or 1)
    page_size = min(50, max(1, cint(page_size) or 10))
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if not customer:
        return {"orders": [], "total": 0}
    orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer, "docstatus": 1},
        fields=["name", "transaction_date", "grand_total", "status", "delivery_status", "currency"],
        order_by="transaction_date desc",
        start=(page - 1) * page_size,
        page_length=page_size,
    )
    total = frappe.db.count("Sales Order", {"customer": customer, "docstatus": 1})
    return {"orders": orders, "total": total, "page": page, "page_size": page_size}


@frappe.whitelist()
def get_order_detail(order_id):
    """Return full details of a specific order."""
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if not customer:
        return None
    order = frappe.db.get_value(
        "Sales Order", {"name": order_id, "customer": customer, "docstatus": 1}, "name"
    )
    if not order:
        return None
    so = frappe.get_doc("Sales Order", order)

    # Batch fetch DL Shop Item data — avoids N+1 queries
    item_codes = [item.item_code for item in so.items]
    dl_map = {}
    if item_codes:
        dl_data = frappe.get_all(
            "DL Shop Item",
            filters={"item_code": ["in", item_codes]},
            fields=["item_code", "featured_image", "route"],
        )
        dl_map = {d.item_code: d for d in dl_data}

    items = []
    for item in so.items:
        dl = dl_map.get(item.item_code, frappe._dict())
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "rate": item.rate,
            "amount": item.amount,
            "image": dl.get("featured_image"),
            "route": dl.get("route"),
        })
    return {
        "name": so.name,
        "date": so.transaction_date,
        "status": so.status,
        "delivery_status": so.delivery_status,
        "grand_total": so.grand_total,
        "currency": so.currency,
        "items": items,
    }


@frappe.whitelist()
def toggle_wishlist(item_route):
    """Add to wishlist if not there, remove if already there."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to use wishlist"))
    if not frappe.db.exists("DL Shop Item", {"route": item_route, "is_published": 1}):
        frappe.throw(_("Product not found"))
    item_name = frappe.db.get_value("DL Shop Item", {"route": item_route}, "name")
    existing = frappe.db.get_value(
        "DL Shop Wishlist Item",
        {"item_route": item_name, "owner": frappe.session.user},
        "name",
    )
    if existing:
        frappe.delete_doc("DL Shop Wishlist Item", existing, ignore_permissions=True)
        frappe.db.sql(
            "UPDATE `tabDL Shop Item` SET wishlist_count = GREATEST(0, wishlist_count - 1) WHERE name = %s",
            item_name,
        )
        frappe.db.commit()
        return {"wishlisted": False}
    wl = frappe.get_doc({
        "doctype": "DL Shop Wishlist Item",
        "item_route": item_name,
        "item_code": frappe.db.get_value("DL Shop Item", item_name, "item_code"),
        "added_on": now_datetime(),
    })
    wl.insert(ignore_permissions=True)
    frappe.db.sql(
        "UPDATE `tabDL Shop Item` SET wishlist_count = wishlist_count + 1 WHERE name = %s",
        item_name,
    )
    frappe.db.commit()
    return {"wishlisted": True}


@frappe.whitelist()
def get_wishlist():
    """Return current user's wishlist with product details."""
    if frappe.session.user == "Guest":
        return []
    settings = get_settings()
    from dlshop.utils import get_display_price, bilingual, get_current_lang
    lang = get_current_lang()
    wl_items = frappe.get_all(
        "DL Shop Wishlist Item",
        filters={"owner": frappe.session.user},
        fields=["name", "item_route", "item_code", "added_on"],
        order_by="added_on desc",
    )
    if not wl_items:
        return []

    # Batch fetch DL Shop Item data — avoids N+1 queries
    item_names = [wl.item_route for wl in wl_items]
    items_data = frappe.get_all(
        "DL Shop Item",
        filters={"name": ["in", item_names], "is_published": 1},
        fields=["name", "web_item_name_en", "web_item_name_ar", "featured_image", "route",
                "is_on_sale", "sale_price", "custom_price", "custom_price_enabled"],
    )
    items_map = {i.name: i for i in items_data}

    result = []
    for wl in wl_items:
        item = items_map.get(wl.item_route)
        if not item:
            continue
        price, orig, has_discount = get_display_price(item, settings)
        result.append({
            "wl_name": wl.name,
            "item_route": wl.item_route,
            "item_code": wl.item_code,
            "name_en": item.web_item_name_en,
            "name_ar": item.web_item_name_ar,
            "name_display": bilingual(item.web_item_name_en, item.web_item_name_ar, lang),
            "image": item.featured_image,
            "route": item.route,
            "price": price,
            "original_price": orig,
            "has_discount": has_discount,
        })
    return result


@frappe.whitelist()
def is_wishlisted(item_route):
    if frappe.session.user == "Guest":
        return False
    item_name = frappe.db.get_value("DL Shop Item", {"route": item_route}, "name")
    if not item_name:
        return False
    return bool(frappe.db.exists(
        "DL Shop Wishlist Item",
        {"item_route": item_name, "owner": frappe.session.user},
    ))


@frappe.whitelist(allow_guest=True)
def subscribe_newsletter(email, full_name=None, lang="en"):
    """Subscribe to newsletter."""
    from dlshop.utils import _rate_limit
    _rate_limit("newsletter", limit=5, window=300)

    email = (email or "").strip().lower()[:200]
    if not email or not validate_email_address(email):
        return {"success": False, "message": _("Invalid email address")}

    full_name = (full_name or "").strip()[:100]
    lang = lang if lang in ("ar", "en") else "en"

    if frappe.db.exists("DL Shop Newsletter Subscriber", {"email": email}):
        sub = frappe.get_doc("DL Shop Newsletter Subscriber", email)
        if not sub.is_active:
            sub.is_active = 1
            sub.save(ignore_permissions=True)
            frappe.db.commit()
        return {"success": True, "already_subscribed": True}
    sub = frappe.get_doc({
        "doctype": "DL Shop Newsletter Subscriber",
        "email": email,
        "full_name": full_name,
        "language_preference": lang,
        "is_active": 1,
        "subscribed_on": now_datetime(),
    })
    sub.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "already_subscribed": False}


@frappe.whitelist()
def get_profile():
    """Return current user profile data."""
    user = frappe.get_doc("User", frappe.session.user)
    customer = frappe.db.get_value(
        "Customer", {"email_id": frappe.session.user},
        ["name", "customer_name", "mobile_no"],
        as_dict=True,
    )
    return {
        "email": user.email,
        "full_name": user.full_name,
        "mobile_no": user.mobile_no or (customer.mobile_no if customer else ""),
        "customer_name": customer.customer_name if customer else user.full_name,
    }


@frappe.whitelist()
def update_profile(full_name, mobile_no=None):
    """Update user display name and phone."""
    full_name = (full_name or "").strip()[:100]
    if not full_name:
        frappe.throw(_("Name is required"))
    if mobile_no:
        mobile_no = str(mobile_no).strip()[:30]

    user = frappe.get_doc("User", frappe.session.user)
    user.full_name = full_name
    if mobile_no:
        user.mobile_no = mobile_no
    user.save(ignore_permissions=True)
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if customer:
        frappe.db.set_value("Customer", customer, "customer_name", full_name)
        if mobile_no:
            frappe.db.set_value("Customer", customer, "mobile_no", mobile_no)
    frappe.db.commit()
    return {"success": True}


def get_wishlist_permission_query(user):
    if not user:
        user = frappe.session.user
    return f"`tabDL Shop Wishlist Item`.`owner` = {frappe.db.escape(user)}"


def get_newsletter_permission_query(user):
    if not user:
        user = frappe.session.user
    if frappe.session.user == "Guest":
        return "1=0"
    return f"`tabDL Shop Newsletter Subscriber`.`email` = {frappe.db.escape(user)}"
