"""Scheduled tasks for dlshop."""

import frappe
from frappe.utils import add_days, today

_BATCH = 500  # max records deleted/updated per daily run to avoid long table locks


def cleanup_expired_carts():
    """Delete abandoned carts older than 30 days (batched to avoid table locks)."""
    cutoff = add_days(today(), -30)
    old_carts = frappe.get_all(
        "DL Shop Cart",
        filters={"status": "Abandoned", "modified": ("<", cutoff)},
        pluck="name",
        limit=_BATCH,
    )
    for name in old_carts:
        frappe.delete_doc("DL Shop Cart", name, ignore_permissions=True)
    if old_carts:
        frappe.db.commit()
        frappe.logger().info(f"DL Shop: cleaned up {len(old_carts)} abandoned carts")


def cleanup_expired_coupons():
    """Mark expired active coupons as inactive (batched)."""
    # NOTE: two "valid_to" keys in a dict silently drops the first — use a list of
    # two-tuples (Frappe filter syntax) to apply both conditions correctly.
    expired = frappe.get_all(
        "DL Shop Coupon",
        filters=[
            ["is_active", "=", 1],
            ["valid_to", "is", "set"],
            ["valid_to", "<", today()],
        ],
        pluck="name",
        limit=_BATCH,
    )
    for name in expired:
        frappe.db.set_value("DL Shop Coupon", name, "is_active", 0)
    if expired:
        frappe.db.commit()
