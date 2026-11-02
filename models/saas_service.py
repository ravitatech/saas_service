import secrets
import xmlrpc.client

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .k8s_client import K8sClient

NAMESPACE = 'saas-dev'
DOMAIN_SUFFIX = 'ravitatech.com'
NODE_HOST = '172.20.21.22'
ODOO_IMAGE = 'ravitatech/odoo:19-saas'
POSTGRES_IMAGE = 'postgres:18'
STORAGE_IMAGE = 'busybox:1.37'


class SaasService(models.Model):
    _name = 'saas.service'
    _description = 'سرویس SaaS'
    _order = 'id desc'
    _rec_name = 'hostname'

    hostname = fields.Char(string='نام سرویس', index=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='مشتری', required=True, index=True)
    sale_order_id = fields.Many2one('sale.order', string='سفارش', copy=False, readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    namespace = fields.Char(default=NAMESPACE, readonly=True)
    random_number = fields.Char(string='شماره تصادفی', readonly=True, copy=False)
    state = fields.Selection(
        [
            ('draft', 'پیش‌نویس'),
            ('provisioning', 'در حال ساخت'),
            ('running', 'فعال'),
            ('inactive', 'غیرفعال'),
            ('error', 'خطا'),
        ],
        string='وضعیت',
        default='draft',
        required=True,
        index=True,
    )
    domain = fields.Char(string='دامنه', compute='_compute_domain', store=True)
    url = fields.Char(string='آدرس دامنه', compute='_compute_domain', store=True)
    node_host = fields.Char(string='آدرس نود', default=NODE_HOST, readonly=True)
    node_port = fields.Integer(string='پورت NodePort', readonly=True, copy=False)
    node_url = fields.Char(string='آدرس NodePort', compute='_compute_node_url', store=True)
    database_name = fields.Char(string='نام دیتابیس', readonly=True, copy=False)
    database_user = fields.Char(string='کاربر دیتابیس', default='odoo', readonly=True)
    database_password = fields.Char(string='رمز دیتابیس', readonly=True, copy=False)
    odoo_admin_login = fields.Char(string='کاربر اودوو', default='admin', readonly=True)
    odoo_admin_password = fields.Char(string='رمز اودوو', readonly=True, copy=False)
    odoo_master_password = fields.Char(string='رمز مستر', readonly=True, copy=False)
    odoo_pod = fields.Char(string='پاد اودوو', readonly=True)
    postgres_pod = fields.Char(string='پاد پستگرس', readonly=True)
    storage_pod = fields.Char(string='پاد ذخیره‌سازی', readonly=True)
    odoo_service = fields.Char(string='سرویس اودوو', readonly=True)
    postgres_service = fields.Char(string='سرویس پستگرس', readonly=True)
    odoo_pod_phase = fields.Char(string='وضعیت پاد اودوو', readonly=True)
    postgres_pod_phase = fields.Char(string='وضعیت پاد پستگرس', readonly=True)
    storage_pod_phase = fields.Char(string='وضعیت پاد ذخیره‌سازی', readonly=True)
    health_state = fields.Selection(
        [
            ('healthy', 'سالم'),
            ('warning', 'در حال آماده‌سازی'),
            ('danger', 'مشکل'),
            ('inactive', 'غیرفعال'),
            ('unknown', 'نامشخص'),
        ],
        string='وضعیت کلی',
        compute='_compute_health_state',
        store=True,
    )
    error_message = fields.Text(string='شرح خطا', readonly=True)
    provisioned_at = fields.Datetime(string='زمان ساخت', readonly=True)
    odoo_image = fields.Char(
        string='ایمیج اودوو',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param(
            'saas_service.odoo_image', ODOO_IMAGE
        ),
    )
    requested_module_ids = fields.Many2many(
        'saas.odoo.module',
        'saas_service_requested_module_rel',
        'service_id',
        'module_id',
        string='ماژول‌های اولیه',
        help='این ماژول‌ها هنگام ساخت سرویس روی اودووی مشتری نصب می‌شوند.',
    )
    service_module_ids = fields.One2many(
        'saas.service.module',
        'service_id',
        string='ماژول‌های سرویس',
    )
    install_module_names = fields.Char(
        string='نصب سریع ماژول',
        help='نام فنی ماژول‌ها را با ویرگول وارد کنید؛ مثلا sale,crm,stock',
    )
    installed_module_count = fields.Integer(
        string='تعداد ماژول نصب‌شده',
        compute='_compute_installed_module_count',
    )

    _hostname_unique = models.Constraint(
        'UNIQUE(hostname)',
        'این نام سرویس قبلاً استفاده شده است.',
    )

    @api.depends('service_module_ids.state')
    def _compute_installed_module_count(self):
        for service in self:
            service.installed_module_count = len(
                service.service_module_ids.filtered(lambda line: line.state == 'installed')
            )

    @api.depends('hostname')
    def _compute_domain(self):
        for service in self:
            if service.hostname:
                service.domain = '%s.%s' % (service.hostname, DOMAIN_SUFFIX)
                service.url = 'http://%s' % service.domain
            else:
                service.domain = False
                service.url = False

    @api.depends('node_host', 'node_port')
    def _compute_node_url(self):
        for service in self:
            if service.node_host and service.node_port:
                service.node_url = 'http://%s:%s' % (service.node_host, service.node_port)
            else:
                service.node_url = False

    @api.depends('state', 'odoo_pod_phase', 'postgres_pod_phase', 'storage_pod_phase')
    def _compute_health_state(self):
        bad_phases = {
            'Failed', 'Missing', 'Error', 'CrashLoopBackOff',
            'ImagePullBackOff', 'ErrImagePull', 'CreateContainerConfigError',
        }
        for service in self:
            phases = [
                service.odoo_pod_phase,
                service.postgres_pod_phase,
                service.storage_pod_phase,
            ]
            if service.state == 'inactive':
                service.health_state = 'inactive'
            elif service.state == 'error' or any((phase or '') in bad_phases for phase in phases):
                service.health_state = 'danger'
            elif all(phase == 'Running' for phase in phases):
                service.health_state = 'healthy'
            elif service.state in ('provisioning', 'draft') or any(phases):
                service.health_state = 'warning'
            else:
                service.health_state = 'unknown'

    def get_health_color(self):
        self.ensure_one()
        return {
            'healthy': 'success',
            'warning': 'warning',
            'danger': 'danger',
            'inactive': 'secondary',
            'unknown': 'secondary',
        }.get(self.health_state or 'unknown', 'secondary')

    def get_phase_color(self, phase):
        if phase == 'Running':
            return 'success'
        if phase in {
            'Failed', 'Missing', 'Error', 'CrashLoopBackOff',
            'ImagePullBackOff', 'ErrImagePull', 'CreateContainerConfigError',
        }:
            return 'danger'
        if phase in {'Pending', 'ContainerCreating', 'PodInitializing', 'Init:0/1'} or (
            phase and str(phase).startswith('Init:')
        ):
            return 'warning'
        if not phase:
            return 'secondary'
        return 'warning'

    @api.model
    def create_from_order(self, order, hostname):
        order.ensure_one()
        if order.saas_service_id:
            return order.saas_service_id
        error = order._saas_hostname_error(hostname)
        service = self.create({
            'hostname': hostname or False,
            'partner_id': order.partner_id.id,
            'sale_order_id': order.id,
            'company_id': order.company_id.id,
            'state': 'draft',
        })
        order.sudo().write({'saas_service_id': service.id})
        if error:
            service.write({'state': 'error', 'error_message': error})
            return service
        service.action_provision()
        return service

    def action_provision(self):
        for service in self:
            service._provision_k8s()
        return True

    def action_sync_status(self):
        for service in self:
            service._sync_status()
        return True

    def action_open_url(self):
        self.ensure_one()
        target = self.node_url or self.url
        if not target:
            raise UserError(_('آدرس سرویس هنوز مشخص نیست.'))
        return {
            'type': 'ir.actions.act_url',
            'url': target,
            'target': 'new',
        }

    def action_open_node_url(self):
        self.ensure_one()
        if not self.node_url:
            raise UserError(_('پورت NodePort هنوز مشخص نیست.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.node_url,
            'target': 'new',
        }

    def action_open_domain_url(self):
        self.ensure_one()
        if not self.url:
            raise UserError(_('دامنه سرویس هنوز مشخص نیست.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.url,
            'target': 'new',
        }

    def action_sync_modules(self):
        for service in self:
            service._sync_installed_modules()
        return True

    def action_install_modules(self):
        for service in self:
            service._install_requested_modules()
        return True

    def action_deactivate(self):
        for service in self:
            service._scale_down_pods()
        return True

    def action_activate(self):
        for service in self:
            service._scale_up_pods()
        return True

    def unlink(self):
        for service in self:
            try:
                service._delete_all_k8s_resources()
            except Exception as error:
                raise UserError(
                    _('حذف منابع Kubernetes برای سرویس %s ناموفق بود: %s')
                    % (service.hostname or service.id, service._safe_error(error))
                ) from error
        return super().unlink()

    def _resource_base(self):
        self.ensure_one()
        if not (self.hostname and self.random_number):
            return False
        return '%s-%s' % (self.hostname, self.random_number)

    def _scale_down_pods(self):
        """غیرفعال: پادها حذف می‌شوند (Scale Down) ولی PVC و سرویس و Ingress می‌مانند."""
        self.ensure_one()
        if self.state == 'inactive':
            return
        if not self._resource_base():
            raise UserError(_('این سرویس هنوز در Kubernetes ساخته نشده است.'))
        try:
            client = self._k8s()
            for name in (self.odoo_pod, self.postgres_pod, self.storage_pod):
                if name:
                    client.delete_pod(name)
        except Exception as error:
            raise UserError(_('غیرفعال‌سازی ناموفق بود: %s') % self._safe_error(error)) from error
        self.write({
            'state': 'inactive',
            'odoo_pod_phase': 'ScaledDown',
            'postgres_pod_phase': 'ScaledDown',
            'storage_pod_phase': 'ScaledDown',
            'error_message': False,
        })

    def _scale_up_pods(self):
        """فعال: پادها دوباره ساخته می‌شوند (Scale Up) روی همان PVCها."""
        self.ensure_one()
        if self.state != 'inactive':
            raise UserError(_('فقط سرویس غیرفعال را می‌توان فعال کرد.'))
        if not self._resource_base():
            raise UserError(_('اطلاعات ساخت سرویس ناقص است.'))
        try:
            client = self._k8s()
            labels = self._base_labels()
            # اگر پاد باقی مانده باشد اول پاک شود
            for name in (self.odoo_pod, self.postgres_pod, self.storage_pod):
                if name:
                    client.delete_pod(name)
            client.ensure_pod(self._postgres_pod_body(labels))
            client.ensure_pod(self._storage_pod_body(labels))
            client.ensure_pod(self._odoo_pod_body(labels))
        except Exception as error:
            self.write({'state': 'error', 'error_message': self._safe_error(error)})
            raise UserError(_('فعال‌سازی ناموفق بود: %s') % self._safe_error(error)) from error
        self.write({
            'state': 'provisioning',
            'error_message': False,
            'odoo_pod_phase': 'Pending',
            'postgres_pod_phase': 'Pending',
            'storage_pod_phase': 'Pending',
        })
        self._sync_status()

    def _delete_all_k8s_resources(self):
        """حذف کامل همه منابع سرویس از namespace saas-dev."""
        self.ensure_one()
        base = self._resource_base()
        if not base:
            return
        client = self._k8s()
        for name in (self.odoo_pod, self.postgres_pod, self.storage_pod):
            if name:
                client.delete_pod(name)
        for name in (self.odoo_service, self.postgres_service):
            if name:
                client.delete_service(name)
        client.delete_ingress('odoo-%s' % base)
        client.delete_pvc('odoo-data-%s' % base)
        client.delete_pvc('postgres-data-%s' % base)
        client.delete_pvc('storage-%s' % base)
        client.delete_secret('saas-%s' % base)

    def _get_param(self, key, default):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    def _image_odoo(self):
        self.ensure_one()
        return self.odoo_image or self._get_param('saas_service.odoo_image', ODOO_IMAGE)

    def _image_postgres(self):
        return self._get_param('saas_service.postgres_image', POSTGRES_IMAGE)

    def _image_storage(self):
        return self._get_param('saas_service.storage_image', STORAGE_IMAGE)

    def _initial_module_names(self):
        self.ensure_one()
        names = ['base']
        names.extend(self.requested_module_ids.mapped('technical_name'))
        if self.install_module_names:
            names.extend(
                part.strip()
                for part in self.install_module_names.split(',')
                if part.strip()
            )
        # unique preserve order
        seen = set()
        ordered = []
        for name in names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    def _ensure_module_lines(self, technical_names, state='pending'):
        self.ensure_one()
        Module = self.env['saas.odoo.module'].sudo()
        Line = self.env['saas.service.module'].sudo()
        for technical_name in technical_names:
            catalog = Module.search([('technical_name', '=', technical_name)], limit=1)
            line = self.service_module_ids.filtered(lambda item: item.technical_name == technical_name)[:1]
            values = {
                'name': catalog.name if catalog else technical_name,
                'module_id': catalog.id if catalog else False,
                'state': state,
            }
            if line:
                line.write(values)
            else:
                Line.create({
                    'service_id': self.id,
                    'technical_name': technical_name,
                    **values,
                })

    def _provision_k8s(self):
        self.ensure_one()
        error = self.env['sale.order']._saas_hostname_error(self.hostname or '')
        if error:
            self.write({'state': 'error', 'error_message': error})
            return
        if not self.random_number:
            self.random_number = str(secrets.randbelow(900000) + 100000)
            suffix = self.hostname.replace('-', '_')
            self.database_name = 'db_%s_%s' % (suffix, self.random_number)
            self.database_user = 'odoo'
            self.database_password = secrets.token_hex(16)
            self.odoo_admin_password = secrets.token_hex(12)
            self.odoo_master_password = secrets.token_hex(16)
        base = '%s-%s' % (self.hostname, self.random_number)
        names = {
            'odoo_pod': 'odoo-%s' % base,
            'postgres_pod': 'postgres-%s' % base,
            'storage_pod': 'storage-%s' % base,
            'odoo_service': 'odoo-%s' % base,
            'postgres_service': 'postgres-%s' % base,
        }
        initial_modules = self._initial_module_names()
        self._ensure_module_lines(initial_modules, state='pending')
        self.write({
            **names,
            'odoo_image': self._image_odoo(),
            'state': 'provisioning',
            'error_message': False,
            'provisioned_at': fields.Datetime.now(),
        })
        try:
            client = self._k8s()
            labels = self._base_labels()
            client.ensure_secret(self._secret_body(base, labels))
            client.ensure_pvc(self._pvc_body('postgres-data-%s' % base, '5Gi', labels, 'postgres'))
            client.ensure_pvc(self._pvc_body('odoo-data-%s' % base, '5Gi', labels, 'odoo'))
            client.ensure_pvc(self._pvc_body('storage-%s' % base, '1Gi', labels, 'storage'))
            client.ensure_pod(self._postgres_pod_body(labels))
            client.ensure_pod(self._storage_pod_body(labels))
            client.ensure_pod(self._odoo_pod_body(labels))
            client.ensure_service(self._service_body(self.postgres_service, self.postgres_pod, 5432, 'postgres'))
            odoo_svc = client.ensure_service(
                self._odoo_nodeport_service_body(self.odoo_service, self.odoo_pod)
            )
            self._store_node_port(odoo_svc)
            client.ensure_ingress(self._ingress_body(base))
        except Exception as error:
            self.write({'state': 'error', 'error_message': self._safe_error(error)})
            return
        self._sync_status()

    def _cron_sync_status(self):
        services = self.search([('state', 'in', ('provisioning', 'running'))])
        for service in services:
            try:
                service._sync_status()
            except Exception as error:
                service.write({'error_message': service._safe_error(error)})

    def _sync_status(self):
        self.ensure_one()
        if not (self.odoo_pod and self.postgres_pod and self.storage_pod):
            return
        client = self._k8s()
        phases = {}
        ready = {}
        problems = []
        for key, name in (
            ('odoo', self.odoo_pod),
            ('postgres', self.postgres_pod),
            ('storage', self.storage_pod),
        ):
            pod = client.get_pod(name)
            if not pod:
                phases[key] = 'Missing'
                ready[key] = False
                continue
            status = pod.get('status') or {}
            phases[key] = status.get('phase') or 'Unknown'
            containers = status.get('containerStatuses') or []
            ready[key] = bool(containers) and all(item.get('ready') for item in containers)
            for container in containers:
                waiting = (container.get('state') or {}).get('waiting') or {}
                reason = waiting.get('reason')
                if reason in {'CrashLoopBackOff', 'ImagePullBackOff', 'ErrImagePull', 'CreateContainerConfigError'}:
                    problems.append('%s: %s' % (name, waiting.get('message') or reason))
            if phases[key] == 'Failed':
                problems.append('%s: Failed' % name)
        values = {
            'odoo_pod_phase': phases.get('odoo'),
            'postgres_pod_phase': phases.get('postgres'),
            'storage_pod_phase': phases.get('storage'),
        }
        if self.odoo_service:
            svc = client.get_service(self.odoo_service)
            node_port = self._extract_node_port(svc)
            if node_port:
                values['node_port'] = node_port
                values['node_host'] = self.node_host or NODE_HOST
        odoo_up = phases.get('odoo') == 'Running' and ready.get('odoo')
        postgres_up = phases.get('postgres') == 'Running'
        storage_up = phases.get('storage') == 'Running'
        if self.state == 'inactive':
            values.update({
                'state': 'inactive',
                'odoo_pod_phase': 'ScaledDown' if phases.get('odoo') == 'Missing' else phases.get('odoo'),
                'postgres_pod_phase': 'ScaledDown' if phases.get('postgres') == 'Missing' else phases.get('postgres'),
                'storage_pod_phase': 'ScaledDown' if phases.get('storage') == 'Missing' else phases.get('storage'),
                'error_message': False,
            })
            self.write(values)
            return
        if problems:
            values.update({'state': 'error', 'error_message': '\n'.join(problems)[:2000]})
        elif odoo_up and postgres_up and storage_up:
            values.update({'state': 'running', 'error_message': False})
        self.write(values)
        if odoo_up and postgres_up and storage_up:
            try:
                self._sync_installed_modules()
            except Exception:
                # همگام‌سازی ماژول نباید وضعیت پاد را خراب کند
                pass

    def _store_node_port(self, service_payload):
        self.ensure_one()
        node_port = self._extract_node_port(service_payload)
        if not node_port and self.odoo_service:
            service_payload = self._k8s().get_service(self.odoo_service)
            node_port = self._extract_node_port(service_payload)
        if node_port:
            self.write({
                'node_port': node_port,
                'node_host': self.node_host or NODE_HOST,
            })

    @api.model
    def _extract_node_port(self, service_payload):
        if not service_payload:
            return False
        for port in (service_payload.get('spec') or {}).get('ports') or []:
            if port.get('name') in (None, 'http') or port.get('port') == 8069:
                if port.get('nodePort'):
                    return int(port['nodePort'])
        return False

    def _k8s(self):
        self.ensure_one()
        return K8sClient(self.namespace or NAMESPACE)

    def _base_labels(self):
        self.ensure_one()
        return {
            'saas.ravitatech/id': str(self.id),
            'app.kubernetes.io/managed-by': 'saas-service',
            'saas.ravitatech/hostname': self.hostname,
        }

    def _component_labels(self, component, app_name):
        labels = self._base_labels()
        labels.update({
            'app': app_name,
            'app.kubernetes.io/component': component,
        })
        return labels

    def _secret_name(self):
        self.ensure_one()
        return 'saas-%s-%s' % (self.hostname, self.random_number)

    def _secret_body(self, base, labels):
        self.ensure_one()
        conf = self._odoo_conf()
        script = self._entrypoint_script()
        return {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {'name': 'saas-%s' % base, 'labels': labels},
            'type': 'Opaque',
            'stringData': {
                'postgres-password': self.database_password,
                'admin-password': self.odoo_admin_password,
                'master-password': self.odoo_master_password,
                'odoo.conf': conf,
                'entrypoint.sh': script,
            },
        }

    def _odoo_conf(self):
        self.ensure_one()
        return '\n'.join([
            '[options]',
            'admin_passwd = %s' % self.odoo_master_password,
            'db_host = %s' % self.postgres_service,
            'db_port = 5432',
            'db_user = %s' % self.database_user,
            'db_password = %s' % self.database_password,
            'db_name = %s' % self.database_name,
            'dbfilter = ^%s$' % self.database_name,
            'list_db = False',
            'proxy_mode = True',
            'without_demo = all',
            'workers = 0',
            'max_cron_threads = 1',
            'data_dir = /var/lib/odoo',
            'http_port = 8069',
            'addons_path = /mnt/saas-addons,/usr/lib/python3/dist-packages/odoo/addons',
            '',
        ])

    def _entrypoint_script(self):
        return """#!/bin/bash
set -e
python3 - <<'PY'
import os, socket, sys, time
host = os.environ.get("HOST", "localhost")
for _ in range(60):
    try:
        with socket.create_connection((host, 5432), 2):
            sys.exit(0)
    except OSError:
        time.sleep(2)
sys.exit(1)
PY
MODULES="${INSTALL_MODULES:-base}"
if [ ! -f /var/lib/odoo/.saas-initialized ]; then
  odoo --config=/etc/odoo/odoo.conf -d "$DB_NAME" -i "$MODULES" --without-demo=all --stop-after-init
  odoo shell --config=/etc/odoo/odoo.conf -d "$DB_NAME" --no-http <<'PY'
import os
user = env["res.users"].search([("login", "=", "admin")], limit=1)
if user:
    user.password = os.environ["ADMIN_PASSWORD"]
env.cr.commit()
PY
  touch /var/lib/odoo/.saas-initialized
fi
exec odoo --config=/etc/odoo/odoo.conf
"""

    def _pvc_body(self, name, size, labels, component):
        body_labels = dict(labels)
        body_labels['app.kubernetes.io/component'] = component
        return {
            'apiVersion': 'v1',
            'kind': 'PersistentVolumeClaim',
            'metadata': {'name': name, 'labels': body_labels},
            'spec': {
                'accessModes': ['ReadWriteOnce'],
                'storageClassName': 'local-path',
                'resources': {'requests': {'storage': size}},
            },
        }

    def _pod_meta(self, name, component):
        return {
            'name': name,
            'labels': self._component_labels(component, name),
        }

    def _postgres_pod_body(self, labels):
        self.ensure_one()
        base = '%s-%s' % (self.hostname, self.random_number)
        return {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': self._pod_meta(self.postgres_pod, 'postgres'),
            'spec': {
                'restartPolicy': 'Always',
                'containers': [{
                    'name': 'postgres',
                    'image': self._image_postgres(),
                    'imagePullPolicy': 'IfNotPresent',
                    'ports': [{'containerPort': 5432}],
                    'env': [
                        {'name': 'POSTGRES_USER', 'value': self.database_user},
                        {'name': 'POSTGRES_DB', 'value': self.database_name},
                        {'name': 'POSTGRES_PASSWORD', 'valueFrom': {'secretKeyRef': {
                            'name': 'saas-%s' % base, 'key': 'postgres-password',
                        }}},
                    ],
                    'readinessProbe': {
                        'exec': {'command': ['pg_isready', '-U', self.database_user, '-d', self.database_name]},
                        'initialDelaySeconds': 10,
                        'periodSeconds': 5,
                    },
                    'resources': {
                        'requests': {'cpu': '100m', 'memory': '256Mi'},
                        'limits': {'cpu': '1', 'memory': '1Gi'},
                    },
                    'volumeMounts': [{'name': 'data', 'mountPath': '/var/lib/postgresql'}],
                }],
                'volumes': [{'name': 'data', 'persistentVolumeClaim': {'claimName': 'postgres-data-%s' % base}}],
            },
        }

    def _storage_pod_body(self, labels):
        self.ensure_one()
        base = '%s-%s' % (self.hostname, self.random_number)
        return {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': self._pod_meta(self.storage_pod, 'storage'),
            'spec': {
                'restartPolicy': 'Always',
                'containers': [{
                    'name': 'storage',
                    'image': self._image_storage(),
                    'imagePullPolicy': 'IfNotPresent',
                    'command': ['sh', '-c', 'sleep infinity'],
                    'resources': {
                        'requests': {'cpu': '10m', 'memory': '16Mi'},
                        'limits': {'cpu': '100m', 'memory': '64Mi'},
                    },
                    'volumeMounts': [{'name': 'data', 'mountPath': '/data'}],
                }],
                'volumes': [{'name': 'data', 'persistentVolumeClaim': {'claimName': 'storage-%s' % base}}],
            },
        }

    def _odoo_pod_body(self, labels):
        self.ensure_one()
        base = '%s-%s' % (self.hostname, self.random_number)
        secret = 'saas-%s' % base
        return {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': self._pod_meta(self.odoo_pod, 'odoo'),
            'spec': {
                'restartPolicy': 'Always',
                'containers': [{
                    'name': 'odoo',
                    'image': self._image_odoo(),
                    'imagePullPolicy': 'IfNotPresent',
                    'args': ['bash', '/saas-entrypoint.sh'],
                    'ports': [{'containerPort': 8069}],
                    'env': [
                        {'name': 'HOST', 'value': self.postgres_service},
                        {'name': 'PORT', 'value': '5432'},
                        {'name': 'USER', 'value': self.database_user},
                        {'name': 'DB_NAME', 'value': self.database_name},
                        {'name': 'INSTALL_MODULES', 'value': ','.join(self._initial_module_names())},
                        {'name': 'PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret, 'key': 'postgres-password'}}},
                        {'name': 'ADMIN_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret, 'key': 'admin-password'}}},
                    ],
                    'startupProbe': {
                        'tcpSocket': {'port': 8069},
                        'periodSeconds': 15,
                        'failureThreshold': 40,
                    },
                    'readinessProbe': {
                        'tcpSocket': {'port': 8069},
                        'periodSeconds': 10,
                    },
                    'resources': {
                        'requests': {'cpu': '200m', 'memory': '512Mi'},
                        'limits': {'cpu': '2', 'memory': '2Gi'},
                    },
                    'volumeMounts': [
                        {'name': 'data', 'mountPath': '/var/lib/odoo'},
                        {'name': 'config', 'mountPath': '/etc/odoo', 'readOnly': True},
                        {'name': 'entrypoint', 'mountPath': '/saas-entrypoint.sh', 'subPath': 'entrypoint.sh', 'readOnly': True},
                    ],
                }],
                'volumes': [
                    {'name': 'data', 'persistentVolumeClaim': {'claimName': 'odoo-data-%s' % base}},
                    {'name': 'config', 'secret': {'secretName': secret, 'items': [{'key': 'odoo.conf', 'path': 'odoo.conf'}]}},
                    {'name': 'entrypoint', 'secret': {'secretName': secret, 'defaultMode': 365, 'items': [{'key': 'entrypoint.sh', 'path': 'entrypoint.sh'}]}},
                ],
            },
        }

    def _service_body(self, name, pod_name, port, port_name, service_type='ClusterIP'):
        return {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': name,
                'labels': self._component_labels('service', name),
            },
            'spec': {
                'type': service_type,
                'selector': {'app': pod_name},
                'ports': [{'name': port_name, 'port': port, 'targetPort': port}],
            },
        }

    def _odoo_nodeport_service_body(self, name, pod_name):
        """مثل odoo-web اصلی: سرویس NodePort روی ۸۰۶۹ با پورت خودکار نود."""
        body = self._service_body(name, pod_name, 8069, 'http', service_type='NodePort')
        return body

    def _ingress_body(self, base):
        self.ensure_one()
        return {
            'apiVersion': 'networking.k8s.io/v1',
            'kind': 'Ingress',
            'metadata': {
                'name': 'odoo-%s' % base,
                'labels': self._base_labels(),
                'annotations': {
                    'traefik.ingress.kubernetes.io/router.entrypoints': 'web,websecure',
                },
            },
            'spec': {
                'ingressClassName': 'traefik',
                'rules': [{
                    'host': self.domain,
                    'http': {
                        'paths': [{
                            'path': '/',
                            'pathType': 'Prefix',
                            'backend': {
                                'service': {
                                    'name': self.odoo_service,
                                    'port': {'number': 8069},
                                },
                            },
                        }],
                    },
                }],
            },
        }

    def _safe_error(self, error):
        text = str(error)
        for secret in (self.database_password, self.odoo_admin_password, self.odoo_master_password):
            if secret:
                text = text.replace(secret, '***')
        return text[:2000]

    def _tenant_rpc(self):
        self.ensure_one()
        if not self.odoo_service or not self.database_name or not self.odoo_admin_password:
            raise UserError(_('اطلاعات اتصال به اودووی مشتری کامل نیست.'))
        url = 'http://%s:8069' % self.odoo_service
        common = xmlrpc.client.ServerProxy('%s/xmlrpc/2/common' % url, allow_none=True, use_datetime=True)
        uid = common.authenticate(self.database_name, 'admin', self.odoo_admin_password, {})
        if not uid:
            raise UserError(_('ورود XML-RPC به اودووی مشتری ناموفق بود.'))
        models_proxy = xmlrpc.client.ServerProxy('%s/xmlrpc/2/object' % url, allow_none=True, use_datetime=True)
        return uid, models_proxy

    def _sync_installed_modules(self):
        self.ensure_one()
        uid, models_proxy = self._tenant_rpc()
        rows = models_proxy.execute_kw(
            self.database_name,
            uid,
            self.odoo_admin_password,
            'ir.module.module',
            'search_read',
            [[('state', '=', 'installed')]],
            {'fields': ['name', 'shortdesc'], 'limit': 500},
        )
        installed_names = set()
        for row in rows:
            technical_name = row['name']
            installed_names.add(technical_name)
            self._ensure_module_lines([technical_name], state='installed')
            line = self.service_module_ids.filtered(lambda item: item.technical_name == technical_name)[:1]
            if line:
                line.write({
                    'name': row.get('shortdesc') or technical_name,
                    'state': 'installed',
                    'last_error': False,
                })
        stale = self.service_module_ids.filtered(
            lambda line: line.state == 'installed' and line.technical_name not in installed_names
        )
        stale.write({'state': 'uninstalled'})

    def _install_requested_modules(self):
        self.ensure_one()
        names = []
        names.extend(self.requested_module_ids.mapped('technical_name'))
        if self.install_module_names:
            names.extend(
                part.strip()
                for part in self.install_module_names.split(',')
                if part.strip()
            )
        pending_lines = self.service_module_ids.filtered(lambda line: line.state in ('pending', 'failed', 'uninstalled'))
        names.extend(pending_lines.mapped('technical_name'))
        names = [name for name in dict.fromkeys(names) if name and name != 'base']
        if not names:
            raise UserError(_('ماژولی برای نصب انتخاب نشده است.'))
        self._ensure_module_lines(names, state='pending')
        uid, models_proxy = self._tenant_rpc()
        module_ids = models_proxy.execute_kw(
            self.database_name,
            uid,
            self.odoo_admin_password,
            'ir.module.module',
            'search',
            [[('name', 'in', names), ('state', '!=', 'installed')]],
        )
        if not module_ids:
            self._sync_installed_modules()
            return
        try:
            models_proxy.execute_kw(
                self.database_name,
                uid,
                self.odoo_admin_password,
                'ir.module.module',
                'button_immediate_install',
                [module_ids],
            )
        except Exception as error:
            for line in self.service_module_ids.filtered(lambda item: item.technical_name in names):
                if line.state != 'installed':
                    line.write({'state': 'failed', 'last_error': self._safe_error(error)})
            raise UserError(_('نصب ماژول ناموفق بود: %s') % self._safe_error(error)) from error
        self._sync_installed_modules()
        self.install_module_names = False
