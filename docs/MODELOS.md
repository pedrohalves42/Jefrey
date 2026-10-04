# Modelos locais: qual usar

Medido em um notebook comum (Intel i7 de 8ª geração, 16 GB de RAM, sem GPU dedicada), com o
sistema real do Jefrey (roteador de intenções + seleção de ferramentas + prompt do produto).
Os 12 casos testam: escolher a ferramenta certa (notas, hora, conta, clima), **não** usar ferramenta em
conversa comum, e responder em português. Veja o método em `evals/` e `src/jefrey/core/hardware.py`.

| Modelo | Tamanho | Acertos | Resposta (mediana) | Ferramentas |
|---|---|---|---|---|
| `qwen2.5:0.5b` | 0,4 GB | não medido no sistema real | rápida | nenhuma (erra fatos simples) |
| `qwen2.5:1.5b` | 1,0 GB | 10/12 | 1,8 s | básicas |
| **`qwen3:1.7b`** (padrão leve) | 1,4 GB | **11/12** | 2,3 s | básicas (hora, contas, notas) |
| `llama3.2:3b` | 2,0 GB | 11/12 | 4,9 s | completas |
| **`qwen2.5:3b`** (recomendado) | 1,9 GB | **12/12** | 4,3 s | completas |
| `qwen3.5:2b` | 2,7 GB | 12/12 | 14,7 s | completas, mas lento sem GPU |

## O que aprendemos

- **Oferecer ferramentas em toda mensagem piora os modelos pequenos**: o `llama3.2:3b` chamava
  ferramenta à toa (clima para "Oi") e o `qwen2.5:3b` ficava inseguro em perguntas de conhecimento
  geral. Por isso o Jefrey só oferece ferramentas quando a mensagem tem sinais de que precisa delas.
- **Pedidos triviais não dependem do modelo**: hora, contas e "o que eu anotei sobre X?" têm um atalho
  determinístico. Isso deixa um modelo de 1,7B confiável no básico e elimina alucinação de hora/conta.
- **Modelos de raciocínio** (`qwen3`, `qwen3.5`) ficam com o raciocínio desligado no chat; ligado, a resposta
  demora várias vezes mais.
- Sem GPU, modelos acima de ~3B ficam lentos. Para respostas mais fortes use um provedor de nuvem
  (Claude, ChatGPT) em Configurações.

## Como escolher

- Pouca memória livre (menos de ~3 GB): `qwen3:1.7b`.
- Memória confortável (3 GB ou mais): `qwen2.5:3b`, para usar todas as ferramentas.
- A tela **Configurações → Modelo de IA** mostra a memória livre e recomenda o maior modelo que cabe.

## Limitações destes números

12 casos e temperatura baixa: servem para ordenar modelos, não para provar qualidade absoluta. Os
tempos variam muito com a memória livre do computador (com pouca RAM livre, tudo fica 5 a 10 vezes mais lento).
