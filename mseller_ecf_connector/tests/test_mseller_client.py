from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.mseller_ecf_connector.models.mseller_client import (
    MSellerClient,
)


def _fake_response(status_code=200, json_body=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.content = b"x" if json_body is not None or text else b""
    response.text = text
    if json_body is None:
        response.json.side_effect = ValueError("no body")
    else:
        response.json.return_value = json_body
    return response


class TestMSellerClient(TransactionCase):

    # ---------- authenticate ----------
    def test_authenticate_success_caches_id_token(self):
        client = MSellerClient("TesteCF", "a@b.com", "pwd", "key")
        fake = _fake_response(
            200,
            {"idToken": "TOK", "accessToken": "A", "refreshToken": "R"},
        )
        with patch("requests.request", return_value=fake) as p:
            data = client.authenticate()
        p.assert_called_once()
        args, kwargs = p.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/TesteCF/customer/authentication"))
        self.assertEqual(
            kwargs["json"], {"email": "a@b.com", "password": "pwd"}
        )
        # auth headers must NOT be sent on the auth call
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertNotIn("x-api-key", kwargs["headers"])
        self.assertEqual(client.id_token, "TOK")
        self.assertEqual(data["idToken"], "TOK")

    def test_authenticate_bad_credentials_raises(self):
        client = MSellerClient("TesteCF", "a@b.com", "wrong", "key")
        fake = _fake_response(401, text="unauthorized")
        with patch("requests.request", return_value=fake):
            with self.assertRaises(UserError):
                client.authenticate()

    def test_authenticate_missing_credentials_raises_before_http(self):
        client = MSellerClient("TesteCF", "", "", "key")
        with patch("requests.request") as p:
            with self.assertRaises(UserError):
                client.authenticate()
        p.assert_not_called()

    # ---------- send_ecf ----------
    def test_send_ecf_success(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        fake = _fake_response(
            200,
            {
                "rnc": "102320705",
                "ecf": "E310000009175",
                "internalTrackId": "abc",
                "securityCode": "fWCZCV",
                "qr_url": "https://example/qr",
                "signedDate": "14-05-2025 02:57:33",
            },
        )
        document = {"ECF": {"Encabezado": {}, "DetallesItems": {}}}
        with patch("requests.request", return_value=fake) as p:
            response = client.send_ecf(document)
        args, kwargs = p.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/TesteCF/documentos-ecf"))
        self.assertEqual(kwargs["json"], document)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer TOK")
        self.assertEqual(kwargs["headers"]["x-api-key"], "key")
        self.assertEqual(response["ecf"], "E310000009175")

    def test_send_ecf_401_raises_reauth_message(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="STALE"
        )
        fake = _fake_response(401, text="token expired")
        with patch("requests.request", return_value=fake):
            with self.assertRaisesRegex(UserError, "re-authenticate"):
                client.send_ecf({"ECF": {}})

    def test_send_ecf_without_id_token_raises_before_http(self):
        client = MSellerClient("TesteCF", "a@b.com", "pwd", "key")
        with patch("requests.request") as p:
            with self.assertRaises(UserError):
                client.send_ecf({"ECF": {}})
        p.assert_not_called()

    # ---------- validate_ecf ----------
    def test_validate_ecf_sets_validate_query_param(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        fake = _fake_response(
            200, {"valid": True, "message": "ok"}
        )
        with patch("requests.request", return_value=fake) as p:
            response = client.validate_ecf({"ECF": {}})
        _, kwargs = p.call_args
        self.assertEqual(kwargs["params"], {"validate": "true"})
        self.assertTrue(response["valid"])

    def test_validate_ecf_invalid_response_passes_through(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        fake = _fake_response(
            200,
            {
                "valid": False,
                "message": "validation failed",
                "details": {"validationErrors": [{"code": "X"}]},
            },
        )
        with patch("requests.request", return_value=fake):
            response = client.validate_ecf({"ECF": {}})
        self.assertFalse(response["valid"])
        self.assertEqual(
            response["details"]["validationErrors"][0]["code"], "X"
        )

    # ---------- get_ecf_status ----------
    def test_get_ecf_status_sets_ecf_query_param(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        fake = _fake_response(
            200, {"ncf": "E310000009179", "status": "Aceptado"}
        )
        with patch("requests.request", return_value=fake) as p:
            response = client.get_ecf_status("E310000009179")
        args, kwargs = p.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(kwargs["params"], {"ecf": "E310000009179"})
        self.assertEqual(response["status"], "Aceptado")

    def test_get_ecf_status_requires_ecf(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        with patch("requests.request") as p:
            with self.assertRaises(UserError):
                client.get_ecf_status("")
        p.assert_not_called()

    # ---------- get_ecf_status_batch ----------
    def test_get_ecf_status_batch_body_shape(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        fake = _fake_response(
            200, {"total": 2, "results": [{"ecf": "E1"}, {"ecf": "E2"}]}
        )
        with patch("requests.request", return_value=fake) as p:
            response = client.get_ecf_status_batch(["E1", "E2"])
        args, kwargs = p.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(
            args[1].endswith("/TesteCF/documentos-ecf/status/batch")
        )
        self.assertEqual(kwargs["json"], {"ecfs": ["E1", "E2"]})
        self.assertEqual(response["total"], 2)

    def test_get_ecf_status_batch_enforces_max(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        too_many = ["E%d" % i for i in range(101)]
        with patch("requests.request") as p:
            with self.assertRaises(UserError):
                client.get_ecf_status_batch(too_many)
        p.assert_not_called()

    def test_get_ecf_status_batch_empty_raises(self):
        client = MSellerClient(
            "TesteCF", "a@b.com", "pwd", "key", id_token="TOK"
        )
        with patch("requests.request") as p:
            with self.assertRaises(UserError):
                client.get_ecf_status_batch([])
        p.assert_not_called()

    # ---------- env / url ----------
    def test_base_url_per_environment(self):
        for env in ("TesteCF", "CerteCF", "eCF"):
            client = MSellerClient(env, "a@b.com", "pwd", "key")
            self.assertEqual(
                client.base_url, "https://ecf.api.mseller.app/%s" % env
            )

    def test_invalid_environment_raises(self):
        with self.assertRaises(UserError):
            MSellerClient("Bogus", "a@b.com", "pwd", "key")
