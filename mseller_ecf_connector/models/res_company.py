import base64
import json
import logging
from datetime import datetime, timedelta

from odoo import _, fields, models
from odoo.exceptions import AccessError

from .mseller_client import MSellerClient

_logger = logging.getLogger(__name__)

# Restrict server-side access to MSeller connection data. Members of
# this group can read the credentials and the cached idToken via ORM
# or RPC; other users cannot read these fields even if they have
# read access to res.company.
MSELLER_FIELD_GROUPS = "base.group_system"

# Fallback expiry when the idToken cannot be decoded (it should always
# be a JWT in practice, but we guard against unexpected formats).
_FALLBACK_TOKEN_TTL = timedelta(hours=1)


def _jwt_expiration(token):
    """Return the ``exp`` claim of a JWT as a naive UTC datetime, or ``None``.

    The token is not validated cryptographically; we only need the
    expiration timestamp to drive the UI hint.
    """
    if not token or token.count(".") < 2:
        return None
    try:
        payload_b64 = token.split(".")[1]
        # JWT payloads are base64url-encoded without padding.
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return None
        return datetime.utcfromtimestamp(int(exp))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


class ResCompany(models.Model):
    _inherit = "res.company"

    mseller_email = fields.Char(
        string="MSeller Email", groups=MSELLER_FIELD_GROUPS
    )
    mseller_password = fields.Char(
        string="MSeller Password", groups=MSELLER_FIELD_GROUPS
    )
    mseller_api_key = fields.Char(
        string="MSeller API Key", groups=MSELLER_FIELD_GROUPS
    )
    mseller_environment = fields.Selection(
        selection=[
            ("TesteCF", "TesteCF (Sandbox)"),
            ("CerteCF", "CerteCF (Certification)"),
            ("eCF", "eCF (Production)"),
        ],
        string="MSeller Environment",
        default="TesteCF",
        required=True,
        groups=MSELLER_FIELD_GROUPS,
    )
    mseller_id_token = fields.Char(
        string="MSeller idToken",
        readonly=True,
        copy=False,
        groups=MSELLER_FIELD_GROUPS,
    )
    mseller_token_expiration = fields.Datetime(
        string="MSeller Token Expiration",
        readonly=True,
        copy=False,
        groups=MSELLER_FIELD_GROUPS,
    )

    def action_mseller_test_connection(self):
        """Authenticate against MSeller and cache the resulting idToken.

        Restricted to Settings administrators (``base.group_system``).
        The cached expiration is derived from the JWT ``exp`` claim
        when possible, falling back to a one-hour hint otherwise.
        """
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(
                _("Only Settings administrators can test the MSeller connection.")
            )
        client = MSellerClient.from_company(self)
        client.authenticate()
        expiration = _jwt_expiration(client.id_token) or (
            datetime.utcnow() + _FALLBACK_TOKEN_TTL
        )
        self.sudo().write({
            "mseller_id_token": client.id_token,
            "mseller_token_expiration": expiration,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("MSeller"),
                "message": _("Connection successful (environment: %s).")
                % self.mseller_environment,
                "type": "success",
                "sticky": False,
            },
        }
