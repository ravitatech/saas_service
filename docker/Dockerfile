FROM odoo:19.0

USER root
COPY saas_no_apps /mnt/saas-addons/saas_no_apps
RUN chown -R odoo:odoo /mnt/saas-addons

USER odoo
ENV ODOO_RC=/etc/odoo/odoo.conf
