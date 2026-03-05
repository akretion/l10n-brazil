# Copyright 2026 Akretion, Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Monitor de CT-e",
    "summary": """
    Monitor incoming CT-e documents via the DF-e distribution web service
    (CTeDistribuicaoDFe).
    """,
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": ["l10n_br_fiscal_dfe", "l10n_br_cte"],
    "data": [
        # Data & Actions
        "data/ir_cron.xml",
        "data/cte_actions.xml",
        # Views
        "views/cte_dfe_views.xml",
        "views/cte_document_views.xml",
        "views/res_company_view.xml",
    ],
    "external_dependencies": {
        "python": [
            "nfelib",
        ],
    },
}
