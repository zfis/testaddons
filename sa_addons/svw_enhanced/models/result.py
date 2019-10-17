# -*- coding: utf-8 -*-
from __future__ import division
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import odoo.addons.decimal_precision as dp
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import CountingStream, DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import babel.dates
import pytz
from odoo.osv import expression
import logging
from odoo.tools import float_round, frozendict, lazy_classproperty, lazy_property, ormcache, \
    Collector, LastOrderedSet, OrderedSet

from collections import defaultdict, MutableMapping, OrderedDict
from odoo.tools import frozendict


class OperationResult(models.HyperModel):
    _inherit = "operation.result"

    @api.model
    def _read_group_format_result_centron(self, data, annotated_groupbys, groupby, domain):
        """
            Helper method to format the data contained in the dictionary data by
            adding the domain corresponding to its values, the groupbys in the
            context and by properly formatting the date/datetime values.

        :param data: a single group
        :param annotated_groupbys: expanded grouping metainformation
        :param groupby: original grouping metainformation
        :param domain: original domain for read_group
        """

        sections = []
        for gb in annotated_groupbys:
            ftype = gb['type']
            value = data[gb['groupby']]

            # full domain for this groupby spec
            d = None
            if value:
                if ftype == 'many2one':
                    value = value[0]
                elif ftype in ('date', 'datetime'):
                    locale = self._context.get('lang') or 'en_US'
                    fmt = DEFAULT_SERVER_DATETIME_FORMAT if ftype == 'datetime' else DEFAULT_SERVER_DATE_FORMAT
                    tzinfo = None
                    range_start = value
                    range_end = value + gb['interval']
                    # value from postgres is in local tz (so range is
                    # considered in local tz e.g. "day" is [00:00, 00:00[
                    # local rather than UTC which could be [11:00, 11:00]
                    # local) but domain and raw value should be in UTC
                    if gb['tz_convert']:
                        tzinfo = range_start.tzinfo
                        range_start = range_start.astimezone(pytz.utc)
                        range_end = range_end.astimezone(pytz.utc)

                    range_start = range_start.strftime(fmt)
                    range_end = range_end.strftime(fmt)
                    if ftype == 'datetime':
                        label = babel.dates.format_datetime(
                            value, format=gb['display_format'],
                            tzinfo=tzinfo, locale=locale
                        )
                    else:
                        label = babel.dates.format_date(
                            value, format=gb['display_format'],
                            locale=locale
                        )
                    data[gb['groupby']] = ('%s/%s' % (range_start, range_end), label)
                    d = [
                        '&',
                        (gb['field'], '>=', range_start),
                        (gb['field'], '<', range_end),
                    ]
            if d is None:
                d = [(gb['field'], '=', value)]
            sections.append(d)
        sections.append(domain)

        data['__domain'] = expression.AND(sections)
        if len(groupby) - len(annotated_groupbys) >= 1:
            data['__context'] = {'group_by': groupby[len(annotated_groupbys):]}
        return data

    @api.model
    def read_group_lacking_by_gun(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        self.check_access_rights('read')
        query = self._where_calc(domain)
        fields = fields or [f.name for f in self._fields.itervalues() if f.store]

        groupby = [groupby] if isinstance(groupby, basestring) else list(OrderedSet(groupby))
        groupby_list = groupby[:1] if lazy else groupby
        annotated_groupbys = [self._read_group_process_groupby(gb, query) for gb in groupby_list]
        for gb in annotated_groupbys:
            if gb['field'] == 'lacking':
                gb['qualified_field'] = "\'lack\'"
            if gb['field'] == 'gun_id':
                gb['qualified_field'] = "a1.equip_id"
        groupby_fields = [g['field'] for g in annotated_groupbys]
        order = orderby or ','.join([g for g in groupby_list])
        groupby_dict = {gb['groupby']: gb for gb in annotated_groupbys}

        self._apply_ir_rules(query, 'read')
        for gb in groupby_fields:
            assert gb in fields, "Fields in 'groupby' must appear in the list of fields to read (perhaps it's missing in the list view?)"
            assert gb in self._fields, "Unknown field %r in 'groupby'" % gb
            gb_field = self._fields[gb].base_field
            assert gb_field.store and gb_field.column_type, "Fields in 'groupby' must be regular database-persisted fields (no function or related fields), or function fields with store=True"

        aggregated_fields = [
            f for f in fields
            if f != 'sequence'
            if f not in groupby_fields
            for field in [self._fields.get(f)]
            if field
            if field.group_operator
            if field.base_field.store and field.base_field.column_type
        ]

        field_formatter = lambda f: (
            self._fields[f].group_operator,
            self._inherits_join_calc(self._table, f, query),
            f,
        )
        select_terms = ['%s(%s) AS "%s" ' % field_formatter(f) for f in aggregated_fields]

        for gb in annotated_groupbys:
            select_terms.append('%s as "%s" ' % (gb['qualified_field'], gb['groupby']))

        groupby_terms, orderby_terms = self._read_group_prepare(order, aggregated_fields, annotated_groupbys, query)
        from_clause, where_clause, where_clause_params = query.get_sql()
        if lazy and (len(groupby_fields) >= 2 or not self._context.get('group_by_no_leaf')):
            count_field = groupby_fields[0] if len(groupby_fields) >= 1 else '_'
        else:
            count_field = '_'
        count_field += '_count'

        prefix_terms = lambda prefix, terms: (prefix + " " + ",".join(terms)) if terms else ''
        prefix_term = lambda prefix, term: ('%s %s' % (prefix, term)) if term else ''

        where_clause2 = '''r1.measure_result in ('ok', 'nok')'''  # 初始化为空

        if where_clause == '':
            where_clause2 = '''r1.measure_result in ('ok', 'nok')'''
        else:
            if where_clause.find('''"operation_result"."control_date"''') > 0:
                where_clause = where_clause.replace('''"operation_result"."control_date"''',
                                                    '''"mw"."date_planned_start"''')

                where_clause_params.extend(where_clause_params[:])
            where_clause2 = where_clause + '''AND r1.measure_result in ('ok', 'nok')'''
        from_clause = '''
                            (select id as equip_id,serial_no as equip_sn, name as equip_name
                              from maintenance_equipment, d1
                              where category_id = d1.gc_id
                             ) a1
                        left join (select a.gun_id,count(a.sequence)  as sequence from mrp_wo_consu a
                                          left join mrp_workorder mw on a.workorder_id = mw.id
                                          %(where)s
                                          group by gun_id) a on a1.equip_id = a.gun_id
                        left join (select gun_id,count(batch) as sequence from
                                          (select distinct r1.workorder_id,r1.gun_id,r1.batch from operation_result r1
                                                left join mrp_workorder mw on r1.workorder_id = mw.id
                                                %(where2)s
                                          ) a group by gun_id) b   on a.gun_id = b.gun_id
                ''' % {
            'where': prefix_term('WHERE', where_clause),
            'where2': prefix_term('WHERE', where_clause2),
        }

        query = """
                    with d1 as ( select id as gc_id from maintenance_equipment_category where name = 'Gun')
                    SELECT  round(round(COALESCE(a.sequence, 0) - COALESCE(b.sequence, 0), 2) / COALESCE(a.sequence, 1) * 100.0, 2) AS "%(count_field)s" %(extra_fields)s
                            FROM %(from)s
                            %(orderby)s
                            %(limit)s
                            %(offset)s
                        """ % {
            'table': self._table,
            'count_field': count_field,
            'extra_fields': prefix_terms(',', select_terms),
            'from': from_clause,
            # 'where': prefix_term('WHERE', where_clause),
            'orderby': 'ORDER BY ' + count_field,
            'limit': prefix_term('LIMIT', int(limit) if limit else None),
            'offset': prefix_term('OFFSET', int(offset) if limit else None),
        }
        self._cr.execute(query, where_clause_params)
        fetched_data = self._cr.dictfetchall()

        if not groupby_fields:
            return fetched_data

        for d in fetched_data:
            n = {'gun_id': self.env['maintenance.equipment'].browse(d['gun_id']).name_get()[0]}
            d.update(n)

        data = map(lambda r: {k: self._read_group_prepare_data(k, v, groupby_dict) for k, v in r.iteritems()},
                   fetched_data)
        result = [self._read_group_format_result_centron(d, annotated_groupbys, groupby, domain) for d in data]

        return result

    @api.model
    def read_group_lacking(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        self.check_access_rights('read')
        query = self._where_calc(domain)
        fields = fields or [f.name for f in self._fields.itervalues() if f.store]

        groupby = [groupby] if isinstance(groupby, basestring) else list(OrderedSet(groupby))
        groupby_list = groupby[:1] if lazy else groupby
        annotated_groupbys = [self._read_group_process_groupby(gb, query) for gb in groupby_list]
        for gb in annotated_groupbys:
            if gb['field'] == 'lacking':
                gb['qualified_field'] = "\'lack\'"
            if gb['field'] == 'control_date':
                gb['qualified_field'] = "d1.control_date"
        groupby_fields = [g['field'] for g in annotated_groupbys]
        order = orderby or ','.join([g for g in groupby_list])
        groupby_dict = {gb['groupby']: gb for gb in annotated_groupbys}

        self._apply_ir_rules(query, 'read')
        for gb in groupby_fields:
            assert gb in fields, "Fields in 'groupby' must appear in the list of fields to read (perhaps it's missing in the list view?)"
            assert gb in self._fields, "Unknown field %r in 'groupby'" % gb
            gb_field = self._fields[gb].base_field
            assert gb_field.store and gb_field.column_type, "Fields in 'groupby' must be regular database-persisted fields (no function or related fields), or function fields with store=True"

        aggregated_fields = [
            f for f in fields
            if f != 'sequence'
            if f not in groupby_fields
            for field in [self._fields.get(f)]
            if field
            if field.group_operator
            if field.base_field.store and field.base_field.column_type
        ]

        field_formatter = lambda f: (
            self._fields[f].group_operator,
            self._inherits_join_calc(self._table, f, query),
            f,
        )
        select_terms = ['%s(%s) AS "%s" ' % field_formatter(f) for f in aggregated_fields]

        for gb in annotated_groupbys:
            select_terms.append('%s as "%s" ' % (gb['qualified_field'], gb['groupby']))

        groupby_terms, orderby_terms = self._read_group_prepare(order, aggregated_fields, annotated_groupbys, query)
        from_clause, where_clause, where_clause_params = query.get_sql()
        if lazy and (len(groupby_fields) >= 2 or not self._context.get('group_by_no_leaf')):
            count_field = groupby_fields[0] if len(groupby_fields) >= 1 else '_'
        else:
            count_field = '_'
        count_field += '_count'

        prefix_terms = lambda prefix, terms: (prefix + " " + ",".join(terms)) if terms else ''
        prefix_term = lambda prefix, term: ('%s %s' % (prefix, term)) if term else ''

        from_clause = '''
                    (select sum(dd.count)                                                                             as acount,
                             date_trunc('%(interval)s', timezone('Asia/Chongqing', timezone('UTC', mp.date_planned_start))) as control_date
                      from (select count(op.*) as count, mw.id as wo_id, mw.production_id as mpdid
                            from mrp_routing_workcenter mrw,
                                 operation_point op,
                                 mrp_workorder mw
                            where mw.operation_id = mrw.id
                              and op.operation_id = mrw.id
                            group by mw.id) dd,
                           mrp_production mp
                      where dd.mpdid = mp.id
                      group by control_date
                      order by control_date) d1,
                     (select sum(dd.count)                                                                             as rs,
                             date_trunc('%(interval)s', timezone('Asia/Chongqing', timezone('UTC', mp.date_planned_start))) as control_date
                      from (select count(e.oprb) as count, e.oprw as oprw
                            from (select distinct opr.batch as oprb, opr.workorder_id as oprw
                                  from operation_result opr
                                  group by opr.workorder_id, opr.batch) as e
                            group by oprw) dd,
                           mrp_workorder mw,
                           mrp_production mp
                      where mw.id = dd.oprw and mp.id = mw.production_id
                      group by control_date
                      order by control_date) d2
        ''' % {
            'interval': annotated_groupbys[0]['groupby'].split(':')[-1] if annotated_groupbys[0][
                                                                               'field'] == 'control_date' else
            annotated_groupbys[1]['groupby'].split(':')[-1],
        }

        if where_clause == '':
            where_clause = 'd1.control_date = d2.control_date'
        else:
            if where_clause.find('''"operation_result"."control_date"''') > 0:
                where_clause = where_clause.replace('''"operation_result"."control_date"''', '''"d1"."control_date"''')
            where_clause += 'AND d1.control_date = d2.control_date'

        query = """
                    SELECT round((d1.acount - d2.rs) / NULLIF(d1.acount, 0) * 100.0, 4) AS "%(count_field)s" %(extra_fields)s
                    FROM %(from)s
                    %(where)s
                    %(orderby)s
                    %(limit)s
                    %(offset)s
                """ % {
            'table': self._table,
            'count_field': count_field,
            'extra_fields': prefix_terms(',', select_terms),
            'from': from_clause,
            'where': prefix_term('WHERE', where_clause),
            'orderby': 'ORDER BY ' + count_field,
            'limit': prefix_term('LIMIT', int(limit) if limit else None),
            'offset': prefix_term('OFFSET', int(offset) if limit else None),
        }
        self._cr.execute(query, where_clause_params)
        fetched_data = self._cr.dictfetchall()

        if not groupby_fields:
            return fetched_data

        many2onefields = [gb['field'] for gb in annotated_groupbys if gb['type'] == 'many2one']
        if many2onefields:
            data_ids = [r['id'] for r in fetched_data]
            many2onefields = list(set(many2onefields))
            data_dict = {d['id']: d for d in self.browse(data_ids).read(many2onefields)}
            for d in fetched_data:
                d.update(data_dict[d['id']])

        data = map(lambda r: {k: self._read_group_prepare_data(k, v, groupby_dict) for k, v in r.iteritems()},
                   fetched_data)
        result = [self._read_group_format_result_centron(d, annotated_groupbys, groupby, domain) for d in data]

        return result

    def read_group_qualified(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        self.check_access_rights('read')
        query = self._where_calc(domain)
        fields = fields or [f.name for f in self._fields.itervalues() if f.store]

        groupby = [groupby] if isinstance(groupby, basestring) else list(OrderedSet(groupby))
        groupby_list = groupby[:1] if lazy else groupby
        annotated_groupbys1 = [self._read_group_process_groupby(gb, query) for gb in groupby_list]
        one_time_pass_state = 0
        for gb in annotated_groupbys1:
            if gb['field'] == 'final_pass':
                gb['qualified_field'] = "\'final\'"
            if gb['field'] == 'one_time_pass':
                one_time_pass_state = 1
                gb['qualified_field'] = "\'once\'"
            if gb['field'] == 'control_date':
                gb['qualified_field'] = "d1.control_date"

        if one_time_pass_state == 1:
            annotated_groupbys = [gb for gb in annotated_groupbys1 if gb['field'] != 'final_pass']
        else:
            annotated_groupbys = [gb for gb in annotated_groupbys1 if gb['field'] != 'one_time_pass']

        groupby_fields = [g['field'] for g in annotated_groupbys]
        order = orderby or ','.join([g for g in groupby_list])
        groupby_dict = {gb['groupby']: gb for gb in annotated_groupbys}

        self._apply_ir_rules(query, 'read')
        for gb in groupby_fields:
            assert gb in fields, "Fields in 'groupby' must appear in the list of fields to read (perhaps it's missing in the list view?)"
            assert gb in self._fields, "Unknown field %r in 'groupby'" % gb
            gb_field = self._fields[gb].base_field
            assert gb_field.store and gb_field.column_type, "Fields in 'groupby' must be regular database-persisted fields (no function or related fields), or function fields with store=True"

        aggregated_fields = [
            f for f in fields
            if f != 'sequence'
            if f not in groupby_fields
            for field in [self._fields.get(f)]
            if field
            if field.group_operator
            if field.base_field.store and field.base_field.column_type
        ]

        field_formatter = lambda f: (
            self._fields[f].group_operator,
            self._inherits_join_calc(self._table, f, query),
            f,
        )
        select_terms = ['%s(%s) AS "%s" ' % field_formatter(f) for f in aggregated_fields]

        for gb in annotated_groupbys:
            select_terms.append('%s as "%s" ' % (gb['qualified_field'], gb['groupby']))

        groupby_terms, orderby_terms = self._read_group_prepare(order, aggregated_fields, annotated_groupbys, query)
        from_clause, where_clause, where_clause_params = query.get_sql()
        if lazy and (len(groupby_fields) >= 2 or not self._context.get('group_by_no_leaf')):
            count_field = groupby_fields[0] if len(groupby_fields) >= 1 else '_'
        else:
            count_field = '_'
        count_field += '_count'

        prefix_terms = lambda prefix, terms: (prefix + " " + ",".join(terms)) if terms else ''
        prefix_term = lambda prefix, term: ('%s %s' % (prefix, term)) if term else ''

        from_clause = """
                            (select count(a.sequence)  as sequence,
                             date_trunc('%(interval)s', timezone('Asia/Chongqing', timezone('UTC', mw.date_planned_start))) as control_date
                            from mrp_wo_consu a
                            left join mrp_workorder mw on a.workorder_id = mw.id
                             where mw.date_planned_start is not null
                            group by control_date) d1,
                            (select count(a.batch)  as sequence  ,
                             date_trunc('%(interval)s', timezone('Asia/Chongqing', timezone('UTC', mw.date_planned_start))) as control_date
                             from
                                (select distinct r1.workorder_id,r1.batch from operation_result r1
                            left join mrp_workorder mw on r1.workorder_id = mw.id  %(interval2)s and  r1.measure_result in ('ok','nok')
                            )a
                             left join  mrp_workorder mw on a.workorder_id=mw.id
                            where mw.date_planned_start is not null
                            group by control_date) d2
                    """ % {

            'interval': annotated_groupbys[0]['groupby'].split(':')[-1] if annotated_groupbys[0][
                                                                               'field'] == 'control_date' else
            annotated_groupbys[1]['groupby'].split(':')[-1],
            'interval2': '''and r1.one_time_pass='true' ''' if one_time_pass_state == 1 else '''and r1.final_pass='pass' ''',
        }

        if where_clause == '':
            where_clause = 'd1.control_date = d2.control_date'
        else:
            if where_clause.find('''"operation_result"."control_date"''') > 0:
                where_clause = where_clause.replace('''"operation_result"."control_date"''', '''"d1"."control_date"''')
            where_clause += 'AND d1.control_date = d2.control_date'

        query = """
                    SELECT round(round(d2.sequence,2)/ NULLIF(d1.sequence, 0) * 100.0, 4) AS "%(count_field)s" %(extra_fields)s
                    FROM %(from)s
                    %(where)s
                    %(orderby)s
                    %(limit)s
                    %(offset)s
                """ % {
            'table': self._table,
            'count_field': count_field,
            'extra_fields': prefix_terms(',', select_terms),
            'from': from_clause,
            'where': prefix_term('WHERE', where_clause),
            'orderby': 'ORDER BY ' + count_field,
            'limit': prefix_term('LIMIT', int(limit) if limit else None),
            'offset': prefix_term('OFFSET', int(offset) if limit else None),
        }

        self._cr.execute(query, where_clause_params)
        fetched_data = self._cr.dictfetchall()

        if not groupby_fields:
            return fetched_data

        many2onefields = [gb['field'] for gb in annotated_groupbys if gb['type'] == 'many2one']
        if many2onefields:
            data_ids = [r['id'] for r in fetched_data]
            many2onefields = list(set(many2onefields))
            data_dict = {d['id']: d for d in self.browse(data_ids).read(many2onefields)}
            for d in fetched_data:
                d.update(data_dict[d['id']])

        data = map(lambda r: {k: self._read_group_prepare_data(k, v, groupby_dict) for k, v in r.iteritems()},
                   fetched_data)
        result = [self._read_group_format_result_centron(d, annotated_groupbys, groupby, domain) for d in data]

        return result

    def read_group_qualified_bynut(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        self.check_access_rights('read')
        query = self._where_calc(domain)
        fields = fields or [f.name for f in self._fields.itervalues() if f.store]

        groupby = [groupby] if isinstance(groupby, basestring) else list(OrderedSet(groupby))
        groupby_list = groupby[:1] if lazy else groupby
        annotated_groupbys1 = [self._read_group_process_groupby(gb, query) for gb in groupby_list]
        one_time_pass_state = 0
        for gb in annotated_groupbys1:
            if gb['field'] == 'final_pass':
                gb['qualified_field'] = "\'final\'"
            if gb['field'] == 'one_time_pass':
                one_time_pass_state = 1
                gb['qualified_field'] = "\'once\'"
            if gb['field'] == 'consu_product_id':
                gb['qualified_field'] = "d1.consu_product_id"

        if one_time_pass_state == 1:
            annotated_groupbys = [gb for gb in annotated_groupbys1 if gb['field'] != 'final_pass']
        else:
            annotated_groupbys = [gb for gb in annotated_groupbys1 if gb['field'] != 'one_time_pass']

        groupby_fields = [g['field'] for g in annotated_groupbys]
        order = orderby or ','.join([g for g in groupby_list])
        groupby_dict = {gb['groupby']: gb for gb in annotated_groupbys}

        self._apply_ir_rules(query, 'read')
        for gb in groupby_fields:
            assert gb in fields, "Fields in 'groupby' must appear in the list of fields to read (perhaps it's missing in the list view?)"
            assert gb in self._fields, "Unknown field %r in 'groupby'" % gb
            gb_field = self._fields[gb].base_field
            assert gb_field.store and gb_field.column_type, "Fields in 'groupby' must be regular database-persisted fields (no function or related fields), or function fields with store=True"

        aggregated_fields = [
            f for f in fields
            if f != 'sequence'
            if f not in groupby_fields
            for field in [self._fields.get(f)]
            if field
            if field.group_operator
            if field.base_field.store and field.base_field.column_type
        ]

        field_formatter = lambda f: (
            self._fields[f].group_operator,
            self._inherits_join_calc(self._table, f, query),
            f,
        )
        select_terms = ['%s(%s) AS "%s" ' % field_formatter(f) for f in aggregated_fields]

        for gb in annotated_groupbys:
            select_terms.append('%s as "%s" ' % (gb['qualified_field'], gb['groupby']))

        groupby_terms, orderby_terms = self._read_group_prepare(order, aggregated_fields, annotated_groupbys, query)
        from_clause, where_clause, where_clause_params = query.get_sql()
        if lazy and (len(groupby_fields) >= 2 or not self._context.get('group_by_no_leaf')):
            count_field = groupby_fields[0] if len(groupby_fields) >= 1 else '_'
        else:
            count_field = '_'
        count_field += '_count'

        prefix_terms = lambda prefix, terms: (prefix + " " + ",".join(terms)) if terms else ''
        prefix_term = lambda prefix, term: ('%s %s' % (prefix, term)) if term else ''

        from_clause = """
                            (select consu_product_id,count (*) as sequence  from (
       select distinct r1.consu_product_id,r1.workorder_id,r1.batch from operation_result r1
       where %(interval2)s and  r1.measure_result in ('ok','nok')) a
group by consu_product_id) d1,
(select a.product_id as consu_product_id,count (*) as sequence from  mrp_wo_consu a left join mrp_workorder mw on a.workorder_id = mw.id
group by consu_product_id)d2
                    """ % {
            'interval2': ''' r1.one_time_pass='true' ''' if one_time_pass_state == 1 else ''' r1.final_pass='pass' ''',
        }

        if where_clause == '':
            where_clause = 'd1.consu_product_id = d2.consu_product_id'
        else:
            if where_clause.find('''"operation_result"."control_date"''') > 0:
                where_clause = where_clause.replace('''"operation_result"."control_date"''', '''"d1"."control_date"''')
            if where_clause.find('''"operation_result"."consu_product_id"''') > 0:
                where_clause = where_clause.replace('''"operation_result"."consu_product_id"''',
                                                    '''"d1"."consu_product_id"''')
            where_clause += 'AND d1.consu_product_id = d2.consu_product_id'

        query = """
                    SELECT round(round(d1.sequence,2)/ NULLIF(d2.sequence, 0) * 100.0, 4) AS "%(count_field)s" %(extra_fields)s
                    FROM %(from)s
                    %(where)s
                    %(orderby)s
                    %(limit)s
                    %(offset)s
                """ % {
            'table': self._table,
            'count_field': count_field,
            'extra_fields': prefix_terms(',', select_terms),
            'from': from_clause,
            'where': prefix_term('WHERE', where_clause),
            'orderby': 'ORDER BY ' + count_field,
            'limit': prefix_term('LIMIT', int(limit) if limit else None),
            'offset': prefix_term('OFFSET', int(offset) if limit else None),
        }

        self._cr.execute(query, where_clause_params)
        fetched_data = self._cr.dictfetchall()

        if not groupby_fields:
            return fetched_data

        for d in fetched_data:
            n = {'consu_product_id': self.env['product.product'].browse(d['consu_product_id']).name_get()[0]}
            d.update(n)

        """
        for d in fetched_data:
           n = {'consu_product_id': """
        # (%(from)s,'test')
        """ % {'from': d['consu_product_id']}}
            d.update(n)
        """
        data = map(lambda r: {k: self._read_group_prepare_data(k, v, groupby_dict) for k, v in r.iteritems()},
                   fetched_data)
        result = [self._read_group_format_result_centron(d, annotated_groupbys, groupby, domain) for d in data]

        return result

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=False):
        _cache = {}
        if 'measure_result' in fields and 'measure_result' not in groupby:
            groupby.append('measure_result')
            res = super(OperationResult, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                          orderby=orderby, lazy=lazy)
        elif 'lacking' in fields and len(groupby) >= 2:
            if 'gun_id' in groupby:
                # res = super(OperationResult, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                #                                               orderby=orderby, lazy=lazy)
                res = self.read_group_lacking_by_gun(domain, fields, groupby, offset=offset, limit=limit,
                                                     orderby=orderby, lazy=lazy)
            else:
                res = self.read_group_lacking(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby,
                                              lazy=lazy)

        elif ('one_time_pass' in groupby or 'final_pass' in groupby) and len(groupby) >= 2:
            if 'consu_product_id' in groupby:
                res = self.read_group_qualified_bynut(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby,
                                                      lazy=lazy)
            else:
                res = self.read_group_qualified(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby,
                                                lazy=lazy)
        else:
            res = super(OperationResult, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                          orderby=orderby, lazy=lazy)
        if 'measure_result' in fields:
            for line in res:
                if '__count' not in line.keys():
                    continue
                _domain = []
                last_domain = None
                if '__domain' in line:
                    for d in line['__domain']:
                        if d[0] == 'measure_result':
                            if last_domain == '|':
                                _domain.pop() if len(_domain) else None
                            else:
                                _domain.pop(0) if len(_domain) else None
                        else:
                            _domain.append(d)
                        last_domain = d
                k = repr(_domain)
                if k not in _cache.keys():
                    _domain += [('measure_result', 'in', ['ok', 'nok'])]
                    _cache[k] = self.search_count(_domain)
                count = _cache[k]
                try:
                    inv_value = float_round(line['__count'] / count, precision_digits=3)
                except ZeroDivisionError:
                    inv_value = 0
                line['__count'] = inv_value

        res = sorted(res, key=lambda l: next(v for (line_key, v) in l.iteritems() if '__count' or '_count' in line_key),
                     reverse=True)

        return res
