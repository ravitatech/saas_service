from odoo import fields, models


class SaasOdooModule(models.Model):
    _name = 'saas.odoo.module'
    _description = 'ماژول قابل نصب روی سرویس‌ها'
    _order = 'category, name'

    name = fields.Char(string='عنوان', required=True)
    technical_name = fields.Char(string='نام فنی', required=True, index=True)
    category = fields.Char(string='دسته')
    description = fields.Text(string='توضیح')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _technical_name_unique = models.Constraint(
        'UNIQUE(technical_name)',
        'این نام فنی قبلاً ثبت شده است.',
    )
