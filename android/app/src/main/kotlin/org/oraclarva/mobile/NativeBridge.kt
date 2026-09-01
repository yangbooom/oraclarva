package org.oraclarva.mobile

internal class NativeBridge private constructor() {
    companion object {
        init {
            System.loadLibrary("oraclarva_android")
        }

        @JvmStatic
        external fun nativeCreate(
            repeatFixturePath: String,
            spatialFixturePath: String,
        ): Long

        @JvmStatic
        external fun nativeDestroy(handle: Long)

        @JvmStatic
        external fun nativeReset(handle: Long)

        @JvmStatic
        external fun nativeAdvance(
            handle: Long,
            posteriorTouchIntensity: Double,
            lightEnabled: Boolean,
            originXM: Double,
            originYM: Double,
            originZM: Double,
            valueAtOriginWM2: Double,
            gradientXWM3: Double,
            gradientYWM3: Double,
            gradientZWM3: Double,
            temporalRateWM2S: Double,
            lowerBoundWM2: Double,
            upperBoundWM2: Double,
            steps: Int,
        ): Int

        @JvmStatic
        external fun nativeRenderCounts(handle: Long): IntArray

        @JvmStatic
        external fun nativeReadFrame(
            handle: Long,
            stateValues: DoubleArray,
            renderVertices: FloatArray,
            renderIndices: IntArray,
        ): Int
    }
}
