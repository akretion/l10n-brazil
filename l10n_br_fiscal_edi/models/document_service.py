# Copyright (C) 2022  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class DocumentService(models.Model):
    _name = "l10n_br_fiscal.document.service"
    _inherit = [
        "l10n_br_fiscal.data.abstract",
        "mail.thread",
        "mail.activity.mixin",
    ]
    _description = "Generic Document Service"

    name = fields.Char(required=True, index=True)

    description = fields.Text(required=True, index=True)

    document_type_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.document.type",
        relation="fiscal_document_type_service_rel",
        column1="document_service_id",
        column2="document_type_id",
        string="Document Type",
    )

    document_service_message_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.document.service.message",
        inverse_name="document_service_id",
        string="Document Service Message"
    )
