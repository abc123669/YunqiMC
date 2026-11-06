/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.server.network;

import dev.yunqimc.server.YunqiMC;
import io.netty.buffer.ByteBuf;
import io.netty.channel.Channel;
import io.netty.channel.ChannelDuplexHandler;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelPromise;
import io.netty.handler.flush.FlushConsolidationHandler;
import io.papermc.paper.network.ChannelInitializeListenerHolder;
import net.kyori.adventure.key.Key;

/** Observes existing Netty traffic without changing ownership or ordering. */
public final class NetworkInstrumentation {
    private NetworkInstrumentation() {}

    public static void register() {
        ChannelInitializeListenerHolder.addListener(Key.key("yunqimc", "network"), NetworkInstrumentation::install);
    }

    static void install(final Channel channel) {
        channel.pipeline().addFirst("yunqimc_bytes", new Bytes());
        channel.pipeline().addBefore("packet_handler", "yunqimc_packets", new Packets());
    }

    /** Called on the event loop as the outbound Minecraft protocol changes. */
    public static void protocolChanged(final Channel channel, final boolean play) {
        configureFlush(channel, play && YunqiMC.flushConsolidationEnabled(), YunqiMC.maxPendingFlushes());
    }

    static void configureFlush(final Channel channel, final boolean enabled, final int maxPending) {
        final String name = "yunqimc_flush";
        if (channel.pipeline().get(name) != null) channel.pipeline().remove(name);
        if (enabled) {
            final FlushConsolidationHandler handler = new FlushConsolidationHandler(maxPending, true);
            if (channel.pipeline().get("yunqimc_bytes") != null) channel.pipeline().addAfter("yunqimc_bytes", name, handler);
            else channel.pipeline().addFirst(name, handler);
        }
    }

    private static final class Bytes extends ChannelDuplexHandler {
        private long nonWritableSince;
        @Override public void channelActive(final ChannelHandlerContext ctx) throws Exception {
            YunqiMC.NETWORK.connectionOpened();
            super.channelActive(ctx);
        }
        @Override public void channelInactive(final ChannelHandlerContext ctx) throws Exception {
            if (this.nonWritableSince != 0) {
                YunqiMC.NETWORK.nonWritable(System.nanoTime() - this.nonWritableSince);
                this.nonWritableSince = 0;
            }
            YunqiMC.NETWORK.connectionClosed();
            super.channelInactive(ctx);
        }
        @Override public void channelWritabilityChanged(final ChannelHandlerContext ctx) throws Exception {
            final long now = System.nanoTime();
            if (!ctx.channel().isWritable() && this.nonWritableSince == 0) this.nonWritableSince = now;
            else if (ctx.channel().isWritable() && this.nonWritableSince != 0) {
                YunqiMC.NETWORK.nonWritable(now - this.nonWritableSince);
                this.nonWritableSince = 0;
            }
            super.channelWritabilityChanged(ctx);
        }
        @Override public void channelRead(final ChannelHandlerContext ctx, final Object msg) throws Exception {
            if (msg instanceof ByteBuf bytes) YunqiMC.NETWORK.bytesRead(bytes.readableBytes());
            super.channelRead(ctx, msg);
        }
        @Override public void write(final ChannelHandlerContext ctx, final Object msg, final ChannelPromise promise) throws Exception {
            if (msg instanceof ByteBuf bytes) YunqiMC.NETWORK.bytesWritten(bytes.readableBytes());
            super.write(ctx, msg, promise);
        }
        @Override public void flush(final ChannelHandlerContext ctx) throws Exception {
            YunqiMC.NETWORK.flushed();
            super.flush(ctx);
        }
    }

    private static final class Packets extends ChannelDuplexHandler {
        private long writeSequence;
        @Override public void channelRead(final ChannelHandlerContext ctx, final Object msg) throws Exception {
            if (msg instanceof net.minecraft.network.protocol.Packet<?>) YunqiMC.NETWORK.packetRead();
            super.channelRead(ctx, msg);
        }
        @Override public void write(final ChannelHandlerContext ctx, final Object msg, final ChannelPromise promise) throws Exception {
            ChannelPromise forwardedPromise = promise;
            if (msg instanceof net.minecraft.network.protocol.Packet<?>) {
                YunqiMC.NETWORK.packetWritten();
                final int sampleRate = YunqiMC.networkSampleRate();
                if (sampleRate > 0 && this.writeSequence++ % sampleRate == 0) {
                    final long started = System.nanoTime();
                    forwardedPromise = promise.unvoid();
                    forwardedPromise.addListener(future -> {
                        if (future.isSuccess()) YunqiMC.NETWORK.writeCompleted(System.nanoTime() - started);
                    });
                }
            }
            super.write(ctx, msg, forwardedPromise);
        }
    }
}
