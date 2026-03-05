def _cte_dfe_search_specific_document(self, access_key=None, nsu=None):
        self.ensure_one()
        processor = self._cte_dfe_get_processor()
        result = processor.consultar_distribuicao(
            chave=access_key,
            nsu_especifico=utils.format_nsu(nsu) if nsu else None,
            cnpj_cpf=re.sub("[^0-9]", "", self.vat),
        )
        if not self._dfe_validate_distribution_response(result, raise_message=True):
            return

        self._dfe_log(f"CT-e Specific OK: {result.resposta.cStat}", log_type="success", result=result)
        self._cte_process_distribution(result.resposta)

    @api.model
    def _cron_cte_dfe_search_documents(self):
        companies = self.search([("cte_auto_fetch", "=", True)])
        for company in companies:
            company._cte_dfe_document_distribution()
