import frappe
from dlshop.utils import get_settings, get_current_lang


def get_context(context):
    # Redirect logged-in users to account
    if frappe.session.user != "Guest":
        lang = get_current_lang()
        frappe.local.flags.redirect_location = f"/account/{lang}"
        raise frappe.Redirect

    lang = get_current_lang()
    frappe.local.lang = lang
    settings = get_settings()

    context.lang = lang
    context.shop_settings = settings
    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"

    # Which tab to show: login or register
    context.active_tab = frappe.form_dict.get("tab", "login")
    context.redirect_to = frappe.form_dict.get("redirect-to", f"/account/{lang}")
