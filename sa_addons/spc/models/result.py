# -*- coding: utf-8 -*-
from __future__ import division
from odoo import fields, models, api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError
import odoo.addons.decimal_precision as dp
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.addons.spc.controllers.result import _post_aiis_result_package
from odoo.tools.misc import CountingStream, DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import babel.dates
import pytz
from odoo.osv import expression
import logging
from odoo.tools import float_round, frozendict, lazy_classproperty, lazy_property, ormcache, \
    Collector, LastOrderedSet, OrderedSet

from collections import defaultdict, MutableMapping, OrderedDict
from odoo.tools import frozendict

_logger = logging.getLogger(__name__)


class OperationResult(models.HyperModel):
    _name = "operation.result"

    sequence = fields.Integer('sequence', default=1)

    workorder_id = fields.Many2one('mrp.workorder', 'Actual Work Order')
    workcenter_id = fields.Many2one('mrp.workcenter', readonly=True)
    production_id = fields.Many2one('mrp.production', 'Production Order')

    expect_workorder_id = fields.Many2one('mrp.workorder', string='Expect Work Order')

    track_no = fields.Char('Finished Product Tracking Number')  # 如果无法通过工单查询,使用此字段

    assembly_line_id = fields.Many2one('mrp.assemblyline', string='Assembly Line', readonly=True)

    qcp_id = fields.Many2one('sa.quality.point', 'Quality Control Point')

    operation_point_id = fields.Many2one('operation.point', string='Tightening Operation Point')

    bom_line_id = fields.Many2one('mrp.bom.line')

    tool_id = fields.Many2one('maintenance.equipment', string='Tightening Tool(Gun/Wrench)', copy=False)

    pset_strategy = fields.Selection([('AD', 'Torque tightening'),
                                      ('AW', 'Angle tightening'),
                                      ('ADW', 'Torque/Angle tightening'),
                                      ('LN', 'Loosening'),
                                      ('AN', 'Number of Pulses tightening'),
                                      ('AT', 'Time tightening')])

    pset_m_max = fields.Float(string='Set Max Torque(NM)', digits=dp.get_precision('Operation Result'))

    pset_m_min = fields.Float(string='Set Min Torque(NM)', digits=dp.get_precision('Operation Result'))

    pset_m_threshold = fields.Float(string='Set Threshold Torque(NM)', digits=dp.get_precision('Operation Result'))

    pset_m_target = fields.Float(string='Set Target Torque(NM)', digits=dp.get_precision('Operation Result'))

    pset_w_max = fields.Float(string='Set Max Angel(grad)', digits=dp.get_precision('Operation Result'))

    pset_w_min = fields.Float(string='Set Min Angel(grad)', digits=dp.get_precision('Operation Result'))

    pset_w_threshold = fields.Float(string='Set Threshold Angel(grad)', digits=dp.get_precision('Operation Result'))

    pset_w_target = fields.Float(string='Set Target Angel(grad)', digits=dp.get_precision('Operation Result'))

    cur_objects = fields.Char(string='Curve Files')

    name = fields.Char('Name', default=lambda self: _('New'))
    quality_state = fields.Selection([
        ('none', 'To do'),
        ('exception', 'Exception'),
        ('pass', 'Passed'),
        ('fail', 'Failed')], string='Status', default='none', copy=False)

    exception_reason = fields.Char('Exception Reason')

    user_id = fields.Many2one('res.users', 'Responsible')

    product_id = fields.Many2one('product.product', 'Vehicle',
                                 domain="[('sa_type', '=', 'vehicle')]")

    consu_bom_line_id = fields.Many2one('mrp.wo.consu', 'Consume BOM line')

    program_id = fields.Many2one('controller.program')

    job = fields.Char(string='Job')

    consu_product_id = fields.Many2one('product.product')

    control_date = fields.Datetime('Control Date')

    measure_torque = fields.Float('Measure Torque(NM)', default=0.0, digits=dp.get_precision('Operation Result'),
                                  group_operator="avg")

    measure_degree = fields.Float('Measure Degree(grad)', default=0.0, digits=dp.get_precision('Operation Result'),
                                  group_operator="avg")

    measure_t_don = fields.Float('Measure Time Done(ms)', default=0.0, digits=dp.get_precision('Operation Result'),
                                 group_operator="avg")

    measure_result = fields.Selection([
        ('none', _('No measure')),
        ('lsn', _('LSN')),
        ('ak2', _('AK2')),
        ('ok', _('OK')),
        ('nok', _('NOK'))], string="Measure Success", default='none')

    lacking = fields.Selection([(_('lack'), _('Data Lacking')),
                                (_('normal'), _('Normal'))], string='Lacking', default='lack')

    op_time = fields.Integer(string=u'第几次拧紧作业', default=1)

    one_time_pass = fields.Selection([('pass', _('One Time Passed')),
                                      ('fail', _('Failed'))], string='One Time Pass', default='fail')

    final_pass = fields.Selection([('pass', _('Final Passed')),
                                   ('fail', _('Failed'))], string='Final Pass', default='fail')

    sent = fields.Boolean('Have sent to aiis', default=False)

    batch = fields.Char('Batch')  # 批次信息

    tightening_id = fields.Integer('TighteningID')

    _sql_constraints = [('tid_track_no_gun_uniq', 'unique(tool_id, tightening_id, track_no,time)',
                         'Per Screw Gun tightening ID Tracking Number must different'),
                        ('tid_wo_gun_uniq', 'unique(tool_id, tightening_id, workorder_id,time)',
                         'Per Screw Gun tightening ID  Work Order  must different')]

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE FUNCTION create_operation_result(pset_m_threshold numeric, pset_m_max numeric,
                                                   control_data timestamp without time zone, pset_w_max numeric,
                                                   user_id bigint, one_time_pass boolean,
                                                   pset_strategy varchar, measure_result varchar,
                                                   pset_w_threshold numeric, cur_objects varchar,
                                                   pset_m_target numeric, pset_m_min numeric,
                                                   final_pass varchar, measure_degree numeric,
                                                   measure_t_done numeric, measure_torque numeric, op_time integer,
                                                   pset_w_min numeric, pset_w_target numeric, lacking varchar,
                                                   quality_state varchar, exception_reason varchar, sent boolean,
                                                   batch varchar,
                                                   order_id bigint, nut_no varchar, r_tightening_id integer,
                                                   vin_code varchar, vehicle_type varchar, gun_sn varchar)
  returns BIGINT as
