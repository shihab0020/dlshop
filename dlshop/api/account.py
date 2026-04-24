"""Account API - wishlist, orders, profile, newsletter."""

import frappe
from frappe import _
from frappe.utils import now_datetime, validate_email_address, cint

from dlshop.utils import get_settings


@frappe.whitelist()
def get_orders(page=1, page_size=10):
    """Return current user's orders with approval status if applicable."""
    page = max(1, cint(page) or 1)
    page_size = min(50, max(1, cint(page_size) or 10))
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if not customer:
        return {"orders": [], "total": 0}
    orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer, "docstatus": ["in", [1, 2]]},
        fields=["name", "transaction_date", "grand_total", "status", "delivery_status", "currency", "docstatus"],
        order_by="creation desc",
        start=(page - 1) * page_size,
        page_length=page_size,
    )
    total = frappe.db.count("Sales Order", {"customer": customer, "docstatus": ["in", [1, 2]]})

    # Batch fetch approval records for all orders in this page
    if orders:
        order_names = [o.name for o in orders]
        approvals = frappe.get_all(
            "DL Shop Order Approval",
            filters={"sales_order": ["in", order_names]},
            fields=["sales_order", "approval_status"],
        )
        approval_map = {a.sales_order: a.approval_status for a in approvals}
        for o in orders:
            o["approval_status"] = approval_map.get(o.name)

    settings = get_settings()
    return {
        "orders": orders,
        "total": total,
        "page": page,
        "page_size": page_size,
        "allow_cancellation": bool(settings.allow_order_cancellation),
        "require_cancel_approval": bool(settings.require_cancel_approval),
        "cancellation_window_hours": settings.cancellation_window_hours or 0,
    }


@frappe.whitelist()
def get_order_detail(order_id):
    """Return full details of a specific order."""
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if not customer:
        return None
    order = frappe.db.get_value(
        "Sales Order", {"name": order_id, "customer": customer, "docstatus": ["in", [1, 2]]}, "name"
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
    # Approval status (present only when approval workflow was used for this order)
    approval = frappe.db.get_value(
        "DL Shop Order Approval",
        {"sales_order": so.name},
        ["approval_status", "payment_method", "rejection_reason"],
        as_dict=True,
    )

    return {
        "name": so.name,
        "date": so.transaction_date,
        "status": so.status,
        "delivery_status": so.delivery_status,
        "grand_total": so.grand_total,
        "currency": so.currency,
        "items": items,
        "approval_status": approval.approval_status if approval else None,
        "payment_method": (approval.payment_method or "").upper() if approval else None,
        "rejection_reason": approval.rejection_reason if approval else None,
        **_can_cancel_order(so, approval),
    }


@frappe.whitelist()
def cancel_order(order_id):
    """Directly cancel an order (used when require_cancel_approval is disabled)."""
    settings = get_settings()
    if not settings.allow_order_cancellation:
        frappe.throw(_("Order cancellation is not enabled"))
    if settings.require_cancel_approval:
        frappe.throw(_("Please use the cancellation request instead"))

    so_doc = _get_owned_order(order_id)
    _assert_cancellable(so_doc, settings)

    # Mark approval record as rejected if present
    approval = frappe.db.get_value(
        "DL Shop Order Approval", {"sales_order": so_doc.name}, ["name", "approval_status"], as_dict=True
    )
    if approval:
        if approval.approval_status == "Pending" and not settings.cancel_pending_approval:
            frappe.throw(_("Orders awaiting approval cannot be cancelled"))
        frappe.db.set_value("DL Shop Order Approval", approval.name, {
            "approval_status": "Rejected",
            "rejection_reason": "Cancelled by customer",
        })

    so_doc.flags.ignore_permissions = True
    so_doc.cancel()
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def request_cancel_order(order_id, reason=None):
    """Submit a cancellation request (used when require_cancel_approval is enabled)."""
    settings = get_settings()
    if not settings.allow_order_cancellation:
        frappe.throw(_("Order cancellation is not enabled"))

    so_doc = _get_owned_order(order_id)
    _assert_cancellable(so_doc, settings)

    # Prevent duplicate requests
    existing = frappe.db.get_value(
        "DL Shop Cancel Request", {"sales_order": so_doc.name, "status": "Pending"}, "name"
    )
    if existing:
        frappe.throw(_("A cancellation request is already pending for this order"))

    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    frappe.get_doc({
        "doctype": "DL Shop Cancel Request",
        "sales_order": so_doc.name,
        "customer": customer or "",
        "customer_email": frappe.session.user,
        "reason": (reason or "").strip()[:500],
        "status": "Pending",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True}


def _get_owned_order(order_id):
    """Fetch a submitted Sales Order that belongs to the current user."""
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if not customer:
        frappe.throw(_("Customer not found"))
    name = frappe.db.get_value(
        "Sales Order", {"name": order_id, "customer": customer, "docstatus": 1}, "name"
    )
    if not name:
        frappe.throw(_("Order not found"))
    return frappe.get_doc("Sales Order", name)


def _assert_cancellable(so_doc, settings):
    """Raise if the order is not in a cancellable state."""
    if so_doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("This order cannot be cancelled"))
    window_hours = settings.cancellation_window_hours or 0
    if window_hours > 0:
        from frappe.utils import get_datetime, now_datetime as _now
        age_seconds = (_now() - get_datetime(so_doc.creation)).total_seconds()
        if age_seconds > window_hours * 3600:
            frappe.throw(_("Cancellation window has expired"))


def _can_cancel_order(so, approval):
    """Return cancel capability flags for the order detail page."""
    try:
        settings = get_settings()
        if not settings.allow_order_cancellation:
            return {"direct": False, "request": False, "cancel_request_status": None}
        if so.docstatus != 1 or so.status in ("Completed", "Cancelled"):
            return {"direct": False, "request": False, "cancel_request_status": None}

        window_hours = settings.cancellation_window_hours or 0
        if window_hours > 0:
            from frappe.utils import get_datetime, now_datetime as _now
            if (_now() - get_datetime(so.creation)).total_seconds() > window_hours * 3600:
                return {"direct": False, "request": False, "cancel_request_status": None}

        if approval and approval.approval_status == "Pending" and not settings.cancel_pending_approval:
            return {"direct": False, "request": False, "cancel_request_status": None}

        # Check for existing cancel request
        cancel_req = frappe.db.get_value(
            "DL Shop Cancel Request", {"sales_order": so.name}, "status"
        )
        require_approval = bool(settings.require_cancel_approval)

        if require_approval:
            return {
                "direct": False,
                "request": not cancel_req or cancel_req == "Denied",
                "cancel_request_status": cancel_req,
            }
        return {
            "direct": True,
            "request": False,
            "cancel_request_status": cancel_req,
        }
    except Exception:
        return {"direct": False, "request": False, "cancel_request_status": None}


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
