"""Somente LEITURA: escuta o dongle do mouse Mchose K7 Ultra por 150 s e mostra
os pacotes 13 1d (onde achamos a bateria). Nao envia nada ao dispositivo."""
import sys, time
import hid

VID, PID = 0x5253, 0x1020
DURACAO = 150

infos = [d for d in hid.enumerate(VID, PID)]
for d in infos:
    print("interface", d["interface_number"], "usage_page", hex(d["usage_page"]), "usage", d["usage"])
alvos = [d for d in infos if d["usage_page"] >= 0xFF00]
if not alvos:
    sys.exit("Nao achei interface vendor do mouse (VID 5253 / PID 1020). Mouse ligado?")

devs = []
for d in alvos:
    h = hid.device()
    try:
        h.open_path(d["path"]); h.set_nonblocking(True)
        devs.append((hex(d["usage_page"]), h))
    except OSError as e:
        print("nao abriu", hex(d["usage_page"]), e)

print(f"Escutando {DURACAO}s... (plugue/desplugue o cabo de carga no meio, se quiser)")
fim = time.time() + DURACAO
t0 = time.time()
while time.time() < fim:
    for nome, h in devs:
        data = h.read(64)
        if data:
            b = bytes(data)
            inv = bytes(255 - x for x in b)
            tag = ""
            if b[:2] == b"\x13\x1d":
                tag = f"  <== status: carregando={inv[4]} bateria={inv[5]}%?"
            print(f"{time.time()-t0:6.1f}s {nome} {b[:12].hex()}{tag}")
    time.sleep(0.01)
