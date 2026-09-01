package org.oraclarva.mobile;

import java.util.Locale;

public final class AndroidFrameDump {
    private static final int STATE_VALUE_COUNT = 69;
    private static final int VERTEX_STRIDE = 7;
    private static final int FRAME_COUNT = 51;
    private static final int STEPS_PER_FRAME = 90;

    private AndroidFrameDump() {}

    private static void advance(long handle, int steps, int contactSteps) {
        int contact = Math.min(contactSteps, steps);
        if (contact > 0) {
            NativeBridge.nativeAdvance(
                    handle, 1.0, true,
                    0.0, 0.0, 0.0, 4.0,
                    0.0, 6000.0, 0.0,
                    0.0, 0.0, 20.0, contact);
        }
        if (steps > contact) {
            NativeBridge.nativeAdvance(
                    handle, 0.0, true,
                    0.0, 0.0, 0.0, 4.0,
                    0.0, 6000.0, 0.0,
                    0.0, 0.0, 20.0, steps - contact);
        }
    }

    public static void main(String[] arguments) {
        if (arguments.length != 2) {
            throw new IllegalArgumentException("repeat and spatial fixture paths are required");
        }
        Locale.setDefault(Locale.US);
        long handle = NativeBridge.nativeCreate(arguments[0], arguments[1]);
        try {
            int[] counts = NativeBridge.nativeRenderCounts(handle);
            double[] state = new double[STATE_VALUE_COUNT];
            float[] vertices = new float[counts[0] * VERTEX_STRIDE];
            int[] indices = new int[counts[1] * 3];
            System.out.println("schema\tandroid_jni_frames_v1");
            System.out.printf("render\t%d\t%d\t%d%n", counts[0], counts[1], VERTEX_STRIDE);
            int contactSteps = 2;
            for (int frame = 0; frame < FRAME_COUNT; ++frame) {
                if (frame > 0) {
                    advance(handle, STEPS_PER_FRAME, contactSteps);
                    contactSteps = Math.max(0, contactSteps - STEPS_PER_FRAME);
                }
                NativeBridge.nativeReadFrame(handle, state, vertices, indices);
                System.out.printf(
                        "frame\t%d\t%.9f\t%.9f\t%.9f\t%.9f\t%.9f\t%.9f\t%.0f",
                        (int) state[1], state[2], state[3], state[4], state[5],
                        state[6], state[7], state[9]);
                for (float value : vertices) System.out.printf("\t%.9g", value);
                System.out.println();
            }
            System.out.print("indices");
            for (int value : indices) System.out.printf("\t%d", value);
            System.out.println();
            System.out.println("field\tgradient_y_w_m3\t6000\tdirect_behavior_command\tfalse");
            System.out.println("capture\thost_jni\tandroid_device\tfalse\trelease_validated\tfalse");
        } finally {
            NativeBridge.nativeDestroy(handle);
        }
    }
}
