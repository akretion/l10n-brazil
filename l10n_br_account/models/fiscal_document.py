# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import SITUACAO_EDOC_EM_DIGITACAO


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    move_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="fiscal_document_id",
        string="Invoices",
    )

    fiscal_partner_id = fields.Many2one(related="partner_id")
    fiscal_company_id = fields.Many2one(related="company_id")
    fiscal_currency_id = fields.Many2one(related="currency_id")
    fiscal_partner_shipping_id = fields.Many2one(related="partner_shipping_id")
    fiscal_user_id = fields.Many2one(related="user_id")

    def write(self, vals):
        if self.document_type_id:
            return super().write(vals)

    def modified(self, fnames, create=False, before=False):
        """
        Modifying a dummy fiscal document (no document_type_id) should not recompute
        any account.move related to the same dummy fiscal document.
        """
        filtered = self.filtered(
            lambda rec: isinstance(rec.id, models.NewId) or rec.document_type_id
        )
        return super(FiscalDocument, filtered).modified(fnames, create, before)

    def _modified_triggers(self, tree, create=False):
        """
        Modifying a dummy fiscal document (no document_type_id) should not recompute
        any account.move related to the same dummy fiscal document.
        """
        filtered = self.filtered(
            lambda rec: isinstance(rec.id, models.NewId) or rec.document_type_id
        )
        return super(FiscalDocument, filtered)._modified_triggers(tree, create)

    fiscal_line_ids = fields.One2many(
        copy=False,
    )

    def unlink(self):
        non_draft_documents = self.filtered(
            lambda d: d.state != SITUACAO_EDOC_EM_DIGITACAO
        )

        if non_draft_documents:
            UserError(
                _("You cannot delete a fiscal document " "which is not draft state.")
            )
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        # OVERRIDE
        # force creation of fiscal_document_line only when creating an AML record
        # In order not to affect the creation of the dummy document, a test was included
        # that verifies that the ACTIVE field is not False. As the main characteristic
        # of the dummy document is the ACTIVE field is False
        for values in vals_list:
            if values.get("fiscal_line_ids") and values.get("active") is not False:
                values.update({"fiscal_line_ids": False})
        return super().create(vals_list)
