/* global document, Event */

odoo.define("l10n_br_portal.tour", ["@web/core/registry"], function (require) {
    "use strict";

    var registry = require("@web/core/registry").registry;

    registry.category("web_tour.tours").add("l10n_br_portal_tour", {
        url: "/my/account",
        test: true,
        steps: () => [
            {
                content: "Complete name",
                trigger: "input[name='name']",
                run: "edit Mileo",
            },
            {
                content: "Complete email",
                trigger: "input[name='email']",
                run: "edit test@example.com",
            },
            {
                content: "Complete phone",
                trigger: "input[name='phone']",
                run: "edit 1234567890",
            },
            {
                content: "Complete CPF",
                trigger: "input[name='vat']",
                run: "edit 89604455095",
            },
            {
                content: "Complete Company Name",
                trigger: "input[name='company_name']",
                run: "edit Empresa X",
            },
            {
                content: "Complete State Tax Number",
                trigger: "input[name='l10n_br_ie_code']",
                run: "edit ISENTO",
            },
            {
                content: "Complete Municipal Tax Number",
                trigger: "input[name='l10n_br_im_code']",
                run: "edit 12345",
            },
            {
                content: "Complete ZIP",
                trigger: "input[name='zipcode']",
                run: function () {
                    const input = document.querySelector("input[name='zipcode']");
                    input.value = "37500015";
                    input.dispatchEvent(new Event("change", {bubbles: true}));
                },
            },
            {
                content: "Complete STREET",
                trigger: "input[name='street_name']",
                run: "edit Rua Teste",
            },
            {
                content: "Complete DISTRICT",
                trigger: "input[name='district']",
                run: "edit Teste",
            },
            {
                content: "Complete NUMBER",
                trigger: "input[name='street_number']",
                run: "edit 200",
            },
            {
                content: "Select country Brasil",
                trigger: "select[name='country_id']",
                run: function () {
                    const select = document.querySelector("select[name='country_id']");
                    for (let option of select.options) {
                        if (option.text.includes("Brazil")) {
                            select.value = option.value;
                            select.dispatchEvent(new Event("change", {bubbles: true}));
                            break;
                        }
                    }
                },
            },
            {
                content: "Select state Minas Gerais",
                trigger: "select[name='state_id']",
                run: function () {
                    const select = document.querySelector("select[name='state_id']");
                    for (let option of select.options) {
                        if (option.text.includes("Minas Gerais")) {
                            select.value = option.value;
                            select.dispatchEvent(new Event("change", {bubbles: true}));
                            break;
                        }
                    }
                },
            },
            {
                content: "Select city Itajubá",
                trigger: "select[name='city_id']",
                run: function () {
                    const select = document.querySelector("select[name='city_id']");
                    for (let option of select.options) {
                        if (option.text.includes("Itajubá")) {
                            select.value = option.value;
                            select.dispatchEvent(new Event("change", {bubbles: true}));
                            break;
                        }
                    }
                },
            },
            {
                trigger: "button[type='submit']",
                run: "click",
            },
        ],
    });
});
