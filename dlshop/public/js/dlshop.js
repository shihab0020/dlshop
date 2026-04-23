/* =============================================================
   dlshop.js — Global utilities: toast, cart badge, search,
   wishlist toggle, newsletter, logout, language switch
   ============================================================= */
(function () {
  'use strict';

  /* ── Security helpers ───────────────────────────────────── */
  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
  }
  /* Only allow relative paths and http/https URLs as image src */
  function safeSrc(u) {
    if (!u) return '';
    return (u.charAt(0) === '/' || /^https?:\/\//i.test(u)) ? u : '';
  }

  /* ── Toast ─────────────────────────────────────────────── */
  window.dlshopToast = function (msg, type, duration) {
    type = type || 'info';
    duration = duration || 3500;
    var container = document.getElementById('dl-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'dl-toast-container';
      document.body.appendChild(container);
    }
    var iconMap = { success: 'fa-check-circle', error: 'fa-times-circle', info: 'fa-info-circle' };
    var t = document.createElement('div');
    t.className = 'dl-toast ' + type;
    var ico = document.createElement('i');
    ico.className = 'fa ' + (iconMap[type] || 'fa-info-circle');
    var sp = document.createElement('span');
    sp.textContent = msg; /* textContent — never eval as HTML */
    t.appendChild(ico);
    t.appendChild(sp);
    container.appendChild(t);
    setTimeout(function () {
      t.style.opacity = '0';
      t.style.transition = 'opacity .3s';
      setTimeout(function () { t.remove(); }, 350);
    }, duration);
  };

  /* ── Cart badge updater ─────────────────────────────────── */
  function updateCartBadges(count) {
    ['cart-badge-desktop', 'cart-badge-mobile'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.textContent = count > 0 ? count : '';
    });
  }

  window.dlshopRefreshCartCount = function () {
    frappe.call({ method: 'dlshop.api.cart.get_cart_count_api', callback: function (r) {
      if (r.message) updateCartBadges(r.message.count || 0);
    }});
  };

  /* ── Add-to-cart (shared across pages) ─────────────────── */
  window.dlshopAddToCart = function (itemCode, qty, btn) {
    var orig = null;
    if (btn) {
      /* Save BEFORE overwriting — works whether or not data-orig-html was pre-set */
      orig = btn.dataset.origHtml || btn.innerHTML;
      btn.dataset.origHtml = orig;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }
    frappe.call({
      method: 'dlshop.api.cart.add_to_cart',
      args: { item_code: itemCode, qty: qty || 1 },
      callback: function (r) {
        if (btn) { btn.disabled = false; btn.innerHTML = orig || btn.dataset.origHtml || ''; }
        if (r.message && r.message.success) {
          updateCartBadges(r.message.count || 0);
          var lang = window.dlshop && window.dlshop.lang;
          dlshopToast(lang === 'ar' ? 'تمت الإضافة إلى السلة ✓' : 'Added to cart ✓', 'success');
        } else {
          dlshopToast((r.message && r.message.message) || (window.dlshop && window.dlshop.lang === 'ar' ? 'حدث خطأ' : 'Error'), 'error');
        }
      },
      error: function () {
        if (btn) { btn.disabled = false; btn.innerHTML = orig || btn.dataset.origHtml || ''; }
        dlshopToast(window.dlshop && window.dlshop.lang === 'ar' ? 'حدث خطأ' : 'Error', 'error');
      }
    });
  };

  /* ── Wishlist toggle ────────────────────────────────────── */
  function handleWishlistClick(btn) {
    var route = btn.dataset.route;
    if (!route) return;
    if (window.dlshop && window.frappe && frappe.session && frappe.session.user === 'Guest') {
      var lang = window.dlshop.lang;
      dlshopToast(lang === 'ar' ? 'سجّل دخولك لإضافة للمفضلة' : 'Login to use wishlist', 'info');
      return;
    }
    frappe.call({
      method: 'dlshop.api.account.toggle_wishlist',
      args: { item_route: route },
      callback: function (r) {
        if (!r.message) return;
        var lang = window.dlshop && window.dlshop.lang;
        var icon = btn.querySelector('.fa');
        if (r.message.wishlisted) {
          btn.classList.add('active');
          if (icon) { icon.style.color = 'var(--dl-accent)'; icon.style.fontWeight = '900'; }
          dlshopToast(lang === 'ar' ? 'تمت الإضافة للمفضلة' : 'Added to wishlist', 'success');
        } else {
          btn.classList.remove('active');
          if (icon) { icon.style.color = ''; icon.style.fontWeight = ''; }
          dlshopToast(lang === 'ar' ? 'تمت الإزالة من المفضلة' : 'Removed from wishlist', 'info');
        }
      }
    });
  }

  /* ── Delegate add-to-cart / wishlist clicks ─────────────── */
  document.addEventListener('click', function (e) {
    var addBtn = e.target.closest('.dl-add-to-cart-btn');
    if (addBtn) {
      e.preventDefault();
      if (!addBtn.dataset.origHtml) addBtn.dataset.origHtml = addBtn.innerHTML;
      dlshopAddToCart(addBtn.dataset.itemCode, 1, addBtn);
      return;
    }
    var wlBtn = e.target.closest('.dl-wishlist-btn');
    if (wlBtn) { e.preventDefault(); handleWishlistClick(wlBtn); return; }
  });

  /* ── Live search ────────────────────────────────────────── */
  var searchInput = document.querySelector('.dl-search-input');
  var suggestions = document.getElementById('dl-search-suggestions');
  var searchTimer;
  if (searchInput && suggestions) {
    searchInput.addEventListener('input', function () {
      clearTimeout(searchTimer);
      var q = this.value.trim();
      if (q.length < 2) { suggestions.classList.add('d-none'); suggestions.innerHTML = ''; return; }
      searchTimer = setTimeout(function () {
        frappe.call({
          method: 'dlshop.api.shop.search_products',
          args: { q: q.slice(0, 100), limit: 8 }, /* cap at 100 chars */
          callback: function (r) {
            var items = r.message || [];
            var lang = window.dlshop && window.dlshop.lang;
            suggestions.innerHTML = '';
            if (!items.length) {
              var noRes = document.createElement('a');
              noRes.className = 'text-muted ps-3 py-2 d-block';
              noRes.textContent = lang === 'ar' ? 'لا توجد نتائج' : 'No results';
              suggestions.appendChild(noRes);
            } else {
              var frag = document.createDocumentFragment();
              items.forEach(function (i) {
                var a = document.createElement('a');
                a.href = '/shop/' + esc(lang) + '/product/' + esc(i.route);
                var src = safeSrc(i.featured_image);
                if (src) {
                  var img = document.createElement('img');
                  img.src = src;
                  img.alt = '';
                  a.appendChild(img);
                } else {
                  var ph = document.createElement('div');
                  ph.style.cssText = 'width:40px;height:40px;background:#f0f0f0;border-radius:6px;flex-shrink:0';
                  a.appendChild(ph);
                }
                var sp = document.createElement('span');
                sp.textContent = i.name_display; /* textContent — never eval as HTML */
                a.appendChild(sp);
                frag.appendChild(a);
              });
              suggestions.appendChild(frag);
            }
            suggestions.classList.remove('d-none');
          }
        });
      }, 280);
    });
    document.addEventListener('click', function (e) {
      if (!suggestions.contains(e.target) && e.target !== searchInput) {
        suggestions.classList.add('d-none');
      }
    });
  }

  /* ── Newsletter form ────────────────────────────────────── */
  var nlForm = document.getElementById('dl-newsletter-form');
  if (nlForm) {
    nlForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = this.querySelector('[name=email]').value.trim();
      if (!email) return;
      var lang = window.dlshop && window.dlshop.lang;
      frappe.call({
        method: 'dlshop.api.account.subscribe_newsletter',
        args: { email: email, lang: lang || 'en' },
        callback: function (r) {
          if (r.message && r.message.success) {
            dlshopToast(lang === 'ar' ? 'شكراً للاشتراك!' : 'Subscribed!', 'success');
          } else if (r.message && r.message.message) {
            dlshopToast(r.message.message, 'error');
          }
        }
      });
      nlForm.reset();
    });
  }

  /* ── Logout ─────────────────────────────────────────────── */
  var logoutLink = document.getElementById('dl-logout');
  if (logoutLink) {
    logoutLink.addEventListener('click', function (e) {
      e.preventDefault();
      frappe.call({ method: 'logout', callback: function () { window.location.href = '/'; } });
    });
  }

  /* ── Intercept Frappe's Bootstrap-4 error dialog ───────── */
  /* Replace frappe.msgprint with our toast so the broken modal never appears */
  document.addEventListener('DOMContentLoaded', function () {
    window.dlshopRefreshCartCount();

    if (window.frappe && frappe.msgprint) {
      var _orig = frappe.msgprint.bind(frappe);
      frappe.msgprint = function (opts, title) {
        /* frappe.msgprint can be called with a string or an options object */
        var msg = (opts && typeof opts === 'object') ? (opts.message || opts.msg || '') : (opts || '');
        var indicator = (opts && opts.indicator) || '';
        var type = (indicator === 'green') ? 'success' : (indicator === 'red' || !indicator) ? 'error' : 'info';
        if (msg) {
          /* Strip basic HTML tags for toast display */
          var plain = String(msg).replace(/<[^>]+>/g, ' ').trim();
          dlshopToast(plain, type);
        }
      };
    }
  });

})();
