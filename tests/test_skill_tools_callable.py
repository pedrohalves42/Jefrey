"""Uma ferramenta pode chamar outra da mesma skill (antes: "'StructuredTool' object is not callable", ex.: busca de e-mails)."""
import asyncio

from src.jefrey.skills import SkillBase, SkillMetadata, tool


class Demo(SkillBase):
    metadata = SkillMetadata(name="demo_chamavel", description="x")

    def initialize(self):
        return True

    def get_tools(self):
        return [self.base, self.busca]

    @tool(description="base")
    async def base(self, query: str = "", max_results: int = 5, user_id: str | None = None) -> list:
        return [{"q": query, "n": max_results, "u": user_id}]

    @tool(description="busca chama a base")
    async def busca(self, query: str, user_id: str | None = None) -> list:
        return await self.base(query=query, max_results=2, user_id=user_id)


def test_ferramenta_chama_outra_direto_e_o_modelo_continua_usando_ainvoke():
    d = Demo()
    assert asyncio.run(d.busca.ainvoke({"query": "oi", "user_id": "ana"})) == [{"q": "oi", "n": 2, "u": "ana"}]
    assert asyncio.run(d.base({"query": "x"})) == [{"q": "x", "n": 5, "u": None}]


def test_email_compacto_cabe_no_limite_do_resultado_da_ferramenta():
    import json

    from src.jefrey.core.tool_runtime import MAX_RESULT_CHARS
    from src.jefrey.skills.email import compact_message

    grande = {"snippet": "texto " * 200, "labelIds": ["INBOX", "UNREAD"]}
    cab = {"Subject": "Assunto " * 40, "From": "Fulano <fulano@exemplo.com>", "Date": "Tue, 6 Oct 2026 10:00:00 -0300 (BRT)", "To": "voce@x.com"}
    itens = [compact_message(f"id{i}", "t", cab, grande) for i in range(10)]
    assert len(json.dumps(itens, ensure_ascii=False)) < MAX_RESULT_CHARS
    assert itens[0]["unread"] is True and "to" not in itens[0] and len(itens[0]["snippet"]) <= 110
    assert compact_message("x", "t", {}, {"snippet": "", "labelIds": ["INBOX"]})["unread"] is False
