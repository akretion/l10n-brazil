# Copyright 2019 Akretion (Raphaël Valyi <raphael.valyi@akretion.com>)
# Copyright 2019 KMEE INFORMATICA LTDA
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields

from odoo.addons.spec_driven_model.models import spec_models

from ..constants.nfe import (
    NFE_ENVIRONMENT_DEFAULT,
    NFE_ENVIRONMENTS,
    NFE_VERSION_DEFAULT,
    NFE_VERSIONS,
)

PROCESSADOR_ERPBRASIL_EDOC = 'erpbrasil_edoc'
PROCESSADOR = [(PROCESSADOR_ERPBRASIL_EDOC, 'erpbrasil.edoc')]


class ResCompany(spec_models.SpecModel):
    _inherit = 'res.company'
    _nfe_search_keys = ['nfe40_CNPJ', 'nfe40_xNome', 'nfe40_xFant']

    processador_edoc = fields.Selection(
        selection_add=PROCESSADOR,
    )

    nfe_version = fields.Selection(
        selection=NFE_VERSIONS,
        string='NFe Version',
        default=NFE_VERSION_DEFAULT,
    )

    nfe_environment = fields.Selection(
        selection=NFE_ENVIRONMENTS,
        string='NFe Environment',
        default=NFE_ENVIRONMENT_DEFAULT,
    )

    nfe_default_serie_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.document.serie',
        string='NF-e Default Serie',
    )

    @api.model
    def _prepare_import_dict(self, values, defaults={}):
        values = super()._prepare_import_dict(values)
        if not values.get('name'):
            values['name'] = (values.get('nfe40_xFant') or
                              values.get('nfe40_xNome'))
        return values
