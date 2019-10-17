# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import odoo.addons.decimal_precision as dp
import json
import uuid


class QualityPoint(models.Model):
    _inherit = "sa.quality.point"

    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide Quality Check Point without removing it.")

    tolerance_min = fields.Float('Torque Min Tolerance', digits=dp.get_precision('Quality Tests'), default=0.0)
    tolerance_max = fields.Float('Torque Max Tolerance', digits=dp.get_precision('Quality Tests'), default=0.0)

    tolerance_min_degree = fields.Float('Degree Min Tolerance', digits=dp.get_precision('Quality Tests'), default=0.0)
    tolerance_max_degree = fields.Float('Degree Max Tolerance', digits=dp.get_precision('Quality Tests'), default=0.0)

    bom_line_id = fields.Many2one('mrp.bom.line', ondelete='cascade')

    # parent_id = fields.Many2one('sa.quality.point', ondelete='cascade')

    operation_id = fields.Many2one('mrp.routing.workcenter', index=True)

    max_redo_times = fields.Integer('Operation Max Redo Times', default=3)  # 此项重试业务逻辑在HMI中实现

    operation_point_ids = fields.One2many('operation.point', 'parent_qcp_id', string='Quality Points(Tightening Point)')

    operation_id_domain = fields.Char(
        compute="_compute_operation_id_domain",
        readonly=True,
        store=False,
    )

    _sql_constraints = [
        ('product_bom_line_id_uniq', 'unique(bom_line_id)', 'Only one quality point per product bom line is allowed')]

    @api.model
    def default_get(self, fields):
        res = super(QualityPoint, self).default_get(fields)

        operation_id = self.env.context.get('default_operation_id')
        if operation_id:
            operation = self.env['mrp.routing.workcenter'].sudo().browse(operation_id)
            if 'max_redo_times' in fields:
                res.update({'max_redo_times': operation.max_redo_times})
            if 'sequence' in fields and operation.operation_point_ids:
                res.update({'sequence': max(operation.operation_point_ids.mapped('sequence')) + 1})
        return res

    @api.multi
    def name_get(self):
        res = []
        for point in self:
            res.append((point.id, _('[%s] %s') % (point.operation_id.name, point.name)))
        return res

    @api.onchange('operation_id')
    def _onchange_opeartion_id(self):
        self.ensure_one()
        bom_line_ids = self.env['mrp.bom.line'].search(
            [('bom_id.product_id', '=', self.product_id.id), ('operation_id', '=', self.operation_id.id)])
        qtys = [bom_line_id.product_qty for bom_line_id in bom_line_ids]
        self.times = sum(qtys)

    @api.constrains('product_id', 'product_tmpl_id')
    def _product_tmpl_product_constraint(self):
        if self.product_id.product_tmpl_id.id != self.product_tmpl_id.id:
            raise ValidationError('The product template "%s" is invalid on product with name "%s"' % (
            self.product_tmpl_id.name, self.product_id.name))

    @api.multi
    @api.depends('operation_id', 'product_id', 'workcenter_id')
    def _compute_operation_id_domain(self):
        for rec in self:
            operation_ids = rec.product_id.bom_ids.mapped('routing_id.operation_ids').ids or []
            rec.operation_id_domain = json.dumps(
                [('workcenter_id', '=', rec.workcenter_id.id), ('id', 'in', operation_ids)])

    @api.model
    def create(self, vals):
        # tightening_point_type = self.env.ref('quality.test_type_tightening_point').id
        # if 'test_type_id' in vals and vals.get('test_type_id') == tightening_point_type:
        #     vals.update({
        #         'name': uuid.uuid4()
        #     })
        ret = super(QualityPoint, self).create(vals)
        return ret


class QualityCheck(models.Model):
    _inherit = "sa.quality.check"

    measure_degree = fields.Float('Measure Degree', default=0.0, digits=dp.get_precision('Quality Tests'),
                                  track_visibility='onchange')

    assembly_line_id = fields.Many2one('mrp.assemblyline', string='Assembly Line ID',
                                       related='production_id.assembly_line_id', readonly=True)

    @api.one
    @api.depends('measure', 'measure_degree')
    def _compute_measure_success(self):
        if self.point_id.test_type == 'passfail':
            self.measure_success = 'none'
        else:
            if self.measure < self.point_id.tolerance_min or self.measure > self.point_id.tolerance_max:
                self.measure_success = 'fail'
            elif self.measure_degree < self.point_id.tolerance_min_degree or self.measure_degree > self.point_id.tolerance_max_degree:
                self.measure_success = 'fail'
            else:
                self.measure_success = 'pass'
