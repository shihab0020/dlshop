import frappe
from dlshop.utils import get_settings, get_current_lang


def get_context(context):
    if frappe.session.user == "Guest":
        _lang = get_current_lang()
        frappe.local.flags.redirect_location = f"/auth/{_lang}?redirect-to=/account/{_lang}"
        raise frappe.Redirect
    settings = get_settings()
    lang = get_current_lang()
    frappe.local.lang = lang
    context.shop_settings = settings
    context.lang = lang
    context.title = "حسابي" if lang == "ar" else "My Account"
    context.user = frappe.session.user
    context.full_name = frappe.db.get_value("User", frappe.session.user, "full_name")
    recent_orders = frappe.get_all(
        "Sales Order",
        filters={
            "customer": frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name") or "__none__",
            "docstatus": ["in", [1, 2]],
        },
        fields=["name", "transaction_date", "grand_total", "status", "currency", "docstatus"],
        order_by="creation desc",
        limit=5,
    )
    context.recent_orders = recent_orders
    wishlist_count = frappe.db.count("DL Shop Wishlist Item", {"owner": frappe.session.user})
    context.wishlist_count = wishlist_count
    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"
