package org.oraclarva.mobile

import java.io.Closeable

internal data class PhysicalLightField(
    val enabled: Boolean = true,
    val originXM: Double = 0.0,
    val originYM: Double = 0.0,
    val originZM: Double = 0.0,
    val valueAtOriginWM2: Double = 4.0,
    val gradientXWM3: Double = 0.0,
    val gradientYWM3: Double = 0.0,
    val gradientZWM3: Double = 0.0,
    val temporalRateWM2S: Double = 0.0,
    val lowerBoundWM2: Double = 0.0,
    val upperBoundWM2: Double = 20.0,
)

internal class NativeFrame(
    val state: DoubleArray,
    val vertices: FloatArray,
    val indices: IntArray,
) {
    val extensionAbi: Int get() = state[0].toInt()
    val stepIndex: Int get() = state[1].toInt()
    val timeS: Double get() = state[2]
    val displacementXUm: Double get() = state[3]
    val displacementYUm: Double get() = state[4]
    val displacementZUm: Double get() = state[5]
    val anatomicalForwardUm: Double get() = -displacementXUm
    val headingDeg: Double get() = state[6]
    val pitchDeg: Double get() = state[7]
    val releaseValidated: Boolean get() = state[8] != 0.0
    val spatialSpikeTotal: Long get() = state[9].toLong()

    fun channelActivation(index: Int): Double = state[26 + index]
}

internal class NativeOrganism(
    repeatFixturePath: String,
    spatialFixturePath: String,
) : Closeable {
    private val ownerThread = Thread.currentThread()
    private var handle = NativeBridge.nativeCreate(
        repeatFixturePath,
        spatialFixturePath,
    )
    private val counts = NativeBridge.nativeRenderCounts(handle)
    private val stateValues = DoubleArray(STATE_VALUE_COUNT)
    private val renderVertices = FloatArray(counts[0] * VERTEX_STRIDE)
    private val renderIndices = IntArray(counts[1] * 3)
    private val frame = NativeFrame(stateValues, renderVertices, renderIndices)

    init {
        require(counts.contentEquals(intArrayOf(302, 600))) {
            "native render topology drifted: ${counts.contentToString()}"
        }
        readFrame()
        require(frame.extensionAbi == 1) { "unexpected environment ABI" }
        require(!frame.releaseValidated) { "research core cannot be release validated" }
    }

    fun advance(
        field: PhysicalLightField,
        steps: Int,
        posteriorTouchIntensity: Double = 0.0,
    ) {
        checkThread()
        check(handle != 0L) { "native organism is closed" }
        NativeBridge.nativeAdvance(
            handle,
            posteriorTouchIntensity,
            field.enabled,
            field.originXM,
            field.originYM,
            field.originZM,
            field.valueAtOriginWM2,
            field.gradientXWM3,
            field.gradientYWM3,
            field.gradientZWM3,
            field.temporalRateWM2S,
            field.lowerBoundWM2,
            field.upperBoundWM2,
            steps,
        )
    }

    fun readFrame(): NativeFrame {
        checkThread()
        check(handle != 0L) { "native organism is closed" }
        NativeBridge.nativeReadFrame(
            handle,
            stateValues,
            renderVertices,
            renderIndices,
        )
        return frame
    }

    fun reset() {
        checkThread()
        check(handle != 0L) { "native organism is closed" }
        NativeBridge.nativeReset(handle)
        readFrame()
    }

    override fun close() {
        checkThread()
        if (handle != 0L) {
            NativeBridge.nativeDestroy(handle)
            handle = 0L
        }
    }

    private fun checkThread() {
        check(Thread.currentThread() === ownerThread) {
            "native organism must stay on its owning GL thread"
        }
    }

    companion object {
        const val STATE_VALUE_COUNT = 69
        const val VERTEX_STRIDE = 7
    }
}