$$
DECLARE
  result_id            bigint;
  r_vin_code           varchar;
  r_job                varchar;
  r_one_time_pass      varchar = 'fail';
  qcp_id               BIGINT  = null;
  consu_bom_id         BIGINT  = null;
  r_consu_product_id   BIGINT  = null;
  r_production_id      BIGINT  = null;
  r_workcenter_id      BIGINT;
  r_gun_id             BIGINT;
  r_product_id         BIGINT;
  r_program_id         BIGINT;
  r_assembly_id        BIGINT;
  r_bom_line_id        BIGINT  = null;
  r_operation_point_id BIGINT  = null;
  r_measure_result     varchar;
  r_expect_order_id    BIGINT  = null;
BEGIN
  case pset_strategy
    when 'LN'
      then r_measure_result = 'lsn';
    ELSE r_measure_result = measure_result;
    end case;
  if one_time_pass
  then
    r_one_time_pass = 'pass';
  end if;

  if order_id != 0
  then
    select mp.track_no,
           qp.id,
           co.id,
           mp.id,
           wo.workcenter_id,
           me.id,
           mp.product_id,
           co.program_id,
           co.product_id,
           mp.assembly_line_id,
           mbl.id,
           mbl.operation_point_id
           into r_vin_code, qcp_id, consu_bom_id, r_production_id, r_workcenter_id, r_gun_id, r_product_id, r_program_id, r_consu_product_id, r_assembly_id,r_bom_line_id,r_operation_point_id
    from public.mrp_workorder wo,
         public.mrp_wo_consu co,
         public.sa_quality_point qp,
         public.mrp_production mp,
         public.product_product pp,
         public.maintenance_equipment me,
         public.mrp_bom_line mbl
    where wo.id = order_id
      and co.workorder_id = order_id
      and pp.default_code = nut_no
      and co.bom_line_id = qp.bom_line_id
      and wo.production_id = mp.id
      and mbl.id = co.bom_line_id
      and me.serial_no = gun_sn
      and co.product_id = pp.id;

    select wo.id into r_expect_order_id
    from public.mrp_workorder wo,
         public.mrp_production mp,
         public.mrp_wo_consu co
    where wo.production_id = mp.id
      and co.workorder_id = wo.id
      and mp.track_no = r_vin_code
      and co.gun_id = r_gun_id
    limit 1;
  else
    r_vin_code = vin_code;
    order_id = null;
    select dd.pid,
           dd.cou_pid,
           job2.code,
           op.workcenter_id,
           gg.gun_id,
           qp2.id,
           dd.cou_bom_id,
           dd.operation_point_id
           into r_product_id, r_consu_product_id,r_job, r_workcenter_id,r_gun_id,qcp_id,r_bom_line_id,r_operation_point_id
    from (select pp.id                  pid,
                 mbl.product_id         cou_pid,
                 mbl.operation_id       cou_opd,
                 mbl.gun_id             cou_gid,
                 mbl.id                 cou_bom_id,
                 mbl.operation_point_id operation_point_id
          from public.product_product pp,
               public.mrp_bom_line mbl,
               public.mrp_bom bom
          where pp.id = bom.product_id
            and pp.default_code = vehicle_type
            and bom.id = mbl.bom_id) as dd,
         (select me.id gun_id
          from public.maintenance_equipment me
          where me.serial_no = gun_sn) as gg,
         public.product_product pp2,
         public.mrp_routing_workcenter op,
         public.sa_quality_point qp2,
         public.controller_job job2
    where pp2.default_code = nut_no
      and pp2.id = cou_pid
      and op.id = cou_opd
      and qp2.bom_line_id = cou_bom_id
      and job2.id = op.op_job_id;

  end if;


  INSERT INTO public.operation_result (pset_m_threshold, pset_m_max, control_date, pset_w_max, user_id,
                                       one_time_pass, pset_strategy, measure_result, pset_w_threshold,
                                       cur_objects, pset_m_target, pset_m_min, final_pass, measure_degree,
                                       measure_t_don,
                                       measure_torque, op_time, pset_w_min, pset_w_target, lacking, quality_state,
                                       exception_reason, sent, batch, track_no,
                                       qcp_id, bom_line_id, operation_point_id, workorder_id,
                                       consu_product_id, consu_bom_line_id,
                                       production_id, tool_id, program_id, product_id, assembly_line_id, workcenter_id,
                                       tightening_id, job, expect_workorder_id,
                                       time)
  VALUES (pset_m_threshold, pset_m_max, control_data, pset_w_max, user_id, r_one_time_pass, pset_strategy,
          r_measure_result,
          pset_w_threshold, cur_objects, pset_m_target, pset_m_min, final_pass, measure_degree,
          measure_t_done, measure_torque, op_time,
          pset_w_min, pset_w_target, lacking,
          quality_state, exception_reason,
          sent, batch, r_vin_code,
          qcp_id, r_bom_line_id, r_operation_point_id, order_id,
          r_consu_product_id,
          consu_bom_id, r_production_id,
          r_gun_id, r_program_id, r_product_id, r_assembly_id,
          r_workcenter_id, r_tightening_id, r_job, r_expect_order_id,
          NOW());

  result_id = lastval();

  RETURN result_id;

