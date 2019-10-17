# -*- coding: utf-8 -*-
# from __future__ import unicode_literals
import numpy as np

SPC_ELEMENTS_IN_GROUP = 5
SPC_GROUP_CC = 2.33


def get_cpk_cmk(data, usl=None, lsl=None):
    """

    :param data: 原始数据
    :param usl: 规格上限
    :param lsl: 规格下限
    :return:
    """
    if not usl:
        usl = max(data)
    if not lsl:
        lsl = min(data)

    target_group = int(len(data) / SPC_ELEMENTS_IN_GROUP)
    target_data = data[:target_group * SPC_ELEMENTS_IN_GROUP]

    group_data = np.reshape(target_data, (target_group, SPC_ELEMENTS_IN_GROUP))

    cls = [np.average(data) for data in group_data]
    rs = [np.max(gd) - np.min(gd) for gd in group_data]

    # 中心限X
    CL_X = np.average(cls)

    # 中心限R
    CL_R = np.average(rs)

    # 估计标准差
    E_STD = CL_R / SPC_GROUP_CC

    cpk = np.min([np.abs((CL_X - lsl) / (3 * E_STD)), np.abs((usl - CL_X) / (3 * E_STD))])

    # 全局平均值
    AVG = np.average(target_data)

    # 统计标准差
    STD = np.std(target_data)

    cmk = np.min([np.abs(usl - AVG) / (3 * STD), (np.abs(AVG - lsl) / (3 * STD))])

    return cpk, cmk
