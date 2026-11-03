const test = require("node:test");
const assert = require("node:assert/strict");

const messageProto = require("../src/third-party/WARemoteDebugProtobuf.js");
const { createWmpfStreamParser } = require("../src/wmpf-stream");

const encodePacket = (seq, payload, options = {}) => {
    const message = {
        seq,
        category: "chromeDevtoolsResult",
        data: Buffer.from(payload),
        compressAlgo: options.compressAlgo || 0,
    };
    if (options.after !== undefined) message.after = options.after;
    if (options.originalSize !== undefined) message.originalSize = options.originalSize;
    return Buffer.from(
        messageProto.mmbizwxadevremote.WARemoteDebug_DebugMessage.encode(message).finish()
    );
};

const decodePacket = (packet) => {
    const decoded = messageProto.mmbizwxadevremote.WARemoteDebug_DebugMessage.decode(packet);
    return {
        seq: decoded.seq,
        after: decoded.after,
        payload: Buffer.from(decoded.data).toString(),
        originalSize: decoded.originalSize,
    };
};

test("passes through one complete packet", () => {
    const parser = createWmpfStreamParser();
    const packet = encodePacket(1, "{}");
    const packets = parser.push(packet);
    assert.equal(packets.length, 1);
    assert.deepEqual(decodePacket(packets[0]), {
        seq: 1,
        after: 0,
        payload: "{}",
        originalSize: 0,
    });
});

test("reassembles a packet split at every byte", () => {
    const parser = createWmpfStreamParser();
    const packet = encodePacket(108945, "{\"id\":214,\"result\":{}}", {
        after: 7,
        compressAlgo: 1,
        originalSize: 321,
    });
    let packets = [];
    for (const byte of packet) {
        packets = packets.concat(parser.push(Buffer.from([byte])));
    }
    assert.equal(packets.length, 1);
    assert.deepEqual(decodePacket(packets[0]), {
        seq: 108945,
        after: 7,
        payload: "{\"id\":214,\"result\":{}}",
        originalSize: 321,
    });
});

test("splits coalesced packets and preserves a trailing partial packet", () => {
    const parser = createWmpfStreamParser();
    const first = encodePacket(2, "first");
    const second = encodePacket(3, "second");
    const third = encodePacket(4, "third");
    const split = 5;
    const chunks = [
        Buffer.concat([first, second, third.subarray(0, split)]),
        third.subarray(split),
    ];

    assert.deepEqual(parser.push(chunks[0]).map(decodePacket).map((packet) => packet.payload), [
        "first",
        "second",
    ]);
    assert.deepEqual(parser.push(chunks[1]).map(decodePacket).map((packet) => packet.payload), [
        "third",
    ]);
});

test("resynchronizes at the next packet after invalid bytes", () => {
    const parser = createWmpfStreamParser();
    const packet = encodePacket(9, "valid");
    const packets = parser.push(Buffer.concat([Buffer.from([0xff, 0x01]), packet]));
    assert.equal(packets.length, 1);
    assert.equal(decodePacket(packets[0]).payload, "valid");
});
