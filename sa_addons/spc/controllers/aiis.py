# -*- coding: utf-8 -*-

from odoo import http, fields, api, SUPERUSER_ID
import json
from odoo.http import request, Response
import re


class AiisConn(http.Controller):
    @http.route(['/api/v1/aiis.connection'], type='http', methods=['GET'], auth='none', cors='*', csrf=False)
    def _get_aiis_conn(self, operation_id=None):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        aiis_urls = env["ir.config_parameter"].get_param("aiis.urls")
        val = {
            "connection": aiis_urls if aiis_urls else ""
        }
        body = json.dumps(val)
        headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
        return Response(body, status=200, headers=headers)
