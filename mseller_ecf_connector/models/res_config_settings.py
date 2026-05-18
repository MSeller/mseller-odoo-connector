from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mseller_email = fields.Char(
        related="company_id.mseller_email", readonly=False
    )
    mseller_password = fields.Char(
        related="company_id.mseller_password", readonly=False
    )
    mseller_api_key = fields.Char(
        related="company_id.mseller_api_key", readonly=False
    )
    mseller_environment = fields.Selection(
        related="company_id.mseller_environment", readonly=False
    )
    mseller_id_token = fields.Char(
        related="company_id.mseller_id_token", readonly=True
    )
    mseller_token_expiration = fields.Datetime(
        related="company_id.mseller_token_expiration", readonly=True
    )

    def action_mseller_test_connection(self):
        self.ensure_one()
        # Defensive: on Odoo 16 the object button may run before the
        # settings form persists related fields. Mirror current values
        # onto the company before delegating.
        self.company_id.write({
            "mseller_email": self.mseller_email,
            "mseller_password": self.mseller_password,
            "mseller_api_key": self.mseller_api_key,
            "mseller_environment": self.mseller_environment,
        })
        return self.company_id.action_mseller_test_connection()
