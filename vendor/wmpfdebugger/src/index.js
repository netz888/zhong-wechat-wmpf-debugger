const { promises: fs } = require("node:fs");
const { EventEmitter } = require("node:events");
const path = require("node:path");
const frida = require("frida");
const WebSocket = require("ws");
const { WebSocketServer } = WebSocket;

const { parse_cli_options } = require("./cli");
const { create_logger } = require("./logger");
const { closeOpenClients, createSessionCoordinator } = require("./session");
const {
    buildReplayMessages,
    isReplayableMethod,
    parseJsonMessage,
    recordReplayableMessage,
    shouldSwallowReplayResponse,
} = require("./cdp-session");
const { createPendingRequestStore } = require("./cdp-pending");
const {
    beginMiniappConnection,
    markReplayComplete,
    shouldReplayForProtocolEvent,
} = require("./replay-gate");
const { buildReconnectResetEvents } = require("./reconnect-events");
const { createNetworkSynthesizer } = require("./network-synth");
const { createWmpfStreamParser } = require("./wmpf-stream");

const codex = require("./third-party/RemoteDebugCodex.js");
const messageProto = require("./third-party/WARemoteDebugProtobuf.js");

class DebugMessageEmitter extends EventEmitter {}

const debugMessageEmitter = new DebugMessageEmitter();

const bufferToHexString = (buffer) =>
    Array.from(new Uint8Array(buffer))
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");

const IMPORTANT_MINIAPP_CATEGORIES = new Set([
    "setupContext",
    "addJsContext",
    "removeJsContext",
    "connectJsContext",
]);

const getActiveMiniappClient = (state) => {
    if (
        state.currentMiniappClient &&
        state.currentMiniappClient.readyState === WebSocket.OPEN
    ) {
        return state.currentMiniappClient;
    }

    const candidates = [...state.miniappClients].filter(
        (client) => client.readyState === WebSocket.OPEN
    );
    state.currentMiniappClient = candidates.length > 0 ? candidates[candidates.length - 1] : null;
    return state.currentMiniappClient;
};

const close_cdp_clients = (state, logger, reason) => {
    if (!state.cdpWss) {
        return 0;
    }

    const closed = closeOpenClients(state.cdpWss.clients, 1012, reason);
    if (closed > 0) {
        logger.main_debug(`[sync] ${reason}; closed ${closed} CDP client(s)`);
    }
    return closed;
};

const rejectPendingCdpRequests = (state, logger, reason) => {
    const rejected = state.pendingRequests.rejectAll(reason);
    for (const item of rejected) {
        debugMessageEmitter.emit("cdpmessage", item.payload);
    }
    if (rejected.length > 0) {
        logger.main_debug(
            `[sync] rejected ${rejected.length} pending CDP request(s): ${rejected
                .map((item) => item.method)
                .join(", ")}`
        );
    }
    return rejected.length;
};

const encodeCdpPayloadForMiniapp = (message, state, logger) => {
    const rawPayload = {
        jscontext_id: "",
        op_id: Math.round(100 * Math.random()),
        payload: typeof message === "string" ? message : message.toString(),
    };
    logger.main_debug(rawPayload);
    const wrappedData = codex.wrapDebugMessageData(rawPayload, "chromeDevtools", 0);
    const outData = {
        seq: ++state.messageCounter,
        category: "chromeDevtools",
        data: wrappedData.buffer,
        compressAlgo: 0,
        originalSize: wrappedData.originalSize,
    };
    return messageProto.mmbizwxadevremote.WARemoteDebug_DebugMessage.encode(outData).finish();
};

const sendCdpMessageToMiniapp = (message, state, logger) => {
    const client = getActiveMiniappClient(state);
    if (!client) {
        logger.main_debug("[sync] drop CDP message because no miniapp client is connected");
        return false;
    }

    const encodedData = encodeCdpPayloadForMiniapp(message, state, logger);
    client.send(encodedData, { binary: true });
    return true;
};

