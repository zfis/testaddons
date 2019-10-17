# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

import requests as Requests

from requests import ConnectionError, RequestException, exceptions

import json

MASTER_DEL_WROKORDERS_API = '/rush/v1/mrp.routing.workcenter.delete'

MASTER_WROKORDERS_API = '/rush/v1/mrp.routing.workcenter'


class MrpBom(models.Model):
    _inherit = 'mrp.bom'
    operation_ids = fields.Many2many('mrp.routing.workcenter', related='routing_id.sa_operation_ids',
                                     copy=False, readonly=True)


    has_operations = fields.Boolean(compute='_compute_has_operations')

    @api.multi
    @api.depends('operation_ids')
    def _compute_has_operations(self):
        for bom_id in self:
            bom_id.has_operations = True if len(bom_id.operation_ids) else False

    #
    # @api.multi
    # def button_add_operation(self):
    #     self.ensure_one()
    #     compose_form = self.env.ref('sa_base.mrp_bom_operation_wizard_from', False)
    #     ctx = dict(
    #         self.env.context,
    #         default_routing_id=self.routing_id.id if self.routing_id else False
    #         )
    #
    #     return {
    #         'name': _('MRP Operation Setting'),
    #         'type': 'ir.actions.act_window',
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'mrp.routing.wc.form',
    #         'views': [(compose_form.id, 'form')],
    #         'view_id': compose_form.id,
    #         'target': 'new',
    #         'context': ctx,
    #     }

    @api.multi
    def button_resequence(self):
        self.ensure_one()
        for idx, bom_line_id in enumerate(self.bom_line_ids):
            bom_line_id.write({'sequence': idx + 1})

    @api.onchange('routing_id', 'product_id')
    def _onchange_routing_id(self):
        self.code = u'[{0}]{1}'.format(self.routing_id.name, self.product_id.name)
        self.operation_ids = [(5,)]  # 刪除所有作業
        self.bom_line_ids = [(5,)]  # 删除所有BOM行

    @api.constrains('product_id', 'product_tmpl_id')
    def _product_tmpl_product_constraint(self):
        if self.product_id.product_tmpl_id.id != self.product_tmpl_id.id:
            raise ValidationError(_(u'The product template "%s" is invalid on product with name "%s"') % (
            self.product_tmpl_id.name, self.product_id.name))

    @api.constrains('product_id', 'routing_id', 'active')
    def _constraint_active_product_routing(self):
        if not self.active:
            return
            ###只有激活状态才检查
        count = self.env['mrp.bom'].search_count(
            [('id', '!=', self.id), ('product_id', '=', self.product_id.id), ('routing_id', '=', self.routing_id.id),
             ('active', '=', True)])
        if count:
            raise ValidationError(
                _(u'The product had a related routing config "%s" been actived!') % (self.product_id.name))

    @api.constrains('product_tmpl_id', 'routing_id', 'active')
    def _constraint_active_product_tmpl_routing(self):
        if not self.active:
            return
            ###只有激活状态才检查
        count = self.env['mrp.bom'].search_count(
            [('id', '!=', self.id), ('product_tmpl_id', '=', self.product_tmpl_id.id),
             ('routing_id', '=', self.routing_id.id), ('active', '=', True)])
        if count:
            raise ValidationError(
                _(u'The product Template had a related routing config "%s" been actived!') % (
                    self.product_tmpl_id.name))

    def _onchange_operations(self):
        self.ensure_one()
        operation_ids = self.operation_ids
        need_delete_bom_line = self.env['mrp.bom.line']
        for bom_line in self.bom_line_ids:
            if bom_line.operation_id.id not in operation_ids.ids:
                need_delete_bom_line += bom_line
        need_delete_bom_line.unlink()  # delete bom line ids

        bom_line_operations = self.bom_line_ids.mapped('operation_id')

        delta_operation = self.operation_ids - bom_line_operations
        for operation in delta_operation:
            for operation_point in operation.sa_step_ids.mapped('operation_point_ids'):
                if not operation_point.product_id:
                    raise UserError(u'未定义作业点{0}的螺栓,请定义'.format(operation_point.name))
                val = {
                    "operation_point_id": operation_point.id,
                    "product_id": operation_point.product_id.id,
                    "bom_id": self.id,
                }
                self.env['mrp.bom.line'].sudo().create(val)

    @api.model
    def create(self, vals):
        auto_operation_inherit = self.env['ir.values'].get_default('sa.config.settings', 'auto_operation_inherit')
        if auto_operation_inherit and 'routing_id' in vals:
            routing_id = self.env['mrp.routing'].browse(vals['routing_id'])
            operation_ids = routing_id.operation_ids
            vals.update({'operation_ids': [(6, None, operation_ids.ids)]})
        ret = super(MrpBom, self).create(vals)
        # if 'operation_ids' in vals:
        ret._onchange_operations()
        return ret

    @api.multi
    def write(self, vals):
        ret = super(MrpBom, self).write(vals)
        # if 'operation_ids' in vals:
        self._onchange_operations()
        return ret

    @api.multi
    def unlink(self):
        raise ValidationError(u'不允许删除物料清单')

    @api.one
    def button_send_mrp_routing_workcenter(self):
        if not self.operation_ids:
            return True
        for operation in self.operation_ids:
            master = operation.workcenter_id.masterpc_id if operation.workcenter_id else None
            if not master:
                continue
            connections = master.connection_ids.filtered(
                lambda r: r.protocol == 'http') if master.connection_ids else None
            if not connections:
                continue
            url = \
            ['http://{0}:{1}{2}'.format(connect.ip, connect.port, MASTER_WROKORDERS_API) for connect in connections][0]

            operation._push_mrp_routing_workcenter(url)
        return True


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the bills of material without removing it.")

    operation_point_id = fields.Many2one('mrp.step', required=1, ondelete='cascade')

    product_id = fields.Many2one('product.product', related="operation_point_id.product_id", store=True)

    product_qty = fields.Float('Product Quantity', related="operation_point_id.product_qty", store=True)

    category_name = fields.Char('Step Category', related="operation_point_id.up_step_id.category_name", store=True)

    operation_id = fields.Many2one('mrp.routing.workcenter', related="operation_point_id.operation_id", store=True)

    op_job_id = fields.Many2one('controller.job', string='Job', related="operation_id.op_job_id")
    group_id = fields.Many2one('mrp.routing.group', related="operation_id.group_id", string='Routing Group')

    program_id = fields.Many2one('controller.program', related="operation_point_id.program_id", string='程序号')

    workcenter_id = fields.Many2one('mrp.workcenter', related="operation_id.workcenter_id", string='Work Center')

    masterpc_id = fields.Many2one('maintenance.equipment', string='Work Center Controller(MasterPC)',
                                  related="operation_id.workcenter_id.masterpc_id")

    controller_id = fields.Many2one('maintenance.equipment', string='Tightening Controller', copy=False)

    gun_id = fields.Many2one('maintenance.equipment', string='Tightening Tool(Gun/Wrench)', copy=False)

    # _sql_constraints = [
    #     ('unique_operation_bom_id', 'unique(bom_id,operation_id)', 'Every Bom unique operation'),
    # ]

    controller_id_domain = fields.Char(
        compute="_compute_gun_id_domain",
        readonly=True,
        store=False,
    )

    gun_id_domain = fields.Char(
        compute="_compute_gun_id_domain",
        readonly=True,
        store=False,
    )

    @api.onchange('operation_id')
    def _onchange_operation(self):
        self.ensure_one()
        self.controller_id = False
        self.gun_id = False

    @api.onchange('masterpc_id')
    def _onchange_masterpc(self):
        self.ensure_one()
        self.controller_id = False

    @api.onchange('controller_id')
    def _onchange_controller(self):
        self.ensure_one()
        self.gun_id = False

    @api.multi
    @api.depends('operation_id.workcenter_id')
    def _compute_gun_id_domain(self):
        for rec in self:
            rec.gun_id_domain = json.dumps([('id', 'in', rec.workcenter_id.gun_ids.ids)])
            rec.controller_id_domain = json.dumps([('id', 'in', rec.workcenter_id.controller_ids.ids)])

    @api.model
    def create(self, vals):
        line = super(MrpBomLine, self).create(vals)
        vals = {
            'product_id': line.bom_id.product_id.id,
            'product_tmpl_id': line.bom_id.product_tmpl_id.id,
            'operation_id': line.operation_id.id,
            'bom_line_id': line.id,
            'picking_type_id':
                self.env['stock.picking.type'].search_read(domain=[('code', '=', 'mrp_operation')], fields=['id'],
                                                           limit=1)[0]['id'],
            'workcenter_id': line.operation_id.workcenter_id.id,
            'times': line.product_qty,
            'test_type': 'measure',
        }
        self.env['sa.quality.point'].sudo().create(vals)
        return line

    @api.multi
    def write(self, vals):
        res = super(MrpBomLine, self).write(vals)
        # if 'product_qty' in vals:
        #     for line in self:
        #         rec = self.env['sa.quality.point'].search([('bom_line_id', '=', line.id)])
        #         rec.sudo().write({'times': line.product_qty})
        # return res

    @api.multi
    def _push_del_routing_workcenter(self, line, url):
        val = [{
            'product_type': line.bom_id.product_id.default_code,
            "id": line.operation_id.id,
        }]
        try:
            ret = Requests.put(url, data=json.dumps(val), headers={'Content-Type': 'application/json'}, timeout=1)
            if ret.status_code == 204:
                self.env.user.notify_info(u'删除工艺成功')
                return True
        except ConnectionError as e:
            self.env.user.notify_warning(u'下发工艺失败, 错误原因:{0}'.format(e.message))
            return False
        except RequestException as e:
            self.env.user.notify_warning(u'下发工艺失败, 错误原因:{0}'.format(e.message))
            return False

    @api.multi
    def unlink(self):
        # quality_points = self.env['sa.quality.point']
        # for line in self:
        #     master = line.workcenter_id.masterpc_id if line.workcenter_id else None
        #     if not master:
        #         raise UserError(u"未找到工位上的工位控制器")
        #     connections = master.connection_ids.filtered(
        #         lambda r: r.protocol == 'http') if master.connection_ids else None
        #     if not connections:
        #         raise UserError(u"未找到工位上的工位控制器的连接信息")
        #     url = ['http://{0}:{1}{2}'.format(connect.ip, connect.port, MASTER_DEL_WROKORDERS_API) for connect in
        #            connections][0]
        #     ret = self._push_del_routing_workcenter(line=line, url=url)
        #     if not ret:
        #         self.env.user.notify_warning(u"未删除物料清单行")
        # for line in self:
        #     rec = self.env['sa.quality.point'].search([('bom_line_id', '=', line.id)])
        #     quality_points += rec
        # quality_points.sudo().unlink()
        ret = super(MrpBomLine, self).unlink()
        return ret
