# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common


class TestQualityMrpCommon(common.TransactionCase):

    def setUp(self):
        super(TestQualityMrpCommon, self).setUp()

        self.product_id = self.ref('product.product_product_27')
        self.product_tmpl_id = self.ref('product.product_product_27_product_template')
        self.product_uom_id = self.ref('product.product_uom_unit')
        self.picking_type_id = self.ref('mrp.picking_type_manufacturing')
        self.bom_id = self.ref('mrp.mrp_bom_laptop_cust')
