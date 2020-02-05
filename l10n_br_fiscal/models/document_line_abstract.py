# Copyright (C) 2019  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models
from odoo.addons import decimal_precision as dp

from ..constants.fiscal import (CFOP_DESTINATION_EXPORT, FISCAL_IN,
                                FISCAL_IN_OUT, FISCAL_OUT, NCM_FOR_SERVICE_REF,
                                PRODUCT_FISCAL_TYPE,
                                PRODUCT_FISCAL_TYPE_SERVICE, TAX_BASE_TYPE,
                                TAX_BASE_TYPE_PERCENT, TAX_DOMAIN_COFINS,
                                TAX_DOMAIN_ICMS, TAX_DOMAIN_ICMS_SN,
                                TAX_DOMAIN_IPI, TAX_DOMAIN_PIS,
                                TAX_FRAMEWORK,
                                TAX_FRAMEWORK_NORMAL,
                                TAX_FRAMEWORK_SIMPLES_ALL)


class DocumentLineAbstract(models.AbstractModel):
    _name = "l10n_br_fiscal.document.line.abstract"
    _inherit = "l10n_br_fiscal.document.line.mixin"
    _description = "Fiscal Document Line Abstract"

    @api.one
    @api.depends(
        "price",
        "discount",
        "quantity",
        "product_id",
        "document_id.partner_id",
        "document_id.company_id",
    )
    def _compute_amount(self):
        round_curr = self.document_id.currency_id.round
        self.amount_untaxed = round_curr(self.price * self.quantity)
        self.amount_tax = 0.00
        self.amount_total = (self.amount_untaxed + self.amount_tax -
                             self.discount)

    # TODO REMOVE
    @api.model
    def default_get(self, fields):
        defaults = super(DocumentLineAbstract, self).default_get(fields)
        if self.env.context.get("default_company_id"):
            company_id = self.env.context.get("default_company_id")
            operation_type = self.env.context.get("default_operation_type")
            # taxes_dict = self._set_default_taxes(company_id, operation_type)
            # defaults.update(taxes_dict)
        return defaults

    @api.model
    def _get_default_ncm_id(self):
        fiscal_type = self.env.context.get("default_fiscal_type")
        if fiscal_type == PRODUCT_FISCAL_TYPE_SERVICE:
            ncm_id = self.env.ref(NCM_FOR_SERVICE_REF)
            return ncm_id

    # used mostly to enable _inherits of account.invoice on fiscal_document
    # when existing invoices have no fiscal document.
    active = fields.Boolean(string="Active", default=True)

    name = fields.Text(string="Name")

    document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.abstract", string="Document"
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        related="document_id.company_id",
        store=True,
        string="Company",
    )

    tax_framework = fields.Selection(
        selection=TAX_FRAMEWORK,
        related="company_id.tax_framework",
        string="Tax Framework")

    partner_id = fields.Many2one(
        comodel_name="res.partner", related="document_id.partner_id", string="Partner"
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency", related="company_id.currency_id", string="Currency"
    )

    product_id = fields.Many2one(comodel_name="product.product", string="Product")

    uom_id = fields.Many2one(comodel_name="uom.uom", string="UOM")

    quantity = fields.Float(
        string="Quantity", digits=dp.get_precision("Product Unit of Measure")
    )

    price = fields.Float(string="Price Unit", digits=dp.get_precision("Product Price"))

    uot_id = fields.Many2one(comodel_name="uom.uom", string="Tax UoM")

    discount = fields.Monetary(string="Discount")

    fiscal_type = fields.Selection(selection=PRODUCT_FISCAL_TYPE, string="Fiscal Type")

    fiscal_genre_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.product.genre", string="Fiscal Genre"
    )

    ncm_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.ncm",
        index=True,
        default=_get_default_ncm_id,
        string="NCM",
    )

    cest_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.cest",
        index=True,
        string="CEST",
        domain="[('ncm_ids', '=', ncm_id)]",
    )

    nbs_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.nbs", index=True, string="NBS"
    )

    service_type_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service.type",
        string="Service Type",
        domain="[('internal_type', '=', 'normal')]",
    )

    notes = fields.Text(string="Notes")

    # Amount Fields
    amount_estimate_tax = fields.Monetary(string="Amount Estimate Total", compute="_compute_amount", default=0.00)

    amount_untaxed = fields.Monetary(string="Amount Untaxed", compute="_compute_amount", default=0.00)

    amount_tax = fields.Monetary(string="Amount Tax", compute="_compute_amount", default=0.00)

    amount_total = fields.Monetary(string="Amount Total", compute="_compute_amount", default=0.00)

    # TODO REMOVE
    def _set_default_taxes(self, company_id, operation_type=FISCAL_OUT):
        company = self.env["res.company"].browse(company_id)
        defaults = {}
        if not self.env.context.get("default_operation_type") == FISCAL_OUT:
            return defaults

        for tax_def in company.tax_definition_ids:
            # Default ICMS SN
            if tax_def.tax_group_id.tax_domain == TAX_DOMAIN_ICMS_SN:
                if company.tax_framework in TAX_FRAMEWORK_SIMPLES_ALL:
                    defaults["icmssn_tax_id"] = tax_def.tax_id.id
                    defaults["icmssn_cst_id"] = tax_def.tax_id.cst_from_tax(
                        operation_type
                    ).id

            # Default ICMS
            if tax_def.tax_group_id.tax_domain == TAX_DOMAIN_ICMS:
                if company.tax_framework == TAX_FRAMEWORK_NORMAL:
                    defaults["icms_tax_id"] = tax_def.tax_id.id
                    defaults["icms_cst_id"] = tax_def.tax_id.cst_from_tax(
                        operation_type
                    ).id

            # Default IPI
            if tax_def.tax_group_id.tax_domain == TAX_DOMAIN_IPI:
                if company.tax_framework in TAX_FRAMEWORK_SIMPLES_ALL:
                    defaults["ipi_tax_id"] = tax_def.tax_id.id
                    defaults["ipi_cst_id"] = tax_def.tax_id.cst_from_tax(
                        operation_type
                    ).id

            if company.tax_framework == TAX_FRAMEWORK_NORMAL and not company.ripi:
                defaults["ipi_tax_id"] = tax_def.tax_id.id
                defaults["ipi_cst_id"] = tax_def.tax_id.cst_from_tax(operation_type).id

            # Default PIS/COFINS
            if tax_def.tax_group_id.tax_domain == TAX_DOMAIN_PIS:
                defaults["pis_tax_id"] = tax_def.tax_id.id
                defaults["pis_cst_id"] = tax_def.tax_id.cst_from_tax(operation_type).id

            if tax_def.tax_group_id.tax_domain == TAX_DOMAIN_COFINS:
                defaults["cofins_tax_id"] = tax_def.tax_id.id
                defaults["cofins_cst_id"] = tax_def.tax_id.cst_from_tax(
                    operation_type
                ).id

        return defaults

    def _compute_taxes(self, taxes, cst=None):
        return taxes.compute_taxes(
            company=self.company_id,
            partner=self.partner_id,
            item=self.product_id,
            prince=self.price,
            quantity=self.quantity,
            uom_id=self.uom_id,
            fiscal_price=self.fiscal_price,
            fiscal_quantity=self.fiscal_quantity,
            uot_id=self.uot_id,
            ncm=self.ncm_id,
            cest=self.cest_id,
            operation_type=self.operation_type,
        )

    @api.multi
    def compute_taxes(self):

        result_taxes = super(DocumentLineAbstract, self).compute_taxes()

        for line in self:
            taxes = self.env["l10n_br_fiscal.tax"]

            # Compute all taxes
            taxes |= (
                line.icms_tax_id
                + line.icmssn_tax_id
                + line.ipi_tax_id
                + line.pis_tax_id
                + line.pisst_tax_id
                + line.cofins_tax_id
                + line.cofinsst_tax_id
            )

            result_taxes = line._compute_taxes(taxes)
            # TODO populate field taxes
        return result_taxes

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            self.ncm_id = self.product_id.ncm_id
            self.cest_id = self.product_id.cest_id
            self.nbs_id = self.product_id.nbs_id
            self.uot_id = self.product_id.uot_id or self.product_id.uom_id

        self._onchange_operation_id()

    @api.onchange("operation_id")
    def _onchange_operation_id(self):

        super(DocumentLineAbstract, self)._onchange_operation_id()

        if not self.operation_id:
            self.operation_id = self.document_id.operation_id

            if self.operation_line_id:
                if self.partner_id.state_id == self.company_id.state_id:
                    self.cfop_id = self.operation_line_id.cfop_internal_id
                elif self.partner_id.state_id != self.company_id.state_id:
                    self.cfop_id = self.operation_line_id.cfop_external_id
                elif self.partner_id.country_id != self.company_id.country_id:
                    self.cfop_id = self.operation_line_id.cfop_export_id

    @api.onchange("uot_id", "uom_id", "price", "quantity")
    def _onchange_commercial_quantity(self):
        if self.uom_id == self.uot_id:
            self.fiscal_price = self.price
            self.fiscal_quantity = self.quantity

        if self.uom_id != self.uot_id:
            self.fiscal_price = self.price / self.product_id.uot_factor
            self.fiscal_quantity = self.quantity * self.product_id.uot_factor

    @api.onchange("ncm_id", "nbs_id", "cest_id")
    def _onchange_ncm_id(self):
        if self.ncm_id:
            # Get IPI from NCM
            if self.company_id.ripi:
                self.ipi_tax_id = self.ncm_id.tax_ipi_id

            # Get II from NCM but only comming from other country
            if (
                self.cfop_id.destination == CFOP_DESTINATION_EXPORT
                and self.operation_type == FISCAL_IN
            ):
                self.ii_tax_id = self.ncm_id.tax_ii_id

            # TODO cest_id compute ICMS ST

            # TODO nbs_id compute ISSQN