const replayBufferedCdpMessages = (state, logger) => {
    if (state.replayBuffer.size === 0) {
        return 0;
    }

    const client = getActiveMiniappClient(state);
    if (!client) {
        return 0;
    }

    const { replayIds, rawMessages } = buildReplayMessages(
        state.replayBuffer,
        () => ++state.replayInternalId
    );
    const replayMethods = [...state.replayBuffer.keys()];
    for (const replayId of replayIds) {
        state.pendingReplayResponseIds.add(replayId);
    }
    for (const rawMessage of rawMessages) {
        sendCdpMessageToMiniapp(rawMessage, state, logger);
    }
    logger.main_debug(`[sync] replayed ${rawMessages.length} buffered CDP initialization command(s)`);
    logger.main_debug(`[sync] replay methods: ${replayMethods.join(", ")}`);
    return rawMessages.length;
};

const emitReconnectResetEvents = (logger) => {
    const events = buildReconnectResetEvents();
    for (const event of events) {
        debugMessageEmitter.emit("cdpmessage", event);
    }
    logger.main_debug(`[sync] emitted ${events.length} synthetic CDP reset event(s)`);
};

const debug_server = (options, logger, state) => {
    const wss = new WebSocketServer({ port: options.debugPort });
    logger.info(`[server] debug server running on ws://localhost:${options.debugPort}`);
    logger.info("[server] debug server waiting for miniapp to connect...");

    const onMessage = (message) => {
        logger.main_debug(
            `[miniapp] client received raw message (hex): ${bufferToHexString(message)}`
        );
        let unwrappedData = null;
        try {
            const decodedData =
                messageProto.mmbizwxadevremote.WARemoteDebug_DebugMessage.decode(message);
            unwrappedData = codex.unwrapDebugMessageData(decodedData);
            logger.main_debug("[miniapp] [DEBUG] decoded data:");
            logger.main_debug(unwrappedData);
        } catch (error) {
            logger.error(`[miniapp] miniapp client err: ${error}`);
        }

        if (unwrappedData === null) {
            return;
        }

        if (IMPORTANT_MINIAPP_CATEGORIES.has(unwrappedData.category)) {
            logger.main_debug(
                `[miniapp] protocol event ${unwrappedData.category}: ${JSON.stringify(unwrappedData.data)}`
            );
        }
        if (!state.seenMiniappCategories.has(unwrappedData.category)) {
            state.seenMiniappCategories.add(unwrappedData.category);
            logger.main_debug(`[miniapp] first seen protocol category: ${unwrappedData.category}`);
        }

        if (shouldReplayForProtocolEvent(state, unwrappedData.category)) {
            logger.main_debug(
                `[sync] runtime ready via ${unwrappedData.category}; replaying buffered DevTools initialization`
            );
            replayBufferedCdpMessages(state, logger);
            emitReconnectResetEvents(logger);
            markReplayComplete(state);
        }

        if (unwrappedData.category === "chromeDevtoolsResult") {
            if (
                shouldSwallowReplayResponse(
                    unwrappedData.data.payload,
                    state.pendingReplayResponseIds
                )
            ) {
                logger.main_debug("[sync] swallowed internal replay response");
                return;
            }

            // Newer WMPF runtimes only emit Network.*ExtraInfo events; the
            // DevTools Network panel needs a primary requestWillBeSent to build
            // each row. Synthesize the missing events from the ExtraInfo data.
            try {
                const payload = parseJsonMessage(unwrappedData.data.payload);
                if (payload) {
                    const synthesized = state.networkSynth.onMiniappCdpMessage(payload);
                    for (const synthMessage of synthesized) {
                        debugMessageEmitter.emit("cdpmessage", synthMessage);
                    }
                }
            } catch (error) {
                logger.main_debug(`[sync] network synth error: ${error}`);
            }

            state.pendingRequests.resolve(unwrappedData.data.payload);
            debugMessageEmitter.emit("cdpmessage", unwrappedData.data.payload);
        }
    };

    wss.on("connection", (ws) => {
        const shouldWaitForReady = beginMiniappConnection(state);
        state.miniappClients.add(ws);
        state.currentMiniappClient = ws;
        state.sessionCoordinator.onMiniappConnected();
        state.hasSeenMiniappConnection = true;
        logger.info("[miniapp] miniapp client connected");

        if (shouldWaitForReady) {
            logger.main_debug(
                "[sync] miniapp runtime reconnected; waiting for protocol ready event before replaying DevTools initialization"
            );
        }

        const streamParser = createWmpfStreamParser();
        ws.on("message", (message) => {
            for (const packet of streamParser.push(message)) {
                onMessage(packet);
            }
        });
        ws.on("error", (error) => {
            logger.error("[miniapp] miniapp client err:", error);
        });
        ws.on("close", () => {
            state.miniappClients.delete(ws);
            if (state.currentMiniappClient === ws) {
                state.currentMiniappClient = null;
            }
            logger.info("[miniapp] miniapp client disconnected");
            rejectPendingCdpRequests(
                state,
                logger,
                "miniapp runtime disconnected before responding; retry after reconnect"
            );

            if (state.miniappClients.size === 0) {
                state.sessionCoordinator.onMiniappDisconnected();
            } else {
                logger.main_debug(
                    `[sync] one miniapp socket closed, ${state.miniappClients.size} socket(s) still active`
                );
            }
        });
    });

    debugMessageEmitter.on("proxymessage", (message) => {
        sendCdpMessageToMiniapp(message, state, logger);
    });
};

