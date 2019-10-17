# -*- coding: utf-8 -*-
from odoo import http, SUPERUSER_ID, api
from odoo.http import request, Response

import json


class LocalSense(http.Controller):
    @http.route('/api/v1/workcenters', type='http', methods=['GET', 'OPTIONS'], auth='none', cors='*', csrf=False)
    def _get_workcenter_info(self, **kw):
        domain = [('category_name', '=', 'Gun')]
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        if 'location_tag' in kw.keys():
            domain += [('location_tag', '=', kw['location_tag'])]
        gun_id = env['maintenance.equipment'].search(domain, limit=1)
        if not gun_id:
            body = json.dumps({'msg': "location tag not correct"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        controller_id = gun_id.parent_id
        if not controller_id:
            body = json.dumps({'msg': "can not found controller for this gun , gun sn:%s" % gun_id.serial_no})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        workercenter_id = env['mrp.workcenter'].search([('gun_ids', 'in', gun_id.ids)], limit=1)
        if not workercenter_id:
            body = json.dumps({'msg': "can not found gun in any work center, gun sn:%s" % gun_id.serial_no})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        if not all([workercenter_id.masterpc_id, workercenter_id.controller_ids, workercenter_id.gun_ids]):
            body = json.dumps({'msg': "Workcenter Cofiguration is not Complete"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        c = workercenter_id.masterpc_id.connection_ids.filtered(lambda r: r.protocol == 'http')
        if c:
            masterpc_connection = c[0]
        else:
            masterpc_connection = None

        val = {
            'info': {
                'workcenter_code': workercenter_id.code,
                'workcenter': workercenter_id.name,
                'worksegment': workercenter_id.worksegment_id.name if workercenter_id.worksegment_id else None,
            },
            'masterpc': {'serial_no': workercenter_id.masterpc_id.serial_no,
                         'connection': masterpc_connection.name_get()[0][1] if masterpc_connection else False},
            'gun': {'serial_no': gun_id.serial_no, 'connection': ""},
            "controllers": {
                "serial_no": controller_id.serial_no,
                "connection": ""
            }
        }

        body = json.dumps(val)
        headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
        return Response(body, status=200, headers=headers)
