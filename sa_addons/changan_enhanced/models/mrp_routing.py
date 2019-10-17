# -*- coding: utf-8 -*-

from odoo import models, fields, api

import json

import requests as Requests

from requests import ConnectionError, RequestException


# MASTER_WROKORDERS_API = '/rush/v1/mrp.routing.workcenter'
#


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    gun_id = fields.Many2one('maintenance.equipment', string='Screw Gun', copy=False,
                             domain=lambda self: [('category_id', '=', self.env.ref('sa_base.equipment_Gun').id)])

    @api.onchange('workcenter_id')
    def _onchange_workcenter_id(self):
        self.ensure_one()
        gun_ids = self.workcenter_id.gun_ids
        self.gun_id = gun_ids.ids[0] if gun_ids else None

    @api.multi
    def name_get(self):
        return [(operation.id,
                 u"[{0}]{1}@{2}/{3}".format(operation.name, operation.op_job_id.code, operation.workcenter_id.name,
                                            operation.routing_id.name)) for operation in self]  # 强制可视化时候名称显示的是code

    @api.one
    def _push_mrp_routing_workcenter(self, url):
        self.ensure_one()
        operation_id = self
        bom_ids = self.env['mrp.bom'].search([('operation_ids', 'in', operation_id.ids)])
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
                'gun_sn': operation_id.gun_id.serial_no if operation_id.gun_id and operation_id.gun_id.serial_no else '',
                'controller_sn': operation_id.gun_id.parent_id.serial_no if operation_id.gun_id and operation_id.gun_id.parent_id and operation_id.gun_id.parent_id.serial_no else '',
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
