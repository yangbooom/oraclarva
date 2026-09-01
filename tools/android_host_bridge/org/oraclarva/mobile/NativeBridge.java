package org.oraclarva.mobile;

final class NativeBridge {
    static {
        System.loadLibrary("oraclarva_android");
    }

    private NativeBridge() {}

    static native long nativeCreate(String repeatFixturePath, String spatialFixturePath);
    static native void nativeDestroy(long handle);
    static native void nativeReset(long handle);
    static native int nativeAdvance(
            long handle,
            double posteriorTouchIntensity,
            boolean lightEnabled,
            double originXM,
            double originYM,
            double originZM,
            double valueAtOriginWM2,
            double gradientXWM3,
            double gradientYWM3,
            double gradientZWM3,
            double temporalRateWM2S,
            double lowerBoundWM2,
            double upperBoundWM2,
            int steps);
    static native int[] nativeRenderCounts(long handle);
    static native int nativeReadFrame(
            long handle,
            double[] stateValues,
            float[] renderVertices,
            int[] renderIndices);
}
