# Copyright 2021 Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).
# pylint: disable=reimported

import logging

from unittest.mock import patch

from odoo.api import NewId
from odoo.orm.model_classes import add_to_registry
from odoo.tests import TransactionCase

from odoo.addons.spec_driven_model.tests import (
    fake_mixin,
    fake_odoo_purchase,
    purchase_order_lib,
    spec_poxsd,
    spec_purchase,
)

_logger = logging.getLogger(__name__)


class TestSpecModel(TransactionCase):
    """
    A simple usage example using the reference PurchaseOrderSchema.xsd
    https://docs.microsoft.com/en-us/visualstudio/xml-tools/sample-xsd-file-purchase-order-schema?view=vs-2019
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fake_model_names = []

        # 1. Register abstract spec models first.
        #    The StackedModel._spec_build_model visits the spec tree
        #    and needs these models to be in the registry.
        spec_abstract_models = [
            fake_mixin.PoXsdMixin,
            spec_poxsd.Items,
            spec_poxsd.Item,
            spec_poxsd.Usaddress,
            spec_poxsd.Comment,
            spec_poxsd.PurchaseOrderType,
        ]
        for model_cls in spec_abstract_models:
            add_to_registry(cls.registry, model_cls)
            cls._fake_model_names.append(model_cls._name)

        # 2. Register fake Odoo concrete models
        for model_cls in [fake_odoo_purchase.PurchaseOrder,
                          fake_odoo_purchase.PurchaseOrderLine]:
            add_to_registry(cls.registry, model_cls)
            cls._fake_model_names.append(model_cls._name)

        # 3. Run _spec_build_model on the spec DEFINITION classes BEFORE
        #    registering them. This modifies their _inherit to include
        #    stacked mixins, allowing add_to_registry to build the
        #    correct _base_classes__.
        #
        #    ORDER MATTERS: ResPartner must go first (maps
        #    poxsd.10.usaddress → res.partner), then PurchaseOrderLine
        #    (maps poxsd.10.item → fake.purchase.order.line), then
        #    PurchaseOrder (StackedModel, visits the spec tree and
        #    needs the mappings from previous models).
        spec_purchase.ResPartner._spec_build_model(
            cls.registry, cls.env.cr
        )
        spec_purchase.PurchaseOrderLine._spec_build_model(
            cls.registry, cls.env.cr
        )
        spec_purchase.PurchaseOrder._spec_build_model(
            cls.registry, cls.env.cr
        )

        # 4. Register SpecModel/StackedModel extensions with their
        #    updated _inherit (stacked mixins now included).
        for model_cls in [spec_purchase.ResPartner,
                          spec_purchase.PurchaseOrderLine,
                          spec_purchase.PurchaseOrder]:
            add_to_registry(cls.registry, model_cls)

        # 5. Setup the models (collects fields, resolves comodels)
        unique_names = list(dict.fromkeys(cls._fake_model_names + [
            "fake.purchase.order",
            "fake.purchase.order.line",
            "res.partner",
        ]))
        cls.registry._setup_models__(cls.env.cr, unique_names)

        # 6. Make remaining abstract spec models concrete
        try:
            cls.env["spec.mixin.poxsd"]._register_remaining_schema_models_hook()
        except Exception as e:
            _logger.warning(
                "_register_remaining_schema_models_hook failed: %s", e
            )

        # 7. Init models (create DB tables)
        cls.registry.init_models(
            cls.env.cr,
            unique_names,
            {"models_to_check": True},
        )

        # 8. Cleanup: remove fake models (not res.partner)
        for name in cls._fake_model_names:
            cls.addClassCleanup(cls.registry.__delitem__, name)

        # NOQA - ensures import side effects happen
        _ = purchase_order_lib

    def test_spec_models(self):
        self.assertTrue(
            set(self.env["res.partner"]._fields.keys()).issuperset(
                set(self.env["poxsd.10.usaddress"]._fields.keys())
            )
        )

        self.assertTrue(
            set(self.env["fake.purchase.order.line"]._fields.keys()).issuperset(
                set(self.env["poxsd.10.item"]._fields.keys())
            )
        )

    def test_stacked_model(self):
        po_fields_or_stacking = set(
            self.env["fake.purchase.order"]._fields.keys()
        )
        po_fields_or_stacking.update(
            set(
                self.env[
                    "fake.purchase.order"
                ]._poxsd10_stacking_points.keys()
            )
        )
        self.assertTrue(
            po_fields_or_stacking.issuperset(
                set(
                    self.env[
                        "poxsd.10.purchaseordertype"
                    ]._fields.keys()
                )
            )
        )
        self.assertEqual(
            list(
                self.env[
                    "fake.purchase.order"
                ]._poxsd10_stacking_points.keys()
            ),
            ["poxsd10_items"],
        )

        # let's ensure fields are remapped to their proper concrete types:
        self.assertEqual(
            self.env["fake.purchase.order"]
            ._fields["poxsd10_shipTo"]
            .comodel_name,
            "res.partner",
        )
        self.assertEqual(
            self.env["fake.purchase.order"]
            ._fields["poxsd10_billTo"]
            .comodel_name,
            "res.partner",
        )

        self.assertEqual(
            self.env["fake.purchase.order"]
            ._fields["poxsd10_item"]
            .comodel_name,
            "fake.purchase.order.line",
        )

    def test_create_export_import(self):
        # 1st we create an Odoo PO:
        partner = self.env["res.partner"].create(
            {
                "name": "Wood Corner",
                "street": "1839 Arbor Way",
                "city": "Turlock",
                "state_id": self.env.ref("base.state_us_5").id,
                "country_id": self.env.ref("base.us").id,
                "zip": "95380",
            }
        )
        po = self.env["fake.purchase.order"].create(
            {
                "name": "PO XSD",
                "date_order": "2024-10-08",
                "partner_id": partner.id,
                "dest_address_id": partner.id,
            }
        )
        self.env["fake.purchase.order.line"].create(
            {
                "name": "Some product desc",
                "product_qty": 42,
                "price_unit": 13,
                "order_id": po.id,
            }
        )

        # 2nd we serialize it into a binding object:
        # (that could be further XML serialized)
        po_binding = po._build_binding(
            spec_schema="poxsd", spec_version="10"
        )
        self.assertEqual(
            [s.__name__ for s in type(po_binding).mro()],
            ["PurchaseOrderType", "object"],
        )
        self.assertEqual(po_binding.bill_to.name, "Wood Corner")
        self.assertEqual(
            po_binding.items.item[0].product_name, "Some product desc"
        )
        self.assertEqual(po_binding.items.item[0].quantity, 42)
        self.assertEqual(po_binding.items.item[0].usprice, "13")  # FIXME

        # 3rd we serialize po_binding as XML and check the output:
        try:
            from xsdata.formats.dataclass.serializers import XmlSerializer
            from xsdata.formats.dataclass.serializers.config import (
                SerializerConfig,
            )

            serializer = XmlSerializer(
                config=SerializerConfig(indent="  ")
            )
            xml = serializer.render(obj=po_binding, ns_map=None)
            expected_xml = """<?xml version="1.0" encoding="UTF-8"?>
