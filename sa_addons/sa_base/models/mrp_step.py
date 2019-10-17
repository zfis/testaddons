# -*- coding: utf-8 -*-


from odoo import api, fields, models, SUPERUSER_ID, _

from odoo.exceptions import UserError, ValidationError

from odoo.addons import decimal_precision as dp

import uuid



class MrpStepCategory(models.Model):
    _name = 'mrp.step.category'

    _order = "id"

    name = fields.Char('Mrp.Step.Category')
    direction = fields.Text('Direction')

class MrpStep(models.Model):
    _name = 'mrp.step'

    # _inherits = {'sa.quality.point': 'qcp_id'}

    _inherit = ['mail.thread']


    _order = "id,sequence"
    note = fields.Text('Description')
    code = fields.Char('Reference', copy=False)
    step_name = fields.Char('Name Point Group')
    category_id = fields.Many2one('mrp.step.category', string='工步类型')
    category_name = fields.Char(compute='_compute_category_name', default='', store=True)
    direction = fields.Text(compute='_compute_category_direction', default='请按提示作业', store=True)

    worksheet = fields.Binary('worksheet')
    worksheet_img = fields.Binary('worksheet_img')

    is_key = fields.Boolean(string='Is Key Point', default=False, )
    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the bills of material without removing it.")
    child_step_count = fields.Integer(string='Operations', compute='_compute_child_step_count')

    sequence = fields.Integer('sequence', default=1)

    name = fields.Char('Operation Point Name', default=lambda self: str(uuid.uuid4()))  # 如果未定义拧紧点编号，即自动生成uuid号作为唯一标示



    group_sequence = fields.Integer('Group Sequence for Multi Spindle')

    product_id = fields.Many2one('product.product', 'Product')

    product_qty = fields.Float('Product Quantity', default=1.0, digits=dp.get_precision('Product Unit of Measure'))

    x_offset = fields.Float('x axis offset from left(%)', default=0.0, digits=dp.get_precision('POINT_OFFSET'))

    y_offset = fields.Float('y axis offset from top(%)', default=0.0, digits=dp.get_precision('POINT_OFFSET'))

    program_id = fields.Many2one('controller.program', string='Pset', ondelete='cascade')
    op_job_id = fields.Many2one('controller.job', string='Job')

    operation_id = fields.Many2one('mrp.routing.workcenter', ondelete='cascade', index=True)

    max_redo_times = fields.Integer('Operation Max Redo Times', default=3)  # 此项重试业务逻辑在HMI中实现

    group_id = fields.Many2one('mrp.step.group')
    up_step_id = fields.Many2one('mrp.step', ondelete='cascade')
    is_child = fields.Boolean(string='Is child', default=False, )
    operation_point_ids = fields.One2many('mrp.step', 'up_step_id', string='Operation Points')
    material_ids = fields.One2many('mrp.step', 'up_step_id', string='Material Ids')
    operation_point_group_ids = fields.One2many('mrp.step.group', 'step_id',
                                                string='Operation Points Group(multi-spindle)')

    @api.multi
    @api.depends('category_id')
    def _compute_category_name(self):
        for equipment in self:
            equipment.category_name = equipment.category_id.name or ''

    @api.multi
    @api.depends('category_id')
    def _compute_category_direction(self):
        for equipment in self:
            equipment.direction = equipment.category_id.direction or ''

    @api.multi
    def name_get(self):
        res = []
        for point in self:
            res.append((point.id, _('[%s] %s') % (point.step_name, point.code)))
        return res

    @api.model
    def default_get(self, fields):
        res = super(MrpStep, self).default_get(fields)

        operation_id = self.env.context.get('default_up_step_id')
        if operation_id:
            operation = self.env['mrp.step'].sudo().browse(operation_id)
            if 'max_redo_times' in fields:
                res.update({'max_redo_times': operation.max_redo_times})
            if 'sequence' in fields and operation.operation_point_ids:
                res.update({'sequence': max(operation.operation_point_ids.mapped('sequence')) + 1})
        return res

    @api.multi
    def unlink(self):
        for point in self:
            msg = _("#%s operation point has been delete") % (point.id)
            point.up_step_id.message_post(body=msg, subject=msg, message_type='comment')
        lines = self.env['mrp.bom.line'].search([('operation_point_id', 'in', self.ids)])
        if lines:
            lines.unlink()
        return super(MrpStep, self).unlink()

    @api.multi
    def toggle_active(self):
        bom_line_ids = self.env['mrp.bom.line'].search([('operation_point_id', 'in', self.ids)])
        if bom_line_ids:
            bom_line_ids.toggle_active()
        return super(MrpStep, self).toggle_active()


    @api.multi
    def delete_child_step(self):
        bom_line_ids = self.env['mrp.step'].search([('up_step_id', 'in', self.ids)])
        if bom_line_ids:
            bom_line_ids.unlink()
        return

    @api.depends('operation_point_ids')
    def _compute_child_step_count(self):
        for routing in self:
            routing.child_step_count = len(routing.operation_point_ids)



    @api.model
    def create(self, vals):
        ret = super(MrpStep, self).create(vals)
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
        tracked_fields = self.env['mrp.step'].fields_get(['max_redo_times', 'program_id', 'product_id'])
        for point in self:
            if 'max_redo_times' in vals or 'program_id' in vals or 'product_id' in vals:
                old_values = {
                    'max_redo_times': point.max_redo_times,
                    'program_id': point.program_id,
                    'product_id': point.product_id
                }
                ret = super(MrpStep, point).write(vals)  # 修改数据

                dummy, tracking_value_ids = point._message_track(tracked_fields, old_values)
                msg = _("#%s operation point has been modified") % (point.id)
                point.up_step_id.message_post(body=msg, message_type='comment', tracking_value_ids=tracking_value_ids,
                                                subject=msg)
            else:
                ret = super(MrpStep, point).write(vals)  # 修改数据
        return ret

        # return super(OperationPoints, self).write(vals)


class StepPointsGroup(models.Model):
    _name = 'mrp.step.group'

    _order = "sequence"

    sequence = fields.Integer('sequence', default=1)

    proposal_key_num = fields.Integer(default=0, copy=False)

    name = fields.Char('step Point Group')
    key_num = fields.Integer(string='Key Point Count', copy=False, compute="_compute_key_point_count",
                             inverse='_inverse_key_point_count',
                             store=True)
    # operation_point_ids_domain = fields.Char(
    #     compute="_compute_operation_point_ids_domain",
    #     readonly=True,
    #     store=False,
    # )

    step_id = fields.Many2one('mrp.step', ondelete='cascade', index=True)

    step_ids = fields.One2many('mrp.step', 'group_id',
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
            lk = len(record.step_ids.filtered(lambda r: r.is_key))
            if record.key_num < lk:
                raise ValidationError(_('Key Point Number Can Not Less Than Operation Point Key Total'))

    @api.multi
    @api.depends('step_ids.is_key', 'proposal_key_num')
    def _compute_key_point_count(self):
        for record in self:
            lk = len(record.step_ids.filtered(lambda r: r.is_key))
            record.key_num = max(record.proposal_key_num, lk)

    @api.multi
    def name_get(self):
        res = []
        for point in self:
            res.append((point.id, _('[%s] %s') % (point.step_id.step_name, point.name)))
        return res
