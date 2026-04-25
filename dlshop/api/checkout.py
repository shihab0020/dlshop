"""Checkout API - address, shipping, place order, payment initiation."""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, validate_email_address

from dlshop.utils import get_settings, get_cart_session_id, recalculate_cart, get_or_create_cart, get_default_customer_group

_ALLOWED_PAYMENT_METHODS = {"cod", "tabby"}
_ALLOWED_FULFILLMENT = {"delivery", "pickup"}


@frappe.whitelist(allow_guest=True)
def get_checkout_data():
    """Return cart + addresses + shipping rules for checkout page."""
    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart", {"session_id": session_id, "status": "Active"}, "name"
    )
    if not cart_name:
        return {"empty": True}
    cart = frappe.get_doc("DL Shop Cart", cart_name)
    if not cart.items:
        return {"empty": True}

    settings = get_settings()
    customer = _get_or_create_customer()
    addresses = _get_addresses(customer)
    shipping_rules = _get_shipping_rules()

    return {
        "cart": _cart_summary(cart, settings),
        "addresses": addresses,
        "shipping_rules": shipping_rules,
        "payment_methods": _get_payment_methods(settings),
        "guest": frappe.session.user == "Guest",
        "customer": customer,
        "pickup_enabled": bool(settings.pickup_enabled),
        "pickup_locations": _get_pickup_locations() if settings.pickup_enabled else [],
    }


@frappe.whitelist(allow_guest=True)
def save_address(
    address_title,
    address_line1,
    address_line2=None,
    city=None,
    state=None,
    country="Saudi Arabia",
    pincode=None,
    phone=None,
    address_type="Shipping",
    address_name=None,
):
    """Create or update a customer address."""
    # Sanitize inputs
    address_title = (address_title or "").strip()[:200]
    address_line1 = (address_line1 or "").strip()[:300]
    if not address_title or not address_line1:
        frappe.throw(_("Address title and address line are required"))

    address_line2 = (address_line2 or "").strip()[:300]
    city = (city or "").strip()[:100]
    state = (state or "").strip()[:100]
    country = (country or "Saudi Arabia").strip()[:100]
    pincode = (pincode or "").strip()[:20]
    phone = (phone or "").strip()[:30]
    address_type = address_type if address_type in ("Shipping", "Billing", "Office", "Personal") else "Shipping"

    customer = _get_or_create_customer()

    if address_name and frappe.db.exists("Address", address_name):
        # Verify the address belongs to the current customer before editing
        if customer and not frappe.db.exists("Dynamic Link", {
            "link_doctype": "Customer",
            "link_name": customer,
            "parent": address_name,
            "parenttype": "Address",
        }):
            frappe.throw(_("Not authorized to edit this address"), frappe.PermissionError)
        addr = frappe.get_doc("Address", address_name)
    else:
        addr = frappe.new_doc("Address")
        addr.address_title = address_title
        addr.address_type = address_type

    addr.address_line1 = address_line1
    addr.address_line2 = address_line2
    addr.city = city
    addr.state = state
    addr.country = country
    addr.pincode = pincode
    addr.phone = phone

    if not addr.name:
        addr.insert(ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Dynamic Link",
            "parent": addr.name,
            "parenttype": "Address",
            "parentfield": "links",
            "link_doctype": "Customer",
            "link_name": customer,
        }).insert(ignore_permissions=True)
    else:
        addr.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "address_name": addr.name}


@frappe.whitelist(allow_guest=True)
def apply_shipping_rule(shipping_rule_name):
    """Apply a shipping rule to the active cart."""
    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart", {"session_id": session_id, "status": "Active"}, "name"
    )
    if not cart_name:
        frappe.throw(_("Cart not found"))

    # Validate shipping rule exists and is enabled
    if shipping_rule_name:
        shipping_rule_name = str(shipping_rule_name).strip()[:140]
        if not frappe.db.exists("Shipping Rule", {"name": shipping_rule_name, "disabled": 0}):
            frappe.throw(_("Invalid shipping rule"))

    cart = frappe.get_doc("DL Shop Cart", cart_name)
    charge = 0
    if shipping_rule_name:
        conditions = frappe.get_all(
            "Shipping Rule Condition",
            filters={"parent": shipping_rule_name},
            fields=["from_value", "to_value", "shipping_amount"],
            order_by="from_value asc",
        )
        for cond in conditions:
            if flt(cart.subtotal) >= flt(cond.from_value or 0):
                if not cond.to_value or flt(cart.subtotal) <= flt(cond.to_value):
                    charge = flt(cond.shipping_amount)
                    break
    cart.shipping_rule = shipping_rule_name
    cart.shipping_charge = charge
    cart = recalculate_cart(cart)
    cart.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "shipping_charge": charge, "grand_total": cart.grand_total}


