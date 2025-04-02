# Copyright (C) 2025  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class ServiceMessage(models.Model):
    _name = "l10n_br_fiscal.service.message"
    _inherit = "l10n_br_fiscal.data.abstract"
    _description = "Generic Fiscal Service Message"

    name = fields.Char(required=True, index=True)

    description = fields.Text(required=True, index=True)

    service_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service",
        string="Fiscal Service",
    )

    document_type_id = fields.Many2one(
        related="service_id.document_type_id",
        string="Document Type",
    )

    message_type = fields.Selection(
        selection=[("request", "Request"), ("response", "Response")],
        string="Message Type",
    )