const proxy_server = (options, logger, state) => {
    const wss = new WebSocketServer({ port: options.cdpPort });
    state.cdpWss = wss;
    logger.info(`[server] proxy server running on ws://localhost:${options.cdpPort}`);
    logger.info(
        `[server] link: devtools://devtools/bundled/inspector.html?ws=127.0.0.1:${options.cdpPort}`
    );

    const onMessage = (message) => {
        const parsedMessage = parseJsonMessage(message);
        if (parsedMessage && parsedMessage.method) {
            const method = parsedMessage.method;
            const replayable = isReplayableMethod(method);
            if (!state.seenCdpMethods.has(method)) {
                state.seenCdpMethods.add(method);
                logger.main_debug(
                    `[cdp] first seen method: ${method} (${replayable ? "replayable" : "not replayable"})`
                );
            }
            if (!replayable && !state.seenNonReplayableCdpMethods.has(method)) {
                state.seenNonReplayableCdpMethods.add(method);
                logger.main_debug(`[cdp] non-replayable method observed: ${method}`);
            }
        }

        const pending = state.pendingRequests.add(message);
        if (pending) {
            logger.main_debug(
                `[cdp] pending request tracked: id=${pending.id}, method=${pending.method}, pending=${state.pendingRequests.size()}`
            );
        }

        const replayableMethod = recordReplayableMessage(state.replayBuffer, message);
        if (replayableMethod) {
            logger.main_debug(
                `[cdp] buffered replayable method: ${replayableMethod} (buffer size=${state.replayBuffer.size})`
            );
        }
        debugMessageEmitter.emit("proxymessage", message);
    };

    wss.on("connection", (ws) => {
        logger.info("[cdp] CDP client connected");
        ws.on("message", onMessage);
        ws.on("error", (error) => {
            logger.error("[cdp] CDP client err:", error);
        });
        ws.on("close", () => {
            logger.info("[cdp] CDP client disconnected");
        });
    });

    debugMessageEmitter.on("cdpmessage", (message) => {
        wss.clients.forEach((client) => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(message);
            }
        });
    });
};

