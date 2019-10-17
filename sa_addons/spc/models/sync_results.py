# -*- coding: utf-8 -*-

import datetime
import logging
import werkzeug.urls
import requests
from dateutil import parser

from odoo import api, release, SUPERUSER_ID, fields
from odoo.exceptions import UserError
from odoo.models import AbstractModel
from odoo.tools.translate import _
from odoo.tools import config
from odoo.tools import misc
from requests import ConnectionError

import json
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

MASTER_RESULT_API = '/rush/v1/results'


class ResultSync(AbstractModel):
    _name = "result.sync"

    def _get_masterpc_results(self, url):
        headers = {'Content-Type': 'application/json'}
        payloads = {'has_upload': False, 'result': ['ok', 'nok']}
        try:
            ret = requests.get(url=url, params=payloads, headers=headers)
        except ConnectionError:
            return False
        if ret.status_code != 200:
            _logger.debug('Sync Result fail')
            return
        ret = ret.json()
        for result in ret:
            op_result = self.env['operation.result'].sudo().browse(result['id'])
            lid = result.pop('local_id') if 'local_id' in result else None
            if not op_result:
                # 新增结果
                if 'control_date' in result:
                    _t = parser.parse(result['control_date']) if result['control_date'] else None
                    if _t:
                        result.update({
                            'control_date': fields.Datetime.to_string((_t - _t.utcoffset())),
                            'time': fields.Datetime.to_string((_t - _t.utcoffset()))
                        })

                self.env['operation.result'].create(result)

                _logger.debug('Sync Result can not found result id: %d' % result['id'])

            else:
                rid = result.pop('id') if 'id' in result else None

                if not rid:
                    continue
                if 'cur_objects' in result:
                    result.update({
                        'cur_objects': json.dumps(result['cur_objects'])
                    })

                if 'control_date' in result:
                    _t = parser.parse(result['control_date']) if result['control_date'] else None
                    if _t:
                        result.update({
                            'control_date': fields.Datetime.to_string((_t - _t.utcoffset()))
                        })
                ret = op_result.sudo().write(result)
                if not ret:
                    _logger.debug(u'更新结果 写入结果失败 result id: %d' % result['id'])
                    continue

            data = {'has_upload': True}
            try:
                ret = requests.patch(url=url + '/{0}'.format(lid), data=json.dumps(data), headers=headers)
            except ConnectionError:
                continue
            if ret.status_code != 200:
                _logger.debug(u'更新MasterPC hasupload标志位失败')

    @api.multi
    def result_sync(self):
        domain = [('protocol', '=', 'http'), ('equipment_id.category_name', '=', 'MasterPC')]
        connections = self.env['maintenance.equipment.connection'].sudo().search(domain)
        urls = ['http://{0}:{1}{2}'.format(connect.ip, connect.port, MASTER_RESULT_API) for connect in connections]
        ret = map(lambda url: self._get_masterpc_results(url), urls)
        return True
