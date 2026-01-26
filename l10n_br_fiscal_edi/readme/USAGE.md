O fluxo de trabalho operacional para emissão e gerenciamento de documentos fiscais eletrônicos segue as etapas abaixo:

1. Validação (Rascunho -> Em Aberto)
------------------------------------
*   O documento inicia no estado **Rascunho** (`Draft`).
*   Ao clicar no botão **Confirmar**, o sistema executa validações de integridade (campos obrigatórios, regras de negócio básicas) e atribui a numeração sequencial (se configurado).
*   O estado muda para **Em Aberto** (`Open`), indicando que o documento está pronto para transmissão.

2. Transmissão (Em Aberto -> Enviando -> Resultado)
---------------------------------------------------
*   No estado **Em Aberto**, o botão **Enviar** fica disponível.
*   Ao acionar o envio, o documento passa para o estado transitório **Enviando** (`Sending`). Neste momento, o sistema se comunica com o webservice do fisco.
*   **Autorização:** Se o fisco validar e autorizar o documento, o estado muda para **Autorizado** (`Authorized`). O protocolo de autorização e o XML final são gravados.
*   **Rejeição:** Se houver erros de validação no fisco, o estado muda para **Rejeitado** (`Rejected`). As mensagens de erro retornadas pela SEFAZ são exibidas no painel do documento.
    *   *Ação:* O usuário pode corrigir os dados no próprio documento e clicar em **Enviar** novamente para tentar uma nova transmissão.
*   **Denegação:** Se houver irregularidade fiscal (emitente ou destinatário), o estado muda para **Denegado** (`Denied`). Este é um estado final; o número não pode ser reutilizado ou corrigido.

3. Cancelamento
---------------
*   Documentos **Autorizados** podem ser cancelados, desde que dentro do prazo legal e atendendo às regras da UF.
*   Clique no botão **Cancelar** para abrir o assistente. É obrigatório informar uma justificativa (mínimo de 15 caracteres).
*   Após o processamento do evento de cancelamento, o estado do documento muda para **Cancelado** (`Cancelled`).
*   *Nota:* Documentos em Rascunho ou Em Aberto (não transmitidos) podem ser cancelados localmente sem comunicação com o fisco.

4. Eventos e Correções
----------------------
*   **Carta de Correção (CC-e):** Para documentos autorizados (como NF-e e CT-e), utilize a ação "Carta de Correção" para sanar erros em campos permitidos pela legislação.
*   **Inutilização:** Caso uma numeração seja pulada acidentalmente ou por falha técnica, utilize a funcionalidade de Inutilização de Numeração (menu Fiscal > Inutilização) para reportar a faixa ao fisco.

5. Visualização e PDF
---------------------
*   Em estados válidos (Em Aberto, Autorizado), os botões **Visualizar XML** e **Visualizar PDF** permitem inspecionar o arquivo enviado e imprimir o DANFE/DACTE/DAMDFE correspondente.
