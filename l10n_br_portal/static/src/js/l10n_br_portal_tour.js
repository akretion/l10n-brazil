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
                run: "selectByLabel Brazil",
            },
            {
                content: "Select state Minas Gerais",
                trigger: "select[name='state_id']",
                run: "selectByLabel Minas Gerais",
            },
            {
                content: "Select city Itajubá",
                trigger: "select[name='city_id']",
                run: "selectByLabel Itajubá",
            },
            {
                trigger: "button[type='submit']",
                run: "click",
            },
        ],
    });
});
