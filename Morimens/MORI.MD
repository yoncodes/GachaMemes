## Morimens

- added a few scripts for the lua

- decrypts the lua files so unluac can decompile
```bash
.\morimendec <input file|folder> <output file|folder>
```

- fixes the strings and batches them with unluac
```bash
python batch.py <input folder> <output folder> --parallel 4/8
```

- custom unluac since opcodes were changed.

## Caution
- about 90 files fail in batch mode out of over 4k 
- those need to be run manually 