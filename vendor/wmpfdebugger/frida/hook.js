const getMainModule = (version) => {
    if (version >= 13331) {
        return Process.findModuleByName("flue.dll");
    }
    return Process.findModuleByName("WeChatAppEx.exe");
};

const activeNativeCallbacks = [];

const patchCDPFilter = (base, config) => {
    // xref: SendToClientFilter OR devtools_message_filter_applet_webview.cc
    if (config.CastToJsonHookOffset) {
        const castToJson = new NativeFunction(
            base.add(config.CastToJsonHookOffset),
            "pointer",
            ["pointer", "pointer"]
        );
        const callback = new NativeCallback(function (thisPtr, jsonOut, cborInput) {
            castToJson(jsonOut, cborInput);
            return jsonOut;
        }, "pointer", ["pointer", "pointer", "pointer"]);
        activeNativeCallbacks.push(callback);
        Interceptor.replace(base.add(config.CDPFilterHookOffset), callback);
        return;
    }

    const offset = config.CDPFilterHookOffset;
    Interceptor.attach(base.add(offset), {
        onEnter(args) {
            this.inputValue = args[0];
        },
        onLeave(retval) {
            const inputValue = this.inputValue.readPointer();
            if (inputValue.isNull() || inputValue.add(8).isNull()) {
                // there's a chance the value could be null
                // return here to avoid crash
                return;
            }

            if (inputValue.add(8).readU32() == 6) {
                inputValue.add(8).writeU32(0x0);
            }
        },
    });
};

const safeReadPointer = (ptr) => {
    if (!ptr || ptr.isNull()) return null;
    try {
        const range = Process.findRangeByAddress(ptr);
        if (!range || !range.protection.includes('r')) return null;
        const result = ptr.readPointer();
        return result.isNull() ? null : result;
    } catch(e) {
        return null;
    }
};

const readPointerChain = (base, offsets) => {
    let current = base;
    for (const offset of offsets) {
        current = safeReadPointer(current.add(offset));
        if (!current) return null;
    }
    return current;
};

const hookModernMiniAppConfig = (a1, config) => {
    const offsets = config.MiniAppConfigStructOffsets;
    const launchConfig = readPointerChain(a1, offsets.LaunchConfigOffsets);
    if (!launchConfig) { send("[hook] launch config chain: null"); return; }

    const remoteDebugConfig = readPointerChain(launchConfig, offsets.RemoteDebugConfigOffsets);
    if (!remoteDebugConfig) { send("[hook] remote debug config chain: null"); return; }

    const scenePtr = remoteDebugConfig.add(offsets.SceneOffset);
    const sceneRange = Process.findRangeByAddress(scenePtr);
    if (!sceneRange || !sceneRange.protection.includes("r")) {
        send("[hook] scene config: unmapped");
        return;
    }

    const sceneValue = scenePtr.readInt();
    send(`[hook] scene: ${sceneValue}`);
    const sceneNumberArray = [
        1005, 1007, 1008, 1011, 1012, 1027, 1035, 1037, 1053, 1074, 1145, 1178,
        1256, 1260, 1302, 1308,
    ];
    if (sceneNumberArray.includes(sceneValue)) {
        send("[hook] hook scene condition -> 1101");
        scenePtr.writeInt(1101);
    } else if (sceneValue !== 1101) {
        return;
    }

    const websocketUrl = "ws://localhost:9421";
    const websocketUrlPtr = launchConfig.add(offsets.WebSocketURLStringOffset);
    const stringMarker = websocketUrlPtr.add(23).readS8();
    if (stringMarker < 0) {
        const dataPtr = safeReadPointer(websocketUrlPtr);
        if (dataPtr) {
            dataPtr.writeUtf8String(websocketUrl);
            websocketUrlPtr.add(8).writeU64(websocketUrl.length);
        }
    } else {
        websocketUrlPtr.writeUtf8String(websocketUrl);
        websocketUrlPtr.add(23).writeU8(websocketUrl.length);
    }
    send(`[hook] websocket url -> ${websocketUrl}`);

    const remoteDebugModePtr = remoteDebugConfig.add(offsets.RemoteDebugModeOffset);
    send(`[hook] remote debug mode: ${remoteDebugModePtr.readInt()} -> 1`);
    remoteDebugModePtr.writeInt(1);
};

