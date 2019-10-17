# -*- coding: utf-8 -*-
from odoo import http

# class TangcheEnhanced(http.Controller):
#     @http.route('/tangche_enhanced/tangche_enhanced/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/tangche_enhanced/tangche_enhanced/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('tangche_enhanced.listing', {
#             'root': '/tangche_enhanced/tangche_enhanced',
#             'objects': http.request.env['tangche_enhanced.tangche_enhanced'].search([]),
#         })

#     @http.route('/tangche_enhanced/tangche_enhanced/objects/<model("tangche_enhanced.tangche_enhanced"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('tangche_enhanced.object', {
#             'object': obj
#         })