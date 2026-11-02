/** @odoo-module **/

function togglePassword(button) {
    const group = button.closest(".o_saas_password_group");
    if (!group) {
        return;
    }
    const input = group.querySelector("input.o_saas_password_input");
    const icon = button.querySelector("i");
    if (!input || !icon) {
        return;
    }
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    icon.classList.toggle("fa-eye", !show);
    icon.classList.toggle("fa-eye-slash", show);
    button.setAttribute("title", show ? "مخفی کردن رمز" : "نمایش رمز");
    button.setAttribute("aria-label", show ? "مخفی کردن رمز" : "نمایش رمز");
}

document.addEventListener("click", (event) => {
    const button = event.target.closest(".o_saas_password_toggle");
    if (!button) {
        return;
    }
    event.preventDefault();
    togglePassword(button);
});
