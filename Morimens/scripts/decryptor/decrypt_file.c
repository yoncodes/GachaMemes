#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include "proto.h"
#include "header.h"
#include <math.h>
#include "../xlua/lua.h"
#include "../xlua/lauxlib.h"

// Normalize XLua/Morimens 0x30 format
static void normalize_morimens_chunk(unsigned char *buf, size_t *psize) {
    size_t size = *psize;
    if (size < 40) return;
    
    // Check signature + version + custom format
    if (buf[0] == 0x1B && buf[1] == 'L' && buf[2] == 'u' && buf[3] == 'a' &&
        buf[4] == 0x54 && buf[5] == 0x30)
    {
        // Remove 0x30 flags at [6],[7]
        memmove(buf + 6, buf + 8, size - 8);
        size -= 2;
        buf[5] = 0x00; // convert to standard format
        
        // Remove 128-byte signature block after header
        const size_t hdr = 31;  // standard lua54 header length
        if (size > hdr + 128) {
            memmove(buf + hdr, buf + hdr + 128, size - hdr - 128);
            size -= 128;
        }
        *psize = size;
    }
}

// Lua writer for lua_dump()
static int writer(lua_State *L, const void *p, size_t sz, void *ud) {
    (void)L;
    FILE *f = (FILE *)ud;
    fwrite(p, sz, 1, f);
    return 0;
}

bool has_custom_header_with_rsa(const uint8_t *data, size_t file_size) {
    if (file_size < 162) return false;
    
    // Validate Lua header
    if (memcmp(data, "\x1bLua\x54", 5) != 0) return false;
    
    // Check if byte 161 is a valid nupvalues value (0-20)
    // If yes → RSA block exists
    // If no → nupvalues is at byte 33 instead
    return (data[161] <= 20);
}


bool decrypt_file(const char *input_path, const char *output_path) {
    FILE *f = fopen(input_path, "rb");
    if (!f) {
        perror("fopen input");
        return false;
    }
    
    fseek(f, 0, SEEK_END);
    long file_size_raw = ftell(f);
    fseek(f, 0, SEEK_SET);
    
    if (file_size_raw <= 0) {
        fprintf(stderr, "Invalid file size\n");
        fclose(f);
        return false;
    }
    
    uint8_t *data = (uint8_t *)malloc((size_t)file_size_raw);
    if (!data) {
        fprintf(stderr, "malloc failed\n");
        fclose(f);
        return false;
    }
    
    fread(data, 1, (size_t)file_size_raw, f);
    fclose(f);
    
    printf("Input: %s (%ld bytes)\n", input_path, file_size_raw);
    
    size_t file_size = (size_t)file_size_raw;
    
    // Validate signature
    if (file_size < 7 || memcmp(data, "\x1bLua", 4) != 0) {
        fprintf(stderr, "Not a Lua chunk (bad signature)\n");
        free(data);
        return false;
    }
    
    // Detect header type
    bool has_rsa = has_custom_header_with_rsa(data, file_size);
    
    printf("  Header: flag1=0x%02X, flag2=0x%02X%s\n", 
           data[5], data[6], has_rsa ? ", has RSA block" : "");
    
    // Determine correct header size and offset
    size_t header_size;
    uint8_t encryption_flag = data[6];  // flag2
    
    if (has_rsa) {
        if (file_size < 162) {
            fprintf(stderr, "File too small for custom header\n");
            free(data);
            return false;
        }
        header_size = 161;
    } else {
        if (file_size < 34) {
            fprintf(stderr, "File too small for header\n");
            free(data);
            return false;
        }
        header_size = 33;
    }
    
    size_t offset = header_size;
    uint8_t nupvalues = data[offset++];

    // Only decrypt if encryption_flag is set
    if (encryption_flag != 0) {
        printf("  → Decrypting (flag=0x%02X)...\n", encryption_flag);
        
        size_t bytes_removed = decrypt_function(
            data,
            &offset,
            file_size,
            encryption_flag,
            0
        );
        
        file_size -= bytes_removed;
        data[6] = 0;  // Clear encryption flag
    } else {
        printf("  → File already decrypted, skipping decryption...\n");
    }

    // NORMALIZE: Convert custom format to standard Lua
    printf("  → Normalizing to standard format...\n");
    normalize_morimens_chunk(data, &file_size);

    // VALIDATE: Load into Lua VM and dump canonical form
    printf("  → Validating with Lua VM...\n");
    lua_State *L = luaL_newstate();
    if (!L) {
        fprintf(stderr, "Failed to create Lua state\n");
        free(data);
        return false;
    }

    if (luaL_loadbufferx(L, (const char*)data, file_size, input_path, "b") != LUA_OK) {
        fprintf(stderr, "Lua load error: %s\n", lua_tostring(L, -1));
        lua_close(L);
        free(data);
        return false;
    }

    free(data);

    // Dump canonical bytecode
    FILE *out = fopen(output_path, "wb");
    if (!out) {
        perror("fopen output");
        lua_close(L);
        return false;
    }

    lua_dump(L, writer, out, 0);
    fclose(out);
    lua_close(L);

    printf("✓ Output: %s\n", output_path);
    return true;
}