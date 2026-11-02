import re

from odoo import api, fields, models
from odoo.tools import float_compare

_HOSTNAME = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    saas_hostname = fields.Char(
        string='نام سرویس',
        copy=False,
        help='نام انگلیسی ساب‌دامین که مشتری انتخاب کرده است. مثلا acme برای acme.ravitatech.com. فرآیند سبد و پرداخت این مقدار را پر می‌کند.',
    )
    saas_service_id = fields.Many2one(
        'saas.service',
        string='سرویس',
        copy=False,
        readonly=True,
    )

    @api.onchange('saas_hostname')
    def _onchange_saas_hostname(self):
        if self.saas_hostname:
            self.saas_hostname = self.saas_hostname.strip().lower()

    def _saas_is_service_order(self):
        self.ensure_one()
        if self.saas_hostname:
            return True
        return any(self.order_line.product_id.mapped('is_saas_service'))

    def _saas_payment_is_final(self):
        self.ensure_one()
        transactions = self.transaction_ids.filtered(
            lambda transaction: transaction.state == 'done' and transaction.currency_id == self.currency_id
        )
        if not transactions:
            return False
        paid = sum(transactions.mapped('amount'))
        return float_compare(paid, self.amount_total, precision_rounding=self.currency_id.rounding) >= 0

    def _saas_provision_if_paid(self):
        for order in self:
            if order.saas_service_id or not order._saas_is_service_order():
                continue
            if not order._saas_payment_is_final():
                continue
            hostname = (order.saas_hostname or '').strip().lower()
            self.env['saas.service'].sudo().create_from_order(order, hostname)

    @api.model
    def _saas_hostname_error(self, hostname):
        if not hostname:
            return 'نام سرویس روی سفارش ثبت نشده است.'
        if not _HOSTNAME.fullmatch(hostname):
            return 'نام سرویس باید فقط با حروف کوچک انگلیسی، عدد و خط تیره باشد.'
        if hostname in {'odoo', 'postgres', 'storage', 'www', 'mail', 'admin', 'saas-dev'}:
            return 'این نام سرویس قابل استفاده نیست.'
        return False
