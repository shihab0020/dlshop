"""DL Shop Analytics — unified shop intelligence report."""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    report_type = filters.get("report_type", "Product Sales")

    dispatch = {
        "Product Sales":     _product_sales,
        "Customer Analysis": _customer_analysis,
        "Brand Sales":       _brand_sales,
        "Category Sales":    _category_sales,
        "Order Trends":      _order_trends,
        "Product Views":     _product_views,
        "Wishlist":          _wishlist,
        "Reviews":           _reviews,
        "Visitor Countries": _visitor_countries,
        "Order Countries":   _order_countries,
    }
    fn = dispatch.get(report_type)
    if not fn:
        return [], [], None, None, None, 0
    return fn(filters)


# --------------------------------------------------------------------------- #
# Status filter helper — applied to all Sales Order-based queries
# --------------------------------------------------------------------------- #
def _so_status_conditions(f):
    """
    Build optional JOIN and WHERE fragments from the four status filters.
    Returns (extra_join, docstatus_cond, extra_where).
    """
    order_status    = (f.get("order_status")    or "").strip()
    approval_status = (f.get("approval_status") or "").strip()
    delivery_filter = (f.get("delivery_filter") or "").strip()
    billing_filter  = (f.get("billing_filter")  or "").strip()

    joins  = []
    extras = []

    # ── Order / docstatus condition ──────────────────────────────────────────
    status_map = {
        "To Deliver and Bill": "so.docstatus = 1 AND so.status = 'To Deliver and Bill'",
        "To Bill":             "so.docstatus = 1 AND so.status = 'To Bill'",
        "To Deliver":          "so.docstatus = 1 AND so.status = 'To Deliver'",
        "Completed":           "so.docstatus = 1 AND so.status = 'Completed'",
        "On Hold":             "so.docstatus = 1 AND so.status = 'On Hold'",
        "Cancelled":           "so.docstatus = 2",
        "Active":              "so.docstatus = 1 AND so.status NOT IN ('Cancelled','Closed')",
    }
    docstatus_cond = status_map.get(order_status, "so.docstatus = 1")

    # ── Delivery status ──────────────────────────────────────────────────────
    delivery_map = {
        "Fully Delivered":  "so.delivery_status = 'Fully Delivered'",
        "Partly Delivered": "so.delivery_status = 'Partly Delivered'",
        "Not Delivered":    "so.delivery_status = 'Not Delivered'",
    }
    if delivery_filter in delivery_map:
        extras.append(delivery_map[delivery_filter])

    # ── Billing / invoice status (per_billed is a reliable float field) ──────
    billing_map = {
        "Fully Billed (Paid)": "so.per_billed >= 100",
        "Partly Billed":       "so.per_billed > 0 AND so.per_billed < 100",
        "Not Billed (Unpaid)": "(so.per_billed = 0 OR so.per_billed IS NULL)",
    }
    if billing_filter in billing_map:
        extras.append(billing_map[billing_filter])

    # ── DL Shop approval status (LEFT JOIN so rows without approval still show) ─
    approval_map = {
        "Approved":           "doa.approval_status = 'Approved'",
        "Pending Approval":   "doa.approval_status = 'Pending'",
        "Rejected":           "doa.approval_status = 'Rejected'",
        "No Approval Record": "doa.name IS NULL",
    }
    if approval_status in approval_map:
        joins.append("LEFT JOIN `tabDL Shop Order Approval` doa ON doa.sales_order = so.name")
        extras.append(approval_map[approval_status])

    join_sql  = "\n        ".join(joins)
    extra_sql = (" AND " + " AND ".join(extras)) if extras else ""
    return join_sql, docstatus_cond, extra_sql


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #
def _date_conds(f, alias="so"):
    from_c = f"AND {alias}.transaction_date >= %(from_date)s" if f.get("from_date") else ""
    to_c   = f"AND {alias}.transaction_date <= %(to_date)s"   if f.get("to_date")   else ""
    return from_c, to_c


