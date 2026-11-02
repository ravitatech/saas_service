import json
import os
import ssl
import urllib.error
import urllib.request


class K8sError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        message = payload
        if isinstance(payload, dict):
            message = payload.get('message') or payload
        super().__init__('Kubernetes API %s: %s' % (status, message))


class K8sClient:
    """In-cluster Kubernetes client. Uses the pod service-account token."""

    def __init__(self, namespace):
        host = os.environ.get('KUBERNETES_SERVICE_HOST')
        port = os.environ.get('KUBERNETES_SERVICE_PORT', '443')
        if not host:
            raise K8sError(0, 'این پردازه داخل کلاستر نیست و به Kubernetes دسترسی ندارد.')
        self.namespace = namespace
        self.base = 'https://%s:%s' % (host, port)
        token_path = '/var/run/secrets/kubernetes.io/serviceaccount/token'
        ca_path = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
        with open(token_path, encoding='utf-8') as handle:
            self.token = handle.read().strip()
        self.ssl_context = ssl.create_default_context(cafile=ca_path)

    def request(self, method, path, body=None):
        data = None
        headers = {'Authorization': 'Bearer %s' % self.token, 'Accept': 'application/json'}
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, context=self.ssl_context, timeout=30) as response:
                raw = response.read().decode('utf-8')
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode('utf-8', errors='replace')
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {'message': raw[:500]}
            return error.code, payload

    def create(self, path, body):
        status, payload = self.request('POST', path, body)
        if status in (200, 201, 202, 409):
            return status, payload
        raise K8sError(status, payload)

    def get(self, path):
        status, payload = self.request('GET', path)
        if status == 404:
            return None
        if status != 200:
            raise K8sError(status, payload)
        return payload

    def patch(self, path, body):
        data = json.dumps(body).encode('utf-8')
        headers = {
            'Authorization': 'Bearer %s' % self.token,
            'Accept': 'application/json',
            'Content-Type': 'application/strategic-merge-patch+json',
        }
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method='PATCH')
        try:
            with urllib.request.urlopen(request, context=self.ssl_context, timeout=30) as response:
                raw = response.read().decode('utf-8')
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode('utf-8', errors='replace')
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {'message': raw[:500]}
            raise K8sError(error.code, payload)

    def _ns(self, api):
        return '%s/namespaces/%s' % (api, self.namespace)

    def ensure_secret(self, body):
        _status, payload = self.create(self._ns('/api/v1') + '/secrets', body)
        return payload

    def ensure_pvc(self, body):
        _status, payload = self.create(self._ns('/api/v1') + '/persistentvolumeclaims', body)
        return payload

    def ensure_pod(self, body):
        _status, payload = self.create(self._ns('/api/v1') + '/pods', body)
        return payload

    def ensure_service(self, body):
        path = self._ns('/api/v1') + '/services'
        status, payload = self.create(path, body)
        name = body['metadata']['name']
        if status == 409:
            existing = self.get_service(name)
            desired_type = (body.get('spec') or {}).get('type', 'ClusterIP')
            if existing and (existing.get('spec') or {}).get('type') != desired_type:
                _status, payload = self.patch(path + '/' + name, {'spec': body['spec']})
            else:
                payload = existing
        return payload

    def ensure_ingress(self, body):
        _status, payload = self.create(self._ns('/apis/networking.k8s.io/v1') + '/ingresses', body)
        return payload

    def get_pod(self, name):
        return self.get(self._ns('/api/v1') + '/pods/' + name)

    def get_service(self, name):
        return self.get(self._ns('/api/v1') + '/services/' + name)

    def delete(self, path):
        status, payload = self.request('DELETE', path)
        if status in (200, 202, 204, 404):
            return payload
        raise K8sError(status, payload)

    def delete_pod(self, name):
        return self.delete(self._ns('/api/v1') + '/pods/' + name)

    def delete_service(self, name):
        return self.delete(self._ns('/api/v1') + '/services/' + name)

    def delete_pvc(self, name):
        return self.delete(self._ns('/api/v1') + '/persistentvolumeclaims/' + name)

    def delete_secret(self, name):
        return self.delete(self._ns('/api/v1') + '/secrets/' + name)

    def delete_ingress(self, name):
        return self.delete(self._ns('/apis/networking.k8s.io/v1') + '/ingresses/' + name)
