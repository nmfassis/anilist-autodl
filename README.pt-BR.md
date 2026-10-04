# anilist-autodl — Anime Downloader para Termux

[English](README.md) · **Português**

Baixa automaticamente os episódios das suas listas do AniList para o celular Android, prontos para assistir offline.
Você escolhe as fontes na instalação:

| Você escolhe | Motor | Fontes |
| --- | --- | --- |
| English | [ani-cli](https://github.com/pystardust/ani-cli) | inglês, legendado/dublado |
| Português | [ani-tupi](https://github.com/levyvix/ani-tupi) | português do Brasil (dublado/legendado) |

> O motor ani-tupi é novidade da versão 2.0. Foi feito com base no código do ani-tupi e testado com fontes simuladas;
> abra uma issue se alguma fonte se comportar mal no seu celular (anexe as linhas `[helper]` do `anilist-autodl logs`).

## O que faz

Verifica suas listas do AniList em intervalos (padrão: a cada hora, só no Wi-Fi):

- **Watching:** os próximos episódios não assistidos de animes em exibição (padrão: 1 adiantado), e até 3 adiantados para animes finalizados.
- **Planning:** ep. 1 dos animes planejados assim que começam a ser exibidos.
- **Dublado ou legendado:** sua versão preferida, com opção de usar a outra se faltar.
- **Limpeza:** episódios assistidos vão para uma pasta oculta `.trash` e são apagados de vez após 3 dias. Se você diminuir o
  progresso no AniList, o episódio da lixeira é restaurado em vez de baixado de novo.
- **Proteção de armazenamento:** pausa abaixo de 2 GB livres (a lixeira é esvaziada antes).
- **Verificações:** todo arquivo é conferido (tamanho, duração, título) antes de chegar à sua pasta de downloads.
- **Notificações:** download concluído, tempo esgotado, primeira falha de um episódio, pouco espaço. Em português ou inglês.
- **Atualização automática:** mantém o motor em dia. As atualizações do ani-tupi passam por um autoteste e são **revertidas**
  automaticamente se a nova versão deixar de funcionar com esta ferramenta.

## 1. Instalar

1. Instale o **Termux** e o **Termux:API** pelo [F-Droid](https://f-droid.org/packages/com.termux/) (ou GitHub). Os dois da
   mesma fonte, **não** pela Play Store.
2. Abra o Termux e rode o instalador direto do GitHub:

```
curl -fsSL https://raw.githubusercontent.com/nmfassis/anilist-autodl/main/install.sh | bash
```

3. Responda às perguntas. O modo *Rápido* só pergunta o idioma (que também escolhe as fontes), seu usuário do AniList e
   dublado/legendado. O modo *Personalizado* pergunta tudo, inclusive as fontes separadas do idioma:

| Pergunta | Padrão |
| --- | --- |
| Idioma / motor | English → ani-cli, Português → ani-tupi |
| Usuário do AniList | – |
| Dublado ou legendado (+ usar a outra versão se faltar) | legendado, com alternativa |
| Pasta de downloads | `/sdcard/Download/Anime` |
| Episódios adiantados: finalizados / em exibição | 3 / 1 |
| Baixar o ep. 1 dos animes planejados | sim |
| Verificar a cada | 1h (mínimo 15m, limite do Android) |
| Tentar de novo um episódio que falhou após | 6 h |
| Desistir de um download após | 60 min |
| Pausar abaixo de | 2 GB livres |
| Dias na lixeira | 3 |
| Só Wi-Fi / pular com bateria fraca | sim / sim |
| Atualização automática do motor / verificar a cada | sim / 7 dias |

4. Permita notificações para o Termux:API (Configurações do Android > Apps > Termux:API > Notificações).
5. Configurações do Android > Apps > **Termux** e **Termux:API** > Bateria > **Sem restrições**. Sem isso o Android pode encerrar downloads longos.

**Bom saber**

- O instalador começa com `pkg update && pkg upgrade`. Pode levar vários minutos e atualizar ferramentas do próprio Termux.
  Se ele parar ou o Termux reiniciar nessa etapa, **rode o mesmo comando de novo**: as respostas são salvas antes e ele continua.
- Com o ani-tupi, a primeira instalação compila o `pydantic-core` (5–15 min). Mantenha o Termux aberto; o instalador segura um wake lock.
- O ani-tupi exige Python 3.12 ou mais novo (o Termux atual já tem).
- Prefere um arquivo? `bash install.sh` a partir de um clone também funciona, e o antigo `install_anime_downloader.sh` continua funcionando.

### Instalação sem perguntas

```
curl -fsSL https://raw.githubusercontent.com/nmfassis/anilist-autodl/main/install.sh | bash -s -- \
  --yes --lang pt --username SEU_USUARIO --set AUDIO=dub --set AHEAD_FINISHED=5 --set INTERVAL_MINUTES=2h
```

`--lang en|pt`, `--engine ani-cli|ani-tupi`, `--username`, `--mode quick|custom`, `--set CHAVE=VALOR` (qualquer chave da
tabela abaixo), `--yes`, `--no-run`, `--reconfigure`, `--uninstall`.

## 2. Uso no dia a dia

```
anilist-autodl run        # verifica o AniList e baixa agora, com saída ao vivo
anilist-autodl status     # configurações, job agendado, versão do motor, últimas linhas do log
anilist-autodl logs       # acompanha o log (use "full" para a saída do yt-dlp/ffmpeg)
anilist-autodl update     # atualiza o motor agora
anilist-autodl retry      # esquece episódios que falharam para tentar de novo na próxima execução
anilist-autodl config     # muda qualquer configuração (refaz as perguntas)
anilist-autodl job        # roda uma vez pelo agendador do Android, como as execuções automáticas
```

## 3. Configurações

Ficam em `~/.config/anilist-autodl/config` (linhas `CHAVE='valor'`). Mude com `anilist-autodl config` ou edite o arquivo; a
próxima execução já usa. Depois de mudar `INTERVAL_MINUTES`, `WIFI_ONLY` ou `BATTERY_NOT_LOW`, use `anilist-autodl config`
para o agendamento ser registrado de novo.

| Chave | Padrão | Significado |
| --- | --- | --- |
| `AUTODL_LANG` | `en` | `en` ou `pt` (idioma das notificações) |
| `AUTODL_ENGINE` | pelo idioma | `ani-cli` ou `ani-tupi` |
| `ANILIST_USERNAME` | – | seu usuário do AniList |
| `AUDIO` / `AUDIO_FALLBACK` | `sub` / `true` | versão preferida; aceitar a outra se faltar |
| `DOWNLOAD_DIR` | `/sdcard/Download/Anime` | pasta final |
| `AHEAD_FINISHED` / `AHEAD_AIRING` | `3` / `1` | episódios adiantados (em exibição, limitado aos já lançados) |
| `DOWNLOAD_PLANNING` | `true` | ep. 1 dos planejados quando começam a ser exibidos |
| `INTERVAL_MINUTES` | `60` | agendamento (mínimo 15) |
| `RETRY_COOLDOWN_HOURS` | `6` | espera antes de tentar de novo um episódio que falhou |
| `TIMEOUT_MINUTES` | `60` | tempo máximo por tentativa de download |
| `MIN_FREE_GB` | `2` | pausar abaixo desse espaço livre |
| `TRASH_DAYS` | `3` | dias que episódios assistidos ficam na `.trash` |
| `WIFI_ONLY` / `BATTERY_NOT_LOW` | `true` / `true` | restrições do agendador |
| `AUTO_UPDATE` / `UPDATE_EVERY_DAYS` | `true` / `7` | atualizações do motor |

**Dublado/legendado no ani-tupi** depende da fonte: o título precisa conter *Dublado*/*Dub* para ser reconhecido. No ani-cli
é usada a opção `--dub`.

## 4. Arquivos

- `~/.anilist-autodl/` — os scripts (`fetch_anime.py`, `fetch_episode_tupi.py`, `run.sh`, `update.sh`, `install.sh`)
- `~/.config/anilist-autodl/config` — suas configurações
- `~/.anime_downloader.log` / `~/.anime_downloader_output.log` — log do script / saída completa
- `~/.anime_downloader_state.json` — histórico e horários de falhas
- `~/.anime_tmp/` — pasta temporária de download (esvaziada automaticamente)

## 5. Atualizando da versão 1.x

Rode o instalador de novo. Ele lê seu usuário e pasta antigos, move o `~/fetch_anime.py` e o `~/run_downloader.sh` antigos
para `*.bak` / `*.old`, mantém seu histórico e registra o job novamente.

## 6. Desinstalar

```
anilist-autodl uninstall
```

Seus episódios baixados não são tocados.

## 7. Solução de problemas

- **O instalador parou no `pkg upgrade`:** rode o mesmo comando de novo; suas respostas foram salvas.
- **Busca lenta no ani-tupi / `Jikan API timeout`:** não afeta esta ferramenta; o downloader desliga essa consulta.
- **Um episódio falha sempre:** ele é tentado de novo após o intervalo. `anilist-autodl logs full` mostra o motivo. No ani-tupi,
  as linhas `[helper]` dizem se o título não foi achado, o episódio ainda não saiu ou nenhum stream foi encontrado.
- **Uma versão nova do ani-tupi quebrou:** o atualizador testa e reverte, avisando uma vez. Veja `anilist-autodl status`.
- **ani-cli: "printf: Argument list too long":** o script já roda o ani-cli com o `sh` do Termux; se voltar, rode
  `termux-fix-shebang $PREFIX/bin/ani-cli`.
- **"Overwrite? [y/N]" ou "No such file" do ffmpeg:** confira se `~/.config/yt-dlp/config` não tem `--force-overwrite` nem
  `--no-m3u8-fixup` (o instalador remove) e se só uma cópia do job roda.
- **Marcou um episódio como assistido por engano:** ele fica 3 dias em `<pasta de downloads>/.trash`. Diminua o progresso no
  AniList e a próxima execução restaura, ou mova os arquivos de volta à mão.
- **Nada roda automaticamente:** `termux-job-scheduler --pending` deve listar o job 1. Se não listar, rode `anilist-autodl config`.
  Confira também a configuração de bateria do passo 1.5.
- **Sem notificações:** o Termux:API precisa estar instalado (mesma fonte do Termux) e com permissão para notificar.

## Aviso sobre IA

Este projeto foi **100% feito com IA**. Todo o código, scripts e documentação foram escritos por assistentes de IA (Google
Gemini nas primeiras versões, depois Claude, da Anthropic). Eu dirigi o trabalho por prompts e testei em um celular de verdade,
mas não escrevi nada à mão. Leia o código antes de rodar e use por sua conta e risco.

## Isenção de responsabilidade

Esta ferramenta não hospeda nem fornece conteúdo. Ela automatiza o ani-cli / ani-tupi, que buscam em fontes de terceiros.
Você é responsável por seguir as leis de direitos autorais e os termos de serviço que se aplicam a você. O software é
fornecido "como está", sem garantia de qualquer tipo. Sem vínculo com AniList, ani-cli ou ani-tupi.

## Créditos

- [ani-cli](https://github.com/pystardust/ani-cli) (GPL-3.0) e [ani-tupi](https://github.com/levyvix/ani-tupi), baixados na
  instalação, não redistribuídos aqui.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org), [Termux](https://termux.dev) e a
  [API do AniList](https://anilist.gitbook.io/anilist-apiv2-docs/).

## Licença

[MIT](LICENSE)
