// Patch ControlAttach once so every Attach/Attach Image button always
// waits for file_uploader.bundle.js before calling the original handler.
// The guard on the prototype prevents re-patching on every form refresh.
(function () {
    function patchAttach() {
        if (frappe.ui.form.ControlAttach.prototype.__dlPatchedAttach) return;
        frappe.ui.form.ControlAttach.prototype.__dlPatchedAttach = true;

        var _orig = frappe.ui.form.ControlAttach.prototype.on_attach_click;
        frappe.ui.form.ControlAttach.prototype.on_attach_click = function () {
            var ctrl = this;
            frappe.require('file_uploader.bundle.js', function () {
                _orig.call(ctrl);
            });
        };
    }

    if (frappe.ui && frappe.ui.form && frappe.ui.form.ControlAttach) {
        patchAttach();
    } else {
        frappe.after_ajax(patchAttach);
    }
})();

frappe.ui.form.on('DL Shop Item', {});
