from odoo import fields, models

from .saas_service import ODOO_IMAGE, POSTGRES_IMAGE, STORAGE_IMAGE, NODE_HOST, DOMAIN_SUFFIX


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    saas_odoo_image = fields.Char(
        string='ایمیج اودوو مشتری',
        config_parameter='saas_service.odoo_image',
        default=ODOO_IMAGE,
    )
    saas_postgres_image = fields.Char(
        string='ایمیج پستگرس',
        config_parameter='saas_service.postgres_image',
        default=POSTGRES_IMAGE,
    )
    saas_storage_image = fields.Char(
        string='ایمیج storage',
        config_parameter='saas_service.storage_image',
        default=STORAGE_IMAGE,
    )
    saas_node_host = fields.Char(
        string='آدرس نود / NodePort',
        config_parameter='saas_service.node_host',
        default=NODE_HOST,
    )
    saas_domain_suffix = fields.Char(
        string='پسوند دامنه',
        config_parameter='saas_service.domain_suffix',
        default=DOMAIN_SUFFIX,
    )
