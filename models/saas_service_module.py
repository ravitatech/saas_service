from odoo import fields, models


class SaasServiceModule(models.Model):
    _name = 'saas.service.module'
    _description = 'ماژول سرویس SaaS'
    _order = 'state, technical_name'

    service_id = fields.Many2one('saas.service', required=True, ondelete='cascade', index=True)
    module_id = fields.Many2one('saas.odoo.module', string='ماژول کاتالوگ', ondelete='set null')
    name = fields.Char(string='عنوان')
    technical_name = fields.Char(string='نام فنی', required=True, index=True)
    state = fields.Selection(
        [
            ('pending', 'در صف نصب'),
            ('installed', 'نصب‌شده'),
            ('uninstalled', 'نصب‌نشده'),
            ('failed', 'خطا'),
        ],
        string='وضعیت',
        default='pending',
        required=True,
    )
    last_error = fields.Text(string='آخرین خطا')
