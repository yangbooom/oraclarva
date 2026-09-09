package org.oraclarva.mobile

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import java.io.File
import java.util.Locale

class MainActivity : Activity() {
    private var surface: OraclarvaSurfaceView? = null
    private var telemetryPanel: TextView? = null
    private var lightMarker: ImageView? = null
    private var toolMessage: TextView? = null
    private var lateralGradient = 0.0
    private var verticalGradient = 0.0
    private var latestTelemetry = "Initializing native closed loop…"
    private var simulationPaused = false
    private var observeExpanded = false
    private var lightX = 0.77f
    private var lightY = 0.39f

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestWindowFeature(Window.FEATURE_NO_TITLE)
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE

        val repeatFixture = materializeFixture("repeat_crawl_native_v1.tsv")
        val spatialFixture = materializeFixture("spatial_environment_native_v1.tsv")
        val root = FrameLayout(this).apply {
            setBackgroundColor(BLACK)
        }
        val createdSurface = OraclarvaSurfaceView(
            this,
            repeatFixture.absolutePath,
            spatialFixture.absolutePath,
            { value ->
                runOnUiThread {
                    latestTelemetry = value
                    if (observeExpanded) telemetryPanel?.text = observationCopy()
                }
            },
            { x, y -> runOnUiThread { setLightField(x, y) } },
        )
        surface = createdSurface
        root.addView(
            createdSurface,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            ),
        )

        addLightMarker(root)
        addHeader(root, createdSurface)
        addToolRail(root, createdSurface)
        addObservationPanel(root)
        addModelBadge(root)
        setContentView(root)

        root.post {
            setLightField(lightX, lightY)
        }
    }

    override fun onResume() {
        super.onResume()
        surface?.onResume()
    }

    override fun onPause() {
        surface?.onPause()
        super.onPause()
    }

    private fun addHeader(root: FrameLayout, createdSurface: OraclarvaSurfaceView) {
        val header = FrameLayout(this).apply {
            setBackgroundColor(Color.argb(222, 3, 7, 11))
            elevation = dp(8).toFloat()
        }
        root.addView(
            header,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(66),
                Gravity.TOP,
            ),
        )

        val brand = text("ORACLARVA", 20f, Typeface.create("sans-serif-light", Typeface.NORMAL)).apply {
            setTextColor(IVORY)
            letterSpacing = 0.34f
            contentDescription = "Oraclarva"
        }
        header.addView(
            brand,
            FrameLayout.LayoutParams(dp(300), ViewGroup.LayoutParams.MATCH_PARENT, Gravity.START).apply {
                marginStart = dp(36)
            },
        )

        val habitatTab = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
        }
        habitatTab.addView(
            text("HABITAT", 11f, Typeface.create("sans-serif-medium", Typeface.NORMAL)).apply {
                setTextColor(MINT)
                letterSpacing = 0.26f
                gravity = Gravity.CENTER
            },
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, 0, 1f),
        )
        habitatTab.addView(
            View(this).apply { setBackgroundColor(MINT) },
            LinearLayout.LayoutParams(dp(74), dp(1)),
        )
        header.addView(
            habitatTab,
            FrameLayout.LayoutParams(dp(180), dp(60), Gravity.CENTER),
        )

        val rightControls = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = roundedBackground(Color.argb(126, 7, 12, 17), BORDER, dp(28).toFloat())
            setPadding(dp(6), 0, dp(12), 0)
        }
        val pause = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_media_pause)
            drawable.mutate().setTint(IVORY)
            background = null
            contentDescription = "Pause simulation"
            setOnClickListener {
                simulationPaused = !simulationPaused
                createdSurface.setSimulationPaused(simulationPaused)
                setImageResource(
                    if (simulationPaused) android.R.drawable.ic_media_play
                    else android.R.drawable.ic_media_pause,
                )
                drawable.mutate().setTint(IVORY)
                contentDescription =
                    if (simulationPaused) "Resume simulation" else "Pause simulation"
                toolMessage?.apply {
                    text = if (simulationPaused) "SIMULATION PAUSED" else "LIVE CLOSED LOOP"
                    setTextColor(if (simulationPaused) WARM else MUTED)
                }
            }
        }
        rightControls.addView(pause, LinearLayout.LayoutParams(dp(48), dp(44)))
        rightControls.addView(
            View(this).apply { setBackgroundColor(BORDER) },
            LinearLayout.LayoutParams(dp(1), dp(28)),
        )
        val observe = text("OBSERVE", 11f, Typeface.create("sans-serif-medium", Typeface.NORMAL)).apply {
            setTextColor(MINT)
            letterSpacing = 0.20f
            gravity = Gravity.CENTER
            isClickable = true
            isFocusable = true
            contentDescription = "Show simulation observation details"
            setOnClickListener {
                observeExpanded = !observeExpanded
                telemetryPanel?.apply {
                    text = observationCopy()
                    visibility = if (observeExpanded) View.VISIBLE else View.GONE
                }
                alpha = if (observeExpanded) 1f else 0.82f
                contentDescription =
                    if (observeExpanded) "Hide simulation observation details"
                    else "Show simulation observation details"
            }
        }
        rightControls.addView(observe, LinearLayout.LayoutParams(dp(112), dp(44)))
        header.addView(
            rightControls,
            FrameLayout.LayoutParams(dp(180), dp(44), Gravity.END or Gravity.CENTER_VERTICAL).apply {
                marginEnd = dp(26)
            },
        )
    }

    private fun addToolRail(root: FrameLayout, createdSurface: OraclarvaSurfaceView) {
        val rail = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = roundedBackground(Color.argb(220, 3, 8, 13), BORDER, dp(24).toFloat())
            clipToOutline = true
            elevation = dp(7).toFloat()
        }
        val light = toolCard(
            label = "LIGHT",
            icon = R.drawable.ic_light_mode_24,
            selected = true,
            enabled = true,
            description = "Light tool selected. Drag on the habitat to move the physical light field.",
        )
        light.setOnClickListener {
            toolMessage?.apply {
                text = getString(R.string.drag_light_in_habitat)
                setTextColor(MINT)
            }
        }
        rail.addView(light, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        rail.addView(divider(), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(1)))

        val ground = toolCard(
            label = "GROUND",
            icon = R.drawable.ic_grain_24,
            selected = false,
            enabled = false,
            description = "Ground editing unavailable. Friction is still a fixed fitted model parameter.",
        )
        rail.addView(ground, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        rail.addView(divider(), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(1)))

        val obstacle = toolCard(
            label = "OBSTACLE",
            icon = R.drawable.ic_bubble_chart_24,
            selected = false,
            enabled = true,
            description = "Pulse a two millisecond posterior physical contact stimulus.",
        )
        obstacle.setOnClickListener {
            createdSurface.pulsePosteriorContact()
            toolMessage?.apply {
                text = getString(R.string.contact_pulse)
                setTextColor(WARM)
                postDelayed({
                    text = getString(R.string.drag_light_in_habitat)
                    setTextColor(MUTED)
                }, 1100L)
            }
        }
        rail.addView(obstacle, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        val footer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
        }
        toolMessage = text("DRAG LIGHT IN HABITAT", 7.5f, Typeface.MONOSPACE).apply {
            setTextColor(MUTED)
            letterSpacing = 0.08f
            gravity = Gravity.CENTER
            maxLines = 1
        }
        footer.addView(
            toolMessage,
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f),
        )
        footer.addView(
            pageIndicator(),
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(32)),
        )
        rail.addView(footer, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(58)))

        root.addView(
            rail,
            FrameLayout.LayoutParams(dp(124), ViewGroup.LayoutParams.MATCH_PARENT, Gravity.START).apply {
                topMargin = dp(86)
                bottomMargin = dp(24)
                marginStart = dp(22)
            },
        )
    }

    private fun addLightMarker(root: FrameLayout) {
        lightMarker = ImageView(this).apply {
            setImageResource(R.drawable.ic_light_mode_24)
            drawable.mutate().setTint(WARM)
            background = roundedBackground(Color.argb(82, 255, 200, 104), Color.argb(190, 255, 215, 132), dp(28).toFloat())
            setPadding(dp(11), dp(11), dp(11), dp(11))
            alpha = 0.9f
            isClickable = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        root.addView(lightMarker, FrameLayout.LayoutParams(dp(48), dp(48)))
    }

    private fun addObservationPanel(root: FrameLayout) {
        telemetryPanel = text(observationCopy(), 10f, Typeface.MONOSPACE).apply {
            setTextColor(Color.rgb(222, 229, 226))
            setPadding(dp(16), dp(13), dp(16), dp(13))
            background = roundedBackground(Color.argb(224, 3, 8, 13), BORDER, dp(16).toFloat())
            visibility = View.GONE
            elevation = dp(9).toFloat()
            contentDescription = "Live native simulation telemetry"
        }
        root.addView(
            telemetryPanel,
            FrameLayout.LayoutParams(dp(420), ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP or Gravity.END).apply {
                topMargin = dp(78)
                marginEnd = dp(26)
            },
        )
    }

    private fun addModelBadge(root: FrameLayout) {
        val stack = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.END
        }
        val causal = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(dp(18), 0, dp(18), 0)
            background = roundedBackground(Color.argb(214, 5, 9, 14), BORDER, dp(22).toFloat())
            contentDescription = "Environment field to sensation to body causal loop"
        }
        causal.addView(causalWord("FIELD", MINT))
        causal.addView(causalArrow())
        causal.addView(causalWord("SENSE", IVORY))
        causal.addView(causalArrow())
        causal.addView(causalWord("BODY", CORAL))
        stack.addView(causal, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(38)))
        stack.addView(
            text("RESEARCH MODEL · release_validated=false", 8f, Typeface.MONOSPACE).apply {
                setTextColor(MUTED)
                letterSpacing = 0.11f
                gravity = Gravity.END or Gravity.CENTER_VERTICAL
            },
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(28)),
        )
        root.addView(
            stack,
            FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.END or Gravity.BOTTOM).apply {
                marginEnd = dp(28)
                bottomMargin = dp(16)
            },
        )
    }

    private fun toolCard(
        label: String,
        icon: Int,
        selected: Boolean,
        enabled: Boolean,
        description: String,
    ): TextView =
        text(label, 11f, Typeface.create("sans-serif-medium", Typeface.NORMAL)).apply {
            setTextColor(if (selected) MINT else IVORY)
            letterSpacing = 0.14f
            gravity = Gravity.CENTER
            setPadding(dp(8), dp(18), dp(8), dp(14))
            setCompoundDrawablesWithIntrinsicBounds(0, icon, 0, 0)
            compoundDrawablePadding = dp(12)
            compoundDrawables[1]?.mutate()?.setTint(if (selected) MINT else Color.rgb(182, 179, 169))
            background =
                if (selected) {
                    roundedBackground(Color.argb(88, 28, 77, 74), MINT_DARK, dp(22).toFloat())
                } else {
                    null
                }
            isClickable = enabled
            isFocusable = enabled
            isEnabled = enabled
            alpha = if (enabled) 1f else 0.48f
            contentDescription = description
        }

    private fun setLightField(x: Float, y: Float) {
        lightX = x.coerceIn(0.16f, 0.96f)
        lightY = y.coerceIn(0.14f, 0.90f)
        lateralGradient = ((lightX - 0.5f) * 12_000.0).coerceIn(-6000.0, 6000.0)
        verticalGradient = ((0.5f - lightY) * 12_000.0).coerceIn(-6000.0, 6000.0)
        publishField()
        (lightMarker?.parent as? FrameLayout)?.let(::positionLightMarker)
        toolMessage?.apply {
            text = String.format(
                Locale.US,
                "FIELD  Y %+.0f · Z %+.0f",
                lateralGradient,
                verticalGradient,
            )
            setTextColor(MINT)
        }
    }

    private fun positionLightMarker(root: FrameLayout) {
        val marker = lightMarker ?: return
        marker.x = lightX * root.width - marker.width * 0.5f
        marker.y = lightY * root.height - marker.height * 0.5f
    }

    private fun publishField() {
        surface?.setPhysicalFieldGradients(lateralGradient, verticalGradient)
    }

    private fun observationCopy(): String =
        "LIVE C++ CLOSED LOOP\n$latestTelemetry\n" +
            String.format(
                Locale.US,
                "light field  Y %+.0f W/m³   Z %+.0f W/m³\n" +
                    "illustrative habitat · no movement command",
                lateralGradient,
                verticalGradient,
            )

    private fun causalWord(value: String, color: Int): TextView =
        text(value, 9f, Typeface.MONOSPACE).apply {
            setTextColor(color)
            letterSpacing = 0.12f
            gravity = Gravity.CENTER
            setPadding(dp(5), 0, dp(5), 0)
        }

    private fun causalArrow(): ImageView =
        ImageView(this).apply {
            setImageResource(android.R.drawable.ic_media_next)
            drawable.mutate().setTint(MUTED)
            setPadding(dp(2), dp(10), dp(2), dp(10))
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }.also {
            it.layoutParams = LinearLayout.LayoutParams(dp(20), dp(38))
        }

    private fun pageIndicator(): LinearLayout =
        LinearLayout(this).apply {
            gravity = Gravity.CENTER
            contentDescription = "Light tool, page one of three"
            repeat(3) { index ->
                addView(
                    ImageView(this@MainActivity).apply {
                        setImageResource(android.R.drawable.btn_radio)
                        drawable.mutate().setTint(if (index == 0) MINT else MUTED)
                        alpha = if (index == 0) 1f else 0.45f
                        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
                    },
                    LinearLayout.LayoutParams(dp(16), dp(16)).apply {
                        marginStart = dp(2)
                        marginEnd = dp(2)
                    },
                )
            }
        }

    private fun divider(): View =
        View(this).apply { setBackgroundColor(Color.argb(120, 40, 53, 61)) }

    private fun roundedBackground(fill: Int, stroke: Int, radius: Float): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            setColor(fill)
            setStroke(dp(1), stroke)
            cornerRadius = radius
        }

    private fun text(value: String, sizeSp: Float, face: Typeface): TextView =
        TextView(this).apply {
            text = value
            textSize = sizeSp
            typeface = face
            gravity = Gravity.CENTER_VERTICAL
            includeFontPadding = false
        }

    private fun materializeFixture(name: String): File {
        val directory = File(filesDir, "native-fixtures")
        check(directory.exists() || directory.mkdirs()) {
            "cannot create native fixture directory"
        }
        val target = File(directory, name)
        assets.open(name).use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        }
        return target
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density + 0.5f).toInt()

    companion object {
        private val BLACK = Color.rgb(3, 7, 11)
        private val IVORY = Color.rgb(230, 225, 215)
        private val MINT = Color.rgb(99, 215, 202)
        private val MINT_DARK = Color.rgb(41, 112, 105)
        private val CORAL = Color.rgb(235, 116, 124)
        private val WARM = Color.rgb(255, 204, 118)
        private val MUTED = Color.rgb(133, 137, 137)
        private val BORDER = Color.rgb(33, 45, 53)
    }
}
