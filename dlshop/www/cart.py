import frappe
from dlshop.utils import get_settings, get_current_lang


def get_context(context):
    settings = get_settings()
    lang = get_current_lang()
    frappe.local.lang = lang
    context.shop_settings = settings
    context.lang = lang
    context.title = "السلة" if lang == "ar" else "Shopping Cart"
    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"
