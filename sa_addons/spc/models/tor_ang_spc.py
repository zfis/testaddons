# -*- coding: utf-8 -*-
# from __future__ import unicode_literals
from __future__ import division
from scipy.stats import norm, dweibull, weibull_max, weibull_min, invweibull, exponweib
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from pyecharts import Overlap, Bar, Line, Grid
import pyecharts
from pandas import DataFrame
import numpy as np
from odoo.tools import float_round
from dateutil.relativedelta import relativedelta
import datetime
import pytz

from ..utils import spc

DEFAULT_LIMIT = 5000
MIN_LIMIT = 1000


class TorAngSPCReport(models.TransientModel):
    _name = "ta.spc.wizard"
    _description = "Result Statistics Process Control"

    query_date_from = fields.Datetime(string='Query Date From')
    query_date_to = fields.Datetime(string='Query Date to', default=fields.Datetime.now())
    product_id = fields.Many2one('product.product', string='Finished Product SKU')
    product_sku_code = fields.Char(string='Finished Product SKU Code(support Fuzzy Search, Case-Insensitive)')
    screw_id = fields.Many2one('product.product', string='Screw Type', domain=[('sa_type', '=', 'screw')])
    tool_id = fields.Many2one('maintenance.equipment', string='Tightening Tool(Gun/Wrench)',
                             domain=lambda self: [('category_id.id', '=', self.env.ref('sa_base.equipment_Gun').id)])
    assembly_line_id = fields.Many2one('mrp.assemblyline', string='Assembly Line')
    limit = fields.Integer('Query Limit', default=DEFAULT_LIMIT)
    spc_target = fields.Selection([('torque', 'Torque'), ('angle', 'Angle')], string='统计对象', default='torque')

    normal_dist = fields.Text(string='Normal Distribution', store=False, compute='_compute_dist')
    weibull_dist = fields.Text(string='Weibull Distribution', store=False, compute='_compute_dist')
    weibull_dist_method = fields.Selection(
        [('double', 'Double Weibull'), ('inverted', 'Inverted'), ('exponential', 'Exponential'), ('min', 'Min Weibull'),
         ('max', 'Max Weibull')], string='韦伯分布统计方法', default='min')
    scatter = fields.Text(string='Scatter', store=False, compute='_compute_dist')

    step = fields.Selection([('day', 'Day'), ('month', 'Month'), ('week', 'Week')], default='day')

    need_render = fields.Boolean(default=False)

    usl = fields.Float(string='规格上限(USL)')

    lsl = fields.Float(string='规格下限(LSL)')

    cmk = fields.Float(string='CMK', store=False, compute='_compute_dist')
    cpk = fields.Float(string='CPK', store=False, compute='_compute_dist')

    @api.onchange('screw_id', 'spc_target')
    def _onchange_usl_lsl(self):
        self.ensure_one()
        qcp_id = self.env['sa.quality.point'].sudo().search([('bom_line_id.product_id', '=', self.screw_id.id)],
                                                            limit=1)
        if not qcp_id:
            return
        if self.spc_target == 'torque':
            self.usl = qcp_id.tolerance_max
            self.lsl = qcp_id.tolerance_min
        else:
            self.usl = qcp_id.tolerance_max_degree
            self.lsl = qcp_id.tolerance_min_degree

    @api.depends('need_render')
    def _compute_dist(self):
        if self.need_render:
            data, length = self._get_data()
            if data.empty:
                self.env.user.notify_warning(u'查询获取结果:{0},请重新定义查询参数或等待新结果数据'.format(length))
                return
            mean = np.mean(data)
            std = np.std(data)
            self.normal_dist, self.cmk, self.cpk = self._get_normal_dist(data=data, mean=mean, std=std, lsl=self.lsl,
                                                                         usl=self.usl)
            scale_parameter = self.env['ir.config_parameter'].sudo().get_param('weibull.scale', default=1.0)
            shape_parameter = self.env['ir.config_parameter'].sudo().get_param('weibull.shape', default=5.0)
            self.weibull_dist = self._get_weibull_dist(len(data), mean=mean, std=std,
                                                       scale=scale_parameter, shape=shape_parameter)

            self.scatter = self._get_scatter(data)

    @api.onchange('weibull_dist_method')
    def _compute_weibull_dist(self):
        if self.need_render:
            data, length = self._get_data()
            if data.empty:
                self.env.user.notify_warning(u'查询获取结果:{0},请重新定义查询参数或等待新结果数据'.format(length))
                return
            mean = np.mean(data)
            std = np.std(data)
            scale_parameter = self.env['ir.config_parameter'].sudo().get_param('weibull.scale', default=1.0)
            shape_parameter = self.env['ir.config_parameter'].sudo().get_param('weibull.shape', default=5.0)
            self.weibull_dist = self._get_weibull_dist(len(data), mean=mean, std=std,
                                                       scale=scale_parameter, shape=shape_parameter)

    @api.constrains('limit')
    def _constraint_limit(self):
        if self.limit < MIN_LIMIT:
            raise UserError(u'查询数量不得小于最小查询数量:{0}'.format(MIN_LIMIT))

    def _get_weibull_dist(self, qty, mean=None, std=None, scale=1.0, shape=5.0):

        x_line = np.arange(mean - std * 4.0, mean + std * 5.0, 1 * std)

        if self.weibull_dist_method == 'double':
            _data = dweibull(shape, loc=mean, scale=std)
            y_line = _data.pdf(x_line) * qty

        if self.weibull_dist_method == 'inverted':
            _data = invweibull(shape, loc=mean, scale=std)
            y_line = _data.pdf(x_line) * qty

        if self.weibull_dist_method == 'exponential':
            _data = exponweib(scale, shape, loc=mean, scale=std)
            y_line = _data.pdf(x_line) * qty

        if self.weibull_dist_method == 'min':
            _data = weibull_min(shape, loc=mean, scale=std)
            y_line = _data.pdf(x_line) * qty

        if self.weibull_dist_method == 'max':
            _data = weibull_max(shape, loc=mean, scale=std)
            y_line = _data.pdf(x_line) * qty

        line = Line(width=1280, height=600)
        line.add(u'{0}'.format(self.spc_target), x_line, y_line, xaxis_name=u'{0}'.format(self.spc_target),
                 yaxis_name=u'数量(Quantity)',
                 line_color='rgba(0 ,255 ,127,0.5)', legend_pos='center',
                 is_smooth=True, line_width=2,
                 tooltip_tragger='axis', is_fill=True, area_color='#20B2AA', area_opacity=0.4)
        pyecharts.configure(force_js_embed=True)
        return line.render_embed()

    def _get_normal_dist(self, data, mean=None, std=None, lsl=None, usl=None):
        CPK, CMK = spc.get_cpk_cmk(data, lsl, usl)
        STEP = 0.25 * std
        length = len(data)
        norm_data = norm(mean, std)
        # x_bar = np.arange(int(min), int(max), 1)
        t = data.get_values()

        x_bar = x_line = np.around(np.arange(mean - std * 3.0, mean + std * 4.0, STEP), decimals=3)
        y_line = np.around(norm_data.pdf(x_line), decimals=3)
        # x_bar = np.arange(mean - std * 3.0, mean + std * 4.0, STEP)
        _y_bar, bin_edges = np.histogram(t, range=(mean - std * 3.0, mean + std * 4.0), bins=len(x_bar))
        vfunc = np.vectorize(lambda x: x / length, otypes=[float])
        y_bar = np.around(vfunc(_y_bar), decimals=3)

        bar = Bar(title=u"Normal Distribution({0})".format(self.spc_target), title_pos="50%", width=960, height=1440)
        bar.add(u'{0}'.format(self.spc_target), bin_edges[1:], y_bar, legend_orient="vertical", legend_top="45%",
                legend_pos='50%',
                xaxis_name=u'{0}'.format(self.spc_target), yaxis_name_gap=100, label_pos='inside', is_label_show=True,
                label_color=['#a6c84c', '#ffa022', '#46bee9'],
                # bar_category_gap=0, ### 直方图
                yaxis_name=u'概率(Probability)')
        line = Line(width=960, height=1440)
        line.add(u'{0}'.format(self.spc_target).format(self.spc_target), x_line, y_line,
                 xaxis_name=u'{0}'.format(self.spc_target),
                 yaxis_name=u'概率(Probability)', mark_line_valuedim=['x', 'x'], mark_line=['min', 'max'],
                 line_color='rgba(0 ,255 ,127,0.5)', is_legend_show=False,
                 is_smooth=True, line_width=2, is_label_show=False,
                 is_datazoom_show=False, datazoom_type='both', label_text_size=16,
                 tooltip_tragger='axis', is_fill=False)

        # grid = Grid(width=1920, height=1440, )
        # grid.add(bar, grid_bottom="60%", grid_left="60%")
        # grid.add(line, grid_bottom="60%", grid_right="60%")
        overlap = Overlap(width=1080, height=1024, page_title=u"Normal Distribution({0})".format(self.spc_target))
        overlap.add(line)
        overlap.add(bar)
        pyecharts.configure(force_js_embed=True)
        return overlap.render_embed(), CMK, CPK

    def _get_scatter(self, data):
        qty = len(data)
        x_line = np.arange(1, qty + 1, 1)
        y_line = data
        line = Line(width=1280, height=800)
        line.add(u'{0}'.format(self.spc_target), x_line, y_line, xaxis_name=u'Sequence',
                 yaxis_name=u'{0}'.format(self.spc_target), mark_line=["min", "average", "max"],
                 line_color='rgba(0 ,255 ,127,0.5)', legend_pos='center',
                 is_smooth=True, line_width=2, is_more_utils=True,
                 tooltip_tragger='axis')
        pyecharts.configure(force_js_embed=True)
        return line.render_embed()

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        result = super(TorAngSPCReport, self).read(fields, load=load)
        return result

    # @api.multi
    # def read(self, fields=None, load='_classic_read'):
    #     data = DataFrame()
    #     mean = 0.0
    #     std = 0.0
    #     result = super(TorAngSPCReport, self).read(fields, load=load)
    #     if 'normal_dist' in fields or 'weibull_dist' in fields or'scatter' in fields and load == '_classic_read':
    #         data, length = self._get_data()
    #         if data.empty:
    #             self.env.user.notify_warning(u'查询获取结果:{0},请重新定义查询参数或等待新结果数据'.format(length))
    #             return result
    #         mean = np.mean(data)
    #         std = np.std(data)
    #     if 'normal_dist' in fields and not data.empty:
    #         result[0].update({'normal_dist': self._get_normal_dist(mean=mean,std=std)})
    #     if 'weibull_dist' in fields and not data.empty:
    #         scale_parameter = self.env['ir.config_parameter'].sudo().get_param('weibull.scale', default=1.0)
    #         shape_parameter = self.env['ir.config_parameter'].sudo().get_param('weibull.shape', default=5.0)
    #         result[0].update({'weibull_dist': self._get_weibull_dist(len(data), mean=mean, std=std,
    #                                                                  scale=scale_parameter, shape=shape_parameter)})
    #     if 'scatter' in fields and not data.empty:
    #         result[0].update({'scatter': self._get_scatter(data)})
    #
    #     return result

    def _get_data(self):
        domain = [('measure_result', '=', 'ok')]
        order = 'control_date desc'
        if self.query_date_from:
            domain += [('control_date', '>=', self.query_date_from)]
        if self.query_date_to:
            domain += [('control_date', '<=', self.query_date_to)]
        if self.product_sku_code:
            product_id = self.env['product.product'].sudo().search([('default_code', 'ilike', self.product_sku_code)],
                                                                   limit=1)
            if product_id:
                domain += [('product_id', '=', product_id.id)]
        if self.product_id:
            domain += [('product_id', '=', self.product_id.id)]
        if self.screw_id:
            domain += [('consu_product_id', '=', self.screw_id.id)]
        if self.tool_id:
            domain += [('tool_id', '=', self.tool_id.id)]
        if self.assembly_line_id:
            domain += [('assembly_line_id', '=', self.assembly_line_id.id)]
        if self.spc_target == 'torque':
            _data = self.env['operation.result'].sudo().get_torques(domain, limit=self.limit, order=order)
            data = {'measure_torque': _data}
        else:
            _data = self.env['operation.result'].sudo().get_angles(domain, limit=self.limit, order=order)
            data = {'measure_degree': _data}
        length = len(_data)
        if length < self.limit and length < 25:
            return DataFrame(), length
        df = DataFrame.from_records(data)
        df = df['measure_degree'] if self.spc_target == 'angle' else df['measure_torque']
        return df, length

    # @api.multi
    # def button_query_vehicle(self):
    #     result = {'count': 0,
    #               'ok': 0,
    #               'lacking': 0,
    #               'nok': 0,
    #               'used': 0}
    #     knr_code = '%' + self.knr_code + '%' if self.knr_code else '%'
    #     query = """
    #                       SELECT b.knr as knr, count(*) as count, o.measure_result as result ,o.lacking as lack
    #                       FROM operation_result o
    #                       FULL JOIN mrp_production b ON (b.id = o.production_id)
    #                       WHERE b.knr LIKE '%s'
    #                       AND o.control_date >= '%s'
    #                       AND o.control_date <= '%s'
    #                       group by o.measure_result, o.lacking, b.knr
    #                     """ % (knr_code, self.query_date_from, self.query_date_to)
    #     self.env.cr.execute(query, ())
    #     data = [row for row in self.env.cr.dictfetchall()]
    #     df = DataFrame.from_dict(data)
    #     print(df)
    #     _df = df.groupby('knr')
    #     print(_df)
    #
    #     result['used'] = result['count'] - result['lacking']
    #     return result

    @api.multi
    def button_query(self):
        self.need_render = True

    @api.multi
    def button_step_day(self):
        self.step = 'day'

    @api.multi
    def button_step_week(self):
        self.step = 'week'

    @api.multi
    def button_step_month(self):
        self.step = 'month'

    @api.multi
    def button_backend(self):
        if self.step == 'day':
            self.query_date_from = fields.Datetime.from_string(self.query_date_from) + datetime.timedelta(days=1)
            self.query_date_to = fields.Datetime.from_string(self.query_date_to) + datetime.timedelta(days=1)
        if self.step == 'week':
            self.query_date_from = fields.Datetime.from_string(self.query_date_from) + datetime.timedelta(weeks=1)
            self.query_date_to = fields.Datetime.from_string(self.query_date_to) + datetime.timedelta(weeks=1)
        if self.step == 'month':
            self.query_date_from = fields.Datetime.from_string(self.query_date_from) + relativedelta(months=1)
            self.query_date_to = fields.Datetime.from_string(self.query_date_to) + relativedelta(months=1)

    @api.multi
    def button_forward(self):
        if self.step == 'day':
            self.query_date_from = fields.Datetime.from_string(self.query_date_from) - datetime.timedelta(days=1)
            self.query_date_to = fields.Datetime.from_string(self.query_date_to) - datetime.timedelta(days=1)
        if self.step == 'week':
            self.query_date_from = fields.Datetime.from_string(self.query_date_from) - datetime.timedelta(weeks=1)
            self.query_date_to = fields.Datetime.from_string(self.query_date_to) - datetime.timedelta(weeks=1)
        if self.step == 'month':
            self.query_date_from = fields.Datetime.from_string(self.query_date_from) - relativedelta(months=1)
            self.query_date_to = fields.Datetime.from_string(self.query_date_to) - relativedelta(months=1)

    @api.multi
    def button_today(self):
        timezone = pytz.timezone(self._context.get('tz'))
        self.query_date_from = timezone.localize(
            datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).astimezone(tz=pytz.utc)
        self.query_date_to = timezone.localize(
            datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)).astimezone(tz=pytz.utc)
