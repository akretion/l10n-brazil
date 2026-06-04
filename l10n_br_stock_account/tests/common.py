# @author Magno Costa <magno.costa@akretion.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.stock_picking_invoicing.tests.common import (
    TestStockPickingInvoicingCommon,
)
from odoo.addons.stock_picking_invoicing.tests.tools import (
    create_with_form_inv_onshipping,
    create_with_form_pck_backorder,
    create_with_form_return_picking,
)


class TestBrPickingInvoicingCommon(TestStockPickingInvoicingCommon):
    def _change_user_company(self, company):
        self.env.user.company_ids += company
        self.env.user.company_id = company

    def create_invoice_wizard(self, pickings):
        return create_with_form_inv_onshipping(self.env, pickings)

    def return_picking_wizard(self, picking):
        return create_with_form_return_picking(self.env, picking)

    def create_backorder_wizard(self, picking):
        return create_with_form_pck_backorder(self.env, picking)
