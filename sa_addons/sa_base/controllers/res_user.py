# -*- coding: utf-8 -*-
from odoo import http, SUPERUSER_ID, api
from odoo.http import request, Response

import json

NORMAL_USER_FIELDS_READ = ['id', 'name', 'login', 'active', 'uuid', 'image_small']

DEFAULT_LIMIT = 80


class UsersAPI(http.Controller):
    @http.route('/api/v1/res.users', type='http', auth='none', cors='*', csrf=False)
    def _get_users_list_info(self, **query_params):
        _limit = DEFAULT_LIMIT
        if 'limit' in query_params:
            _limit = int(query_params['limit'])
        domain = [('id', '!=', 1)]
        if 'uuids' in query_params:
            uuids = query_params['uuids'].split(',')
            domain += [('uuid', 'in', uuids)]
        _users = request.env['res.users'].sudo().search(domain, limit=_limit)
        users = []
        if _users:
            users = _users.read(fields=NORMAL_USER_FIELDS_READ)
        for user in users:
            if 'active' in user:
                user.update({
                    'status': 'active' if user['active'] else 'archived'
                })
                user.pop('active')
            if 'image_small' in user:
                user.update({
                    'image_small': u'data:{0};base64,{1}'.format('image/png', user['image_small']) if user[
                        'image_small'] else ""
                })
        return Response(json.dumps(users), headers={'content-type': 'application/json'}, status=200)

    @http.route('/api/v1/res.users/<string:uuid>', type='http', auth='none', cors='*', csrf=False)
    def _get_user_info(self, uuid):

        user_id = request.env['res.users'].sudo().search([('uuid', '=', uuid)], limit=1)

        if not user_id:
            return Response(json.dumps({'msg': 'User not found'}), headers={'content-type': 'application/json'},
                            status=404)

        ret = user_id.sudo().read(fields=NORMAL_USER_FIELDS_READ)[0]
        if 'active' in ret:
            ret.update({
                'status': 'active' if ret['active'] else 'archived'
            })
            ret.pop('active')
        if 'image_small' in ret:
            ret.update({
                'image_small': u'data:{0};base64,{1}'.format('image/png', ret['image_small']) if ret[
                    'image_small'] else ""
            })

        return Response(json.dumps(ret), headers={'content-type': 'application/json'}, status=200)

    @http.route('/api/v1/res.users/batch_archived', type='json', auth='none', cors='*', csrf=False)
    def _bach_patch_user_archived(self):
        uuids = request.jsonrequest
        user_ids = request.env['res.users'].sudo().search([('uuid', 'in', uuids)])

        if not user_ids:
            return Response(json.dumps({'msg': 'User not found'}), headers={'content-type': 'application/json'},
                            status=404)

        ret = user_ids.sudo().write({
            'active': False
        })
        if not ret:
            return Response(json.dumps({'msg': 'Batch Archived fail'}), headers={'content-type': 'application/json'},
                            status=405)
        ret = user_ids.sudo().read(fields=NORMAL_USER_FIELDS_READ)[0]
        if 'active' in ret:
            ret.update({
                'status': 'active' if ret['active'] else 'archived'
            })
            ret.pop('active')

        return Response(json.dumps(ret), headers={'content-type': 'application/json'}, status=200)
