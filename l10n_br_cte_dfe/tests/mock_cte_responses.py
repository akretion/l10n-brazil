# Mock Responses for CT-e

_RES_CTE_XML = (
    '<resCTe xmlns="http://www.portalfiscal.inf.br/cte">'
    "<chCTe>35200159594315000157570010000000012062777161</chCTe>"
    "<CNPJ>59594315000157</CNPJ>"
    "<xNome>Test Emitter CTe</xNome>"
    "<dhEmi>2026-02-23T12:15:38-03:00</dhEmi>"
    "<vCarga>2500.00</vCarga>"
    "<cSitCTe>1</cSitCTe>"
    "</resCTe>"
)

_PROC_CTE_XML = (
    '<procCTe xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">'
    "<CTe><infCte>"
    "<ide><dhEmi>2026-02-23T12:15:38-03:00</dhEmi></ide>"
    "<emit><xNome>Test Emitter CTe Complete</xNome></emit>"
    "<vPrest><vTPrest>150.00</vTPrest></vPrest>"
    "</infCte></CTe>"
    "<protCTe><infProt>"
    "<chCTe>35200159594315000157570010000000012062777162</chCTe>"
    "</infProt></protCTe>"
    "</procCTe>"
)

# Used for success query
response_cte_success = """<?xml version="1.0" encoding="UTF-8"?><soap:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><cteDistDFeInteresseResponse xmlns="http://www.portalfiscal.inf.br/cte/wsdl/CTeDistribuicaoDFe"><cteDistDFeInteresseResult><retDistDFeInt xmlns="http://www.portalfiscal.inf.br/cte" versao="1.00"><cStat>138</cStat><xMotivo>Documento(s) localizado(s)</xMotivo><ultNSU>000000000000201</ultNSU><maxNSU>000000000000201</maxNSU><loteDistDFeInt><docZip NSU="000000000000200" schema="resCTe_v1.00.xsd">H4sIAAAAAAAEAIVS22qDQBD9FfFdd9Z7ZLKQphosqQ3mQuibMZto8RJcifn8rjG9PZUdZg7DOWeGYbHlIg65cqvKWvg3cZyqedddfEL6vtd7U2/aMzEAKNm/LtdZzqtU/SYX/5O1ohZdWmdcVa68FWkzVakO8PD4o780bZeWp0JkaakX9Uk/tKQ+cZVhlssVmUkNoPLZnjcAGKBtDwVMzzIodak3AIO6HpJRg/N49cL+apDcm3iLm4qz99lKWSSzMJrPlEAJnqPNWyJRlATLCMnIwShgUkqpNLEAHBOJ7OAxD6qCGWCARkEDZwPg30MDU2YkIwG7SxwyiuRe8SqTN3H1iXQZMB6L8y4t2W73sXdtJ+6TUDhGveaLbc9DsXyyt1NpNZLkzIRnh675PZZOfMP2LfNn7IOD9aptOkaHy5meDS44FnWRjG3M1kU3HEmu9gWRjP+BfQI6BY33GAIAAA==</docZip></loteDistDFeInt></retDistDFeInt></cteDistDFeInteresseResult></cteDistDFeInteresseResponse></soap:Body></soap:Envelope>"""
