import base64
from io import BytesIO

from odoo import _, models
from odoo.exceptions import UserError


class L10nBrFiscalDfeDocument(models.Model):
    _inherit = "l10n_br_fiscal_dfe.document"

    def import_document(self):
        if self.fiscal_type != "cte":
            return super().import_document()

        complete = self.dfe_ids.filtered(lambda d: d.document_type_dfe == "complete")[
            :1
        ]
        if not complete:
            raise UserError(_("Can only import Complete CT-e."))

        xml_bytes = base64.b64decode(complete.attachment_id.datas)
        return self.company_id.parse_procCTe(BytesIO(xml_bytes))

    def make_pdf(self):
        if self.fiscal_type != "cte":
            return super().make_pdf()

        # Placeholder: If you have a CT-e report generator similar to brazilfiscalreport
        # implementation would go here. For now, we rely on the imported document's
        # make_pdf capability if available, or raise error.

        # If the fiscal document is already imported, try to use its mechanism
        fiscal_doc = self.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", self.access_key)], limit=1
        )
        if fiscal_doc:
            return fiscal_doc.make_pdf()

        raise UserError(
            _(
                "DACTE generation directly from XML is not yet implemented. Please import the document first."
            )
        )
