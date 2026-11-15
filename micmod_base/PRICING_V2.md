# Quotation pricing v2 — rollout and BI contract

The original quotation route, form classes, workflow, JS and customer/employee
print templates remain available. Version-2 pricing is explicitly enabled per
QuotationItem and uses a separate price editor.

## Rollout

1. Deploy code and run `python manage.py migrate micmod_base`.
2. Existing rows receive `pricing_version=1` (including historic manager-approved
   prices with a discount). **No price or discount is migrated or recalculated.**
3. Open `/micmod_base/quotation/v2/<quotation_id>/` using the current project's
   URL prefix. There is also a link on the original quotation screen.
4. Add any new rows via this editor: they are created with `pricing_version=2`,
   even if the parent quotation contains version-1 rows.
5. Refresh the inquiry on a v2 row, select the reference, then save. The server
   selects the reference amount from its persisted snapshot (not the submitted
   amount).
6. Version-1 rows show their legacy financial totals. Upgrading one requires
   explicitly selecting a system reference and checking the acknowledgement.
7. Verify with:
   `python manage.py test micmod_base.test_pricing_v2 factor.test_modern_print`

The legacy entry screen still creates legacy-form rows, intentionally preserving
its unchanged calculations. Use the v2 price editor to add v2 rows.

## BI fields on micmod_base_quotationitem

| Column | Meaning |
| --- | --- |
| pricing_version | 1 = historical rules; 2 = new rules |
| system_price | Reference unit price from inquiry, **never overwritten by manager approval** |
| system_price_method | Selected pricing method |
| system_price_snapshot | Selected inquiry metadata and currency |
| manager_approved_price | Manually approved selling unit price, if used |
| effective_unit_price | Unit sale price after commercial discounts (before tax) |
| calculated_row_discount | Row discount total, including applicable official tax-base adjustment |
| manager_price_difference | Signed unit difference: approved minus system price |
| manager_positive_difference | Positive approved-minus-system difference × row quantity |

Version-1 BI fields are NULL, not zero, when a valid historical baseline cannot
be reconstructed. Do not coalesce these NULLs to zero in performance reporting.

For a v2 manager-priced row, the document-level `self_discount` and the
legacy `discount_per_item` never apply. If the approved unit price is lower
than the system reference, the customer-visible unit base is the system
reference and the difference is the row discount. If the approved price is
higher, the customer-visible unit base is the approved price, the row
commercial discount is zero, and the positive difference is recorded for BI.

Version-1 item methods and existing historical data retain their previous
behavior. The v2 calculator is `micmod_base.pricing_v2`. Quotation item and
quotation financial change signals keep materialized BI fields current. A
currency switch on a priced v2 document is blocked until the pricing reference
is reselected, to prevent silently reinterpreting its unit price.

## Related systems

- Quotation totals, current customer print, and Sepidar quotation serialization
  use the version-aware item financial properties.
- Direct factor conversion and quotation-backed factor creation use the
  v2 customer-visible base and calculated unit discount; manager-priced factor
  rows skip the quotation-wide self_discount.
- Existing factor and quotation legacy rows use their original calculations.
- Print layouts display an increase over system price as the customer-visible
  price without exposing the system reference.

## Safety checks before merging

Test on a staging copy of production data. Compare all historical quotations'
amounts, especially the known legacy manager-priced + discounted rows.
Verify quotation-to-Sepidar totals, quote-to-factor totals, and BI queries using
a mix of v1, v2 regular, v2 manager-below, and v2 manager-above rows. Do not
enable production rollout without running migrations and end-to-end integration
tests with the actual Sepidar and database environment.
