import * as api from "./api";

function unityEngineCall(method: string): string | null {
    try {
        const domain = api.mono_get_root_domain();
        let coreModuleImage: NativePointer | null = null;
        
        // Look specifically for UnityEngine.CoreModule
        const callback = new NativeCallback((assembly: NativePointer) => {
            const img = api.mono_assembly_get_image(assembly);
            const nm = api.mono_image_get_name(img).readUtf8String();
            
            if (nm === "UnityEngine.CoreModule") {
                // /console.log(`[DEBUG] Found UnityEngine.CoreModule`);
                coreModuleImage = img;
            }
        }, "void", ["pointer", "pointer"]);

        api.mono_domain_assembly_foreach(domain, callback, ptr(0));
        
        if (!coreModuleImage) {
            //console.log("[DEBUG] UnityEngine.CoreModule not found");
            return null;
        }

        // Find Application class
        const ns = Memory.allocUtf8String("UnityEngine");
        const cn = Memory.allocUtf8String("Application");
        const appClass = api.mono_class_from_name(coreModuleImage, ns, cn);
        
        if (appClass.isNull()) {
            //console.log("[DEBUG] UnityEngine.Application class not found in CoreModule");
            return null;
        }
        //console.log("[DEBUG] Found UnityEngine.Application class in CoreModule");

        // Find the method
        const methodName = Memory.allocUtf8String(method);
        const methodHandle = api.mono_class_get_method_from_name(appClass, methodName, 0);
        
        if (methodHandle.isNull()) {
            //console.log(`[DEBUG] Method ${method} not found`);
            return null;
        }
       //console.log(`[DEBUG] Found method ${method}`);

        // For static methods, we need to pass NULL as the instance
        const nativeFunction = api.mono_compile_method(methodHandle);
        const result = new NativeFunction(nativeFunction, "pointer", ["pointer"])(ptr(0)); // NULL instance for static
        
        if (result.isNull()) {
            //console.log(`[DEBUG] Method ${method} returned null`);
            return null;
        }

        // Read Mono string result
        const len = result.add(0x10).readS32();
        if (len <= 0 || len > 0x1000) {
            //console.log(`[DEBUG] Invalid string length: ${len}`);
            return null;
        }
        const stringResult = result.add(0x14).readUtf16String(len) || null;
        //console.log(`[DEBUG] Method ${method} returned: ${stringResult}`);
        return stringResult;
        
    } catch (e) {
        console.log(`[DEBUG] Error calling ${method}: ${e}`);
        return null;
    }
}

export const application = {
    get dataPath(): string | null {
        return unityEngineCall("get_persistentDataPath");
    },

    get identifier(): string | null {
        return unityEngineCall("get_identifier");
    },

    get version(): string | null {
        return unityEngineCall("get_version");
    },

    get unityVersion(): string | null {
        try {
            const override = (globalThis as any).MONO_UNITY_VERSION;
            if (override) return override;
            
            return unityEngineCall("get_unityVersion");
        } catch (e) {
            return null;
        }
    }
};