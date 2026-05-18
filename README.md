# MSeller DGII e-CF Connector for Odoo

Foundation Odoo add-on that connects an Odoo company to the
[MSeller](https://mseller.app) DGII e-CF API (`https://ecf.api.mseller.app`)
so it can later push and reconcile electronic invoices (e-CF) with the
Dominican Republic's [DGII](https://dgii.gov.do).

> **Status — Foundation only.** This phase ships the connection
> configuration UI, a reusable Python client covering the full
> public e-CF API surface, and a Test Connection action. Invoice
> push, vendor bill ingestion and eNCF sequence management are
> on the roadmap below.

## Compatibility

| Odoo series | Python | Branch              | Status      |
|-------------|--------|---------------------|-------------|
| 17.0        | 3.10+  | `main`              | Supported   |
| 18.0        | 3.10+  | `main`              | Supported   |
| 19.0        | 3.11+  | `main`              | Supported   |
| 16.0        | 3.10   | (planned `16.0`)    | Not yet     |

The `main` branch targets Odoo **17.0 and later** in a single
codebase — Odoo 17 changed the settings form structure to use the
new `<app>` / `<block>` / `<setting>` tags, which are incompatible
with the 16.0 markup. Odoo 16.0 support will land on a dedicated
`16.0` branch (PRs welcome).

No extra Python dependencies — only the `requests` library bundled
with Odoo.

## Install

1. Clone this repository inside your Odoo add-ons path:
   ```bash
   git clone https://github.com/MSeller/mseller-odoo-connector.git \
       /opt/odoo/custom_addons/mseller-odoo-connector
   ```
2. Add the parent directory to `addons_path` in your `odoo.conf`:
   ```
   addons_path = /opt/odoo/addons,/opt/odoo/custom_addons/mseller-odoo-connector
   ```
3. Restart Odoo and update the apps list:
   ```bash
   ./odoo-bin -c odoo.conf -d <db> -u base --stop-after-init
   ```
4. **Apps** → remove the "Apps" filter → search "MSeller" → **Install**.

## Configure

Two equivalent entry points:

- **Settings → MSeller DGII e-CF** — quickest path for a single
  company.
- **Settings → Users & Companies → Companies → (pick) → MSeller e-CF
  tab** — useful in multi-company setups.

Fill in:

| Field        | Description                                                                 |
|--------------|-----------------------------------------------------------------------------|
| Environment  | `TesteCF` (sandbox), `CerteCF` (certification), or `eCF` (production).      |
| Email        | The MSeller account email.                                                  |
| Password     | The MSeller account password (masked in the UI).                            |
| API Key      | Created at <https://ecf.mseller.app/api-keys/list> (masked in the UI).      |

Save, then click **Test Connection**. On success a green toast is
shown and the cached `idToken` + expiry hint (decoded from the JWT
`exp` claim) appear under the button. On failure a `UserError` with
the underlying reason is raised. The action is restricted to
Settings administrators server-side, not only in the UI.

## Security note

Credentials are stored on `res.company` as plain text — Odoo's
standard storage. **Restrict database access accordingly** (encrypted
volumes, restricted DB users, etc.). The MSeller fields
(`mseller_email`, `mseller_password`, `mseller_api_key`,
`mseller_environment`, `mseller_id_token`,
`mseller_token_expiration`) carry `groups="base.group_system"` at
the model level, so non-admins cannot read them via ORM or RPC even
if they have read access to `res.company`. The Settings and
Companies views are gated by the same group. The Test Connection
action also enforces `has_group("base.group_system")` server-side.
Application-level encryption is on the roadmap.

## What the Python client exposes

The module ships `MSellerClient` in
`mseller_ecf_connector/models/mseller_client.py`. It is a plain
Python class (no ORM coupling) so it can be reused from models,
crons, controllers, and tests. The full public e-CF API surface is
implemented today:

| Method                              | HTTP | Path                            |
|-------------------------------------|------|---------------------------------|
| `authenticate()`                    | POST | `/customer/authentication`      |
| `send_ecf(document)`                | POST | `/documentos-ecf`               |
| `validate_ecf(document)`            | POST | `/documentos-ecf?validate=true` |
| `get_ecf_status(ecf)`               | GET  | `/documentos-ecf?ecf={NCF}`     |
| `get_ecf_status_batch(ecfs)`        | POST | `/documentos-ecf/status/batch`  |

Quick example:

```python
from odoo.addons.mseller_ecf_connector.models.mseller_client import MSellerClient

client = MSellerClient.from_company(env.company)
client.authenticate()
result = client.send_ecf(document_dict)
```

Document schemas follow the DGII e-CF JSON format documented in
[`ecf-mseller-docs`](https://github.com/MSeller/ecf-mseller-docs).

## Run the tests

```bash
./odoo-bin -c odoo.conf -d <db> \
    -i mseller_ecf_connector \
    --test-enable --stop-after-init --log-level=test
```

All HTTP calls are mocked, so no network access is required.

## Roadmap

1. **Invoice send** — wire `account.move` to `MSellerClient.send_ecf`;
   persist `internalTrackId`, `securityCode`, `qr_url`.
2. **eNCF sequence management** — per-journal sequence model with
   exhaustion warnings.
3. **Resilience** — cron-driven token refresh using `refreshToken`,
   application-level credential encryption, optional `queue_job`
   integration.
4. **Inbound** — poll DGII for received e-CFs, create draft vendor
   bills.
5. **Localization polish** — RNC validation, taxes / fiscal-position
   mapping on top of community `l10n_do`.

## Contributing

Pull requests are welcome. Please:

- Open an issue first for sizeable changes so we can align on scope.
- Target the `main` branch for Odoo 17 / 18 / 19 work, and the
  (planned) `16.0` branch for Odoo 16-specific work — they use
  fundamentally different settings-view markup.
- Keep new code compatible with the entire range supported by the
  branch you're targeting. On `main`: stick to APIs that exist on
  Odoo 17.0; avoid v18/19-only ORM helpers without a fallback. On
  `16.0`: use the legacy `<div class="app_settings_block">` markup
  and `attrs="{...}"` boolean syntax.
- Run the test suite locally before submitting.

## License

Licensed under the GNU Lesser General Public License v3.0
([LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.txt)). See `LICENSE`.
