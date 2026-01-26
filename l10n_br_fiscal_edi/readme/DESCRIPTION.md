Este módulo fornece a infraestrutura base para o Intercâmbio Eletrônico de Dados (EDI) de documentos fiscais brasileiros no Odoo.

Ele implementa uma Máquina de Estados Finitos (FSM - Finite State Machine) robusta para gerenciar o ciclo de vida dos documentos fiscais eletrônicos (NF-e, NFS-e, CT-e, MDF-e, etc.), garantindo integridade, consistência e rastreabilidade em todas as transições de estado.

Principais Características
------------------------

*   **Máquina de Estados (FSM):** Controle rigoroso das transições de estado (ex: de 'Em Aberto' para 'Enviando', e subsequentemente para 'Autorizado', 'Rejeitado' ou 'Denegado'), prevenindo movimentos inválidos e garantindo que o documento reflita a realidade fiscal.
*   **Gerenciamento de Eventos:** Arquitetura para suportar eventos fiscais vinculados ao documento, como Cancelamento, Carta de Correção Eletrônica (CC-e) e Inutilização de Numeração.
*   **Abstração de Protocolo:** Separa a lógica de negócios da lógica de comunicação. Módulos específicos (como `l10n_br_nfe` ou `l10n_br_nfse`) herdam deste módulo para implementar a comunicação com os webservices (SEFAZ/Prefeituras), enquanto o `l10n_br_fiscal_edi` orquestra o fluxo.
*   **Interface Padronizada:** Oferece uma experiência de usuário consistente com botões e ações uniformes, independentemente do modelo de documento fiscal (55, 65, 57, etc.).

Workflow de Estados
-------------------

O diagrama abaixo ilustra os possíveis estados e transições gerenciados pelo módulo:

.. image:: ../static/description/fsm_graph.png
   :alt: Diagrama da Máquina de Estados (FSM)
   :width: 100%
   :align: center
