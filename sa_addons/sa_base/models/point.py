# -*- coding: utf-8 -*-


from odoo import api, fields, models, SUPERUSER_ID, _

from odoo.exceptions import UserError, ValidationError

from odoo.addons import decimal_precision as dp

import uuid


class OperationPointsGroup(models.Model):
    _name = 'operation.point.group'

    _order = "sequence"

    sequence = fields.Integer('sequence', default=1)

    proposal_key_num = fields.Integer(default=0, copy=False)

    name = fields.Char('Operation Point Group')
    key_num = fields.Integer(string='Key Point Count', copy=False, compute="_compute_key_point_count",
                             inverse='_inverse_key_point_count',
                             store=True)
    # operation_point_ids_domain = fields.Char(
    #     compute="_compute_operation_point_ids_domain",
    #     readonly=True,
    #     store=False,
    # )

    operation_id = fields.Many2one('mrp.routing.workcenter', ondelete='cascade', index=True)

    operation_point_ids = fields.One2many('operation.point', 'group_id',
                                          string='Points', copy=False)

    # @api.constrains('operation_point_ids')
    # def _constraint_operation_point_ids(self):
    #     point_ids = self.operation_point_ids.ids
    #     if len(point_ids) != len(set(point_ids)):
    #         raise ValidationError(u'作业点设定中存在重复项')

    @api.multi
    def _inverse_key_point_count(self):
        for record in self:
            record.proposal_key_num = record.key_num

    @api.constrains('key_num')
    def _constraint_key_num(self):
        for record in self:
            lk = len(record.operation_point_ids.filtered(lambda r: r.is_key))
            if record.key_num < lk:
                raise ValidationError(_('Key Point Number Can Not Less Than Operation Point Key Total'))

    @api.multi
    @api.depends('operation_point_ids.is_key', 'proposal_key_num')
    def _compute_key_point_count(self):
        for record in self:
            lk = len(record.operation_point_ids.filtered(lambda r: r.is_key))
            record.key_num = max(record.proposal_key_num, lk)

    @api.multi
    def name_get(self):
        res = []
        for point in self:
            res.append((point.id, _('[%s] %s') % (point.operation_id.name, point.name)))
        return res


