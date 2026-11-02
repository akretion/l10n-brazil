# Copyright (C) 2026 - Akretion (<https://akretion.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Convert 17.0 plain columns of fields that became ``company_dependent``.

In 18.0 these fields are stored in a jsonb column shaped ``{"<company_id>":
value}``; in 17.0 they were plain varchar / integer columns.  Odoo's own
automatic conversion (``ALTER ... USING column::jsonb``) fails on values such
as ``'07'`` and cannot convert integer columns that still carry a foreign
key, which aborts the whole upgrade of the module.
"""

import logging

import psycopg2
from openupgradelib import openupgrade

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


# (table, column, is_text)
COMPANY_DEPENDENT_COLUMNS = [
    ("product_template", "fiscal_type", True),
    ("product_template", "icms_origin", True),
    ("l10n_br_fiscal_operation", "fiscal_position_id", False),
    ("l10n_br_fiscal_operation", "journal_id", False),
    ("l10n_br_fiscal_operation_line", "fiscal_position_id", False),
]


def _column_type(cr, table, column):
    cr.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table, column),
    )
    row = cr.fetchone()
    return row and row[0]


def _drop_foreign_keys(cr, table, column):
    """A m2o that becomes company-dependent can no longer carry an FK."""
    cr.execute(
        """
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_attribute att
             ON att.attrelid = rel.oid AND att.attnum = ANY (con.conkey)
        WHERE con.contype = 'f'
          AND rel.relname = %s
          AND att.attname = %s
        """,
        (table, column),
    )
    for (conname,) in cr.fetchall():
        cr.execute(
            SQL(
                "ALTER TABLE %s DROP CONSTRAINT %s",
                SQL.identifier(table),
                SQL.identifier(conname),
            )
        )
        _logger.info("l10n_br_fiscal: dropped constraint %s", conname)


def _drop_dependent_views(cr, table, column):
    """Drop (materialized) views reading the column, they are recreated by
    their own module once the ORM re-runs with the new column type."""
    cr.execute(
        """
        SELECT DISTINCT dep.relname
        FROM pg_depend d
        JOIN pg_rewrite rw ON rw.oid = d.objid
        JOIN pg_class dep ON dep.oid = rw.ev_class
        JOIN pg_class src ON src.oid = d.refobjid
        JOIN pg_attribute att
             ON att.attrelid = src.oid AND att.attnum = d.refobjsubid
        WHERE d.classid = 'pg_rewrite'::regclass
          AND d.refclassid = 'pg_class'::regclass
          AND src.relname = %s
          AND att.attname = %s
          AND dep.relkind IN ('v', 'm')
          AND dep.relname <> src.relname
        """,
        (table, column),
    )
    for (view,) in cr.fetchall():
        cr.execute(
            SQL(
                "DROP VIEW IF EXISTS %s CASCADE",
                SQL.identifier(view),
            )
        )
        _logger.warning("l10n_br_fiscal: dropped view %s", view)


def _to_company_dependent_jsonb(cr, table, column, company_id, is_text):
    col_type = _column_type(cr, table, column)
    if col_type in (None, "jsonb"):
        # column absent (module not installed) or already converted: idempotent
        return
    _logger.info(
        "l10n_br_fiscal: converting %s.%s (%s) to company-dependent jsonb",
        table,
        column,
        col_type,
    )
    _drop_foreign_keys(cr, table, column)
    cr.execute(
        SQL(
            "ALTER TABLE %s ALTER COLUMN %s DROP DEFAULT",
            SQL.identifier(table),
            SQL.identifier(column),
        )
    )
    empty = SQL("%s::text = ''", SQL.identifier(column)) if is_text else SQL("FALSE")
    query = SQL(
        """
        ALTER TABLE %s ALTER COLUMN %s TYPE jsonb
        USING (
            CASE WHEN %s IS NULL OR %s THEN NULL
                 ELSE jsonb_build_object(%s, %s) END
        )
        """,
        SQL.identifier(table),
        SQL.identifier(column),
        SQL.identifier(column),
        empty,
        str(company_id),
        SQL.identifier(column),
    )
    try:
        with cr.savepoint():
            cr.execute(query)
    except psycopg2.errors.NotSupportedError:
        _drop_dependent_views(cr, table, column)
        cr.execute(query)


@openupgrade.migrate()
def migrate(env, version):
    cr = env.cr
    if not openupgrade.table_exists(cr, "product_template"):
        return
    cr.execute("SELECT id FROM res_company ORDER BY id LIMIT 1")
    row = cr.fetchone()
    company_id = row and row[0]
    if not company_id:
        _logger.warning("l10n_br_fiscal: no company, skipping conversion")
        return
    cr.execute("SELECT count(*) FROM res_company")
    if cr.fetchone()[0] > 1:
        _logger.warning(
            "l10n_br_fiscal: several companies, the existing 17.0 values are "
            "attributed to company %s",
            company_id,
        )
    for table, column, is_text in COMPANY_DEPENDENT_COLUMNS:
        if not openupgrade.column_exists(cr, table, column):
            continue
        _to_company_dependent_jsonb(cr, table, column, company_id, is_text)