# --------------------------------------------------------------------------- #
# 1. Product Sales
# --------------------------------------------------------------------------- #
def _product_sales(f):
    from_c, to_c = _date_conds(f)
    sj, dsc, exw = _so_status_conditions(f)

    item_join = ""
    item_cond = ""
    if f.get("brand"):
        item_join = "JOIN `tabItem` it ON it.name = soi.item_code"
        item_cond = "AND it.brand = %(brand)s"
    if f.get("item_group"):
        item_join = item_join or "JOIN `tabItem` it ON it.name = soi.item_code"
        item_cond += " AND it.item_group = %(item_group)s"

    rows = frappe.db.sql(f"""
        SELECT
            soi.item_code,
            soi.item_name,
            SUM(soi.qty)             AS total_qty,
            SUM(soi.amount)          AS total_revenue,
            COUNT(DISTINCT so.name)  AS order_count,
            MAX(so.transaction_date) AS last_sold
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        {sj}
        {item_join}
        WHERE {dsc}
          {from_c} {to_c} {exw} {item_cond}
        GROUP BY soi.item_code, soi.item_name
        ORDER BY total_revenue DESC
        LIMIT 50
    """, {"from_date": f.get("from_date"), "to_date": f.get("to_date"),
          "brand": f.get("brand"), "item_group": f.get("item_group")}, as_dict=True)

    item_codes = [r.item_code for r in rows]
    dl_map = {}
    if item_codes:
        dl_rows = frappe.get_all("DL Shop Item",
            filters={"item_code": ["in", item_codes]},
            fields=["item_code", "web_item_name_en", "brand"])
        dl_map = {d.item_code: d for d in dl_rows}

    data = []
    for r in rows:
        dl = dl_map.get(r.item_code, frappe._dict())
        data.append({
            "item_code":     r.item_code,
            "product_name":  dl.get("web_item_name_en") or r.item_name,
            "brand":         dl.get("brand") or "",
            "total_qty":     flt(r.total_qty),
            "total_revenue": flt(r.total_revenue),
            "order_count":   r.order_count,
            "avg_order_val": flt(r.total_revenue) / r.order_count if r.order_count else 0,
            "last_sold":     r.last_sold,
        })

    columns = [
        {"label": _("Item Code"),       "fieldname": "item_code",     "fieldtype": "Link",     "options": "Item", "width": 130},
        {"label": _("Product Name"),    "fieldname": "product_name",  "fieldtype": "Data",     "width": 200},
        {"label": _("Brand"),           "fieldname": "brand",         "fieldtype": "Data",     "width": 110},
        {"label": _("Qty Sold"),        "fieldname": "total_qty",     "fieldtype": "Float",    "width": 100},
        {"label": _("Revenue"),         "fieldname": "total_revenue", "fieldtype": "Currency", "width": 130},
        {"label": _("Orders"),          "fieldname": "order_count",   "fieldtype": "Int",      "width": 80},
        {"label": _("Avg Order Value"), "fieldname": "avg_order_val", "fieldtype": "Currency", "width": 130},
        {"label": _("Last Sold"),       "fieldname": "last_sold",     "fieldtype": "Date",     "width": 110},
    ]
    chart = _make_chart(f, [r["product_name"] for r in data[:15]], [
        {"name": _("Revenue"),  "values": [r["total_revenue"] for r in data[:15]]},
        {"name": _("Qty Sold"), "values": [r["total_qty"]     for r in data[:15]]},
    ], default="bar")
    summary = _summary([
        (_("Products Sold"), len(data),                               "blue"),
        (_("Total Revenue"), sum(r["total_revenue"] for r in data),   "green"),
        (_("Total Orders"),  sum(r["order_count"]   for r in data),   "orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 2. Customer Analysis
# --------------------------------------------------------------------------- #
def _customer_analysis(f):
    from_c, to_c = _date_conds(f)
    sj, dsc, exw = _so_status_conditions(f)

    rows = frappe.db.sql(f"""
        SELECT
            so.customer,
            so.customer_name,
            COUNT(so.name)           AS order_count,
            SUM(so.grand_total)      AS total_spent,
            AVG(so.grand_total)      AS avg_order,
            MAX(so.transaction_date) AS last_order,
            MIN(so.transaction_date) AS first_order
        FROM `tabSales Order` so
        {sj}
        WHERE {dsc}
          {from_c} {to_c} {exw}
        GROUP BY so.customer, so.customer_name
        ORDER BY total_spent DESC
        LIMIT 50
    """, {"from_date": f.get("from_date"), "to_date": f.get("to_date")}, as_dict=True)

    email_map = {}
    if rows:
        for c in frappe.get_all("Customer",
                filters={"name": ["in", [r.customer for r in rows]]},
                fields=["name", "email_id"]):
            email_map[c.name] = c.email_id

    data = [{
        "rank":          i + 1,
        "customer":      r.customer,
        "customer_name": r.customer_name,
        "email":         email_map.get(r.customer, ""),
        "order_count":   r.order_count,
        "total_spent":   flt(r.total_spent),
        "avg_order":     flt(r.avg_order),
        "first_order":   r.first_order,
        "last_order":    r.last_order,
    } for i, r in enumerate(rows)]

    columns = [
        {"label": _("Rank"),          "fieldname": "rank",          "fieldtype": "Int",      "width": 60},
        {"label": _("Customer"),      "fieldname": "customer",      "fieldtype": "Link",     "options": "Customer", "width": 140},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data",     "width": 170},
        {"label": _("Email"),         "fieldname": "email",         "fieldtype": "Data",     "width": 180},
        {"label": _("Orders"),        "fieldname": "order_count",   "fieldtype": "Int",      "width": 80},
        {"label": _("Total Spent"),   "fieldname": "total_spent",   "fieldtype": "Currency", "width": 130},
        {"label": _("Avg Order"),     "fieldname": "avg_order",     "fieldtype": "Currency", "width": 120},
        {"label": _("First Order"),   "fieldname": "first_order",   "fieldtype": "Date",     "width": 110},
        {"label": _("Last Order"),    "fieldname": "last_order",    "fieldtype": "Date",     "width": 110},
    ]
    chart = _make_chart(f, [r["customer_name"] for r in data[:15]], [
        {"name": _("Total Spent"), "values": [r["total_spent"] for r in data[:15]]},
    ], default="bar")
    summary = _summary([
        (_("Total Customers"), len(data),                              "blue"),
        (_("Total Revenue"),   sum(r["total_spent"] for r in data),    "green"),
        (_("Avg per Customer"),
         sum(r["total_spent"] for r in data) / len(data) if data else 0, "orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 3. Brand Sales
# --------------------------------------------------------------------------- #
def _brand_sales(f):
    from_c, to_c = _date_conds(f)
    sj, dsc, exw = _so_status_conditions(f)

    rows = frappe.db.sql(f"""
        SELECT
            it.brand,
            SUM(soi.qty)             AS total_qty,
            SUM(soi.amount)          AS total_revenue,
            COUNT(DISTINCT so.name)  AS order_count,
            COUNT(DISTINCT soi.item_code) AS product_count
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        JOIN `tabItem` it ON it.name = soi.item_code
        {sj}
        WHERE {dsc}
          AND it.brand IS NOT NULL AND it.brand != ''
          {from_c} {to_c} {exw}
        GROUP BY it.brand
        ORDER BY total_revenue DESC
    """, {"from_date": f.get("from_date"), "to_date": f.get("to_date")}, as_dict=True)

    total_rev = sum(flt(r.total_revenue) for r in rows)
    data = [{
        "brand":         r.brand,
        "product_count": r.product_count,
        "total_qty":     flt(r.total_qty),
        "total_revenue": flt(r.total_revenue),
        "order_count":   r.order_count,
        "revenue_share": round(flt(r.total_revenue) / total_rev * 100, 1) if total_rev else 0,
    } for r in rows]

    columns = [
        {"label": _("Brand"),           "fieldname": "brand",         "fieldtype": "Link",    "options": "Brand", "width": 150},
        {"label": _("Products"),        "fieldname": "product_count", "fieldtype": "Int",     "width": 90},
        {"label": _("Qty Sold"),        "fieldname": "total_qty",     "fieldtype": "Float",   "width": 100},
        {"label": _("Revenue"),         "fieldname": "total_revenue", "fieldtype": "Currency","width": 130},
        {"label": _("Orders"),          "fieldname": "order_count",   "fieldtype": "Int",     "width": 80},
        {"label": _("Revenue Share %"), "fieldname": "revenue_share", "fieldtype": "Percent", "width": 120},
    ]
    chart = _make_chart(f, [r["brand"] for r in data], [
        {"name": _("Revenue"), "values": [r["total_revenue"] for r in data]},
    ], default="bar")
    summary = _summary([
        (_("Total Brands"),  len(data),                        "blue"),
        (_("Total Revenue"), total_rev,                        "green"),
        (_("Top Brand"),     data[0]["brand"] if data else "-","orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 4. Category Sales
# --------------------------------------------------------------------------- #
def _category_sales(f):
    from_c, to_c = _date_conds(f)
    sj, dsc, exw = _so_status_conditions(f)
    ig_cond = "AND it.item_group = %(item_group)s" if f.get("item_group") else ""

    rows = frappe.db.sql(f"""
        SELECT
            it.item_group,
            SUM(soi.qty)             AS total_qty,
            SUM(soi.amount)          AS total_revenue,
            COUNT(DISTINCT so.name)  AS order_count,
            COUNT(DISTINCT soi.item_code) AS product_count
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        JOIN `tabItem` it ON it.name = soi.item_code
        {sj}
        WHERE {dsc}
          AND it.item_group IS NOT NULL AND it.item_group != ''
          {from_c} {to_c} {exw} {ig_cond}
        GROUP BY it.item_group
        ORDER BY total_revenue DESC
    """, {"from_date": f.get("from_date"), "to_date": f.get("to_date"),
          "item_group": f.get("item_group")}, as_dict=True)

    total_rev = sum(flt(r.total_revenue) for r in rows)
    data = [{
        "item_group":    r.item_group,
        "product_count": r.product_count,
        "total_qty":     flt(r.total_qty),
        "total_revenue": flt(r.total_revenue),
        "order_count":   r.order_count,
        "revenue_share": round(flt(r.total_revenue) / total_rev * 100, 1) if total_rev else 0,
    } for r in rows]

    columns = [
        {"label": _("Category"),        "fieldname": "item_group",    "fieldtype": "Link",    "options": "Item Group","width": 170},
        {"label": _("Products"),        "fieldname": "product_count", "fieldtype": "Int",     "width": 90},
        {"label": _("Qty Sold"),        "fieldname": "total_qty",     "fieldtype": "Float",   "width": 100},
        {"label": _("Revenue"),         "fieldname": "total_revenue", "fieldtype": "Currency","width": 130},
        {"label": _("Orders"),          "fieldname": "order_count",   "fieldtype": "Int",     "width": 80},
        {"label": _("Revenue Share %"), "fieldname": "revenue_share", "fieldtype": "Percent", "width": 120},
    ]
    chart = _make_chart(f, [r["item_group"] for r in data], [
        {"name": _("Revenue"), "values": [r["total_revenue"] for r in data]},
    ], default="bar")
    summary = _summary([
        (_("Total Categories"), len(data),                             "blue"),
        (_("Total Revenue"),    total_rev,                             "green"),
        (_("Top Category"),     data[0]["item_group"] if data else "-","orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 5. Order Trends
# --------------------------------------------------------------------------- #
def _order_trends(f):
    from_c = "AND transaction_date >= %(from_date)s" if f.get("from_date") else ""
    to_c   = "AND transaction_date <= %(to_date)s"   if f.get("to_date")   else ""

    # Build status conditions (without so. alias since this query has no alias)
    sj, dsc, exw = _so_status_conditions(f)
    # Strip so. prefix — Order Trends has no alias
    dsc_plain = dsc.replace("so.", "")
    exw_plain = exw.replace("so.", "")
    # Rebuild join with alias since we have no JOIN here — drop approval join for trends
    trend_join = ""
    trend_exw  = exw_plain
    if "doa" in exw:
        trend_join = "LEFT JOIN `tabDL Shop Order Approval` doa ON doa.sales_order = name"
        trend_exw  = exw  # keep original with alias since join exists

    rows = frappe.db.sql(f"""
        SELECT transaction_date, grand_total, docstatus, status, delivery_status, per_billed
        FROM `tabSales Order`
        {trend_join}
        WHERE {dsc_plain}
          {from_c} {to_c} {trend_exw}
        ORDER BY transaction_date ASC
    """, {"from_date": f.get("from_date"), "to_date": f.get("to_date")}, as_dict=True)

    range_type = f.get("range", "Monthly")
    buckets = {}
    for r in rows:
        period = _get_period_label(r.transaction_date, range_type)
        if period not in buckets:
            buckets[period] = {"period": period, "order_count": 0, "revenue": 0.0,
                               "cancelled": 0, "delivered": 0, "billed": 0}
        buckets[period]["order_count"] += 1
        if r.docstatus == 1:
            buckets[period]["revenue"] += flt(r.grand_total)
        if r.docstatus == 2 or r.status == "Cancelled":
            buckets[period]["cancelled"] += 1
        if r.delivery_status == "Fully Delivered":
            buckets[period]["delivered"] += 1
        if flt(r.per_billed) >= 100:
            buckets[period]["billed"] += 1

    data = list(buckets.values())
    for r in data:
        active = r["order_count"] - r["cancelled"]
        r["avg_order"] = r["revenue"] / active if active > 0 else 0

    columns = [
        {"label": _("Period"),    "fieldname": "period",      "fieldtype": "Data",     "width": 130},
        {"label": _("Orders"),    "fieldname": "order_count", "fieldtype": "Int",      "width": 90},
        {"label": _("Revenue"),   "fieldname": "revenue",     "fieldtype": "Currency", "width": 130},
        {"label": _("Avg Order"), "fieldname": "avg_order",   "fieldtype": "Currency", "width": 120},
        {"label": _("Delivered"), "fieldname": "delivered",   "fieldtype": "Int",      "width": 90},
        {"label": _("Billed"),    "fieldname": "billed",      "fieldtype": "Int",      "width": 80},
        {"label": _("Cancelled"), "fieldname": "cancelled",   "fieldtype": "Int",      "width": 100},
    ]
    chart = _make_chart(f,
        labels=[r["period"] for r in data],
        datasets=[
            {"name": _("Revenue"),   "values": [r["revenue"]     for r in data]},
            {"name": _("Orders"),    "values": [r["order_count"] for r in data]},
            {"name": _("Delivered"), "values": [r["delivered"]   for r in data]},
            {"name": _("Cancelled"), "values": [r["cancelled"]   for r in data]},
        ],
        default="line",
    )
    summary = _summary([
        (_("Total Orders"),  sum(r["order_count"] for r in data), "blue"),
        (_("Total Revenue"), sum(r["revenue"]     for r in data), "green"),
        (_("Delivered"),     sum(r["delivered"]   for r in data), "orange"),
        (_("Cancelled"),     sum(r["cancelled"]   for r in data), "red"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 6. Product Views (no Sales Order filters apply)
# --------------------------------------------------------------------------- #
def _product_views(f):
    filters = {"is_published": 1}
    if f.get("brand"):
        filters["brand"] = f.brand
    if f.get("item_group"):
        filters["item_group"] = f.item_group

    rows = frappe.get_all("DL Shop Item", filters=filters,
        fields=["item_code", "web_item_name_en", "brand", "item_group",
                "view_count", "wishlist_count", "review_count", "average_rating"],
        order_by="view_count desc", limit=100)

    data = [{
        "item_code":      r.item_code,
        "product_name":   r.web_item_name_en,
        "brand":          r.brand or "",
        "category":       r.item_group or "",
        "view_count":     r.view_count or 0,
        "wishlist_count": r.wishlist_count or 0,
        "review_count":   r.review_count or 0,
        "avg_rating":     flt(r.average_rating or 0),
    } for r in rows]

    columns = [
        {"label": _("Item Code"),    "fieldname": "item_code",      "fieldtype": "Link",  "options": "Item", "width": 130},
        {"label": _("Product Name"), "fieldname": "product_name",   "fieldtype": "Data",  "width": 210},
        {"label": _("Brand"),        "fieldname": "brand",          "fieldtype": "Data",  "width": 110},
        {"label": _("Category"),     "fieldname": "category",       "fieldtype": "Data",  "width": 130},
        {"label": _("Views"),        "fieldname": "view_count",     "fieldtype": "Int",   "width": 90},
        {"label": _("Wishlisted"),   "fieldname": "wishlist_count", "fieldtype": "Int",   "width": 90},
        {"label": _("Reviews"),      "fieldname": "review_count",   "fieldtype": "Int",   "width": 90},
        {"label": _("Avg Rating"),   "fieldname": "avg_rating",     "fieldtype": "Float", "width": 100, "precision": 1},
    ]
    chart = _make_chart(f, [r["product_name"] for r in data[:15]], [
        {"name": _("Views"),      "values": [r["view_count"]     for r in data[:15]]},
        {"name": _("Wishlisted"), "values": [r["wishlist_count"] for r in data[:15]]},
    ], default="bar")
    summary = _summary([
        (_("Total Products"),   len(data),                                "blue"),
        (_("Total Views"),      sum(r["view_count"]     for r in data),   "green"),
        (_("Total Wishlisted"), sum(r["wishlist_count"] for r in data),   "orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 7. Wishlist
# --------------------------------------------------------------------------- #
def _wishlist(f):
    rows = frappe.db.sql("""
        SELECT COUNT(wl.name) AS wishlist_count,
               di.web_item_name_en AS product_name,
               di.brand, di.item_group, di.average_rating
        FROM `tabDL Shop Wishlist Item` wl
        JOIN `tabDL Shop Item` di ON di.name = wl.item_route
        WHERE di.is_published = 1
        GROUP BY wl.item_route
        ORDER BY wishlist_count DESC
        LIMIT 50
    """, as_dict=True)

    data = [{
        "product_name":   r.product_name,
        "brand":          r.brand or "",
        "category":       r.item_group or "",
        "wishlist_count": r.wishlist_count,
        "avg_rating":     flt(r.average_rating or 0),
    } for r in rows]

    columns = [
        {"label": _("Product Name"),  "fieldname": "product_name",   "fieldtype": "Data",  "width": 220},
        {"label": _("Brand"),         "fieldname": "brand",          "fieldtype": "Data",  "width": 120},
        {"label": _("Category"),      "fieldname": "category",       "fieldtype": "Data",  "width": 140},
        {"label": _("Wishlisted By"), "fieldname": "wishlist_count", "fieldtype": "Int",   "width": 120},
        {"label": _("Avg Rating"),    "fieldname": "avg_rating",     "fieldtype": "Float", "width": 100, "precision": 1},
    ]
    chart = _make_chart(f, [r["product_name"] for r in data[:15]], [
        {"name": _("Wishlist Count"), "values": [r["wishlist_count"] for r in data[:15]]},
    ], default="bar")
    summary = _summary([
        (_("Products Wishlisted"),    len(data),                                "blue"),
        (_("Total Wishlist Entries"), sum(r["wishlist_count"] for r in data),   "green"),
        (_("Top Wishlisted"),         data[0]["product_name"] if data else "-", "orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 8. Reviews
# --------------------------------------------------------------------------- #
def _reviews(f):
    rows = frappe.db.sql("""
        SELECT di.web_item_name_en AS product_name, di.brand, di.item_group,
               COUNT(rv.name)                                       AS total_reviews,
               SUM(CASE WHEN rv.is_approved=1 THEN 1 ELSE 0 END)   AS approved,
               SUM(CASE WHEN rv.is_approved=0 THEN 1 ELSE 0 END)   AS pending,
               ROUND(AVG(rv.rating), 1)                             AS avg_rating,
               MIN(rv.rating) AS min_rating, MAX(rv.rating) AS max_rating
        FROM `tabDL Shop Review` rv
        JOIN `tabDL Shop Item` di ON di.name = rv.item_route
        GROUP BY rv.item_route
        ORDER BY total_reviews DESC
        LIMIT 50
    """, as_dict=True)

    data = [{
        "product_name":  r.product_name,
        "brand":         r.brand or "",
        "category":      r.item_group or "",
        "total_reviews": r.total_reviews,
        "approved":      r.approved or 0,
        "pending":       r.pending or 0,
        "avg_rating":    flt(r.avg_rating or 0),
        "min_rating":    r.min_rating or 0,
        "max_rating":    r.max_rating or 0,
    } for r in rows]

    columns = [
        {"label": _("Product Name"),  "fieldname": "product_name",  "fieldtype": "Data",  "width": 220},
        {"label": _("Brand"),         "fieldname": "brand",         "fieldtype": "Data",  "width": 110},
        {"label": _("Category"),      "fieldname": "category",      "fieldtype": "Data",  "width": 130},
        {"label": _("Total Reviews"), "fieldname": "total_reviews", "fieldtype": "Int",   "width": 110},
        {"label": _("Approved"),      "fieldname": "approved",      "fieldtype": "Int",   "width": 90},
        {"label": _("Pending"),       "fieldname": "pending",       "fieldtype": "Int",   "width": 90},
        {"label": _("Avg Rating"),    "fieldname": "avg_rating",    "fieldtype": "Float", "width": 100, "precision": 1},
        {"label": _("Min Rating"),    "fieldname": "min_rating",    "fieldtype": "Int",   "width": 90},
        {"label": _("Max Rating"),    "fieldname": "max_rating",    "fieldtype": "Int",   "width": 90},
    ]
    chart = _make_chart(f, [r["product_name"] for r in data[:15]], [
        {"name": _("Avg Rating"),    "values": [r["avg_rating"]    for r in data[:15]]},
        {"name": _("Total Reviews"), "values": [r["total_reviews"] for r in data[:15]]},
    ], default="bar")
    summary = _summary([
        (_("Products Reviewed"), len(data),                             "blue"),
        (_("Total Reviews"),     sum(r["total_reviews"] for r in data), "green"),
        (_("Pending Approval"),  sum(r["pending"]       for r in data), "orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 9. Visitor Countries — where visitors come from
# --------------------------------------------------------------------------- #
def _visitor_countries(f):
    from_c = "AND timestamp >= %(from_date)s" if f.get("from_date") else ""
    to_c   = "AND timestamp <= %(to_date)s"   if f.get("to_date") else ""

    rows = frappe.db.sql(f"""
        SELECT
            COALESCE(NULLIF(country, ''), 'Unknown')  AS country,
            COALESCE(NULLIF(country_code,''), '--')   AS country_code,
            COUNT(*)                                   AS visits,
            COUNT(DISTINCT session_id)                 AS unique_sessions,
            COUNT(DISTINCT NULLIF(user,''))            AS logged_in_users
        FROM `tabDL Shop Visitor Log`
        WHERE sales_order IS NULL OR sales_order = ''
          {from_c} {to_c}
        GROUP BY country, country_code
        ORDER BY visits DESC
        LIMIT 60
    """, {"from_date": f.get("from_date"), "to_date": f.get("to_date")}, as_dict=True)

    total_visits = sum(r.visits for r in rows)
    data = [{
        "country":         r.country,
        "country_code":    r.country_code,
        "visits":          r.visits,
        "unique_sessions": r.unique_sessions,
        "logged_in_users": r.logged_in_users or 0,
        "visit_share":     round(r.visits / total_visits * 100, 1) if total_visits else 0,
    } for r in rows]

    columns = [
        {"label": _("Country"),        "fieldname": "country",         "fieldtype": "Data", "width": 180},
        {"label": _("Code"),           "fieldname": "country_code",    "fieldtype": "Data", "width": 70},
        {"label": _("Page Views"),     "fieldname": "visits",          "fieldtype": "Int",  "width": 110},
        {"label": _("Unique Sessions"),"fieldname": "unique_sessions", "fieldtype": "Int",  "width": 130},
        {"label": _("Logged-in Users"),"fieldname": "logged_in_users", "fieldtype": "Int",  "width": 130},
        {"label": _("Share %"),        "fieldname": "visit_share",     "fieldtype": "Percent","width": 110},
    ]

    chart_type = f.get("chart_type") or "bar"
    chart = _make_chart(f, [r["country"] for r in data[:15]], [
        {"name": _("Page Views"),      "values": [r["visits"]          for r in data[:15]]},
        {"name": _("Unique Sessions"), "values": [r["unique_sessions"] for r in data[:15]]},
    ], default=chart_type)

    summary = _summary([
        (_("Countries"),       len(data),          "blue"),
        (_("Total Page Views"), total_visits,       "green"),
        (_("Unique Sessions"), sum(r["unique_sessions"] for r in data), "orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# 10. Order Countries — where orders come from
# --------------------------------------------------------------------------- #
def _order_countries(f):
    from_c = "AND vl.timestamp >= %(from_date)s" if f.get("from_date") else ""
    to_c   = "AND vl.timestamp <= %(to_date)s"   if f.get("to_date") else ""
    sj, dsc, exw = _so_status_conditions(f)
    # For order countries, docstatus condition applies to the Sales Order join
    dsc_so = dsc.replace("so.", "so.")

    rows = frappe.db.sql(f"""
        SELECT
            COALESCE(NULLIF(vl.country,''), 'Unknown') AS country,
            COALESCE(NULLIF(vl.country_code,''), '--') AS country_code,
            COALESCE(NULLIF(vl.city,''), '')           AS top_city,
            COUNT(DISTINCT vl.sales_order)             AS order_count,
            SUM(so.grand_total)                        AS revenue,
            AVG(so.grand_total)                        AS avg_order
        FROM `tabDL Shop Visitor Log` vl
        JOIN `tabSales Order` so ON so.name = vl.sales_order
        {sj}
        WHERE vl.sales_order IS NOT NULL AND vl.sales_order != ''
          AND {dsc_so}
          {from_c} {to_c} {exw}
        GROUP BY vl.country, vl.country_code
        ORDER BY revenue DESC
        LIMIT 60
    """, {"from_date": f.get("from_date"), "to_date": f.get("to_date")}, as_dict=True)

    total_rev = sum(flt(r.revenue) for r in rows)
    data = [{
        "country":       r.country,
        "country_code":  r.country_code,
        "order_count":   r.order_count,
        "revenue":       flt(r.revenue),
        "avg_order":     flt(r.avg_order),
        "revenue_share": round(flt(r.revenue) / total_rev * 100, 1) if total_rev else 0,
    } for r in rows]

    columns = [
        {"label": _("Country"),         "fieldname": "country",       "fieldtype": "Data",     "width": 180},
        {"label": _("Code"),            "fieldname": "country_code",  "fieldtype": "Data",     "width": 70},
        {"label": _("Orders"),          "fieldname": "order_count",   "fieldtype": "Int",      "width": 90},
        {"label": _("Revenue"),         "fieldname": "revenue",       "fieldtype": "Currency", "width": 130},
        {"label": _("Avg Order"),       "fieldname": "avg_order",     "fieldtype": "Currency", "width": 120},
        {"label": _("Revenue Share %"), "fieldname": "revenue_share", "fieldtype": "Percent",  "width": 120},
    ]

    chart_type = f.get("chart_type") or "bar"
    chart = _make_chart(f, [r["country"] for r in data], [
        {"name": _("Revenue"),    "values": [r["revenue"]     for r in data]},
        {"name": _("Orders"),     "values": [r["order_count"] for r in data]},
    ], default=chart_type)

    summary = _summary([
        (_("Countries"),    len(data),    "blue"),
        (_("Total Revenue"), total_rev,   "green"),
        (_("Total Orders"), sum(r["order_count"] for r in data), "orange"),
    ])
    return columns, data, None, chart, summary, 0


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _make_chart(f, labels, datasets, default="bar"):
    return {
        "data": {"labels": labels, "datasets": datasets},
        "type": f.get("chart_type") or default,
        "fieldtype": "Currency",
    }


def _get_period_label(date, range_type):
    d = getdate(date)
    if range_type == "Weekly":
        return f"W{d.isocalendar()[1]} {d.year}"
    if range_type == "Quarterly":
        return f"Q{(d.month-1)//3+1} {d.year}"
    return d.strftime("%b %Y")


def _summary(items):
    result = []
    for label, value, color in items:
        result.append({
            "value":     value,
            "label":     label,
            "datatype":  "Data" if isinstance(value, str) else "Float" if isinstance(value, float) else "Int",
            "indicator": color,
        })
    return result
