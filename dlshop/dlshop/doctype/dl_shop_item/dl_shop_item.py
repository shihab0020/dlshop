import re
import frappe
from frappe.model.document import Document


def _slugify(text):
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "product"


class DLShopItem(Document):

    def before_save(self):
        if not self.route:
            self.route = _slugify(self.web_item_name_en)
        self.route = _slugify(self.route)

    def on_update(self):
        frappe.clear_cache(doctype="DL Shop Item")

    def get_context(self, context):
        """Called from www/product.py when rendering a product page."""
        from dlshop.utils import get_settings, get_item_price, get_item_stock, get_item_variants, get_virtual_stock_remaining
        from dlshop.utils import get_current_lang

        settings = get_settings()
        lang = get_current_lang()
        frappe.local.lang = lang

        context.shop_settings = settings
        context.lang = lang
        context.request = frappe.request

        context.item_name = self.web_item_name_ar if lang == "ar" else self.web_item_name_en
        context.item_description = self.description_ar if lang == "ar" else self.description_en
        context.short_description = self.short_description_ar if lang == "ar" else self.short_description_en
        context.meta_title = self.meta_title_ar if lang == "ar" else self.meta_title_en
        context.meta_description = self.meta_description_ar if lang == "ar" else self.meta_description_en

        # Pricing
        context.price = get_item_price(self.item_code, settings)
        context.sale_price = self.sale_price or None
        context.custom_price = self.custom_price if self.custom_price_enabled else None

        # Stock — respect virtual stock flag
        dl_item_dict = frappe._dict({
            "allow_virtual_stock": self.allow_virtual_stock,
            "virtual_stock_limit": self.virtual_stock_limit,
        })
        if self.allow_virtual_stock:
            remaining = get_virtual_stock_remaining(self.item_code, dl_item_dict)
            context.in_stock = -1 if remaining == -1 else remaining  # -1=unlimited, 0=none, N=remaining
            context.is_virtual_stock = True
        else:
            context.in_stock = get_item_stock(self.item_code, settings.default_warehouse)
            context.is_virtual_stock = False

        # Variants (if template item)
        context.variants = get_item_variants(self.item_code)

        # Reviews
        if settings.enable_reviews:
            context.reviews = frappe.get_all(
                "DL Shop Review",
                filters={"item_route": self.name, "is_approved": 1},
                fields=["owner", "rating", "title", "review_text", "creation"],
                order_by="creation desc",
                limit=10,
            )
        else:
            context.reviews = []

        # Related items (same item_group)
        context.related_items = frappe.get_all(
            "DL Shop Item",
            filters={"item_group": self.item_group, "is_published": 1, "name": ("!=", self.name)},
            fields=["name", "web_item_name_en", "web_item_name_ar", "featured_image", "route", "is_on_sale", "sale_price", "is_new_arrival"],
            order_by="sort_order asc",
            limit=6,
        )

        # Increment view count atomically
        frappe.db.sql(
            "UPDATE `tabDL Shop Item` SET view_count = COALESCE(view_count, 0) + 1 WHERE name = %s",
            self.name,
        )
        frappe.db.commit()

        context.user_full_name = (
            frappe.db.get_value("User", frappe.session.user, "full_name")
            if frappe.session.user != "Guest" else ""
        )
        context.title = context.meta_title or context.item_name
        context.no_cache = 1
        # Required so the product_detail.html template can access context.item_name etc.
        context.context = context
