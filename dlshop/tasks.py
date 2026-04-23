"""Scheduled tasks for dlshop."""

import frappe
from frappe.utils import add_days, today


def cleanup_expired_carts():
    """Delete abandoned carts older than 30 days."""
    cutoff = add_days(today(), -30)
    old_carts = frappe.get_all(
        "DL Shop Cart",
        filters={"status": "Abandoned", "modified": ("<", cutoff)},
        pluck="name",
    )
    for name in old_carts:
        frappe.delete_doc("DL Shop Cart", name, ignore_permissions=True)
    if old_carts:
        frappe.db.commit()
        frappe.logger().info(f"DL Shop: cleaned up {len(old_carts)} abandoned carts")


def cleanup_expired_coupons():
    """Mark expired coupons as inactive."""
    expired = frappe.get_all(
        "DL Shop Coupon",
        filters={"is_active": 1, "valid_to": ("<", today()), "valid_to": ("is", "set")},
        pluck="name",
    )
    for name in expired:
        frappe.db.set_value("DL Shop Coupon", name, "is_active", 0)
    if expired:
        frappe.db.commit()
