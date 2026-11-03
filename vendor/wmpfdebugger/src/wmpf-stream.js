const readVarint = (buffer, offset) => {
    let value = 0;
    let multiplier = 1;
    for (let index = 0; index < 5; index += 1) {
        if (offset + index >= buffer.length) return null;
        const byte = buffer[offset + index];
        value += (byte & 0x7f) * multiplier;
        if ((byte & 0x80) === 0) {
            return { value, offset: offset + index + 1 };
        }
        multiplier *= 0x80;
    }
    return { invalid: true };
};

const readBytes = (buffer, offset) => {
    const length = readVarint(buffer, offset);
    if (!length || length.invalid) return length;
    const end = length.offset + length.value;
    if (end > buffer.length) return null;
    return { offset: end };
};

const parsePacket = (buffer) => {
    if (buffer.length === 0) return { partial: true };
    if (buffer[0] !== 8) return { invalid: true };

    let cursor = 1;
    const seq = readVarint(buffer, cursor);
    if (!seq) return { partial: true };
    if (seq.invalid) return seq;
    cursor = seq.offset;

    if (cursor >= buffer.length) return { partial: true };
    if (buffer[cursor] === 16) {
        const after = readVarint(buffer, cursor + 1);
        if (!after) return { partial: true };
        if (after.invalid) return after;
        cursor = after.offset;
        if (cursor >= buffer.length) return { partial: true };
    }

    if (buffer[cursor] !== 26) return { invalid: true };
    const category = readBytes(buffer, cursor + 1);
    if (!category) return { partial: true };
    if (category.invalid) return category;
    cursor = category.offset;

    if (cursor >= buffer.length) return { partial: true };
    if (buffer[cursor] !== 34) return { invalid: true };
    const data = readBytes(buffer, cursor + 1);
    if (!data) return { partial: true };
    if (data.invalid) return data;
    cursor = data.offset;

    if (cursor >= buffer.length) return { partial: true };
    if (buffer[cursor] !== 40) return { invalid: true };
    const compressAlgo = readVarint(buffer, cursor + 1);
    if (!compressAlgo) return { partial: true };
    if (compressAlgo.invalid) return compressAlgo;
    cursor = compressAlgo.offset;

    if (compressAlgo.value !== 0 && cursor >= buffer.length) return { partial: true };
    if (cursor < buffer.length && buffer[cursor] === 48) {
        const originalSize = readVarint(buffer, cursor + 1);
        if (!originalSize) return { partial: true };
        if (originalSize.invalid) return originalSize;
        cursor = originalSize.offset;
    }

    return { packetLength: cursor };
};

const createWmpfStreamParser = () => {
    let buffered = Buffer.alloc(0);

    return {
        push(chunk) {
            buffered = Buffer.concat([buffered, Buffer.from(chunk)]);
            const packets = [];

            while (buffered.length > 0) {
                const result = parsePacket(buffered);
                if (result.partial) break;
                if (result.invalid) {
                    const nextPacket = buffered.indexOf(8, 1);
                    buffered = nextPacket === -1 ? Buffer.alloc(0) : buffered.subarray(nextPacket);
                    continue;
                }

                packets.push(buffered.subarray(0, result.packetLength));
                buffered = buffered.subarray(result.packetLength);
            }

            return packets;
        },
    };
};

module.exports = {
    createWmpfStreamParser,
};
