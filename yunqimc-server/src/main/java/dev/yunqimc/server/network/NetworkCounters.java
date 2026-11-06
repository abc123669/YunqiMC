/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.server.network;

import dev.yunqimc.api.NetworkStats;
import java.util.concurrent.atomic.LongAdder;
import java.util.concurrent.atomic.LongAccumulator;

/** Bounded, process-wide counters safe to update from network event loops. */
public final class NetworkCounters {
    private final LongAdder opened = new LongAdder();
    private final LongAdder closed = new LongAdder();
    private final LongAdder packetsRead = new LongAdder();
    private final LongAdder packetsWritten = new LongAdder();
    private final LongAdder bytesRead = new LongAdder();
    private final LongAdder bytesWritten = new LongAdder();
    private final LongAdder flushes = new LongAdder();
    private final LongAdder nonWritableNanos = new LongAdder();
    private final LongAdder writeCompletionSamples = new LongAdder();
    private final LongAdder writeCompletionNanos = new LongAdder();
    private final LongAccumulator maxWriteCompletionNanos = new LongAccumulator(Long::max, 0);

    public void connectionOpened() { this.opened.increment(); }
    public void connectionClosed() { this.closed.increment(); }
    public void packetRead() { this.packetsRead.increment(); }
    public void packetWritten() { this.packetsWritten.increment(); }
    public void bytesRead(final int count) { if (count > 0) this.bytesRead.add(count); }
    public void bytesWritten(final int count) { if (count > 0) this.bytesWritten.add(count); }
    public void flushed() { this.flushes.increment(); }
    public void nonWritable(final long nanos) { if (nanos > 0) this.nonWritableNanos.add(nanos); }
    public void writeCompleted(final long nanos) {
        if (nanos < 0) return;
        this.writeCompletionSamples.increment();
        this.writeCompletionNanos.add(nanos);
        this.maxWriteCompletionNanos.accumulate(nanos);
    }

    public NetworkStats snapshot() {
        return new NetworkStats(this.opened.sum(), this.closed.sum(), this.packetsRead.sum(),
            this.packetsWritten.sum(), this.bytesRead.sum(), this.bytesWritten.sum(), this.flushes.sum(),
            this.nonWritableNanos.sum(), this.writeCompletionSamples.sum(), this.writeCompletionNanos.sum(),
            this.maxWriteCompletionNanos.get());
    }
}
