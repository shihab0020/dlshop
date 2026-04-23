import frappe
from dlshop.utils import get_current_lang


def get_context(context):
    # item_route comes from the route variable /shop/en/product/<item_route>
    item_route = frappe.form_dict.get("item_route", "")

    # Derive lang from the URL path (e.g. /shop/ar/product/...)
    path = frappe.request.path if frappe.request else ""
    parts = path.strip("/").split("/")
    if "ar" in parts:
        lang = "ar"
    elif "en" in parts:
        lang = "en"
    else:
        lang = get_current_lang()

    frappe.local.lang = lang

    if not item_route:
        frappe.throw("Product not found", frappe.DoesNotExistError)

    item_name = frappe.db.get_value(
        "DL Shop Item", {"route": item_route, "is_published": 1}, "name"
    )
    if not item_name:
        frappe.throw("Product not found", frappe.DoesNotExistError)

    doc = frappe.get_doc("DL Shop Item", item_name)
    context.doc = doc
    doc.get_context(context)

    # Make context available as a template variable (product_detail.html uses context.xxx)
    context.context = context
