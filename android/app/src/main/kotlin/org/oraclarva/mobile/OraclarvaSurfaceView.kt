package org.oraclarva.mobile

import android.content.Context
import android.opengl.GLSurfaceView

internal class OraclarvaSurfaceView(
    context: Context,
    repeatFixturePath: String,
    spatialFixturePath: String,
    telemetry: (String) -> Unit,
) : GLSurfaceView(context) {
    private val oraclarvaRenderer = OraclarvaRenderer(
        repeatFixturePath,
        spatialFixturePath,
        telemetry,
    )

    init {
        setEGLContextClientVersion(3)
        setPreserveEGLContextOnPause(false)
        setRenderer(oraclarvaRenderer)
        renderMode = RENDERMODE_CONTINUOUSLY
    }

    fun setPhysicalFieldGradients(lateralWM3: Double, verticalWM3: Double) {
        oraclarvaRenderer.setPhysicalFieldGradients(lateralWM3, verticalWM3)
    }

    fun pulsePosteriorContact() {
        queueEvent(oraclarvaRenderer::pulsePosteriorContact)
    }

    override fun onPause() {
        queueEvent(oraclarvaRenderer::release)
        super.onPause()
    }
}
