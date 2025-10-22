function get_self_process_name() {
    var openPtr = Module.getExportByName('libc.so', 'open');
    var open = new NativeFunction(openPtr, 'int', ['pointer', 'int']);

    var readPtr = Module.getExportByName("libc.so", "read");
    var read = new NativeFunction(readPtr, "int", ["int", "pointer", "int"]);

    var closePtr = Module.getExportByName('libc.so', 'close');
    var close = new NativeFunction(closePtr, 'int', ['int']);

    var path = Memory.allocUtf8String("/proc/self/cmdline");
    var fd = open(path, 0);  // Open the file
    if (fd != -1) {
        var buffer = Memory.alloc(0x1000);  // Allocate a buffer to read into
        var result = read(fd, buffer, 0x1000);  // Read the content into the buffer
        close(fd);  // Close the file descriptor
        if (result > 0) {  // Only proceed if the read was successful
            //@ts-ignore
            return ptr(buffer).readCString();  // Return the command line as a string
        } else {
            return "Failed to read cmdline";
        }
    }
    return "Failed to open /proc/self/cmdline";
}


function dump_metadata() {
    const lib = Process.findModuleByName("libil2cpp.so");
    if (!lib) {
        console.error("[-] libil2cpp.so not found.");
        return;
    }

    const s_GlobalMetadata_offset = 0xB694F48; // update this as needed
    const s_GlobalMetadata_ptr = lib.base.add(s_GlobalMetadata_offset).readPointer();

    console.log("[+] s_GlobalMetadata pointer: " + s_GlobalMetadata_ptr);

    // Locate string literal region using metadata offsets
    const stringLiteralCount = s_GlobalMetadata_ptr.add(12).readU32();
    const stringLiteralInfoOffset = s_GlobalMetadata_ptr.add(8).readU32();
    const stringLiteralDataOffset = s_GlobalMetadata_ptr.add(16).readU32();

    const stringLiteralInfoSize = stringLiteralCount; // in bytes
    const info_size = stringLiteralCount >>> 3; // count = infoSize / 8 entries

    // Resolve where the string literal data lives
    const stringLiteralDataBase = s_GlobalMetadata_ptr.add(stringLiteralDataOffset);

    const stringsDataAddr = stringLiteralDataBase.add(
        s_GlobalMetadata_ptr.add(24).readU32()
    );

    // Find readable ranges
    const metaRange = Process.findRangeByAddress(s_GlobalMetadata_ptr);
    const stringRange = Process.findRangeByAddress(stringsDataAddr);

    if (!metaRange || !stringRange) {
        console.error("[-] Could not find metadata or string literal memory ranges");
        return;
    }

    //@ts-ignore
    const metaRegionSize = metaRange.size - s_GlobalMetadata_ptr.sub(metaRange.base);
    //@ts-ignore
    const stringDataRegionSize = stringRange.size - stringsDataAddr.sub(stringRange.base);

    // Patch metadata for full dump size
    s_GlobalMetadata_ptr.add(24).writeU32(metaRegionSize);

    // Decrypt string literals
    for (let i = 0; i < info_size; i++) {
        const length = s_GlobalMetadata_ptr.add(stringLiteralInfoOffset).add(i * 8).readU32();
        const offset = s_GlobalMetadata_ptr.add(stringLiteralInfoOffset).add(i * 8 + 4).readU32();

        const src = s_GlobalMetadata_ptr.add(stringLiteralDataOffset).add(offset);
        //@ts-ignore
        const raw = Memory.readByteArray(src, length);
        const arr = new Uint8Array(raw);
        const key = length ^ 0x2e;
        const decrypted = arr.map(b => b ^ key);
        //@ts-ignore
        Memory.writeByteArray(src, decrypted);
    }

    // Write to file
    const filePath = "/data/data/" + get_self_process_name() + "/global-metadata.dat";
    const f = new File(filePath, "wb");
    //@ts-ignore
    f.write(Memory.readByteArray(s_GlobalMetadata_ptr, metaRegionSize));
    //@ts-ignore
    f.write(Memory.readByteArray(stringsDataAddr, stringDataRegionSize));
    f.flush();
    f.close();

    console.log("[+] Dumped global-metadata.dat to: " + filePath);
}