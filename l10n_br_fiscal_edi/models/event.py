# Copyright (C) 2025  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class Event(models.Model):
    _name = "l10n_br_fiscal.event"
    _inherit = "l10n_br_fiscal.data.abstract"
    _description = "Generic Fiscal Event"

    name = fields.Char(required=True, index=True)

    description = fields.Text(required=True, index=True)

    event_type = fields.Selection(
        selection=[
            ("issuer", "Recorded by the Issuer"),
            ("recipient", "Recorded by Recipient"),
            ("fisco", "Registered by the Issuer Tax Authorities"),
            ("propagation", "Propagation from Events Recorded by Other Documents"),
            ("other", "Registered by the Issuer Tax Authorities"),
        ]
    )

    document_type_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.document.type",
        relation="fiscal_document_type_event_rel",
        column1="event_id",
        column2="document_type_id",
        string="Document Type",
    )

    service_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service",
        string="Service",
        # required=True,
    )

    event_message_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.service.message",
        relation="fiscal_event_service_message_rel",
        column1="event_id",
        column2="service_message_id",
        string="Event Message",
    )
