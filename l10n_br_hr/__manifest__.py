# -*- coding: utf-8 -*-
# (c) 2014 Kmee - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    'name': 'Brazilian Localization HR',
    'summary': 'Brazilian Localization HR',
    'category': 'Localization',
    'author': (
        'KMEE',
        'Odoo Community Association (OCA)'
    ),
    'website': 'http://www.kmee.com.br',
    'version': '12.0.0.0.0',
    'depends': ['hr', 'l10n_br_base'],
    'data': [
        'data/l10n_br_hr.cbo.csv',
        'data/dependent_type_data.xml',
        'data/hr_employee_data.xml',
        'data/hr_employee_nationality_code_data.xml',
        'security/ir.model.access.csv',
        'views/res_company_view.xml',
        'views/l10n_br_hr_cbo_view.xml',
        'views/hr_employee_dependent_view.xml',
        'views/hr_employee_view.xml',
        'views/hr_job_view.xml',
    ],
    'test': [
        'test/l10n_br_hr_demo.yml'
    ],
    'installable': True,
    'auto_install': False,
    'license': 'AGPL-3',
}
