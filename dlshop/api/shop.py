"""Shop API - product listing, search, filters, categories."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from dlshop.utils import get_settings, get_display_price, bilingual, get_current_lang


@frappe.whitelist(allow_guest=True)
def get_products(
    page=1,
    category=None,
    brand=None,
    search=None,
    sort_by="sort_order",
    sort_order="asc",
    min_price=None,
    max_price=None,
    is_featured=None,
    is_new_arrival=None,
    is_on_sale=None,
    page_size=None,
):
    """Return paginated product list with filters."""
    settings = get_settings()
    page = max(1, cint(page) or 1)
    page_size = min(100, max(1, cint(page_size) or settings.products_per_page or 20))
    lang = get_current_lang()

    filters = {"is_published": 1}
    if category:
        cat = frappe.db.get_value("DL Shop Category", {"route": category}, ["name", "item_group"], as_dict=True)
        if cat and cat.item_group:
            filters["item_group"] = cat.item_group
    if brand:
        filters["brand"] = str(brand).strip()[:140]
    if is_featured:
        filters["is_featured"] = 1
    if is_new_arrival:
        filters["is_new_arrival"] = 1
    if is_on_sale:
        filters["is_on_sale"] = 1

    valid_sorts = {"sort_order", "modified", "view_count", "purchase_count", "web_item_name_en"}
    if sort_by not in valid_sorts:
        sort_by = "sort_order"
    sort_order = "asc" if (sort_order or "").lower() == "asc" else "desc"

    # Full text search — cap length and escape LIKE wildcards
    or_filters = []
    if search:
        search = str(search).strip()[:200]
        # Escape SQL LIKE wildcards in user input so they match literally
        safe = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        term = f"%{safe}%"
        or_filters = [
            ["web_item_name_en", "like", term],
            ["web_item_name_ar", "like", term],
        ]

    # Validate price range inputs
    min_p = flt(min_price) if min_price else None
    max_p = flt(max_price) if max_price else None
    if min_p and min_p < 0:
        min_p = None
    if max_p and max_p < 0:
        max_p = None

    total = frappe.db.count("DL Shop Item", filters=filters)
    items = frappe.get_all(
        "DL Shop Item",
        filters=filters,
        or_filters=or_filters if or_filters else None,
        fields=[
            "name", "web_item_name_en", "web_item_name_ar", "featured_image",
            "route", "is_on_sale", "sale_price", "is_new_arrival", "is_featured",
            "item_code", "badge_text_en", "badge_text_ar", "custom_price",
            "custom_price_enabled", "brand", "item_group",
            "allow_virtual_stock", "virtual_stock_limit",
        ],
        order_by=f"{sort_by} {sort_order}",
        start=(page - 1) * page_size,
        page_length=page_size,
    )

    from dlshop.utils import is_in_stock, get_settings as _gs
    for item in items:
        item["name_display"] = bilingual(item["web_item_name_en"], item["web_item_name_ar"], lang)
        item["badge"] = bilingual(item["badge_text_en"], item["badge_text_ar"], lang)
        price, orig, has_discount = get_display_price(frappe._dict(item), settings)
        item["price"] = price
        item["original_price"] = orig
        item["has_discount"] = has_discount
        item["in_stock"] = is_in_stock(item["item_code"], settings.default_warehouse, settings, frappe._dict(item))

    # Price filter post-fetch
    if min_p or max_p:
        filtered = []
        for item in items:
            p = item["price"]
            if min_p and p < min_p:
                continue
            if max_p and p > max_p:
                continue
            filtered.append(item)
        items = filtered

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": -(-total // page_size),
    }


@frappe.whitelist(allow_guest=True)
def search_products(q, limit=10):
    """Quick search - returns items matching q in EN or AR name."""
    if not q:
        return []
    q = str(q).strip()[:200]
    if len(q) < 2:
        return []
    limit = min(20, max(1, cint(limit) or 10))
    # Escape LIKE wildcards
    safe = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    term = f"%{safe}%"
    lang = get_current_lang()
    items = frappe.get_all(
        "DL Shop Item",
        filters={"is_published": 1},
        or_filters=[
            ["web_item_name_en", "like", term],
            ["web_item_name_ar", "like", term],
        ],
        fields=["name", "web_item_name_en", "web_item_name_ar", "featured_image", "route"],
        limit=limit,
    )
    for item in items:
        item["name_display"] = bilingual(item["web_item_name_en"], item["web_item_name_ar"], lang)
    return items


@frappe.whitelist(allow_guest=True)
def get_product_detail(route):
    """Get full product detail for a given route."""
    if not route:
        frappe.throw(_("Invalid route"), frappe.DoesNotExistError)
    item = frappe.db.get_value(
        "DL Shop Item",
        {"route": str(route).strip()[:200], "is_published": 1},
        [
            "name", "item_code", "web_item_name_en", "web_item_name_ar",
            "featured_image", "is_on_sale", "sale_price", "custom_price",
            "custom_price_enabled", "short_description_en", "short_description_ar",
            "average_rating", "review_count",
        ],
        as_dict=True,
    )
    if not item:
        frappe.throw(_("Product not found"), frappe.DoesNotExistError)
    settings = get_settings()
    price, orig, has_discount = get_display_price(item, settings)
    item["price"] = price
    item["original_price"] = orig
    item["has_discount"] = has_discount
    return item


@frappe.whitelist(allow_guest=True)
def get_filters_data(category=None):
    """Return available brands and price range for filter sidebar."""
    filters = {"is_published": 1}
    if category:
        cat = frappe.db.get_value("DL Shop Category", {"route": str(category).strip()[:200]}, "item_group")
        if cat:
            filters["item_group"] = cat

    brands = frappe.get_all(
        "DL Shop Item",
        filters=filters,
        fields=["brand"],
        distinct=True,
        ignore_ifnull=True,
    )
    brand_list = [b["brand"] for b in brands if b["brand"]]

    return {"brands": brand_list}


@frappe.whitelist(allow_guest=True)
def submit_review(item_route, rating, title, review_text, reviewer_name=None):
    """Submit a product review."""
    settings = get_settings()
    if not settings.enable_reviews:
        frappe.throw(_("Reviews are disabled"))

    rating = flt(rating)
    if rating < 1 or rating > 5:
        frappe.throw(_("Rating must be between 1 and 5"))

    title = (title or "").strip()[:200]
    review_text = (review_text or "").strip()[:2000]
    if not title or not review_text:
        frappe.throw(_("Title and review text are required"))

    if not frappe.db.exists("DL Shop Item", {"route": item_route, "is_published": 1}):
        frappe.throw(_("Product not found"))

    review = frappe.get_doc({
        "doctype": "DL Shop Review",
        "item_route": frappe.db.get_value("DL Shop Item", {"route": item_route}, "name"),
        "rating": rating,
        "title": title,
        "review_text": review_text,
        "reviewer_name": (reviewer_name or "").strip()[:100] or (frappe.session.user if frappe.session.user != "Guest" else "Anonymous"),
        "reviewer_email": frappe.session.user if frappe.session.user != "Guest" else "",
        "is_approved": 1 if settings.auto_approve_reviews else 0,
    })
    review.insert(ignore_permissions=True)
    frappe.db.commit()

    if settings.auto_approve_reviews:
        _update_item_rating(review.item_route)

    return {"success": True, "approved": bool(settings.auto_approve_reviews)}


def get_review_permission_query(user):
    return "`tabDL Shop Review`.`is_approved` = 1"


def _update_item_rating(item_name):
    """Recalculate and update average rating for an item."""
    result = frappe.db.sql(
        "SELECT AVG(rating) as avg, COUNT(*) as cnt FROM `tabDL Shop Review` WHERE item_route = %s AND is_approved = 1",
        item_name,
        as_dict=True,
    )
    if result:
        frappe.db.set_value("DL Shop Item", item_name, {
            "average_rating": round(flt(result[0]["avg"] or 0), 1),
            "review_count": result[0]["cnt"] or 0,
        }, update_modified=False)
