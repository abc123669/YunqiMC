/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.api;

/**
 * Immutable process-wide network counters since server startup.
 * Written bytes count data submitted to the transport, not delivery acknowledgements.
 * Write completion samples measure server-side pipeline completion, not client
 * receipt. Non-writable time is summed across connections. Concurrent updates
 * may be observed between individual counter reads.
 */
public record NetworkStats(
    long connectionsOpened,
    long connectionsClosed,
    long packetsRead,
    long packetsWritten,
    long bytesRead,
    long bytesWritten,
    long flushes,
    long nonWritableNanos,
    long writeCompletionSamples,
    long writeCompletionNanos,
    long maxWriteCompletionNanos
) {}