<PurchaseOrderType orderDate="2024-10-08">
  <ns0:shipTo xmlns:ns0="http://tempuri.org/PurchaseOrderSchema.xsd" country="US">
    <ns0:name>Wood Corner</ns0:name>
    <ns0:street>1839 Arbor Way</ns0:street>
    <ns0:city>Turlock</ns0:city>
    <ns0:state>California</ns0:state>
    <ns0:zip>0</ns0:zip>
  </ns0:shipTo>
  <ns0:billTo xmlns:ns0="http://tempuri.org/PurchaseOrderSchema.xsd" country="US">
    <ns0:name>Wood Corner</ns0:name>
    <ns0:street>1839 Arbor Way</ns0:street>
    <ns0:city>Turlock</ns0:city>
    <ns0:state>California</ns0:state>
    <ns0:zip>0</ns0:zip>
  </ns0:billTo>
  <ns0:items xmlns:ns0="http://tempuri.org/PurchaseOrderSchema.xsd">
    <ns0:item>
      <ns0:productName>Some product desc</ns0:productName>
      <ns0:quantity>42</ns0:quantity>
      <ns0:USPrice>13</ns0:USPrice>
    </ns0:item>
  </ns0:items>
</PurchaseOrderType>
"""
            self.assertEqual(xml, expected_xml)

        except ImportError:
            _logger.error(
                "xsdata Python lib not installed, skipping XML test!"
            )

        # 4th we import an Odoo PO from this binding object
        # first we will do a dry run import:
        imported_po_dry_run = self.env[
            "fake.purchase.order"
        ].build_from_binding("poxsd", "10", po_binding, dry_run=True)
        assert isinstance(imported_po_dry_run.id, NewId)

        # now a real import:
        imported_po = self.env[
            "fake.purchase.order"
        ].build_from_binding("poxsd", "10", po_binding)
        self.assertEqual(imported_po.partner_id.name, "Wood Corner")
        self.assertEqual(imported_po.partner_id.id, partner.id)
        self.assertEqual(
            imported_po.order_line[0].name, "Some product desc"
        )

    def test_polymorphic_comodel_from_binding_type(self):
        binding_type = "Cte.Tcte.Ide"
        expected_model_name = "cte.40.ide"
        available_models = {
            expected_model_name: "Found Fallback Model"
        }

        method_path = (
            "odoo.addons.spec_driven_model.models.spec_mixin."
            "SpecMixin._get_concrete_model"
        )
        with patch(method_path) as mock_get_concrete_model:
            mock_get_concrete_model.side_effect = (
                lambda name: available_models.get(name)
            )
            model_instance = self.env["spec.mixin"].with_context(
                spec_schema="cte", spec_version="40"
            )
            result = model_instance._comodel_from_binding_type(
                binding_type
            )

        assert result == "Found Fallback Model"

        # Check the full sequence of calls.
        actual_calls = [
            c.args[0]
            for c in mock_get_concrete_model.call_args_list
        ]
        expected_model_suffixes = [
            "cte.40.cte_ide",
            "cte.40.cte_tcte_ide",
            "cte.40.ide",
        ]

        assert actual_calls == expected_model_suffixes
        assert mock_get_concrete_model.call_count == len(
            expected_model_suffixes
        )
