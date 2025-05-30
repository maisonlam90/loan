# -*- coding: utf-8 -*-

{
    'name': "Loan",
    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "Loan",
    'website': "https://www.mailan.net",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        'security/loan_security.xml',
        'security/ir.model.access.csv',

        'views/views.xml',
        'views/templates.xml',
        'views/loan_customer_views.xml',
        'views/loan_contract_views.xml',
        'views/loan_asset_views.xml',
        'views/menu.xml',
        'data/loan_cron.xml',
        
  
    ],

    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],



}
