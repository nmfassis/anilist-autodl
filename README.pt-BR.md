# anilist-autodl — Anime Downloader para Termux

[English](README.md) · **Português**

Baixa automaticamente os episódios das suas listas do AniList para o celular Android, prontos para assistir offline.
Você escolhe as fontes na instalação:

| Você escolhe | Motor principal | Reserva | Fontes |
| --- | --- | --- | --- |
| English | [ani-cli-rs](https://github.com/vorlie/ani-cli-rs) | [ani-cli](https://github.com/pystardust/ani-cli) | inglês, legendado/dublado; o ani-cli-rs embute as legendas no arquivo |
| Português | [ani-tupi](https://github.com/levyvix/ani-tupi) | nenhum | português do Brasil (dublado/legendado) |

No modo *Personalizado* dá para trocar o motor principal e o de reserva (qualquer um dos três, em qualquer ordem). O de reserva
entra sempre que o principal não entrega um arquivo válido: anime errado, sem áudio, não encontrado, provedor fora do ar, tempo esgotado.

> O ani-cli-rs e o ani-tupi são novidade aqui. Foram feitos com base na documentação / no código deles e testados com fontes
> simuladas, não com os sites de verdade. Se algo se comportar mal, rode `anilist-autodl doctor` e anexe a saída e as linhas
> `[helper]` / `ani-cli-rs` do `anilist-autodl logs` a uma issue.

## O que faz

Verifica suas listas do AniList em intervalos (padrão: a cada hora, só no Wi-Fi):

- **Watching:** os próximos episódios não assistidos de animes em exibição (padrão: 1 adiantado), e até 3 adiantados para animes finalizados.
- **Planning:** ep. 1 dos animes planejados assim que começam a ser exibidos.
- **Dublado ou legendado:** sua versão preferida, com opção de usar a outra se faltar.
- **Limpeza:** episódios assistidos vão para uma pasta oculta `.trash` e são apagados de vez após 3 dias. Animes que saem das listas Watching/Planning
  (**Completed**, Dropped, Paused) também são limpos: todo arquivo que esta ferramenta baixou para eles vai para a lixeira. Se você diminuir o progresso no AniList, o episódio da lixeira é
  restaurado em vez de baixado de novo.
- **Proteção de armazenamento:** pausa abaixo de 2 GB livres (a lixeira é esvaziada antes).
- **Verificações:** todo arquivo é conferido antes de chegar à sua pasta de downloads: tamanho, legível, duração, título e
  **uma faixa de áudio** (vídeo sem som, ou com áudio que acaba antes, é rejeitado e a próxima fonte é tentada). Isso
  aproveita a mesma chamada do `ffprobe` que já media a duração, então não custa nada a mais.
- **Legendas (ani-cli-rs):** ele baixa as faixas de legenda do provedor e, com o ffmpeg, embute no MP4. Se um arquivo legendado
  vier sem nenhuma, o outro catálogo do ani-cli-rs é tentado primeiro; se nenhum tiver legendas o arquivo é mantido mesmo assim
  (pode ter legenda queimada na imagem) e o log avisa. Legenda queimada não dá para detectar, só faixas de legenda.
- **Anime exato:** o ani-cli-rs recebe o anime pelo ID, escolhido com a mesma verificação rigorosa de título, em vez de "o
  primeiro resultado da busca".
- **Notificações:** download concluído, tempo esgotado, primeira falha de um episódio, pouco espaço. Em português ou inglês.
- **Atualização automática:** mantém os motores em dia. As atualizações do ani-tupi passam por um autoteste e são **revertidas**
  automaticamente se a nova versão deixar de funcionar com esta ferramenta. O ani-cli-rs só é recompilado quando o repositório
  muda, e a nova versão só substitui a instalada depois de passar por um autoteste (a antiga fica guardada como reserva).

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
| Idioma (também escolhe os motores) | English → ani-cli-rs + ani-cli de reserva, Português → ani-tupi |
| *Personalizado:* motor principal e de reserva | pelo idioma |
| *Personalizado:* tentar o outro catálogo do ani-cli-rs quando um arquivo legendado vier sem faixas de legenda | sim |
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
- O ani-cli-rs **não tem binário para Android**, então o instalador o compila a partir do código com Rust (5–15 min, até 4 jobs de
  compilação para o celular não ficar sem memória). Se a compilação falhar, o instalador segue com o motor de reserva como
  principal e avisa; rode de novo para tentar outra vez.
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
anilist-autodl update     # atualiza os motores agora
anilist-autodl doctor     # testa cada motor e mostra o que o ani-cli-rs realmente devolve
anilist-autodl check ARQ  # faixas de áudio/legenda de um vídeo e se ele seria aceito
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
| `AUTODL_ENGINE` | pelo idioma | motor principal: `ani-cli-rs`, `ani-cli` ou `ani-tupi` |
| `AUTODL_BACKUP_ENGINE` | `ani-cli` (inglês) / vazio | usado quando o principal falha; vazio = nenhum |
| `PREFER_SUBS` | `true` | ani-cli-rs: um arquivo `sub` sem faixas de legenda faz tentar o outro catálogo antes de aceitar |
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

- `~/.anilist-autodl/` — os scripts (`fetch_anime.py`, `fetch_episode_tupi.py`, `run.sh`, `update.sh`, `install.sh`) e o código
  do ani-cli-rs (`ani-cli-rs-src/`, compilado pelo instalador)
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
- **Um vídeo está sem som / o áudio acaba antes:** desde a 2.1 esses arquivos são rejeitados automaticamente e a próxima fonte é
  tentada (veja no log `no audio track`). Para inspecionar qualquer arquivo: `anilist-autodl check "/sdcard/Download/Anime/Anime Episode 3.mp4"`.
- **ani-cli-rs não acha nada ou `could not parse this output`:** rode `anilist-autodl doctor`. Ele mostra o que cada catálogo
  devolve. O leitor foi escrito a partir da documentação e aceita vários nomes de campo; se o seu for diferente, anexe a
  primeiras linhas que o `doctor` mostra a uma issue.
- **Um arquivo está sem legendas:** o log diz `NO subtitle tracks` quando o ani-cli-rs entregou um sem faixas. Esse arquivo pode ter
  legenda queimada na imagem, o que não dá para detectar. Arquivos do ani-cli ou do ani-tupi nunca são checados quanto a legendas.
- **A compilação do ani-cli-rs falha (sem memória):** feche outros apps e rode o instalador de novo, ou escolha o ani-cli como
  motor principal no modo *Personalizado*.
- **Baixou o anime errado (corrigido na 2.0.1):** apague esse arquivo da sua pasta de downloads. O episódio para o qual ele
  foi registrado será baixado de novo, agora com a verificação de título rigorosa. Se você avançou o progresso de um anime e
  arquivos de outro foram para a `.trash`, restaure-os de `<pasta de downloads>/.trash`.
- **Um episódio "falha" mesmo o anime existindo:** a linha do log `does not match any known title (...)` mostra quais nomes
  foram comparados. Se a fonte usa um nome muito diferente, adicione-o como sinônimo na página do anime no AniList.
- **Um anime completo ainda tem arquivos:** só são para a lixeira os arquivos que esta ferramenta baixou (ela guarda um
  registro de cada um), nunca arquivos que você colocou à mão, e arquivos de versões muito antigas não têm registro. Nada vai
  para a lixeira numa execução em que uma lista do AniList não carregou (veja `anilist-autodl logs`). Apague esses à mão.
- **Um anime pausado/abandonado foi para a lixeira:** é o esperado, animes que saem das listas Watching/Planning perdem os
  arquivos baixados após `TRASH_DAYS`. Volte-o para Watching nesse prazo e os episódios são restaurados da `.trash`.
- **Marcou um episódio como assistido por engano:** ele fica 3 dias em `<pasta de downloads>/.trash`. Diminua o progresso no
  AniList e a próxima execução restaura, ou mova os arquivos de volta à mão.
- **Nada roda automaticamente:** `termux-job-scheduler --pending` deve listar o job 1. Se não listar, rode `anilist-autodl config`.
  Confira também a configuração de bateria do passo 1.5.
- **Sem notificações:** o Termux:API precisa estar instalado (mesma fonte do Termux) e com permissão para notificar.

## Testes

`python3 -m unittest discover -s tests -v` (sem rede nem Termux) cobre a verificação de títulos.

## Aviso sobre IA

Este projeto foi **100% feito com IA**. Todo o código, scripts e documentação foram escritos por assistentes de IA (Google
Gemini nas primeiras versões, depois Claude, da Anthropic). Eu dirigi o trabalho por prompts e testei em um celular de verdade,
mas não escrevi nada à mão. Leia o código antes de rodar e use por sua conta e risco.

## Isenção de responsabilidade

Esta ferramenta não hospeda nem fornece conteúdo. Ela automatiza o ani-cli / ani-tupi, que buscam em fontes de terceiros.
Você é responsável por seguir as leis de direitos autorais e os termos de serviço que se aplicam a você. O software é
fornecido "como está", sem garantia de qualquer tipo. Sem vínculo com AniList, ani-cli ou ani-tupi.

## Créditos

- [ani-cli-rs](https://github.com/vorlie/ani-cli-rs), [ani-cli](https://github.com/pystardust/ani-cli) (GPL-3.0) e
  [ani-tupi](https://github.com/levyvix/ani-tupi), baixados ou compilados na instalação, não redistribuídos aqui.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org), [Termux](https://termux.dev) e a
  [API do AniList](https://anilist.gitbook.io/anilist-apiv2-docs/).

## Licença

[MIT](LICENSE)
