import frappe
from dlshop.utils import get_settings, get_current_lang


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = f"/auth/{get_current_lang()}"
        raise frappe.Redirect
    settings = get_settings()
    lang = get_current_lang()
    frappe.local.lang = lang
    context.shop_settings = settings
    context.lang = lang

    # Order name from URL: /account/order/<name>/en  or  /account/order/<name>/ar
    path = frappe.request.path if frappe.request else ""
    parts = [p for p in path.rstrip("/").split("/") if p]
    # Strip trailing lang segment if present
    if parts and parts[-1] in ("en", "ar"):
        parts = parts[:-1]
    order_name = parts[-1] if parts else ""
    context.order_name = order_name
    context.title = ("الطلب: " if lang == "ar" else "Order: ") + order_name
    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"
