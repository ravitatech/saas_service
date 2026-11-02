from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class SaasCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'service_count' in counters:
            values['service_count'] = request.env['saas.service'].search_count([])
        return values

    @http.route(['/my/services', '/my/services/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_services(self, page=1, **kwargs):
        service_model = request.env['saas.service']
        total = service_model.search_count([])
        pager = portal_pager(url='/my/services', total=total, page=page, step=20)
        services = service_model.search([], limit=20, offset=pager['offset'], order='id desc')
        values = self._prepare_portal_layout_values()
        values.update({
            'services': services,
            'pager': pager,
            'page_name': 'saas_service',
        })
        return request.render('saas_service.portal_my_services', values)

    @http.route('/my/services/<int:service_id>', type='http', auth='user', website=True)
    def portal_my_service(self, service_id, **kwargs):
        service = request.env['saas.service'].search([('id', '=', service_id)], limit=1)
        if not service:
            return request.not_found()
        values = self._prepare_portal_layout_values()
        values.update({
            'service': service,
            'page_name': 'saas_service_detail',
        })
        return request.render('saas_service.portal_my_service', values)
