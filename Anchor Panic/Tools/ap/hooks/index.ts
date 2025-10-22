export interface HookConfig {
    namespace: string;
    className: string;
    methodName: string;
    paramCount: number;
    onEnter?: (args: InvocationArguments) => void;
    onLeave?: (retval: InvocationReturnValue) => void;
}

export function hookMethod(assembly: any, config: HookConfig): boolean {
    const klass = assembly.findClass(config.namespace, config.className);
    if (!klass) {
        console.log(`[!] ${config.namespace}.${config.className} not found`);
        return false;
    }
    console.log(`[+] Resolved ${config.namespace}.${config.className}`);

    const method = klass.findMethod(config.methodName, config.paramCount);
    if (!method) {
        console.log(`[!] ${config.methodName} method not found`);
        return false;
    }

    console.log(`[+] Hooking ${config.className}.${config.methodName}`);
    method.hook({
        onEnter: config.onEnter,
        onLeave: config.onLeave
    });
    
    return true;
}