"""Somente LEITURA: escuta as colecoes HID do dongle do headset Mchose V9 Pro por 180 s
e mostra todo pacote que chegar. Nao envia NADA ao dispositivo."""
import sys, time
import hid

VID, PID = 0x291D, 0x385D
DURACAO = 180

infos = list(hid.enumerate(VID, PID))
if not infos:
    sys.exit("Dongle do headset nao encontrado (VID 291D / PID 385D). Headset ligado? M HUB fechado?")
for d in infos:
    print("interface", d["interface_number"], "usage_page", hex(d["usage_page"]), "usage", d["usage"], d["product_string"])

devs = []
for d in infos:
    if d["usage_page"] >= 0xFF00:
        h = hid.device()
        try:
            h.open_path(d["path"]); h.set_nonblocking(True)
            devs.append([hex(d["usage_page"]), h])
            print("aberta:", hex(d["usage_page"]))
        except OSError as e:
            print("nao abriu", hex(d["usage_page"]), e)
if not devs:
    sys.exit("Nenhuma colecao vendor aberta.")

print(f"\nEscutando {DURACAO}s. Durante esse tempo faca, com intervalo de uns 10 s entre cada:")
print("  1) aumente e abaixe o volume   2) ative/desative o mudo do microfone")
print("  3) desligue e ligue o headset  4) plugue/desplugue o cabo de carga")
print("  5) troque o modo (ex.: ANC/equalizador), se tiver\n")
fim = time.time() + DURACAO
t0 = time.time()
vistos = {}
while time.time() < fim and devs:
    for item in list(devs):
        nome, h = item
        try:
            data = h.read(512)          # buffer grande: o Windows exige >= tamanho do relatorio
        except OSError as e:
            print(f"  ({nome}: sem leitura de entrada, ignorada: {e})")
            devs.remove(item)
            continue
        if data:
            b = bytes(data)
            vistos[b] = vistos.get(b, 0) + 1
            print(f"{time.time()-t0:6.1f}s {nome} len={len(b)} {b[:32].hex()}")
    time.sleep(0.01)
print(f"\nFim. {len(vistos)} pacotes diferentes. Colecoes que ainda estavam ativas: {[n for n, _ in devs]}")
