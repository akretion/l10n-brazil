# Copyright (C) 2009  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, models
from odoo.exceptions import UserError


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _create_return(self):
        """
        Creates return picking.
        @param self: The object pointer.
        @return: A dictionary which of fields with values.
        """
        new_picking = super()._create_return()

        origin_picking = self.env["stock.picking"].browse(self.env.context["active_id"])

        if origin_picking.fiscal_operation_id:
            refund_fiscal_operation = (
                origin_picking.fiscal_operation_id.return_fiscal_operation_id
            )

            if not refund_fiscal_operation:
                if self.invoice_state == "2binvoiced":
                    raise UserError(
                        _(
                            "This Fiscal Operation has no Fiscal Operation"
                            " for Returns defined!"
                        )
                    )
            else:
                new_picking.fiscal_operation_id = refund_fiscal_operation
                for move in new_picking.move_ids:
                    ret_move = move.origin_returned_move_id
                    fiscal_op = ret_move.fiscal_operation_id.return_fiscal_operation_id
                    fiscal_op_line = ret_move.fiscal_operation_line_id.line_refund_id
                    vals = {}
                    vals["fiscal_operation_id"] = fiscal_op.id
                    if fiscal_op_line:
                        # Only include fiscal_operation_line_id when the return
                        # has a fiscal operation line otherwise, omit it so Odoo
                        # can compute/fallback to the default value.
                        vals["fiscal_operation_line_id"] = fiscal_op_line.id
                    if vals:
                        move.write(vals)
        return new_picking