const hookOnLoadScene = (a1, config) => {
    if (config.MiniAppConfigStructOffsets) {
        hookModernMiniAppConfig(a1, config);
        return;
    }

    const sceneOffsets = config.SceneOffsets;
    const baseOffset = typeof config.SceneBaseOffset === "number" ? config.SceneBaseOffset : 56;

    const ptr1 = safeReadPointer(a1.add(baseOffset));
    if (!ptr1) { send(`[hook] scene chain: null at this+${baseOffset}`); return; }

    const ptr2 = safeReadPointer(ptr1.add(sceneOffsets[0]));
    if (!ptr2) { send(`[hook] scene chain: null at ptr1+${sceneOffsets[0]}`); return; }

    const ptr3 = safeReadPointer(ptr2.add(8));
    if (!ptr3) { send(`[hook] scene chain: null at ptr2+8`); return; }

    const ptr4 = safeReadPointer(ptr3.add(sceneOffsets[1]));
    if (!ptr4) { send(`[hook] scene chain: null at ptr3+${sceneOffsets[1]}`); return; }

    const ptr5 = safeReadPointer(ptr4.add(16));
    if (!ptr5) { send(`[hook] scene chain: null at ptr4+16`); return; }

    const miniappScenePtr = ptr5.add(sceneOffsets[2]);
    const range = Process.findRangeByAddress(miniappScenePtr);
    if (!range || !range.protection.includes('r')) {
        send(`[hook] scene chain: unmapped at ptr5+${sceneOffsets[2]}`);
        return;
    }

    const sceneValue = miniappScenePtr.readInt();
    send(`[hook] scene: ${sceneValue}`);

    // 1000: from issue #83 <-- will crash the process
    // 1007: from issue #80
    // 1008: from issue #53
    // 1027: from issue #78
    // 1035: from issue #78
    // 1053: from issue #25
    // 1074: from issue #32
    // 1145: from search
    // 1178: from phone (issue #117)
    // 1256: from recent
    // 1260: from frequently used
    // 1302: from services
    // 1308: minigame?
    const sceneNumberArray = [
        1005, 1007, 1008, 1027, 1035, 1053, 1074, 1145, 1178, 1256, 1260, 1302,
        1308,
    ];
    if (!sceneNumberArray.includes(sceneValue)) {
        return;
    }
    send("[hook] hook scene condition -> 1101");
    miniappScenePtr.writeInt(1101);

    // TODO: customize debugging endpoint
    // const websocketServerStringPtr = passArgs.add(8).readPointer().add(520);
    // VERBOSE && console.log("[hook] hook websocket server, original: ", websocketServerStringPtr.readUtf8String());
    // websocketServerStringPtr.writeUtf8String("ws://127.0.0.1:8189/");
};

const patchOnLoadStart = (base, config) => {
    // xref: AppletIndexContainer::OnLoadStart
    Interceptor.attach(base.add(config.LoadStartHookOffset), {
        onEnter(args) {
            send(
                `[inteceptor] AppletIndexContainer::OnLoadStart onEnter, ` +
                    `indexContainer.this: ${this.context.rcx}`,
            );
            // write dl to 0x1
            if ((this.context.rdx & 0xff) !== 1) {
                this.context.rdx = (this.context.rdx & ~0xff) | 0x1;
            }
            // handle onLoad scene
            hookOnLoadScene(this.context.rcx, config);
        },
        onLeave(retval) {
            // do nothing
        },
    });
};

const parseConfig = () => {
    const rawConfig = `@@CONFIG@@`;
    if (rawConfig.includes("@@")) {
        // test addresses
        return {
            Version: 18955,
            LoadStartHookOffset: "0x25B52C0",
            CDPFilterHookOffset: "0x30248B0",
            SceneOffsets: [1408, 1344, 488],
        };
    }
    return JSON.parse(rawConfig);
};

const main = () => {
    const config = parseConfig();
    const mainModule = getMainModule(config.Version);
    patchOnLoadStart(mainModule.base, config);
    patchCDPFilter(mainModule.base, config);
};

main();
