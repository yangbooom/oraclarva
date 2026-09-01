plugins {
    id("com.android.application")
}

android {
    namespace = "org.oraclarva.mobile"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.oraclarva.mobile"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1-stage10"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
        externalNativeBuild {
            cmake {
                arguments += "-DANDROID_STL=c++_static"
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isDebuggable = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.28.3"
        }
    }

    sourceSets {
        getByName("main").assets.srcDir("../../data/parity")
    }
}
