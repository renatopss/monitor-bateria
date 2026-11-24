# Monitor de bateria na bandeja do Windows

Mostra na barra de tarefas a bateria dos meus periféricos sem fio — controle, mouse e headset — sem
precisar abrir três apps de fabricante diferentes. Lê **a cada 30 minutos** (configurável), dorme o resto
do tempo, não usa rede e não roda como administrador.

| Aparelho | Conexão | Como a bateria é lida |
|---|---|---|
| Controle GameSir Nova 2 | dongle 2.4G | pede `01 01` e lê o byte 18 da resposta `01 85` |
| Mouse Mchose K7 Ultra | receptor 2.4G | feature report `11 f9 ff…`, resposta `13 1d` invertida bit a bit |
| Headset Mchose V9 Pro | dongle 2.4G | relatório `55 65 01`, byte 2 da resposta `55 65` |

## O princípio

Todo periférico sem fio conversa com o PC por **HID** (o mesmo protocolo de teclado e mouse). Além das
interfaces "normais", os dongles expõem uma **interface de fabricante** (usage page `0xFF00`+) que o app
oficial usa para pedir coisas como a bateria. Nenhum fabricante documenta esse protocolo — mas o app
oficial *já sabe* falar com o aparelho. Então a ideia é simples:

1. **Observar** o que o app oficial manda e o que o aparelho devolve.
2. **Descobrir** qual pacote é o pedido de bateria e em que byte da resposta está o número.
3. **Repetir só esse pedido**, de forma isolada, num app leve que vive na bandeja.

Não há engenharia reversa de binário, driver ou firmware — só leitura do tráfego USB que já passa pelo cabo.

## O que eu aprendi: fazer tracking dos retornos na máquina

O coração deste projeto foi aprender a **rastrear o que os aparelhos respondem**, byte a byte, direto no PC.
O caminho que funcionou:

### 1. Enxergar o que existe
`ver-aparelhos-usb.py` só enumera (não abre nada) e lista VID/PID e as *usage pages* de cada aparelho.
Rodar com e sem o cabo plugado já mostra coisas importantes — o headset, por exemplo, **some do dongle**
quando entra em modo USB para carregar.

### 2. Capturar o app oficial
Com um sniffer USB, gravei o tráfego enquanto o GameSir Connect / M HUB mostravam a bateria.
Comparando as capturas com o número que o app exibia, aparece o padrão:

```
GameSir   → envia 01 01 00 00 …          ← recebe 01 85 … [byte 18 = 0x42] = 66 %
Mchose V9 → envia 55 65 01 00 …          ← recebe 55 65 64 02 …  (0x64 = 100 %)
Mchose K7 → envia 11 f9 ff ff …          ← recebe 13 1d …  (tudo invertido: 255 - valor)
```

O mouse foi o mais interessante: os dados vêm **invertidos bit a bit** (`0xF9` = `~0x06`, o comando
"ler informações"). Desinvertendo, o pacote vira `01 01 <carregando> <bateria> … "K7 Ultra"`.

### 3. Escutar passivamente
`escutar-headset.py` e `escutar-mouse.py` abrem as interfaces de fabricante **sem enviar nada** e imprimem
todo pacote que chega, com o tempo. Enquanto escutam, eu mexia no aparelho (volume, mudo, ligar/desligar,
plugar o cabo) e via qual pacote correspondia a cada ação. Foi assim que descobri que o receptor do mouse
**empurra sozinho** um `13 1d` quando o cabo é plugado — e daí veio o raio ⚡ de "carregando" em tempo real.

### 4. Pedir e conferir
`pedir-bateria-mouse.py`, `pedir-bateria-headset.py` e `diagnostico-controle.py` enviam **apenas** o pedido
de leitura capturado e mostram a resposta crua. Rodando várias vezes (com/sem cabo, bateria alta/baixa)
e comparando com o app oficial, confirmei cada offset — ex.: o K7 leu 93 % enquanto o M HUB, que arredonda,
mostrava 90 %.

### 5. Transformar em teste
Cada resposta real capturada virou uma **fixture** em `tests/fixtures/*.json` (válidas, inválidas e ruído).
Os parsers são testados contra esses bytes reais, sem precisar do aparelho plugado.

**Lições:** filtrar o ruído (o controle manda um fluxo contínuo de pacotes de estado que precisam ser
ignorados); limpar a fila antes de pedir, para não confundir resposta velha com nova; respeitar o tempo de
cada aparelho (o mouse demora ~2 s, às vezes 5 s); e nunca reenviar um comando que eu não entendo — o app
oficial também manda comandos que **alteram configuração**.

## Segurança

- **Só lê.** Cada plugin declara a lista exata de bytes que pode enviar e o `GuardedTransport` recusa
  qualquer outra escrita.
