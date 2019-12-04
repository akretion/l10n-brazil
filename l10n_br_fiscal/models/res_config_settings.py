# Copyright (C) 2015  Luis Felipe Miléo - KMEE <mileo@kmee.com.br>
# Copyright (C) 2019  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ibpt_api = fields.Boolean(
        string="Use IBPT API", related="company_id.ibpt_api", readonly=False
    )

    ibpt_token = fields.Char(
        string="IBPT Token", related="company_id.ibpt_token", readonly=False
    )

    ibpt_update_days = fields.Integer(
        string="IBPT Update", related="company_id.ibpt_update_days", readonly=False
    )

    cert_expired_alert = fields.Integer(
        string="Certificate Expired Alert",
        config_parameter="l10n_br_fiscal_cert_expired_alert",
        required=True,
        default=30,
    )
