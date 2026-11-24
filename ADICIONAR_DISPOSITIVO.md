# Como entrar com a bateria do mouse ou do headset sem quebrar nada

Os três aparelhos atuais (controle, mouse K7 e headset V9) já têm plugin funcionando. Este roteiro vale para
qualquer aparelho novo (herde `UnsupportedDevice` como reserva até decifrar o protocolo):

1. **Fixture primeiro.** Crie `tests/fixtures/<device_id>.json` com payloads reais capturados:
   `valid` (hex + percent esperado, incluindo a leitura conferida com o app da marca),
   `invalid` (cabeçalho errado, valor acima de 100, pacote curto) e `noise` (pacotes que devem ser ignorados).
   Use `tests/fixtures/gamesir_nova2.json` como modelo.
2. **Promova o plugin:** em `devices/mchose_k7.py`, troque `UnsupportedDevice` por `BatteryDevice`,
   defina `CMD`, `allowed_writes = frozenset({CMD})`, `parse_response()` e `_read_percent()`
   (copie `gamesir_nova2.py`). Remova `is_stub`/`enabled_by_default=False` herdados.
3. **Rode `pytest`.** O contrato (`test_contract_all_devices.py`) passa a valer sozinho para o plugin:
   nunca levanta exceção, tem tempo limite, só escreve o que está na lista, fecha o aparelho,
   e **exige a fixture** do passo 1 (sem ela o teste falha).
4. **Teste de regressão do cenário:** `test_new_device_scenario.py` já prova que o controle lê igual
   com um plugin novo ao lado e que um plugin com bug é contido. Se mudar algo no serviço, ele avisa.
5. **Ligue no config:** `"mchose_k7": true` em `config.json`, rode `ler-agora.bat` e compare
   com o número do M HUB.
6. Se o texto da bandeja mudar de propósito, atualize `tests/snapshots/tooltip.txt`.

Regras de ouro: só comandos de **leitura**; nunca copie para a lista algo que o app da marca
envia sem entender o que faz (pode alterar configuração do aparelho).
