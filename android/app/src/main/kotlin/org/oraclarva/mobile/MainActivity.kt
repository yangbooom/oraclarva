package org.oraclarva.mobile

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import java.io.File

class MainActivity : Activity() {
    private var surface: OraclarvaSurfaceView? = null
    private var lateralGradient = 0.0
    private var verticalGradient = 0.0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val repeatFixture = materializeFixture("repeat_crawl_native_v1.tsv")
        val spatialFixture = materializeFixture("spatial_environment_native_v1.tsv")
        val root = FrameLayout(this)
        val telemetry = text(
            "Initializing native closed loop…",
            13f,
            Typeface.MONOSPACE,
        )
        telemetry.setTextColor(Color.rgb(222, 213, 226))
        telemetry.setShadowLayer(5f, 0f, 1f, Color.BLACK)
        val createdSurface = OraclarvaSurfaceView(
            this,
            repeatFixture.absolutePath,
            spatialFixture.absolutePath,
        ) { value -> runOnUiThread { telemetry.text = value } }
        surface = createdSurface
        root.addView(
            createdSurface,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            ),
        )

        val telemetryParams = FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        )
        telemetryParams.gravity = Gravity.TOP or Gravity.START
        telemetryParams.setMargins(dp(18), dp(14), dp(18), 0)
        root.addView(telemetry, telemetryParams)

        val controls = LinearLayout(this)
        controls.orientation = LinearLayout.VERTICAL
        controls.setPadding(dp(14), dp(10), dp(14), dp(10))
        controls.setBackgroundColor(Color.argb(190, 17, 13, 24))
        val heading = text(
            "PHYSICAL LIGHT FIELD · sensory input, not a heading command",
            11f,
            Typeface.MONOSPACE,
        )
        heading.setTextColor(Color.rgb(151, 207, 193))
        controls.addView(heading)
        controls.addView(fieldRow("−Y", "+Y") { value ->
            lateralGradient = value
            publishField()
        })
        controls.addView(fieldRow("−Z", "+Z") { value ->
            verticalGradient = value
            publishField()
        })
        val contact = Button(this)
        contact.text = "POSTERIOR CONTACT · 2 ms"
        contact.setOnClickListener { createdSurface.pulsePosteriorContact() }
        controls.addView(
            contact,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(42),
            ),
        )
        val boundary = text(
            "MODEL_FITTED · host parity gate · release_validated=false",
            9f,
            Typeface.MONOSPACE,
        )
        boundary.setTextColor(Color.rgb(238, 170, 101))
        controls.addView(boundary)

        val controlsParams = FrameLayout.LayoutParams(dp(410), ViewGroup.LayoutParams.WRAP_CONTENT)
        controlsParams.gravity = Gravity.BOTTOM or Gravity.END
        controlsParams.setMargins(dp(12), dp(12), dp(18), dp(16))
        root.addView(controls, controlsParams)
        setContentView(root)
    }

    override fun onResume() {
        super.onResume()
        surface?.onResume()
    }

    override fun onPause() {
        surface?.onPause()
        super.onPause()
    }

    private fun publishField() {
        surface?.setPhysicalFieldGradients(lateralGradient, verticalGradient)
    }

    private fun fieldRow(
        negative: String,
        positive: String,
        update: (Double) -> Unit,
    ): LinearLayout {
        val row = LinearLayout(this)
        row.gravity = Gravity.CENTER_VERTICAL
        row.orientation = LinearLayout.HORIZONTAL
        val left = text(negative, 11f, Typeface.MONOSPACE)
        val right = text(positive, 11f, Typeface.MONOSPACE)
        left.setTextColor(Color.LTGRAY)
        right.setTextColor(Color.LTGRAY)
        val slider = SeekBar(this)
        slider.max = 200
        slider.progress = 100
        slider.setOnSeekBarChangeListener(
            object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(
                    seekBar: SeekBar?,
                    progress: Int,
                    fromUser: Boolean,
                ) {
                    if (fromUser) update((progress - 100) * 60.0)
                }

                override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit
                override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
            },
        )
        row.addView(left, LinearLayout.LayoutParams(dp(34), dp(42)))
        row.addView(slider, LinearLayout.LayoutParams(0, dp(42), 1f))
        row.addView(right, LinearLayout.LayoutParams(dp(34), dp(42)))
        return row
    }

    private fun text(value: String, sizeSp: Float, face: Typeface): TextView {
        val result = TextView(this)
        result.text = value
        result.textSize = sizeSp
        result.typeface = face
        result.gravity = Gravity.CENTER_VERTICAL
        return result
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
}
