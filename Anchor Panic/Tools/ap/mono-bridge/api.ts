// Module detection
const monoModule = Process.getModuleByName("mono-2.0-bdwgc.dll") ?? 
                   Process.getModuleByName("mono.dll") ?? 
                   Process.getModuleByName("libmono.so");

if (!monoModule) throw new Error("Mono module not found");

// Unity module detection
export const unityPlayerModule = Process.findModuleByName("UnityPlayer.dll");

export const mono_get_root_domain = new NativeFunction(monoModule.findExportByName("mono_get_root_domain")!, "pointer", []);
export const mono_thread_attach = new NativeFunction(monoModule.findExportByName("mono_thread_attach")!, "pointer", ["pointer"]);
export const mono_domain_assembly_foreach = new NativeFunction(monoModule.findExportByName("mono_domain_assembly_foreach")!, "void", ["pointer", "pointer", "pointer"]);
export const mono_assembly_get_image = new NativeFunction(monoModule.findExportByName("mono_assembly_get_image")!, "pointer", ["pointer"]);
export const mono_image_get_name = new NativeFunction(monoModule.findExportByName("mono_image_get_name")!, "pointer", ["pointer"]);
export const mono_class_from_name = new NativeFunction(monoModule.findExportByName("mono_class_from_name")!, "pointer", ["pointer", "pointer", "pointer"]);
export const mono_class_get_method_from_name = new NativeFunction(monoModule.findExportByName("mono_class_get_method_from_name")!, "pointer", ["pointer", "pointer", "int"]);
export const mono_compile_method = new NativeFunction(monoModule.findExportByName("mono_compile_method")!, "pointer", ["pointer"]);