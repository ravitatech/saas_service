from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _set_done(self, *, state_message=None, extra_allowed_states=()):
        transactions = super()._set_done(
            state_message=state_message,
            extra_allowed_states=extra_allowed_states,
        )
        done = self.filtered(lambda transaction: transaction.state == 'done')
        done.sale_order_ids._saas_provision_if_paid()
        return transactions

    def _post_process(self):
        result = super()._post_process()
        done = self.filtered(lambda transaction: transaction.state == 'done')
        done.sale_order_ids._saas_provision_if_paid()
        return result
