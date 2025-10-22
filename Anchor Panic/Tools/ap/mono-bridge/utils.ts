export function readMonoString(ptr: NativePointer): string {
    try {
        if (ptr.isNull()) return "";
        const len = ptr.add(0x10).readS32();
        if (len <= 0 || len > 0x1000) return "";
        return ptr.add(0x14).readUtf16String(len) || "";
    } catch {
        return "";
    }
}