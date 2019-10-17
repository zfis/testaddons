# -*- coding: utf-8 -*-
from __future__ import division
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
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

    def read_group_qualified(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        self.check_access_rights('read')
        # gun_filter = []
        w_clause_centron_part2 = ""
        w_clause_centron_part1 = ""
        d = list()
        for r in domain:
            if r[0] == 'measure_result':
                continue
            if r[0] == 'gun_id':
                # gun_filter = [r[2]] if isinstance(r[2], int) else r[2]
                if len(w_clause_centron_part1):
                    w_clause_centron_part1 += 'and gun_id = {0}'.format(r[2])
                else:
                    w_clause_centron_part1 += 'where gun_id = {0}'.format(r[2])
                w_clause_centron_part2 += 'and r1.gun_id = {0}'.format(r[2])
                continue
            if r[0] == 'vin':
                # 过滤vin
                if len(w_clause_centron_part1):
                    w_clause_centron_part1 += "and vin ilike \'%{0}%\'".format(r[2])
                else:
                    w_clause_centron_part1 += "where vin ilike \'%{0}%\'".format(r[2])
                w_clause_centron_part2 += "and r1.vin ilike \'%{0}%\'".format(r[2])
                continue
            d.append(r)
        domain = d
        query = self._where_calc(domain)
        fields = fields or [f.name for f in self._fields.itervalues() if f.store]

        groupby = [groupby] if isinstance(groupby, basestring) else list(OrderedSet(groupby))
        groupby_list = groupby[:1] if lazy else groupby
        annotated_groupbys1 = [self._read_group_process_groupby(gb, query) for gb in groupby_list]
        one_time_pass_state = False
        for gb in annotated_groupbys1:
            if gb['field'] == 'final_pass':
                gb['qualified_field'] = "\'final\'"
            if gb['field'] == 'one_time_pass':
                one_time_pass_state = True
                gb['qualified_field'] = "\'one time\'"
            if gb['field'] == 'control_date':
                gb['qualified_field'] = "d1.control_date"
                gb['tz_convert'] = False

        if one_time_pass_state:
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
                                        (select sum(b.sequence) as sequence, date_trunc('%(interval)s', timezone('Asia/Chongqing', timezone('UTC', mw.date_planned_start))) as control_date from
                                        (select  vin,product_id,min(control_date) as date_planned_start  from operation_result
                                        %(where_clause_part1)s
                                        group by vin,product_id) mw
                                        left join
                                        (select  a.product_id,count(*) as sequence from mrp_bom a
                                        left join mrp_bom_line b on a.id=b.bom_id
                                        group by a.product_id) b on mw.product_id=b.product_id
                                        group by control_date
                                        ) d1
                                       ,
                                        (SELECT  count (mw.batch) as sequence,  date_trunc('%(interval)s', timezone('Asia/Chongqing', timezone('UTC', mw.date_planned_start))) as control_date FROM
                                        (select DISTINCT mw.date_planned_start,r1.VIN,r1.batch from operation_result r1
                                        LEFT JOIN (select  vin,product_id,min(control_date) as date_planned_start  from operation_result
                                        group by vin,product_id) mw ON R1.vin=MW.vin
                                        where   %(interval2)s and  r1.measure_result in ('ok','nok') %(where_clause_part2)s) mw
                                        group by control_date
                                        ) d2 
                                    """ % {
            'interval': annotated_groupbys[0]['groupby'].split(':')[-1] if annotated_groupbys[0][
                                                                               'field'] == 'control_date' else
            annotated_groupbys[1]['groupby'].split(':')[-1],
            'interval2': ''' r1.one_time_pass='pass' ''' if one_time_pass_state else ''' r1.final_pass='pass' ''',
            'where_clause_part1': w_clause_centron_part1,
            'where_clause_part2': w_clause_centron_part2
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

    def read_group_qualified_byvin(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        self.check_access_rights('read')
        w_clause_centron_part2 = ""
        d = list()
        for r in domain:
            if r[0] == 'measure_result':
                continue
            if r[0] == 'gun_id':
                w_clause_centron_part2 += 'and r1.gun_id = {0}'.format(r[2])
                continue
            d.append(r)
        domain = d
        query = self._where_calc(domain)
        fields = fields or [f.name for f in self._fields.itervalues() if f.store]

        groupby = [groupby] if isinstance(groupby, basestring) else list(OrderedSet(groupby))
        groupby_list = groupby[:1] if lazy else groupby
        annotated_groupbys1 = [self._read_group_process_groupby(gb, query) for gb in groupby_list]
        one_time_pass_state = False
        for gb in annotated_groupbys1:
            if gb['field'] == 'final_pass':
                gb['qualified_field'] = "\'final\'"
            if gb['field'] == 'one_time_pass':
                one_time_pass_state = True
                gb['qualified_field'] = "\'one time\'"
            if gb['field'] == 'vin':
                gb['qualified_field'] = "d1.vin"

        if one_time_pass_state:
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
                    (select a.vin,sum(COALESCE(b.sequence, 0)) as sequence from
                    (select  distinct  vin,product_id from operation_result) a
                    left join
                    (select  a.product_id,count(*) as sequence from mrp_bom a
                    left join mrp_bom_line b on a.id=b.bom_id
                    group by a.product_id) b on a.product_id=b.product_id
                    group by a.vin) d1
                    left join 
                    (select  a.VIN,count (a.*) as sequence  from (
                    select distinct r1.VIN,r1.point_id,r1.batch from operation_result r1
                    where  %(interval2)s  and  r1.measure_result in ('ok','nok') %(where_clause)s) a
                    group by a.VIN) d2  on d1.VIN = d2.VIN
                    left join 
                    (select  vin,min(control_date) as control_date  from operation_result
                      group by vin) d3 on d1.VIN = d3.VIN
                        """ % {
            'interval2': ''' r1.one_time_pass='pass' ''' if one_time_pass_state else ''' r1.final_pass='pass' ''',
            'where_clause': w_clause_centron_part2
        }

        if where_clause == '':
            where_clause = ''
        else:
            if where_clause.find('''"operation_result"."vin"''') > 0:
                where_clause = where_clause.replace('''"operation_result"."vin"''', '''"d1"."vin"''')
            if where_clause.find('''"operation_result"."control_date"''') > 0:
                where_clause = where_clause.replace('''"operation_result"."control_date"''', '''"d3"."control_date"''')
            where_clause += ''

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
        """
        for d in fetched_data:
            n = {'consu_product_id': self.env['product.product'].browse(d['consu_product_id']).name_get()[0]}
            d.update(n)
        """
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
        if 'vin' in groupby:
            domain_fields = [r[0] for r in domain]
            if 'vin' not in domain_fields:
                raise UserError(u"通过VIN号分组,必须添加VIN过滤")
        if 'measure_result' in fields and 'measure_result' not in groupby:
            groupby.append('measure_result')
            res = super(OperationResult, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                          orderby=orderby, lazy=lazy)
        elif ('one_time_pass' in groupby or 'final_pass' in groupby) and len(groupby) >= 2:
            if 'vin' in groupby:
                res = self.read_group_qualified_byvin(domain, fields, groupby, offset=offset, limit=limit,
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
