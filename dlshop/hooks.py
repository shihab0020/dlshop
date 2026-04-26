app_name = "dlshop"
app_title = "Dlits Shop"
app_publisher = "shihab0020"
app_description = "Dlits Shopping Cart and Online App"
app_email = "shihab0020@gmail.com"
app_license = "mit"
app_icon_url = "/assets/dlshop/images/logo.svg"
app_icon_title = "Dlits Shop"
app_icon_route = "/desk/dl-shop"

# Apps Screen
add_to_apps_screen = [
    {
        "name": "dlshop",
        "logo": "/assets/dlshop/images/logo.svg",
        "title": "DL Shop",
        "route": "/desk/dl-shop",
        "has_permission": "dlshop.utils.has_app_permission",
    }
]

# Web Assets — included directly in layout.html (Bootstrap 5 + dlshop)
web_include_css = []
web_include_js = []

# Desk Assets (ERPNext admin)
app_include_css = ["/assets/dlshop/css/dlshop_desk.css"]

# Jinja Filters & Methods
jinja = {
    "methods": ["dlshop.utils"],
    "filters": ["dlshop.utils.currency", "dlshop.utils.bilingual"],
}

# Fixtures — export/import app-bundled records
fixtures = [
    {"dt": "Workspace", "filters": [["name", "=", "DL Shop"]]}
]

# Installation
after_install = "dlshop.install.after_install"
after_migrate = ["dlshop.install.fix_desktop_icon"]

# Document Events
doc_events = {
    "Sales Order": {
        "on_submit": "dlshop.api.cart.on_sales_order_submit",
    },
}

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "dlshop.tasks.cleanup_expired_carts",
        "dlshop.tasks.cleanup_expired_coupons",
    ],
}

# Bilingual Website Route Rules
# Pattern: /{page}/{lang} and /{page}/{lang}/{rest}
# e.g.  /shop/ar  →  shop  (Arabic)
#        /shop/en  →  shop  (English)
website_route_rules = [
    # Product detail pages — static lang segment so these beat /shop/en/<path:category>
    {"from_route": "/shop/en/product/<path:item_route>", "to_route": "product"},
    {"from_route": "/shop/ar/product/<path:item_route>", "to_route": "product"},
    # Tabby payment return
    {"from_route": "/tabby-return", "to_route": "tabby_return"},
    # Shop (must come before generic category catch-all)
    {"from_route": "/shop/ar", "to_route": "shop"},
    {"from_route": "/shop/en", "to_route": "shop"},
    {"from_route": "/shop/ar/<path:category>", "to_route": "shop"},
    {"from_route": "/shop/en/<path:category>", "to_route": "shop"},
    # Cart
    {"from_route": "/cart/ar", "to_route": "cart"},
    {"from_route": "/cart/en", "to_route": "cart"},
    # Checkout
    {"from_route": "/checkout/ar", "to_route": "checkout"},
    {"from_route": "/checkout/en", "to_route": "checkout"},
    # Search
    {"from_route": "/search/ar", "to_route": "search"},
    {"from_route": "/search/en", "to_route": "search"},
    # Account
    {"from_route": "/account/ar", "to_route": "account"},
    {"from_route": "/account/en", "to_route": "account"},
    {"from_route": "/account/orders/ar", "to_route": "account/orders"},
    {"from_route": "/account/orders/en", "to_route": "account/orders"},
    {"from_route": "/account/order/<name>/ar", "to_route": "account/order"},
    {"from_route": "/account/order/<name>/en", "to_route": "account/order"},
    {"from_route": "/account/wishlist/ar", "to_route": "account/wishlist"},
    {"from_route": "/account/wishlist/en", "to_route": "account/wishlist"},
    {"from_route": "/account/addresses/ar", "to_route": "account/addresses"},
    {"from_route": "/account/addresses/en", "to_route": "account/addresses"},
    {"from_route": "/account/profile/ar", "to_route": "account/profile"},
    {"from_route": "/account/profile/en", "to_route": "account/profile"},
    # Auth (login + register combined page)
    {"from_route": "/auth/ar", "to_route": "auth"},
    {"from_route": "/auth/en", "to_route": "auth"},
    # Static info pages
    {"from_route": "/contact/ar", "to_route": "contact"},
    {"from_route": "/contact/en", "to_route": "contact"},
    {"from_route": "/privacy/ar", "to_route": "privacy"},
    {"from_route": "/privacy/en", "to_route": "privacy"},
    {"from_route": "/terms/ar", "to_route": "terms"},
    {"from_route": "/terms/en", "to_route": "terms"},
    # Plain /account/order/<name> (no lang suffix)
    {"from_route": "/account/order/<name>", "to_route": "account/order"},
    # Generic category (no lang suffix, backward-compat)
    {"from_route": "/shop/<path:category>", "to_route": "shop"},
]

# Override Website Context
override_whitelisted_methods = {}

# Permissions
permission_query_conditions = {
    "DL Shop Cart": "dlshop.api.cart.get_cart_permission_query",
    "DL Shop Review": "dlshop.api.shop.get_review_permission_query",
    "DL Shop Wishlist Item": "dlshop.api.account.get_wishlist_permission_query",
    "DL Shop Newsletter Subscriber": "dlshop.api.account.get_newsletter_permission_query",
}

# User Data Protection (GDPR)
user_data_fields = [
    {
        "doctype": "DL Shop Cart",
        "filter_by": "owner",
        "redact_fields": ["phone", "notes"],
        "partial": 1,
    },
    {
        "doctype": "DL Shop Wishlist Item",
        "filter_by": "owner",
    },
    {
        "doctype": "DL Shop Newsletter Subscriber",
        "filter_by": "email",
        "partial": 1,
    },
]
