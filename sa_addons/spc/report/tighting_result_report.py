# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from itertools import groupby


class TightResultReport(models.TransientModel):
    _name = 'tight.result.report'
    _description = u'拧紧结果报告'

    def _get_default_date_from(self):
        year = fields.Date.from_string(fields.Date.today()).strftime('%Y')
        return '{}-01-01'.format(year)

    def _get_default_date_to(self):
        date = fields.Date.from_string(fields.Date.today())
        return date.strftime('%Y') + '-' + date.strftime('%m') + '-' + date.strftime('%d')

    date_from = fields.Date(string='Start Date', required=True, default=_get_default_date_from)
    date_to = fields.Date(string='End Date', required=True, default=_get_default_date_to)

    @api.multi
    def print_report(self):
        """
         To get the date and print the report
         @return: return report
        """
        self.ensure_one()
        data = {'ids': self.env.context.get('active_ids', [])}
        res = self.read()
        res = res and res[0] or {}
        data.update({'form': res})
        return self.env['report'].get_action(self, 'spc.report_result_tighting', data=data)


class ReportTightResultReport(models.AbstractModel):
    _name = 'report.spc.report_result_tighting'

    @api.model
    def render_html(self, docids, data=None):
        """
        渲染报告html的方法,在每个项目中进行override,重写方法
        :param docids:
        :param data:
        :return:
        """
        return True
