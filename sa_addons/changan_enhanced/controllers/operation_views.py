# -*- coding: utf-8 -*-

from odoo import http, api, SUPERUSER_ID
import json
from odoo.http import request, Response

DEFAULT_LIMIT = 80


class OperationViews(http.Controller):
    @http.route(['/api/v1/operation/<string:center_code>'], type='http', methods=['GET'], auth='none', cors='*',
                csrf=False)
    def _get_operation_by_center_code(self, center_code=None, **kw):
        bom_id = False
        job_id = False
        operation_id = None
        domain = ['|', ('workcenter_id.code', '=', center_code), ('workcenter_id.name', '=', center_code)]
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        if 'limit' in kw.keys():
            limit = int(kw['limit'])
        else:
            limit = 1
        if 'carType' in kw:
            bom_id = env['mrp.bom'].search([('product_id.default_code', '=', kw['carType'])], limit=1)
        if 'Job' in kw:
            job_id = env['controller.job'].search(['|', ('code', '=', str(kw['Job'])), ('name', '=', str(kw['Job']))],
                                                  limit=1)

        if all([bom_id, job_id]):
            body = json.dumps({'msg': "not found correct BOM or Job"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=400, headers=headers)
        else:
            if bom_id:
                operation_ids = bom_id.bom_line_ids.mapped('operation_id')
                operation_id = operation_ids.filtered(
                    lambda r: center_code in [r.workcenter_id.code, r.workcenter_id.name]) if operation_ids else None
            elif job_id:
                domain += [('op_job_id', '=', job_id.id)]
                operation_id = env['mrp.routing.workcenter'].search(domain, limit=limit)
        if not operation_id:
            body = json.dumps({'msg': "not found correct operation"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=400, headers=headers)
        _points = []
        for point in operation_id.operation_point_ids:
            _points.append({
                'sequence': point.sequence,
                'group_sequence': point.group_sequence,
                'offset_x': point.x_offset,
                'offset_y': point.y_offset,
                'max_op_time': point.max_redo_times
            })

        if not bom_id and operation_id:
            bom_id = env['mrp.bom'].search([('operation_ids', 'in', operation_id.ids)], limit=1)

        val = {
            "id": operation_id.id,
            "workcenter_id": operation_id.workcenter_id.id,
            "job": int(operation_id.op_job_id.code) if operation_id.op_job_id else None,
            "max_op_time": operation_id.max_op_time,
            "name": u"[{0}]{1}@{2}/{3}".format(operation_id.name, operation_id.group_id.code,
                                               operation_id.workcenter_id.name,
                                               operation_id.routing_id.name),
            "img": u'data:{0};base64,{1}'.format('image/png',
                                                 operation_id.worksheet_img) if operation_id.worksheet_img else "",
            "product_id": bom_id.product_id.id if bom_id.product_id else None,
            'vehicleTypeImg': u'data:{0};base64,{1}'.format('image/png',
                                                            bom_id.product_id.image_small) if bom_id and bom_id.product_id.image_small else None,
            "points": _points
        }
        body = json.dumps(val)
        headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
        return Response(body, status=200, headers=headers)
