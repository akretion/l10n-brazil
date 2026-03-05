import base64
import gzip
from io import BytesIO
from unittest import mock

from xsdata.formats.dataclass.transports import DefaultTransport

from odoo.tests.common import TransactionCase

# Using helper to simulate dynamic build or just importing static mock
from .mock_cte_responses import _PROC_CTE_XML, _RES_CTE_XML


def _gzip_base64(xml_str):
    buf = BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(xml_str.encode("utf-8"))
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _build_cte_response(
    doczip_list, ult_nsu="000000000000300", max_nsu="000000000000300"
):
    parts = []
    for nsu, schema, xml_content in doczip_list:
        encoded = _gzip_base64(xml_content)
        parts.append(f'<docZip NSU="{nsu}" schema="{schema}">{encoded}</docZip>')
    doczip_xml = "".join(parts)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soap:Body><cteDistDFeInteresseResponse"
        ' xmlns="http://www.portalfiscal.inf.br/cte/wsdl/CTeDistribuicaoDFe"><cteDistDFeInteresseResult>'
        '<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/cte" versao="1.00">'
        "<cStat>138</cStat><xMotivo>Documento(s) localizado(s)</xMotivo>"
        f"<ultNSU>{ult_nsu}</ultNSU><maxNSU>{max_nsu}</maxNSU>"
        f"<loteDistDFeInt>{doczip_xml}</loteDistDFeInt>"
        "</retDistDFeInt></cteDistDFeInteresseResult>"
        "</cteDistDFeInteresseResponse></soap:Body></soap:Envelope>"
    )


class TestCTeDFe(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")

    def setUp(self):
        super().setUp()
        self.company.invalidate_recordset()
        self.company.write({"cte_last_nsu": "0", "cte_max_nsu": "0"})
        self.env["l10n_br_fiscal_dfe.dfe"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()
        self.env["l10n_br_fiscal_dfe.document"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()

    def _search_cte_dfe(self):
        return self.env["l10n_br_fiscal_dfe.dfe"].search(
            [("company_id", "=", self.company.id), ("fiscal_type", "=", "cte")]
        )

    @mock.patch.object(DefaultTransport, "post")
    def test_cte_search_documents_success(self, mock_post):
        # We construct a response dynamically to ensure we control the XML content match
        mock_response = _build_cte_response(
            [
                ("000000000000200", "resCTe_v1.00.xsd", _RES_CTE_XML),
                ("000000000000201", "procCTe_v4.00.xsd", _PROC_CTE_XML),
            ],
            ult_nsu="000000000000201",
            max_nsu="000000000000201",
        )

        mock_post.return_value = mock_response.encode("utf-8")
        self.company._cte_dfe_document_distribution()

        self.assertEqual(self.company.cte_last_nsu, "000000000000201")
        records = self._search_cte_dfe()
        self.assertEqual(len(records), 2)

        # Validate resCTe
        summary = records.filtered(lambda r: r.document_type_dfe == "summary")
        self.assertEqual(
            summary.access_key, "35200159594315000157570010000000012062777161"
        )
        # Ensure document header fields populated
        self.assertEqual(summary.dfe_document_id.emitter, "Test Emitter CTe")

        # Validate procCTe
        complete = records.filtered(lambda r: r.document_type_dfe == "complete")
        self.assertEqual(
            complete.access_key, "35200159594315000157570010000000012062777162"
        )
        self.assertEqual(complete.dfe_document_id.emitter, "Test Emitter CTe Complete")

    @mock.patch.object(DefaultTransport, "post")
    def test_cte_import_document(self, mock_post):
        mock_response = _build_cte_response(
            [
                ("000000000000201", "procCTe_v4.00.xsd", _PROC_CTE_XML),
            ]
        )
        mock_post.return_value = mock_response.encode("utf-8")
        self.company._cte_dfe_document_distribution()

        doc = self.env["l10n_br_fiscal_dfe.document"].search(
            [
                ("company_id", "=", self.company.id),
                ("access_key", "=", "35200159594315000157570010000000012062777162"),
            ]
        )

        fiscal_doc = doc.import_document()
        self.assertTrue(
            fiscal_doc, "Fiscal document should be created after CTe import"
        )
        self.assertEqual(
            fiscal_doc.document_key, "35200159594315000157570010000000012062777162"
        )
