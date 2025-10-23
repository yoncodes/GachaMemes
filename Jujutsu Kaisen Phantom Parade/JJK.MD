## Tools
- GhostAssets - decrypts the asset files
- OctCrypto - decrypts the octocacheevai files
- SaveUtil - decrypts the excel files game uses

## Note
- these are only tested for global should work for jp as well

## Added
- key.js dumps SaveUtil keys. you have to change the offsets for your version
- JP (as of 2.8.1)
```bash
  Password: TRya5qdkwKJNpLFDmyjstVeh
  Key: XhJdhn6iCRWw
```
- Global (as of 2.7.2)
```bash
  Password: hogehoge
  Key: hogehoge
```

- a script to decrypt jp metadata (key changes per patch)


## Decrypt Metadata 
Step 1 find where global-metadata is loaded

```bash
    ?? ?? ?? ?? A0 ?? ?? F9 ?? ?? 00 B4 ?? ?? ?? ?? C0 ?? ?? F9
```

Step 2 Lets look for the decrypt function the game uses
(dont forget to change the offset)
```bash
  Run the frida script dump_metadata.js 
```