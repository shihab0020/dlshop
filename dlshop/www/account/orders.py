import frappe
from dlshop.utils import get_settings, get_current_lang


def get_context(context):
    if frappe.session.user == "Guest":
        _lang = get_current_lang()
        frappe.local.flags.redirect_location = f"/auth/{_lang}?redirect-to=/account/orders/{_lang}"
        raise frappe.Redirect
    settings = get_settings()
    lang = get_current_lang()
    frappe.local.lang = lang
    context.shop_settings = settings
    context.lang = lang
    context.title = "طلباتي" if lang == "ar" else "My Orders"
    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"
