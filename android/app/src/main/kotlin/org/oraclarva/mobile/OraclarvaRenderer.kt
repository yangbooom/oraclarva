package org.oraclarva.mobile

import android.opengl.GLES30
import android.opengl.GLSurfaceView
import android.opengl.Matrix
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.nio.IntBuffer
import java.util.Locale
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import kotlin.math.max
import kotlin.math.min

internal class OraclarvaRenderer(
    private val repeatFixturePath: String,
    private val spatialFixturePath: String,
    private val telemetry: (String) -> Unit,
) : GLSurfaceView.Renderer {
    @Volatile
    private var lateralGradientWM3 = 0.0

    @Volatile
    private var verticalGradientWM3 = 0.0

    private var organism: NativeOrganism? = null
    private var program = 0
    private var width = 1
    private var height = 1
    private var previousFrameNs = 0L
    private var accumulatorS = 0.0
    private var posteriorContactSteps = 2
    private var frameCounter = 0
    private var telemetryStartNs = 0L
    private val projection = FloatArray(16)
    private val view = FloatArray(16)
    private val model = FloatArray(16)
    private val viewModel = FloatArray(16)
    private val mvp = FloatArray(16)
    private var vertexBuffer: FloatBuffer? = null
    private var indexBuffer: IntBuffer? = null

    fun setPhysicalFieldGradients(lateralWM3: Double, verticalWM3: Double) {
        lateralGradientWM3 = lateralWM3.coerceIn(-6000.0, 6000.0)
        verticalGradientWM3 = verticalWM3.coerceIn(-6000.0, 6000.0)
    }

    fun pulsePosteriorContact() {
        posteriorContactSteps = 2
    }

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        GLES30.glClearColor(0.05f, 0.04f, 0.07f, 1.0f)
        GLES30.glEnable(GLES30.GL_DEPTH_TEST)
        GLES30.glEnable(GLES30.GL_BLEND)
        GLES30.glBlendFunc(GLES30.GL_SRC_ALPHA, GLES30.GL_ONE_MINUS_SRC_ALPHA)
        program = linkProgram(VERTEX_SHADER, FRAGMENT_SHADER)
        ensureOrganism()
        previousFrameNs = 0L
        accumulatorS = 0.0
        telemetryStartNs = System.nanoTime()
        frameCounter = 0
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        this.width = max(1, width)
        this.height = max(1, height)
        GLES30.glViewport(0, 0, this.width, this.height)
    }

    override fun onDrawFrame(gl: GL10?) {
        val native = ensureOrganism()
        val now = System.nanoTime()
        if (previousFrameNs == 0L) previousFrameNs = now
        val elapsedS = min(0.05, (now - previousFrameNs) * 1e-9)
        previousFrameNs = now
        accumulatorS += elapsedS
        val steps = min(MAX_STEPS_PER_FRAME, (accumulatorS / FIXED_DT_S).toInt())
        val field = PhysicalLightField(
            gradientYWM3 = lateralGradientWM3,
            gradientZWM3 = verticalGradientWM3,
        )
        if (steps > 0) {
            val contact = min(steps, posteriorContactSteps)
            if (contact > 0) {
                native.advance(field, contact, posteriorTouchIntensity = 1.0)
                posteriorContactSteps -= contact
            }
            if (steps > contact) native.advance(field, steps - contact)
            accumulatorS -= steps * FIXED_DT_S
        }
        val frame = native.readFrame()
        draw(frame)
        updateTelemetry(now, frame)
    }

    fun release() {
        organism?.close()
        organism = null
        vertexBuffer = null
        indexBuffer = null
        previousFrameNs = 0L
    }

    private fun ensureOrganism(): NativeOrganism {
        organism?.let { return it }
        val created = NativeOrganism(repeatFixturePath, spatialFixturePath)
        val frame = created.readFrame()
        vertexBuffer = ByteBuffer
            .allocateDirect(frame.vertices.size * Float.SIZE_BYTES)
            .order(ByteOrder.nativeOrder())
            .asFloatBuffer()
        indexBuffer = ByteBuffer
            .allocateDirect(frame.indices.size * Int.SIZE_BYTES)
            .order(ByteOrder.nativeOrder())
            .asIntBuffer()
        organism = created
        posteriorContactSteps = 2
        return created
    }

    private fun draw(frame: NativeFrame) {
        val lateralTint = (lateralGradientWM3 / 6000.0).toFloat()
        val verticalTint = (verticalGradientWM3 / 6000.0).toFloat()
        GLES30.glClearColor(
            0.045f + max(0f, -lateralTint) * 0.025f,
            0.035f + max(0f, verticalTint) * 0.025f,
            0.065f + max(0f, lateralTint) * 0.025f,
            1.0f,
        )
        GLES30.glClear(GLES30.GL_COLOR_BUFFER_BIT or GLES30.GL_DEPTH_BUFFER_BIT)

        var centerX = 0.0
        var centerY = 0.0
        var centerZ = 0.0
        for (node in 0 until 13) {
            centerX += frame.state[30 + node * 3]
            centerY += frame.state[31 + node * 3]
            centerZ += frame.state[32 + node * 3]
        }
        centerX /= 13.0
        centerY /= 13.0
        centerZ /= 13.0

        val vertices = vertexBuffer ?: return
        vertices.clear()
        for (offset in frame.vertices.indices step NativeOrganism.VERTEX_STRIDE) {
            vertices.put(((frame.vertices[offset] - centerX) * WORLD_SCALE).toFloat())
            vertices.put(((frame.vertices[offset + 1] - centerY) * WORLD_SCALE).toFloat())
            vertices.put(((frame.vertices[offset + 2] - centerZ) * WORLD_SCALE).toFloat())
            vertices.put(frame.vertices[offset + 3])
            vertices.put(frame.vertices[offset + 4])
            vertices.put(frame.vertices[offset + 5])
            vertices.put(frame.vertices[offset + 6])
        }
        vertices.position(0)
        val indices = indexBuffer ?: return
        indices.clear()
        indices.put(frame.indices)
        indices.position(0)

        val aspect = width.toFloat() / height.toFloat()
        Matrix.orthoM(projection, 0, -1.35f * aspect, 1.35f * aspect, -1.35f, 1.35f, 0.1f, 10f)
        Matrix.setLookAtM(view, 0, 0f, 2.8f, 1.7f, 0f, 0f, 0f, 0f, 0f, 1f)
        Matrix.setIdentityM(model, 0)
        Matrix.multiplyMM(viewModel, 0, view, 0, model, 0)
        Matrix.multiplyMM(mvp, 0, projection, 0, viewModel, 0)

        GLES30.glUseProgram(program)
        val mvpLocation = GLES30.glGetUniformLocation(program, "uMvp")
        GLES30.glUniformMatrix4fv(mvpLocation, 1, false, mvp, 0)
        vertices.position(0)
        GLES30.glEnableVertexAttribArray(0)
        GLES30.glVertexAttribPointer(0, 3, GLES30.GL_FLOAT, false, 28, vertices)
        vertices.position(3)
        GLES30.glEnableVertexAttribArray(1)
        GLES30.glVertexAttribPointer(1, 3, GLES30.GL_FLOAT, false, 28, vertices)
        vertices.position(6)
        GLES30.glEnableVertexAttribArray(2)
        GLES30.glVertexAttribPointer(2, 1, GLES30.GL_FLOAT, false, 28, vertices)
        indices.position(0)
        GLES30.glDrawElements(
            GLES30.GL_TRIANGLES,
            frame.indices.size,
            GLES30.GL_UNSIGNED_INT,
            indices,
        )
        GLES30.glDisableVertexAttribArray(0)
        GLES30.glDisableVertexAttribArray(1)
        GLES30.glDisableVertexAttribArray(2)
    }

    private fun updateTelemetry(now: Long, frame: NativeFrame) {
        frameCounter += 1
        val intervalS = (now - telemetryStartNs) * 1e-9
        if (intervalS < 0.25) return
        val fps = frameCounter / intervalS
        frameCounter = 0
        telemetryStartNs = now
        telemetry(
            String.format(
                Locale.US,
                "C++  t %.3f s   forward %.2f µm   yaw %+.2f°   pitch %+.2f°\n" +
                    "GL %.1f fps   spikes %d   release_validated=false",
                frame.timeS,
                frame.anatomicalForwardUm,
                frame.headingDeg,
                frame.pitchDeg,
                fps,
                frame.spatialSpikeTotal,
            ),
        )
    }

    private fun linkProgram(vertexSource: String, fragmentSource: String): Int {
        val vertex = compileShader(GLES30.GL_VERTEX_SHADER, vertexSource)
        val fragment = compileShader(GLES30.GL_FRAGMENT_SHADER, fragmentSource)
        val result = GLES30.glCreateProgram()
        GLES30.glAttachShader(result, vertex)
        GLES30.glAttachShader(result, fragment)
        GLES30.glLinkProgram(result)
        val status = IntArray(1)
        GLES30.glGetProgramiv(result, GLES30.GL_LINK_STATUS, status, 0)
        GLES30.glDeleteShader(vertex)
        GLES30.glDeleteShader(fragment)
        check(status[0] == GLES30.GL_TRUE) {
            "OpenGL program link failed: ${GLES30.glGetProgramInfoLog(result)}"
        }
        return result
    }

    private fun compileShader(type: Int, source: String): Int {
        val shader = GLES30.glCreateShader(type)
        GLES30.glShaderSource(shader, source)
        GLES30.glCompileShader(shader)
        val status = IntArray(1)
        GLES30.glGetShaderiv(shader, GLES30.GL_COMPILE_STATUS, status, 0)
        check(status[0] == GLES30.GL_TRUE) {
            "OpenGL shader compile failed: ${GLES30.glGetShaderInfoLog(shader)}"
        }
        return shader
    }

    companion object {
        private const val FIXED_DT_S = 0.001
        private const val MAX_STEPS_PER_FRAME = 50
        private const val WORLD_SCALE = 0.002
        private const val VERTEX_SHADER = """
            #version 300 es
            layout(location = 0) in vec3 aPosition;
            layout(location = 1) in vec3 aNormal;
            layout(location = 2) in float aActivation;
            uniform mat4 uMvp;
            out vec3 vNormal;
            out float vActivation;
            void main() {
                gl_Position = uMvp * vec4(aPosition, 1.0);
                vNormal = aNormal;
                vActivation = clamp(aActivation, 0.0, 1.0);
            }
        """
        private const val FRAGMENT_SHADER = """
            #version 300 es
            precision mediump float;
            in vec3 vNormal;
            in float vActivation;
            out vec4 color;
            void main() {
                vec3 teal = vec3(0.28, 0.79, 0.72);
                vec3 active = vec3(0.96, 0.25, 0.48);
                vec3 lightDirection = normalize(vec3(-0.4, 0.3, 1.0));
                float diffuse = 0.38 + 0.62 * max(dot(normalize(vNormal), lightDirection), 0.0);
                color = vec4(mix(teal, active, vActivation) * diffuse, 0.97);
            }
        """
    }
}
