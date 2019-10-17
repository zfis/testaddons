# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, SUPERUSER_ID

from odoo.exceptions import UserError, ValidationError

import requests as Requests

from requests import ConnectionError, RequestException, exceptions

import json

MASTER_WROKORDERS_API = '/rush/v1/mrp.routing.workcenter'


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'
    """重写routing_id的定义"""
    routing_id = fields.Many2one(
        'mrp.routing', 'Parent Routing',
        index=True, ondelete='set null', required=False,
        help="The routing contains all the Work Centers used and for how long. This will create work orders afterwards"
        "which alters the execution of the manufacturing order. ")

    sa_routing_ids = fields.Many2many('mrp.routing', 'routing_operation_rel', 'operation_id', 'routing_id',
                                     string="Routes", copy=False)

    workcenter_group = fields.Many2one('mrp.workcenter.group', copy=False)
    workcenter_ids = fields.Many2many('mrp.workcenter', related='workcenter_group.sa_workcenter_ids',
                                     copy=False, readonly=True)

    sa_step_ids = fields.Many2many('mrp.step', 'step_operation_rel', 'operation_id', 'step_id',
                                     string="Steps", copy=False)
    workcenter_id = fields.Many2one('mrp.workcenter', copy=False, required=False)

    socket = fields.Char(string='Socket No')
    op_job_id = fields.Many2one('controller.job', string='Job', track_visibility="onchange")
    # op_job_id = fields.Many2one('controller.job', string='Job')

    operation_point_ids = fields.One2many('operation.point', 'operation_id', string='Operation Points')

    operation_point_group_ids = fields.One2many('operation.point.group', 'operation_id',
                                                string='Operation Points Group(multi-spindle)')

    group_id = fields.Many2one('mrp.routing.group', string='Routing Group')
    max_redo_times = fields.Integer('Operation Max Redo Times', default=3,
                                    track_visibility="onchange")  # 此项重试业务逻辑在HMI中实现

    worksheet_img = fields.Binary('worksheet_img')

    sync_download_time = fields.Datetime(string=u'同步下发时间')

    max_op_time = fields.Integer('Max Operation time(second)', default=60, track_visibility="onchange")

    routing_tracking_count = fields.Integer(compute='_compute_routing_tracking_count', string="Routing Modification")

    _sql_constraints = [('routing_group_wc_uniq', 'unique(routing_id,group_id, workcenter_id)',
                         'Per Routing only has one unique Routing group per Work Center!')]

    @api.multi
    def action_sa_view_routing_tracking(self):
        self.ensure_one()
        action = self.env.ref('mail.action_view_mail_message').read()[0]
        # # workcenter_id = self.env.ref('sa_base.cunrong_default_workcenter').id
        # ids = self.ids
        # # bom specific to this variant or global to template
        action['context'] = {
            'search_default_model': 'mrp.routing.workcenter',
            'search_default_res_id': self.id
        }
        # action['domain'] = [('routing_id', 'in', [self.ids])]
        return action

    @api.multi
    def _track_subtype(self, init_values):
        # if 'op_job_id' in init_values:
        #     return 'account_voucher.mt_voucher_state_change'
        return super(MrpRoutingWorkcenter, self)._track_subtype(init_values)

    @api.multi
    def _compute_routing_tracking_count(self):
        for routing in self:
            routing.routing_tracking_count = len(routing.message_ids)

    @api.one
    def _push_mrp_routing_workcenter(self, url):
        self.ensure_one()
        operation_id = self
        bom_ids = self.env['mrp.bom'].search([('operation_ids', 'in', operation_id.ids), ('active', '=', True)])
        if not bom_ids:
            return
        _points = []
        for point in operation_id.operation_point_ids:
            # bom_line = self.env['mrp.bom.line'].search([('operation_id', '=', operation_id.id), ('operation_point_id', '=', point.id)])
            # qcp = self.env['sa.quality.point'].search([('operation_id', '=', operation_id.id), ('bom_line_id', '=', bom_line.id)])
            _points.append({
                'sequence': point.sequence,
                'group_sequence': point.group_sequence,
                'offset_x': point.x_offset,
                'offset_y': point.y_offset,
                'max_redo_times': point.max_redo_times,
                'gun_sn': '',  # 默认模式下这里传送的枪的序列号是空字符串
                'controller_sn': '',
                # 'tolerance_min': qcp.tolerance_min,
                # 'tolerance_max': qcp.tolerance_max,
                # 'tolerance_min_degree': qcp.tolerance_min_degree,
                # 'tolerance_max_degree': qcp.tolerance_max_degree,
                'consu_product_id': point.product_id.id if point.product_id.id else 0,
                'nut_no': point.product_id.default_code if point.product_id else '',
            })

        for bom_id in bom_ids:
            val = {
                "id": operation_id.id,
                "workcenter_id": operation_id.workcenter_id.id,
                "job": int(operation_id.op_job_id.code) if operation_id.op_job_id else 0,
                "max_op_time": operation_id.max_op_time,
                "name": u"[{0}]{1}@{2}/{3}".format(operation_id.name, operation_id.group_id.code,
                                                   operation_id.workcenter_id.name,
                                                   operation_id.routing_id.name),
                "img": u'data:{0};base64,{1}'.format('image/png',
                                                     operation_id.worksheet_img) if operation_id.worksheet_img else "",
                "product_id": bom_id.product_id.id if bom_id else 0,
                "product_type": bom_id.product_id.default_code if bom_id else "",
                "workcenter_code": operation_id.workcenter_id.code if operation_id.workcenter_id else "",
                'vehicleTypeImg': u'data:{0};base64,{1}'.format('image/png',
                                                                bom_id.product_id.image_small) if bom_id.product_id.image_small else "",
                "points": _points
            }
            try:
                ret = Requests.put(url, data=json.dumps(val), headers={'Content-Type': 'application/json'}, timeout=1)
                if ret.status_code == 200:
                    # operation_id.write({'sync_download_time': fields.Datetime.now()})  ### 更新发送结果
                    self.env.user.notify_info(u'下发工艺成功')
            except ConnectionError as e:
                self.env.user.notify_warning(u'下发工艺失败, 错误原因:{0}'.format(e.message))
            except RequestException as e:
                self.env.user.notify_warning(u'下发工艺失败, 错误原因:{0}'.format(e.message))

        return True

    @api.multi
    def button_send_mrp_routing_workcenter(self):
        for operation in self:
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

    @api.multi
    def get_operation_points(self):
        if not self:
            return []
        self.ensure_one()
        vals = []
        for point in self.operation_point_ids:
            vals.append({
                'sequence': point.sequence,
                'x_offset': point.x_offset,
                'y_offset': point.y_offset
            })
        return vals

    @api.multi
    def button_resequence(self):
        self.ensure_one()
        has_sort_point_list = self.env['operation.point']
        group_idx = 0
        need_add = False
        for idx, point_group in enumerate(self.operation_point_group_ids):
            point_group.write({'sequence': idx + 1})
            for point in point_group.operation_point_ids:
                need_add = True
                point.write({'group_sequence': group_idx + 1})
                has_sort_point_list += point
            if need_add:
                need_add = False
                group_idx += 1
        not_sort_list = self.operation_point_ids - has_sort_point_list
        for idx, point in enumerate(not_sort_list.sorted(key=lambda r: r.sequence)):
            point.write({'group_sequence': group_idx + idx + 1})
        for idx, point in enumerate(self.operation_point_ids.sorted(key=lambda r: r.group_sequence)):
            point.write({'sequence': idx + 1})

    @api.multi
    def unlink(self):
        raise ValidationError(u'不允许删除作业')

    @api.multi
    def name_get(self):
        return [(operation.id,
                 u"[{0}]{1}@{2}/{3}".format(operation.name, operation.group_id.code, operation.workcenter_id.name,
                                            operation.routing_id.name)) for operation in self]  # 强制可视化时候名称显示的是code


