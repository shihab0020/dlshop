# DL Shop — Bilingual E-Commerce Storefront for Frappe & ERPNext

> Production-ready online store built for the Saudi & Gulf market — bilingual Arabic/English, full RTL support, official SAR symbol (⃁), Tabby BNPL integration, and complete order management — all on top of your existing ERPNext installation.

DL Shop is a **Frappe v16 app** that adds a complete storefront and admin workspace on top of ERPNext. No separate e-commerce platform needed — your ERPNext items, pricing, customers, and orders are the single source of truth.

---

## Features

### Storefront & Navigation
- **Bilingual Arabic / English** — full RTL layout for Arabic; language is part of the URL (`/shop/ar`, `/shop/en`) so every page is directly shareable and crawlable
- **Language switcher** — swaps `ar` ↔ `en` in the current URL without a page reload
- **Configurable navigation bar** — custom nav items with optional dropdowns, managed from the ERPNext desk
- **Category bar** — nested category tree rendered below the navbar
- **Configurable footer** — multiple sections with custom links, managed from the desk
- **Static info pages** — `/contact`, `/privacy`, `/terms` with bilingual content and working lang-suffixed routes (`/contact/en`, `/contact/ar`, etc.)
- **Maintenance mode** — set a custom AR/EN message and lock the storefront with one toggle in settings

### Product Catalog
- **Shop page** — grid layout, category sidebar, brand filter, price range slider, sort options (price, name, popularity, newest)
- **Category browsing** — nested categories in sidebar and URL (`/shop/en/electronics`)
- **Product detail page** — image gallery with thumbnails, bilingual name & description, tabs for details/reviews, related products
- **New arrivals** and **sale / discounted** product flags with configurable badge text
- **Flash deals section** — highlighted products with live countdown timer (configurable background & accent colors)
- **Virtual stock** — optional capped-quantity mode per item (limits orders regardless of warehouse stock)

### Search
- **Search page** (`/search/en?q=…`) with results via API
- Searches item name (AR & EN), description, SKU, and brand
- Paginated results
- XSS-safe: search query JSON-encoded in JS context

