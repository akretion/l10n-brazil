# Copyright (C) 2026 - Akretion - Raphaël Valyi
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    "name": "Brazilian Localization Rural Producer (POC extra field)",
    "summary": (
        "POC for OCA/l10n-brazil#5580: produtor rural (pessoa física com CNPJ "
        "CAEPF) modeled with a second fiscal document field on res.partner"
    ),
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "18.0.1.0.0",
    "depends": ["l10n_br_nfe"],
    "data": [
        "views/res_partner_views.xml",
    ],
    "demo": [
        "demo/res_partner_demo.xml",
        "demo/fiscal_document_demo.xml",
    ],
    "installable": True,
}
