import base64
import re
from datetime import datetime, timezone

from lxml import objectify

from odoo import api, fields, models

from odoo.addons.l10n_br_fiscal_dfe.tools import utils

try:
    # Check your nfelib binding path, assuming standard CteProc for v4.00
    from nfelib.cte.bindings.v4_0.proc_cte_v4_00 import CteProc
    from nfelib.cte.client.v4_0.dfe import CteDfeClient
except ImportError:
    CteDfeClient = None
    CteProc = None


class ResCompany(models.Model):
    _inherit = "res.company"

    cte_last_nsu = fields.Char(string="CT-e Last NSU", size=25, default="0")
    cte_max_nsu = fields.Char(string="CT-e Max NSU", readonly=True)
    cte_dfe_next_query = fields.Datetime(string="CT-e Next Query")
    cte_dfe_last_query = fields.Datetime(string="CT-e Last Query")
    cte_auto_fetch = fields.Boolean(default=False, string="Auto-fetch CT-e")

    def _cte_dfe_get_processor(self):
        self.ensure_one()
        cert = base64.b64decode(self.certificate.file)
        return CteDfeClient(
            ambiente=self.cte_environment,
            uf=self.state_id.ibge_code,
            pkcs12_data=cert,
            pkcs12_password=self.certificate.password,
            wrap_response=True,
        )

    def _cte_dfe_search_specific_document(self, access_key=None, nsu=None):
        self.ensure_one()
        processor = self._cte_dfe_get_processor()
        result = processor.consultar_distribuicao(
            chave=access_key,
            nsu_especifico=utils.format_nsu(nsu) if nsu else None,
            cnpj_cpf=re.sub("[^0-9]", "", self.vat),
        )
        if not self._dfe_validate_distribution_response(result, raise_message=True):
            return

        self._dfe_log(
            f"CT-e Specific OK: {result.resposta.cStat}",
            log_type="success",
            result=result,
        )
        self._cte_process_distribution(result.resposta)

    def _cte_dfe_document_distribution(self):
        self.ensure_one()
        last_nsu = (
            self.cte_last_nsu if self.cte_last_nsu.isdigit() else "000000000000000"
        )
        processor = self._cte_dfe_get_processor()

        while True:
            try:
                result = processor.consultar_distribuicao(
                    cnpj_cpf=re.sub("[^0-9]", "", self.vat),
                    ultimo_nsu=utils.format_nsu(last_nsu),
                )
            except Exception as exc:
                self._dfe_log(f"CT-e Search Error: {exc}", log_type="error")
                break

            resp = result.resposta
            if not self._dfe_validate_distribution_response(result):
                if resp.cStat == "656" and getattr(resp, "ultNSU", False):
                    last_nsu = resp.ultNSU
                break

            last_nsu = getattr(resp, "ultNSU", last_nsu)
            max_nsu = getattr(resp, "maxNSU", False)

            self._dfe_log(
                f"CT-e OK: {resp.cStat} - {resp.xMotivo}",
                log_type="success",
                result=result,
            )
            self._cte_process_distribution(resp)

            if max_nsu and last_nsu >= max_nsu:
                self.cte_max_nsu = max_nsu
                break

        self.cte_last_nsu = last_nsu
        self.cte_dfe_last_query = fields.Datetime.now()

    def _cte_process_distribution(self, result):
        DfeRecord = self.env["l10n_br_fiscal_dfe.dfe"].sudo()
        for doc in result.loteDistDFeInt.docZip:
            payload = getattr(doc, "value", None) or getattr(doc, "valueOf_", None)
            if not payload:
                continue

            xml = utils.parse_gzip_xml(
                base64.b64encode(payload).decode()
                if isinstance(payload, bytes)
                else payload
            ).read()
            root = objectify.fromstring(xml)
            schema_type = (
                getattr(doc, "schema_value", "") or getattr(doc, "schema", "")
            ).split("_")[0]
            nsu = utils.format_nsu(getattr(doc, "NSU", False))

            if DfeRecord.search(
                [
                    ("nsu", "=", nsu),
                    ("company_id", "=", self.id),
                    ("fiscal_type", "=", "cte"),
                ],
                limit=1,
            ):
                continue

            dfe_record = DfeRecord.create(
                {
                    "nsu": nsu,
                    "company_id": self.id,
                    "fiscal_type": "cte",
                    "schema_type": schema_type,
                }
            )

            if schema_type == "procCTe":
                self._cte_create_from_procCTe(root, dfe_record)
            elif schema_type == "resCTe":
                self._cte_create_from_resCTe(root, dfe_record)

            dfe_record.create_xml_attachment(xml)

    def _cte_get_or_create_document(self, access_key):
        Document = self.env["l10n_br_fiscal_dfe.document"].sudo()
        doc = Document.search(
            [("access_key", "=", access_key), ("company_id", "=", self.id)], limit=1
        )
        if not doc:
            doc = Document.create(
                {
                    "access_key": access_key,
                    "company_id": self.id,
                    "fiscal_type": "cte",
                    "vat": utils.mask_cnpj(access_key[6:20]),
                    "serie": access_key[22:25].lstrip("0") or "0",
                    "document_number": access_key[25:34].lstrip("0") or "0",
                }
            )
        return doc

    def _cte_create_from_procCTe(self, root, dfe_record):
        key = str(root.protCTe.infProt.chCTe)
        doc = self._cte_get_or_create_document(key)
        dfe_record.write(
            {
                "access_key": key,
                "document_type_dfe": "complete",
                "dfe_document_id": doc.id,
            }
        )
        doc._update_metadata(
            {
                "emitter": str(root.CTe.infCte.emit.xNome),
                "document_amount": float(root.CTe.infCte.vPrest.vTPrest),
                "document_state": "1",
                "document_emission_date": datetime.fromisoformat(
                    str(root.CTe.infCte.ide.dhEmi)
                )
                .astimezone(timezone.utc)
                .replace(tzinfo=None),
            },
            is_complete=True,
        )

    def _cte_create_from_resCTe(self, root, dfe_record):
        key = str(root.chCTe)
        doc = self._cte_get_or_create_document(key)
        dfe_record.write(
            {
                "access_key": key,
                "document_type_dfe": "summary",
                "dfe_document_id": doc.id,
            }
        )
        doc._update_metadata(
            {
                "emitter": str(root.xNome),
                # resCTe has vCarga (Total Value of Cargo) or vTPrest? resCTe usually exposes vCarga or vRec.
                # Standard resCTe v3.00/4.00 has vTPrest? No, it has vCarga. But often mapping vCarga to amount is acceptable for summary.
                "document_amount": float(
                    getattr(root, "vTPrest", getattr(root, "vCarga", 0.0))
                ),
                "document_state": str(root.cSitCTe),
                "document_emission_date": datetime.fromisoformat(str(root.dhEmi))
                .astimezone(timezone.utc)
                .replace(tzinfo=None),
            }
        )

    @api.model
    def parse_procCTe(self, xml_stream):
        binding = CteProc.from_xml(xml_stream.read().decode())
        return self.env["l10n_br_fiscal.document"].import_binding_cte(binding)

    @api.model
    def _cron_cte_dfe_search_documents(self):
        companies = self.search([("cte_auto_fetch", "=", True)])
        for company in companies:
            # Add delay logic here if needed or run synchronously
            company._cte_dfe_document_distribution()
