# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# Copyright (C) 2014  KMEE - www.kmee.com.br
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import logging

from odoo import _, api, fields, models

# from odoo.l10n_br_fiscal.constants.fiscal import EVENT_ENVIRONMENT
# from ..tools.misc import build_edoc_path

_logger = logging.getLogger(__name__)

# TODO remove
# FILE_SUFIX_EVENT = {
#     "0": "env",
#     "1": "con-rec",
#     "2": "can",
#     "3": "inu",
#     "4": "con-edoc",
#     "5": "con-status",
#     "6": "con-cad",
#     "7": "dpec-rec",
#     "8": "dpec-con",
#     "9": "rec-eve",
#     "10": "dow",
#     "11": "con-dest",
#     "12": "dist-dfe",
#     "13": "man",
#     "14": "cce",
# }


class DocumentEvent(models.Model):
    _name = "l10n_br_fiscal.document.event"
    _description = "Generic Fiscal Document Event"

    @api.depends("document_id.name", "invalidate_number_id.name")
    def _compute_display_name(self):
        for record in self:
            if record.document_id:
                names = [
                    _("Fiscal Document"),
                    record.document_id.name,
                ]
                record.display_name = " / ".join(filter(None, names))
            elif record.invalidate_number_id:
                names = [
                    _("Invalidate Number"),
                    record.invalidate_number_id.name,
                ]
                record.display_name = " / ".join(filter(None, names))
            else:
                record.display_name = ""

    document_type_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.type",
        string="Document Type",
        index=True,
        required=True,
    )

    document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document",
        string="Fiscal Document",
        domain="[('document_type_id', '=', document_type_id)]",
        index=True,
    )

    document_event_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.event",
        string="Document Event",
        index=True,
    )

    invalidate_number_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.invalidate.number",
        string="Invalidate Number",
        index=True,
    )

    # TODO precisa ter a empresa no evento, não pode ser um related do documento fiscal
    # Porque pode estar ligado a uma sequencia de invalidação
    company_id = fields.Many2one(comodel_name="res.company")

    sequence = fields.Char(
        help="Fiscal Document Event Sequence",
    )

    # TODO Precisa deixar esse campo no evento?
    # Poderia estar só no wizard já que no evento
    # tem esse campo na resposta do evento
    justification = fields.Char()

    display_name = fields.Char(
        string="name",
        compute="_compute_display_name",
        store=True,
    )

    event_transmission_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.event.transmission",
        string="Event Transmition",
    )

    message_response_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service.message",
        string="Message Response",
        domain="[('message_type', '=', 'response')]",
    )

    service_response_signed = fields.Text(string="Service Response Signed")

    response_status_code = fields.Char(string="Status Code")

    response_status_description = fields.Char(string="Status Description")

    response_receipt_number = fields.Char(string="Receipt Number")

    response_receipt_date = fields.Datetime(string="Receipt Date")

    response_message_code = fields.Char(string="Message Code")

    response_message_description = fields.Char(string="Message Description")
