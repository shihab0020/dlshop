"""Cart API - add/remove/update items, apply coupon, get cart summary."""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, cint

from dlshop.utils import (
    get_or_create_cart,
    get_cart_session_id,
    recalculate_cart,
    validate_coupon,
    get_item_price,
    is_in_stock,
    get_settings,
    get_cart_count,
)

_MAX_QTY = 999


@frappe.whitelist(allow_guest=True)
def get_cart():
    """Return full cart data."""
    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart", {"session_id": session_id, "status": "Active"}, "name"
    )
    if not cart_name:
        return {"items": [], "subtotal": 0, "grand_total": 0, "count": 0}
    cart = frappe.get_doc("DL Shop Cart", cart_name)
    return _cart_to_dict(cart)


@frappe.whitelist(allow_guest=True)
def add_to_cart(item_code, qty=1, variant_item_code=None):
    """Add item to cart. Uses variant_item_code if specified."""
    qty = max(1, min(_MAX_QTY, int(flt(qty) or 1)))
    target_item = variant_item_code or item_code
    if not frappe.db.exists("Item", target_item):
        frappe.throw(_("Item {0} not found").format(target_item))
    settings = get_settings()
    if not is_in_stock(target_item, settings.default_warehouse, settings):
        frappe.throw(_("Item is out of stock"))
    cart = get_or_create_cart()
    existing = next((i for i in cart.items if i.item_code == target_item), None)
    if existing:
        new_qty = min(_MAX_QTY, flt(existing.qty) + qty)
        existing.qty = new_qty
        existing.amount = new_qty * flt(existing.rate or get_item_price(target_item, settings))
    else:
        price = get_item_price(target_item, settings)
        image = frappe.db.get_value("Item", target_item, "image")
        cart.append(
            "items",
            {
                "item_code": target_item,
                "item_name": frappe.db.get_value("Item", target_item, "item_name"),
                "qty": qty,
                "rate": price,
                "amount": qty * price,
                "warehouse": settings.default_warehouse,
                "image": image,
            },
        )
    cart = recalculate_cart(cart)
    cart.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "cart": _cart_to_dict(cart), "count": get_cart_count()}


@frappe.whitelist(allow_guest=True)
def update_qty(item_code, qty):
    """Update quantity of an item in cart. qty=0 removes it."""
    qty = max(0, min(_MAX_QTY, flt(qty)))
    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart", {"session_id": session_id, "status": "Active"}, "name"
    )
    if not cart_name:
        frappe.throw(_("Cart not found"))
    cart = frappe.get_doc("DL Shop Cart", cart_name)
    if qty <= 0:
        cart.items = [i for i in cart.items if i.item_code != item_code]
    else:
        existing = next((i for i in cart.items if i.item_code == item_code), None)
        if existing:
            existing.qty = qty
            existing.amount = qty * flt(existing.rate)
        else:
            frappe.throw(_("Item not in cart"))
    cart = recalculate_cart(cart)
    cart.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "cart": _cart_to_dict(cart), "count": get_cart_count()}


@frappe.whitelist(allow_guest=True)
def remove_item(item_code):
    """Remove an item from cart."""
    return update_qty(item_code, 0)


@frappe.whitelist(allow_guest=True)
def apply_coupon(coupon_code):
    """Validate and apply a coupon to the cart."""
    coupon_code = str(coupon_code or "").strip()[:50]
    if not coupon_code:
        frappe.throw(_("Coupon code is required"))
    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart", {"session_id": session_id, "status": "Active"}, "name"
    )
    if not cart_name:
        frappe.throw(_("Cart not found"))
    cart = frappe.get_doc("DL Shop Cart", cart_name)
    result = validate_coupon(coupon_code, cart.subtotal or 0)
    if not result["valid"]:
        return {"success": False, "message": result["message"]}
    cart.coupon_code = coupon_code
    cart = recalculate_cart(cart)
    cart.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "success": True,
        "discount": cart.coupon_discount,
        "cart": _cart_to_dict(cart),
    }


@frappe.whitelist(allow_guest=True)
def remove_coupon():
    """Remove applied coupon."""
    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart", {"session_id": session_id, "status": "Active"}, "name"
    )
    if not cart_name:
        return {"success": True}
    cart = frappe.get_doc("DL Shop Cart", cart_name)
    cart.coupon_code = ""
    cart.coupon_discount = 0
    cart = recalculate_cart(cart)
    cart.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "cart": _cart_to_dict(cart)}


@frappe.whitelist(allow_guest=True)
def get_cart_count_api():
    """Lightweight endpoint to get cart item count."""
    return {"count": get_cart_count()}


def on_sales_order_submit(doc, method):
    """Mark cart as converted when Sales Order is submitted."""
    cart_name = frappe.db.get_value("DL Shop Cart", {"sales_order": doc.name}, "name")
    if cart_name:
        frappe.db.set_value("DL Shop Cart", cart_name, "status", "Converted")


def get_cart_permission_query(user):
    if not user:
        user = frappe.session.user
    session_id = user if user != "Guest" else frappe.session.sid
    return f"`tabDL Shop Cart`.`session_id` = {frappe.db.escape(session_id)}"


def _cart_to_dict(cart):
    settings = get_settings()

    # Batch fetch DL Shop Item data — avoids N+1 queries
    item_codes = [item.item_code for item in cart.items]
    dl_map = {}
    if item_codes:
        dl_data = frappe.get_all(
            "DL Shop Item",
            filters={"item_code": ["in", item_codes], "is_published": 1},
            fields=["item_code", "web_item_name_en", "web_item_name_ar", "route", "featured_image"],
        )
        dl_map = {d.item_code: d for d in dl_data}

    items = []
    for item in cart.items:
        dl = dl_map.get(item.item_code, frappe._dict())
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "rate": item.rate,
            "amount": item.amount,
            "image": item.image or dl.get("featured_image"),
            "route": dl.get("route"),
            "name_en": dl.get("web_item_name_en") or item.item_name,
            "name_ar": dl.get("web_item_name_ar") or item.item_name,
        })
    return {
        "name": cart.name,
        "items": items,
        "subtotal": cart.subtotal,
        "coupon_code": cart.coupon_code,
        "coupon_discount": cart.coupon_discount,
        "shipping_charge": cart.shipping_charge,
        "grand_total": cart.grand_total,
        "count": sum(i.qty for i in cart.items),
        "currency": settings.default_currency or "SAR",
    }
