# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# Copyright (C) 2019 - TODAY Raphaël Valyi - Akretion
# Copyright (C) 2020 - TODAY Luis Felipe Mileo - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
# pylint: disable=api-one-deprecated

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_ISSUER_COMPANY,
    DOCUMENT_ISSUER_PARTNER,
    FISCAL_OUT,
    SITUACAO_EDOC_CANCELADA,
    SITUACAO_EDOC_EM_DIGITACAO,
)

INVOICE_TO_OPERATION = {
    "out_invoice": "out",
    "in_invoice": "in",
    "out_refund": "in",
    "in_refund": "out",
}

REFUND_TO_OPERATION = {
    "out_invoice": "in",
    "in_invoice": "out",
    "out_refund": "out",
    "in_refund": "in",
}

FISCAL_TYPE_REFUND = {
    "out": ["purchase_refund", "in_return"],
    "in": ["sale_refund", "out_return"],
}

INVOICE_TAX_USER_TYPE = {
    "out_invoice": "sale",
    "in_invoice": "purchase",
    "out_refund": "sale",
    "in_refund": "purchase",
}

SHADOWED_FIELDS = [
    "partner_id",
    "company_id",
    "currency_id",
    "partner_shipping_id",
    "user_id",
]


class AccountInvoice(models.Model):
    _name = "account.invoice"
    _inherit = [
        _name,
        "l10n_br_fiscal.document.mixin.methods",
        "l10n_br_fiscal.document.invoice.mixin",
    ]
    _inherits = {"l10n_br_fiscal.document": "fiscal_document_id"}
    _order = "date_invoice DESC, number DESC"

    # initial account.invoice inherits on fiscal.document that are
    # disable with active=False in their fiscal_document table.
    # To make these invoices still visible, we set active=True
    # in the invoice table.
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    cnpj_cpf = fields.Char(
        string="CNPJ/CPF",
        related="partner_id.cnpj_cpf",
    )

    legal_name = fields.Char(
        string="Adapted Legal Name",
        related="partner_id.legal_name",
    )

    ie = fields.Char(
        string="Adapted State Tax Number",
        related="partner_id.inscr_est",
    )

    document_electronic = fields.Boolean(
        related="document_type_id.electronic",
        string="Electronic?",
    )

    # this default should be overwritten to False in a module pretending to
    # create fiscal documents from the invoices. But this default here
    # allows to install the l10n_br_account module without creating issues
    # with the existing Odoo invoice (demo or not).
    fiscal_document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document",
        string="Fiscal Document",
        required=True,
        copy=False,
        ondelete="cascade",
    )

    document_type = fields.Char(
        related="document_type_id.code",
        store=True,
    )

    withholding_invoice_ids = fields.Many2many(
        comodel_name="account.invoice",
        relation="account_invoice_withholding_invoice_rel",
        column1="invoice_id",
        column2="withholding_invoice_id",
        compute="_compute_withholding_invoice_ids",
        store=True,
        string="Withholding Invoice",
    )

    withholding_origin_ids = fields.Many2many(
        comodel_name="account.invoice",
        relation="account_invoice_withholding_invoice_rel",
        column1="withholding_invoice_id",
        column2="invoice_id",
        compute="_compute_withholding_invoice_ids",
        store=True,
        string="Withholding Origin Invoice",
    )

    @api.depends("move_id.line_ids")
    def _compute_withholding_invoice_ids(self):
        for invoice in self.filtered(lambda i: i.move_id):
            invoices = (
                self.env["account.invoice.line"]
                .search(
                    [("wh_move_line_id", "in", invoice.move_id.mapped("line_ids").ids)]
                )
                .mapped("invoice_id")
            )
            invoice.withholding_invoice_ids = invoices

    def _get_amount_lines(self):
        """Get object lines instaces used to compute fields"""
        return self.mapped("invoice_line_ids")

    @api.model
    def _shadowed_fields(self):
        """Returns the list of shadowed fields that are synced
        from the parent."""
        return SHADOWED_FIELDS

    def _prepare_shadowed_fields_dict(self, default=False):
        self.ensure_one()
        vals = self._convert_to_write(self.read(self._shadowed_fields())[0])
        if default:  # in case you want to use new rather than write later
            return {"default_%s" % (k,): vals[k] for k in vals.keys()}
        return vals

    def _write_shadowed_fields(self):
        for invoice in self:
            if invoice.document_type_id:
                shadowed_fiscal_vals = invoice._prepare_shadowed_fields_dict()
                invoice.fiscal_document_id.write(shadowed_fiscal_vals)

    @api.model
    def fields_view_get(
        self, view_id=None, view_type="form", toolbar=False, submenu=False
    ):

        order_view = super().fields_view_get(view_id, view_type, toolbar, submenu)

        if view_type == "form":
            view = self.env["ir.ui.view"]

            if view_id == self.env.ref("l10n_br_account.fiscal_invoice_form").id:
                invoice_line_form_id = self.env.ref(
                    "l10n_br_account.fiscal_invoice_line_form"
                ).id
            else:
                invoice_line_form_id = self.env.ref(
                    "l10n_br_account.invoice_line_form"
                ).id

            sub_form_view = self.env["account.invoice.line"].fields_view_get(
                view_id=invoice_line_form_id, view_type="form"
            )["arch"]

            sub_form_node = etree.fromstring(
                self.env["account.invoice.line"].fiscal_form_view(sub_form_view)
            )

            sub_arch, sub_fields = view.postprocess_and_fields(
                "account.invoice.line", sub_form_node, None
            )

            order_view["fields"]["invoice_line_ids"]["views"]["form"] = {}

            order_view["fields"]["invoice_line_ids"]["views"]["form"][
                "fields"
            ] = sub_fields
            order_view["fields"]["invoice_line_ids"]["views"]["form"]["arch"] = sub_arch

        return order_view

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        invoice_type = self.env.context.get("type", "out_invoice")
        defaults["fiscal_operation_type"] = INVOICE_TO_OPERATION[invoice_type]
        if defaults["fiscal_operation_type"] == FISCAL_OUT:
            defaults["issuer"] = DOCUMENT_ISSUER_COMPANY
        else:
            defaults["issuer"] = DOCUMENT_ISSUER_PARTNER
        return defaults

    @api.model
    def create(self, values):
        if not values.get("document_type_id"):
            values.update(
                {"fiscal_document_id": self.env.user.company_id.fiscal_dummy_id.id}
            )
            # to avoid bug 2) of https://github.com/OCA/l10n-brazil/issues/1813
            # we use a context key to avoid recomputing all invoices
            # linked to a dummy fiscal document
            recompute_inv_after_id = self.search([], order="id DESC", limit=1).id
            invoice = super(
                AccountInvoice,
                self.with_context(recompute_inv_after_id=recompute_inv_after_id),
            ).create(values)
        else:
            invoice = super().create(values)
        invoice._write_shadowed_fields()
        invoice.compute_taxes()
        return invoice

    def _recompute_todo(self, field):
        # overriden to avoid bug 2 of https://github.com/OCA/l10n-brazil/issues/1813
        if self._context.get("recompute_inv_after_id"):
            return self.env.add_todo(
                field,
                self.filtered(
                    lambda rec: rec.id > self._context["recompute_inv_after_id"]
                ),
            )
        else:
            return super()._recompute_todo(field)

    def write(self, values):
        result = super().write(values)
        self._write_shadowed_fields()
        return result

    def unlink(self):
        """Allows delete a draft or cancelled invoices"""
        self.filtered(lambda i: i.state in ("draft", "cancel")).write(
            {"move_name": False}
        )
        unlink_invoices = self.env["account.invoice"]
        unlink_documents = self.env["l10n_br_fiscal.document"]
        for invoice in self:
            if not invoice.exists():
                continue
            if (
                invoice.fiscal_document_id
                and invoice.fiscal_document_id.id
                != self.env.user.company_id.fiscal_dummy_id.id
            ):
                unlink_documents |= invoice.fiscal_document_id
            unlink_invoices |= invoice
        result = super(AccountInvoice, unlink_invoices).unlink()
        unlink_documents.unlink()
        self.clear_caches()
        return result

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        if self.document_type_id:
            default["line_ids"] = False
        else:
            default["line_ids"] = self.line_ids[0]
        return super().copy(default)

    @api.one
    @api.depends(
        "invoice_line_ids",
        "currency_id",
        "company_id",
        "date_invoice",
        "type",
    )
    def _compute_amount(self):
        inv_lines = self.invoice_line_ids.filtered(
            lambda l: not l.fiscal_operation_line_id
            or l.fiscal_operation_line_id.add_to_amount
        )
        for inv_line in inv_lines:
            if inv_line.cfop_id:
                if inv_line.cfop_id.finance_move:
                    self.amount_untaxed += inv_line.price_subtotal
                    self.amount_tax += inv_line.price_tax
                    self.amount_total += inv_line.price_total
            else:
                self.amount_untaxed += inv_line.price_subtotal
                self.amount_tax += inv_line.price_tax
                self.amount_total += inv_line.price_total

        self.amount_total -= self.amount_tax_withholding

        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if (
            self.currency_id
            and self.company_id
            and self.currency_id != self.company_id.currency_id
        ):
            currency_id = self.currency_id
            amount_total_company_signed = currency_id._convert(
                self.amount_total,
                self.company_id.currency_id,
                self.company_id,
                self.date_invoice or fields.Date.today(),
            )
            amount_untaxed_signed = currency_id._convert(
                self.amount_untaxed,
                self.company_id.currency_id,
                self.company_id,
                self.date_invoice or fields.Date.today(),
            )
        sign = self.type in ["in_refund", "out_refund"] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign

    @api.model
    def invoice_line_move_line_get(self):
        move_lines_dict = super().invoice_line_move_line_get()
        new_mv_lines_dict = []
        for line in move_lines_dict:
            invoice_line = self.invoice_line_ids.filtered(
                lambda l: l.id == line.get("invl_id")
            )

            if invoice_line.fiscal_operation_id:
                if invoice_line.fiscal_operation_id.deductible_taxes:
                    line["price"] = invoice_line.price_total
                else:
                    line["price"] = invoice_line.price_total - (
                        invoice_line.amount_tax_withholding
                        + invoice_line.amount_tax_included
                    )

            if invoice_line.cfop_id:
                if invoice_line.cfop_id.finance_move:
                    new_mv_lines_dict.append(line)
            else:
                new_mv_lines_dict.append(line)

        return new_mv_lines_dict

    @api.model
    def tax_line_move_line_get(self):
        tax_lines_dict = super().tax_line_move_line_get()
        if self.fiscal_operation_id and self.fiscal_operation_id.deductible_taxes:
            for tax_line in self.tax_line_ids:
                analytic_tag_ids = [
                    (4, analytic_tag.id, None)
                    for analytic_tag in tax_line.analytic_tag_ids
                ]

                deductible_tax = tax_line.tax_id.tax_group_id.deductible_tax(
                    INVOICE_TAX_USER_TYPE[self.type]
                )

                if deductible_tax:
                    account = deductible_tax.account_id or tax_line.account_id
                    tax_line_vals = {
                        "invoice_tax_line_id": tax_line.id,
                        "tax_line_id": tax_line.tax_id.id,
                        "type": "tax",
                        "name": tax_line.name or deductible_tax.name,
                        "price_unit": tax_line.amount_total * -1,
                        "quantity": 1,
                        "price": tax_line.amount_total * -1,
                        "account_id": account.id,
                        "account_analytic_id": tax_line.account_analytic_id.id,
                        "analytic_tag_ids": analytic_tag_ids,
                        "invoice_id": self.id,
                    }
                    tax_lines_dict.append(tax_line_vals)

        return tax_lines_dict

    def finalize_invoice_move_lines(self, move_lines):
        lines = super().finalize_invoice_move_lines(move_lines)
        financial_lines = [
            line for line in lines if line[2]["account_id"] == self.account_id.id
        ]

        # É preciso ordernar pela Data de Vencimento para ter as Numeração das Parcelas
        # seguindo essa sequencia, se não fica confuso ter a última Parcela sendo
        # a primeira a ser Paga
        financial_lines.sort(key=lambda l: l[2].get("date_maturity"))

        count = 1

        for line in financial_lines:
            if line[2]["debit"] or line[2]["credit"]:
                if self.document_type_id:
                    line[2]["name"] = "{}/{}-{}".format(
                        self.fiscal_document_id.with_context(
                            fiscal_document_no_company=True
                        )._compute_document_name(),
                        count,
                        len(financial_lines),
                    )
                    count += 1
        return lines

    def get_taxes_values(self):
        tax_grouped = {}
        round_curr = self.currency_id.round
        for line in self.invoice_line_ids:
            if not line.account_id or line.display_type:
                continue

            computed_taxes = line.invoice_line_tax_ids.compute_all(
                price_unit=line.price_unit,
                currency=line.invoice_id.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=line.invoice_id.partner_id,
                fiscal_taxes=line.fiscal_tax_ids,
                operation_line=line.fiscal_operation_line_id,
                ncm=line.ncm_id,
                nbs=line.nbs_id,
                nbm=line.nbm_id,
                cest=line.cest_id,
                discount_value=line.discount_value,
                insurance_value=line.insurance_value,
                other_value=line.other_value,
                freight_value=line.freight_value,
                fiscal_price=line.fiscal_price,
                fiscal_quantity=line.fiscal_quantity,
                uot=line.uot_id,
                icmssn_range=line.icmssn_range_id,
                ind_final=line.ind_final,
            )["taxes"]

            for tax in computed_taxes:
                if tax.get("amount", 0.0) != 0.0:
                    val = self._prepare_tax_line_vals(line, tax)
                    key = (
                        self.env["account.tax"].browse(tax["id"]).get_grouping_key(val)
                    )

                    if key not in tax_grouped:
                        tax_grouped[key] = val
                        tax_grouped[key]["base"] = round_curr(val["base"])
                    else:
                        tax_grouped[key]["amount"] += val["amount"]
                        tax_grouped[key]["base"] += round_curr(val["base"])
        return tax_grouped

    @api.onchange("fiscal_operation_id")
    def _onchange_fiscal_operation_id(self):
        super()._onchange_fiscal_operation_id()
        if self.fiscal_operation_id and self.fiscal_operation_id.journal_id:
            self.journal_id = self.fiscal_operation_id.journal_id

    def open_fiscal_document(self):
        if self.env.context.get("type", "") == "out_invoice":
            action = self.env.ref("l10n_br_account.fiscal_invoice_out_action").read()[0]
        elif self.env.context.get("type", "") == "in_invoice":
            action = self.env.ref("l10n_br_account.fiscal_invoice_in_action").read()[0]
        else:
            action = self.env.ref("l10n_br_account.fiscal_invoice_all_action").read()[0]
        form_view = [(self.env.ref("l10n_br_account.fiscal_invoice_form").id, "form")]
        if "views" in action:
            action["views"] = form_view + [
                (state, view) for state, view in action["views"] if view != "form"
            ]
        else:
            action["views"] = form_view
        action["res_id"] = self.id
        return action

    def open_invoice_document(self):
        self.ensure_one()
        if self.type == "in_invoice":
            action = self.env.ref("account.action_vendor_bill_template").read()[0]
        elif self.type == "in_refund":
            action = self.env.ref("account.action_invoice_in_refund").read()[0]
        elif self.type == "out_refund":
            action = self.env.ref("account.action_invoice_out_refund").read()[0]
        else:
            action = self.env.ref("account.action_invoice_tree1").read()[0]

        if self.type[:2] == "in":
            form_view = [(self.env.ref("account.invoice_form").id, "form")]
        else:
            form_view = [(self.env.ref("account.invoice_supplier_form").id, "form")]

        if "views" in action:
            action["views"] = form_view + [
                (state, view) for state, view in action["views"] if view != "form"
            ]
        else:
            action["views"] = form_view

        action["res_id"] = self.id
        return action

    def action_date_assign(self):
        """Usamos esse método para definir a data de emissão do documento
        fiscal e numeração do documento fiscal para ser usado nas linhas
        dos lançamentos contábeis."""
        super().action_date_assign()
        for invoice in self:
            if invoice.document_type_id:
                if invoice.issuer == DOCUMENT_ISSUER_COMPANY:
                    invoice.fiscal_document_id._document_date()
                    invoice.fiscal_document_id._document_number()

    def action_move_create(self):
        result = super().action_move_create()
        self.mapped("fiscal_document_id").filtered(
            lambda d: d.document_type_id
        ).action_document_confirm()
        return result

    def action_invoice_draft(self):
        for i in self.filtered(lambda d: d.document_type_id):
            if i.state_edoc == SITUACAO_EDOC_CANCELADA:
                if i.issuer == DOCUMENT_ISSUER_COMPANY:
                    raise UserError(
                        _(
                            "You can't set this document number: {} to draft "
                            "because this document is cancelled in SEFAZ".format(
                                i.document_number
                            )
                        )
                    )
            if i.state_edoc != SITUACAO_EDOC_EM_DIGITACAO:
                i.fiscal_document_id.action_document_back2draft()
        return super().action_invoice_draft()

    def action_document_send(self):
        invoices = self.filtered(lambda d: d.document_type_id)
        if invoices:
            invoices.mapped("fiscal_document_id").action_document_send()
            for invoice in invoices:
                invoice.move_id.post(invoice=invoice)

    def action_document_cancel(self):
        for i in self.filtered(lambda d: d.document_type_id):
            return i.fiscal_document_id.action_document_cancel()

    def action_document_correction(self):
        for i in self.filtered(lambda d: d.document_type_id):
            return i.fiscal_document_id.action_document_correction()

    def action_document_invalidate(self):
        for i in self.filtered(lambda d: d.document_type_id):
            return i.fiscal_document_id.action_document_invalidate()

    def action_document_back2draft(self):
        """Sets fiscal document to draft state and cancel and set to draft
        the related invoice for both documents remain equivalent state."""
        for i in self.filtered(lambda d: d.document_type_id):
            i.action_cancel()
            i.action_invoice_draft()

    def action_invoice_open(self):
        result = super().action_invoice_open()

        for record in self.filtered(lambda i: i.refund_invoice_id):
            if record.state == "open" and record.refund_invoice_id.state == "open":
                # Ao confirmar uma fatura/documento fiscal se é uma devolução
                # é feito conciliado com o documento de origem para abater
                # o valor devolvido pelo documento de refund
                to_reconcile_lines = self.env["account.move.line"]
                for line in record.refund_invoice_id.move_id.line_ids:
                    if line.account_id.id == record.refund_invoice_id.account_id.id:
                        to_reconcile_lines += line
                    if line.reconciled:
                        line.remove_move_reconcile()
                for line in record.move_id.line_ids:
                    if line.account_id.id == record.account_id.id:
                        to_reconcile_lines += line
                if to_reconcile_lines and record.move_id.state == "draft":
                    record.move_id.action_post()

                if to_reconcile_lines:
                    to_reconcile_lines.filtered(lambda l: not l.reconciled).reconcile()

        return result

    def action_invoice_cancel(self):
        for i in self.filtered(lambda d: d.document_type_id):
            i.fiscal_document_id.action_document_cancel()
        return super().action_invoice_cancel()

    def view_xml(self):
        self.ensure_one()
        return self.fiscal_document_id.view_xml()

    def view_pdf(self):
        self.ensure_one()
        return self.fiscal_document_id.view_pdf()

    def action_send_email(self):
        self.ensure_one()
        return self.fiscal_document_id.action_send_email()

    def _get_refund_common_fields(self):
        fields = super()._get_refund_common_fields()
        fields += [
            "fiscal_operation_id",
            "document_type_id",
            "document_serie_id",
        ]
        return fields

    @api.multi
    @api.returns("self")
    def refund(self, date_invoice=None, date=None, description=None, journal_id=None):
        new_invoices = super().refund(date_invoice, date, description, journal_id)

        force_fiscal_operation_id = False
        if self.env.context.get("force_fiscal_operation_id"):
            force_fiscal_operation_id = self.env["l10n_br_fiscal.operation"].browse(
                self.env.context.get("force_fiscal_operation_id")
            )

        for record in new_invoices.filtered(lambda i: i.document_type_id):
            if (
                not force_fiscal_operation_id
                and not record.fiscal_operation_id.return_fiscal_operation_id
            ):
                raise UserError(
                    _("""Document without Return Fiscal Operation! \n Force one!""")
                )

            record.fiscal_operation_id = (
                force_fiscal_operation_id
                or record.fiscal_operation_id.return_fiscal_operation_id
            )
            record.fiscal_document_id._onchange_fiscal_operation_id()

            for line in record.invoice_line_ids:
                if (
                    not force_fiscal_operation_id
                    and not line.fiscal_operation_id.return_fiscal_operation_id
                ):
                    raise UserError(
                        _(
                            """Line without Return Fiscal Operation! \n
                            Please force one! \n{}""".format(
                                line.name
                            )
                        )
                    )

                line.fiscal_operation_id = (
                    force_fiscal_operation_id
                    or line.fiscal_operation_id.return_fiscal_operation_id
                )
                line._onchange_fiscal_operation_id()

            refund_inv_id = record.refund_invoice_id

            if record.refund_invoice_id.document_type_id:
                record.fiscal_document_id._document_reference(
                    refund_inv_id.fiscal_document_id
                )

        return new_invoices

    def _refund_cleanup_lines(self, lines):
        result = super()._refund_cleanup_lines(lines)
        for _a, _b, vals in result:
            if vals.get("fiscal_document_line_id"):
                vals.pop("fiscal_document_line_id")

        for i, line in enumerate(lines):
            for name, _field in line._fields.items():
                if name == "fiscal_tax_ids":
                    result[i][2][name] = [(6, 0, line[name].ids)]

        return result
