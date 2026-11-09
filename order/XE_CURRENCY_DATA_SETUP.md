# Xe Currency Data integration — Quick Packing

This integration uses the **official [Xe Currency Data API](https://developers.xe.com/docs/currency-data-api/getting-started)**, not scraping `xe.com`.

## Configure

In your deployment's **private** `.env` / environment variables:

```ini
XE_CURRENCY_API_KEY=your_xe_api_key
XE_RATES_CACHE_SECONDS=300
```

Alternatively for an existing Xe Data account, set both
`XE_CURRENCY_USERNAME` and `XE_CURRENCY_PASSWORD` (HTTP Basic auth). An
API key takes precedence when supplied. Do not check actual credentials into Git.

Xe's API requires an account/trial and subscription/allowance for live
or daily mid-market rates. A trial may return sample rates rather than real
market prices; confirm your entitlement with Xe. No Xe rate is generated
locally or guessed when access is unavailable.

## What users see

- Currency source/target: existing `Order.currency` and `Packing.currency`.
- On the header FX card, use **دریافت نرخ از XE** to fetch suggested rates
  for all applicable ISO currencies (single batched request).
- Missing rates can be filled automatically from the Xe suggestion. Saved
  rates and manual overrides stay untouched until the user explicitly chooses
  **استفاده از نرخ XE** beside a particular currency.
- The rate input remains editable at all times, including during Xe outages.
- XE returns mid-market quotes. For efficiency the server queries **target ->
  source** and inverts them before displaying **1 source -> target**.
- XE timestamp and data source are displayed. A fresh fetch can replace
  suggestions; the user must still save the Packing to persist adopted rates.
- Only the target and edited rates are stored in `currency_exchange_rates`.
  Calculated totals are computed client-side and never saved.
- The provider API credential is never sent to a browser.

**Limitations:** Only ISO three-letter currency codes supported by the Xe
subscription can be quoted. `RMB` is mapped to ISO `CNY`. Custom,
non-ISO currency labels remain manual. Rate quotes are cached briefly to
reduce API usage, subject to your Xe licensing conditions. XE plans can
limit the number and frequency of quotes.
