import base64
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from odoo.addons.mseller_ecf_connector.models.res_company import (
    _jwt_expiration,
)


def _make_jwt(payload):
    """Build a non-signed JWT-shaped token from a payload dict."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=")
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=")
    return ("%s.%s.sig" % (header.decode(), body.decode()))


class TestJwtExpiration(TransactionCase):

    def test_parses_exp_claim(self):
        token = _make_jwt({"exp": 1_700_000_000, "sub": "x"})
        result = _jwt_expiration(token)
        self.assertEqual(result, datetime.utcfromtimestamp(1_700_000_000))

    def test_returns_none_when_exp_missing(self):
        token = _make_jwt({"sub": "x"})
        self.assertIsNone(_jwt_expiration(token))

    def test_returns_none_for_non_jwt(self):
        self.assertIsNone(_jwt_expiration("not-a-jwt"))
        self.assertIsNone(_jwt_expiration(""))
        self.assertIsNone(_jwt_expiration(None))

    def test_returns_none_for_malformed_payload(self):
        # Two dots, but middle segment is not valid base64+JSON.
        self.assertIsNone(_jwt_expiration("aaa.@@@.bbb"))

    def test_non_numeric_exp_returns_none(self):
        token = _make_jwt({"exp": "never"})
        self.assertIsNone(_jwt_expiration(token))


class TestActionTestConnection(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.user.company_id
        # Use sudo() because the credential fields are restricted to
        # base.group_system at the field level.
        self.company.sudo().write({
            "mseller_environment": "TesteCF",
            "mseller_email": "a@b.com",
            "mseller_password": "pwd",
            "mseller_api_key": "key",
        })

    def test_admin_can_test_connection(self):
        # The admin used in tests is a member of base.group_system.
        exp_ts = 1_700_000_000
        idtoken = _make_jwt({"exp": exp_ts})
        fake = MagicMock(status_code=200)
        fake.content = b"x"
        fake.json.return_value = {
            "idToken": idtoken,
            "accessToken": "A",
            "refreshToken": "R",
        }
        with patch("requests.request", return_value=fake):
            action = self.company.action_mseller_test_connection()
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        # Re-read with sudo() so the test user can see the restricted field.
        self.assertEqual(
            self.company.sudo().mseller_id_token, idtoken
        )
        self.assertEqual(
            self.company.sudo().mseller_token_expiration,
            datetime.utcfromtimestamp(exp_ts),
        )

    def test_non_admin_cannot_test_connection(self):
        non_admin = self.env["res.users"].create({
            "name": "Joe",
            "login": "joe-mseller-test",
            "email": "joe@example.com",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        # Same company; just downgraded user.
        company_as_joe = self.company.with_user(non_admin)
        with patch("requests.request") as p:
            with self.assertRaises(AccessError):
                company_as_joe.action_mseller_test_connection()
        # No HTTP call should have been attempted.
        p.assert_not_called()
