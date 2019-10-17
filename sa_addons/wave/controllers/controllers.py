# -*- coding: utf-8 -*-
from odoo import http

# class Weave(http.Controller):
#     @http.route('/weave/weave/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/weave/weave/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('weave.listing', {
#             'root': '/weave/weave',
#             'objects': http.request.env['weave.weave'].search([]),
#         })

#     @http.route('/weave/weave/objects/<model("weave.weave"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('weave.object', {
#             'object': obj
#         })
