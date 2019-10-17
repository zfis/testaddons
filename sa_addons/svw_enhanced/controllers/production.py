# -*- coding: utf-8 -*-
from odoo import http, fields, api, SUPERUSER_ID
import json
from odoo.http import request, Response
from dateutil import parser
import time

DEFAULT_LIMIT = 80

NORMAL_RESULT_FIELDS_READ = ['vin', 'id', 'knr', 'product_id', 'assembly_line_id', 'result_ids']


class SaConfiguration(http.Controller):
    @http.route(['/api/v1/mrp.productions', '/api/v1/mrp.productions/<string:vin>'], type='http',
                methods=['GET', 'OPTIONS'], auth='none', cors='*', csrf=False)
    def _get_productions(self, vin=None, **kw):
        domain = []
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        if vin:
            production_ids = env['mrp.production'].search([('vin', '=', vin)])
        else:
            if 'vins' in kw:
                vins = kw['vins'].split(',')
                domain += [('vin', 'in', vins)]
            if 'limit' in kw.keys():
                limit = int(kw['limit'])
            else:
                limit = DEFAULT_LIMIT
            production_ids = env['mrp.production'].search(domain, limit=limit)
        if not production_ids:
            body = json.dumps({'msg': "MO not existed"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        vals = [{
            'id': production.id,
            'vin': production.vin,
            'knr': production.knr,
            'product_id': production.product_id.id,
            'assembly_line_id': production.assembly_line_id.id,
            'result_ids': production.result_ids.ids,
        } for production in production_ids]
        ret = vals[0] if vin else vals
        body = json.dumps(ret)
        return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))], status=200)

    @http.route('/api/v1/mrp.productions', type='json', methods=['POST', 'OPTIONS'], auth='none', cors='*', csrf=False)
    def assemble_mo_create(self):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        vals = request.jsonrequest
        # print(vals)
        vin = vals['vin'] if 'vin' in vals else None
        if not vin:
            body = json.dumps({"msg": "Track Number(Serial Number/VIN) not exists in parameters"})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=405)
        mo_name = u'{0}--V001--{1}-{2}-{3}={4}'.format(
            vals['equipment_name'], vals['factory_name'], vals['year'], vals['pin'], vals['pin_check_code'])

        count = env['mrp.production'].search_count(
            [('name', '=', mo_name)])
        if count > 0:
            # MO已存在
            body = json.dumps({"msg": "MO name " + mo_name + " already exists"})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=405)

        count = env['mrp.production'].search_count(
            [('vin', '=', vin)])
        if count > 0:
            # MO已存在
            body = json.dumps({"msg": "MO vin " + vin + " already exists"})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=405)

        vechile_code = vals['model'] if 'model' in vals else None
        if not vechile_code:
            body = json.dumps({"msg": "Vehicle Type code  not exists  in parameters"})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=405)
        vals.pop('model')
        records = env['product.product'].search(
            [('default_code', 'ilike', vechile_code)], limit=1)

        if not records:
            # 找不到对应车型
            body = json.dumps({"msg": "vehicle model " + vechile_code + " not found"})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=400)

        product_id = records[0]

        assemble_line = vals['assembly_line'] if 'assembly_line' in vals else None
        if not assemble_line:
            body = json.dumps({"msg": "assembly_line  not exists  in parameters"})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=405)

        vals.pop('assembly_line')
        records = env['mrp.assemblyline'].search(
            ['|', ('name', 'ilike', assemble_line), ('code', 'ilike', assemble_line)], limit=1)

        if not records:
            # 找不到对应装配线
            records = env['mrp.assemblyline'].create({'name': assemble_line, 'code': assemble_line})
            # Response.status = "400 Bad Request"
            # return {"msg": "Assembly line " + assemble_line + " not found"}

        assembly_line_id = records[0]

        vals.update({'name': mo_name})
        vals.update({'product_id': product_id.id,
                     'bom_id': product_id.active_bom_id.id,
                     'product_tmpl_id': product_id.product_tmpl_id.id,
                     'product_uom_id': product_id.active_bom_id.product_uom_id.id,
                     'routing_id': product_id.active_bom_id.routing_id.id,
                     'assembly_line_id': assembly_line_id.id})

        prs = vals['prs']
        vals.pop('prs')
        vals.update(
            {'production_routings': json.dumps(prs)}
        )

        if 'date_planned_start' in vals:
            _t = parser.parse(vals['date_planned_start']) if vals['date_planned_start'] else None
            if _t:
                vals.update({
                    'date_planned_start': fields.Datetime.to_string((_t - _t.utcoffset()))
                })
        production = env['mrp.production'].create(vals)
        production.plan_by_prs()  ### 模拟点击安排,自动生成工单

        if not production:
            body = json.dumps({"msg": "create MO failed"})
            return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))],
                            status=400)

        # 创建MO成功
        vals = {
            'id': production.id,
            'vin': production.vin,
            'knr': production.knr,
            'product_id': production.product_id.id,
            'assembly_line_id': production.assembly_line_id.id,
            'result_ids': production.result_ids.ids if production.result_ids else [],
            'workorder_ids': production.workorder_ids.ids if production.workorder_ids else [],
        }
        body = json.dumps(vals)
        return Response(body, headers=[('Content-Type', 'application/json'), ('Content-Length', len(body))], status=201)
