"""Customer registration and login helpers."""

import frappe
from frappe import _
from frappe.utils import validate_email_address

from dlshop.utils import _rate_limit, get_default_customer_group


@frappe.whitelist(allow_guest=True)
def register_customer(full_name, email, phone, password, confirm_password,
                      address_line1=None, city=None, country="Saudi Arabia"):
    """Create a new website user + ERPNext Customer, then log them in."""
    # ── Rate limit: 5 registrations per IP per 10 minutes ────
    _rate_limit("register", limit=5, window=600)

    # ── Sanitize & validate inputs ────────────────────────────
    full_name = (full_name or "").strip()[:100]
    email = (email or "").strip().lower()[:200]
    phone = (phone or "").strip()[:30]

    if not full_name:
        return {"success": False, "message": _("Full name is required")}
    if not email or not validate_email_address(email):
        return {"success": False, "message": _("A valid email address is required")}
    if not phone:
        return {"success": False, "message": _("Phone number is required")}
    if not password or len(password) < 8:
        return {"success": False, "message": _("Password must be at least 8 characters")}
    if len(password) > 128:
        return {"success": False, "message": _("Password is too long")}
    if password != confirm_password:
        return {"success": False, "message": _("Passwords do not match")}
    if frappe.db.exists("User", email):
        return {"success": False, "message": _("An account with this email already exists")}

    # Sanitize optional address fields
    if address_line1:
        address_line1 = address_line1.strip()[:200]
    if city:
        city = city.strip()[:100]
    if country:
        country = country.strip()[:100]

    try:
        # ── Create Frappe User ────────────────────────────────────
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "send_welcome_email": 0,
            "user_type": "Website User",
            "mobile_no": phone,
            "enabled": 1,
        })
        user.insert(ignore_permissions=True)

        from frappe.utils.password import update_password
        update_password(email, password)

        # ── Create ERPNext Customer ───────────────────────────────
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": full_name,
            "customer_type": "Individual",
            "customer_group": get_default_customer_group(),
            "territory": "Saudi Arabia",
        })
        customer.insert(ignore_permissions=True)

        # ── Create Contact linked to Customer ─────────────────────
        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": full_name,
            "email_ids": [{"email_id": email, "is_primary": 1}],
            "phone_nos": [{"phone": phone, "is_primary_phone": 1}],
            "links": [{"link_doctype": "Customer", "link_name": customer.name}],
        })
        contact.insert(ignore_permissions=True)

        # ── Create Address if provided ────────────────────────────
        if address_line1 and city:
            address = frappe.get_doc({
                "doctype": "Address",
                "address_title": full_name,
                "address_type": "Billing",
                "address_line1": address_line1,
                "city": city,
                "country": country or "Saudi Arabia",
                "email_id": email,
                "phone": phone,
                "links": [{"link_doctype": "Customer", "link_name": customer.name}],
            })
            address.insert(ignore_permissions=True)

        frappe.db.commit()

        # ── Auto-login ────────────────────────────────────────────
        frappe.local.login_manager.login_as(email)

        return {"success": True}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "DL Shop Registration Error")
        return {"success": False, "message": _("Registration failed. Please try again.")}


@frappe.whitelist(allow_guest=True)
def login_customer(email, password, redirect_to=None):
    """Log in with email + password, return redirect URL."""
    # ── Rate limit: 10 attempts per IP per minute ─────────────
    _rate_limit("login", limit=10, window=60)

    email = (email or "").strip().lower()[:200]
    if not email or not password:
        return {"success": False, "message": _("Email and password are required")}
    # Only accept internal paths to prevent open-redirect
    if redirect_to and not (redirect_to.startswith("/") and not redirect_to.startswith("//")):
        redirect_to = None
    try:
        frappe.local.login_manager.authenticate(user=email, pwd=password)
        frappe.local.login_manager.post_login()
        return {"success": True, "redirect": redirect_to or "/account/en"}
    except frappe.AuthenticationError:
        return {"success": False, "message": _("Invalid email or password")}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "DL Shop Login Error")
        return {"success": False, "message": _("Login failed. Please try again.")}
