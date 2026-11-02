{
    'name': 'saas-service',
    'version': '19.0.1.5.0',
    'author': 'RavitaTech',
    'category': 'Services',
    'summary': 'ساخت سرویس اودوو مشتری بعد از قطعی شدن پرداخت',
    'description': """
بعد از تکمیل و قطعی شدن پرداخت، برای سفارش سرویس SaaS یک مجموعه از
پادهای odoo و postgres و storage در namespace مربوط می‌سازد، آن‌ها را
به هم وصل می‌کند، دامنه و NodePort می‌سازد، از ایمیج اختصاصی استفاده
می‌کند و نصب/مدیریت ماژول‌های انتخابی را فراهم می‌کند.
    """,
    'license': 'LGPL-3',
    'depends': ['sale', 'portal', 'payment', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'security/saas_security.xml',
        'security/saas_service_module_rules.xml',
        'data/ir_config_parameter_data.xml',
        'data/saas_odoo_module_data.xml',
        'data/ir_cron.xml',
        'views/saas_service_views.xml',
        'views/saas_odoo_module_views.xml',
        'views/sale_order_views.xml',
        'views/product_views.xml',
        'views/portal_templates.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'saas_service/static/src/components/saas_password_field/saas_password_field.js',
            'saas_service/static/src/components/saas_password_field/saas_password_field.xml',
            'saas_service/static/src/components/saas_status_dot/saas_status_dot.js',
            'saas_service/static/src/components/saas_status_dot/saas_status_dot.xml',
        ],
        'web.assets_frontend': [
            'saas_service/static/src/js/portal_password_toggle.js',
        ],
    },
    'installable': True,
    'application': True,
}
