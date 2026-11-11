# Copyright 2023 KMEE
# Copyright 2024 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields
from odoo.exceptions import ValidationError

from odoo.addons.spec_driven_model.models import spec_models

# Max length of the Comp/xNome tag of the CT-e leiaute.
# The leiaute documents it with component labels of the freight price
# ("FRETE PESO", "FRETE VALOR", "SEC/CAT", "ADEME", "AGENDAMENTO"), not with
# the description of the transport service.
CTE_COMP_NAME_SIZE = 15

# Label declared when the line does not carry one: what a CT-e of a single
# freight component has always declared here.
CTE_COMP_DEFAULT_NAME = "Frete"


class CTeLine(spec_models.StackedModel):
    _name = "l10n_br_fiscal.document.line"
    _inherit = ["l10n_br_fiscal.document.line", "cte.40.tcte_vprest_comp"]

    _cte40_odoo_module = (
        "odoo.addons.l10n_br_cte_spec.models.v4_0.cte_tipos_basico_v4_00"
    )
    _cte40_stacking_mixin = "cte.40.tcte_vprest_comp"
    _cte40_stacking_skip_paths = ("cte40_Comp_vPrest_id",)

    ##########################
    # CT-e tag: comp
    ##########################

    # cte40_xNome is the label of the component, not the description of the
    # service: the leiaute caps it at 15 characters and the module validates
    # the CT-e against the schema before sending it, so the fiscal line
    # description used to make any realistic CT-e unsendable.
    cte40_xNome = fields.Char(
        string="Componente do Frete",
        help="Nome do componente do valor da prestação, como FRETE PESO, "
        "FRETE VALOR, SEC/CAT, ADEME ou AGENDAMENTO.\n"
        "Quando vazio, o CT-e declara o componente único 'Frete'.",
    )

    cte40_vComp = fields.Monetary(related="fiscal_amount_total")

    # FIXME ORM/spec_model_driven workaround
    # see https://github.com/OCA/l10n-brazil/pull/3651#issuecomment-2729890350
    cte40_Comp_vPrest_id = fields.Many2one(copy=False)

    @api.constrains("cte40_xNome")
    def _check_cte40_xNome(self):
        for record in self.filtered("cte40_xNome"):
            if len(record.cte40_xNome) > CTE_COMP_NAME_SIZE:
                raise ValidationError(
                    _(
                        "O componente do frete é limitado a %(size)s caracteres "
                        "pelo leiaute do CT-e: %(name)s",
                        size=CTE_COMP_NAME_SIZE,
                        name=record.cte40_xNome,
                    )
                )

    def _export_fields_cte_40_tcte_vprest_comp(
        self, xsd_fields, class_obj, export_dict
    ):
        """Declare the component label, falling back to a single freight.

        The CT-e of a carrier that does not itemize its price declares one
        component holding the whole vTPrest, labelled "Frete"; the leiaute
        caps the label at 15 characters, so the service description of the
        line can never be used here.
        """
        if "cte40_xNome" in xsd_fields:
            xsd_fields.remove("cte40_xNome")
        export_dict["xNome"] = self.cte40_xNome or CTE_COMP_DEFAULT_NAME
