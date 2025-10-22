export * from "./api";
export * from "./utils";
export * from "./domain";
export * from "./application";
export * from "./unity-version";

import * as UnityVersionModule from "./unity-version";

// Declare the global type first
declare global {
    var Mono: any;
}

// Then assign to globalThis
if (!globalThis.Mono) {
    globalThis.Mono = {};
}

globalThis.Mono.UnityVersion = UnityVersionModule;