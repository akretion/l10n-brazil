# Copyright (C) 2020 - TODAY Renato Lima - Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, models


class AccountTax(models.Model):
    _name = "account.tax"
    _inherit = ["account.tax.mixin", "account.tax"]

    def _update_repartition_lines(self, account_id, refund_account_id):
        for tax in self:
            tax.write(
                {
                    "invoice_repartition_line_ids": [
                        Command.clear(),
                        Command.create(
                            {
                                "factor_percent": 100,
                                "repartition_type": "base",
                            }
                        ),
                        Command.create(
                            {
                                "factor_percent": (
                                    -100 if tax.deductible or tax.withholdable else 100
                                ),
                                "repartition_type": "tax",
                                "account_id": account_id,
                            }
                        ),
                    ],
                    "refund_repartition_line_ids": [
                        Command.clear(),
                        Command.create(
                            {
                                "factor_percent": 100,
                                "repartition_type": "base",
                            }
                        ),
                        Command.create(
                            {
                                "factor_percent": (
                                    -100 if tax.deductible or tax.withholdable else 100
                                ),
                                "repartition_type": "tax",
                                "account_id": refund_account_id,
                            }
                        ),
                    ],
                }
            )
