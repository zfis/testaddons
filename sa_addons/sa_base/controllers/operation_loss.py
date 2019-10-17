# -*- coding: utf-8 -*-

from odoo import http, fields, api, SUPERUSER_ID
import json
from odoo.http import request, Response

DEFAULT_LIMIT = 80


class OperationLoss(http.Controller):
    @http.route('/api/v1/mrp.workcenter.productivity.loss', type='http', methods=['GET', 'OPTIONS'], auth='none',
                cors='*', csrf=False)
    def _get_production_loss(self, **kw):
        domain = [('manual', '=', True)]
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        if 'limit' in kw.keys():
            limit = int(kw['limit'])
        else:
            limit = DEFAULT_LIMIT
        if 'lossType' not in kw or len(kw['lossType'].split(',')) != 1 or kw['lossType'] not in ['availability',
                                                                                                 'performance',
                                                                                                 'quality',
                                                                                                 'productive']:
            body = json.dumps({'msg': "lossType parameter not correct"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=400, headers=headers)
        domain += [('loss_type', '=', kw['lossType'])]
        losses = env['mrp.workcenter.productivity.loss'].search(domain, limit=limit)
        vals = []
        for loss in losses:
            vals.append({
                'loss_id': loss.id,
                'name': loss.name
            })
        body = json.dumps(vals)
        headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
        return Response(body, status=200, headers=headers)
