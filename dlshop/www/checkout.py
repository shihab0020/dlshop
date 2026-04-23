import frappe
from dlshop.utils import get_settings, get_current_lang


def get_context(context):
    settings = get_settings()
    lang = get_current_lang()
    frappe.local.lang = lang
    context.shop_settings = settings
    context.lang = lang
    context.title = "إتمام الطلب" if lang == "ar" else "Checkout"
    context.is_guest = frappe.session.user == "Guest"
    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"