- Respostas são validadas (cabeçalho, tamanho, faixa 0–100) antes de virar número.
- Sem rede, sem `subprocess`, sem `eval/exec`, sem código dinâmico, sem administrador, sem telemetria —
  `tests/test_security_guards.py` verifica isso no código-fonte.
- Dependências mínimas e **fixadas com hash**: hidapi, Pillow, pystray (+ six).
- Um plugin com erro, travado ou devolvendo lixo não derruba os outros: cada leitura tem tempo limite.
- Acesso ao HID isolado em `transport.py`; os plugins não importam `hid`.

## Instalar e usar

### Pelo instalador (recomendado)
Baixe o `MonitorBateria-<versão>-setup.exe` em [Releases](https://github.com/renatopss/monitor-bateria/releases)
e execute. Não precisa de Python nem de administrador: instala só para o seu usuário, em
`%LOCALAPPDATA%\Programs\MonitorBateria`, com a opção de abrir junto com o Windows.

> O executável não é assinado digitalmente, então o SmartScreen pode avisar na primeira vez:
> "Mais informações" → "Executar assim mesmo".

Para gerar o instalador a partir do código: `powershell -ExecutionPolicy Bypass -File packaging\build.ps1`
(precisa de Python 3.10+ e do [Inno Setup 6](https://jrsoftware.org/isinfo.php)). Sai em `dist\`.

### Pelo código-fonte
1. Python 3.10+ (python.org, 64 bits).
2. `instalar.bat` cria um ambiente isolado e instala só o `requirements.txt`, recusando pacote com hash errado.
3. `ler-agora.bat` faz uma leitura única no terminal — bom para comparar com o app do fabricante.
4. `iniciar.bat` abre na bandeja. Para abrir com o Windows: `Win+R` → `shell:startup` → atalho para `iniciar.bat`.

> Feche o app do fabricante (GameSir Connect / M HUB) se ele estiver segurando o dongle.

### Interface
- **Bandeja**: um ícone por aparelho, só com o número, e um **contorno na cor do aparelho** para saber
  quem é quem — controle **cinza**, mouse **dourado e preto**, headset **vermelho e preto**. O miolo segue a
  cor da bateria e aparece ⚡ quando carregando. Botão direito: **Atualizar agora**, **Editar cores…**,
  **Widget flutuante**, **Sair**.
- **Widget flutuante** (opcional, desligado por padrão): liga/desliga pelo menu da bandeja, sem reiniciar.
  Mostra o desenho de cada aparelho e o percentual; arraste para posicionar.
- Cores: verde > 50 %, âmbar ≤ 50 %, vermelho ≤ 20 %, cinza sem leitura — todas editáveis.
- Aviso abaixo de 20 %, uma vez só, até a bateria subir 10 pontos.

### Configuração
`%LOCALAPPDATA%\monitor-bateria\config.json` (criado na primeira execução):

```json
{"interval_minutes": 30, "low_battery_percent": 20,
 "devices": {"gamesir_nova2": true, "mchose_k7": true, "mchose_v9": true}}
```

- Intervalo aceito: 5 a 1440 min; valores inválidos voltam ao padrão.
- `"floating_widget": true` liga o widget flutuante (o mesmo que marcar no menu).
- `"borders"`: contorno de cada tipo, cores de fora para dentro (até 3; `[]` = sem contorno), ex.
  `{"controller": ["#9e9e9e"], "mouse": ["#d4af37", "#000000"], "headset": ["#e53935", "#000000"]}`.
  Também editável em **Editar cores…**.
- `"tray_mode": "unico"` usa um ícone só (menor bateria, sem contorno).
- Log em `monitor.log` (200 KB, sem dados dos aparelhos).

## Limitações
- Só no modo **dongle 2.4G**; Bluetooth e cabo usam outros caminhos.
- Controle desligado pode responder 0 % — aparece como "desconectado".
- Só o mouse informa "carregando". O headset sai do 2.4G ao plugar o cabo.

## Testes
`testar.bat` (ou `pytest`) roda ~200 testes sem nenhum aparelho conectado: parsers com payloads reais,
contrato de plugins, falhas simuladas, segurança e o cenário de novo dispositivo.

## Adicionar um aparelho
Veja [ADICIONAR_DISPOSITIVO.md](ADICIONAR_DISPOSITIVO.md): capture, crie a fixture, escreva o plugin, rode os testes.

## Estrutura
```
src/monitor_bateria/   models, transport (HID), devices/ (um plugin por aparelho), service (laço),
                       config, icon, tray, ui_widget, single_instance, __main__
tests/                 fixtures/ (capturas reais), snapshots/, fakes.py e os testes
*.py na raiz           ferramentas de investigação: enumerar, escutar e pedir bateria
```