### Shopping & Checkout
- **Cart** — add / update qty / remove; persists across sessions for guests and logged-in users
- **Wishlist** — save items for later (logged-in users only)
- **Coupon codes** — fixed-amount or percentage discount; minimum order amount; per-user and total usage limits; expiry date
- **Checkout flow** — delivery address or store pickup selection, guest checkout (no account required), order notes
- **Shipping rules** — weight or value-based shipping charge calculation
- **Multiple payment methods**
  - Cash on Delivery (COD) with configurable COD surcharge
  - [Tabby](https://tabby.ai) Buy Now Pay Later — full redirect flow with webhook return handling
- **Race-condition safe** — cart atomically locked before Sales Order creation; double-submit rejected

### Customer Accounts
- **Registration & login** — email + password; rate-limited (5 registrations / 10 min, 10 logins / min per IP); ERPNext Customer + Contact created automatically
- **Account dashboard** — order summary and quick links
- **Order history** — paginated list with status, delivery status, grand total
- **Order detail** — full line-items, address, payment method, approval status
- **Order cancellation** — optional; configurable time window; supports direct cancel or approval-required workflow
- **Cancellation requests** — customer submits reason; admin approves or rejects from the desk
- **Address book** — add, edit, delete shipping/billing addresses
- **Profile** — update name, phone, email

### Order Management (ERPNext Desk)
- **DL Shop Cart** — live view of all active, processing, converted, and abandoned carts
- **DL Shop Order Approval** — admin reviews and approves/rejects pending orders before fulfilment
- **DL Shop Cancel Request** — customer-submitted cancellation requests with reason; admin approves or rejects
- **Sales Order integration** — cart converts to a submitted Frappe Sales Order; `on_submit` hook keeps cart status in sync

### Engagement
- **Customer reviews & ratings** — 1–5 star with text; optional auto-approve; review gating (purchase required toggle); displayed on product page with average rating
- **Newsletter subscriber** — email signup form with language preference; rate-limited (5 / 5 min)
- **Customer inquiry** — contact form with optional order reference; rate-limited (5 / 10 min); order ownership validated for logged-in users
- **Visitor log** — country recorded per order and per page visit for geo analytics

### Payments — Tabby BNPL
- Full checkout integration: create Tabby session → redirect buyer → handle `/tabby-return` webhook
- Tabby public key and secret stored securely via Frappe's encrypted `get_password()`
- **DL Tabby Log** doctype records every transaction (request / success / failure)

### Analytics & Reports
- **DL Shop Analytics** query report in the ERPNext desk
  - Revenue by period, top products, top categories, order count, average order value
  - Visitor country breakdown from Visitor Log
- **Visitor Log** — country per session for geo dashboards

### Admin Workspace (ERPNext Desk)
DL Shop gets its own workspace on the ERPNext main desk grid and sidebar with a branded icon (shopping bag + "DL" in indigo):

| Card | DocTypes / Reports |
|---|---|
| **Catalog** | DL Shop Item, Category, Banner, Coupon |
| **Orders & Customers** | Cart, Order Approval, Cancel Request, Inquiry |
| **Engagement** | Review, Wishlist Item, Newsletter Subscriber, Visitor Log |
| **Payments** | DL Tabby Log, DL Tabby Settings |
| **Analytics & Reports** | DL Shop Analytics (query report) |
| **Settings** | DL Shop Settings, Pickup Location, Navigation Item, Footer Section |

The workspace icon **survives reinstalls and `bench migrate`** via an `after_migrate` hook backed by a sentinel fixture file (`dlshop/desktop_icon/dl_shop.json`) — Frappe's orphan-detection finds it and never deletes it.

### DL Shop Settings (single DocType controls everything)

| Group | Fields |
|---|---|
| Branding | Site name AR/EN, logo URL, favicon |
| Colors | Primary, secondary, accent, navbar bg, footer bg & text, flash deals bg & accent |
| Social | Instagram, Facebook, X/Twitter, TikTok, YouTube, WhatsApp |
| Support | Support email, support phone |
| Analytics | Google Analytics ID, Google Tag Manager ID |
| Custom code | Custom CSS, custom `<head>` HTML, custom `<body>` HTML |
| Commerce | Products per page, default currency, warehouse, price list, tax template, cost center |
| Checkout | Guest checkout toggle, COD enabled/charge, Tabby enabled |
| Reviews | Enable reviews, auto-approve, require purchase before review |
| Orders | Allow cancellation, cancellation window (hours), require cancel approval |
| Order Approval | Enable order approval workflow |
| Maintenance | Maintenance mode toggle, custom AR/EN message |

---

## Security

| Concern | Mitigation |
|---|---|
| XSS in JS context | `\| tojson` for all values rendered inside `<script>` blocks |
| Open redirect | `redirect_to` validated: must start with `/` and not `//` |
| IDOR on orders | All order APIs verify the order belongs to the current user's customer record |
| IDOR on inquiry | `order_id` ownership validated against the logged-in user's customer |
| Double-submit / race condition | Cart atomically flipped `Active → Processing` via `UPDATE … WHERE status='Active'`; `ROW_COUNT()=0` aborts the duplicate |
| Rate limiting | Fixed-window Redis counter per IP: registration (5/10 min), login (10/min), newsletter (5/5 min), inquiry (5/10 min) |
| SQL injection | Frappe ORM parameterised queries throughout; `frappe.db.escape()` in any raw SQL |
| CSRF | Non-guest API methods protected by Frappe's default CSRF token |
| Secrets | Tabby keys via `get_password()` (Frappe encrypted field) |
| Input sanitisation | All free-text inputs stripped and length-capped at system boundaries |
| Permission queries | Cart, review, wishlist, and newsletter records filtered to owner at query level via `permission_query_conditions` |

---

## URL Structure

| Page | English | Arabic |
|---|---|---|
| Shop | `/shop/en` | `/shop/ar` |
| Shop + category | `/shop/en/<category>` | `/shop/ar/<category>` |
| Product | `/shop/en/product/<route>` | `/shop/ar/product/<route>` |
| Search | `/search/en?q=…` | `/search/ar?q=…` |
| Cart | `/cart/en` | `/cart/ar` |
| Checkout | `/checkout/en` | `/checkout/ar` |
| Login / Register | `/auth/en` | `/auth/ar` |
| Account | `/account/en` | `/account/ar` |
| Orders | `/account/orders/en` | `/account/orders/ar` |
| Order detail | `/account/order/<name>/en` | `/account/order/<name>/ar` |
| Wishlist | `/account/wishlist/en` | `/account/wishlist/ar` |
| Addresses | `/account/addresses/en` | `/account/addresses/ar` |
| Profile | `/account/profile/en` | `/account/profile/ar` |
| Contact | `/contact/en` | `/contact/ar` |
| Privacy Policy | `/privacy/en` | `/privacy/ar` |
| Terms of Service | `/terms/en` | `/terms/ar` |

---

## Requirements

| Dependency | Version |
|---|---|
| Python | ≥ 3.10 |
| Frappe | v16 |
| ERPNext | v16 |
| Node.js | ≥ 18 |

---

## Installation

```bash
# From your bench directory
bench get-app https://github.com/shihab0020/dlshop.git --branch version-16
bench --site <your-site> install-app dlshop
bench build --app dlshop
bench --site <your-site> migrate
bench restart
```

---

## Quick Setup

1. Open ERPNext desk → **DL Shop** workspace (or search "DL Shop Settings")
2. Set your site name (AR & EN), logo URL, and brand colors
3. Create **DL Shop Items** linked to your ERPNext Items — add images, bilingual names/descriptions, price, and a URL route slug
4. Create **DL Shop Categories** and assign items to them
5. *(Optional)* Configure navigation items, footer sections, and pickup locations
6. Visit `/shop/en` or `/shop/ar`

---

## Payment Setup

### Cash on Delivery
Enabled by default in DL Shop Settings. Set a COD surcharge if needed.

### Tabby (Buy Now Pay Later)
1. Sign up at [tabby.ai](https://tabby.ai) and get your public key and secret key
2. In ERPNext → **DL Tabby Settings**: enter the keys, merchant code, and currency
3. Tabby will appear as a payment option at checkout automatically

---

## Scheduled Tasks

| Task | Schedule | Description |
|---|---|---|
| `cleanup_expired_carts` | Daily | Delete abandoned carts older than 30 days (500 per run) |
| `cleanup_expired_coupons` | Daily | Mark expired active coupons as inactive (500 per run) |

---

## Screenshots

### Storefront — Home Page
<img width="1140" alt="DLShop Home Page" src="https://github.com/user-attachments/assets/ac89b5ed-789b-4447-9bea-660f34a07322" />

### Customer Dashboard
<img width="1154" alt="Customer Dashboard" src="https://github.com/user-attachments/assets/881acdc6-d95e-4475-aa52-0a3d129de974" />

### ERPNext — DL Shop Settings
<img width="2305" alt="DL Shop Settings in ERPNext" src="https://github.com/user-attachments/assets/546359ba-ad56-4c14-be64-b46298773237" />

---

## Technical Notes

- **Bootstrap 5** bundled locally — no conflict with Frappe's Bootstrap 4
- **SAR symbol** (⃁ U+20C1, SAMA Unicode 17.0) rendered via a bundled WOFF2 font — no CDN required
- **No N+1 queries** — batch `get_all()` used throughout catalog, cart, and order APIs
- **Offline-capable** — all fonts, icons, and JS assets served from `/assets/dlshop/`
- **`after_migrate` hook** ensures the DL Shop desktop icon (`standard=1, hidden=0`) survives every `bench migrate` and reinstall
- Jinja helpers registered via `hooks.py jinja.methods` — `get_settings()`, `get_nav_items()`, `get_footer_sections()`, `get_categories()`, `localize_url()`, `bilingual()`, `is_rtl()` available in all templates

---

## License

[MIT](license.txt)

---

## Author

Built by [DLITS](https://github.com/shihab0020) — contributions and issues welcome.
