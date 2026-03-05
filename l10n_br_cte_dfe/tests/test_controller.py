import contextlib
from unittest import mock

import odoo.http
from odoo import fields
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_br_fiscal_dfe.controllers.main import DfeDocumentBannerController


@contextlib.contextmanager
def mock_request(env):
    request = mock.Mock()
    request.env = env
    request.session.debug = ""
    odoo.http._request_stack.push(request)
    try:
        yield request
    finally:
        odoo.http._request_stack.pop()


class TestDfeControllerCte(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.controller = DfeDocumentBannerController()

    def _call_banner(self, fiscal_type="cte"):
        env = self.env(context={"allowed_company_ids": [self.company.id]})
        with mock_request(env):
            return self.controller.document_banner(fiscal_type=fiscal_type)

    def test_banner_cte_never_queried(self):
        self.company.cte_dfe_last_query = False
        self.company.cte_last_nsu = "0"

        result = self._call_banner(fiscal_type="cte")
        self.assertIn("Never been queried", result["html"])
        # Ensure it didn't look at NFe
        self.assertIn("CT-E Status", result["html"].upper())

    def test_banner_cte_synced(self):
        now = fields.Datetime.now()
        self.company.cte_dfe_last_query = now
        self.company.cte_last_nsu = "500"
        self.company.cte_max_nsu = "500"

        result = self._call_banner(fiscal_type="cte")
        self.assertIn("Synced", result["html"])
