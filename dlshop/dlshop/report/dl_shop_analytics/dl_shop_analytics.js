frappe.query_reports["DL Shop Analytics"] = {
	filters: [
		{
			fieldname: "report_type",
			label: __("Report Type"),
			fieldtype: "Select",
			options: [
				"Product Sales",
				"Customer Analysis",
				"Brand Sales",
				"Category Sales",
				"Order Trends",
				"Product Views",
				"Wishlist",
							"Reviews",
			"Visitor Countries",
			"Order Countries",
			].join("\n"),
			default: "Product Sales",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "chart_type",
			label: __("Chart Type"),
			fieldtype: "Select",
			options: "bar\nline\npie\npercentage",
			default: "bar",
		},

		// ── Order status filters (hidden for Views / Wishlist / Reviews) ────
		{
			fieldname: "order_status",
			label: __("Order Status"),
			fieldtype: "Select",
			options: "\nActive\nCompleted\nTo Deliver and Bill\nTo Bill\nTo Deliver\nOn Hold\nCancelled",
			depends_on: 'eval:!["Product Views","Wishlist","Reviews"].includes(doc.report_type)',
		},
		{
			fieldname: "approval_status",
			label: __("Approval Status"),
			fieldtype: "Select",
			options: "\nApproved\nPending Approval\nRejected\nNo Approval Record",
			depends_on: 'eval:!["Product Views","Wishlist","Reviews"].includes(doc.report_type)',
		},
		{
			fieldname: "delivery_filter",
			label: __("Delivery"),
			fieldtype: "Select",
			options: "\nFully Delivered\nPartly Delivered\nNot Delivered",
			depends_on: 'eval:!["Product Views","Wishlist","Reviews"].includes(doc.report_type)',
		},
		{
			fieldname: "billing_filter",
			label: __("Billing / Invoice"),
			fieldtype: "Select",
			options: "\nFully Billed (Paid)\nPartly Billed\nNot Billed (Unpaid)",
			depends_on: 'eval:!["Product Views","Wishlist","Reviews"].includes(doc.report_type)',
		},

		// ── Dimension filters ───────────────────────────────────────────────
		{
			fieldname: "range",
			label: __("Trend Range"),
			fieldtype: "Select",
			options: "Weekly\nMonthly\nQuarterly",
			default: "Monthly",
			depends_on: 'eval:doc.report_type=="Order Trends"',
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
			depends_on: 'eval:["Product Sales","Brand Sales","Product Views"].includes(doc.report_type)',
		},
		{
			fieldname: "item_group",
			label: __("Category"),
			fieldtype: "Link",
			options: "Item Group",
			depends_on: 'eval:["Product Sales","Category Sales","Product Views"].includes(doc.report_type)',
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "avg_rating" && data && data.avg_rating) {
			const n = Math.round(data.avg_rating);
			value = "★".repeat(n) + "☆".repeat(5 - n) + ` ${data.avg_rating}`;
		}
		if (column.fieldname === "revenue_share" && data) {
			const pct = data.revenue_share || 0;
			value =
				`${pct}% <div style="background:#e9ecef;border-radius:3px;height:8px;margin-top:3px">` +
				`<div style="background:#5e64ff;width:${Math.min(pct, 100)}%;height:100%;border-radius:3px"></div></div>`;
		}
		return value;
	},
};
