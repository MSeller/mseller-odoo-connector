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
        # Persist any unsaved edits on the settings form so the test
        # runs against the values the user just typed in.
        self.execute()
        return self.company_id.action_mseller_test_connection()
