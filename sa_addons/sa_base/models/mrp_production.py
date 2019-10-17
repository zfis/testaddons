# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MrpWOConsu(models.Model):
    _name = 'mrp.wo.consu'

    _order = "sequence"

    _log_access = False

    sequence = fields.Integer(string='Sequence')

    workorder_id = fields.Many2one('mrp.workorder')

    bom_line_id = fields.Many2one('mrp.bom.line')

    product_id = fields.Many2one('product.product', string='Consume Product')
    qty = fields.Float('Consume Product Qty')

    gun_id = fields.Many2one('maintenance.equipment', string='Screw Gun', copy=False)

    program_id = fields.Many2one('controller.program')

    @api.model
    def _bulk_create(self, all_vals):
        # low-level implementation of create()
        if self.is_transient():
            self._transient_vacuum()

        all_updates = []
        for vals in all_vals:
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


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    track_no = fields.Char('Finished Product Tracking Number', related='production_id.track_no')

    consu_bom_line_ids = fields.One2many('mrp.wo.consu', 'workorder_id', string='Consume Product')

    @api.multi
    def unlink(self):
        raise ValidationError(u'不允许删除工单')


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    track_no = fields.Char('Finished Product Tracking Number')


    assembly_line_id = fields.Many2one('mrp.assemblyline', string='Assembly Line ID')
