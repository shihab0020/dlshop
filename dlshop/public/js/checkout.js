/* =============================================================
   checkout.js — Multi-step checkout: fulfillment → shipping → payment → confirm
   ============================================================= */
(function () {
  'use strict';
  var cfg = window.dlCheckoutConfig || {};
  var lang = cfg.lang || 'en';
  var rtl = cfg.rtl || false;
  var currency = cfg.currency || 'SAR';
  var isGuest = cfg.isGuest || false;
  var step = 1;
  var checkoutData = {};
  var selections = {
    billing_address: null,
    shipping_address: null,
    shipping_rule: null,
    payment_method: 'cod',
    fulfillment_type: 'delivery',
    pickup_location: null,
    pickup_location_name: null,
  };

  function fmt(v) {
    return (lang === 'ar' ? 'ر.س ' : 'SAR ') + parseFloat(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2 });
  }

  /* ── Step indicator ─────────────────────────────────────── */
  function setStep(n) {
    step = n;
    document.querySelectorAll('.dl-step').forEach(function (s) {
      var sn = parseInt(s.dataset.step);
      s.classList.toggle('active', sn === n);
      s.classList.toggle('done', sn < n);
    });
    var main = document.getElementById('dl-checkout-main');
    var tpl = document.getElementById('tpl-step-' + n);
    if (tpl) main.innerHTML = tpl.innerHTML;
    bindStep(n);
  }

  /* ── Order summary ──────────────────────────────────────── */
  function renderSummary(cart) {
    var el = document.getElementById('dl-order-items');
    if (!el || !cart) return;
    el.innerHTML = (cart.items || []).map(function (i) {
      return '<div class="d-flex gap-2 mb-2 align-items-center">' +
        (i.image ? '<img src="' + i.image + '" width="48" height="48" class="rounded object-fit-cover" />' : '<div class="bg-light rounded" style="width:48px;height:48px;flex-shrink:0;"></div>') +
        '<div class="flex-grow-1 small"><div>' + i.item_name + '</div><div class="text-muted">\xd7' + i.qty + '</div></div>' +
        '<div class="small fw-semibold">' + fmt(i.amount) + '</div></div>';
    }).join('');
    var totals = document.getElementById('dl-order-totals');
    var html = '<div class="d-flex justify-content-between small mb-1"><span class="text-muted">' + (lang === 'ar' ? 'المجموع الفرعي' : 'Subtotal') + '</span><span>' + fmt(cart.subtotal) + '</span></div>';
    if (cart.coupon_discount > 0) html += '<div class="d-flex justify-content-between small mb-1 text-success"><span>' + (lang === 'ar' ? 'خصم' : 'Discount') + '</span><span>- ' + fmt(cart.coupon_discount) + '</span></div>';
    if (cart.shipping_charge > 0) html += '<div class="d-flex justify-content-between small mb-1"><span class="text-muted">' + (lang === 'ar' ? 'شحن' : 'Shipping') + '</span><span>' + fmt(cart.shipping_charge) + '</span></div>';
    totals.innerHTML = html;
    document.getElementById('dl-order-grand-total').textContent = fmt(cart.grand_total);
  }

  /* ── Pickup location cards ──────────────────────────────── */
  function renderPickupLocations(locations) {
    var el = document.getElementById('dl-pickup-locations');
    if (!el) return;
    if (!locations || !locations.length) {
      el.innerHTML = '<div class="col-12"><p class="text-muted">' + (lang === 'ar' ? 'لا توجد مواقع استلام متاحة حالياً' : 'No pickup locations available') + '</p></div>';
      return;
    }
    el.innerHTML = locations.map(function (loc) {
      var name = lang === 'ar' ? (loc.location_name_ar || loc.location_name_en) : loc.location_name_en;
      var addr = lang === 'ar' ? (loc.address_ar || loc.address_en) : (loc.address_en || '');
      var hours = lang === 'ar' ? (loc.working_hours_ar || loc.working_hours_en) : (loc.working_hours_en || '');
      var selected = selections.pickup_location === loc.name;
      return '<div class="col-12 col-md-6">' +
        '<div class="dl-pickup-card card h-100 cursor-pointer ' + (selected ? 'border-primary border-2' : 'border') + '" data-loc="' + loc.name + '" data-name-en="' + loc.location_name_en + '" data-name-ar="' + (loc.location_name_ar || loc.location_name_en) + '" style="cursor:pointer;">' +
        (loc.photo ? '<img src="' + loc.photo + '" class="card-img-top" style="height:150px;object-fit:cover;" alt="' + name + '" />' : '') +
        '<div class="card-body">' +
        '<h6 class="fw-bold mb-2">' + (selected ? '<i class="fa fa-check-circle text-primary me-1"></i>' : '') + name + '</h6>' +
        (addr ? '<p class="small text-muted mb-1"><i class="fa fa-map-marker-alt me-1"></i>' + addr + '</p>' : '') +
        (loc.phone ? '<p class="small mb-1"><i class="fa fa-phone me-1"></i><a href="tel:' + loc.phone + '" onclick="event.stopPropagation()">' + loc.phone + '</a></p>' : '') +
        (hours ? '<p class="small text-muted mb-2"><i class="fa fa-clock me-1"></i>' + hours + '</p>' : '') +
        (loc.map_link ? '<a href="' + loc.map_link + '" target="_blank" class="btn btn-outline-secondary btn-sm" onclick="event.stopPropagation()"><i class="fa fa-map-marked-alt me-1"></i>' + (lang === 'ar' ? 'عرض الخريطة' : 'View Map') + '</a>' : '') +
        '</div></div></div>';
    }).join('');

    el.querySelectorAll('.dl-pickup-card').forEach(function (card) {
      card.addEventListener('click', function () {
        var locName = this.dataset.loc;
        selections.pickup_location = locName;
        selections.pickup_location_name = lang === 'ar' ? this.dataset.nameAr : this.dataset.nameEn;
        el.querySelectorAll('.dl-pickup-card').forEach(function (c) {
          c.classList.remove('border-primary', 'border-2');
          c.classList.add('border');
        });
        this.classList.add('border-primary', 'border-2');
        this.classList.remove('border');
      });
    });
  }

  /* ── Fulfillment toggle ─────────────────────────────────── */
  function bindFulfillmentToggle() {
    var pickupCol = document.getElementById('dl-pickup-tab-col');
    if (pickupCol && checkoutData.pickup_enabled) {
      pickupCol.style.display = '';
    }

    document.querySelectorAll('.dl-fulfill-option').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var type = this.dataset.type;
        selections.fulfillment_type = type;
        document.querySelectorAll('.dl-fulfill-option').forEach(function (b) {
          b.classList.remove('border-primary', 'border-2', 'selected');
          b.classList.add('border');
          b.querySelector('i') && b.querySelector('i').classList.replace('text-primary' , 'text-muted') && null;
          b.querySelector('i') && b.querySelector('i').classList.add('text-muted');
          b.querySelector('i') && b.querySelector('i').classList.remove('text-primary');
        });
        this.classList.add('border-primary', 'border-2', 'selected');
        this.classList.remove('border');
        this.querySelector('i') && this.querySelector('i').classList.add('text-primary');
        this.querySelector('i') && this.querySelector('i').classList.remove('text-muted');

        var deliverySection = document.getElementById('dl-delivery-section');
        var pickupSection = document.getElementById('dl-pickup-section');
        if (type === 'pickup') {
          if (deliverySection) deliverySection.style.display = 'none';
          if (pickupSection) {
            pickupSection.style.display = '';
            renderPickupLocations(checkoutData.pickup_locations || []);
          }
        } else {
          if (deliverySection) deliverySection.style.display = '';
          if (pickupSection) pickupSection.style.display = 'none';
        }
      });
    });
  }

  /* ── Bind step events ───────────────────────────────────── */
  function bindStep(n) {
    if (n === 1) {
      /* Show guest fields if guest */
      var guestFields = document.getElementById('dl-guest-fields');
      if (guestFields && isGuest) guestFields.style.display = '';

      /* Restore fulfillment UI state */
      if (selections.fulfillment_type === 'pickup') {
        var deliverySection = document.getElementById('dl-delivery-section');
        var pickupSection = document.getElementById('dl-pickup-section');
        if (deliverySection) deliverySection.style.display = 'none';
        if (pickupSection) pickupSection.style.display = '';
      }

      bindFulfillmentToggle();

      /* Render saved addresses for delivery */
      var savedEl = document.getElementById('dl-saved-addresses');
      if (savedEl && checkoutData.addresses && checkoutData.addresses.length) {
        savedEl.innerHTML = '<p class="small text-muted mb-2">' + (lang === 'ar' ? 'العناوين المحفوظة:' : 'Saved addresses:') + '</p>' +
          checkoutData.addresses.map(function (a) {
            return '<div class="dl-radio-card dl-radio-cards mb-2 ' + (selections.shipping_address === a.name ? 'selected' : '') + '" data-addr="' + a.name + '">' +
              '<strong>' + a.address_title + '</strong><p class="mb-0 small text-muted">' + [a.address_line1, a.city, a.country].filter(Boolean).join(', ') + '</p></div>';
          }).join('') +
          '<hr/><p class="small">' + (lang === 'ar' ? 'أو أدخل عنوانًا جديدًا:' : 'Or enter a new address:') + '</p>';

        savedEl.querySelectorAll('.dl-radio-card').forEach(function (card) {
          card.addEventListener('click', function () {
            selections.shipping_address = this.dataset.addr;
            selections.billing_address = this.dataset.addr;
            savedEl.querySelectorAll('.dl-radio-card').forEach(function (c) { c.classList.remove('selected'); });
            this.classList.add('selected');
          });
        });
      }

      /* Re-render pickup locations if returning to step 1 in pickup mode */
      if (selections.fulfillment_type === 'pickup') {
        renderPickupLocations(checkoutData.pickup_locations || []);
      }

      var nextBtn = document.getElementById('dl-next-step-1');
      if (nextBtn) {
        nextBtn.addEventListener('click', function () {
          if (selections.fulfillment_type === 'pickup') {
            if (!selections.pickup_location) {
              dlshopToast(lang === 'ar' ? 'يرجى اختيار موقع الاستلام' : 'Please select a pickup location', 'error');
              return;
            }
            setStep(3);
          } else {
            /* Delivery: validate address */
            var l1 = document.getElementById('co-addr1');
            if (l1 && l1.value.trim()) {
              frappe.call({
                method: 'dlshop.api.checkout.save_address',
                args: {
                  address_title: lang === 'ar' ? 'عنوان جديد' : 'New Address',
                  address_line1: l1.value,
                  address_line2: document.getElementById('co-addr2').value,
                  city: document.getElementById('co-city').value,
                  state: document.getElementById('co-state').value,
                  country: document.getElementById('co-country').value,
                  phone: document.getElementById('co-phone').value,
                },
                callback: function (r) {
                  if (r.message && r.message.success) {
                    selections.shipping_address = r.message.address_name;
                    selections.billing_address = r.message.address_name;
                    setStep(2);
                  }
                }
              });
            } else if (selections.shipping_address) {
              setStep(2);
            } else {
              dlshopToast(lang === 'ar' ? 'يرجى إدخال عنوان التوصيل' : 'Please enter a delivery address', 'error');
            }
          }
        });
      }
    }

    if (n === 2) {
      var shippingEl = document.getElementById('dl-shipping-options');
      if (shippingEl) {
        var rules = checkoutData.shipping_rules || [];
        if (!rules.length) {
          shippingEl.innerHTML = '<p class="text-muted small">' + (lang === 'ar' ? 'الشحن مجاني' : 'Free shipping') + '</p>';
        } else {
          shippingEl.innerHTML = rules.map(function (r) {
            return '<label class="dl-radio-card d-flex gap-3 align-items-center cursor-pointer"><input type="radio" name="shipping_rule" value="' + r.name + '" class="mt-1" /><div><div class="fw-semibold">' + r.label + '</div></div></label>';
          }).join('');
          var firstRadio = shippingEl.querySelector('input[type=radio]');
          if (firstRadio) firstRadio.checked = true;
          shippingEl.querySelectorAll('input[type=radio]').forEach(function (r) {
            r.addEventListener('change', function () {
              selections.shipping_rule = this.value;
              frappe.call({
                method: 'dlshop.api.checkout.apply_shipping_rule',
                args: { shipping_rule_name: this.value },
                callback: function (res) {
                  if (res.message) {
                    checkoutData.cart.shipping_charge = res.message.shipping_charge;
                    checkoutData.cart.grand_total = res.message.grand_total;
                    renderSummary(checkoutData.cart);
                  }
                }
              });
            });
          });
        }
      }
      document.getElementById('dl-next-step-2').addEventListener('click', function () { setStep(3); });
      document.getElementById('dl-back-step-2').addEventListener('click', function () { setStep(1); });
    }

    if (n === 3) {
      var pmEl = document.getElementById('dl-payment-options');
      var methods = checkoutData.payment_methods || [];
      if (!methods.length) methods = [{ id: 'cod', label_en: 'Cash on Delivery', label_ar: 'الدفع عند الاستلام', charge: 0 }];
      pmEl.innerHTML = methods.map(function (m, idx) {
        var lbl = lang === 'ar' ? m.label_ar : m.label_en;
        var desc = lang === 'ar' ? m.description_ar : m.description_en;
        var iconHtml = m.icon === 'tabby'
          ? '<img src="https://cdn.tabby.ai/assets/tabby-badge.png" alt="Tabby" style="height:22px;vertical-align:middle;" class="me-2" />'
          : '<i class="fa fa-money-bill me-2"></i>';
        var isFirst = idx === 0;
        return '<label class="dl-radio-card d-flex gap-3 align-items-center cursor-pointer">' +
          '<input type="radio" name="payment_method" value="' + m.id + '" class="mt-1" ' + (isFirst ? 'checked' : '') + ' />' +
          '<div><div class="fw-semibold">' + iconHtml + lbl + '</div>' +
          (desc ? '<div class="small text-muted">' + desc + '</div>' : '') +
          (m.charge > 0 ? '<div class="small text-warning">+' + fmt(m.charge) + '</div>' : '') +
          '</div></label>';
      }).join('');
      pmEl.querySelectorAll('input[type=radio]').forEach(function (r) {
        r.addEventListener('change', function () { selections.payment_method = this.value; });
      });

      /* Back goes to step 2 for delivery, step 1 for pickup */
      document.getElementById('dl-back-step-3').addEventListener('click', function () {
        setStep(selections.fulfillment_type === 'pickup' ? 1 : 2);
      });
      document.getElementById('dl-place-order-btn').addEventListener('click', placeOrder);
    }
  }

  /* ── Place order ────────────────────────────────────────── */
  function placeOrder() {
    var btn = document.getElementById('dl-place-order-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>' + (lang === 'ar' ? 'جاري التأكيد...' : 'Placing order...');
    var args = {
      billing_address: selections.billing_address,
      shipping_address: selections.shipping_address,
      payment_method: selections.payment_method,
      notes: (document.getElementById('co-notes') || {}).value || '',
      fulfillment_type: selections.fulfillment_type,
      pickup_location: selections.pickup_location,
    };
    if (isGuest) {
      args.guest_name = (document.getElementById('co-guest-name') || {}).value;
      args.guest_email = (document.getElementById('co-guest-email') || {}).value;
      args.guest_phone = (document.getElementById('co-guest-phone') || {}).value;
    }
    frappe.call({
      method: 'dlshop.api.checkout.place_order',
      args: args,
      callback: function (r) {
        if (r.message && r.message.success) {
          window.dlshopRefreshCartCount && window.dlshopRefreshCartCount();

          /* Tabby: redirect to Tabby checkout page */
          if (r.message.payment_method === 'tabby' && r.message.redirect_url) {
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>' +
              (lang === 'ar' ? 'جاري التوجيه لتابي...' : 'Redirecting to Tabby...');
            window.location.href = r.message.redirect_url;
            return;
          }

          /* Other methods: show inline success step */
          setStep(4);
          document.getElementById('dl-order-id').textContent = r.message.order_id;
          var fulfillmentEl = document.getElementById('dl-success-fulfillment');
          if (fulfillmentEl) {
            if (selections.fulfillment_type === 'pickup' && selections.pickup_location_name) {
              fulfillmentEl.innerHTML = '<i class="fa fa-store me-1 text-primary"></i>' +
                (lang === 'ar' ? 'الاستلام من: ' : 'Pickup from: ') +
                '<strong>' + selections.pickup_location_name + '</strong>';
            } else {
              fulfillmentEl.innerHTML = '<i class="fa fa-truck me-1 text-primary"></i>' +
                (lang === 'ar' ? 'سيتم التوصيل إلى عنوانك' : 'Will be delivered to your address');
            }
          }
        } else {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa fa-check-circle me-2"></i>' + (lang === 'ar' ? 'تأكيد الطلب' : 'Place Order');
          dlshopToast((r.message && r.message.message) || (lang === 'ar' ? 'حدث خطأ' : 'Error placing order'), 'error');
        }
      },
      error: function () {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa fa-check-circle me-2"></i>' + (lang === 'ar' ? 'تأكيد الطلب' : 'Place Order');
        dlshopToast('Error', 'error');
      }
    });
  }

  /* ── Init ───────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    frappe.call({
      method: 'dlshop.api.checkout.get_checkout_data',
      callback: function (r) {
        if (!r.message || r.message.empty) {
          window.location.href = '/shop/' + lang;
          return;
        }
        checkoutData = r.message;
        renderSummary(checkoutData.cart);
        setStep(1);
      }
    });
  });
})();
