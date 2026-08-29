# Skill: Busca Web (Tavily / SerpAPI)

Você busca informações atuais na web quando o conhecimento do modelo não basta.

## Ferramentas Disponíveis
- `web_search` - Busca geral (query, max_results=5, search_depth="basic|advanced")
- `web_search_news` - Busca notícias recentes (query, max_results=5, days=7)
- `web_extract` - Extrai conteúdo de URLs específicas

## Quando Usar
- Fatos atuais (preços, clima, notícias, cotações)
- Pesquisa técnica (documentação, APIs, versões)
- Comparativos de produtos/serviços
- Verificação de fatos
- Informações locais (restaurantes, horários, endereços)

## Regras
- **Cite fontes** sempre: `[fonte: título - URL]`
- Prefira `search_depth: "advanced"` para pesquisas complexas
- Limite a 5 resultados por busca
- Se resultados forem ruins, refine a query e tente novamente
- Para notícias: use `web_search_news` com `days=7` padrão

## Formato de Resposta
```
**Resumo:** Resposta direta à pergunta

**Fontes:**
1. Título - URL
2. Título - URL
```

## Exemplos
- "qual o dólar hoje?" → web_search("cotação dólar hoje real brasileiro")
- "novidades Python 3.13" → web_search("Python 3.13 release notes features", depth=advanced)
- "melhores notebooks 2024 custo benefício" → web_search + web_extract top 3