# Copyright (C) 2025  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class DocumentType(models.Model):
    _inherit = "l10n_br_fiscal.document.type"

    service_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.service",
        relation="fiscal_document_type_service_rel",
        column1="document_type_id",
        column2="service_id",
        string="Document Service",
    )

    event_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.event",
        relation="fiscal_document_type_event_rel",
        column1="document_type_id",
        column2="event_id",
        string="Document Event",
    )
