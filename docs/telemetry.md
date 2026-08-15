# Telemetria

O TDN Protheus MCP não envia telemetria. A versão atual não contém cliente, endpoint, identificador persistente nem coleta de uso.

Se uma versão futura oferecer telemetria, ela deverá permanecer desativada por padrão e exigir consentimento local explícito. O único dado permitido será métrica agregada de operação; conteúdo TDN, consultas, prompts, URLs, caminhos, IPs, credenciais e identificadores de pessoa são proibidos.

A mudança exigirá versão minor, configuração reversível, documentação de retenção e teste que prove ausência de chamadas de rede sem consentimento.