@frappe.whitelist(allow_guest=True)
def place_order(
    billing_address=None,
    shipping_address=None,
    payment_method="cod",
    notes=None,
    guest_name=None,
    guest_email=None,
    guest_phone=None,
    fulfillment_type="delivery",
    pickup_location=None,
):
    """Convert cart to Sales Order and return order info."""
    settings = get_settings()

    # Validate enum-like inputs
    payment_method = payment_method if payment_method in _ALLOWED_PAYMENT_METHODS else "cod"
    fulfillment_type = fulfillment_type if fulfillment_type in _ALLOWED_FULFILLMENT else "delivery"

    # Sanitize free-text inputs
    notes = str(notes).strip()[:500] if notes else ""

    session_id = get_cart_session_id()
    cart_name = frappe.db.get_value(
        "DL Shop Cart", {"session_id": session_id, "status": "Active"}, "name"
    )
    if not cart_name:
        frappe.throw(_("Your cart is empty"))

    # Atomically flip status to 'Processing' so a double-submit can't create
    # two Sales Orders from the same cart.
    frappe.db.sql(
        "UPDATE `tabDL Shop Cart` SET status='Processing' WHERE name=%s AND status='Active'",
        cart_name,
    )
    if not frappe.db.sql("SELECT ROW_COUNT()")[0][0]:
        frappe.throw(_("Your order is already being processed. Please wait."))

    cart = frappe.get_doc("DL Shop Cart", cart_name)
    if not cart.items:
        frappe.db.set_value("DL Shop Cart", cart_name, "status", "Active")
        frappe.throw(_("Your cart is empty"))

    if frappe.session.user == "Guest":
        guest_email = (guest_email or "").strip()[:200]
        if not guest_email or not validate_email_address(guest_email):
            frappe.throw(_("A valid email is required for guest checkout"))
        guest_name = (guest_name or "").strip()[:100]
        guest_phone = (guest_phone or "").strip()[:30]
        customer = _get_or_create_guest_customer(guest_name, guest_email, guest_phone)
    else:
        customer = _get_or_create_customer()

    cost_center = settings.default_cost_center or _get_default_cost_center()

    terms = ""
    if fulfillment_type == "pickup" and pickup_location:
        pickup_location = str(pickup_location).strip()[:140]
        loc = frappe.db.get_value(
            "DL Shop Pickup Location",
            pickup_location,
            ["location_name_en", "address_en", "phone", "working_hours_en"],
            as_dict=True,
        )
        if loc:
            terms = (
                f"PICKUP ORDER\nLocation: {loc.location_name_en}\n"
                f"Address: {loc.address_en or ''}\nPhone: {loc.phone or ''}\n"
                f"Hours: {loc.working_hours_en or ''}"
            )

    so = frappe.get_doc({
        "doctype": "Sales Order",
        "customer": customer,
        "transaction_date": frappe.utils.today(),
        "delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
        "price_list": settings.default_price_list or "Standard Selling",
        "currency": settings.default_currency or "SAR",
        "customer_address": billing_address if fulfillment_type == "delivery" else None,
        "shipping_address_name": shipping_address if fulfillment_type == "delivery" else None,
        "taxes_and_charges": settings.default_tax_template,
        "cost_center": cost_center,
        "po_no": f"DLSHOP-{cart_name[:8]}",
        "terms": terms,
        "items": [],
    })
    for item in cart.items:
        so.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "rate": item.rate,
            "warehouse": item.warehouse or settings.default_warehouse,
            "cost_center": cost_center,
        })

    if cart.shipping_charge and cart.shipping_charge > 0:
        so.append("taxes", {
            "charge_type": "Actual",
            "account_head": _get_shipping_account(),
            "description": "Shipping Charge",
            "tax_amount": cart.shipping_charge,
        })

    if payment_method == "cod" and settings.cod_charge and settings.cod_charge > 0:
        so.append("taxes", {
            "charge_type": "Actual",
            "account_head": _get_shipping_account(),
            "description": "Cash on Delivery Charge",
            "tax_amount": settings.cod_charge,
        })

    try:
        so.insert(ignore_permissions=True)
        so.submit()
    except Exception:
        # Release the cart lock so the user can retry
        frappe.db.set_value("DL Shop Cart", cart_name, "status", "Active")
        frappe.db.commit()
        raise

    # Log visitor country for geo analytics (best-effort, never raises)
    try:
        from dlshop.api.analytics import log_order as _log_order
        _log_order(so.name)
    except Exception:
        pass

    frappe.db.set_value("DL Shop Cart", cart_name, {
        "sales_order": so.name,
        "status": "Converted",
        "notes": notes,
    })

    if cart.coupon_code:
        frappe.db.sql(
            "UPDATE `tabDL Shop Coupon` SET used_count = used_count + 1 WHERE coupon_code = %s",
            cart.coupon_code,
        )

    for item in cart.items:
        dl_item = frappe.db.get_value("DL Shop Item", {"item_code": item.item_code}, "name")
        if dl_item:
            frappe.db.sql(
                "UPDATE `tabDL Shop Item` SET purchase_count = purchase_count + 1 WHERE name = %s",
                dl_item,
            )

    frappe.db.commit()

    # Order Approval workflow (optional, controlled by DL Shop Settings)
    if settings.enable_order_approval:
        frappe.get_doc({
            "doctype": "DL Shop Order Approval",
            "sales_order": so.name,
            "customer": customer,
            "customer_email": frappe.session.user if frappe.session.user != "Guest" else (guest_email or ""),
            "payment_method": payment_method.upper(),
            "grand_total": so.grand_total,
            "approval_status": "Pending",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        return {
            "success": True,
            "order_id": so.name,
            "grand_total": so.grand_total,
            "payment_method": payment_method,
            "approval_required": True,
        }

    if payment_method == "tabby":
        redirect_url = _create_tabby_payment_request(so)
        if redirect_url:
            return {
                "success": True,
                "order_id": so.name,
                "payment_method": "tabby",
                "redirect_url": redirect_url,
            }
        frappe.log_error("Tabby session creation returned no URL", "Tabby")

    return {
        "success": True,
        "order_id": so.name,
        "grand_total": so.grand_total,
        "payment_method": payment_method,
    }


@frappe.whitelist(allow_guest=True)
def get_payment_url(order_name):
    """Called after approval — initiate payment for an approved order."""
    order_name = (order_name or "").strip()[:140]
    if not order_name:
        frappe.throw(_("Order not specified"))

    approval = frappe.db.get_value(
        "DL Shop Order Approval",
        {"sales_order": order_name},
        ["name", "approval_status", "payment_method", "customer_email"],
        as_dict=True,
    )
    if not approval:
        frappe.throw(_("No approval record found for this order"))
    if approval.approval_status != "Approved":
        frappe.throw(_("Order has not been approved yet"))

    # Verify ownership: logged-in user or guest with matching email
    if frappe.session.user != "Guest":
        user_email = frappe.session.user
    else:
        frappe.throw(_("Please login to complete payment"))

    if approval.customer_email and approval.customer_email != user_email:
        frappe.throw(_("Not authorized"), frappe.PermissionError)

    so = frappe.get_doc("Sales Order", order_name)

    if (approval.payment_method or "").upper() == "TABBY":
        redirect_url = _create_tabby_payment_request(so)
        if redirect_url:
            return {"success": True, "payment_method": "tabby", "redirect_url": redirect_url}
        frappe.throw(_("Could not initiate Tabby payment. Please contact support."))

    # COD — nothing more to do; order is confirmed
    return {"success": True, "payment_method": "cod"}


def _get_or_create_customer():
    user = frappe.session.user
    if user == "Guest":
        return None
    customer = frappe.db.get_value("Customer", {"email_id": user}, "name")
    if not customer:
        full_name = frappe.db.get_value("User", user, "full_name") or user
        cust = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": full_name,
            "customer_type": "Individual",
            "customer_group": get_default_customer_group(),
            "email_id": user,
        })
        cust.insert(ignore_permissions=True)
        frappe.db.commit()
        return cust.name
    return customer