class OperationPoints(models.Model):
    _name = 'operation.point'

    _inherits = {'sa.quality.point': 'qcp_id'}

    _inherit = ['mail.thread']

    _order = "group_sequence, sequence"

    @api.model
    def _get_default_picking_type(self):
        return self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            (
                'warehouse_id.company_id', 'in',
                [self.env.context.get('company_id', self.env.user.company_id.id), False])],
            limit=1).id

    is_key = fields.Boolean(string='Is Key Point', default=False)
    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the bills of material without removing it.")

    sequence = fields.Integer('sequence', default=1)

    name = fields.Char('Tightening Point Name', related='qcp_id.name', inherited=True, default=lambda self: str(uuid.uuid4()))  # 如果未定义拧紧点编号，即自动生成uuid号作为唯一标示

    group_id = fields.Many2one('operation.point.group')

    group_sequence = fields.Integer('Group Sequence for Multi Spindle')

    product_id = fields.Many2one('product.product', 'Consume Product', related='qcp_id.product_id', inherited=True,
                                 domain="[('sa_type', '=', 'screw')]")

    product_tmpl_id = fields.Many2one('product.template', 'Consume Product(Tightening Screw)',
                                      related='qcp_id.product_tmpl_id', inherited=True,
                                      domain="[('type', 'in', ['product', 'consu']), ('sa_type', '=', 'screw')]")

    product_qty = fields.Float('Product Quantity', default=1.0, digits=dp.get_precision('Product Unit of Measure'))

    x_offset = fields.Float('x axis offset from left(%)', default=0.0, digits=dp.get_precision('POINT_OFFSET'))

    y_offset = fields.Float('y axis offset from top(%)', default=0.0, digits=dp.get_precision('POINT_OFFSET'))

    program_id = fields.Many2one('controller.program', string='程序号(Pset/Job)', ondelete='cascade')

    control_mode = fields.Selection(related='program_id.control_mode', readonly=1)

    parent_qcp_id = fields.Many2one('sa.quality.point', ondelete='cascade', index=True)

    qcp_id = fields.Many2one('sa.quality.point', required=True, string='Quality Control Point(Tightening Work Step)',
                             ondelete='cascade', auto_join=True)

    picking_type_id = fields.Many2one('stock.picking.type', related='qcp_id.test_type_id', inherited=True,
                                      default=_get_default_picking_type)

    operation_id = fields.Many2one('mrp.routing.workcenter', related='qcp_id.operation_id', inherited=True)

    test_type_id = fields.Char(related='qcp_id.test_type_id', inherited=True)

    max_redo_times = fields.Integer(string='Operation Max Redo Times', related='qcp_id.max_redo_times',
                                    default=3)  # 此项重试业务逻辑在HMI中实现

    # @api.multi
    # def _track_subtype(self, init_values):
    #     self.ensure_one()
    #     if 'max_redo_times' in init_values:
    #         return 'sa_base.mt_op_point_max_redo_time'
    #     elif 'program_id' in init_values:
    #         return 'sa_base.mt_op_program_id'
    #     return super(OperationPoints, self)._track_subtype(init_values)

    @api.multi
    def name_get(self):
        res = []
        for point in self:
            res.append((point.id, _('[%s] %s') % (point.operation_id.name, point.name)))
        return res

    @api.model
    def default_get(self, fields):
        res = super(OperationPoints, self).default_get(fields)
        if 'picking_type_id' not in res:
            res.update({
                'picking_type_id': self._get_default_picking_type()
            })

        operation_id = self.env.context.get('default_operation_id')
        if operation_id:
            operation = self.env['mrp.routing.workcenter'].sudo().browse(operation_id)
            if 'max_redo_times' in fields:
                res.update({'max_redo_times': operation.max_redo_times})
            if 'sequence' in fields and operation.operation_point_ids:
                res.update({'sequence': max(operation.operation_point_ids.mapped('sequence')) + 1})
        return res

    @api.multi
    def unlink(self):
        for point in self:
            msg = _("#%s operation point has been delete") % (point.id)
            point.operation_id.message_post(body=msg, subject=msg, message_type='comment')
        lines = self.env['mrp.bom.line'].search([('operation_point_id', 'in', self.ids)])
        if lines:
            lines.unlink()
        return super(OperationPoints, self).unlink()

    @api.multi
    def toggle_active(self):
        bom_line_ids = self.env['mrp.bom.line'].search([('operation_point_id', 'in', self.ids)])
        if bom_line_ids:
            bom_line_ids.toggle_active()
        return super(OperationPoints, self).toggle_active()

    @api.model
    def create(self, vals):
        tightening_point_type_id = self.env.ref('quality.test_type_tightening_point').id
        vals.update({
            'test_type_id': tightening_point_type_id
        })
        if 'product_tmpl_id' not in vals and 'product_id' in vals:
            product_tmpl_id = self.env['product.product'].sudo().browse(vals.get('product_id')).product_tmpl_id.id
            vals.update({
                'product_tmpl_id': product_tmpl_id
            })
        ret = super(OperationPoints, self).create(vals)
        auto_operation_point_inherit = self.env['ir.values'].get_default('sa.config.settings',
                                                                         'auto_operation_point_inherit')
        if auto_operation_point_inherit:
            operation_id = ret.operation_id
            bom_ids = self.env['mrp.bom'].search([('operation_ids', 'in', operation_id.ids)])
            for bom in bom_ids:
                val = {
                    "operation_point_id": ret.id,
                    "product_id": ret.product_id.id,
                    "bom_id": bom.id,
                }
                self.env['mrp.bom.line'].sudo().create(val)
        return ret

    @api.multi
    def write(self, vals):
        ret = None
        tracked_fields = self.env['operation.point'].fields_get(['max_redo_times', 'program_id', 'product_id'])
        for point in self:
            if 'max_redo_times' in vals or 'program_id' in vals or 'product_id' in vals:
                old_values = {
                    'max_redo_times': point.max_redo_times,
                    'program_id': point.program_id,
                    'product_id': point.product_id
                }
                ret = super(OperationPoints, point).write(vals)  # 修改数据

                dummy, tracking_value_ids = point._message_track(tracked_fields, old_values)
                msg = _("#%s operation point has been modified") % (point.id)
                point.operation_id.message_post(body=msg, message_type='comment', tracking_value_ids=tracking_value_ids,
                                                subject=msg)
            else:
                ret = super(OperationPoints, point).write(vals)  # 修改数据
        return ret

        # return super(OperationPoints, self).write(vals)
