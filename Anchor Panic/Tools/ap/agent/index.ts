import * as Mono from "../mono-bridge";
import * as Hooks from "../hooks";

function initHook(): void {
    Mono.domain.attach();

    console.log(`[INFO] Unity Version: ${Mono.application.unityVersion}`);

    const assembly = Mono.domain.findAssembly("Assembly-CSharp");
    if (!assembly) {
        console.log("[!] Assembly-CSharp not found");
        return;
    }
    console.log("[+] Found Assembly-CSharp");

    // Define and setup hooks here
    Hooks.hookMethod(assembly, {
        namespace: "Lylibs",
        className: "SocketConnector", 
        methodName: "Connect",
        paramCount: 4,
        onEnter(args) {
            try {
                const ip = Mono.readMonoString(args[1]);
                const port = args[2].toInt32();
                console.log(`[CONNECT] Target: ${ip}:${port}`);
            } catch (e) {
                console.log("[ERR] Connect hook:", e);
            }
        }
    });

    Hooks.hookMethod(assembly, {
        namespace: "Lylibs",
        className: "Protocol",
        methodName: "TryGetMsgFromDecoderBuffer", 
        paramCount: 2,
        onEnter: function(args) {
            this.msgPtr = args[1];
        },
        onLeave: function(retval) {
            if (retval.toInt32() === 1) {
                try {
                    const msgId = (this.msgPtr as NativePointer).readS32();
                    console.log(`[MSG] Extracted message ID: ${msgId}`);
                } catch (e) {
                    console.log("[ERR] TryGetMsgFromDecoderBuffer:", e);
                }
            }
        }
    });
}

console.log("[*] Script loaded");
setTimeout(initHook, 250);

