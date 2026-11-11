# Copyright (C) 2026 - Akretion - Raphaël Valyi
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import re

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_br_fiscal.constants.fiscal import DOCUMENT_STATE_DRAFT

PF_CPF = "48290617402"
RURAL_CNPJ = "48290617000115"


class TestRuralProducerFieldNFe(TransactionCase):
    """POC https://github.com/OCA/l10n-brazil/issues/5580 — proposal B.

    One res.partner holds both documents: the CPF in `vat` and the rural
    activity CNPJ in `l10n_br_rural_cnpj`. The NFe tag choice is overridden
    so the XML goes out with the rural CNPJ (static per-partner rule).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env.ref("l10n_br_rural_producer.res_partner_rural_producer")

    def _serialize(self, nfe):
        """Same flow as l10n_br_nfe/tests/test_nfe_serialize.py"""
        if nfe.state_edoc != DOCUMENT_STATE_DRAFT:
            nfe.action_document_back2draft()
        nfe._register_hook()
        nfe.nfe40_detPag = [
            Command.clear(),
            Command.create(
                {
                    "nfe40_indPag": "0",
                    "nfe40_tPag": "01",
                    "nfe40_vPag": nfe.amount_financial_total,
                },
            ),
        ]
        nfe.action_document_confirm()
        nfe.with_context(force_product_lang="en_US")._document_export()
        return nfe.send_file_id.raw

    def test_partner_modeling(self):
        """One partner, two documents: CPF in vat, CNPJ in the rural field."""
        self.assertFalse(self.partner.is_company)
        self.assertEqual(self.partner.vat, PF_CPF)
        self.assertEqual(self.partner.l10n_br_rural_cnpj, RURAL_CNPJ)
        self.assertTrue(self.partner.l10n_br_is_rural_producer)
        self.assertEqual(self.partner.ind_ie_dest, "1")  # contribuinte ICMS

    def test_rural_cnpj_constraints(self):
        # invalid CNPJ is rejected
        with self.assertRaises(ValidationError):
            self.partner.l10n_br_rural_cnpj = "48290617000199"
        # the rural CNPJ cannot collide with another partner's vat
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Clone PJ",
                    "is_company": True,
                    "country_id": self.env.ref("base.br").id,
                    "vat": RURAL_CNPJ,
                }
            )
        # the rural CNPJ cannot collide with another partner's rural CNPJ
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Other Rural Producer",
                    "is_company": False,
                    "country_id": self.env.ref("base.br").id,
                    "vat": "71533482632",
                    "l10n_br_is_rural_producer": True,
                    "l10n_br_rural_cnpj": RURAL_CNPJ,
                }
            )
        # a company cannot be flagged as rural producer
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Wrong Company",
                    "is_company": True,
                    "country_id": self.env.ref("base.br").id,
                    "vat": "71533482000193",
                    "l10n_br_is_rural_producer": True,
                }
            )

    def test_nfe_out_dest_rural_cnpj(self):
        """The NFe dest carries the rural CNPJ + IE, not the CPF."""
        nfe = self.env.ref("l10n_br_rural_producer.demo_nfe_rural_out")
        xml = self._serialize(nfe)
        match = re.search(rb"<dest>.*?</dest>", xml, re.DOTALL)
        self.assertTrue(match, "no <dest> block in the serialized NFe")
        dest = match.group(0)
        self.assertIn(f"<CNPJ>{RURAL_CNPJ}</CNPJ>".encode(), dest)
        self.assertNotIn(b"<CPF>", dest)
        self.assertIn(b"<indIEDest>1</indIEDest>", dest)
        self.assertIn(b"<IE>6230790400090</IE>", dest)

    def test_nfe_in_vendor_nfe(self):
        """The vendor NFe is registered on the single partner, whose
        document-related fields still expose the CPF (see README limits)."""
        nfe = self.env.ref("l10n_br_rural_producer.demo_nfe_rural_in")
        self.assertEqual(nfe.issuer, "partner")
        self.assertEqual(nfe.partner_id, self.partner)
        # LIMITATION of proposal B: the document record shows the CPF while
        # the vendor's original XML was issued with the CNPJ.
        self.assertEqual(nfe.partner_cnpj_cpf, PF_CPF)
