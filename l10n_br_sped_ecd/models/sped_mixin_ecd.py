# Copyright 2023 - TODAY, Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).
# Generated by https://github.com/akretion/sped-extractor and xsdata-odoo

from odoo import fields, models


class SpecMixinECD(models.AbstractModel):
    _name = "l10n_br_sped.mixin.ecd"
    _description = "l10n_br_sped.mixin.ecd"
    _inherit = "l10n_br_sped.mixin"

    declaration_id = fields.Many2one(
        comodel_name="l10n_br_sped.ecd.0000",
        required=True,
    )

    state = fields.Selection(related="declaration_id.state")
