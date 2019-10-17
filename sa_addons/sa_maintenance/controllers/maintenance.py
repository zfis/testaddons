# -*- coding: utf-8 -*-
import werkzeug

from odoo import http, fields, api, SUPERUSER_ID
import json
from odoo.http import request, Response

from odoo.api import Environment

from odoo import SUPERUSER_ID
from odoo import registry as registry_get


class SaMaintenance(http.Controller):
    @http.route([
        "/maintenance/requests/<int:ticket_id>",
        "/maintenance/requests/<int:ticket_id>/<token>"
    ], type='http', auth="public")
    def get_maintenance_requests(self, db, ticket_id, token=None):
        registry = registry_get(db)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            Ticket = False
            if token:
                Ticket = env['maintenance.request'].sudo().search(
                    [('id', '=', ticket_id), ('access_token', '=', token)])
            else:
                Ticket = env['maintenance.request'].browse(ticket_id)
            if not Ticket:
                return request.not_found()

            return werkzeug.utils.redirect(
                '/web?db=%s#id=%s&view_type=form&model=maintenance.request' % (db, ticket_id))

    @http.route(["/api/v1/maintenance/requests"], type='json', methods=['POST', 'OPTIONS'], auth='none', cors='*',
                csrf=False)
    def _create_maintenance_requests(self):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        kw = request.jsonrequest
        if 'serial_no' not in kw or 'type' not in kw:
            body = json.dumps({'msg': "payload must contain serial number!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=405, headers=headers)
        if kw['type'] not in ['corrective', 'calibration', 'preventive']:
            body = json.dumps({'msg': "maintenance type: {0} is not support!!!!".format(kw['type'])})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        gun_id = env['maintenance.equipment'].search([('serial_no', '=', kw["serial_no"])], limit=1)
        if not gun_id:
            body = json.dumps({'msg': "not found equipment(gun)!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        vals = {
            "name": "{0}Maintenance:{1}@{2}".format(kw['type'], gun_id.serial_no, fields.Date.context_today(gun_id)),
            "maintenance_type": kw['type'],
            "equipment_id": gun_id.id,
            # "description": kw['description']
        }

        ret = env['maintenance.request'].create(vals)
        if not ret:
            body = json.dumps({'msg': "create maintenance request fail!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=400, headers=headers)
        else:
            body = json.dumps({'msg': "create maintenance request success!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=201, headers=headers)

    @http.route(["/api/v1/maintenance/requests/try"], type='json', methods=['POST', 'OPTIONS'], auth='none', cors='*',
                csrf=False)
    def _try_create_maintenance_requests(self):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        kw = request.jsonrequest
        if 'serial_no' not in kw or 'times' not in kw or 'sin_last_service' not in kw:
            body = json.dumps({'msg': "payload must contain serial number!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=405, headers=headers)
        gun_id = env['maintenance.equipment'].search([('serial_no', '=', kw["serial_no"])], limit=1)
        if not gun_id:
            body = json.dumps({'msg': "not found equipment(gun)!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        total_times = kw['times']
        times_since_last_service = kw['sin_last_service']
        if total_times > gun_id.next_action_times + gun_id.times_margin and gun_id.times > 0:
            mType = 'preventive'
        elif times_since_last_service > gun_id.times and gun_id.times > 0:
            mType = 'preventive'
        elif total_times > gun_id.next_calibration_action_times + gun_id.times_margin and gun_id.calibration_times > 0:
            mType = 'calibration'
        elif times_since_last_service > gun_id.calibration_times and gun_id.calibration_times > 0:
            mType = 'calibration'
        else:
            # body = json.dumps({'msg': "do not need create maintenance request!!!!"})
            headers = [('Content-Type', 'application/json')]
            return Response(status=204, headers=headers)

        m_r = env['maintenance.request'].search([('equipment_id', '=', gun_id.id),
                                                 ('action_times', '=', total_times),
                                                 ('maintenance_type', '=', mType)])
        if m_r:
            body = json.dumps({'msg': "maintenance request is existed !!!!"})
            headers = [('Content-Type', 'application/json')]
            return Response(body, status=403, headers=headers)
        vals = {
            "name": "{0}Maintenance:{1}@{2}".format(mType, gun_id.serial_no, fields.Date.context_today(gun_id)),
            "maintenance_type": mType,
            "equipment_id": gun_id.id,
            "action_times": total_times
        }

        ret = env['maintenance.request'].create(vals)
        if not ret:
            body = json.dumps({'msg': "create maintenance request fail!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=400, headers=headers)
        else:
            body = json.dumps({'msg': "create maintenance request success!!!!"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=201, headers=headers)
