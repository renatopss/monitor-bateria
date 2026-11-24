"""Lista o que o Windows enxerga do controle (VID 3537) e do headset (VID 291D).
Só enumera: nao abre nem escreve nada. Rode sem cabo e depois com cabo e compare."""
import hid

for nome, vid in (("Controle GameSir", 0x3537), ("Headset Mchose", 0x291D)):
    pids = sorted({d["product_id"] for d in hid.enumerate(vid, 0)})
    print(f"{nome} (VID {vid:04x}): PIDs = {[f'{p:04x}' for p in pids] or 'nenhum'}")
