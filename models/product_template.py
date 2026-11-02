from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_saas_service = fields.Boolean(
        string='سرویس SaaS',
        help='اگر فعال باشد، بعد از قطعی شدن پرداخت سفارش این محصول یک سرویس اودوو ساخته می‌شود.',
    )
