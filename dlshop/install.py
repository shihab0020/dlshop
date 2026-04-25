"""Post-install setup: create default DL Shop Settings and seed initial data."""

import frappe


def after_install():
    create_default_settings()
    create_default_nav_items()
    create_default_footer()
    fix_desktop_icon()
    frappe.db.commit()
    print("✓ DL Shop installed successfully")


def fix_desktop_icon():
    """Ensure the DL Shop desktop icon is visible on the main desk.

    The sentinel file dlshop/desktop_icon/dl_shop.json makes Frappe's
    orphan-detection (model/sync.py remove_orphan_entities) find this icon
    in the app's file tree, so it won't be deleted even with app+standard set.
    """
    if frappe.db.exists("Desktop Icon", "DL Shop"):
        frappe.db.set_value(
            "Desktop Icon", "DL Shop",
            {
                "standard": 1,
                "hidden": 0,
                "app": "dlshop",
                "icon": "retail",
                "logo_url": "/assets/dlshop/images/desk_icon.svg",
            },
            update_modified=False,
        )
    else:
        # Create fresh — fires after_install (before auto_generate_icons)
        # or after the icon was recreated from the sentinel JSON.
        try:
            frappe.get_doc({
                "doctype": "Desktop Icon",
                "label": "DL Shop",
                "link": "/desk/dl-shop",
                "icon_type": "App",
                "icon": "retail",
                "app": "dlshop",
                "standard": 1,
                "hidden": 0,
                "logo_url": "/assets/dlshop/images/desk_icon.svg",
            }).insert(ignore_permissions=True, ignore_if_duplicate=True)
        except Exception:
            pass
    frappe.db.commit()


def create_default_settings():
    if frappe.db.exists("DL Shop Settings", "DL Shop Settings"):
        return
    settings = frappe.get_doc({
        "doctype": "DL Shop Settings",
        "site_name_en": "My Online Shop",
        "site_name_ar": "متجري الإلكتروني",
        "site_description_en": "Welcome to our online store",
        "site_description_ar": "مرحبًا بكم في متجرنا الإلكتروني",
        "primary_color": "#1a73e8",
        "secondary_color": "#ffffff",
        "accent_color": "#e53935",
        "navbar_bg_color": "#ffffff",
        "guest_checkout_enabled": 1,
        "enable_reviews": 1,
        "auto_approve_reviews": 0,
        "products_per_page": 20,
        "cod_enabled": 1,
        "cod_charge": 0,
        "default_currency": "SAR",
    })
    settings.insert(ignore_permissions=True)


def create_default_nav_items():
    if frappe.db.count("DL Shop Navigation Item") > 0:
        return
    nav_items = [
        {"label_en": "Shop", "label_ar": "المتجر", "url": "/shop", "sort_order": 1},
        {"label_en": "New Arrivals", "label_ar": "وصل حديثًا", "url": "/shop?is_new_arrival=1", "sort_order": 2},
        {"label_en": "Sale", "label_ar": "التخفيضات", "url": "/shop?is_on_sale=1", "sort_order": 3},
    ]
    for item in nav_items:
        frappe.get_doc(dict(doctype="DL Shop Navigation Item", is_active=1, **item)).insert(ignore_permissions=True)


def create_default_footer():
    if frappe.db.count("DL Shop Footer Section") > 0:
        return
    sections = [
        {
            "title_en": "Quick Links",
            "title_ar": "روابط سريعة",
            "sort_order": 1,
            "links": [
                {"label_en": "Shop", "label_ar": "المتجر", "url": "/shop"},
                {"label_en": "My Account", "label_ar": "حسابي", "url": "/account"},
                {"label_en": "Track Order", "label_ar": "تتبع الطلب", "url": "/account/orders"},
            ],
        },
        {
            "title_en": "Help",
            "title_ar": "المساعدة",
            "sort_order": 2,
            "links": [
                {"label_en": "Contact Us", "label_ar": "تواصل معنا", "url": "/contact"},
                {"label_en": "Privacy Policy", "label_ar": "سياسة الخصوصية", "url": "/privacy"},
                {"label_en": "Terms of Service", "label_ar": "شروط الاستخدام", "url": "/terms"},
            ],
        },
    ]
    for sec in sections:
        links = sec.pop("links")
        doc = frappe.get_doc(dict(doctype="DL Shop Footer Section", is_active=1, **sec))
        for link in links:
            doc.append("links", link)
        doc.insert(ignore_permissions=True)