const frida_server = async (options, logger) => {
    const localDevice = await frida.getLocalDevice();
    const processes = await localDevice.enumerateProcesses({
        scope: frida.Scope.Metadata,
    });
    const wmpfProcesses = processes.filter(
        (process) => process.name === "WeChatAppEx.exe"
    );
    const pidCounts = new Map();
    const knownWmpfPids = new Set(wmpfProcesses.map((process) => process.pid));
    for (const process of wmpfProcesses) {
        const parentPid = process.parameters.ppid ? Number(process.parameters.ppid) : 0;
        if (!knownWmpfPids.has(parentPid)) {
            continue;
        }
        pidCounts.set(parentPid, (pidCounts.get(parentPid) || 0) + 1);
    }

    let wmpfPid = options.pid;
    if (wmpfPid === null) {
        if (pidCounts.size > 0) {
            wmpfPid = [...pidCounts.entries()]
                .sort((left, right) => left[1] - right[1])
                .pop()[0];
        }
        if (wmpfPid === null && wmpfProcesses.length > 0) {
            const fallbackProcess = wmpfProcesses
                .filter((process) => process.parameters.path)
                .sort((left, right) => left.pid - right.pid)
                .pop();
            wmpfPid = fallbackProcess ? fallbackProcess.pid : null;
        }
    }
    if (wmpfPid === undefined || wmpfPid === null) {
        throw new Error("[frida] WeChatAppEx.exe process not found");
    }

    const wmpfProcess =
        processes.filter((process) => process.pid === wmpfPid)[0] || null;
    const wmpfProcessPath =
        wmpfProcess && wmpfProcess.parameters ? wmpfProcess.parameters.path : null;
    const wmpfVersionMatch = wmpfProcessPath ? wmpfProcessPath.match(/\d+/g) : null;
    const wmpfVersion =
        options.version || (wmpfVersionMatch ? Number(wmpfVersionMatch.pop()) : 0);
    if (wmpfVersion === 0) {
        throw new Error("[frida] error in find wmpf version");
    }

    const session = await localDevice.attach(Number(wmpfPid));
    const projectRoot = path.join(
        path.dirname(
            (require.main && require.main.filename) ||
                (process.mainModule && process.mainModule.filename) ||
                process.cwd()
        ),
        ".."
    );
    const scriptContent = (
        await fs.readFile(path.join(projectRoot, "frida", "hook.js"))
    ).toString();
    const configContent = JSON.stringify(
        JSON.parse(
            (
                await fs.readFile(
                    path.join(projectRoot, "frida", "config", `addresses.${wmpfVersion}.json`)
                )
            ).toString()
        )
    );

    const script = await session.createScript(
        scriptContent.replace("@@CONFIG@@", configContent)
    );
    script.message.connect((message) => {
        if (message.type === "error") {
            logger.error("[frida client]", message);
            return;
        }
        logger.frida_debug("[frida client]", message.payload);
    });
    await script.load();
    logger.info(`[frida] script loaded, WMPF version: ${wmpfVersion}, pid: ${wmpfPid}`);
    logger.info("[frida] you can now open any miniapps");
};

const main = async () => {
    const options = parse_cli_options();
    const logger = create_logger(options);
    const state = {
        cdpWss: null,
        currentMiniappClient: null,
        miniappClients: new Set(),
        sessionCoordinator: null,
        hasSeenMiniappConnection: false,
        messageCounter: 0,
        replayInternalId: 900000000,
        replayBuffer: new Map(),
        pendingReplayResponseIds: new Set(),
        pendingRequests: createPendingRequestStore(),
        seenCdpMethods: new Set(),
        seenMiniappCategories: new Set(),
        seenNonReplayableCdpMethods: new Set(),
        networkSynth: createNetworkSynthesizer(),
    };
    state.sessionCoordinator = createSessionCoordinator({
        logger,
        disconnectGraceMs: 1500,
        closeCdpClients: (reason) => close_cdp_clients(state, logger, reason),
    });
    debug_server(options, logger, state);
    proxy_server(options, logger, state);
    await frida_server(options, logger);
};

main().catch((error) => {
    console.error(error);
    process.exit(1);
});
