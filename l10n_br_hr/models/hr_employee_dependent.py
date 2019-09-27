# (c) 2014 Kmee - Rafael da Silva Lima <rafael.lima@kmee.com.br>
# (c) 2014 Kmee - Matheus Felix <matheus.felix@kmee.com.br>
# (c) 2016 KMEE Informática - Daniel Sadamo <daniel.sadamo@kmee.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from erpbrasil.base.fiscal import cnpj_cpf
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployeeDependent(models.Model):
    _name = 'hr.employee.dependent'
    _description = 'Employee\'s Dependents'
    _rec_name = "dependent_name"
    _inherits = {'res.partner': 'partner_id'}

    @api.constrains('dependent_cpf')
    def _validate_cpf(self):
        if self.dependent_cpf:
            if not cnpj_cpf.validar(self.dependent_cpf):
                raise ValidationError(_('Invalid CPF for dependent %s')
                                      % self.dependent_name)

    def _get_default_employee(self):
        if self.env.user.has_group('base.group_hr_user'):
            return False
        return self.env.user.employee_ids[0]

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee')

    dependent_name = fields.Char(
        string='Name',
        size=64,
        required=True)

    dependent_dob = fields.Date(
        string='Date of birth',
        required=True)

    dependent_type_id = fields.Many2one(
        string='Relatedness',
        required=True,
        comodel_name='hr.dependent.type')

    pension_benefits = fields.Float(
        string='Allowance value')

    dependent_verification = fields.Boolean(
        string='Is dependent')

    health_verification = fields.Boolean(
        string='Healthcare plan')

    dependent_gender = fields.Selection(
        string='Gender',
        selection=[
            ('m', 'Male'),
            ('f', 'Female')])

    dependent_rg = fields.Char(
        string='RG')

    dependent_cpf = fields.Char(
        string='CPF')

    have_alimony = fields.Boolean(
        string='Tem Pensão?')

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        ondelete='cascade',
        auto_join=True,
        required=True,
        help="Parceiro que contem as informações de banco do dependente."
    )

    partner_id_bank_ids = fields.One2many(
        comodel_name='res.partner.bank',
        string='Info Bank',
        related='partner_id.bank_ids',
    )
    dep_sf = fields.Boolean(
        string='Salário Família?',
    )
    inc_trab = fields.Boolean(
        string='Incapacidade Física ou Mental?',
    )
    inc_trab_inss_file = fields.Binary(
        string='Atestado de incapacidade INSS',
    )
    relative_file = fields.Binary(
        string='Documento comprobatório da relação',
        help='Certidão de Nascimento / Casamento / etc'
    )

    @api.model
    def create(self, vals):
        ctx = self.env.context.copy()
        ctx['create_depentent'] = True
        ctx['depentent_employee_id'] = vals.get('employee_id', False)
        #
        # O sudo foi utilizado para evitar a permissão de criação de contato
        # para o funcionário.
        #
        patient = super(
            HrEmployeeDependent, self.sudo().with_context(ctx)
        ).create(vals)
        return patient
