"""Diagnostico do controle GameSir: o que o dongle responde com e sem cabo.

1) Lista todos os aparelhos GameSir (VID 3537) que o Windows enxerga.
2) Envia ao dongle o MESMO pedido de leitura que o app usa (01 01 + zeros)
   e mostra a resposta 01 85 inteira. Nada de escrita de configuracao.

Rode duas vezes: uma com o controle SEM cabo e outra COM o cabo carregando.
Feche o GameSir Connect antes.
"""
import sys
import time

import hid

VID, PID_DONGLE = 0x3537, 0x1098
PEDIDO = bytes([0x01, 0x01]) + bytes(62)

print("== Aparelhos GameSir vistos pelo Windows ==")
vistos = hid.enumerate(VID, 0)
if not vistos:
    print("   nenhum")
for d in vistos:
    print(f"   PID={d['product_id']:04x} usage_page={d['usage_page']:04x} "
          f"usage={d['usage']:04x} produto={d.get('product_string')!r}")

alvo = next((d for d in hid.enumerate(VID, PID_DONGLE) if d["usage_page"] == 0xFF7A), None)
if not alvo:
    sys.exit("\nInterface 0xff7a do dongle nao encontrada.")

h = hid.device()
h.open_path(alvo["path"])
h.set_nonblocking(True)
print("\n== Resposta do dongle (3 tentativas) ==")
for tentativa in range(1, 4):
    while h.read(64):
        pass
    h.write(b"\x00" + PEDIDO)
    t0 = time.time()
    achou = False
    while time.time() - t0 < 3:
        d = h.read(64)
        if d and bytes(d[:2]) == b"\x01\x85":
            b = bytes(d)
            print(f"[{tentativa}] byte18(bateria)={b[18]}  bytes16..24={b[16:25].hex(' ')}")
            print(f"    completo: {b[:40].hex(' ')}")
            achou = True
            break
        time.sleep(0.01)
    if not achou:
        print(f"[{tentativa}] sem resposta 01 85 em 3 s")
    time.sleep(1)
h.close()
