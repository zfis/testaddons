# -*- coding: utf-8 -*-


from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import odoo.addons.decimal_precision as dp
import json


class OperationResult(models.HyperModel):
    _inherit = "operation.result"

    @api.multi
    def show_waveform(self):
        if not len(self):
            self.env.user.notify_warning(u'查询获取结果:0,请重新定义查询参数或等待新结果数据')
            return None, None
        context = self._context
        wave_obj = self.env['wave.wave']
        wave_form = self.env.ref('wave.spc_compose_wave_wizard_form')
        if not wave_form:
            return None, None
        # datas, ret, mark_line_coords = wave_obj._get_data(self)
        datas = wave_obj._get_data(self)
        if not len(datas):
            self.env.user.notify_warning(u'查询获取结果:0,请重新定义查询参数或等待新结果数据')
            return None, None
        # wave = wave_obj._get_echart_data(datas, ret,mark_line_coords)
        wave = json.dumps(datas)
        wave_wizard_id = self.env['wave.compose.wave'].sudo().create({'wave': wave})
        if not wave_wizard_id:
            return None, None
        action = {
            'name': _('Curve Scope'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'wave.compose.wave',
            'view_id': wave_form.id,
            'res_id': wave_wizard_id.id,
            'target': 'new',
            'context': context,
        }

        return wave_form.id, wave_wizard_id.id


class OperationResultLine(models.TransientModel):
    _name = "operation.result.line"

    wizard_id = fields.Many2one('wave.wave', ondelete='cascade')

    # result_id = fields.Many2one('operation.result', ondelete='')

    selected = fields.Boolean('select', help='Whether add this result to create waveform', default=False)

    workorder_id = fields.Many2one('mrp.workorder')
    workcenter_id = fields.Many2one('mrp.workcenter')  # TDE: necessary ?
    # production_id = fields.Many2one('mrp.production', 'Production Order')
    #
    # cur_objects = fields.Char(string='Waveform Files')
    #
    # user_id = fields.Many2one('res.users', 'Responsible')
    #
    product_id = fields.Many2one('product.product', 'Vehicle')
    #
    consu_product_id = fields.Many2one('product.product', 'Screw')
    #
    control_date = fields.Datetime('Control Date')
    #
    measure_torque = fields.Float('Measure Torque(NM)', default=0.0, digits=dp.get_precision('Operation Result'))

    measure_degree = fields.Float('Measure Degree(grad)', default=0.0, digits=dp.get_precision('Operation Result'))

    measure_t_don = fields.Float('Measure Time Done(ms)', default=0.0, digits=dp.get_precision('Operation Result'))
    #

    cur_objects = fields.Char(string='Waveform Files')

    measure_result = fields.Selection([
        ('none', 'No measure'),
        ('ok', 'OK'),
        ('nok', 'NOK')], string="Measure Result", default='none')

    #
    # lacking = fields.Selection([('lack', 'Data Lacking'),
    #     ('normal', 'Normal')], string='Lacking', default='lack', compute='_compute_result_lacking', store=True)
    #
    # op_time = fields.Integer(string=u'第几次拧紧作业', default=1)
    #
    # one_time_pass = fields.Selection([('pass', 'One Time Passed'),
    #     ('fail', 'Failed')], string='One Time Pass', default='fail',
    #                                compute='_compute_result_pass', store=True)
    #
    # final_pass = fields.Selection([('pass', 'Final Passed'),
    #     ('fail', 'Failed')], string='Final Pass', default='fail',
    #                             compute='_compute_result_pass', store=True)

    @api.model
    def bulk_create(self, all_vals):
        if self.is_transient():
            self._transient_vacuum()

        all_updates = []
        for vals in all_vals:
            # if 'name' not in vals or vals['name'] == _('New'):
            #     vals['name'] = self.env['ir.sequence'].next_by_code('sa.quality.check') or _('New')
            # data of parent records to create or update, by model
            tocreate = {
                parent_model: {'id': vals.pop(parent_field, None)}
                for parent_model, parent_field in self._inherits.iteritems()
            }

            # list of column assignments defined as tuples like:
            #   (column_name, format_string, column_value)
            #   (column_name, sql_formula)
            # Those tuples will be used by the string formatting for the INSERT
            # statement below.
            updates = [
                ('id', "%s", "nextval('%s')" % self._sequence),
            ]

            upd_todo = []
            unknown_fields = []
            protected_fields = []
            for name, val in vals.items():
                field = self._fields.get(name)
                if not field:
                    unknown_fields.append(name)
                    del vals[name]
                elif field.inherited:
                    tocreate[field.related_field.model_name][name] = val
                    del vals[name]
                elif not field.store:
                    del vals[name]
                elif field.inverse:
                    protected_fields.append(field)
            # if unknown_fields:
            #     _logger.warning('No such field(s) in model %s: %s.', self._name, ', '.join(unknown_fields))

            # set boolean fields to False by default (to make search more powerful)
            for name, field in self._fields.iteritems():
                if field.type == 'boolean' and field.store and name not in vals:
                    vals[name] = False

            # determine SQL values
            for name, val in vals.iteritems():
                field = self._fields[name]
                if field.store and field.column_type:
                    updates.append((name, field.column_format, field.convert_to_column(val, self)))
                else:
                    upd_todo.append(name)

                if hasattr(field, 'selection') and val:
                    self._check_selection_field_value(name, val)

            # if self._log_access:
            #     updates.append(('create_uid', '%s', self._uid))
            #     updates.append(('write_uid', '%s', self._uid))
            #     updates.append(('create_date', "(now() at time zone 'UTC')"))
            #     updates.append(('write_date', "(now() at time zone 'UTC')"))
            all_updates.append(updates)
            # insert a row for this record
        cr = self._cr
        t = [tuple(u[2] for u in update if len(u) > 2) for update in all_updates]
        query = """INSERT INTO "%s" (%s) VALUES %s RETURNING id""" % (
            self._table,
            ', '.join('"%s"' % u[0] for u in all_updates[0]),
            ','.join("(nextval('%s')," % self._sequence + str(_t[1:])[1:] for _t in t),
        )

        cr.execute(query)

        # from now on, self is the new record
        ids_news = cr.fetchall()
        return ids_news
