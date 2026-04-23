/* =============================================================
   shop.js — Product grid loader, filters, pagination
   Used by: /shop, /search
   ============================================================= */
(function () {
  'use strict';

  var cfg = window.dlShopConfig || window.dlSearchConfig || {};
  var lang = cfg.lang || 'en';
  var currency = cfg.currency || 'SAR';
  var currentPage = 1;
  var currentFilters = {
    category: cfg.categoryRoute || '',
    search: cfg.q || '',
    brand: '',
    min_price: '',
    max_price: '',
    sort_by: 'sort_order',
    sort_order: 'asc',
  };

  /* ── Render item card HTML ──────────────────────────────── */
  function renderCard(item) {
    var rtl = lang === 'ar';
    var name = rtl ? (item.web_item_name_ar || item.web_item_name_en) : (item.web_item_name_en || item.web_item_name_ar);
    var price = parseFloat(item.price) || 0;
    var rawSale = item.is_on_sale && item.sale_price ? parseFloat(item.sale_price) : null;
    var hasSale = rawSale && rawSale < price;
    /* U+20C1 — official SAMA Saudi Riyal symbol. Symbol appears left of amount. */
    var isSAR = !currency || currency === 'SAR';
    var sym = isSAR ? '⃁' : currency;
    function fmt(v) {
      var n = parseFloat(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2 });
      return sym + ' ' + n;
    }

    /* Price: only show strikethrough when actual discount exists */
    var priceHtml = hasSale
      ? '<span class="dl-price-sale">' + fmt(rawSale) + '</span> <span class="dl-price-orig">' + fmt(price) + '</span>'
      : '<span class="dl-price">' + fmt(rawSale || price) + '</span>';

    /* Single most-important badge */
    var badge = '';
    if (hasSale)                           badge = '<span class="dl-card-badge dl-badge-sale">' + (rtl ? 'خصم' : 'Sale') + '</span>';
    else if (item.is_new_arrival)          badge = '<span class="dl-card-badge dl-badge-new">'  + (rtl ? 'جديد' : 'New')  + '</span>';
    else { var bt = rtl ? (item.badge_text_ar||'') : (item.badge_text_en||'');
           if (bt) badge = '<span class="dl-card-badge dl-badge-custom">' + bt + '</span>'; }

    var img = item.featured_image
      ? '<img src="' + item.featured_image + '" class="card-img-top dl-card-img" loading="lazy" alt="' + name + '" />'
      : '<div class="dl-card-img dl-no-img d-flex align-items-center justify-content-center bg-light"><i class="fa fa-image fa-2x text-muted"></i></div>';

    return '<div class="col">' +
      '<div class="dl-item-card card h-100 border-0" data-item-code="' + item.item_code + '">' +
        '<a href="/shop/' + lang + '/product/' + item.route + '" class="dl-card-img-wrap">' +
          img + badge +
          '<button class="dl-wishlist-btn" data-route="' + item.route + '" aria-label="wishlist"><i class="fa fa-heart"></i></button>' +
        '</a>' +
        '<div class="card-body dl-card-body">' +
          '<a href="/shop/' + lang + '/product/' + item.route + '" class="text-decoration-none">' +
            '<p class="dl-card-title">' + name + '</p>' +
          '</a>' +
          '<div class="dl-card-price">' + priceHtml + '</div>' +
          '<button class="btn dl-add-to-cart-btn w-100 mt-2 dl-add-to-cart-btn" data-item-code="' + item.item_code + '" data-item-name="' + name + '">' +
            '<i class="fa fa-cart-plus"></i> ' + (rtl ? 'أضف للسلة' : 'Add to Cart') +
          '</button>' +
        '</div>' +
      '</div></div>';
  }

  /* ── Load products ──────────────────────────────────────── */
  window.dlLoadProducts = function (overrides) {
    var opts = Object.assign({}, currentFilters, overrides || {});
    var container = document.getElementById(opts.container || 'dl-products-grid');
    var paginationEl = document.getElementById(opts.paginationContainer || 'dl-pagination');
    var countEl = opts.countContainer ? document.getElementById(opts.countContainer) : document.getElementById('dl-total-text');
    if (!container) return;
    container.innerHTML = '<div class="col-12 text-center py-5"><div class="spinner-border text-primary"></div></div>';
    var sortParts = (opts.sort_by || 'sort_order').split('|');
    frappe.call({
      method: 'dlshop.api.shop.get_products',
      args: {
        page: opts.page || currentPage,
        category: opts.category || '',
        search: opts.search || '',
        brand: opts.brand || '',
        min_price: opts.min_price || '',
        max_price: opts.max_price || '',
        sort_by: sortParts[0],
        sort_order: sortParts[1] || 'asc',
        is_on_sale: opts.is_on_sale || '',
        is_new_arrival: opts.is_new_arrival || '',
        is_featured: opts.is_featured || '',
      },
      callback: function (r) {
        var data = r.message;
        if (!data || !data.items) { container.innerHTML = '<div class="col-12 text-center py-5 text-muted"><i class="fa fa-box-open fa-2x d-block mb-2"></i>' + (lang === 'ar' ? 'لا توجد منتجات' : 'No products found') + '</div>'; return; }
        if (!data.items.length) { container.innerHTML = '<div class="col-12 text-center py-5 text-muted"><i class="fa fa-box-open fa-2x d-block mb-2"></i>' + (lang === 'ar' ? 'لا توجد منتجات تطابق بحثك' : 'No products match your search') + '</div>'; return; }
        container.innerHTML = data.items.map(renderCard).join('');
        if (countEl) countEl.textContent = (lang === 'ar' ? 'عرض ' : 'Showing ') + data.items.length + (lang === 'ar' ? ' من ' : ' of ') + data.total + (lang === 'ar' ? ' منتج' : ' products');
        if (paginationEl) renderPagination(paginationEl, data.page, data.total_pages);
        loadBrandFilters();
      }
    });
  };

  /* ── Pagination ─────────────────────────────────────────── */
  function renderPagination(el, page, total) {
    if (total <= 1) { el.innerHTML = ''; return; }
    var html = '<nav><ul class="pagination justify-content-center flex-wrap gap-1">';
    html += '<li class="page-item' + (page <= 1 ? ' disabled' : '') + '"><a class="page-link" href="#" data-page="' + (page - 1) + '">&laquo;</a></li>';
    for (var p = Math.max(1, page - 2); p <= Math.min(total, page + 2); p++) {
      html += '<li class="page-item' + (p === page ? ' active' : '') + '"><a class="page-link" href="#" data-page="' + p + '">' + p + '</a></li>';
    }
    html += '<li class="page-item' + (page >= total ? ' disabled' : '') + '"><a class="page-link" href="#" data-page="' + (page + 1) + '">&raquo;</a></li>';
    html += '</ul></nav>';
    el.innerHTML = html;
    el.querySelectorAll('[data-page]').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); currentPage = parseInt(this.dataset.page); window.dlLoadProducts(); });
    });
  }

  /* ── Brand filter loader ────────────────────────────────── */
  function loadBrandFilters() {
    var el = document.getElementById('dl-brand-list');
    if (!el) return;
    frappe.call({ method: 'dlshop.api.shop.get_filters_data', args: { category: cfg.categoryRoute || '' },
      callback: function (r) {
        var brands = (r.message && r.message.brands) || [];
        if (!brands.length) { el.closest('#dl-brand-filter') && (el.closest('#dl-brand-filter').style.display = 'none'); return; }
        el.innerHTML = brands.map(function (b) {
          return '<div class="form-check"><input class="form-check-input dl-brand-cb" type="checkbox" id="br-' + b + '" value="' + b + '" /><label class="form-check-label" for="br-' + b + '">' + b + '</label></div>';
        }).join('');
        el.querySelectorAll('.dl-brand-cb').forEach(function (cb) {
          cb.addEventListener('change', function () {
            var checked = Array.from(el.querySelectorAll('.dl-brand-cb:checked')).map(function (c) { return c.value; });
            currentFilters.brand = checked.join(',');
            currentPage = 1;
            window.dlLoadProducts();
          });
        });
      }
    });
  }

  /* ── Sort ───────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    var sortSel = document.getElementById('dl-sort-select');
    if (sortSel) {
      sortSel.addEventListener('change', function () {
        currentFilters.sort_by = this.value;
        currentPage = 1;
        window.dlLoadProducts();
      });
    }

    /* Price filter */
    var applyPrice = document.getElementById('dl-apply-price');
    if (applyPrice) {
      applyPrice.addEventListener('click', function () {
        currentFilters.min_price = document.getElementById('dl-min-price').value;
        currentFilters.max_price = document.getElementById('dl-max-price').value;
        currentPage = 1;
        window.dlLoadProducts();
      });
    }

    /* Grid / list view toggle */
    var gridBtn = document.getElementById('dl-grid-view');
    var listBtn = document.getElementById('dl-list-view');
    var grid = document.getElementById('dl-products-grid');
    if (gridBtn && listBtn && grid) {
      gridBtn.addEventListener('click', function () {
        grid.className = 'row row-cols-2 row-cols-md-3 g-3';
        gridBtn.classList.add('active'); listBtn.classList.remove('active');
      });
      listBtn.addEventListener('click', function () {
        grid.className = 'row row-cols-1 g-3';
        listBtn.classList.add('active'); gridBtn.classList.remove('active');
      });
    }

    /* Initial load */
    if (document.getElementById('dl-products-grid')) window.dlLoadProducts();

    /* Flash deals countdown to midnight */
    initCountdown();

    /* Horizontal strip nav buttons */
    initStripNav();
  });

  /* ── Countdown timer (to midnight) ─────────────────────── */
  function initCountdown() {
    var h = document.getElementById('dl-t-h');
    var m = document.getElementById('dl-t-m');
    var s = document.getElementById('dl-t-s');
    if (!h) return;
    function tick() {
      var now = new Date();
      var midnight = new Date();
      midnight.setHours(24, 0, 0, 0);
      var diff = Math.max(0, Math.floor((midnight - now) / 1000));
      var hh = Math.floor(diff / 3600);
      var mm = Math.floor((diff % 3600) / 60);
      var ss = diff % 60;
      h.textContent = String(hh).padStart(2, '0');
      m.textContent = String(mm).padStart(2, '0');
      s.textContent = String(ss).padStart(2, '0');
    }
    tick();
    setInterval(tick, 1000);
  }

  /* ── Strip navigation buttons ───────────────────────────── */
  function initStripNav() {
    document.querySelectorAll('.dl-strip-nav').forEach(function (btn) {
      var stripId = btn.dataset.strip;
      var strip = document.getElementById(stripId);
      if (!strip) return;
      var isPrev = btn.classList.contains('prev');
      var scrollAmt = 380;

      btn.addEventListener('click', function () {
        strip.scrollBy({ left: isPrev ? -scrollAmt : scrollAmt, behavior: 'smooth' });
      });

      function updateVisibility() {
        var atStart = strip.scrollLeft <= 4;
        var atEnd = strip.scrollLeft + strip.clientWidth >= strip.scrollWidth - 4;
        btn.classList.toggle('dl-nav-hidden', isPrev ? atStart : atEnd);
      }
      strip.addEventListener('scroll', updateVisibility, { passive: true });
      updateVisibility();
    });
  }

})();