def _get_or_create_guest_customer(name, email, phone=None):
    existing = frappe.db.get_value("Customer", {"email_id": email}, "name")
    if existing:
        return existing
    cust = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": name or email,
        "customer_type": "Individual",
        "customer_group": get_default_customer_group(),
        "email_id": email,
        "mobile_no": phone,
    })
    cust.insert(ignore_permissions=True)
    frappe.db.commit()
    return cust.name


def _get_addresses(customer):
    if not customer:
        return []
    links = frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
        fields=["parent"],
    )
    if not links:
        return []
    addr_names = [l.parent for l in links]
    return frappe.get_all(
        "Address",
        filters={"name": ["in", addr_names]},
        fields=["name", "address_title", "address_line1", "address_line2",
                "city", "state", "country", "pincode", "phone", "address_type"],
    )


def _get_shipping_rules():
    return frappe.get_all(
        "Shipping Rule",
        filters={"disabled": 0},
        fields=["name", "label"],
        order_by="label asc",
    )


def _get_payment_methods(settings):
    methods = []
    if settings.cod_enabled:
        methods.append({
            "id": "cod",
            "label_en": "Cash on Delivery",
            "label_ar": "الدفع عند الاستلام",
            "description_en": settings.cod_description_en or "",
            "description_ar": settings.cod_description_ar or "",
            "charge": settings.cod_charge or 0,
            "icon": "fa fa-money-bill",
        })
    if settings.tabby_enabled and _tabby_is_configured():
        methods.append({
            "id": "tabby",
            "label_en": "Tabby — Buy Now, Pay Later",
            "label_ar": "تابي — اشتر الآن وادفع لاحقاً",
            "description_en": "Split into 4 interest-free payments",
            "description_ar": "قسّم مشترياتك على 4 دفعات بدون فوائد",
            "charge": 0,
            "icon": "tabby",
        })
    return methods


