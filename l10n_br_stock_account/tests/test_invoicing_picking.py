# @ 2019 Akretion - www.akretion.com.br -
#   Magno Costa <magno.costa@akretion.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class InvoicingPickingTest(TransactionCase):
    """Test invoicing picking"""

    def setUp(self):
        super(InvoicingPickingTest, self).setUp()
        self.stock_picking = self.env['stock.picking']
        self.invoice_model = self.env['account.invoice']
        self.invoice_wizard = self.env['stock.invoice.onshipping']
        self.stock_return_picking = self.env['stock.return.picking']
        self.stock_picking_sp = self.env.ref(
            'l10n_br_stock_account.demo_main_l10n_br_stock_account-picking-1')
        self.partner = self.env.ref('l10n_br_base.res_partner_cliente1_sp')
        self.company = self.env.ref('l10n_br_base.empresa_lucro_presumido')

    def _run_fiscal_onchanges(self, record):
        record._onchange_fiscal_operation_id()

    def _run_fiscal_line_onchanges(self, record):
        record._onchange_product_id_fiscal()
        record._onchange_fiscal_operation_id()
        record._onchange_fiscal_operation_line_id()
        record._onchange_fiscal_taxes()

    def test_invoicing_picking(self):
        """Test Invoicing Picking"""

        nb_invoice_before = self.invoice_model.search_count([])
        self._run_fiscal_onchanges(self.stock_picking_sp)

        for line in self.stock_picking_sp.move_lines:
            self._run_fiscal_line_onchanges(line)
            line._onchange_product_quantity()

        self.stock_picking_sp.action_confirm()
        self.stock_picking_sp.action_assign()

        # Force product availability
        for move in self.stock_picking_sp.move_ids_without_package:
            move.quantity_done = move.product_uom_qty
        self.stock_picking_sp.button_validate()
        self.assertEquals(
            self.stock_picking_sp.state, 'done',
            'Change state fail.'
        )
        # Verificar os Valores de Preço pois isso é usado na Valorização do
        # Estoque, o metodo do core é chamado pelo botão Validate

        for line in self.stock_picking_sp.move_lines:
            # No Brasil o caso de Ordens de Entrega que não tem ligação com
            # Pedido de Venda precisam informar o Preço de Custo e não o de
            # Venda, ex.: Simples Remessa, Remessa p/ Industrialiazação e etc.
            # Teria algum caso que não deve usar ?

            # Os metodos do stock/core alteram o valor p/
            # negativo por isso o abs
            self.assertEqual(
                abs(line.price_unit), line.product_id.standard_price)
            # O Campo fiscal_price precisa ser um espelho do price_unit,
            # apesar do onchange p/ preenche-lo sem incluir o compute no campo
            # ele traz o valor do lst_price e falha no teste abaixo
            # TODO - o fiscal_price aqui tbm deve ter um valor negativo ?
            self.assertEqual(line.fiscal_price, line.price_unit)

        wizard_obj = self.invoice_wizard.with_context(
            active_ids=self.stock_picking_sp.ids,
            active_model=self.stock_picking_sp._name,
            active_id=self.stock_picking_sp.id,
        )
        fields_list = wizard_obj.fields_get().keys()
        wizard_values = wizard_obj.default_get(fields_list)
        wizard = wizard_obj.create(wizard_values)
        wizard.onchange_group()
        wizard.action_generate()
        domain = [('picking_ids', '=', self.stock_picking_sp.id)]
        invoice = self.invoice_model.search(domain)

        self.assertTrue(invoice, 'Invoice is not created.')
        self.assertEqual(self.stock_picking_sp.invoice_state, 'invoiced')
        self.assertEqual(invoice.partner_id, self.partner)
        self.assertIn(invoice, self.stock_picking_sp.invoice_ids)
        self.assertIn(self.stock_picking_sp, invoice.picking_ids)
        nb_invoice_after = self.invoice_model.search_count([])
        self.assertEquals(nb_invoice_before, nb_invoice_after - len(invoice))
        assert invoice.invoice_line_ids, 'Error to create invoice line.'
        for line in invoice.picking_ids:
            self.assertEquals(
                line.id, self.stock_picking_sp.id,
                'Relation between invoice and picking are missing.')
        for line in invoice.invoice_line_ids:
            self.assertTrue(
                line.invoice_line_tax_ids,
                'Taxes in invoice lines are missing.'
            )
            # No Brasil o caso de Ordens de Entrega que não tem ligação com
            # Pedido de Venda precisam informar o Preço de Custo e não o de
            # Venda, ex.: Simples Remessa, Remessa p/ Industrialiazação e etc.
            # Aqui o campo não pode ser negativo
            self.assertEqual(line.price_unit, line.product_id.standard_price)

        self.assertTrue(
            invoice.fiscal_operation_id,
            'Mapping fiscal operation on wizard to create invoice fail.'
        )
        self.assertTrue(
            invoice.fiscal_document_id,
            'Mapping Fiscal Documentation_id on wizard to create invoice fail.'
        )

        self.return_wizard = self.stock_return_picking.with_context(
            dict(active_id=self.stock_picking_sp.id)).create(
            dict(invoice_state='2binvoiced'))
        for line in self.return_wizard.product_return_moves:
            line.quantity = line.move_id.product_uom_qty

        result = self.return_wizard.create_returns()
        self.assertTrue(result, 'Create returns wizard fail.')

    def test_invoicing_picking_overprocessed(self):
        """Test Invoicing Picking overprocessed EXTRA Fields"""

        self._run_fiscal_onchanges(self.stock_picking_sp)

        for line in self.stock_picking_sp.move_lines:
            self._run_fiscal_line_onchanges(line)

        self.stock_picking_sp.action_confirm()
        self.stock_picking_sp.action_assign()

        # Force product availability
        for move in self.stock_picking_sp.move_ids_without_package:
            # Overprocessed
            move.quantity_done = move.product_uom_qty + 1

        res_overprocessed_transfer = self.stock_picking_sp.button_validate()
        stock_overprocessed_transfer = self.env[
            'stock.overprocessed.transfer'].browse(
            res_overprocessed_transfer.get('res_id'))
        stock_overprocessed_transfer.action_confirm()

        self.assertEquals(
            self.stock_picking_sp.state, 'done',
            'Change state fail.'
        )

    def test_picking_invoicing_by_product2(self):
        """
        Test the invoice generation grouped by partner/product with 2
        picking and 3 moves per picking.
        We use same partner for 2 picking so we should have 1 invoice with 3
        lines (and qty 2)
        :return:
        """
        nb_invoice_before = self.invoice_model.search_count([])
        self.partner.write({'type': 'invoice'})
        picking = self.env.ref(
            'l10n_br_stock_account.demo_main_l10n_br_stock_account-picking-1')
        picking.action_confirm()
        # Check product availability
        picking.action_assign()
        # Force product availability
        for move in picking.move_ids_without_package:
            move.quantity_done = move.product_uom_qty
        picking.button_validate()
        picking2 = self.env.ref(
            'l10n_br_stock_account.demo_main_l10n_br_stock_account-picking-2')
        # Check product availability
        picking2.action_assign()
        # Force product availability
        for move in picking2.move_ids_without_package:
            move.quantity_done = move.product_uom_qty
        picking2.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking2.state, 'done')
        pickings = picking | picking2
        wizard_obj = self.invoice_wizard.with_context(
            active_ids=pickings.ids,
            active_model=pickings._name,
        )
        fields_list = wizard_obj.fields_get().keys()
        wizard_values = wizard_obj.default_get(fields_list)
        # One invoice per partner but group products
        wizard_values.update({
            'group': 'partner_product',
        })
        wizard = wizard_obj.create(wizard_values)
        wizard.onchange_group()
        wizard.action_generate()
        domain = [('picking_ids', '=', picking.id)]
        invoice = self.invoice_model.search(domain)
        self.assertEquals(len(invoice), 1)
        self.assertEqual(picking.invoice_state, 'invoiced')
        self.assertEqual(picking2.invoice_state, 'invoiced')
        self.assertEqual(invoice.partner_id, self.partner)
        self.assertIn(invoice, picking.invoice_ids)
        self.assertIn(invoice, picking2.invoice_ids)
        self.assertIn(picking, invoice.picking_ids)
        self.assertIn(picking2, invoice.picking_ids)
        for inv_line in invoice.invoice_line_ids:
            # qty = 3 because 1 move + duplicate one + 1 new
            self.assertAlmostEqual(inv_line.quantity, 3)
            self.assertTrue(
                inv_line.invoice_line_tax_ids,
                'Error to map Sale Tax in invoice.line.')
        # Now test behaviour if the invoice is delete
        invoice.unlink()
        for picking in pickings:
            self.assertEquals(picking.invoice_state, '2binvoiced')
        nb_invoice_after = self.invoice_model.search_count([])
        # Should be equals because we delete the invoice
        self.assertEquals(nb_invoice_before, nb_invoice_after)

    def test_picking_invoicing_by_product2(self):
        """
        Test the invoice generation grouped by partner/product with 2
        picking and 3 moves per picking, but 1 picking are the one
        address of the other partner so we should have 2 invoicies
        with 3 lines (and qty 2)
        :return:
        """
        nb_invoice_before = self.invoice_model.search_count([])
        self.partner.write({'type': 'invoice'})
        picking = self.env.ref(
            'l10n_br_stock_account.demo_main_l10n_br_stock_account-picking-3')
        picking.action_confirm()
        # Check product availability
        picking.action_assign()
        # Force product availability
        for move in picking.move_ids_without_package:
            move.quantity_done = move.product_uom_qty
        picking.button_validate()
        picking2 = self.env.ref(
            'l10n_br_stock_account.demo_main_l10n_br_stock_account-picking-4')
        # Check product availability
        picking2.action_assign()
        # Force product availability
        for move in picking2.move_ids_without_package:
            move.quantity_done = move.product_uom_qty
        picking2.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking2.state, 'done')
        pickings = picking | picking2
        wizard_obj = self.invoice_wizard.with_context(
            active_ids=pickings.ids,
            active_model=pickings._name,
        )
        fields_list = wizard_obj.fields_get().keys()
        wizard_values = wizard_obj.default_get(fields_list)
        # One invoice per partner but group products
        wizard_values.update({
            'group': 'partner_product',
        })
        wizard = wizard_obj.create(wizard_values)
        wizard.onchange_group()
        wizard.action_generate()
        domain = [('picking_ids', 'in', (picking.id, picking2.id))]
        invoicies = self.invoice_model.search(domain)
        self.assertEquals(len(invoicies), 2)
        self.assertEqual(picking.invoice_state, 'invoiced')
        self.assertEqual(picking2.invoice_state, 'invoiced')
        invoice_pick_1 = invoicies.filtered(
            lambda t: t.partner_id == picking.partner_id)
        # TODO - está trazendo o mesmo Partner apesar de ser um endereço do
        #  de outro principal, o metodo address_get chamado pelo
        #  get_invoice_partner está trazendo o primeiro is_company. Isso
        #  significa que no caso de uso de ter um Picking para ser Faturado
        #  sem relação com um Pedido de Venda/Compras a opção de ter um
        #  Endereço de Entrega diferente do de Faturamento precirá ser
        #  feita manualmente na Fatura/Doc Fiscal criados.
        self.assertEqual(invoice_pick_1.partner_id, picking.partner_id)
        self.assertIn(invoice_pick_1, picking.invoice_ids)
        self.assertIn(picking, invoice_pick_1.picking_ids)

        invoice_pick_2 = invoicies.filtered(
            lambda t: t.partner_id == picking2.partner_id)
        self.assertIn(invoice_pick_2, picking2.invoice_ids)

        self.assertIn(picking2, invoice_pick_2.picking_ids)

        # Not grouping products with different Operation Fiscal Line
        self.assertEquals(len(invoice_pick_1.invoice_line_ids), 3)
        for inv_line in invoice_pick_1.invoice_line_ids:
            self.assertTrue(
                inv_line.invoice_line_tax_ids,
                'Error to map Sale Tax in invoice.line.')
        # Now test behaviour if the invoice is delete
        invoice_pick_1.unlink()
        invoice_pick_2.unlink()
        for picking in pickings:
            self.assertEquals(picking.invoice_state, '2binvoiced')
        nb_invoice_after = self.invoice_model.search_count([])
        # Should be equals because we delete the invoice
        self.assertEquals(nb_invoice_before, nb_invoice_after)
