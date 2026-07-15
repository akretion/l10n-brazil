# Copyright (C) 2025 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    fiscal_document_count = fields.Integer(
        string="Fiscal Doc Count",
        compute="_compute_fiscal_document_count",
        store=True,
    )

    @api.depends("fiscal_document_ids")
    def _compute_fiscal_document_count(self):
        for move in self:
            move.fiscal_document_count = len(move.fiscal_document_ids)

    def open_fiscal_document(self):
        """
        Open the account.move with the fiscal document mask form view.
        When only 1 fiscal document exists, switch the current account.move
        form to the fiscal mask view (same record, different view).
        When several fiscal documents exist, open the fiscal document list.
        """
        self.ensure_one()

        if len(self.fiscal_document_ids) <= 1:
            # Switch to the fiscal mask form view on the same account.move
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": self.id,
                "views": [
                    (
                        self.env.ref(
                            "l10n_br_account_fiscal_invoice.fiscal_invoice_form"
                        ).id,
                        "form",
                    ),
                    (
                        self.env.ref(
                            "l10n_br_account_fiscal_invoice.fiscal_invoice_tree"
                        ).id,
                        "list",
                    ),
                ],
                "target": "current",
                "context": self.env.context,
            }

        # Multiple fiscal documents: open the fiscal document list
        if self.env.context.get("move_type") == "out_invoice":
            xmlid = "l10n_br_fiscal.document_out_action"
        elif self.env.context.get("move_type") == "in_invoice":
            xmlid = "l10n_br_fiscal.document_in_action"
        else:
            xmlid = "l10n_br_fiscal.document_all_action"
        action = self.env["ir.actions.act_window"]._for_xml_id(xmlid)
        action["domain"] = [("id", "in", self.fiscal_document_ids.ids)]
        return action

    def action_view_fiscal_documents(self):
        """Open the list of fiscal documents related to this account.move."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_br_fiscal.document_all_action"
        )
        action["domain"] = [("id", "in", self.fiscal_document_ids.ids)]
        return action
