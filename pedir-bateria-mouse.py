"""Teste: envia ao mouse K7 Ultra UM pedido de leitura (o mesmo que o M HUB faz:
feature report 0x11 com comando 0x06 = 'ler informacoes') e espera o pacote 13 1d.
Repete 3 vezes. Nada de escrita de configuracao."""
import sys, time
import hid

VID, PID = 0x5253, 0x1020
PEDIDO = bytes([0x11, 0xF9]) + bytes([0xFF]) * 19   # 21 bytes, igual ao capturado

alvo = next((d for d in hid.enumerate(VID, PID) if d["usage_page"] == 0xFF01), None)
if not alvo:
    sys.exit("Interface 0xff01 do mouse nao encontrada. Mouse ligado? M HUB fechado?")
h = hid.device()
h.open_path(alvo["path"]); h.set_nonblocking(True)

for tentativa in range(1, 4):
    # limpa o que estiver na fila
    while h.read(64):
        pass
    t0 = time.time()
    n = h.send_feature_report(PEDIDO)
    print(f"[{tentativa}] pedido enviado ({n} bytes), esperando resposta...")
    achou = False
    while time.time() - t0 < 8:
        d = h.read(64)
        if d:
            b = bytes(d); inv = bytes(255 - x for x in b)
            if b[:2] == b"\x13\x1d":
                print(f"   {time.time()-t0:.1f}s  carregando={inv[4]}  bateria={inv[5]}%  ({b[:8].hex()})")
                achou = True; break
            else:
                print(f"   {time.time()-t0:.1f}s  outro pacote {b[:6].hex()}")
        time.sleep(0.01)
    if not achou:
        print("   sem pacote de status em 8 s")
    time.sleep(3)
h.close()
