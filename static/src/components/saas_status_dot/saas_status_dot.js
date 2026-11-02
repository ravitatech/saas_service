/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const HEALTH_COLORS = {
    healthy: "text-success",
    warning: "text-warning",
    danger: "text-danger",
    inactive: "text-muted",
    unknown: "text-muted",
    running: "text-success",
    provisioning: "text-warning",
    draft: "text-muted",
    error: "text-danger",
};

const PHASE_COLORS = {
    Running: "text-success",
    Pending: "text-warning",
    ContainerCreating: "text-warning",
    PodInitializing: "text-warning",
    ScaledDown: "text-muted",
    Failed: "text-danger",
    Missing: "text-danger",
    Error: "text-danger",
    CrashLoopBackOff: "text-danger",
    ImagePullBackOff: "text-danger",
    ErrImagePull: "text-danger",
    CreateContainerConfigError: "text-danger",
    Unknown: "text-muted",
};

const HEALTH_LABELS = {
    healthy: _t("سالم"),
    warning: _t("در حال آماده‌سازی"),
    danger: _t("مشکل"),
    inactive: _t("غیرفعال"),
    unknown: _t("نامشخص"),
};

export class SaasStatusDot extends Component {
    static template = "saas_service.SaasStatusDot";
    static props = {
        ...standardFieldProps,
        options: { type: Object, optional: true },
    };

    get rawValue() {
        return this.props.record.data[this.props.name];
    }

    get mode() {
        return (this.props.options && this.props.options.mode) || "auto";
    }

    get colorClass() {
        const value = this.rawValue;
        if (!value) {
            return "text-muted";
        }
        if (this.mode === "phase") {
            if (PHASE_COLORS[value]) {
                return PHASE_COLORS[value];
            }
            if (String(value).startsWith("Init:")) {
                return "text-warning";
            }
            return "text-warning";
        }
        if (this.mode === "health" || this.mode === "state") {
            return HEALTH_COLORS[value] || "text-muted";
        }
        return HEALTH_COLORS[value] || PHASE_COLORS[value] || "text-muted";
    }

    get label() {
        const value = this.rawValue;
        if (!value) {
            return _t("نامشخص");
        }
        if (HEALTH_LABELS[value]) {
            return HEALTH_LABELS[value];
        }
        const selection = this.props.record.fields[this.props.name]?.selection || [];
        const match = selection.find((item) => item[0] === value);
        return match ? match[1] : value;
    }
}

export const saasStatusDot = {
    component: SaasStatusDot,
    supportedTypes: ["char", "selection"],
    extractProps: ({ options }) => ({
        options: options || {},
    }),
};

registry.category("fields").add("saas_status_dot", saasStatusDot);
