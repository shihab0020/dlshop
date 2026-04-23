import frappe
from dlshop.utils import get_current_lang


def get_context(context):
    lang = get_current_lang()
    frappe.local.lang = lang
    context.lang = lang
    context.no_cache = 1

    status     = frappe.form_dict.get("status", "")      # success / failure / cancel
    payment_id = frappe.form_dict.get("payment_id", "")  # Tabby appends this

    context.status    = status
    context.success   = status == "success"
    context.cancelled = status == "cancel"
    context.order_id  = None
    context.shop_url   = f"/shop/{lang}"
    context.orders_url = f"/account/orders/{lang}"

    if not payment_id:
        return

    log_name = frappe.db.get_value(
        "DL Tabby Log", {"tabby_payment_id": payment_id}, "name"
    )
    if not log_name:
        return

    log = frappe.get_doc("DL Tabby Log", log_name)
    context.order_id = log.sales_order

    if status == "success":
        _sync_and_capture(log)


def _sync_and_capture(log):
    """Fetch current payment status from Tabby; capture if AUTHORIZED."""
    import requests as _requests

    try:
        ts = frappe.get_single("DL Tabby Settings")
        secret = ts.get_password("key_secret")

        resp = _requests.get(
            f"https://api.tabby.ai/api/v2/payments/{log.tabby_payment_id}",
            headers={"Authorization": f"Bearer {secret}"},
            timeout=10,
        )
        resp.raise_for_status()
        data   = resp.json()
        status = (data.get("status") or "").upper()

        frappe.db.set_value("DL Tabby Log", log.name, "status", status)

        if status == "AUTHORIZED":
            cap = _requests.post(
                f"https://api.tabby.ai/api/v2/payments/{log.tabby_payment_id}/captures",
                json={"amount": str(log.amount)},
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            cap.raise_for_status()
            frappe.db.set_value("DL Tabby Log", log.name, "status", "CLOSED")

        frappe.db.commit()

    except Exception:
        frappe.log_error(frappe.get_traceback(), "DL Tabby Capture Error")
