# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil import relativedelta
import datetime
import json
import urllib

import requests as Requests

from requests import ConnectionError, RequestException, exceptions

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

DELETE_ALL_MASTER_WROKORDERS_API = '/rush/v1/mrp.routing.workcenter/all'


class MrpWorkAssembly(models.Model):
    _name = 'mrp.assemblyline'
    _description = 'Work Assembly Line'
    _order = "id"

    name = fields.Char('Assembly Line', copy=False)
    code = fields.Char('Reference', copy=False, required=True)
    worksegment_count = fields.Integer('Work Sections', compute='_compute_worksegments_count')

    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the bills of material without removing it.")

    worksegment_ids = fields.One2many('mrp.worksection', 'workassembly_id', 'Work Sections', copy=False)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Only one code per Work Assembly Line is allowed')]

    @api.multi
    @api.depends('worksegment_ids')
    def _compute_worksegments_count(self):
        for line in self:
            line.worksegment_count = len(line.worksegment_ids)

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        res = []
        for line in self:
            name = u"[{0}] {1}".format(line.code, line.name)
            res.append((line.id, name))
        return res


class MrpWorkSegment(models.Model):
    _name = 'mrp.worksection'
    _description = 'Work Section'
    _order = "id"

    name = fields.Char('Work Section Name', copy=False)
    code = fields.Char('Work Section Reference', copy=False, required=True)
    workassembly_id = fields.Many2one('mrp.assemblyline', string='Work Assembly Line')
    workcenter_count = fields.Integer('Work Centers', compute='_compute_workcenters_count')

    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the bills of material without removing it.")

    workcenter_ids = fields.One2many('mrp.workcenter', 'worksegment_id', 'Work Centers', copy=False)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Only one code per Work Section is allowed')]

    @api.multi
    @api.depends('workcenter_ids')
    def _compute_workcenters_count(self):
        for segment in self:
            segment.workcenter_count = len(segment.workcenter_ids)

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        res = []
        for segment in self:
            name = u"[{0}] {1}".format(segment.code, segment.name)
            res.append((segment.id, name))
        return res


class MrpWorkCenter(models.Model):
    _inherit = 'mrp.workcenter'

    external_url = fields.Text('External URL', compute='_compute_external_url')

    type = fields.Selection([('normal', 'Normal'),
                             ('rework', 'Rework')], default='normal')

    qc_workcenter_id = fields.Many2one('mrp.workcenter', string='Quality Check Work Center')

    worksegment_id = fields.Many2one('mrp.worksection', copy=False)
    hmi_id = fields.Many2one('maintenance.equipment', string='Human Machine Interface(HMI)', copy=False,
                             domain=lambda self: [('category_id', '=', self.env.ref('sa_base.equipment_hmi').id)])
    masterpc_id = fields.Many2one('maintenance.equipment', string='Work Center Controller(MasterPC)', copy=False,
                                  domain=lambda self: [
                                      ('category_id', '=', self.env.ref('sa_base.equipment_MasterPC').id)])
    io_id = fields.Many2one('maintenance.equipment', string='Remote IO', copy=False,
                            domain=lambda self: [('category_id', '=', self.env.ref('sa_base.equipment_IO').id)])

    rfid_id = fields.Many2one('maintenance.equipment', string='Radio Frequency Identification(RFID)', copy=False,
                              domain=lambda self: [('category_id', '=', self.env.ref('sa_base.equipment_RFID').id)])

    controller_ids = fields.Many2many('maintenance.equipment', 'controller_center_rel', 'workcenter_id', 'controller_id',
                                      string='Tightening Controllers', copy=False)

    gun_ids = fields.Many2many('maintenance.equipment', 'tool_workcenter_rel', 'workcenter_id', 'tool_id',
                               string='Tightening Tools', copy=False)

    controller_ids_domain = fields.Char(
        compute="_compute_controller_ids_domain",
        readonly=True,
        store=False,
    )

    gun_ids_domain = fields.Char(
        compute="_compute_gun_ids_domain",
        readonly=True,
        store=False,
    )

    _sql_constraints = [('code_hmi', 'unique(hmi_id)', 'Only one HMI is allowed'),
                        ('code_rfid', 'unique(rfid_id)', 'Only one RFID is allowed'),
                        ('code_io', 'unique(io_id)', 'Only one Remote IO is allowed')]

    @api.constrains('controller_ids', 'gun_ids')
    def _constraint_equipments(self):
        self.ensure_one()
        workcenter_ids = self.env['mrp.workcenter'].sudo().search([('id', '!=', self.id)])
        for workcenter in workcenter_ids:
            # org_list = workcenter.controller_ids.ids
            # new_list = self.controller_ids.ids
            # new = len(new_list) if new_list else 0
            # org = len(org_list) if org_list else 0
            # org_list.extend(new_list)
            # if len(set(org_list)) != new + org:
            #     raise ValidationError('控制器设置重复')
            org_list = workcenter.gun_ids.ids
            new_list = self.gun_ids.ids
            new = len(new_list) if new_list else 0
            org = len(org_list) if org_list else 0
            org_list.extend(new_list)
            if len(set(org_list)) != new + org:
                raise ValidationError('拧紧枪设置重复')

    @api.one
    def _delete_workcenter_all_opertaions(self, url):
        try:
            ret = Requests.delete(url, headers={'Content-Type': 'application/json'}, timeout=1)
            if ret.status_code == 200:
                # operation_id.write({'sync_download_time': fields.Datetime.now()})  ### 更新发送结果
                self.env.user.notify_info(u'删除工艺成功')
                return True
        except ConnectionError as e:
            self.env.user.notify_warning(u'下发工艺失败, 错误原因:{0}'.format(e.message))
            return False
        except RequestException as e:
            self.env.user.notify_warning(u'下发工艺失败, 错误原因:{0}'.format(e.message))
            return False
        return False

    @api.multi
    def button_sync_operations(self):
        operation_obj_sudo = self.env['mrp.routing.workcenter'].sudo()
        for center in self:
            master = center.masterpc_id
            if not master:
                continue
            connections = master.connection_ids.filtered(
                lambda r: r.protocol == 'http') if master.connection_ids else None
            if not connections:
                continue
            url = ['http://{0}:{1}{2}'.format(connect.ip, connect.port, DELETE_ALL_MASTER_WROKORDERS_API) for connect in
                   connections][0]
            center._delete_workcenter_all_opertaions(url)
            operations = operation_obj_sudo.search([('workcenter_id', '=', center.id)])
            for operation in operations:
                operation.button_send_mrp_routing_workcenter()

    @api.multi
    def _compute_external_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.external_url = urllib.quote(
                u'{0}/web#id={1}&view_type=form&model=mrp.workcenter'.format(base_url, rec.id))

    @api.multi
    @api.depends('masterpc_id')
    def _compute_controller_ids_domain(self):
        category_id = self.env.ref('sa_base.equipment_screw_controller').id
        for rec in self:
            rec.controller_ids_domain = json.dumps(
                [('id', 'in', rec.masterpc_id.child_ids.ids), ('category_id', '=', category_id)])
            rec.controller_ids = [(5,)]  # 去除所有的枪 重新设置

    @api.multi
    @api.depends('controller_ids')
    def _compute_gun_ids_domain(self):
        category_id = self.env.ref('sa_base.equipment_Gun').id
        for rec in self:
            child_ids = rec.controller_ids.mapped('child_ids')
            rec.gun_ids_domain = json.dumps([('id', 'in', child_ids.ids), ('category_id', '=', category_id)])
            rec.gun_ids = [(5,)]  # 去除所有的枪 重新设置