END;
$$
  LANGUAGE plpgsql;
            """)

    @api.multi
    def sent_aiis(self):
        results = self.filtered(lambda r: r.measure_result in ['ok', 'nok'])
        if not results:
            return True
        aiis_urls = self.env['ir.config_parameter'].sudo().get_param('aiis.urls')
        if not aiis_urls:
            return
        aiis_urls = aiis_urls.split(',')
        ret = _post_aiis_result_package(aiis_urls, results)
        return True

    # @api.one
    # @api.constrains('cur_objects')
    # def _constraint_curs(self):
    #     try:
    #         obj = json.loads(self.cur_objects)
    #         if not isinstance(obj, list):
    #             raise ValidationError('Waveform File is not a list')
    #     except ValueError:
    #         raise ValidationError('Waveform File is not Schema correct')

    # @api.multi
    # @api.depends('measure_result', 'op_time')
    # def _compute_result_pass(self):
    #     for result in self:
    #         result.one_time_pass = 'fail'
    #         result.final_pass = 'fail'
    #         if result.measure_result != 'ok':
    #             continue
    #         result.final_pass = 'pass'
    #         if result.op_time == 1:
    #             result.one_time_pass = 'pass'

    # @api.multi
    # # @api.depends('measure_torque', 'measure_degree', 'measure_result')
    # @api.depends('measure_result')
    # def _compute_result_lacking(self):
    #     for result in self:
    #         result.lacking = 'lack'
    #         if result.measure_result != 'none': # if result.measure_torque not in [False, 0.0] and result.measure_degree not in [False, 0.0] and result.measure_result != 'none':
    #             result.lacking = 'normal'

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        if not fields:
            return super(OperationResult, self).read(fields, load=load)
        if 'display_name' in fields:
            fields.remove('display_name')
        if '__last_update' in fields:
            fields.remove('__last_update')
        return super(OperationResult, self).read(fields, load=load)

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sa.quality.check') or _('New')
        return super(OperationResult, self).create(vals)

    @api.model
    def _bulk_create(self, all_vals):
        # low-level implementation of create()
        if self.is_transient():
            self._transient_vacuum()

        all_updates = []
        for vals in all_vals:
            if 'name' not in vals or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sa.quality.check') or _('New')
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
            if unknown_fields:
                _logger.warning('No such field(s) in model %s: %s.', self._name, ', '.join(unknown_fields))

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

            if self._log_access:
                updates.append(('create_uid', '%s', self._uid))
                updates.append(('write_uid', '%s', self._uid))
                updates.append(('create_date', "(now() at time zone 'UTC')"))
                updates.append(('write_date', "(now() at time zone 'UTC')"))
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
        return [ids[0] for ids in ids_news]

    @api.model
    def bulk_create(self, vals):
        vals = [self._add_missing_default_values(val) for val in vals]
        self._bulk_create(vals)

    @api.multi
    def write(self, vals):
        # if 'cur_objects' in vals:
        #     cur_objects = list(set(json.loads(vals['cur_objects'])))  # 去重
        #     vals.update({'cur_objects': json.dumps(cur_objects)})
        ret = super(OperationResult, self).write(vals)
        return ret

    @api.multi
    def _bulk_write(self, all_vals):
        all_updates = []
        update_wo_ids = []
        for vals in all_vals:
            updates = []  # list of (column, expr) or (column, pattern, value)
            splite_updates = []
            upd_todo = []  # list of column names to set explicitly
            updend = []  # list of possibly inherited field names
            direct = []  # list of direcly updated columns
            has_trans = self.env.lang and self.env.lang != 'en_US'
            single_lang = len(self.env['res.lang'].get_installed()) <= 1
            for name, val in vals.iteritems():
                field = self._fields[name]
                if field and field.deprecated:
                    _logger.warning('Field %s.%s is deprecated: %s', self._name, name, field.deprecated)
                if field.store:
                    if hasattr(field, 'selection') and val:
                        self._check_selection_field_value(name, val)
                    if field.column_type:
                        # if single_lang or not (has_trans and field.translate is True):
                        #     # val is not a translation: update the table
                        #     val = field.convert_to_column(val, self)
                        updates.append((name, field.column_format,
                                        '''timestamp '%s' ''' % val if field.column_type[0] == 'timestamp' else val))
                        if name != 'id':
                            splite_updates.append((name, field.column_format,
                                                   '''timestamp '%s' ''' % val if field.column_type[
                                                                                      0] == 'timestamp' else val))
                        direct.append(name)
                    else:
                        upd_todo.append(name)
                else:
                    updend.append(name)

            if self._log_access:
                updates.append(('write_uid', '%s', self._uid))
                updates.append(('write_date', "(now() at time zone 'UTC')"))
                direct.append('write_uid')
                direct.append('write_date')
            all_updates.append(updates)
            update_wo_ids.append(splite_updates)

        ### 添加需要重计算字段
        self.modified([u[0] for u in update_wo_ids[0]])
        cr = self._cr
        t = [tuple(u[2] for u in update if len(u) > 2) for update in all_updates]
        x = []
        for _t in t:
            s = '(%s)' % (','.join("'%s'" % _s if (isinstance(_s, str) or isinstance(_s, unicode)) and _s.find(
                'timestamp') < 0 else '%s' % str(_s) for _s in _t))
            x.append(s)
        query = """UPDATE "%s" AS o SET (%s) = (%s) FROM(VALUES %s) AS s (%s) WHERE o.id = s.id""" % (
            self._table,
            ', '.join('%s' % u[0] for u in update_wo_ids[0]),
            ','.join("s.%s" % u[0] for u in update_wo_ids[0]),
            ','.join('%s' % _t for _t in x),
            ', '.join('%s' % u[0] for u in all_updates[0]),
        )

        cr.execute(query)
        map(lambda vals: self.browse(vals['id'])._validate_fields(vals), all_vals)

        # recompute new-style fields
        # if self.env.recompute and self._context.get('recompute', True):
        #     self._bulk_recompute()

        return True

    @api.model
    def _bulk_recompute(self):
        """ Recompute stored function fields. The fields and records to
            recompute have been determined by method :meth:`modified`.
        """
        while self.env.has_todo():
            field, recs = self.env.get_todo()
            # determine the fields to recompute
            fs = self.env[field.model_name]._field_computed[field]
            ns = [f.name for f in fs if f.store]
            # evaluate fields, and group record ids by update
            updates = defaultdict(set)
            for rec in recs.exists():
                vals = rec._convert_to_write({n: rec[n] for n in ns})
                updates[frozendict(vals)].add(rec.id)
            # update records in batch when possible
            with recs.env.norecompute():
                for vals, ids in updates.iteritems():
                    recs.browse(ids)._write(dict(vals))
            # mark computed fields as done
            map(recs._recompute_done, fs)

    @api.multi
    def bulk_write(self, vals):
        if not self:
            return True
        self._check_concurrency()
        self._bulk_write(vals)
        return True

    @api.multi
    def do_fail(self):
        self.write({
            'quality_state': 'fail',
            'user_id': self.env.user.id})
        return True

    @api.multi
    def do_exception(self):
        self.write({
            'quality_state': 'exception',
            'user_id': self.env.user.id})
        return True

    @api.multi
    def get_torques(self, args, limit=1000, order=None):
        query = self._where_calc(args)
        self._apply_ir_rules(query, 'read')
        from_clause, where_clause, where_clause_params = query.get_sql()

        order_by = self._generate_order_by(order, query)

        where_str = where_clause and (" WHERE %s" % where_clause) or ''

        limit_str = limit and ' limit %d' % limit or ''
        query_str = 'SELECT "%s".measure_torque FROM ' % self._table + from_clause + where_str + order_by + limit_str
        self._cr.execute(query_str, where_clause_params)
        res = self._cr.fetchall()

        # TDE note: with auto_join, we could have several lines about the same result
        # i.e. a lead with several unread messages; we uniquify the result using
        # a fast way to do it while preserving order (http://www.peterbe.com/plog/uniqifiers-benchmark)
        # def _uniquify_list(seq):
        #     seen = set()
        #     return [x for x in seq if x not in seen and not seen.add(x)]

        return [x[0] for x in res]

    @api.multi
    def get_angles(self, args, limit=1000, order=None):
        query = self._where_calc(args)
        self._apply_ir_rules(query, 'read')
        from_clause, where_clause, where_clause_params = query.get_sql()

        where_str = where_clause and (" WHERE %s" % where_clause) or ''

        order_by = self._generate_order_by(order, query)

        limit_str = limit and ' limit %d' % limit or ''
        query_str = 'SELECT "%s".measure_degree FROM ' % self._table + from_clause + where_str + order_by + limit_str
        self._cr.execute(query_str, where_clause_params)
        res = self._cr.fetchall()

        # TDE note: with auto_join, we could have several lines about the same result
        # i.e. a lead with several unread messages; we uniquify the result using
        # a fast way to do it while preserving order (http://www.peterbe.com/plog/uniqifiers-benchmark)
        # def _uniquify_list(seq):
        #     seen = set()
        #     return [x for x in seq if x not in seen and not seen.add(x)]

        return [x[0] for x in res]

    @api.multi
    def do_pass(self):
        self.write({'quality_state': 'pass',
                    'user_id': self.env.user.id})
        return True

    @api.multi
    def do_measure(self):
        if self.measure_torque < self.point_id.tolerance_min or self.measure_torque > self.point_id.tolerance_max:
            return self.do_fail()
        elif self.measure_degree < self.point_id.tolerance_min_degree or self.measure_degree > self.point_id.tolerance_max_degree:
            return self.do_fail()
        else:
            return self.do_pass()

    @api.multi
    def unlink(self):
        if self.env.uid != SUPERUSER_ID:
            raise ValidationError(u'不允许删除结果数据')
        return super(OperationResult, self).unlink()
