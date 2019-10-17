# -*- coding: utf-8 -*-
from odoo import http, SUPERUSER_ID, api
from odoo.http import request, Response

from api_data import api_data
import json


class BaseApi(http.Controller):
    # 如果想使用此API,必须在配置文件中指定数据库方可使用
    @http.route('/api/v1/doc', type='http', auth='none', cors='*', csrf=False)
    def _api_doc(self):
        return json.dumps(api_data)

    @http.route('/api/v1/logo', type='http', auth='none', cors='*', csrf=False)
    def _get_default_logo(self):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        company = env['res.company'].search([])
        logo = company[0].logo
        if not logo:
            body = json.dumps({'msg': 'Logo not found'})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=404)
        ret = {
            "logo": u'data:{0};base64,{1}'.format('image/png', company[0].logo) if company[0].logo else ""
        }
        body = json.dumps(ret)
        return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))], status=200)

    @http.route('/api/v1/healthz', type='http', auth='none', cors='*', csrf=False)
    def _healthz(self):
        return Response(status=204)
