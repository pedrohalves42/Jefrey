# Padrões que vão dentro do instalador

Coloque aqui, **antes de gerar o instalador** (`packaging\build_exe.bat`), os arquivos abaixo. Na primeira abertura o Jefrey os copia
para a pasta de dados da pessoa (`%LOCALAPPDATA%\Jefrey\config`) e **nunca sobrescreve** o que ela já tiver.

| Arquivo | Para quê |
|---|---|
| `google_oauth.json` | Credenciais do app do Google (cliente "Aplicativo para computador"), para o botão "Entrar com o Google" funcionar sem configuração. Veja `docs/GOOGLE.md` |
| `update_url.txt` | Endereço https do `manifest.json` das atualizações |
| `update_public_key.txt` | Chave **pública** das atualizações (a privada nunca vai para o instalador) |

Estes arquivos **não vão para o Git** (ver `.gitignore`). O "client secret" de um app para computador não é um segredo forte
(o Google o trata como público), mas mantenha fora do repositório mesmo assim.