class MrpPR(models.Model):
    _name = 'mrp.routing.group'
    _description = 'Manufacutre Routing Group'

    code = fields.Char(string='Routing Group Rerence', required=True)

    name = fields.Char(string='Routing Group')

    _sql_constraints = [('name_uniq', 'unique(name)',
                         'Routing Group name must be unique!'),
                        ('code_uniq', 'unique(code)',
                         'Routing Group code must be unique!')
                        ]

    @api.onchange('code')
    def _routing_group_code_change(self):
        for routing in self:
            routing.name = routing.code

    @api.onchange('name')
    def _routing_group_name_change(self):
        for routing in self:
            routing.code = routing.name

    @api.multi
    def name_get(self):
        return [(group.id, group.code) for group in self]  # 强制可视化时候名称显示的是code


class ControllerJob(models.Model):
    _name = 'controller.job'
    _description = 'Controller Job'

    name = fields.Char('Job Name')
    code = fields.Char('Job Code', required=True, help=u'Job')

    active = fields.Boolean('Active', default=True)

    description = fields.Html('Description')

    @api.multi
    def unlink(self):
        if self.env.uid != SUPERUSER_ID:
            raise UserError(_(u"Only SuperUser can delete Job ID"))
        return super(ControllerJob, self).unlink()


class ControllerProgram(models.Model):
    _name = 'controller.program'
    _description = 'Controller Program'

    name = fields.Char('Program Name')
    code = fields.Char('Program Code', required=True, help=u'程序号')
    strategy = fields.Selection([('AD', 'Torque tightening'),
                                 ('AW', 'Angle tightening'),
                                 ('ADW', 'Torque/Angle tightening'),
                                 ('LN', 'Loosening'),
                                 ('AN', 'Number of Pulses tightening'),
                                 ('AT', 'Time tightening')], required=True)

    active = fields.Boolean('Active', default=True)

    control_mode = fields.Selection([('pset', 'Parameter Set'), ('job', 'Assembly Process')],
                                    default='pset', string='Control Mode For Tightening')

    @api.onchange('code', 'strategy')
    def _onchange_code_style(self):
        for program in self:
            program.name = u"{0}({1})".format(program.code, program.strategy)

    @api.model
    def create(self, vals):
        if 'name' not in vals:
            vals['name'] = u"{0}({1})".format(vals['code'], vals['strategy'])
        return super(ControllerProgram, self).create(vals)

    @api.multi
    def unlink(self):
        if self.env.uid != SUPERUSER_ID:
            raise UserError(_(u"Only SuperUser can delete program"))
        return super(ControllerProgram, self).unlink()


