# Copyright (C) 2026 - Akretion - Raphaël Valyi
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import re

from odoo import Command
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_br_fiscal.constants.fiscal import DOCUMENT_STATE_DRAFT

PF_CPF = "48290617402"
FAZENDA_CNPJ = "48290617000115"


class TestRuralProducerChildNFe(TransactionCase):
    """POC https://github.com/OCA/l10n-brazil/issues/5580 — proposal A.

    The produtor rural is a parent/child partner pair: the pessoa física
    keeps his CPF, the child company holds the rural activity CNPJ/IE.
    No code change is required: the NFe CNPJ/CPF tag choice follows the
    selected partner, so both fiscal personas of the same individual can
    receive (and emit) fiscal documents.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.pf = cls.env.ref("l10n_br_rural_producer.res_partner_rural_producer_pf")
        cls.fazenda = cls.env.ref(
            "l10n_br_rural_producer.res_partner_rural_producer_fazenda"
        )

    def _dest_block(self, nfe):
        xml = self._serialize(nfe)
        match = re.search(rb"<dest>.*?</dest>", xml, re.DOTALL)
        self.assertTrue(match, "no <dest> block in the serialized NFe")
        return match.group(0)

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
        """Parent/child keep independent documents; sync never copies vat."""
        self.assertFalse(self.pf.is_company)
        self.assertEqual(self.pf.vat, PF_CPF)
        self.assertEqual(self.pf.ind_ie_dest, "9")  # não contribuinte

        self.assertTrue(self.fazenda.is_company)
        self.assertEqual(self.fazenda.vat, FAZENDA_CNPJ)
        self.assertEqual(self.fazenda.parent_id, self.pf)
        self.assertEqual(self.fazenda.ind_ie_dest, "1")  # contribuinte ICMS
        self.assertTrue(self.fazenda.l10n_br_ie_code)
        # a child company is its own commercial partner:
        self.assertEqual(self.fazenda.commercial_partner_id, self.fazenda)

        # l10n_br_base excludes `vat` from the parent<->children commercial
        # sync: running it explicitly must not clobber either document.
        self.fazenda._commercial_sync_from_company()
        self.pf._commercial_sync_to_children()
        self.assertEqual(self.pf.vat, PF_CPF)
        self.assertEqual(self.fazenda.vat, FAZENDA_CNPJ)

    def test_nfe_out_dest_cnpj(self):
        """Sale to the rural activity: <dest> carries the CNPJ + IE."""
        nfe = self.env.ref("l10n_br_rural_producer.demo_nfe_rural_out_cnpj")
        dest = self._dest_block(nfe)
        self.assertIn(f"<CNPJ>{FAZENDA_CNPJ}</CNPJ>".encode(), dest)
        self.assertNotIn(b"<CPF>", dest)
        self.assertIn(b"<indIEDest>1</indIEDest>", dest)
        self.assertIn(b"<IE>6230790400090</IE>", dest)

    def test_nfe_out_dest_cpf(self):
        """Sale to the pessoa física: <dest> carries the CPF, no IE."""
        nfe = self.env.ref("l10n_br_rural_producer.demo_nfe_rural_out_cpf")
        dest = self._dest_block(nfe)
        self.assertIn(f"<CPF>{PF_CPF}</CPF>".encode(), dest)
        self.assertNotIn(b"<CNPJ>", dest)
        self.assertIn(b"<indIEDest>9</indIEDest>", dest)
        self.assertNotIn(b"<IE>", dest)

    def test_nfe_in_vendor_nfe(self):
        """The NFe the produtor rural emits is registered on the CNPJ child."""
        nfe = self.env.ref("l10n_br_rural_producer.demo_nfe_rural_in")
        self.assertEqual(nfe.issuer, "partner")
        self.assertEqual(nfe.partner_id, self.fazenda)
        self.assertEqual(nfe.partner_cnpj_cpf, FAZENDA_CNPJ)
        self.assertEqual(nfe.partner_id.commercial_partner_id, self.fazenda)
