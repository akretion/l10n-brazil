# Copyright 2026 Akretion - Raphaël Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import re

from odoo.exceptions import ValidationError

from .test_cte_serialize import TestCTeSerialize


class TestCTeComp(TestCTeSerialize):
    """The vPrest/Comp group of the CT-e.

    The leiaute caps the label of a component at 15 characters and documents
    it with freight price components ("FRETE PESO", "FRETE VALOR", "SEC/CAT"),
    so the description of the fiscal line, which has no such limit, can never
    be sent there: it used to be, and any realistic description made the
    CT-e fail the schema validation the module runs before sending it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass(
            [
                {
                    "record_ref": "l10n_br_cte.demo_cte_lc_modal_rodoviario",
                    "xml_file": "CTe35240781583054000129570010000057311040645894.xml",
                }
            ]
        )

    def _xml(self):
        """Serialize and sign the CT-e, then run the sending validation."""
        cte = self.cte_list[0]["cte"]
        edoc = cte.serialize()[0]
        xml = cte._edoc_processor().assina_raiz(edoc, edoc.infCte.Id)
        cte._validate_xml(xml)
        return cte, re.sub(
            r"\s+", " ", re.search(r"<vPrest>.*?</vPrest>", xml, re.S).group(0)
        )

    def test_long_description_is_never_the_label(self):
        """A realistic line description stays out of the 15 characters tag."""
        cte = self.cte_list[0]["cte"]
        cte.fiscal_line_ids.name = "Transporte rodoviario de cargas fracionadas"
        cte, vprest = self._xml()

        self.assertFalse(cte.xml_error_message, cte.xml_error_message)
        self.assertIn("<xNome>Frete</xNome>", vprest)

    def test_component_label_is_declared(self):
        """An itemized freight declares its own component label."""
        cte = self.cte_list[0]["cte"]
        cte.fiscal_line_ids.cte40_xNome = "PEDAGIO"
        cte, vprest = self._xml()

        self.assertFalse(cte.xml_error_message, cte.xml_error_message)
        self.assertIn("<xNome>PEDAGIO</xNome>", vprest)
        self.assertIn("<vComp>100.00</vComp>", vprest)

    def test_component_label_length_is_checked(self):
        """The leiaute limit is a user error, not a schema error at sending."""
        line = self.cte_list[0]["cte"].fiscal_line_ids[:1]
        with self.assertRaises(ValidationError):
            line.cte40_xNome = "A" * 16

    def test_one_component_per_line(self):
        """An itemized freight declares one component per fiscal line."""
        cte = self.cte_list[0]["cte"]
        cte.fiscal_line_ids.cte40_xNome = "FRETE PESO"
        cte.fiscal_line_ids[0].copy(
            {"name": "Pedagio", "cte40_xNome": "PEDAGIO", "price_unit": 30.0}
        )
        cte, vprest = self._xml()

        self.assertFalse(cte.xml_error_message, cte.xml_error_message)
        self.assertEqual(vprest.count("<Comp>"), 2)
        self.assertIn("<xNome>FRETE PESO</xNome>", vprest)
        self.assertIn("<xNome>PEDAGIO</xNome>", vprest)
        components = re.findall(r"<vComp>([\d.]+)</vComp>", vprest)
        self.assertAlmostEqual(sum(float(v) for v in components), cte.cte40_vTPrest)
