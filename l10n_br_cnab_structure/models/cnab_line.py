# Copyright 2022 Engenere
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..cnab.cnab import CnabLine


class CNABLine(models.Model):

    _name = "l10n_br_cnab.line"
    _description = "Lines that make up the CNAB."

    name = fields.Char(compute="_compute_name", store=True)

    sequence = fields.Integer(readonly=True, states={"draft": [("readonly", False)]})

    cnab_structure_id = fields.Many2one(
        comodel_name="l10n_br_cnab.structure",
        ondelete="cascade",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    segment_code = fields.Char(
        states={"draft": [("readonly", False)]},
    )

    content_source_model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Content Source",
        help="Related model that will provide the origin of the contents of CNAB files.",
        compute="_compute_content_source_model_id",
    )

    content_dest_model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Content Destination",
        help="Related model that will provide the destination of the contents of return CNAB files.",
        compute="_compute_dest_source_model_id",
    )

    requerid = fields.Boolean()

    communication_flow = fields.Selection(
        [("sending", "Sending"), ("return", "Return"), ("both", "Sending and Return")],
        required=True,
    )

    current_view = fields.Selection(
        [("general", "General"), ("sending", "Sending"), ("return", "Return")],
        required=True,
        default="general",
    )

    type = fields.Selection(
        [("header", "Header"), ("segment", "Segment"), ("trailer", "Trailer")],
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    field_ids = fields.One2many(
        comodel_name="l10n_br_cnab.line.field",
        inverse_name="cnab_line_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    batch_id = fields.Many2one(
        comodel_name="l10n_br_cnab.batch",
        ondelete="cascade",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    cnab_structure_id = fields.Many2one(
        comodel_name="l10n_br_cnab.structure",
        ondelete="cascade",
        required=True,
        readonly=True,
        states={"draft": [("readonly", "=", False)]},
    )

    @api.model
    def _selection_target_model(self):
        return [
            ("account.payment.order", "Payment Order"),
            ("bank.payment.line", "Bank Payment Line"),
        ]

    resource_ref = fields.Reference(
        string="Reference",
        selection="_selection_target_model",
    )

    cnab_format = fields.Char(related="cnab_structure_id.cnab_format")

    state = fields.Selection(
        selection=[("draft", "Draft"), ("review", "Review"), ("approved", "Approved")],
        readonly=True,
        default="draft",
    )

    def _compute_content_source_model_id(self):
        if self.type in ["header", "trailer"]:
            self.content_source_model_id = self.env["ir.model"].search(
                [("model", "=", "account.payment.order")]
            )
        else:
            self.content_source_model_id = self.env["ir.model"].search(
                [("model", "=", "bank.payment.line")]
            )

    def _compute_dest_source_model_id(self):
        if self.type in ["header", "trailer"] and not self.batch_id:
            self.content_dest_model_id = self.env["ir.model"].search(
                [("model", "=", "l10n_br_cnab.return.log")]
            )
        else:
            self.content_dest_model_id = self.env["ir.model"].search(
                [("model", "=", "l10n_br_cnab.return.event")]
            )

    def output(self, resource_ref, record_type, **kwargs):
        "Compute CNAB output with all fields for this Line"
        self.ensure_one()
        line = CnabLine(record_type)
        for field_id in self.field_ids:
            name, value = field_id.output(resource_ref, **kwargs)
            line.add_field(name, value)
        return line

    @api.depends("segment_code", "cnab_structure_id", "cnab_structure_id.name", "type")
    def _compute_name(self):
        for line in self:
            if line.type == "segment":
                name = f"{line.type} {line.segment_code}"
            else:
                name = line.type

            if line.batch_id:
                line.name = (
                    f"{line.cnab_structure_id.name} -> {line.batch_id.name} -> {name}"
                )
            else:
                line.name = f"{line.cnab_structure_id.name} -> {name}"

    def unlink(self):
        lines = self.filtered(lambda l: l.state != "draft")
        if lines:
            raise UserError(_("You cannot delete an CNAB Line which is not draft !"))
        return super(CNABLine, self).unlink()

    def check_line(self):

        cnab_fields = self.field_ids.sorted(key=lambda r: r.start_pos)

        for f in cnab_fields:
            f.check_field()

        if cnab_fields[0].start_pos != 1:
            raise UserError(
                _(f"{self.name}: The start position of first field must be 1.")
            )

        ref_pos = 0
        for f in cnab_fields:
            if f.start_pos != ref_pos + 1:
                raise UserError(
                    _(
                        f"{self.name}: Start position of field '{f.name}' is less"
                        " than the end position of the previous one."
                    )
                )
            ref_pos = f.end_pos

        last_pos = int(self.cnab_structure_id.cnab_format)
        if cnab_fields[-1].end_pos != last_pos:
            raise UserError(
                _(f"{self.name}: the end position of last field is not {last_pos}.")
            )

        if self.batch_id and self.batch_id.cnab_structure_id != self.cnab_structure_id:
            raise UserError(
                _(
                    f"{self.name}: line cnab structure is different of batch cnab structure."
                )
            )

    @api.onchange("communication_flow")
    def _onchange_communication_flow(self):
        self.current_view = "general"

    def action_general_view(self):
        self.current_view = "general"

    def action_sending_view(self):
        self.current_view = "sending"

    def action_return_view(self):
        self.current_view = "return"
