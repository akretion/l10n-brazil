# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# Copyright (C) 2014  KMEE - www.kmee.com.br
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    CANCELADO, SITUACAO_FISCAL_CANCELADO_EXTEMPORANEO,
    SITUACAO_EDOC_CANCELADA, SITUACAO_FISCAL_CANCELADO,
)


class DocumentCancel(models.Model):
    _name = "l10n_br_fiscal.document.cancel"
    _inherit = "l10n_br_fiscal.event.abstract"
    _description = "Fiscal Document Cancel Record"

    cancel_document_event_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.document.event",
        inverse_name="cancel_document_event_id",
        string=u"Eventos",
    )

    @api.multi
    def cancel_document(self, event_id):
        for record in self:
            if not record.document_id or not record.justificative:
                continue

            processador = record.document_id._processador()

            evento = processador.cancela_documento(
                chave=record.document_id.key[3:],
                protocolo_autorizacao=
                record.document_id.protocolo_autorizacao,
                justificativa=record.justificative
            )
            processo = processador.enviar_lote_evento(
                lista_eventos=[evento]
            )

            for retevento in processo.resposta.retEvento:
                if not retevento.infEvento.chNFe == \
                       record.document_id.key[3:]:
                    continue

                if retevento.infEvento.cStat not in CANCELADO:
                    mensagem = 'Erro no cancelamento'
                    mensagem += '\nCódigo: ' + \
                                retevento.infEvento.cStat
                    mensagem += '\nMotivo: ' + \
                                retevento.infEvento.xMotivo
                    raise UserError(mensagem)

                if retevento.infEvento.cStat == '155':
                    record.document_id.state_fiscal = \
                        SITUACAO_FISCAL_CANCELADO_EXTEMPORANEO
                    record.document_id.state_edoc = SITUACAO_EDOC_CANCELADA
                elif retevento.infEvento.cStat == '135':
                    record.document_id.state_fiscal = \
                        SITUACAO_FISCAL_CANCELADO
                    record.document_id.state_edoc = SITUACAO_EDOC_CANCELADA

                event_id.write({
                    'file_sent': processo.envio_xml,
                    'file_returned': processo.retorno.content,
                    'status': retevento.infEvento.cStat,
                    'message': retevento.infEvento.xMotivo,
                    'state': 'done',
                })
