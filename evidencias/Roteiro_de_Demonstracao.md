# Roteiro para as evidências da demonstração

## Preparar a API

No terminal do VS Code, na pasta `CODING07`, configure uma chave local e inicie a API:

```powershell
$env:JWT_SECRET_KEY = "chave-local-de-demonstracao-troque-depois"
python seed_demo.py
python -m uvicorn app.main:app --reload
```

Abra `http://127.0.0.1:8000/docs`. Em cada troca de perfil, use **Authorize** e autentique com a conta correspondente. O login usa formulário, com e-mail no campo `username`.

## Evidência 1 — testes

Em um segundo terminal na pasta do projeto, rode `python -m pytest -v`. Tire uma captura mostrando o comando e os 13 testes `PASSED`. A saída integral também está guardada em `pytest-v.txt`.

## Evidência 2 — tentativa sem permissão

1. Entre como Ana (`ana@nexuscorp.com`, `Ana123!`) e crie uma solicitação.
2. Entre como Bruno (`bruno@nexuscorp.com`, `Bruno123!`) e crie outra solicitação. Anote o ID retornado para Bruno.
3. Entre novamente como Ana e consulte `GET /solicitacoes/{id-do-Bruno}`.
4. Registre a resposta **404**. Ela impede a consulta sem revelar os dados de Bruno.

Pode também demonstrar o cenário do gestor: crie e envie uma solicitação de Bruno; autenticada como Patrícia (`patricia@nexuscorp.com`, `Patricia123!`), tente analisá-la. A resposta deve ser **404**, pois Patrícia só é responsável pelo Comercial.

## Evidência 3 — fluxo completo

1. Autentique Ana e crie uma solicitação de despesa, depois use `POST /solicitacoes/{id}/enviar`.
2. Autentique Patrícia e use `POST /solicitacoes/{id}/analise-gestor` com `{"decision":"aprovar","note":"Despesa do departamento confirmada"}`.
3. Autentique Fernanda (`fernanda@nexuscorp.com`, `Fernanda123!`) e use `POST /solicitacoes/{id}/analise-financeira` com `{"decision":"aprovar","note":"Comprovante conferido"}`.
4. Ainda como Fernanda, use `POST /solicitacoes/{id}/pagamento`.
5. Consulte `GET /solicitacoes/{id}` e mostre o estado `paga` e os quatro eventos do histórico (submissão, gestor, financeiro e pagamento).

Salve as capturas na pasta `evidencias` com nomes como `01-testes.png`, `02-acesso-negado.png` e `03-fluxo-completo.png`. As senhas são contas locais de demonstração; não as reutilize em ambientes reais.
