## Tools
- GhostAssets - decrypts the asset files
- OctCrypto - decrypts the octocacheevai files
- SaveUtil - decrypts the excel files game uses

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