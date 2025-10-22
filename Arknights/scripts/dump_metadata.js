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

(function() {
    var lib = Process.findModuleByName("libil2cpp.so");
    if (!lib) throw new Error("libil2cpp.so not found");
    var base = lib.base;
    console.log("[*] base:", base);

    // update as needed
    var sPtr = base.add(0x7893B50).readPointer(); //Metadata_offset
    console.log("[*] s_GlobalMetadata ptr:", sPtr);

    function u32(p) { return sPtr.add(p).readU32(); }
    function u64(p) { return sPtr.add(p).readU64(); }

    // header quick-info
    console.log("[*] version:", u32(4));
    console.log("[*] stringInfoOffset:", u32(8), " stringInfoCount(bytes):", u32(12));
    console.log("[*] stringDataOffset:", u32(16));
    console.log("[*] imagesOffset:", u32(0xAC), " imagesCountBytes:", u32(0xB0));
    console.log("[*] assembliesOffset:", u32(0xB4), " assembliesCountBytes:", u32(0xB8));

    // compute dump size by scanning header offset/count pairs
    var maxEnd = 0;
    var MAX_PAIRS = 128;
    for (var i = 0; i < MAX_PAIRS; i++) {
        var off = sPtr.add(8 + i*8 + 0).readU32();
        var cnt = sPtr.add(8 + i*8 + 4).readU32();
        if ((off|cnt) === 0) continue;
        // ignore obviously bogus
        if (off > 0x4000000 || cnt > 0x4000000) continue;
        var end = off + cnt;
        if (end > maxEnd) maxEnd = end;
    }

    if (maxEnd === 0) {
        console.warn("[!] header scan failed, falling back to 6MB");
        maxEnd = 6 * 1024 * 1024;
    }

    // ensure we cover string data region
    var sInfoOff = u32(8), sInfoCnt = u32(12), sDataOff = u32(16);
    var stringRegionEnd = 0;
    if (sInfoOff !== 0 && sInfoCnt !== 0 && sDataOff !== 0) {
        // iterate entries to find high end
        var entries = Math.floor(sInfoCnt / 8);
        for (var j = 0; j < entries; j++) {
            var len = sPtr.add(sInfoOff + j*8 + 0).readU32();
            var off = sPtr.add(sInfoOff + j*8 + 4).readU32();
            if ((len|off) === 0) continue;
            var e = sDataOff + off + len;
            if (e > stringRegionEnd) stringRegionEnd = e;
        }
    }
    if (stringRegionEnd > maxEnd) maxEnd = stringRegionEnd;

    console.log("[*] computed dump size:", maxEnd, "bytes (~", Math.ceil(maxEnd/1024), "KB )");

    // read the whole metadata area into ArrayBuffer
    var metaBytes = Memory.readByteArray(sPtr, maxEnd);
    if (!metaBytes) throw new Error("failed to read metadata region");

    // decrypt string literals into the array copy
    if (sInfoOff && sInfoCnt && sDataOff) {
        var entries = Math.floor(sInfoCnt / 8);
        var view = new Uint8Array(metaBytes);
        for (var k = 0; k < entries; k++) {
            var length = sPtr.add(sInfoOff + k*8 + 0).readU32();
            var offset = sPtr.add(sInfoOff + k*8 + 4).readU32();
            if (length === 0) continue;
            // bounds safety
            if (offset + length > view.length || offset > view.length) continue;
            var key = length ^ 0x2e;
            for (var b = 0; b < length; b++) {
                view[sDataOff + offset + b] = view[sDataOff + offset + b] ^ key;
            }
        }
    } else {
        console.warn("[!] no string info/data found in header - skipping decrypt");
    }

    // write to file

    var filePath = "/data/data/"+ get_self_process_name() +"/files/global-metadata.dat";
    try {
        var f = new File(filePath, "wb");
        f.write(metaBytes);
        f.flush();
        f.close();
        console.log("[+] wrote", filePath, "size", maxEnd);
    } catch (e) {
        console.error("write failed:", e);
    }
})();
