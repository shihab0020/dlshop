import frappe
from dlshop.utils import get_current_lang


def get_context(context):
    lang = get_current_lang()
    frappe.local.lang = lang
    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"
