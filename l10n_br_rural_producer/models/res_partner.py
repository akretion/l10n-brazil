# Copyright (C) 2026 - Akretion - Raphaël Valyi
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from erpbrasil.base.fiscal import cnpj_cpf
from erpbrasil.base.misc import punctuation_rm

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.l10n_br_base.tools import check_ie


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_br_is_rural_producer = fields.Boolean(
        string="Rural Producer (PF)",
        help="Pessoa física with a registered rural activity (CAEPF/CNPJ). "
        "Fiscal documents of the rural activity are issued with the Rural "
        "CNPJ below instead of the CPF.",
        tracking=True,
    )
    l10n_br_rural_cnpj = fields.Char(
        string="Rural CNPJ (CAEPF)",
        help="CNPJ of the rural activity of this pessoa física. The partner "
        "keeps his CPF in the standard VAT field; fiscal documents emitted "
        "for the rural activity use this CNPJ instead.",
        tracking=True,
    )

    @api.onchange("l10n_br_rural_cnpj")
    def _onchange_l10n_br_rural_cnpj(self):
        for record in self:
            if record.l10n_br_rural_cnpj:
                record.l10n_br_rural_cnpj = punctuation_rm(record.l10n_br_rural_cnpj)

    @api.constrains("l10n_br_is_rural_producer", "is_company", "vat")
    def _check_rural_producer_is_pf(self):
        for record in self:
            if not record.l10n_br_is_rural_producer:
                continue
            if record.is_company:
                raise ValidationError(
                    self.env._(
                        "A rural producer with a CAEPF/CNPJ is a pessoa física: "
                        "'Is a Company' must be unset (partner %(name)s).",
                        name=record.name,
                    )
                )
            if record.country_id == self.env.ref("base.br") and (
                not record.vat or not cnpj_cpf.validar_cpf(record.vat)
            ):
                raise ValidationError(
                    self.env._(
                        "A rural producer must keep his valid CPF in the VAT "
                        "field (partner %(name)s).",
                        name=record.name,
                    )
                )

    @api.constrains("l10n_br_rural_cnpj", "vat", "country_id")
    def _check_l10n_br_rural_cnpj(self):
        """The rural CNPJ must be valid and unique across BOTH document
        columns: no other partner may hold it as `vat` or as his own rural
        CNPJ, and conversely no rural CNPJ may equal another partner's vat.
        Plain vat-vs-vat duplicates are left to the l10n_br_base constraint.
        """
        for record in self:
            rural_cnpj = punctuation_rm(record.l10n_br_rural_cnpj or "")
            vat = punctuation_rm(record.vat or "")
            if rural_cnpj:
                if record.country_id == self.env.ref(
                    "base.br"
                ) and not cnpj_cpf.validar_cnpj(rural_cnpj):
                    raise ValidationError(
                        self.env._(
                            "Rural CNPJ %(cnpj)s is invalid (partner %(name)s).",
                            cnpj=record.l10n_br_rural_cnpj,
                            name=record.name,
                        )
                    )
                others = self.search(
                    [
                        ("id", "!=", record.id),
                        "|",
                        ("l10n_br_rural_cnpj", "!=", False),
                        ("vat", "!=", False),
                    ]
                )
                for other in others:
                    if rural_cnpj in (
                        punctuation_rm(other.l10n_br_rural_cnpj or ""),
                        punctuation_rm(other.vat or ""),
                    ):
                        raise ValidationError(
                            self.env._(
                                "Rural CNPJ %(cnpj)s is already used by partner "
                                "%(name)s (ID %(partner_id)s).",
                                cnpj=record.l10n_br_rural_cnpj,
                                name=other.name,
                                partner_id=other.id,
                            )
                        )
            if vat:
                # reverse direction: a vat (CPF or CNPJ) may not collide
                # with the rural CNPJ of another partner.
                rural_others = self.search(
                    [
                        ("id", "!=", record.id),
                        ("l10n_br_rural_cnpj", "!=", False),
                    ]
                )
                for other in rural_others:
                    if vat == punctuation_rm(other.l10n_br_rural_cnpj or ""):
                        raise ValidationError(
                            self.env._(
                                "The document %(vat)s is already the rural CNPJ "
                                "of partner %(name)s (ID %(partner_id)s).",
                                vat=record.vat,
                                name=other.name,
                                partner_id=other.id,
                            )
                        )

    @api.constrains("l10n_br_ie_code", "state_id", "l10n_br_is_rural_producer")
    def _check_rural_producer_ie(self):
        """l10n_br_base only validates the IE when is_company=True; the rural
        producer is a pessoa física but his IE is the fiscal IE of the rural
        activity and must be validated as well."""
        for record in self:
            if record.l10n_br_is_rural_producer and not record.is_company:
                check_ie(
                    record.env,
                    record.l10n_br_ie_code,
                    record.state_id,
                    record.country_id,
                )

    @api.depends("l10n_br_is_rural_producer", "l10n_br_rural_cnpj")
    def _compute_nfe_data(self):
        """Rural producer pessoa física: emit the NFe with the rural CNPJ
        (CAEPF) instead of the CPF.

        NOTE (POC simplification): the choice is STATIC per partner — once
        the rural CNPJ is set, every NFe involving this partner uses it,
        whatever the operation. A contextual (per-document) choice would
        require threading the document context into this partner compute,
        which is exactly the regression risk the issue raises.
        """
        res = super()._compute_nfe_data()
        for rec in self:
            if (
                rec.l10n_br_is_rural_producer
                and rec.l10n_br_rural_cnpj
                and rec.country_id.code == "BR"
            ):
                rec.nfe40_choice_tlocal = "nfe40_CNPJ"
                rec.nfe40_choice_emit = "nfe40_CNPJ"
                rec.nfe40_choice_dest = "nfe40_CNPJ"
                rec.nfe40_choice_transporta = "nfe40_CNPJ"
                rec.nfe40_CNPJ = punctuation_rm(rec.l10n_br_rural_cnpj)
                rec.nfe40_CPF = None
        return res

    def _export_field(self, xsd_field, class_obj, member_spec, export_value=None):
        """l10n_br_nfe's res_partner._export_field re-derives the CNPJ/CPF
        from `self.vat` at export time (gated by nfe40_choice_tlocal),
        bypassing the computed nfe40_CNPJ — the rural CNPJ must be injected
        here as well. This is exactly the kind of direct `vat` read the
        issue #5580 lists as problematic."""
        if (
            xsd_field in ("nfe40_CNPJ", "nfe40_CPF")
            and self.l10n_br_is_rural_producer
            and self.l10n_br_rural_cnpj
            and self.country_id.code == "BR"
            and xsd_field == self.nfe40_choice_tlocal
        ):
            return punctuation_rm(self.l10n_br_rural_cnpj)
        return super()._export_field(xsd_field, class_obj, member_spec, export_value)