def _tabby_is_configured():
    try:
        ts = frappe.get_single("DL Tabby Settings")
        return bool(ts.key_id and ts.key_secret and ts.merchant_code)
    except Exception:
        return False


def _get_pickup_locations():
    return frappe.get_all(
        "DL Shop Pickup Location",
        filters={"is_active": 1},
        fields=["name", "location_name_en", "location_name_ar", "address_en", "address_ar",
                "phone", "photo", "working_hours_en", "working_hours_ar", "map_link"],
        order_by="sort_order asc, location_name_en asc",
    )


def _get_default_cost_center():
    return (
        frappe.db.get_value("Cost Center", {"is_group": 0, "disabled": 0}, "name")
        or frappe.db.get_value("Cost Center", {"is_group": 0}, "name")
    )


def _get_shipping_account():
    return (
        frappe.db.get_value("Account", {"account_type": "Tax", "is_group": 0}, "name")
        or frappe.db.get_value("Account", {"account_name": ["like", "%Shipping%"], "is_group": 0}, "name")
        or "Shipping - DL"
    )


def _create_tabby_payment_request(so):
    import requests as _requests

    try:
        ts = frappe.get_single("DL Tabby Settings")
        cust = frappe.get_doc("Customer", so.customer)

        site_url = frappe.utils.get_url().rstrip("/")
        success_url = ts.success_url or f"{site_url}/tabby-return?status=success"
        failure_url = ts.failure_url or f"{site_url}/tabby-return?status=failure"
        cancel_url  = ts.cancel_url  or f"{site_url}/tabby-return?status=cancel"

        payload = {
            "payment": {
                "amount": str(so.grand_total),
                "currency": so.currency or "SAR",
                "buyer": {
                    "phone": cust.mobile_no or "",
                    "email": cust.email_id or "",
                    "name": cust.customer_name,
                    "dob": "2000-01-01",
                },
                "shipping_address": {"address": "", "city": "", "zip": ""},
                "order": {"reference_id": so.name},
                "order_history": [],
            },
            "lang": frappe.local.lang or "en",
            "merchant_code": ts.merchant_code,
            "merchant_urls": {
                "success": success_url,
                "cancel":  cancel_url,
                "failure": failure_url,
            },
        }

        resp = _requests.post(
            "https://api.tabby.ai/api/v2/checkout",
            json=payload,
            headers={
                "Authorization": f"Bearer {ts.get_password('key_secret')}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        session_id   = data.get("id", "")
        payment      = data.get("payment", {})
        payment_id   = payment.get("id", "")
        products     = data.get("configuration", {}).get("available_products", {})
        installments = products.get("installments", [])
        checkout_url = installments[0].get("web_url", "") if installments else ""

        log = frappe.get_doc({
            "doctype": "DL Tabby Log",
            "sales_order": so.name,
            "amount": so.grand_total,
            "currency": so.currency or "SAR",
            "tabby_session_id": session_id,
            "tabby_payment_id": payment_id,
            "tabby_order_url": checkout_url,
            "status": "CREATED",
        })
        log.insert(ignore_permissions=True)
        frappe.db.commit()

        return checkout_url or None

    except Exception:
        frappe.log_error(frappe.get_traceback(), "DL Tabby Payment Error")
        return None


def _cart_summary(cart, settings):
    return {
        "items": [
            {
                "item_code": i.item_code, "item_name": i.item_name,
                "qty": i.qty, "rate": i.rate, "amount": i.amount, "image": i.image,
            }
            for i in cart.items
        ],
        "subtotal": cart.subtotal,
        "coupon_code": cart.coupon_code,
        "coupon_discount": cart.coupon_discount,
        "shipping_charge": cart.shipping_charge,
        "grand_total": cart.grand_total,
        "currency": settings.default_currency or "SAR",
    }