class MrpRouting(models.Model):
    """ Specifies routings of work centers """
    _inherit = 'mrp.routing'

    '''重写operation_ids的定义'''
    sa_operation_ids = fields.Many2many('mrp.routing.workcenter', 'routing_operation_rel', 'routing_id', 'operation_id',
                                     string="Operations", copy=False)
    code = fields.Char('Reference', copy=False)

    operation_count = fields.Integer(string='Operations', compute='_compute_operation_count')

    @api.onchange('code')
    def _routing_code_change(self):
        for routing in self:
            routing.name = routing.code

    @api.onchange('name')
    def _routing_code_change(self):
        for routing in self:
            routing.code = routing.name

    @api.depends('operation_ids')
    def _compute_operation_count(self):
        for routing in self:
            routing.operation_count = len(routing.sa_operation_ids)

    @api.multi
    def action_sa_view_operation(self):
        action = self.env.ref('sa_base.sa_mrp_routing_workcenter_action').read()[0]
        # workcenter_id = self.env.ref('sa_base.cunrong_default_workcenter').id
        ids = self.ids
        # bom specific to this variant or global to template
        action['context'] = {
            'default_sa_routing_ids': [(4, ids[0], None)]
            # 'default_workcenter_id': self.workcenter_id.id
        }
        action['domain'] = [('sa_routing_ids', 'in', self.ids)]
        return action

    @api.multi
    def name_get(self):
        return [(routing.id, u'[{0}]{1}'.format(routing.code, routing.name)) for routing in self]  # 强制可视化时候名称显示的是code
