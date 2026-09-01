package org.oraclarva.mobile;

import java.util.Arrays;
import java.util.Locale;

public final class AndroidHostHarness {
    private static final int STATE_VALUE_COUNT = 69;
    private static final int VERTEX_STRIDE = 7;

    private AndroidHostHarness() {}

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }

    private static void advance(long handle, double gradientY, double gradientZ, int steps) {
        int contactSteps = Math.min(2, steps);
        NativeBridge.nativeAdvance(
                handle, 1.0, true,
                0.0, 0.0, 0.0, 4.0,
                0.0, gradientY, gradientZ,
                0.0, 0.0, 20.0, contactSteps);
        int remainingSteps = steps - contactSteps;
        while (remainingSteps > 0) {
            int batchSteps = Math.min(1_000, remainingSteps);
            NativeBridge.nativeAdvance(
                    handle, 0.0, true,
                    0.0, 0.0, 0.0, 4.0,
                    0.0, gradientY, gradientZ,
                    0.0, 0.0, 20.0, batchSteps);
            remainingSteps -= batchSteps;
        }
    }

    public static void main(String[] arguments) {
        if (arguments.length != 2) {
            throw new IllegalArgumentException("repeat and spatial fixture paths are required");
        }
        long handle = NativeBridge.nativeCreate(arguments[0], arguments[1]);
        try {
            int[] counts = NativeBridge.nativeRenderCounts(handle);
            require(Arrays.equals(counts, new int[] {302, 600}), "render topology drifted");
            double[] state = new double[STATE_VALUE_COUNT];
            float[] vertices = new float[counts[0] * VERTEX_STRIDE];
            int[] indices = new int[counts[1] * 3];

            advance(handle, 0.0, 0.0, 14_600);
            int step = NativeBridge.nativeReadFrame(handle, state, vertices, indices);
            require(step == 14_600, "uniform step count drifted");
            require(state[0] == 1.0, "environment ABI drifted");
            require(state[8] == 0.0, "release validation boundary drifted");
            require(Math.abs(state[2] - 14.6) < 1e-12, "uniform time drifted");
            require(Math.abs(-state[3] - 467.53928512972095) < 1e-8, "forward path drifted");
            require(Math.abs(state[6]) < 1e-12, "uniform field produced yaw");
            for (int channel = 0; channel < 4; ++channel) {
                require(Math.abs(state[22 + channel] - 0.5) < 1e-12, "receptor symmetry drifted");
            }
            for (int index : indices) {
                require(0 <= index && index < counts[0], "render index is out of range");
            }
            double[] expectedState = state.clone();
            float[] expectedVertices = vertices.clone();
            int[] expectedIndices = indices.clone();

            NativeBridge.nativeReset(handle);
            advance(handle, 0.0, 0.0, 14_600);
            NativeBridge.nativeReadFrame(handle, state, vertices, indices);
            require(Arrays.equals(expectedState, state), "JNI reset state replay drifted");
            require(Arrays.equals(expectedVertices, vertices), "JNI reset mesh replay drifted");
            require(Arrays.equals(expectedIndices, indices), "JNI reset topology replay drifted");

            NativeBridge.nativeReset(handle);
            advance(handle, 6000.0, 0.0, 4_500);
            NativeBridge.nativeReadFrame(handle, state, vertices, indices);
            require(Math.abs(state[6] - -3.8310160300481635) < 2e-9, "lateral field yaw drifted");

            System.out.printf(
                    Locale.US,
                    "uniform\t%.12f\t%.12f\t%.12f\t%.0f%n",
                    expectedState[2], -expectedState[3], expectedState[6], expectedState[9]);
            System.out.printf(Locale.US, "lateral\t%.12f\t%.12f%n", state[6], state[4]);
            System.out.printf("render\t%d\t%d%n", counts[0], counts[1]);
            System.out.println("replay\texact");
            System.out.println("release_validated\tfalse");
        } finally {
            NativeBridge.nativeDestroy(handle);
        }
    }
}
