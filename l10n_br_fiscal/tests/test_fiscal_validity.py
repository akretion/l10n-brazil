# Copyright 2026 Akretion - Renato Lima <renato.lima@akretion.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, fields
from odoo.tests import TransactionCase


class TestFiscalDataValidity(TransactionCase):
    """Validity window (date_start/date_end) for `l10n_br_fiscal.data.abstract`
    descendants, exercised through `l10n_br_fiscal.ncm`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ncm = cls.env["l10n_br_fiscal.ncm"]
        cls.today = fields.Date.context_today(cls.Ncm)

    def _create_ncm(self, code, **kwargs):
        vals = {"code": code, "name": "Test NCM %s" % code}
        vals.update(kwargs)
        return self.Ncm.create(vals)

    def test_no_dates_stay_active(self):
        ncm = self._create_ncm("11111111")
        ncm._expire_invalid_records()
        self.assertTrue(ncm.active)

    def test_future_start_date_stays_active(self):
        """A record that has not started yet must not be archived: it is
        already kept out of any selection by the query-time filter, and
        there is no method to reactivate it once archived."""
        ncm = self._create_ncm(
            "22222222", date_start=fields.Date.add(self.today, days=5)
        )
        ncm._expire_invalid_records()
        self.assertTrue(ncm.active)

    def test_past_end_date_expires(self):
        ncm = self._create_ncm(
            "33333333", date_end=fields.Date.subtract(self.today, days=1)
        )
        ncm._expire_invalid_records()
        self.assertFalse(ncm.active)

    def test_within_range_stays_active(self):
        ncm = self._create_ncm(
            "44444444",
            date_start=fields.Date.subtract(self.today, days=1),
            date_end=fields.Date.add(self.today, days=1),
        )
        ncm._expire_invalid_records()
        self.assertTrue(ncm.active)

    def test_only_start_date_in_the_past_stays_active(self):
        ncm = self._create_ncm(
            "55555555", date_start=fields.Date.subtract(self.today, days=1)
        )
        ncm._expire_invalid_records()
        self.assertTrue(ncm.active)

    def test_cron_expires_across_fiscal_data_models(self):
        expired_ncm = self._create_ncm(
            "66666666", date_end=fields.Date.subtract(self.today, days=1)
        )
        valid_ncm = self._create_ncm("77777777")
        self.env["l10n_br_fiscal.data.abstract"]._cron_expire_fiscal_parametrization()
        self.assertFalse(expired_ncm.active)
        self.assertTrue(valid_ncm.active)


class TestOperationLineValidity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.line = self.env.ref("l10n_br_fiscal.fo_venda_venda")
        self.today = fields.Datetime.now()

    def test_expired_line_is_marked_expired(self):
        self.line.state = "approved"
        self.line.date_end = fields.Datetime.subtract(self.today, hours=1)
        self.env["l10n_br_fiscal.operation.line"]._expire_invalid_lines()
        self.assertEqual(self.line.state, "expired")

    def test_valid_line_is_not_marked_expired(self):
        self.line.state = "approved"
        self.line.date_start = False
        self.line.date_end = False
        self.env["l10n_br_fiscal.operation.line"]._expire_invalid_lines()
        self.assertEqual(self.line.state, "approved")

    def test_future_line_is_not_marked_expired(self):
        """A line that has not started yet must not be marked 'expired':
        it hasn't ended, it hasn't even begun, and there is no way back
        from 'expired' other than a manual re-approval."""
        self.line.state = "approved"
        self.line.date_start = fields.Datetime.add(self.today, days=5)
        self.line.date_end = False
        self.env["l10n_br_fiscal.operation.line"]._expire_invalid_lines()
        self.assertEqual(self.line.state, "approved")


class TestTaxDefinitionValidity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Datetime.now()

    def _create_tax_definition(self, code, **kwargs):
        vals = {
            "tax_group_id": self.env.ref("l10n_br_fiscal.tax_group_icms").id,
            "code": code,
            "name": "Test Tax Definition %s" % code,
            "state": "approved",
        }
        vals.update(kwargs)
        return self.env["l10n_br_fiscal.tax.definition"].create(vals)

    def test_expired_definition_is_marked_expired(self):
        tax_definition = self._create_tax_definition(
            "TDV001",
            date_end=fields.Datetime.subtract(self.today, hours=1),
        )
        self.env["l10n_br_fiscal.tax.definition"]._expire_invalid_definitions()
        self.assertEqual(tax_definition.state, "expired")

    def test_valid_definition_is_not_marked_expired(self):
        tax_definition = self._create_tax_definition("TDV002")
        self.env["l10n_br_fiscal.tax.definition"]._expire_invalid_definitions()
        self.assertEqual(tax_definition.state, "approved")

    def test_future_definition_is_not_marked_expired(self):
        """A definition that has not started yet must not be marked
        'expired': see test_future_line_is_not_marked_expired above for
        why."""
        tax_definition = self._create_tax_definition(
            "TDV004", date_start=fields.Datetime.add(self.today, days=5)
        )
        self.env["l10n_br_fiscal.tax.definition"]._expire_invalid_definitions()
        self.assertEqual(tax_definition.state, "approved")

    def test_map_tax_definition_excludes_out_of_validity_records(self):
        tax_definition = self._create_tax_definition(
            "TDV003",
            date_start=fields.Datetime.add(self.today, days=5),
            state_from_id=self.env.ref("base.state_br_sp").id,
            state_to_ids=[Command.set(self.env.ref("base.state_br_mg").ids)],
        )
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        partner = self.env.ref("l10n_br_base.res_partner_cliente9_mg")
        product = self.env.ref("product.product_product_7")
        result = tax_definition.map_tax_definition(
            company,
            partner,
            product,
            city_taxation_code=self.env["l10n_br_fiscal.city.taxation.code"],
            national_taxation_code=self.env["l10n_br_fiscal.national.taxation.code"],
            service_type=self.env["l10n_br_fiscal.service.type"],
        )
        self.assertNotIn(tax_definition, result)

    def test_map_tax_definition_uses_reference_date(self):
        """map_tax_definition() must filter against `reference_date` (e.g.
        the document's own date) instead of always using now(), so
        backdated documents are taxed with the rules that were in force
        on their own date, not today's."""
        tax_definition = self._create_tax_definition(
            "TDV005",
            date_start=fields.Datetime.subtract(self.today, days=20),
            date_end=fields.Datetime.subtract(self.today, days=10),
            state_from_id=self.env.ref("base.state_br_sp").id,
            state_to_ids=[Command.set(self.env.ref("base.state_br_mg").ids)],
        )
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        partner = self.env.ref("l10n_br_base.res_partner_cliente9_mg")
        product = self.env.ref("product.product_product_7")
        kwargs = dict(
            city_taxation_code=self.env["l10n_br_fiscal.city.taxation.code"],
            national_taxation_code=self.env["l10n_br_fiscal.national.taxation.code"],
            service_type=self.env["l10n_br_fiscal.service.type"],
        )

        # today the definition is already over: excluded by default (now())
        result_today = tax_definition.map_tax_definition(
            company, partner, product, **kwargs
        )
        self.assertNotIn(tax_definition, result_today)

        # but it was in force on a document dated within its window
        result_backdated = tax_definition.map_tax_definition(
            company,
            partner,
            product,
            reference_date=fields.Datetime.subtract(self.today, days=15),
            **kwargs,
        )
        self.assertIn(tax_definition, result_backdated)


class TestOperationLineDefinitionReferenceDate(TransactionCase):
    """`_line_domain()`/`line_definition()` must also filter against
    `reference_date`, not just `map_tax_definition()`, so a backdated
    document resolves the operation line that was in force on its own
    date."""

    def test_line_definition_uses_reference_date(self):
        operation = self.env.ref("l10n_br_fiscal.fo_bonificacao")
        partner = self.env["res.partner"].create(
            {"name": "Destinatário Teste Vigência", "ind_ie_dest": "9"}
        )
        product = self.env["product.product"].create({"name": "Produto Teste Vigência"})
        today = fields.Datetime.now()

        line = operation.line_definition(self.env.company, partner, product)
        self.assertTrue(line, "bonificação ficou sem linha de operação")

        line.date_start = fields.Datetime.subtract(today, days=20)
        line.date_end = fields.Datetime.subtract(today, days=10)

        # today the line is already over: not selected by default (now())
        self.assertFalse(operation.line_definition(self.env.company, partner, product))

        # but it was in force on a document dated within its window
        backdated_line = operation.line_definition(
            self.env.company,
            partner,
            product,
            reference_date=fields.Datetime.subtract(today, days=15),
        )
        self.assertEqual(backdated_line, line)
