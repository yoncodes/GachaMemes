## Black Beacon

## Decrypt lua & Json 
- can be used to decrypt files like luagame.txt back to luac
```bash
python decrypt.py 
```
- Needs unluac to convert back use  [unluac_2025_10_19.jar](https://sourceforge.net/projects/unluac/files/Unstable/)

## Network protocol
- Game uses [Sproto](https://github.com/cloudwu/sproto)
- Basically protobuf but lua
- Made a few scripts to decode the spb.bytes file back to something readable

## Hybrid Clr
- Games hides a few dlls from a regular dump.
- You have to trace where it gets loaded and decrypt them
- Every game is different but lucky for us these are already in the asset files
- Point the script to the hotfix files and it will convert the bytes files back to dll.

```bash
python hotfix.py source output
```