# Quotation V2 — Row UX (visual redesign only)

Branch: `feature/quotation-v2-row-ux-20261116`
Base: `feature/quotation-pricing-v2-20261115`

## Scope

The complete quotation header, document form, workflow, routes and backend
pricing services remain unchanged. This phase replaces the row presentation
in `micmod_base/templates/micmod-base/quotation/v2/item_full.html`.
When the UI is approved, pricing behavior can be addressed in a **separate**
follow-up phase.

## Layout

- **Collapsed card:** item number, SKU, title, fulfillment/inquiry status,
  quantity, unit price and total
- **Primary workspace:** product selection, description, quantity, stock,
  target price, packaging, customer SKU/name, price method, unit price,
  per-unit discount, existing v2 reference controls and financial breakdown
- **Inquiry & available prices:** local/foreign flags, selected inquiry,
  permission-aware quote history and refresh operation
- **Inventory & alternatives:** prior fulfillment lines, stock by warehouse,
  quantity already in orders, alternate SKU, recent sales
- **Supply & delivery:** supply date/status, estimated delivery, item in
  China, assigned trade personnel, progress and delay details, with access
  controls for trade-only fields
- **Notes & audit:** internal/sales/inquiry descriptions, per-row comments,
  inquiry file and change log
- **Row footer:** mark for delete, move/reorder, change history and inquiry file

## Legacy integration contract

Do not rename the hooks used by `quotation1.js` and `formset.js`:
`item`, `question-btn`, `row-counter`, `counter`, `answer`,
`goods_code`, `goods_code_alt`, `selected_price_code`,
`id_price_method_container`, `id_display_price_container`,
`customer-last-sales`, `sepidar_stock_info_result`,
`new-inquiry-result-*`, `handel-drop`, and all Django
formset management and nested InquiryResult fields.

The visual behavior is in `quotation_v2_rows.js`. It does not override
pricing or workflow functions. It also normalizes dynamically added formset
rows to `#sortable-container` to match the existing sortable and pricing
observers. The original operational logic remains authoritative.

## Manual regression checklist

1. Open a historic mixed-version quotation and verify row totals and statuses.
2. Add two new rows, select SKUs using Select2, verify summaries and nested
   form indexes, save/reload and confirm both rows persist.
3. Open/close each card with mouse and keyboard, use open-all/close-all,
   and exercise existing global expand/collapse controls.
4. Check local and foreign inquiry flags, select inquiry, refresh and
   display price list according to user permission.
5. Test alternate SKU, item stock, order stock, assigned trade users,
   deadline, delay status, comments and customer descriptions.
6. Mark a row for deletion, then unmark it. Check removal after save and
   reorder with the drag handle.
7. Validate error cases and ensure invalid fields remain visible on rerender.
8. Try desktop, tablet and narrow mobile sizes with right-to-left labels.
9. Run the regression tests:
   `python manage.py test micmod_base.test_quotation_v2_row_ux micmod_base.test_pricing_v2_full micmod_base.test_pricing_v2`

No migration required. No production merge until the Django tests and
end-to-end UI checks have been run successfully.


## Compact layout refinement (2026-11-16)

- In quotations containing multiple rows, all valid existing rows start
  **collapsed**. Their compact header shows SKU, item, quantity, unit price,
  total amount and fulfillment indicators.
- All pricing UI is consolidated into one main **قیمت و محاسبات** block:
  inquiry flags, inquiry selection and history, pricing method, target
  price, unit fee, discount and totals. Price-source details form an
  expandable section *inside* this same pricing block.
- Quantity and stock are in the always-visible product workspace.
  **موجودی انبارها** and **موجودی سفارش‌ها** are now immediate product
  actions, not hidden inside an accordion. Existing Ajax endpoints and
  callbacks are unchanged.
- Packaging and customer-specific code/name remain available under a small
  summary disclosure in the product workspace.
- The three remaining secondary accordions—fulfillment/alternatives,
  supply/delivery and notes—are compact and show their key current values
  even when closed. Front-end summaries refresh after edits.
- Select2 product, alternate-product and inquiry selectors attach their
  dropdowns to their row **only on the v2 page**; legacy pages retain
  the body dropdown default. This avoids misplaced menus due to scroll
  containers/sticky toolbars.
- No changes to quotation calculations, ORM models, data, migrations,
  factor behavior or workflow logic.

Regression tests:

`python manage.py test micmod_base.test_quotation_v2_row_ux micmod_base.test_pricing_v2_full micmod_base.test_pricing_v2`

Manually verify the Select2 placement while scrolling, opening a collapsed
price inquiry, using each inventory action, adding/reordering rows, and
saving/advancing through the workflow. Static checks alone cannot prove
live browser geometry or business integration.
