# -*- coding: utf-8 -*-
from odoo import http, fields, api, SUPERUSER_ID
import json
from odoo.http import request, Response
from urlparse import urljoin
import logging
import validators
import requests as Requests
from requests import ConnectionError, RequestException

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 80

DEFAULT_ORDER_BY = 'production_date DESC'
URGE_REQ_URL = '/aiis/v1/fis.urgs'


def str_time_to_rfc3339(s_time):
    sp = s_time.split(' ')
    return sp[0] + 'T' + sp[1] + 'Z'


class ApiMrpWorkorder(http.Controller):

    @http.route(['/api/v1/mrp.workorders/<int:order_id>', '/api/v1/mrp.workorders'], type='http', methods=['GET'],
                auth='none', cors='*', csrf=False)
    def _get_workorders(self, order_id=None, **kw):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        workcenter_id = None
        if order_id:
            order = env['mrp.workorder'].search([('id', '=', int(order_id))])
            if not order:
                body = json.dumps({'msg': 'Can not found workorder'})
                return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                                status=404)
            # points = env['point.point'].search_read(
            #     domain=[('res_model', '=', 'mrp.routing.workcenter'), ('res_id', '=', order.operation_id.id),
            #             ('res_field', '=', 'worksheet_img')],
            #     fields=['x_offset', 'y_offset'])

            # 工单中的消耗品列表
            _consumes = list()
            if order.consu_bom_line_ids:
                for consu in order.consu_bom_line_ids:
                    # 定位消耗品的qcp
                    _qcps = env['sa.quality.point'].search([('bom_line_id', '=', consu.bom_line_id.id),
                                                            ('operation_id', '=', order.operation_id.id)],
                                                           limit=1)

                    _consumes.append({
                        "sequence": consu.bom_line_id.operation_point_id.sequence,
                        "group_sequence": consu.bom_line_id.operation_point_id.group_sequence,
                        'max_redo_times': consu.bom_line_id.operation_point_id.max_redo_times,
                        'offset_x': consu.bom_line_id.operation_point_id.x_offset,
                        'offset_y': consu.bom_line_id.operation_point_id.y_offset,
                        "pset": consu.bom_line_id.program_id.code,
                        "nut_no": consu.product_id.default_code,
                        "gun_sn": consu.bom_line_id.gun_id.serial_no,
                        "controller_sn": consu.bom_line_id.controller_id.serial_no,
                        'tolerance_min': _qcps.tolerance_min if _qcps else 0.0,
                        'tolerance_max': _qcps.tolerance_max if _qcps else 0.0,
                        'tolerance_min_degree': _qcps.tolerance_min_degree if _qcps else 0.0,
                        'tolerance_max_degree': _qcps.tolerance_max_degree if _qcps else 0.0,
                        "result_ids": consu.result_ids.ids
                    })

            ret = {
                'id': order.id,
                'hmi': {'id': order.workcenter_id.hmi_id.id,
                        'uuid': order.workcenter_id.hmi_id.serial_no} if order.workcenter_id else None,
                'workcenter': {'name': order.workcenter_id.name,
                               'code': order.workcenter_id.code} if order.workcenter_id else None,
                # 'vehicleTypeImg': u'data:{0};base64,{1}'.format('image/png', order.product_id.image_small) if order.product_id.image_small else None,
                # 'worksheet': u'data:{0};base64,{1}'.format('image/png', order.operation_id.worksheet_img) if order.operation_id.worksheet_img else "",
                # 'max_redo_times': order.operation_id.max_redo_times,
                'img_op_id': order.operation_id.id,
                'max_op_time': order.operation_id.max_op_time,
                'job': order.operation_id.op_job_id.code if order.operation_id.op_job_id else False,
                # 'nut_total': order.consu_product_qty,
                'vin': order.production_id.vin,
                'knr': order.production_id.knr,
                'long_pin': order.production_id.long_pin,
                # 'result_ids': order.result_ids.ids,
                'status': order.state,  # pending, ready, process, done, cancel

                'equipment_name': order.production_id.equipment_name,
                'factory_name': order.production_id.factory_name,
                'year': order.production_id.year,
                'pin': order.production_id.pin,
                'pin_check_code': order.production_id.pin_check_code,
                'assembly_line': order.production_id.assembly_line_id.code,
                'lnr': order.production_id.lnr,
                # 'nut_no': order.consu_product_id.default_code,
                'consumes': _consumes,
                'model': order.production_id.product_id.default_code,
                'update_time': str_time_to_rfc3339(order.production_date)
            }
            body = json.dumps(ret)
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=200)
        domain = []
        if 'masterpc' in kw:
            masterpc_uuid = kw['masterpc']
            workcenter_id = env['mrp.workcenter'].search([('masterpc_id.serial_no', '=', masterpc_uuid)], limit=1)
            if not workcenter_id:
                body = json.dumps({'msg': 'Can not found Workcenter'})
                return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                                status=405)
            domain += [('workcenter_id', 'in', workcenter_id.ids)]  # 添加查询域

        if 'hmi' in kw:
            hmi = env['maintenance.equipment'].search([('serial_no', '=', kw['hmi'])], limit=1)
            if hmi:
                workcenter_id = env['mrp.workcenter'].search([('hmi_id', '=', hmi.ids[0])])
                domain += [('workcenter_id', 'in', workcenter_id.ids)]
            else:
                body = json.dumps({'msg': 'Can not found hmi'})
                return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                                status=405)
        if 'workcenter' in kw:
            code = kw['workcenter']
            workcenter_id = env['mrp.workcenter'].search(['|', ('code', '=', code), ('name', '=', code)], limit=1)
            if not workcenter_id:
                body = json.dumps({'msg': 'Can not found Workcenter'})
                return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                                status=405)
            domain += [('workcenter_id', 'in', workcenter_id.ids)]  # 添加查询域

        if 'code' in kw:
            code = kw['code']
            domain += ['|', '|', ('production_id.long_pin', '=', code), ('production_id.knr', '=', code),
                       ('production_id.vin', '=', code)]
        if 'limit' in kw.keys():
            limit = int(kw['limit'])
        else:
            limit = DEFAULT_LIMIT
        if 'order' in kw.keys():
            order_by = kw['order'] + ' DESC'
        else:
            order_by = DEFAULT_ORDER_BY

        workorder_ids = env['mrp.workorder'].search(domain, limit=limit, order=order_by)
        if not workorder_ids:
            logger.info(u"未发现工单,调用快速请求进行创建")
            body = json.dumps({'msg': 'Can not found workorder'})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=404)
        _ret = list()
        for order in workorder_ids:
            # points = env['point.point'].search_read(
            #     domain=[('res_model', '=', 'mrp.routing.workcenter'), ('res_id','=', order.operation_id.id), ('res_field', '=', 'worksheet_img')],
            #     fields=['x_offset', 'y_offset', 'sequence'])

            # 工单中的消耗品列表
            _consumes = list()
            if order.consu_bom_line_ids:
                for consu in order.consu_bom_line_ids:
                    # 定位消耗品的qcp
                    _qcps = env['sa.quality.point'].search([('bom_line_id', '=', consu.bom_line_id.id),
                                                            ('operation_id', '=', order.operation_id.id)],
                                                           limit=1)

                    _consumes.append({
                        "sequence": consu.bom_line_id.operation_point_id.sequence,
                        "group_sequence": consu.bom_line_id.operation_point_id.group_sequence,
                        'max_redo_times': consu.bom_line_id.operation_point_id.max_redo_times,
                        'offset_x': consu.bom_line_id.operation_point_id.x_offset,
                        'offset_y': consu.bom_line_id.operation_point_id.y_offset,
                        "pset": consu.bom_line_id.program_id.code,
                        "nut_no": consu.product_id.default_code,
                        "gun_sn": consu.bom_line_id.gun_id.serial_no,
                        "controller_sn": consu.bom_line_id.controller_id.serial_no,
                        'tolerance_min': _qcps.tolerance_min if _qcps else 0.0,
                        'tolerance_max': _qcps.tolerance_max if _qcps else 0.0,
                        'tolerance_min_degree': _qcps.tolerance_min_degree if _qcps else 0.0,
                        'tolerance_max_degree': _qcps.tolerance_max_degree if _qcps else 0.0,
                        "result_ids": consu.result_ids.ids
                    })

            _ret.append({
                'id': order.id,
                'hmi': {'id': workcenter_id.hmi_id.id,
                        'uuid': workcenter_id.hmi_id.serial_no} if workcenter_id else None,
                'workcenter': {'name': workcenter_id.name, 'code': workcenter_id.code} if workcenter_id else None,
                'vehicleTypeImg': u'data:{0};base64,{1}'.format('image/png',
                                                                order.product_id.image_small) if order.product_id.image_small else None,
                # 'worksheet': u'data:{0};base64,{1}'.format('image/png', order.operation_id.worksheet_img) if order.operation_id.worksheet_img else "",
                'img_op_id': order.operation_id.id,
                # 'max_redo_times': order.operation_id.max_redo_times,
                'max_op_time': order.operation_id.max_op_time,
                'job': order.operation_id.op_job_id.code if order.operation_id.op_job_id else False,
                # 'nut_total': order.consu_product_qty,
                'vin': order.production_id.vin,
                'knr': order.production_id.knr,
                'long_pin': order.production_id.long_pin,
                # 'result_ids': order.result_ids.ids,
                'status': order.state,  # pending, ready, process, done, cancel

                'equipment_name': order.production_id.equipment_name,
                'factory_name': order.production_id.factory_name,
                'year': order.production_id.year,
                'pin': order.production_id.pin,
                'pin_check_code': order.production_id.pin_check_code,
                'assembly_line': order.production_id.assembly_line_id.code,
                'lnr': order.production_id.lnr,
                # 'nut_no': order.consu_product_id.default_code,
                'consumes': _consumes,
                'model': order.production_id.product_id.default_code,
                'update_time': str_time_to_rfc3339(order.production_date)
            })
        if len(_ret) == 0:
            body = json.dumps([])
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        body = json.dumps(_ret)
        return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))], status=200)
