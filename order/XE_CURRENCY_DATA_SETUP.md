# XE reference workflow (no XE API or page scraping)

The current Quick Packing UI offers **manual entry of an exchange rate** with
a direct link to the corresponding pair on [Xe's currency converter](https://www.xe.com/currencyconverter/).
Opening that link is a user action; the portal **does not fetch or parse XE's
currency website or its API**, and no credentials or XE subscription are required.

Xe's [Terms of Use](https://www.xe.com/legal/) prohibit automated extraction
of its rate data (including screen scraping), as well as certain other uses of
its data. Confirm that your intended use is permitted by your applicable terms.

## Steps

1. In the financial overview on Quick Packing, select the destination
   currency (for example USD).
2. Next to each source currency (such as EUR), click **View rate on XE**.
   The user sees the relevant 1 EUR -> USD XE converter in a new tab.
3. Enter the desired rate into the corresponding editable rate field.
   In Quick Packing, 1 source currency unit = N destination currency units.
4. Save the Packing. Only the target and manually entered rates are stored;
   the calculated total is always calculated in the browser.
5. Besides standard ISO codes, the following internal Currency.title_en values
   map to XE three-letter ISO codes (case-insensitive; whitespace-normalized):

   | Currency.title_en | XE ISO code |
   | --- | --- |
   | `ero` | `EUR` |
   | `rmb` | `CNY` |
   | `Dollar` | `USD` |
   | `Emirates Dirham` | `AED` |

   Other/custom currencies remain manual without an XE link.

The page never automatically changes manual rates, and the rate shown on XE
should be verified by the user at the time of entry.

To obtain automatic quotes for an ERP without the XE API, use an alternative
source whose license permits automated ingestion; do not scrape XE's site
without written authorization.
