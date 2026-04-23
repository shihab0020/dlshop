import frappe
from dlshop.utils import get_settings, get_current_lang, is_rtl, bilingual, get_categories, get_hero_banners, get_display_price, get_featured_items


def get_context(context):
    settings = get_settings()
    lang = get_current_lang()
    frappe.local.lang = lang

    context.shop_settings = settings
    context.lang = lang
    context.categories = get_categories(lang)

    # Category filter from URL: /shop/en/electronics or /shop/ar/cameras/dslr
    path = frappe.request.path if frappe.request else ""
    path_parts = path.strip("/").split("/")
    category_route = None
    if "shop" in path_parts:
        shop_idx = path_parts.index("shop")
        rest = [p for p in path_parts[shop_idx + 1:] if p not in ("ar", "en")]
        category_route = "/".join(rest) if rest else None

    context.category_route = category_route
    if category_route:
        cat = frappe.db.get_value(
            "DL Shop Category",
            {"route": category_route},
            ["category_name_en", "category_name_ar", "description_en", "description_ar", "image", "meta_title_en", "meta_title_ar"],
            as_dict=True,
        )
        context.current_category = cat
        context.title = bilingual(cat.meta_title_en or cat.category_name_en, cat.meta_title_ar or cat.category_name_ar, lang) if cat else ""
    else:
        context.current_category = None
        context.title = bilingual(settings.meta_title_en or settings.site_name_en, settings.meta_title_ar or settings.site_name_ar, lang)

    # Hero banners (shown when no category filter)
    context.hero_banners = get_hero_banners() if not category_route else []

    # Get promo banners
    context.promo_banners = frappe.get_all(
        "DL Shop Banner",
        filters={"is_active": 1, "banner_type": "Promo"},
        fields=["title_en", "title_ar", "subtitle_en", "subtitle_ar", "desktop_image", "mobile_image", "link", "button_text_en", "button_text_ar", "text_color", "overlay_opacity"],
        order_by="sort_order asc",
        limit=4,
    )

    # Homepage-only sections
    if not category_route:
        _s = get_settings()

        # Flash deals (on-sale items)
        _flash = frappe.get_all(
            "DL Shop Item",
            filters={"is_published": 1, "is_on_sale": 1, "sale_price": [">", 0]},
            fields=["item_code", "web_item_name_en", "web_item_name_ar", "featured_image",
                    "route", "sale_price", "is_on_sale", "badge_text_en", "badge_text_ar"],
            order_by="sort_order asc",
            limit=12,
        )
        for _it in _flash:
            _it["name_display"] = bilingual(_it.get("web_item_name_en"), _it.get("web_item_name_ar"), lang)
            _price, _orig, _ = get_display_price(frappe._dict(_it), _s)
            _it["price"] = _price
            _it["orig_price"] = _orig
            _it["discount_pct"] = round((1 - _price / _orig) * 100) if _orig and _orig > _price else 0
        context.flash_deals = _flash

        # New arrivals
        _new = frappe.get_all(
            "DL Shop Item",
            filters={"is_published": 1, "is_new_arrival": 1},
            fields=["item_code", "web_item_name_en", "web_item_name_ar", "featured_image",
                    "route", "sale_price", "is_on_sale", "badge_text_en", "badge_text_ar"],
            order_by="creation desc",
            limit=12,
        )
        for _it in _new:
            _it["name_display"] = bilingual(_it.get("web_item_name_en"), _it.get("web_item_name_ar"), lang)
            _price, _orig, _disc = get_display_price(frappe._dict(_it), _s)
            _it["price"] = _price
            _it["orig_price"] = _orig
            _it["has_discount"] = _disc
        context.new_arrivals = _new

        # Featured products
        context.featured_items = get_featured_items(12, lang)
    else:
        context.flash_deals = []
        context.new_arrivals = []
        context.featured_items = []

    # Filters from query params
    context.q = frappe.form_dict.get("q", "")
    context.selected_brand = frappe.form_dict.get("brand", "")
    context.selected_sort = frappe.form_dict.get("sort", "sort_order")
    context.current_page = int(frappe.form_dict.get("page", 1))

    context.no_cache = 1
    context.body_class = "dl-shop rtl" if lang == "ar" else "dl-shop"
