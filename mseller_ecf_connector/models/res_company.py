from datetime import datetime, timedelta

from odoo import _, fields, models

from .mseller_client import MSellerClient


class ResCompany(models.Model):
    _inherit = "res.company"

    mseller_email = fields.Char(string="MSeller Email")
    mseller_password = fields.Char(string="MSeller Password")
    mseller_api_key = fields.Char(string="MSeller API Key")
    mseller_environment = fields.Selection(
        selection=[
            ("TesteCF", "TesteCF (Sandbox)"),
            ("CerteCF", "CerteCF (Certification)"),
            ("eCF", "eCF (Production)"),
        ],
        string="MSeller Environment",
        default="TesteCF",
        required=True,
    )
    mseller_id_token = fields.Char(
        string="MSeller idToken", readonly=True, copy=False
    )
    mseller_token_expiration = fields.Datetime(
        string="MSeller Token Expiration", readonly=True, copy=False
    )

    def action_mseller_test_connection(self):
        """Authenticate against MSeller and cache the resulting idToken."""
        self.ensure_one()
        client = MSellerClient.from_company(self)
        client.authenticate()
        self.sudo().write({
            "mseller_id_token": client.id_token,
            "mseller_token_expiration": datetime.utcnow() + timedelta(hours=1),
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
