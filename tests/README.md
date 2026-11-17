# Quotation workspace browser checks

The suite uses the production workspace controller and Chromium with 200 synthetic quotation rows. It checks payload preservation (including nested inquiry forms), pagination, Persian/Arabic search, permissions, quantity events, error reveal, deletion/undo, stable pricing prefixes after reordering, and the existing formset Add/submit handlers.

Run from the repository root with Node 20+:

```sh
npm install --no-save --package-lock=false playwright
npx playwright install chromium
node --test tests/quotation_workspace.test.cjs
```

If Chromium is installed separately, set `CHROMIUM_PATH=/path/to/chromium`. The suite automatically uses `/usr/bin/chromium` when present. These are development dependencies; production needs no additional JavaScript packages.

The fixtures do not connect to the application's database, Sepidar, stock services or price inquiry APIs. Before release, check a saved quotation and a new quotation in staging, with sales and inquiry roles: price lookup/refresh, discounts/tax, workflow transitions, print/export, comments/payments, customer lookup, and existing invoiced/cancelled restrictions.

The editor keeps all real form controls mounted when filtering/paging; proxy quantity controls have no POST name. `.counter` stays tied to the Django form prefix because the existing price-method builder reads it. `[data-qw-position]` supplies the visible order separately. The original shared `item3.html` remains unchanged; the quotation view uses `workspace_item.html`.
