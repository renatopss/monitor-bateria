"""Teste: envia ao dongle do headset V9 Pro o MESMO pedido que o M HUB faz (55 65 01 + zeros)
e espera a resposta 55 65 <bateria> <estado>. Tenta dois formatos de escrita do Windows.
Nao envia nada alem desse pedido."""
import sys, time
import hid

VID, PID, PAGE = 0x291D, 0x385D, 0xFF90
PEDIDO = bytes([0x55, 0x65, 0x01]) + bytes(61)        # 64 bytes, igual ao capturado

alvo = next((d for d in hid.enumerate(VID, PID) if d["usage_page"] == PAGE), None)
if not alvo:
    sys.exit("Colecao 0xff90 do headset nao encontrada. Headset ligado e no 2.4G? M HUB fechado?")
h = hid.device()
h.open_path(alvo["path"]); h.set_nonblocking(True)

formatos = [("A: 64 bytes (0x55 como ID do relatorio)", PEDIDO),
            ("B: 0x00 + 64 bytes (sem ID)", b"\x00" + PEDIDO)]
for nome, dados in formatos:
    while h.read(512):
        pass
    try:
        n = h.write(dados)
    except OSError as e:
        print(f"{nome}: erro ao escrever: {e}")
        continue
    print(f"{nome}: write devolveu {n}")
    if n is None or n < 0:
        continue
    fim = time.time() + 3
    while time.time() < fim:
        d = h.read(512)
        if d:
            b = bytes(d)
            print(f"   resposta len={len(b)} {b[:8].hex()}")
            if b[:2] == b"\x55\x65":
                print(f"   >>> bateria={b[2]}%  estado={b[3]:#04x}")
                h.close(); sys.exit(0)
        time.sleep(0.01)
    print("   sem resposta em 3 s")
h.close()
