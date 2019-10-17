# -*- coding: utf-8 -*-

from odoo import http, fields, api, SUPERUSER_ID
import json
from odoo.http import request, Response
import re

import werkzeug.utils
import werkzeug.wrappers
import odoo
import base64
import os

DEFAULT_LIMIT = 80


class OperationView(http.Controller):

    def placeholder(self, image='placeholder.png'):
        addons_path = http.addons_manifest['web']['addons_path']
        return open(os.path.join(addons_path, 'web', 'static', 'src', 'img', image), 'rb').read()

    def force_contenttype(self, headers, contenttype='image/png'):
        dictheaders = dict(headers)
        dictheaders['Content-Type'] = contenttype
        return dictheaders.items()

    @http.route('/api/v1/mrp.routing.workcenter/<int:operation_id>/edit', type='json', methods=['PUT', 'OPTIONS'],
                auth='none', cors='*', csrf=False)
    def _edit(self, operation_id=None):
        pattern = re.compile(r"^data:image/(.+);base64,(.+)", re.DOTALL)
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        operation = env['mrp.routing.workcenter'].search([('id', '=', operation_id)], limit=1)
        if not operation:
            body = json.dumps({'msg': "Operation %d not existed" % operation_id})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        else:
            req_vals = request.jsonrequest
            points = []
            if req_vals.has_key('points'):
                points = req_vals['points']
            img = req_vals['img'] if 'img' in req_vals else None
            if img:
                g = pattern.search(img)
                if not g:
                    body = json.dumps({'msg': "Image Format error"})
                    headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
                    return Response(body, status=405, headers=headers)
                _data = g.group(2)
                ret = operation.write({'worksheet_img': _data})
                if not ret:
                    body = json.dumps({'msg': "Operation %d upload image fail" % operation_id})
                    headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
                    return Response(body, status=405, headers=headers)
            if not req_vals.has_key('points'):
                body = json.dumps({'msg': "Edit point success"})
                headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
                return Response(body, status=200, headers=headers)
            if not isinstance(points, list):
                body = json.dumps({'msg': "Body must be point array"})
                headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
                return Response(body, status=405, headers=headers)

            current_points = env['operation.point'].search([('operation_id', '=', operation_id)])
            points_map = {i.id: i for i in current_points}

            for val in points:
                point_id = env['operation.point'].search([('operation_id', '=', operation_id),
                                                          ('sequence', '=', val['sequence'])])
                if not point_id:
                    # 新增
                    val.update({
                        'operation_id': operation_id,
                        'sequence': val['sequence'],
                        'x_offset': val['x_offset'],
                        'y_offset': val['y_offset']
                    })
                    env['operation.point'].create(val)
                else:
                    # 更新
                    point_id.write(val)
                    if points_map.has_key(point_id.id):
                        del points_map[point_id.id]

            for k in points_map:
                points_map[k].toggle_active()

            # 下发作业
            operation.button_send_mrp_routing_workcenter()

            body = json.dumps({'msg': "Edit point success"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=200, headers=headers)

    @http.route('/api/v1/mrp.routing.workcenter/<int:operation_id>/points_edit', type='json',
                methods=['PUT', 'OPTIONS'], auth='none', cors='*', csrf=False)
    def _edit_points(self, operation_id=None):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        operation = env['mrp.routing.workcenter'].search([('id', '=', operation_id)], limit=1)
        if not operation:
            body = json.dumps({'msg': "Operation %d not existed" % operation_id})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=404, headers=headers)
        else:
            points = request.jsonrequest
            if not isinstance(points, list):
                body = json.dumps({'msg': "Body must be point array"})
                headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
                return Response(body, status=405, headers=headers)

            current_points = env['operation.point'].search([('operation_id', '=', operation_id)])
            points_map = {i.id: i for i in current_points}

            for val in points:
                point_id = env['operation.point'].search([('operation_id', '=', operation_id),
                                                          ('sequence', '=', val['sequence'])])
                if not point_id:
                    # 新增
                    val.update({
                        'operation_id': operation_id,
                        'sequence': val['sequence'],
                        'x_offset': val['x_offset'],
                        'y_offset': val['y_offset'],
                        'product_id': env.ref('sa_base.product_product_screw_default').id  # 获取默认螺栓
                    })
                    env['operation.point'].create(val)
                else:
                    # 更新
                    ret = point_id.write(val)
                    if not ret:
                        print(u'更新点位失败')
                    if points_map.has_key(point_id.id):
                        del points_map[point_id.id]

            need_delete_points = env['operation.point']
            for p in points_map.values():
                need_delete_points += p

            need_delete_points.unlink()

            body = json.dumps({'msg': "Edit point success"})
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=200, headers=headers)

    @http.route(['/api/v1/worksheet'], type='http', methods=['GET'], auth='none', cors='*', csrf=False)
    def _get_worksheet(self, model=None, id=None, field=None, width=0, height=0):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        unique = False
        filename = None
        filename_field = 'datas_fname'
        download = False
        mimetype = None
        default_mimetype = 'application/octet-stream',
        status, headers, content = env['ir.http'].binary_content(model=model, id=id, field=field, filename=filename,
                                                                 filename_field=filename_field, unique=unique,
                                                                 download=download, mimetype=mimetype,
                                                                 default_mimetype=default_mimetype, env=env)
        if status == 304:
            return werkzeug.wrappers.Response(status=304, headers=headers)
        elif status == 301:
            return werkzeug.utils.redirect(content, code=301)
        elif status != 200 and download:
            return request.not_found()

        height = int(height or 0)
        width = int(width or 0)
        if content and (width or height):
            # resize maximum 500*500
            if width > 500:
                width = 500
            if height > 500:
                height = 500
            content = odoo.tools.image_resize_image(base64_source=content, size=(width or None, height or None),
                                                    encoding='base64', filetype='PNG')
            # resize force png as filetype
            headers = self.force_contenttype(headers, contenttype='image/png')

        if content:
            image_base64 = base64.b64decode(content)
        else:
            image_base64 = self.placeholder(image='placeholder.png')  # could return (contenttype, content) in master
            headers = self.force_contenttype(headers, contenttype='image/png')

        headers.append(('Content-Length', len(image_base64)))
        response = request.make_response(image_base64, headers)
        response.status_code = status
        return response

    @http.route(['/api/v1/mrp.routing.workcenter/<int:operation_id>', '/api/v1/mrp.routing.workcenter'], type='http',
                methods=['GET'], auth='none', cors='*', csrf=False)
    def _get_operations(self, operation_id=None, **kw):
        env = api.Environment(request.cr, SUPERUSER_ID, request.context)
        if operation_id:
            operation = env['mrp.routing.workcenter'].search([('id', '=', operation_id)], limit=1)
            if not operation:
                body = json.dumps({'msg': "Operation %d not existed" % operation_id})
                headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
                return Response(body, status=404, headers=headers)
            else:
                _points = []
                for point in operation.operation_point_ids:
                    _points.append({
                        'sequence': point.sequence,
                        'x_offset': point.x_offset,
                        'y_offset': point.y_offset
                    })

                val = {
                    "id": operation_id,
                    "name": u"[{0}]{1}@{2}/{3}".format(operation.name, operation.group_id.code,
                                                       operation.workcenter_id.name, operation.routing_id.name),
                    "img": u'data:{0};base64,{1}'.format('image/png',
                                                         operation.worksheet_img) if operation.worksheet_img else "",
                    # "worksheet": u'data:{0};base64,{1}'.format('application/pdf', operation.worksheet) if operation.worksheet else "",
                    "points": _points
                }
                body = json.dumps(val)
                headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
                return Response(body, status=200, headers=headers)
        else:
            ### 获取作业清单
            domain = []
            if 'hmi_sn' in kw:
                domain += [('workcenter_id.hmi_id.serial_no', '=', kw['hmi_sn'])]
            if 'limit' in kw.keys():
                limit = int(kw['limit'])
            else:
                limit = DEFAULT_LIMIT
            operations = env['mrp.routing.workcenter'].search(domain, limit=limit)
            vals = []

            for operation in operations:
                # _points = []
                # for point in operation.operation_point_ids:
                #     _points.append({
                #         'sequence': point.sequence,
                #         'x_offset': point.x_offset,
                #         'y_offset': point.y_offset
                #     })

                boms = env['mrp.bom'].search([('operation_ids', 'in', operation.id)])
                if boms:
                    for bom in boms:
                        vals.append({
                            'id': operation.id,
                            'name': u"{0}@{1}".format(bom.product_id.default_code, operation.name),
                        })

            body = json.dumps(vals)
            headers = [('Content-Type', 'application/json'), ('Content-Length', len(body))]
            return Response(body, status=200, headers=headers)
