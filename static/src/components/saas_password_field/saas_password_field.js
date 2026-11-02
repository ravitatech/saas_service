/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class SaasPasswordField extends Component {
    static template = "saas_service.SaasPasswordField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({ visible: false });
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    get inputType() {
        return this.state.visible ? "text" : "password";
    }

    toggleVisibility() {
        this.state.visible = !this.state.visible;
    }
}

export const saasPasswordField = {
    component: SaasPasswordField,
    supportedTypes: ["char"],
};

registry.category("fields").add("saas_password", saasPasswordField);
