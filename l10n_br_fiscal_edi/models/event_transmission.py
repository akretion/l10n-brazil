# Copyright (C) 2025  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class EventTransmission(models.Model):
    _name = "l10n_br_fiscal.event.transmission"
    _description = "Generic Fiscal Document Event Transmission"

    document_type_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.type",
        string="Document Event",
    )

    event_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.event",
        string="Fiscal Document",
        index=True,
    )

    service_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service",
        string="Document Service",
        domain="[('document_type_id', '=', document_type_id)]",
    )

    document_service_code = fields.Char(
        # related="service_id.code",
        string="Document Service Code"
    )

    document_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.document",
        relation="document_event_transmission_rel",
        column1="event_transmission_id",
        column2="document_id",
        readonly=True,
        string="Documents",
    )

    # Campos com informações de Envio

    message_request_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service.message",
        string="Message Request",
        domain="[('service_id', '=', service_id)," "('message_type', '=', 'request')]",
    )

    message_request_code = fields.Char(
        related="message_request_id.code", string="Message Request Code"
    )

    service_request = fields.Text(string="Service Request")

    service_request_signed = fields.Text(string="Service Request Signed")

    # Campos com informações de retorno

    message_response_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.message",
        string="Message Response",
        domain="[('service_id', '=', service_id)," "('message_type', '=', 'response')]",
    )

    message_response_code = fields.Char(
        # related="message_response_id.code",
    )

    service_response = fields.Text(string="Service Response")

    service_response_signed = fields.Text(string="Service Response Signed")

    response_status_code = fields.Char(string="Status Code")

    response_status_description = fields.Char(string="Status Description")

    response_receipt_number = fields.Char(string="Receipt Number")

    response_receipt_date = fields.Datetime(string="Receipt Date")

    response_message_code = fields.Char(string="Message Code")

    response_message_description = fields.Char(string="Message Description")

    state = fields.Selection(
        selection=[("todo", "To Do"), ("done", "Done")],
        string="State",
        default="todo",
    )

    # TODO incluir um campo calculado para dizer baseado no status se a transmissão
    # deu certo ou não

    def _service_request_sign(self):
        """Assina a mensagem de envio e grava no campo service_request_signed"""
        pass

    def action_event_send(self):
        """Executa a transmissão e cria um evento deve estar em uma unica transação"""
        pass
