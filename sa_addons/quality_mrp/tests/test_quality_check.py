# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .test_common import TestQualityMrpCommon


class TestQualityCheck(TestQualityMrpCommon):

    def test_00_production_quality_check(self):
        """Test quality check on production order."""

        # Create Quality Point for product Laptop Customized with Manufacturing Picking Type.
        self.qality_point_test1 = self.env['sa.quality.point'].create({
            'product_id': self.product_id,
            'product_tmpl_id': self.product_tmpl_id,
            'picking_type_id': self.picking_type_id,
        })

        # Check that quality point created.
        assert self.qality_point_test1, "First Quality Point not created for Laptop Customized."

        # Create Production Order of Laptop Customized to produce 5.0 Unit.
        self.mrp_production_qc_test1 = self.env['mrp.production'].create({
            'product_id': self.product_id,
            'product_qty': 5.0,
            'product_uom_id': self.product_uom_id,
            'bom_id': self.bom_id,
        })

        # Check that Production Order of Laptop Customized to produce 5.0 Unit is created.
        assert self.mrp_production_qc_test1, "Production Order not created."

        # Perform check availability and produce product.
        self.mrp_production_qc_test1.action_assign()
        produce_wiz = self.env['mrp.product.produce'].with_context(active_id=self.mrp_production_qc_test1.id).create(
            {'product_qty': self.mrp_production_qc_test1.product_qty,
             'lot_id': self.env.ref('mrp.lot_product_27_0').id})
        produce_wiz.consume_line_ids.write({'quantity_done': produce_wiz.product_qty})
        produce_wiz.do_produce()

        # Check Quality Check for Production is created and check it's state is 'none'.
        self.assertEquals(len(self.mrp_production_qc_test1.check_ids), 1)
        self.assertEquals(self.mrp_production_qc_test1.check_ids.quality_state, 'none')

        # 'Pass' Quality Checks of production order.
        self.mrp_production_qc_test1.check_ids.do_pass()

        # Post Inventory and Set MO Done.
        self.mrp_production_qc_test1.post_inventory()
        self.mrp_production_qc_test1.button_mark_done()

        # Now check state of quality check.
        self.assertEquals(self.mrp_production_qc_test1.check_ids.quality_state, 'pass')
