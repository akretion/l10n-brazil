# Copyright (C) 2025 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    "name": "Brazilian Account Fiscal Invoice UI",
    "summary": "Fiscal document editing UI directly on account.move records",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "maintainers": ["rvalyi", "renatonlima"],
    "depends": [
        "l10n_br_account",
    ],
    "data": [
        "views/fiscal_invoice_view.xml",
        "views/fiscal_invoice_line_view.xml",
        "views/fiscal_invoice_menu.xml",
    ],
    "installable": True,
    "auto_install": False,
}
