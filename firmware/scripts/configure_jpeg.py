"""Select TJpg_Decoder's documented fast Huffman tables in the local build copy."""

from pathlib import Path
import re

Import('env')

config = Path(env.subst('$PROJECT_LIBDEPS_DIR')) / env.subst('$PIOENV') / 'TJpg_Decoder/src/tjpgdcnf.h'
text = config.read_text()
for name, value in (('JD_FASTDECODE', 2), ('JD_TBLCLIP', 1)):
    text, count = re.subn(r'(?m)^(#define\s+' + name + r'\s+)\d+',
                          lambda match: match[1] + str(value), text)
    if count != 1:
        raise RuntimeError('Unexpected TJpg_Decoder configuration: ' + name)
if text != config.read_text():
    config.write_text(text)
print('JPEG: fast Huffman tables, workspace 9644 bytes')

