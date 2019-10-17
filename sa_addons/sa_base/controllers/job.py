# -*- coding: utf-8 -*-
from odoo import http, api, SUPERUSER_ID
import json
from odoo.http import request, Response

DEFAULT_LIMIT = 80


class Job(http.Controller):
    @http.route(['/api/v1/controller.job'], type='http', methods=['GET', 'OPTIONS'], auth='none', cors='*', csrf=False)
    def _get_jobs(self, **kw):
        domain = [('active', '=', True)]
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        if 'limit' in kw.keys():
            limit = int(kw['limit'])
        else:
            limit = DEFAULT_LIMIT
        jobs = env['controller.job'].search(domain, limit=limit)
        if not jobs:
            body = json.dumps({'msg': "Job not existed"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        vals = [{
            'name': job.name,
            'code': job.code,
        } for job in jobs]
        body = json.dumps(vals)
        return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))], status=200)
