// Frida script to hook GhostCryptographyProcessor

console.log("[*] Starting Frida script - Waiting for libil2cpp.so...");

function hookGhostCrypto() {
    const baseAddress = Module.findBaseAddress("libil2cpp.so");
    
    if (!baseAddress) {
        console.log("[-] libil2cpp.so not found yet");
        return false;
    }
    
    console.log("[+] libil2cpp.so found at: " + baseAddress);
    
    // GhostCryptographyProcessor offsets
    const initialize_offset = 0x05672DFC;
    const encrypt_bytes_offset = 0x05672F84;
    const decrypt_bytes_offset = 0x056730C4;
    const generate_key_offset = 0x05672E84;
    
    const initialize_addr = baseAddress.add(initialize_offset);
    const encrypt_bytes_addr = baseAddress.add(encrypt_bytes_offset);
    const decrypt_bytes_addr = baseAddress.add(decrypt_bytes_offset);
    const generate_key_addr = baseAddress.add(generate_key_offset);
    
    console.log("[+] Hooks:");
    console.log("    Initialize: " + initialize_addr);
    console.log("    Encrypt: " + encrypt_bytes_addr);
    console.log("    Decrypt: " + decrypt_bytes_addr);
    console.log("    GenerateKey: " + generate_key_addr);
    
    // Helper to read byte array
    function readByteArray(arrayPtr) {
        if (!arrayPtr || arrayPtr.isNull()) return null;
        try {
            const length = arrayPtr.add(Process.pointerSize * 3).readU32();
            const arrayData = arrayPtr.add(Process.pointerSize * 4);
            return arrayData.readByteArray(length);
        } catch (e) {
            return null;
        }
    }
    
    // Helper to read char array
    function readCharArray(arrayPtr) {
        if (!arrayPtr || arrayPtr.isNull()) return null;
        try {
            const length = arrayPtr.add(Process.pointerSize * 3).readU32();
            const arrayData = arrayPtr.add(Process.pointerSize * 4);
            return arrayData.readUtf16String(length);
        } catch (e) {
            return null;
        }
    }
    
    // Helper to decrypt ObscuredString
    function decryptObscuredString(obscuredPtr) {
        if (!obscuredPtr || obscuredPtr.isNull()) return null;
        
        try {
            // Try to read hiddenChars field (offset 0x28)
            const hiddenCharsPtr = obscuredPtr.add(0x28).readPointer();
            if (hiddenCharsPtr && !hiddenCharsPtr.isNull()) {
                const hiddenChars = readCharArray(hiddenCharsPtr);
                
                // Try to read cryptoKey field (offset 0x20)
                const cryptoKeyPtr = obscuredPtr.add(0x20).readPointer();
                if (cryptoKeyPtr && !cryptoKeyPtr.isNull()) {
                    const cryptoKey = readCharArray(cryptoKeyPtr);
                    
                    if (hiddenChars && cryptoKey) {
                        // Decrypt: XOR each char with key
                        let decrypted = '';
                        for (let i = 0; i < hiddenChars.length; i++) {
                            const hiddenChar = hiddenChars.charCodeAt(i);
                            const keyChar = cryptoKey.charCodeAt(i % cryptoKey.length);
                            decrypted += String.fromCharCode(hiddenChar ^ keyChar);
                        }
                        return decrypted;
                    }
                }
            }
            
            // Fallback: try to read fakeValue (offset 0x30) if fakeValueActive
            const fakeValuePtr = obscuredPtr.add(0x30).readPointer();
            if (fakeValuePtr && !fakeValuePtr.isNull()) {
                const length = fakeValuePtr.add(Process.pointerSize * 2).readU32();
                const stringData = fakeValuePtr.add(Process.pointerSize * 2 + 4);
                return stringData.readUtf16String(length);
            }
            
        } catch (e) {
            console.log("    [!] Error decrypting ObscuredString: " + e);
        }
        
        return null;
    }
    
    // Hook Initialize
    Interceptor.attach(initialize_addr, {
        onEnter: function(args) {
            console.log("\n[*] Initialize called!");
            console.log("    this: " + args[0]);
            
            const password = decryptObscuredString(args[1]);
            const saltKey = decryptObscuredString(args[2]);
            
            console.log("    Password: " + (password || "<unable to decrypt>"));
            console.log("    SaltKey: " + (saltKey || "<unable to decrypt>"));
            
            this.thisPtr = args[0];
        },
        onLeave: function(retval) {
            // Read generated _k and _i fields
            try {
                const k_ptr = this.thisPtr.add(0x18).readPointer();
                const i_ptr = this.thisPtr.add(0x20).readPointer();
                
                if (k_ptr && !k_ptr.isNull()) {
                    const k_bytes = readByteArray(k_ptr);
                    if (k_bytes) {
                        const k_hex = Array.from(new Uint8Array(k_bytes))
                            .map(b => b.toString(16).padStart(2, '0'))
                            .join('');
                        console.log("    Key (_k): " + k_hex);
                    }
                }
                
                if (i_ptr && !i_ptr.isNull()) {
                    const i_bytes = readByteArray(i_ptr);
                    if (i_bytes) {
                        const i_hex = Array.from(new Uint8Array(i_bytes))
                            .map(b => b.toString(16).padStart(2, '0'))
                            .join('');
                        console.log("    IV (_i): " + i_hex);
                    }
                }
            } catch (e) {
                console.log("    [!] Error reading keys: " + e);
            }
            
            console.log("    [*] Initialize completed\n");
        }
    });
    
    // Hook GenerateKeyFromPassword
    Interceptor.attach(generate_key_addr, {
        onEnter: function(args) {
            console.log("\n[*] GenerateKeyFromPassword called!");
            
            const password = decryptObscuredString(args[1]);
            const saltKey = decryptObscuredString(args[2]);
            
            console.log("    Password: " + (password || "<unable to decrypt>"));
            console.log("    SaltKey: " + (saltKey || "<unable to decrypt>"));
            
            this.thisPtr = args[0];
        },
        onLeave: function(retval) {
            console.log("    [*] Key generation completed\n");
        }
    });
    
    // Hook Encrypt
    Interceptor.attach(encrypt_bytes_addr, {
        onEnter: function(args) {
            this.plaintext = readByteArray(args[1]);
            
            if (this.plaintext) {
                console.log("\n[ENCRYPT] Called");
                console.log("    Length: " + this.plaintext.byteLength + " bytes");
                console.log("    Plaintext:");
                console.log(hexdump(this.plaintext, { ansi: true, length: 128 }));
            }
        },
        onLeave: function(retval) {
            if (this.plaintext && retval && !retval.isNull()) {
                const ciphertext = readByteArray(retval);
                if (ciphertext) {
                    console.log("    Ciphertext:");
                    console.log(hexdump(ciphertext, { ansi: true, length: 128 }));
                }
            }
        }
    });
    
    // Hook Decrypt
    Interceptor.attach(decrypt_bytes_addr, {
        onEnter: function(args) {
            this.ciphertext = readByteArray(args[1]);
            
            if (this.ciphertext) {
                console.log("\n[DECRYPT] Called");
                console.log("    Length: " + this.ciphertext.byteLength + " bytes");
                console.log("    Ciphertext:");
                console.log(hexdump(this.ciphertext, { ansi: true, length: 128 }));
            }
        },
        onLeave: function(retval) {
            if (this.ciphertext && retval && !retval.isNull()) {
                const plaintext = readByteArray(retval);
                if (plaintext) {
                    console.log("    Plaintext:");
                    console.log(hexdump(plaintext, { ansi: true, length: 128 }));
                }
            }
        }
    });
    
    console.log("[+] All hooks installed!");
    console.log("="*60 + "\n");
    return true;
}

if (!hookGhostCrypto()) {
    const checkInterval = setInterval(function() {
        if (hookGhostCrypto()) {
            clearInterval(checkInterval);
        }
    }, 500);
}