# Copyright (C) 2025  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # 1. Migrate l10n_br_fiscal.document state_edoc
    # Map states that are ALWAYS the same
    sql_query = """
        UPDATE l10n_br_fiscal_document
        SET state_edoc = CASE state_edoc
            WHEN 'em_digitacao' THEN 'draft'
            WHEN 'cancelada' THEN 'cancel'
            WHEN 'inutilizada' THEN 'cancel'
            ELSE state_edoc
        END
        WHERE state_edoc IN ('em_digitacao', 'cancelada', 'inutilizada');
    """
    openupgrade.logged_query(env.cr, sql_query)

    # Map other states for non-electronic documents
    sql_query = """
        UPDATE l10n_br_fiscal_document
        SET state_edoc = CASE state_edoc
            WHEN 'a_enviar' THEN 'open'
            WHEN 'autorizada' THEN 'open'
            WHEN 'enviada' THEN 'open'
            WHEN 'rejeitada' THEN 'open'
            WHEN 'denegada' THEN 'cancel'
            ELSE state_edoc
        END
        WHERE document_electronic = False
          AND state_edoc IN
          ('a_enviar', 'autorizada', 'enviada', 'rejeitada', 'denegada');
    """
    openupgrade.logged_query(env.cr, sql_query)

    # If l10n_br_fiscal_edi is NOT installed, we must map electronic ones too
    # to avoid invalid states in base.
    if not openupgrade.is_module_installed(env.cr, "l10n_br_fiscal_edi"):
        sql_query = """
            UPDATE l10n_br_fiscal_document
            SET state_edoc = CASE state_edoc
                WHEN 'a_enviar' THEN 'open'
                WHEN 'autorizada' THEN 'open'
                WHEN 'enviada' THEN 'open'
                WHEN 'rejeitada' THEN 'open'
                WHEN 'denegada' THEN 'cancel'
                ELSE state_edoc
            END
            WHERE state_edoc IN (
                'a_enviar', 'autorizada', 'enviada',
                'rejeitada', 'denegada'
            );
        """
        openupgrade.logged_query(env.cr, sql_query)

    # 2. Migrate l10n_br_fiscal.document.email (l10n_br_fiscal_notification)
    if openupgrade.table_exists(env.cr, "l10n_br_fiscal_document_email"):
        sql_query = """
            UPDATE l10n_br_fiscal_document_email
            SET state_edoc = CASE state_edoc
                WHEN 'em_digitacao' THEN 'draft'
                WHEN 'autorizada' THEN 'open'
                WHEN 'cancelada' THEN 'cancel'
                WHEN 'a_enviar' THEN 'open'
                WHEN 'enviada' THEN 'open'
                WHEN 'rejeitada' THEN 'open'
                WHEN 'denegada' THEN 'cancel'
                WHEN 'inutilizada' THEN 'cancel'
                ELSE state_edoc
            END
            WHERE state_edoc IN (
                'em_digitacao', 'autorizada', 'cancelada',
                'a_enviar', 'enviada', 'rejeitada',
                'denegada', 'inutilizada'
            );
        """
        openupgrade.logged_query(env.cr, sql_query)

    # 3. Migrate l10n_br_fiscal.subsequent.operation
    # (l10n_br_fiscal_subsequent_document)
    if openupgrade.table_exists(env.cr, "l10n_br_fiscal_subsequent_operation"):
        sql_query = """
            UPDATE l10n_br_fiscal_subsequent_operation
            SET generation_situation = CASE generation_situation
                WHEN 'em_digitacao' THEN 'draft'
                WHEN 'autorizada' THEN 'open'
                WHEN 'cancelada' THEN 'cancel'
                WHEN 'a_enviar' THEN 'open'
                WHEN 'enviada' THEN 'open'
                WHEN 'rejeitada' THEN 'open'
                WHEN 'denegada' THEN 'cancel'
                WHEN 'inutilizada' THEN 'cancel'
                ELSE generation_situation
            END
            WHERE generation_situation IN (
                'em_digitacao', 'autorizada', 'cancelada',
                'a_enviar', 'enviada', 'rejeitada',
                'denegada', 'inutilizada'
            );
        """
        openupgrade.logged_query(env.cr, sql_query)
