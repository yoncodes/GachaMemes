import * as api from "./api";

export const domain = {
    attach() {
        api.mono_thread_attach(api.mono_get_root_domain());
    },
    findAssembly(name: string) {
        let foundImage: NativePointer | null = null;
        
        const callback = new NativeCallback((assembly: NativePointer) => {
            const img = api.mono_assembly_get_image(assembly);
            const nm = api.mono_image_get_name(img).readUtf8String();
            if (nm && nm.indexOf(name) !== -1) {
                foundImage = img;
            }
        }, "void", ["pointer", "pointer"]);

        api.mono_domain_assembly_foreach(api.mono_get_root_domain(), callback, ptr(0));
        
        return foundImage ? {
            findClass(namespace: string, className: string) {
                const ns = Memory.allocUtf8String(namespace);
                const cn = Memory.allocUtf8String(className);
                const klass = api.mono_class_from_name(foundImage!, ns, cn);
                
                return klass.isNull() ? null : {
                    findMethod(methodName: string, paramCount: number) {
                        const mn = Memory.allocUtf8String(methodName);
                        const method = api.mono_class_get_method_from_name(klass, mn, paramCount);
                        
                        return method.isNull() ? null : {
                            hook(callbacks: InvocationListenerCallbacks) {
                                const fn = api.mono_compile_method(method);
                                return Interceptor.attach(fn, callbacks);
                            }
                        };
                    }
                };
            }
        } : null;
    }
};