import re
import frappe
from frappe.website.website_generator import WebsiteGenerator


def _slugify(text):
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "product"


class DLShopItem(WebsiteGenerator):
    website = frappe._dict(
        page_title_field="web_item_name_en",
        condition_field="is_published",
        template="dlshop/templates/pages/product_detail.html",
        route_field="route",
    )

    def before_save(self):
        if not self.route:
            self.route = _slugify(self.web_item_name_en)
        self.route = _slugify(self.route)

    def on_update(self):
        frappe.clear_cache(doctype="DL Shop Item")

    def get_context(self, context):
        """Called when this item's web page is rendered."""
        from dlshop.utils import get_settings, get_item_price, get_item_stock, get_item_variants

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

        # Stock
        context.in_stock = get_item_stock(self.item_code, settings.default_warehouse)

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

        # Increment view count
        frappe.db.set_value("DL Shop Item", self.name, "view_count", (self.view_count or 0) + 1, update_modified=False)

        context.title = context.meta_title or context.item_name
        context.no_cache = 1
