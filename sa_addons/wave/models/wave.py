# -*- coding: utf-8 -*-

from odoo import models, fields, api
from pyecharts import Line
import pyecharts
from minio import Minio
from urlparse import urlsplit
import json
from pandas import DataFrame, merge_ordered, merge_asof
import itertools
from boltons.cacheutils import LRU

minioClient = None

_wave_cache = LRU(max_size=128)


def _create_wave_result_dict(x, data):
    # _ret = dict()
    # _ret['name'] = x
    _data = json.loads(data)
    # _ret['result'] = _data['result']  # 不是dataframe 对象
    # _data.pop('result')
    # _data[u'{0}'.format(x)] = _data['cur_m']
    # _data.pop('cur_m')
    # _ret['wave'] = DataFrame.from_dict(_data)
    _data['name'] = x.split('.')[0]
    _wave_cache[x] = _data  # 将其加入缓存

    return _data


class Wave(models.TransientModel):
    '''
        瞬态模型. 不需要持久化
    '''
    _name = 'wave.wave'
    _description = 'Waveform scope wizard'

    # . In its computed method do::

    query_date_from = fields.Datetime(string='Query Date From')
    query_date_to = fields.Datetime(string='Query Date to', default=fields.Datetime.now())
    vehicle_id = fields.Many2one('product.product', string='Vehicle Type', domain=[('sa_type', '=', 'vehicle')])
    screw_id = fields.Many2one('product.product', string='Screw Type', domain=[('sa_type', '=', 'screw')])
    assembly_line_id = fields.Many2one('mrp.assemblyline', string='Assembly Line')
    segment_id = fields.Many2one('mrp.worksection', string='Work Segment')
    knr_code = fields.Char(string='KNR')
    vin_code = fields.Char(string='VIN')
    limit = fields.Integer('Query Limit', default=5)

    result_line_ids = fields.One2many('operation.result.line', 'wizard_id')

    wave = fields.Text(string='Waves', store=False, compute='_compute_wave')

    need_render = fields.Boolean(default=False)

    @api.depends('need_render')
    def _compute_wave(self):
        self.ensure_one()
        if not self.need_render:
            return
        records = self.result_line_ids.filtered(lambda r: r.selected)
        if not records:
            self.env.user.notify_warning(u'查询获取结果:0,请重新定义查询参数或等待新结果数据')
            return
        datas, ret = self._get_data(records)
        if not len(datas):
            self.env.user.notify_warning(u'查询获取结果:0,请重新定义查询参数或等待新结果数据')
            return
        # self.wave = self._get_echart_data(datas, ret)
        self.wave = datas

    def _recreate_minio_client(self):
        global minioClient
        try:
            minio_url = self.env['ir.config_parameter'].get_param('minio.url')
            minio_bucket = self.env["ir.config_parameter"].get_param("minio.bucket")
            minio_access_key = self.env["ir.config_parameter"].get_param("minio.access_key")
            minio_secret_key = self.env["ir.config_parameter"].get_param("minio.secret_key")
            if not minio_url:
                return None, None
            secruity = False if urlsplit(minio_url).scheme == 'http' else True
            if not minioClient:
                minioClient = Minio(minio_url.split('://')[-1], access_key=minio_access_key,
                                    secret_key=minio_secret_key, secure=secruity)
            elif minioClient._endpoint_url != minio_url or minioClient._access_key != minio_access_key or minioClient._secret_key != minio_secret_key:
                minioClient = Minio(minio_url.split('://')[-1], access_key=minio_access_key,
                                    secret_key=minio_secret_key, secure=secruity)
            if not minioClient.bucket_exists(minio_bucket):
                minioClient.make_bucket(minio_bucket)
            return minioClient, minio_bucket
        except Exception as e:
            return None, None

    def _get_echart_data(self, datas, ret, mark_line_coords):
        line = Line(u"{0}".format(u'Curve'), u"{0}-{1}".format(self.query_date_from, self.query_date_to), width=1920,
                    height=1080)
        for index, data in enumerate(datas):
            line.add(data['name'].split('.')[0], ret['cur_w'].values, ret[u'{0}'.format(data['name'])].values,
                     is_smooth=True, line_width=2, is_datazoom_show=True, is_stack=True,
                     mark_line_coords=mark_line_coords,
                     datazoom_type='both', tooltip_tragger='axis', mark_line=["min", "max"])
            line.options.get('series')[index].update({'connectNulls': True})
        # line.print_echarts_options()
        pyecharts.configure(force_js_embed=True)
        ret = line.render_embed()
        return ret

    @api.multi
    def read(self, fields=None, load='_classic_`'):
        return super(Wave, self).read(fields, load=load)

    def _get_data(self, data):
        client, bucket = self._recreate_minio_client()
        if not client or not bucket:
            return [], None, []  ### 返回无结果数值
        cur_objects = data.mapped('cur_objects')
        _objects = [x for x in cur_objects if x]
        objects = []
        cur_objects = map(json.loads, _objects)
        objs = list(itertools.chain.from_iterable(cur_objects))
        for cur in objs:
            objects.append(cur['file'])

        ret = None
        need_fetch_objects = []
        _datas = []
        for _t in objects:
            try:
                # try to get the cache
                _datas.append(_wave_cache[_t])
            except KeyError as e:
                need_fetch_objects.append(_t)
        try:
            _datas.extend(map(lambda x: _create_wave_result_dict(x, client.get_object(bucket, x).data.decode('utf-8')),
                              need_fetch_objects))  # 合并结果
            print(_datas)
        except Exception as e:
            return [], None, []
        return _datas
        # if len(_datas) > 1:
        #     for i in range(len(_datas) - 1):
        #         ret = _datas[i]['wave'].merge(_datas[i + 1]['wave'], how='outer', on='cur_w') if i == 0 else ret.merge(
        #             _datas[i + 1]['wave'], how='outer', on='cur_w')
        # elif len(_datas) == 0:
        #     return [], None, []
        # else:
        #     ret = _datas[0]['wave']
        # # ret = ret.sort_values(by=['cur_w'])
        # # mark_line_coords =  [[100, 1], [400, 2]]
        # mark_line_coords = []
        #
        # return _datas, ret, mark_line_coords

    @api.multi
    def button_show(self):
        self.ensure_one()
        self.need_render = True

    def _get_result_data(self):
        domain = [('cur_objects', '!=', False)]
        if self.query_date_from:
            domain += [('control_date', '>=', self.query_date_from)]
        if self.query_date_to:
            domain += [('control_date', '<=', self.query_date_to)]
        if self.vehicle_id:
            domain += [('product_id', '=', self.vehicle_id.id)]
        if self.screw_id:
            domain += [('consu_product_id', '=', self.screw_id.id)]
        if self.assembly_line_id:
            domain += [('production_id.assembly_line_id', '=', self.assembly_line_id.id)]
        if self.segment_id:
            domain += [('workcenter_id.worksegment_id', '=', self.segment_id.id)]
        if self.knr_code:
            domain += [('production_id.knr', 'like', self.knr_code)]
        if self.vin_code:
            domain += [('production_id.vin', 'like', self.vin_code)]
        return self.env['operation.result'].sudo().search(domain, limit=self.limit)

    def _bulk_create_result_data(self, data):
        datas = []
        for result in data:
            vals = {
                'wizard_id': self.id,
                'workorder_id': result.workorder_id.id,
                'workcenter_id': result.workcenter_id.id,
                'product_id': result.product_id.id,
                'control_date': result.control_date,
                'consu_product_id': result.consu_product_id.id,
                'measure_result': result.measure_result,
                'measure_torque': result.measure_torque,
                'measure_degree': result.measure_degree,
                'measure_t_don': result.measure_t_don,
                'cur_objects': result.cur_objects
            }
            datas.append(vals)

        if len(datas) == 0:
            return

        ids = self.env['operation.result.line'].sudo().bulk_create(datas)
        target_ids = [x[0] for x in ids]

        self.sudo().write({'result_line_ids': [(6, 0, target_ids)]})

    @api.multi
    def button_query(self):
        self.ensure_one()
        self.need_render = False

        _data = self._get_result_data()
        if len(_data) == 0:
            self.env.user.notify_warning(u'查询获取结果:0,请重新定义查询参数或等待新结果数据')
            # return result
        self._bulk_create_result_data(_data)
