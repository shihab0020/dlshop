/* =============================================================
   cart.js — Cart page: render items, update qty, coupon
   ============================================================= */
(function () {
  'use strict';
  var lang = window.dlshop && window.dlshop.lang || 'en';
  var currency = window.dlshop && window.dlshop.currency || 'SAR';
  var isSAR = !currency || currency === 'SAR';
  var sym = isSAR ? '⃁' : currency;
  function fmt(v) { return sym + ' ' + parseFloat(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2 }); }

  function render(cart) {
    var el = document.getElementById('dl-cart-content');
    if (!cart || !cart.items || !cart.items.length) {
      el.innerHTML = document.getElementById('tpl-cart-empty').innerHTML;
      return;
    }
    el.innerHTML = document.getElementById('tpl-cart-has-items').innerHTML;

    /* rows */
    var tbody = document.getElementById('dl-cart-rows');
    tbody.innerHTML = cart.items.map(function (i) {
      var name = lang === 'ar' ? (i.name_ar || i.item_name) : (i.name_en || i.item_name);
      return '<tr id="cr-' + i.item_code + '">' +
        '<td><div class="d-flex align-items-center gap-3">' +
          (i.image ? '<img src="' + i.image + '" class="dl-cart-item-img rounded" />' : '<div class="dl-cart-item-img rounded bg-light"></div>') +
          '<div><a href="/shop/' + lang + '/product/' + (i.route || '') + '" class="text-decoration-none fw-semibold">' + name + '</a><br/><small class="text-muted">' + i.item_code + '</small></div>' +
        '</div></td>' +
        '<td class="text-center" style="min-width:140px;"><div class="input-group input-group-sm" style="width:110px;margin:auto;">' +
          '<button class="btn btn-outline-secondary dl-qty-dec-row" data-code="' + i.item_code + '">-</button>' +
          '<input type="number" value="' + i.qty + '" min="1" max="99" class="form-control text-center dl-qty-row" data-code="' + i.item_code + '" style="max-width:46px;" />' +
          '<button class="btn btn-outline-secondary dl-qty-inc-row" data-code="' + i.item_code + '">+</button>' +
        '</div></td>' +
        '<td class="text-end">' + fmt(i.rate) + '</td>' +
        '<td class="text-end fw-semibold">' + fmt(i.amount) + '</td>' +
        '<td class="text-end"><button class="btn btn-sm btn-link text-danger dl-remove-item" data-code="' + i.item_code + '" title="Remove"><i class="fa fa-trash"></i></button></td>' +
        '</tr>';
    }).join('');

    /* totals */
    var summaryEl = el.querySelector('.dl-summary-rows');
    var rows = '<div class="d-flex justify-content-between mb-2"><span class="text-muted">' + (lang === 'ar' ? 'المجموع الفرعي' : 'Subtotal') + '</span><span>' + fmt(cart.subtotal) + '</span></div>';
    if (cart.coupon_discount && cart.coupon_discount > 0) {
      rows += '<div class="d-flex justify-content-between mb-2 text-success"><span>' + (lang === 'ar' ? 'خصم الكوبون' : 'Coupon Discount') + '</span><span>- ' + fmt(cart.coupon_discount) + '</span></div>';
    }
    if (cart.shipping_charge && cart.shipping_charge > 0) {
      rows += '<div class="d-flex justify-content-between mb-2"><span class="text-muted">' + (lang === 'ar' ? 'رسوم الشحن' : 'Shipping') + '</span><span>' + fmt(cart.shipping_charge) + '</span></div>';
    }
    summaryEl.innerHTML = rows;
    el.querySelector('#dl-cart-grand-total').textContent = fmt(cart.grand_total);

    /* coupon state */
    if (cart.coupon_code) {
      el.querySelector('#dl-coupon-form').classList.add('d-none');
      var applied = el.querySelector('#dl-coupon-applied');
      applied.classList.remove('d-none');
      el.querySelector('#dl-coupon-label').textContent = cart.coupon_code + ' — -' + fmt(cart.coupon_discount);
    }

    bindEvents(cart);
  }

  function bindEvents() {
    /* qty dec */
    document.querySelectorAll('.dl-qty-dec-row').forEach(function (btn) {
      btn.addEventListener('click', function () { var inp = document.querySelector('.dl-qty-row[data-code="' + this.dataset.code + '"]'); var nv = Math.max(1, parseInt(inp.value) - 1); inp.value = nv; updateQty(this.dataset.code, nv); });
    });
    /* qty inc */
    document.querySelectorAll('.dl-qty-inc-row').forEach(function (btn) {
      btn.addEventListener('click', function () { var inp = document.querySelector('.dl-qty-row[data-code="' + this.dataset.code + '"]'); var nv = Math.min(99, parseInt(inp.value) + 1); inp.value = nv; updateQty(this.dataset.code, nv); });
    });
    /* qty input */
    document.querySelectorAll('.dl-qty-row').forEach(function (inp) {
      var t; inp.addEventListener('input', function () { clearTimeout(t); var code = this.dataset.code; var v = parseInt(this.value); t = setTimeout(function () { if (v >= 1) updateQty(code, v); }, 600); });
    });
    /* remove */
    document.querySelectorAll('.dl-remove-item').forEach(function (btn) {
      btn.addEventListener('click', function () { removeItem(this.dataset.code); });
    });
    /* coupon apply */
    var applyBtn = document.getElementById('dl-apply-coupon');
    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        var code = (document.getElementById('dl-coupon-input').value || '').trim();
        if (!code) return;
        frappe.call({ method: 'dlshop.api.cart.apply_coupon', args: { coupon_code: code },
          callback: function (r) {
            var msg = document.getElementById('dl-coupon-msg');
            if (r.message && r.message.success) { render(r.message.cart); dlshopToast(lang === 'ar' ? 'تم تطبيق الكوبون' : 'Coupon applied!', 'success'); }
            else { msg.textContent = (r.message && r.message.message) || (lang === 'ar' ? 'كوبون غير صالح' : 'Invalid coupon'); msg.className = 'small mt-1 text-danger'; }
          }
        });
      });
    }
    /* coupon remove */
    var removeBtn = document.getElementById('dl-remove-coupon');
    if (removeBtn) {
      removeBtn.addEventListener('click', function () {
        frappe.call({ method: 'dlshop.api.cart.remove_coupon', callback: function (r) { if (r.message) render(r.message.cart); } });
      });
    }
  }

  function updateQty(itemCode, qty) {
    frappe.call({ method: 'dlshop.api.cart.update_qty', args: { item_code: itemCode, qty: qty },
      callback: function (r) { if (r.message && r.message.cart) { render(r.message.cart); window.dlshopRefreshCartCount && window.dlshopRefreshCartCount(); } }
    });
  }

  function removeItem(itemCode) {
    frappe.call({ method: 'dlshop.api.cart.remove_item', args: { item_code: itemCode },
      callback: function (r) { if (r.message && r.message.cart) { render(r.message.cart); window.dlshopRefreshCartCount && window.dlshopRefreshCartCount(); } }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    frappe.call({ method: 'dlshop.api.cart.get_cart',
      callback: function (r) { render(r.message || {}); }
    });
  });
})();
