# NexusCorp — API de Gestão de Reembolsos

Primeira versão didática de uma API REST para registrar e analisar despesas corporativas. Usa FastAPI, SQLAlchemy e SQLite persistente.

## Requisitos

- Python 3.10 ou superior
- PowerShell (ou terminal equivalente)

## Instalação e execução no Windows

Na pasta do projeto, execute:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:JWT_SECRET_KEY = "substitua-por-uma-chave-aleatoria-longa"
python seed_demo.py
python -m uvicorn app.main:app --reload
```

A API ficará em `http://127.0.0.1:8000`. A documentação interativa OpenAPI fica em `http://127.0.0.1:8000/docs`; a alternativa ReDoc fica em `/redoc`. O banco persistente é salvo em `BD/reembolsos.db` dentro da pasta do projeto e permanece entre reinicializações. `DATABASE_URL` pode apontar para outro banco SQLAlchemy compatível.

> A chave JWT padrão existe apenas para facilitar o uso local. Configure uma chave própria antes de qualquer implantação. As contas e senhas de demonstração também são apenas para o ambiente didático.

## Contas para demonstração

`python seed_demo.py` cria os departamentos e estas contas se ainda não existirem:

| Perfil | E-mail | Senha | Departamento |
|---|---|---|---|
| Colaborador | `ana@nexuscorp.com` | `Ana123!` | Comercial |
| Colaborador | `bruno@nexuscorp.com` | `Bruno123!` | Tecnologia |
| Gestor | `patricia@nexuscorp.com` | `Patricia123!` | Comercial |
| Gestor | `marcos@nexuscorp.com` | `Marcos123!` | Tecnologia |
| Financeiro | `fernanda@nexuscorp.com` | `Fernanda123!` | Financeiro |

O login é `POST /auth/token` com formulário `username` (e-mail) e `password`. Use o token retornado como `Authorization: Bearer <token>`. No `/docs`, clique em **Authorize** para testar operações protegidas.

## Fluxo de uma solicitação

1. Colaborador autenticado cria uma solicitação em rascunho.
2. O solicitante envia o rascunho para análise do gestor.
3. Gestor do mesmo departamento aprova ou recusa; recusa exige justificativa.
4. Se aprovada pelo gestor, a solicitação passa ao financeiro.
5. Financeiro aprova ou recusa; depois da aprovação financeira, pode registrar o pagamento.
6. As decisões e o pagamento ficam no histórico com responsável, horário, etapa, resultado e observação.

## Testes e evidências

```powershell
python -m pytest -v
```

A suíte cobre os oito cenários descritos no enunciado, além de autenticação obrigatória, duplicidade, valores e datas inválidos e justificativa de recusa. Consulte `evidencias/pytest-v.txt` para a última saída completa e `docs/Documentacao_Tecnica.md` para contratos, regras e permissões. Para capturas de tela, rode o comando no terminal do VS Code e use `Win + Shift + S`.

## Arquivos principais

- `app/main.py`: rotas e transições do fluxo.
- `app/models.py`: entidades relacionais.
- `app/schemas.py`: contratos e validação de entrada/saída.
- `app/security.py`: hash de senha, emissão/verificação de token e autorização por perfil.
- `seed_demo.py`: criação local de departamentos e contas de demonstração.
- `tests/test_reembolsos.py`: cenários automatizados de homologação.
- `docs/Documentacao_Tecnica.md`: documentação da solução.
