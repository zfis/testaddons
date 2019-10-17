# -*- coding: utf-8 -*-

from odoo import models, fields, api
import time


class MrpWOConsu(models.Model):
    _inherit = 'mrp.wo.consu'

    result_ids = fields.One2many('operation.result', 'consu_bom_line_id', string='Operation Results')


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    worksheet_img = fields.Binary(
        'Worksheet', related='operation_id.worksheet_img', readonly=True)

    result_ids = fields.One2many('operation.result', 'workorder_id', string='Operation Results')

    sent = fields.Boolean('Have Sent To Work Center(MasterPC)', default=False)

    @api.model
    def create(self, vals):
        order = super(MrpWorkorder, self).create(vals)
        return order

    @api.multi
    def _create_checks(self):
        ret_vals = []
        idx = 1
        ir_values = self.env['ir.values'].get_default('sa.config.settings', 'generate_result_sequence')
        for wo in self:
            if not ir_values:
                idx = 1  # 重置sequence
            production = wo.production_id
            points = self.env['sa.quality.point'].search([('workcenter_id', '=', wo.workcenter_id.id),
                                                          ('operation_id', '=', wo.operation_id.id),  # 定位到某个作业的质量控制点
                                                          ('picking_type_id', '=', production.picking_type_id.id),
                                                          '|', ('product_id', '=', production.product_id.id),
                                                          '&', ('product_id', '=', False), ('product_tmpl_id', '=',
                                                                                            production.product_id.product_tmpl_id.id)])
            for point in points:
                consu = wo.consu_bom_line_ids.filtered(lambda r: r.bom_line_id.id == point.bom_line_id.id)
                vals = {
                    "sequence": idx,
                    'workorder_id': wo.id,
                    'production_id': production.id,
                    'qcp_id': point.id,
                    'workcenter_id': wo.workcenter_id.id,
                    'assembly_line_id': production.assembly_line_id.id,
                    'point_id': point.id,
                    'product_id': production.product_id.id,
                    'consu_bom_line_id': consu.id,
                    'gun_id': consu.gun_id.id or None,
                    'consu_product_id': consu.product_id.id,
                    'program_id': consu.program_id.id,
                    'time': production.date_planned_start or fields.Datetime.now(),
                    'control_date': fields.Datetime.now()}

                for i in range(point.times):
                    if vals['gun_id']:
                        ret_vals.append(vals)
                        idx += 1
        if len(ret_vals):
            self.env['operation.result'].sudo().bulk_create(ret_vals)
