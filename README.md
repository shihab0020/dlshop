# DLShop — Bilingual E-Commerce Storefront for Frappe & ERPNext

> Open-source e-commerce storefront built for the Saudi & Gulf market — bilingual Arabic/English, RTL-ready, official SAR symbol (⃁), Tabby BNPL integration, and full order management.

DLShop is a **Frappe app** that adds a complete, production-ready online store front-end on top of your existing ERPNext setup. No separate e-commerce platform needed — your ERPNext items, pricing, and orders are the single source of truth.

---

## Features

### Storefront
- **Bilingual Arabic / English** — full RTL support for Arabic, switchable per-URL (`/shop/ar`, `/shop/en`)
- **Product catalog** with category navigation, brand filtering, price range filter, and sort options
- **Product detail page** — image gallery, description tabs, customer reviews & ratings
- **Flash deals** section with live countdown timer
- **Search** with live suggestions and full results page

### Shopping
- **Shopping cart** — add, update quantity, remove items; persists per session
- **Wishlist** — save items for later (logged-in users)
- **Coupon codes** — fixed amount or percentage discounts with minimum order rules
- **Checkout** — delivery or store pickup, guest checkout supported
- **Multiple payment methods** — Cash on Delivery (COD) and [Tabby](https://tabby.ai) Buy Now Pay Later

### Accounts & Orders
- **Customer registration & login** with email verification
- **Order history** with status tracking and delivery status
- **Address book** management
- **Profile management**

### Admin & Configuration
- **DL Shop Settings** — single DocType to control everything:
  - Site name (AR/EN), logo, colors (primary, secondary, accent, navbar, footer)
  - Flash deals background & text colors
  - Social media links (Instagram, Facebook, X/Twitter, TikTok, YouTube, WhatsApp)
  - Support email & phone
  - Google Analytics & Google Tag Manager IDs
  - Custom CSS / head HTML / body HTML injection
  - Maintenance mode with custom message
- **Configurable navigation** — custom nav items with dropdowns, footer sections and links
- **Category tree** — nested categories shown in navbar and category bar

### Technical
- Built on **Bootstrap 5** (not Frappe's Bootstrap 4 — no conflicts)
- **Official SAR symbol** (⃁ U+20C1, SAMA Unicode 17.0) with bundled font — works offline
- Security hardened: XSS prevention, rate limiting, input validation, SQL injection protection
- N+1 query elimination — batch DB fetches throughout
- **Fully offline-capable** — all fonts and assets served locally, no CDN dependency at runtime

---

## Screenshots

### Storefront — Home Page
<img width="1140" alt="DLShop Home Page" src="https://github.com/user-attachments/assets/ac89b5ed-789b-4447-9bea-660f34a07322" />

### Customer Dashboard
<img width="1154" alt="Customer Dashboard" src="https://github.com/user-attachments/assets/881acdc6-d95e-4475-aa52-0a3d129de974" />

### ERPNext — DL Shop Settings
<img width="2305" alt="DL Shop Settings in ERPNext" src="https://github.com/user-attachments/assets/546359ba-ad56-4c14-be64-b46298773237" />

---

## Requirements

| Dependency | Version |
|---|---|
| Python | ≥ 3.10 |
| Frappe | v15 / v16 |
| ERPNext | v15 / v16 |
| Node.js | ≥ 18 |

---

## Installation

```bash
# From your bench directory
bench get-app https://github.com/shihab0020/dlshop.git --branch version-16
bench install-app dlshop
bench build --app dlshop
bench restart
```

---

## Quick Setup

After installation:

1. Open ERPNext desk → search **DL Shop Settings**
2. Set your site name (Arabic & English), logo, and brand colors
3. Create **DL Shop Items** (linked to your ERPNext Items) with images, descriptions, and pricing
4. Optionally create **DL Shop Categories** and assign items
5. Visit `/shop/en` or `/shop/ar`

---

## URL Structure

| Page | English | Arabic |
|---|---|---|
| Shop | `/shop/en` | `/shop/ar` |
| Product | `/shop/en/product/<route>` | `/shop/ar/product/<route>` |
| Search | `/search/en?q=...` | `/search/ar?q=...` |
| Cart | `/cart/en` | `/cart/ar` |
| Checkout | `/checkout/en` | `/checkout/ar` |
| Login / Register | `/auth/en` | `/auth/ar` |
| Account | `/account/en` | `/account/ar` |
| Orders | `/account/orders/en` | `/account/orders/ar` |

---

## Payment Integration

### Cash on Delivery
Enabled by default. No configuration needed.

### Tabby (Buy Now Pay Later)
1. Get your API keys from [Tabby for Business](https://tabby.ai)
2. Add your **Tabby Public Key** and **Secret Key** in DL Shop Settings
3. Tabby will appear as a payment option at checkout

---

## License

[MIT](license.txt)

---

## Author

Built by [DLITS](https://github.com/shihab0020) — contributions and issues welcome.
