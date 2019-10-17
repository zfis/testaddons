# -*- coding: utf-8 -*-

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from itertools import groupby

MAX_RESULT = 5000


class ReportTightResultReport(models.AbstractModel):
    _inherit = 'report.spc.report_result_tighting'

    @api.model
    def render_html(self, docids, data=None):
        report_pages = [[]]
        if not data.get('form'):
            raise UserError(_("Form content is missing, this report cannot be printed."))

        Report = self.env['report']
        date_from = fields.Datetime.to_string(fields.Datetime.from_string(data['form']['date_from']))
        date_to = fields.Datetime.to_string(fields.Datetime.from_string(data['form']['date_to']))

        holidays_report = Report._get_report_from_name('spc.report_result_tighting')
        # results = self.env['operation.result'].search([('control_date', '>=', date_from), ('control_date', '<=', date_to ) ])
        #
        # if not results:
        #     return True

        # for vin, lines in groupby(results, lambda r: r.vin):
        #     if report_pages[-1] and report_pages[-1][-1]['name']:
        #         report_pages.append([])
        #         # Append category to current report page
        #     report_pages[-1].append({
        #         'name': vin or 'Uncategorized',
        #         'lines': list(lines)
        #     })

        query = '''select tb.vin, json_agg(json_build_array(tb.control_date, tb.job, tb.measure_result))
                from (select ors.vin as vin, ors.control_date as control_date, ors.measure_result as measure_result, ors.job as job from operation_result ors where ors.control_date >= '%s' and ors.control_date <= '%s' order by ors.control_date) tb
                group by tb.vin''' % (
            date_from,
            date_to
        )

        cr = self._cr
        cr.execute(query)
        results = cr.fetchall()

        length = len(results)

        if length > MAX_RESULT:
            raise UserError(u'请缩小时间范围,当前报告数量过大:{0}'.format(length))

        docargs = {
            'doc_ids': self.ids,
            'doc_model': holidays_report.model,
            'docs': results,
            'get_day': fields.Datetime.now(),
        }
        return Report.render('spc.report_result_tighting', docargs)
