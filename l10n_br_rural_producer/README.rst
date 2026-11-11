=============================================
Rural Producer POC — parent/child proposal (A)
=============================================

**Proof of concept for https://github.com/OCA/l10n-brazil/issues/5580 — NOT for production.**

Context
=======

From 2027 the Receita Federal requires every produtor rural pessoa física to
have a CNPJ (the former CAEPF becomes a CNPJ of the individual). The same
person then holds **two fiscal documents**: his CPF (civil identity) and his
CNPJ (registered rural activity). Today ``res.partner.vat`` is a single field
and ``is_company`` is used as a proxy for "which document tag should the
NFe/CTe XML use", so this case is not supported.

Proposal A — parent/child (this branch)
=======================================

Model the rural activity as a **child partner**:

* the pessoa física keeps ``is_company=False`` and his **CPF** in ``vat``;
* a second ``res.partner`` is created with ``is_company=True``, the **CNPJ**
  in ``vat``, the rural IE and ``parent_id`` pointing to the pessoa física.

This module contains **no Python code at all**: it only ships demo data and
tests proving the standard mechanisms already support the case:

* ``l10n_br_base`` already excludes ``vat`` from the parent↔children
  commercial sync (``_commercial_sync_from_company`` /
  ``_commercial_sync_to_children``), so the two records never clobber each
  other's document;
* the NFe CNPJ/CPF tag choice (``res.partner._compute_nfe_data``) keys off
  ``is_company`` of the **selected partner** — sale to the child emits
  ``<CNPJ>``, sale to the parent emits ``<CPF>``;
* a child company is its own ``commercial_partner_id``, so accounting and
  receivables of the rural activity stay separate from the person's;
* an incoming vendor NFe issued by the produtor rural is registered on the
  child partner — which is also what the NFe XML import matches by ``vat``;
* the duplicate-CNPJ constraint (``_check_cnpj_l10n_br_ie_code``) already
  excludes parent/children from its search.

Demo data
=========

* ``res_partner_rural_producer_pf`` — João Silva, PF, CPF 482.906.174-02,
  profile "Não Contribuinte" (indIEDest 9);
* ``res_partner_rural_producer_fazenda`` — child PJ, CNPJ 48.290.617/0001-15,
  IE 623.079.040/0090 (MG), profile "Contribuinte" (indIEDest 1);
* ``demo_nfe_rural_out_cnpj`` — outgoing NFe **to the fazenda** (dest CNPJ);
* ``demo_nfe_rural_out_cpf`` — outgoing NFe **to the pessoa física** (dest CPF);
* ``demo_nfe_rural_in`` — incoming NFe **emitted by the produtor rural**
  (issuer=partner), registered on the child partner.

What still needs a (small) code review for the real PR
======================================================

* the spots listed in the issue that read ``partner_id.vat`` directly
  (``l10n_br_fiscal.document`` related fields, SPED EFD participant export)
  to make sure they follow the document's ``partner_id`` and never jump to
  ``commercial_partner_id`` — for a child company they already coincide;
* a UX helper ("create rural activity" action on the partner) to create the
  child with the address copied, instead of manual data entry.

Note: during this POC we found that ``l10n_br_nfe``'s
``res_partner._export_field`` (and its CTe twin) re-derives the CNPJ/CPF
from ``self.vat`` at export time — bypassing the computed fields — with a
``parent_id`` fallback. That is one more direct ``vat`` read the issue
should list; it also makes the field-based alternative *harder* (it must be
overridden too), while for the parent/child modeling it works as-is: the
child's ``vat`` *is* the CNPJ, and a vat-less delivery child inherits the
document of its parent, which is the behavior you want for the fazenda's
delivery addresses.
