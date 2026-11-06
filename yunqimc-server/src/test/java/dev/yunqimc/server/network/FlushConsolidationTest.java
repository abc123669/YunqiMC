/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.server.network;

import static org.junit.jupiter.api.Assertions.*;

import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.channel.ChannelInboundHandlerAdapter;
import dev.yunqimc.server.YunqiMC;
import net.minecraft.network.protocol.common.ClientboundKeepAlivePacket;
import org.junit.jupiter.api.Test;

class FlushConsolidationTest {
    @Test void samplesVoidPromisesWithoutDroppingThePacket() {
        final EmbeddedChannel channel = new EmbeddedChannel();
        try {
            channel.pipeline().addLast("packet_handler", new ChannelInboundHandlerAdapter());
            NetworkInstrumentation.install(channel);
            final long before = YunqiMC.NETWORK.snapshot().writeCompletionSamples();
            channel.pipeline().write(new ClientboundKeepAlivePacket(43L), channel.voidPromise());
            channel.flushOutbound();
            channel.runPendingTasks();
            assertInstanceOf(ClientboundKeepAlivePacket.class, channel.readOutbound());
            assertEquals(1, YunqiMC.NETWORK.snapshot().writeCompletionSamples() - before);
        } finally { channel.finishAndReleaseAll(); }
    }

    @Test void recordsBoundedMetricsWithoutTakingOwnershipOfBuffers() {
        final EmbeddedChannel channel = new EmbeddedChannel();
        try {
            channel.pipeline().addLast("packet_handler", new ChannelInboundHandlerAdapter());
            NetworkInstrumentation.install(channel);
            final var before = YunqiMC.NETWORK.snapshot();
            assertTrue(channel.writeInbound(Unpooled.wrappedBuffer(new byte[] {1, 2})));
            final ByteBuf inbound = channel.readInbound();
            assertEquals(2, inbound.readableBytes());
            assertTrue(inbound.release());
            assertTrue(channel.writeOutbound(Unpooled.wrappedBuffer(new byte[] {3, 4, 5})));
            final ByteBuf outbound = channel.readOutbound();
            assertEquals(3, outbound.readableBytes());
            assertTrue(outbound.release());
            assertTrue(channel.writeOutbound(new ClientboundKeepAlivePacket(42L)));
            assertInstanceOf(ClientboundKeepAlivePacket.class, channel.readOutbound());
            channel.runPendingTasks();
            final var after = YunqiMC.NETWORK.snapshot();
            assertEquals(2, after.bytesRead() - before.bytesRead());
            assertEquals(3, after.bytesWritten() - before.bytesWritten());
            assertEquals(1, after.packetsWritten() - before.packetsWritten());
            assertEquals(1, after.writeCompletionSamples() - before.writeCompletionSamples());
        } finally { channel.finishAndReleaseAll(); }
    }

    @Test void preservesOrderAndPromisesAcrossScheduledFlush() {
        final EmbeddedChannel channel = new EmbeddedChannel();
        try {
            NetworkInstrumentation.configureFlush(channel, true, 256);
            final ByteBuf first = Unpooled.wrappedBuffer(new byte[] {1});
            final ByteBuf second = Unpooled.wrappedBuffer(new byte[] {2});
            final var a = channel.writeOneOutbound(first);
            final var b = channel.writeOneOutbound(second);
            channel.flushOutbound();
            channel.runPendingTasks();
            assertTrue(a.isSuccess());
            assertTrue(b.isSuccess());
            final ByteBuf x = channel.readOutbound();
            final ByteBuf y = channel.readOutbound();
            assertEquals(1, x.readUnsignedByte());
            assertEquals(2, y.readUnsignedByte());
            assertTrue(x.release());
            assertTrue(y.release());
        } finally { channel.finishAndReleaseAll(); }
    }

    @Test void removalAtProtocolBoundaryDrainsPendingFlush() {
        final EmbeddedChannel channel = new EmbeddedChannel();
        try {
            NetworkInstrumentation.configureFlush(channel, true, 256);
            final var result = channel.writeAndFlush(Unpooled.wrappedBuffer(new byte[] {7}));
            NetworkInstrumentation.configureFlush(channel, false, 256);
            channel.runPendingTasks();
            assertTrue(result.isSuccess());
            final ByteBuf actual = channel.readOutbound();
            assertEquals(7, actual.readUnsignedByte());
            assertTrue(actual.release());
            assertNull(channel.pipeline().get("yunqimc_flush"));
        } finally { channel.finishAndReleaseAll(); }
    }
}
