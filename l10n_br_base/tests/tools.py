# Copyright (C) 2024 - TODAY Raphaël Valyi - Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from os import path

from odoo.tools.convert import convert_file


def load_fixture_files(env, module, file_names, idref=None, mode="init"):
    """Load demo XML files as noupdate fixtures for tests.

    This allows tests to selectively load only the data they need
    without depending on demo data being fully installed.

    Backported from the 18.0 fixture-loading framework (PR #4326).

    Args:
        env: Odoo environment
        module: Module name (e.g. 'l10n_br_fiscal')
        file_names: List of file names relative to the demo/ directory
        idref: Optional idref dict for XML ID mapping
        mode: 'init' or 'update'
    """
    if idref is None:
        idref = {}
    for file_name in file_names:
        if "/" not in file_name:
            file_name = path.join("demo", file_name)
        convert_file(
            env,
            module=module,
            filename=file_name,
            idref=idref,
            mode=mode,
            noupdate=True,
            kind="demo",
        )
