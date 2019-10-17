# # -*- coding: utf-8 -*-
#
# from odoo import tools
# from odoo import models, fields, api
# from pyecharts import Line, Bar
# from pyecharts import Pie, Style
# import pyecharts
# from pandas import DataFrame
#
# class OperationResultReport(models.TransientModel):
#     _name = "operation.result.wizard"
#     _description = "Result Statistics Process Control"
#
#     query_date_from = fields.Datetime(string='Query Date From')
#     query_date_to = fields.Datetime(string='Query Date to', default=fields.Datetime.now())
#     vehicle_id = fields.Many2one('product.product', string='Vehicle Type', domain=[('sa_type', '=', 'vehicle')])
#     screw_id = fields.Many2one('product.product', string='Screw Type', domain=[('sa_type', '=', 'screw')])
#     assembly_line_id = fields.Many2one('mrp.assemblyline', string='Assembly Line')
#     controller_ids = fields.Many2many('maintenance.equipment', string='Controllers', domain=[('category_name', '=', 'Controller')])
#     segment_id = fields.Many2one('mrp.worksection', string='Work Segment')
#     knr_code = fields.Char(string='KNR')
#     vin_code = fields.Char(string='Track Number(Serial Number/VIN)')
#     limit = fields.Integer('Query Limit', default=80)
#
#     success_analyze = fields.Text(string='合格率分析', store=False)
#     success_controller_analyze = fields.Text(string='合格率分析', store=False)
#
#     def _get_success_anaylize_data(self,data):
#         pie = Pie(u"{0}".format(u'单车合格率'), u"KIN/Track Number(Serial Number/VIN):{0}".format(self.knr_code or self.vin_code), title_pos='center',width=1920,height=1080)
#         style = Style()
#         pie_style = style.add(label_pos="center", is_label_show=True, label_text_color=None)
#
#         pie.add("", ["剧情", "xx"], [25, 75], center=[10, 30],
#                 radius=[18, 24], legend_pos="left", legend_orient='vertical', **pie_style)
#         pie.add("", ["奇幻", "yy"], [24, 76], center=[30, 30],
#                 radius=[18, 24],  legend_pos="right", legend_orient='vertical', **pie_style)
#         pyecharts.configure(force_js_embed=True)
#         return pie.render_embed()
#
#     @api.multi
#     def read(self, fields=None, load='_classic_read'):
#         result = super(OperationResultReport, self).read(fields, load=load)
#         if 'success_analyze' in fields and load == '_classic_read':
#             data = self._get_data()
#             result[0].update({'success_analyze': self._get_success_anaylize_data(data)})
#         return result
#
#     def _get_data(self):
#         domain = []
#         if self.query_date_from:
#             domain += [('control_date', '>=', self.query_date_from)]
#         if self.query_date_to:
#             domain += [('control_date', '<=', self.query_date_to)]
#         if self.vehicle_id:
#             domain += [('product_id', '=', self.vehicle_id.id)]
#         if self.screw_id:
#             domain += [('consu_product_id', '=', self.screw_id.id)]
#         if self.assembly_line_id:
#             domain += [('production_id.assembly_line_id', '=', self.assembly_line_id.id)]
#         if self.segment_id:
#             domain += [('workcenter_id.worksegment_id', '=', self.segment_id.id)]
#         if self.knr_code:
#             domain += [('production_id.knr', 'like', self.knr_code)]
#         if self.vin_code:
#             domain += [('production_id.vin', 'like', self.vin_code)]
#         if self.controller_ids:
#             domain += [('workcenter_id.controller_id', 'in', self.controller_ids.ids)]
#         return self.env['operation.result'].sudo().search(domain, limit=self.limit)
#
#     @api.multi
#     def button_query_vehicle(self):
#         result = {'count': 0,
#                   'ok': 0,
#                   'lacking': 0,
#                   'nok': 0,
#                   'used': 0}
#         knr_code = '%' + self.knr_code + '%' if self.knr_code else '%'
#         query = """
#                           SELECT b.knr as knr, count(*) as count, o.measure_result as result ,o.lacking as lack
#                           FROM operation_result o
#                           FULL JOIN mrp_production b ON (b.id = o.production_id)
#                           WHERE b.knr LIKE '%s'
#                           AND o.control_date >= '%s'
#                           AND o.control_date <= '%s'
#                           group by o.measure_result, o.lacking, b.knr
#                         """ % (knr_code, self.query_date_from, self.query_date_to)
#         self.env.cr.execute(query, ())
#         data = [row for row in self.env.cr.dictfetchall()]
#         df = DataFrame.from_dict(data)
#         print(df)
#         _df = df.groupby('knr')
#         print(_df)
#
#         result['used'] = result['count'] - result['lacking']
#         return result
#
#     @api.multi
#     def button_query_controller(self):
#         result = {}
#         query = """
#                   SELECT count(*) as c, measure_result as measure_result, workorder_id as wo_id,
#                   workcenter_id as wc_id
#                   FROM operation_result
#                   GROUP BY workcenter_id, measure_result
#                 """
#         self.env.cr.execute(query)
#         for row in self.env.cr.dictfetchall():
#             result[row.pop('measure_result')] = row
#
#
#
# # query = """
# #                   SELECT count (*) as total,
# #                   CASE WHEN measure_result IN ('ok') THEN count(measure_result) ELSE 0 END AS pass_total,
# #                   CASE WHEN measure_result IN ('nok') THEN count(measure_result) ELSE 0 END AS fail_total
# #                   FROM operation_result
# #                   WHERE workcenter_id IN (select w.id
# #                   from mrp_workcenter as w
# #                   LEFT JOIN maintenance_equipment AS me
# #                     ON w.controller_id = me.id
# #                     WHERE st.id IN %s)
# #                   GROUP BY workcenter_id
# #                 """
