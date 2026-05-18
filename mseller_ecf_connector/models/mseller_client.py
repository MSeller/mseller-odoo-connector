import logging

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MSellerClient:
    """Plain-Python client for the MSeller DGII e-CF API.

    Stateless across requests except for the cached ``id_token``. Reuse from
    Odoo models, controllers, crons, or unit tests by constructing with raw
    values or via :meth:`from_company`.
    """

    HOST = "https://ecf.api.mseller.app"
    DEFAULT_TIMEOUT = 30

    ENV_PATHS = {
        "TesteCF": "TesteCF",
        "CerteCF": "CerteCF",
        "eCF": "eCF",
    }

    PATH_AUTH = "/customer/authentication"
    PATH_DOCUMENTOS_ECF = "/documentos-ecf"
    PATH_DOCUMENTOS_ECF_STATUS_BATCH = "/documentos-ecf/status/batch"

    BATCH_STATUS_MAX = 100

    def __init__(
        self,
        environment,
        email,
        password,
        api_key,
        id_token=None,
        timeout=None,
    ):
        if environment not in self.ENV_PATHS:
            raise UserError(
                _("Invalid MSeller environment: %s") % environment
            )
        self.environment = environment
        self.email = email
        self.password = password
        self.api_key = api_key
        self.id_token = id_token
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    @classmethod
    def from_company(cls, company):
        return cls(
            environment=company.mseller_environment or "TesteCF",
            email=company.mseller_email,
            password=company.mseller_password,
            api_key=company.mseller_api_key,
            id_token=company.mseller_id_token,
        )

    @property
    def base_url(self):
        return "%s/%s" % (self.HOST, self.ENV_PATHS[self.environment])

    def _auth_headers(self):
        if not self.id_token:
            raise UserError(
                _("MSeller client is not authenticated yet. Call authenticate() first.")
            )
        if not self.api_key:
            raise UserError(_("MSeller API key is not configured."))
        return {
            "Authorization": "Bearer %s" % self.id_token,
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method, path, *, authed=True, **kwargs):
        url = "%s%s" % (
            self.base_url,
            path if path.startswith("/") else "/" + path,
        )
        kwargs.setdefault("timeout", self.timeout)
        headers = dict(kwargs.pop("headers", None) or {})
        if authed:
            headers.update(self._auth_headers())
        else:
            headers.setdefault("Content-Type", "application/json")

        try:
            response = requests.request(method, url, headers=headers, **kwargs)
        except requests.exceptions.Timeout:
            raise UserError(
                _("MSeller request timed out after %ss: %s %s")
                % (self.timeout, method, url)
            )
        except requests.exceptions.ConnectionError as exc:
            raise UserError(
                _("Cannot reach MSeller (%s): %s") % (url, exc)
            )
        except requests.exceptions.RequestException as exc:
            raise UserError(_("MSeller %s %s failed: %s") % (method, url, exc))

        if response.status_code == 401:
            if authed:
                raise UserError(
                    _("MSeller token expired or unauthorized. Please re-authenticate.")
                )
            raise UserError(
                _("MSeller authentication failed: invalid email or password.")
            )
        if response.status_code >= 400:
            body = (response.text or "")[:500]
            raise UserError(
                _("MSeller %s %s [%s]: %s")
                % (method, url, response.status_code, body)
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise UserError(
                _("MSeller returned a non-JSON response: %s")
                % (response.text or "")[:200]
            )

    def authenticate(self):
        """POST ``/customer/authentication``.

        Returns the parsed response (``accessToken``, ``idToken``,
        ``refreshToken``) and caches ``id_token`` on the instance.
        """
        if not (self.email and self.password):
            raise UserError(_("MSeller email and password are required."))
        data = self._request(
            "POST",
            self.PATH_AUTH,
            authed=False,
            json={"email": self.email, "password": self.password},
        )
        id_token = data.get("idToken") or (
            data.get("AuthenticationResult") or {}
        ).get("IdToken")
        if not id_token:
            raise UserError(
                _("MSeller authentication response is missing idToken: %s") % data
            )
        self.id_token = id_token
        return data

    def send_ecf(self, document):
        """POST ``/documentos-ecf`` — submit a signed e-CF document."""
        if not isinstance(document, dict):
            raise UserError(_("MSeller e-CF document must be a dict."))
        return self._request(
            "POST", self.PATH_DOCUMENTOS_ECF, json=document
        )

    def validate_ecf(self, document):
        """POST ``/documentos-ecf?validate=true`` — dry-run validation.

        Does NOT consume an eNCF sequence.
        """
        if not isinstance(document, dict):
            raise UserError(_("MSeller e-CF document must be a dict."))
        return self._request(
            "POST",
            self.PATH_DOCUMENTOS_ECF,
            params={"validate": "true"},
            json=document,
        )

    def get_ecf_status(self, ecf):
        """GET ``/documentos-ecf?ecf={NCF}`` — single document status."""
        if not ecf:
            raise UserError(_("ecf is required to query MSeller status."))
        return self._request(
            "GET", self.PATH_DOCUMENTOS_ECF, params={"ecf": ecf}
        )

    def get_ecf_status_batch(self, ecfs):
        """POST ``/documentos-ecf/status/batch`` — bulk status query.

        ``ecfs`` is a list of eNCF strings, max ``BATCH_STATUS_MAX`` per call.
        """
        if not isinstance(ecfs, (list, tuple)):
            raise UserError(_("ecfs must be a list of eNCF strings."))
        if not ecfs:
            raise UserError(_("ecfs cannot be empty."))
        if len(ecfs) > self.BATCH_STATUS_MAX:
            raise UserError(
                _("MSeller batch status accepts at most %s eCFs per call (got %s).")
                % (self.BATCH_STATUS_MAX, len(ecfs))
            )
        return self._request(
            "POST",
            self.PATH_DOCUMENTOS_ECF_STATUS_BATCH,
            json={"ecfs": list(ecfs)},
        )
