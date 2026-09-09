package org.oraclarva.mobile

import android.content.Context
import android.opengl.GLSurfaceView
import android.view.MotionEvent

internal class OraclarvaSurfaceView(
    context: Context,
    repeatFixturePath: String,
    spatialFixturePath: String,
    telemetry: (String) -> Unit,
    private val lightFieldTouch: (Float, Float) -> Unit,
) : GLSurfaceView(context) {
    private val oraclarvaRenderer = OraclarvaRenderer(
        context.applicationContext,
        repeatFixturePath,
        spatialFixturePath,
        telemetry,
    )

    init {
        setEGLContextClientVersion(3)
        setPreserveEGLContextOnPause(false)
        setRenderer(oraclarvaRenderer)
        renderMode = RENDERMODE_CONTINUOUSLY
        contentDescription = "Habitat simulation. Drag to move the physical light field."
        isFocusable = true
        setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN,
                MotionEvent.ACTION_MOVE,
                -> {
                    val normalizedX = (event.x / width.coerceAtLeast(1)).coerceIn(0f, 1f)
                    val normalizedY = (event.y / height.coerceAtLeast(1)).coerceIn(0f, 1f)
                    lightFieldTouch(normalizedX, normalizedY)
                    true
                }

                MotionEvent.ACTION_UP -> {
                    performClick()
                    true
                }

                else -> false
            }
        }
    }

    fun setPhysicalFieldGradients(lateralWM3: Double, verticalWM3: Double) {
        oraclarvaRenderer.setPhysicalFieldGradients(lateralWM3, verticalWM3)
    }

    fun pulsePosteriorContact() {
        queueEvent(oraclarvaRenderer::pulsePosteriorContact)
    }

    fun setSimulationPaused(paused: Boolean) {
        oraclarvaRenderer.setSimulationPaused(paused)
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    override fun onPause() {
        queueEvent(oraclarvaRenderer::release)
        super.onPause()
    }
}
