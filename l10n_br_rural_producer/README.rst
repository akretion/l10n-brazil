=============================================
Rural Producer POC — extra field proposal (B)
=============================================

**Proof of concept for https://github.com/OCA/l10n-brazil/issues/5580 — NOT for production.**

Context
=======

From 2027 the Receita Federal requires every produtor rural pessoa física to
have a CNPJ (the former CAEPF). The same person then holds **two fiscal
documents**: his CPF (civil identity) and his CNPJ (registered rural
activity). Today ``res.partner.vat`` is a single field and ``is_company`` is
used as a proxy for "which document tag should the NFe/CTe XML use", so this
case is not supported.

Proposal B — extra field (this branch)
======================================

Keep **one** ``res.partner`` per person and add a second document field:

* ``l10n_br_is_rural_producer`` (boolean, only for pessoa física);
* ``l10n_br_rural_cnpj`` — the CNPJ of the rural activity (CAEPF);
* ``vat`` keeps the **CPF**;
* the NFe tag choice (``res.partner._compute_nfe_data``) is overridden so
  the XML uses the rural CNPJ for emit/dest/transporta/tlocal.

Two override points are required, not one
=========================================

The POC uncovered that the NFe document-number choice is implemented in
**two** places, not one:

1. ``res.partner._compute_nfe_data`` sets the ``nfe40_choice_*`` selections
   and the ``nfe40_CNPJ``/``nfe40_CPF`` computed values from ``is_company``;
2. ``l10n_br_nfe``'s ``res_partner._export_field`` **re-derives** the CNPJ/CPF
   from ``self.vat`` at export time (gated by ``nfe40_choice_tlocal``, with a
   ``parent_id`` fallback), **bypassing the computed fields entirely**.

Overriding only the compute produces a corrupt XML (``<CNPJ>`` tag with the
CPF digits) — the first POC failure. This is precisely the "reads
``partner_id.vat`` directly" pattern the issue lists; any field-based
proposal must find and patch every such bypass (CTe has an equivalent
``res_partner._export_field`` override, SPED another one...). The
parent/child proposal needs none of them, because the child partner's
``vat`` simply *is* the CNPJ.

Constraints shipped in this POC
===============================

* the rural CNPJ must be a valid CNPJ (check digits);
* it must be **unique across both document columns** (``vat`` and
  ``l10n_br_rural_cnpj``) of all partners;
* a rural producer must be a pessoa física with a valid CPF in ``vat``;
* his IE is validated per state (``l10n_br_base._check_ie`` only validates
  the IE of companies, so this POC adds the check).

Known limitations (demonstrated by the demo/tests)
==================================================

* **static choice**: once the rural CNPJ is set, *every* NFe of this partner
  uses it — a personal (CPF) sale to the same person is no longer possible
  without editing the partner. A contextual (per-document) choice would
  require threading the document through the partner compute — the surface
  of change the issue warns about (NFe, CTe, MDFe, NFSe, SPED...);
* **import de-para**: the NFe XML import matches partners by ``vat``; an XML
  issued with the rural CNPJ would not match this partner and would create
  a duplicate PJ partner — the import matching must be extended;
* **related fields**: ``l10n_br_fiscal.document.partner_cnpj_cpf`` (related
  to ``partner_id.vat``) shows the CPF even on documents fiscally issued
  with the CNPJ (asserted in ``test_nfe_in_vendor_nfe``).

Demo data
=========

* ``res_partner_rural_producer`` — João Silva, PF, CPF 482.906.174-02 in
  ``vat``, rural CNPJ 48.290.617/0001-15, IE 623.079.040/0090 (MG), fiscal
  profile "Contribuinte" PF (indIEDest 1);
* ``demo_nfe_rural_out`` — outgoing NFe to him (dest = rural CNPJ + IE);
* ``demo_nfe_rural_in`` — incoming NFe **emitted by him** (issuer=partner).
