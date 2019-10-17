# -*- coding: utf-8 -*-
{
    'name': "sa_base",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Frank Gu",
    'website': "http://www.centronsys.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Manufacturing',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['mrp_maintenance', 'maintenance', 'mrp', 'web_domain_field', 'quality_mrp', 'web_image_editor',
                'web_widget_many2many_tags_multi_selection'],

    "external_dependencies": {
        "python": ['validators'],
    },

    # always loaded
    'data': [
        # 'security/quality.xml',  # 权限
        'security/ir.model.access.csv',
        'data/maintenance_data.xml',
        'data/point_data.xml',
        'data/product_data.xml',
        'data/mail_template.xml',
        'data/step_data.xml',
        # 'wizards/mrp_bom_wizard_views.xml',
        'views/res_user_views.xml',
        'views/menu_hide_views.xml',
        'views/sa_views_menus.xml',
        'views/equipment_connection_views.xml',
        'views/mrp_worksegment_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/mrp_routing_view.xml',
        'views/mrp_step_view.xml',
        'views/mrp_routing_group_views.xml',
        'views/controller_job_views.xml',
        'views/controller_program_views.xml',
        'views/mrp_bom_views.xml',
        'views/product_views.xml',
        'views/maintenance_views.xml',
        'views/quality_views.xml',
        'report/sa_mrp_report_main.xml',
        'report/workcenter_report_template.xml',
        'report/equipment_report_template.xml',
        'report/product_product_tempaltes.xml',
        'views/sa_config_setting.xml'
    ],
    'demo': [
        # 'demo/test_demo.xml',   # 测试数据
    ],
}
