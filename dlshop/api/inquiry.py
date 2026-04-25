"""Customer inquiry / messaging API."""

import frappe
from frappe import _
from frappe.utils import validate_email_address

from dlshop.utils import get_settings


@frappe.whitelist(allow_guest=True)
def submit_inquiry(customer_name, message, customer_email=None, customer_phone=None, subject=None, order_id=None):
    """Submit a customer inquiry. Rate-limited to 5 per 10 minutes per IP."""
    from dlshop.utils import _rate_limit
    _rate_limit("inquiry", limit=5, window=600)

    customer_name = (customer_name or "").strip()[:100]
    message = (message or "").strip()[:2000]
    customer_email = (customer_email or "").strip()[:200]
    customer_phone = (customer_phone or "").strip()[:30]
    subject = (subject or "").strip()[:200] or "General Inquiry"
    order_id = (order_id or "").strip()[:140]

    if not customer_name:
        frappe.throw(_("Name is required"))
    if not message:
        frappe.throw(_("Message is required"))
    if customer_email and not validate_email_address(customer_email):
        frappe.throw(_("Invalid email address"))

    # If logged in, fill in email from session and validate order ownership
    if frappe.session.user != "Guest":
        if not customer_email:
            customer_email = frappe.session.user
        if order_id:
            customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
            owned = customer and frappe.db.get_value(
                "Sales Order", {"name": order_id, "customer": customer}, "name"
            )
            if not owned:
                frappe.throw(_("Invalid order reference"))

    doc = frappe.get_doc({
        "doctype": "DL Shop Inquiry",
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "subject": subject,
        "message": message,
        "order_id": order_id,
        "status": "New",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}
