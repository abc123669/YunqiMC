/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.server;

import static org.junit.jupiter.api.Assertions.*;

import io.papermc.paper.ServerBuildInfo;
import io.papermc.paper.ServerBuildInfoImpl;
import net.kyori.adventure.key.Key;
import net.minecraft.SharedConstants;
import org.junit.jupiter.api.Test;

class BrandingTest {
    @Test void preservesPaperCompatibilityWithoutClaimingItsIdentity() {
        SharedConstants.tryDetectVersion();
        final var info = new ServerBuildInfoImpl();
        assertEquals(Key.key("yunqimc", "yunqimc"), info.brandId());
        assertEquals("YunqiMC", info.brandName());
        assertTrue(info.isBrandCompatible(ServerBuildInfo.BRAND_PAPER_ID));
        assertTrue(info.isBrandCompatible(info.brandId()));
        assertFalse(info.isBrandCompatible(Key.key("papermc", "folia")));
        assertTrue(info.asString(ServerBuildInfo.StringRepresentation.VERSION_SIMPLE).startsWith("1.21.11-"));
    }
}
